from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, Query

router = APIRouter(prefix="/v1", tags=["intelligence"])


def _to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_water_level_json(wlvl: dict[str, Any]) -> dict:
    records = wlvl.get("records", []) if isinstance(wlvl, dict) else []
    if not records:
        return {}
    latest = records[-1]
    horizon_cols = [k for k in latest.keys() if k.startswith("y_pred_t_plus_")]
    valid = []
    for col in horizon_cols:
        v = latest.get(col)
        if v is None:
            continue
        try:
            minutes = int(col.split("_t_plus_")[-1])
        except Exception:
            continue
        valid.append((minutes, float(v)))
    if not valid:
        return {}
    peak_minutes, peak_level = max(valid, key=lambda x: x[1])
    ts_raw = latest.get("timestamp")
    try:
        base = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
    except Exception:
        base = datetime.now(timezone.utc)
    estimated = (base + timedelta(minutes=peak_minutes)).astimezone(timezone.utc)
    return {
        "predicted_peak_level_m": round(float(peak_level), 4),
        "estimated_flood_time": _to_iso(estimated),
        "peak_horizon_minutes": int(peak_minutes),
    }


def _get_db_conn():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return psycopg.connect(dsn, row_factory=dict_row)


@router.get("/predictions")
def list_predictions(
    severity: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    limit: int = Query(default=50),
) -> dict:
    rows: list[dict] = []
    with _get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT fp.prediction_id, fp.zone_id, z.zone_name, fp.water_level, fp.model_id, fp.created_at
                FROM flood_predictions fp
                LEFT JOIN zones z ON fp.zone_id = z.zone_id
                ORDER BY fp.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = list(cur.fetchall())

    results = []
    for r in rows:
        wl = r.get("water_level") or {}
        summary = _parse_water_level_json(wl)
        if not summary:
            continue

        model_version = None
        model_id = r.get("model_id")
        if model_id:
            try:
                with _get_db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT version FROM model_metadata WHERE model_id = %s", (model_id,))
                        meta = cur.fetchone()
                        if meta:
                            model_version = meta.get("version")
            except Exception:
                model_version = None

        pk = summary.get("predicted_peak_level_m")
        severity_value = "UNKNOWN"
        if pk is None:
            severity_value = "UNKNOWN"
        else:
            if pk >= 5.0:
                severity_value = "CRITICAL"
            elif pk >= 4.0:
                severity_value = "HIGH"
            elif pk >= 2.0:
                severity_value = "MEDIUM"
            else:
                severity_value = "LOW"

        item = {
            "prediction_id": r.get("prediction_id"),
            "zone_id": r.get("zone_id"),
            "zone_name": r.get("zone_name"),
            "created_at": _to_iso(r.get("created_at")),
            "prediction_window": {"from": wl.get("generated_at"), "to": None},
            "flood_probability_percent": None,
            "predicted_peak_level_m": summary.get("predicted_peak_level_m"),
            "estimated_flood_time": summary.get("estimated_flood_time"),
            "severity": severity_value,
            "confidence_percent": None,
            "model_version": model_version,
            "top_risk_factors": [
                {"factor": "Predicted Peak Water Level", "value": f"{summary.get('predicted_peak_level_m')}m", "impact": "High"}
            ],
        }

        results.append(item)

    if severity:
        wanted = {s.strip().upper() for s in severity.split(",") if s.strip()}
        results = [x for x in results if x.get("severity") in wanted]
    if zone_id:
        results = [x for x in results if x.get("zone_id") == zone_id]
    if timeframe == "next_24h":
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=24)

        def in_window(it):
            eft = it.get("estimated_flood_time")
            if not eft:
                return False
            try:
                t = datetime.fromisoformat(eft.replace("Z", "+00:00"))
                return now <= t <= cutoff
            except Exception:
                return False

        results = [x for x in results if in_window(x)]

    return {"status": "success", "count": len(results), "data": results}


@router.get("/alerts")
def list_alerts(limit: int = Query(default=50)) -> dict:
    with _get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ae.alert_id, ae.triggered_at, fp.prediction_id, fp.zone_id, z.zone_name, fp.water_level
                FROM alert_events ae
                LEFT JOIN flood_predictions fp ON ae.prediction_id = fp.prediction_id
                LEFT JOIN zones z ON fp.zone_id = z.zone_id
                ORDER BY ae.triggered_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = list(cur.fetchall())

    alerts = []
    for r in rows:
        wl = r.get("water_level") or {}
        summary = _parse_water_level_json(wl)
        severity = "UNKNOWN"
        pk = summary.get("predicted_peak_level_m")
        if pk is not None:
            if pk >= 5.0:
                severity = "CRITICAL"
            elif pk >= 4.0:
                severity = "HIGH"
            elif pk >= 2.0:
                severity = "MEDIUM"
            else:
                severity = "LOW"
        alerts.append(
            {
                "alert_id": r.get("alert_id"),
                "zone_id": r.get("zone_id"),
                "zone_name": r.get("zone_name"),
                "source_prediction_id": r.get("prediction_id"),
                "severity": severity,
                "severity_code": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(severity, 0),
                "title": f"Automated alert ({severity}) for {r.get('zone_name')}",
                "message": "Automated alert generated by intelligence service.",
                "triggered_at": _to_iso(r.get("triggered_at")),
                "triggered_by": "XGBOOST_AUTOMATED",
                "status": "ACTIVE",
                "resolved_at": None,
                "affected_population": None,
                "recommended_action": "EVACUATE" if severity == "CRITICAL" else "PREPARE",
                "recommended_shelters": [],
                "notifications_sent": {"push": 0, "sms": 0, "email": 0},
            }
        )

    return {"status": "success", "count": len(alerts), "data": alerts}


@router.get("/zones/{zone_id}/alerts")
def list_zone_alerts(
    zone_id: str,
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50),
) -> dict:
    with _get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ae.alert_id, ae.triggered_at, fp.prediction_id, fp.zone_id, z.zone_name, fp.water_level
                FROM alert_events ae
                LEFT JOIN flood_predictions fp ON ae.prediction_id = fp.prediction_id
                LEFT JOIN zones z ON fp.zone_id = z.zone_id
                WHERE fp.zone_id = %s
                ORDER BY ae.triggered_at DESC
                LIMIT %s
                """,
                (zone_id, limit),
            )
            rows = list(cur.fetchall())

    alerts = []
    for r in rows:
        wl = r.get("water_level") or {}
        summary = _parse_water_level_json(wl)
        pk = summary.get("predicted_peak_level_m")
        sev = "UNKNOWN"
        if pk is not None:
            if pk >= 5.0:
                sev = "CRITICAL"
            elif pk >= 4.0:
                sev = "HIGH"
            elif pk >= 2.0:
                sev = "MEDIUM"
            else:
                sev = "LOW"

        alerts.append(
            {
                "alert_id": r.get("alert_id"),
                "zone_id": r.get("zone_id"),
                "zone_name": r.get("zone_name"),
                "source_prediction_id": r.get("prediction_id"),
                "severity": sev,
                "severity_code": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(sev, 0),
                "title": f"Automated alert ({sev}) for {r.get('zone_name')}",
                "message": "Automated alert generated by intelligence service.",
                "triggered_at": _to_iso(r.get("triggered_at")),
                "triggered_by": "XGBOOST_AUTOMATED",
                "status": "ACTIVE",
                "resolved_at": None,
                "affected_population": None,
                "recommended_action": "EVACUATE" if sev == "CRITICAL" else "PREPARE",
                "recommended_shelters": [],
                "notifications_sent": {"push": 0, "sms": 0, "email": 0},
            }
        )

    # apply filters
    if status:
        wanted = {s.strip().upper() for s in status.split(",") if s.strip()}
        alerts = [a for a in alerts if a.get("status") in wanted]
    if severity:
        wanted = {s.strip().upper() for s in severity.split(",") if s.strip()}
        alerts = [a for a in alerts if a.get("severity") in wanted]

    return {
        "status": "success",
        "zone_id": zone_id,
        "zone_name": rows[0].get("zone_name") if rows else None,
        "count": len(alerts),
        "data": alerts,
    }


@router.get("/zones/{zone_id}/predictions")
def list_zone_predictions(
    zone_id: str,
    severity: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    limit: int = Query(default=50),
) -> dict:
    rows: list[dict] = []
    with _get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT fp.prediction_id, fp.zone_id, z.zone_name, fp.water_level, fp.model_id, fp.created_at
                FROM flood_predictions fp
                LEFT JOIN zones z ON fp.zone_id = z.zone_id
                WHERE fp.zone_id = %s
                ORDER BY fp.created_at DESC
                LIMIT %s
                """,
                (zone_id, limit),
            )
            rows = list(cur.fetchall())

    results = []
    for r in rows:
        wl = r.get("water_level") or {}
        summary = _parse_water_level_json(wl)
        if not summary:
            continue

        model_version = None
        model_id = r.get("model_id")
        if model_id:
            try:
                with _get_db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT version FROM model_metadata WHERE model_id = %s", (model_id,))
                        meta = cur.fetchone()
                        if meta:
                            model_version = meta.get("version")
            except Exception:
                model_version = None

        pk = summary.get("predicted_peak_level_m")
        severity_value = "UNKNOWN"
        if pk is None:
            severity_value = "UNKNOWN"
        else:
            if pk >= 5.0:
                severity_value = "CRITICAL"
            elif pk >= 4.0:
                severity_value = "HIGH"
            elif pk >= 2.0:
                severity_value = "MEDIUM"
            else:
                severity_value = "LOW"

        item = {
            "prediction_id": r.get("prediction_id"),
            "zone_id": r.get("zone_id"),
            "zone_name": r.get("zone_name"),
            "created_at": _to_iso(r.get("created_at")),
            "prediction_window": {"from": wl.get("generated_at"), "to": None},
            "flood_probability_percent": None,
            "predicted_peak_level_m": summary.get("predicted_peak_level_m"),
            "estimated_flood_time": summary.get("estimated_flood_time"),
            "severity": severity_value,
            "confidence_percent": None,
            "model_version": model_version,
            "top_risk_factors": [
                {"factor": "Predicted Peak Water Level", "value": f"{summary.get('predicted_peak_level_m')}m", "impact": "High"}
            ],
        }

    return {"status": "success", "count": len(alerts), "data": alerts}


        results.append(item)

    if severity:
        wanted = {s.strip().upper() for s in severity.split(",") if s.strip()}
        results = [x for x in results if x.get("severity") in wanted]
    if timeframe == "next_24h":
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=24)

        def in_window(it):
            eft = it.get("estimated_flood_time")
            if not eft:
                return False
            try:
                t = datetime.fromisoformat(eft.replace("Z", "+00:00"))
                return now <= t <= cutoff
            except Exception:
                return False

        results = [x for x in results if in_window(x)]

    return {
        "status": "success",
        "zone_id": zone_id,
        "zone_name": rows[0].get("zone_name") if rows else None,
        "count": len(results),
        "data": results,
    }
