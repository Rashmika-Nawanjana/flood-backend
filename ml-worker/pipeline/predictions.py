from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def event_payload(event: str, data: dict) -> dict:
    return {"event": event, "timestamp": now_utc_iso(), "data": data}


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)


def get_zone_thresholds(database_url: str, zone_id: str, default_warning_m: float = 3.0, default_critical_m: float = 4.0) -> tuple[float, float]:
    """
    Fetch zone thresholds as the minimum of all sensor thresholds in the zone.
    
    Returns (warning_m, critical_m) tuple based on minimum sensor values.
    Falls back to defaults if no sensors found or if query fails.
    """
    try:
        query = """
            SELECT 
                MIN(warning_m) as min_warning_m,
                MIN(critical_m) as min_critical_m
            FROM sensor_nodes
            WHERE zone_id = %s AND is_active = TRUE
        """
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (zone_id,))
                row = cur.fetchone()
        
        if row and row["min_warning_m"] is not None and row["min_critical_m"] is not None:
            return (float(row["min_warning_m"]), float(row["min_critical_m"]))
    except Exception as e:
        print(f"WARNING: Could not fetch zone thresholds for {zone_id}: {e}. Using defaults.")
    
    return (default_warning_m, default_critical_m)


def create_kafka_producer(kafka_broker: str | None):
    if not kafka_broker:
        return None
    if KafkaProducer is None:
        raise RuntimeError("Missing dependency: kafka-python. Install with: pip install kafka-python")
    return KafkaProducer(
        bootstrap_servers=kafka_broker,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        acks="all",
        retries=3,
    )


def severity_from_peak(peak_level_m: float, warning_m: float, critical_m: float) -> str:
    if peak_level_m >= critical_m:
        return "CRITICAL"
    if peak_level_m >= warning_m:
        return "HIGH"
    if peak_level_m >= warning_m * 0.75:
        return "MEDIUM"
    return "LOW"


def color_for_severity(severity: str) -> str:
    return {
        "LOW": "#22C55E",
        "MEDIUM": "#FACC15",
        "HIGH": "#F97316",
        "CRITICAL": "#EF4444",
    }.get(severity, "#9CA3AF")


def summarize_zone_prediction(
    zone_id: str,
    zone_name: str,
    df_pred: pd.DataFrame,
    database_url: str,
    default_warning_m: float = 3.0,
    default_critical_m: float = 4.0,
) -> dict:
    """
    Summarize zone predictions using zone-specific thresholds fetched from sensor_nodes.
    
    Thresholds are computed as the minimum of all active sensors in the zone (conservative approach).
    Falls back to environment defaults if sensors are not found.
    """
    # Fetch zone thresholds from sensor data (minimum across all sensors in zone)
    warning_m, critical_m = get_zone_thresholds(
        database_url, zone_id, default_warning_m, default_critical_m
    )
    
    latest = df_pred.iloc[-1]
    horizon_cols = [col for col in df_pred.columns if col.startswith("y_pred_t_plus_")]
    valid_horizons = []
    for col in horizon_cols:
        value = latest[col]
        if pd.isna(value):
            continue
        minutes = int(col.split("_t_plus_")[-1])
        valid_horizons.append((minutes, float(value), col))

    if not valid_horizons:
        raise ValueError(f"No prediction values available for zone {zone_id}")

    peak_minutes, peak_level_m, _ = max(valid_horizons, key=lambda item: item[1])
    severity = severity_from_peak(peak_level_m, warning_m, critical_m)
    risk_score = round(min(100.0, max(0.0, (peak_level_m / critical_m) * 100.0)), 1)

    time_raw = str(latest["TimeStamp"])
    try:
        base_ts = datetime.fromisoformat(time_raw.replace("Z", "+00:00"))
    except ValueError:
        base_ts = datetime.now(timezone.utc)
    if base_ts.tzinfo is None:
        base_ts = base_ts.replace(tzinfo=timezone.utc)
    estimated_flood_time = (base_ts + timedelta(minutes=peak_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

    prediction_id = f"PRED-{safe_name(zone_id)}-{int(datetime.now(timezone.utc).timestamp())}"
    return {
        "prediction_id": prediction_id,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "predicted_peak_level_m": round(peak_level_m, 4),
        "estimated_flood_time": estimated_flood_time,
        "severity": severity,
        "risk_score": risk_score,
        "color_code": color_for_severity(severity),
        "peak_horizon_minutes": peak_minutes,
    }


def publish_zone_events(producer, analytics_topic: str, alerts_topic: str, summary: dict) -> None:
    producer.send(
        analytics_topic,
        event_payload(
            "zone:risk:update",
            {
                "zone_id": summary["zone_id"],
                "zone_name": summary["zone_name"],
                "previous_level": "UNKNOWN",
                "current_level": summary["severity"],
                "risk_score": summary["risk_score"],
                "color_code": summary["color_code"],
            },
        ),
    )

    producer.send(
        analytics_topic,
        event_payload(
            "prediction:new",
            {
                "prediction_id": summary["prediction_id"],
                "zone_id": summary["zone_id"],
                "zone_name": summary["zone_name"],
                "predicted_peak_level_m": summary["predicted_peak_level_m"],
                "estimated_flood_time": summary["estimated_flood_time"],
                "severity": summary["severity"],
                "top_risk_factors": [
                    {
                        "factor": "Predicted Peak Water Level",
                        "value": f"{summary['predicted_peak_level_m']}m",
                        "impact": "High" if summary["severity"] in {"HIGH", "CRITICAL"} else "Medium",
                    }
                ],
            },
        ),
    )

    if summary["severity"] in {"HIGH", "CRITICAL"}:
        producer.send(
            alerts_topic,
            event_payload(
                "alert:new",
                {
                    "alert_id": f"ALT-{safe_name(summary['zone_id'])}-{int(datetime.now(timezone.utc).timestamp())}",
                    "zone_id": summary["zone_id"],
                    "severity": summary["severity"],
                    "title": f"Flood risk {summary['severity']} in {summary['zone_name']}",
                    "message": "Predicted water levels indicate elevated flood risk. Review preparedness actions.",
                    "recommended_action": "EVACUATE" if summary["severity"] == "CRITICAL" else "PREPARE",
                    "recommended_shelters": [],
                },
            ),
        )


def write_prediction_return_id(database_url: str, model_id: int, zone_id: str, water_level: dict) -> int:
    insert = """
        INSERT INTO flood_predictions (zone_id, model_id, water_level)
        VALUES (%s, %s, %s)
        RETURNING prediction_id
    """
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(insert, (zone_id, model_id, Json(water_level)))
            row = cur.fetchone()
            conn.commit()
            return int(row["prediction_id"])


def publish_zone_events(producer, analytics_topic: str, alerts_topic: str, summary: dict, database_url: str | None = None) -> None:
    producer.send(
        analytics_topic,
        event_payload(
            "zone:risk:update",
            {
                "zone_id": summary["zone_id"],
                "zone_name": summary["zone_name"],
                "previous_level": "UNKNOWN",
                "current_level": summary["severity"],
                "risk_score": summary["risk_score"],
                "color_code": summary["color_code"],
            },
        ),
    )

    producer.send(
        analytics_topic,
        event_payload(
            "prediction:new",
            {
                "prediction_id": summary.get("prediction_id"),
                "zone_id": summary["zone_id"],
                "zone_name": summary["zone_name"],
                "predicted_peak_level_m": summary["predicted_peak_level_m"],
                "estimated_flood_time": summary["estimated_flood_time"],
                "severity": summary["severity"],
                "top_risk_factors": [
                    {
                        "factor": "Predicted Peak Water Level",
                        "value": f"{summary['predicted_peak_level_m']}m",
                        "impact": "High" if summary["severity"] in {"HIGH", "CRITICAL"} else "Medium",
                    }
                ],
            },
        ),
    )

    if summary["severity"] in {"HIGH", "CRITICAL"}:
        alert_id = f"ALT-{safe_name(summary['zone_id'])}-{int(datetime.now(timezone.utc).timestamp())}"
        producer.send(
            alerts_topic,
            event_payload(
                "alert:new",
                {
                    "alert_id": alert_id,
                    "zone_id": summary["zone_id"],
                    "severity": summary["severity"],
                    "title": f"Flood risk {summary['severity']} in {summary['zone_name']}",
                    "message": "Predicted water levels indicate elevated flood risk. Review preparedness actions.",
                    "recommended_action": "EVACUATE" if summary["severity"] == "CRITICAL" else "PREPARE",
                    "recommended_shelters": [],
                },
            ),
        )

        # persist alert event linking to prediction if database_url and prediction_db_id available
        try:
            pred_db_id = summary.get("prediction_db_id")
            if database_url and pred_db_id is not None:
                insert_alert = """
                    INSERT INTO alert_events (prediction_id, triggered_at)
                    VALUES (%s, NOW())
                """
                with psycopg.connect(database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute(insert_alert, (int(pred_db_id),))
                    conn.commit()
        except Exception:
            # persistence errors should not stop event publishing
            pass


def resolve_model_id(database_url: str, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    if not database_url:
        raise ValueError("database_url is required to resolve model_id")

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT model_id
                FROM model_metadata
                WHERE deployed_at IS NOT NULL
                ORDER BY deployed_at DESC, trained_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                return int(row["model_id"])

            cur.execute(
                """
                SELECT model_id
                FROM model_metadata
                ORDER BY trained_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                return int(row["model_id"])

    raise ValueError("No model_metadata entries available to resolve model_id")


def build_water_level_payload(df: pd.DataFrame) -> dict:
    horizon_cols = [col for col in df.columns if col.startswith("y_pred_t_plus_")]
    horizons = [int(col.split("_t_plus_")[-1]) for col in horizon_cols]

    records = []
    for _, row in df.iterrows():
        entry = {"timestamp": row["TimeStamp"]}
        for col in horizon_cols:
            value = row[col]
            entry[col] = None if pd.isna(value) else float(value)
        records.append(entry)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "horizons": sorted(horizons),
        "records": records,
    }


def write_predictions_to_db(database_url: str, model_id: int, payloads: list[dict]) -> None:
    if not payloads:
        return

    insert = """
        INSERT INTO flood_predictions (zone_id, model_id, water_level)
        VALUES (%s, %s, %s)
    """
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for item in payloads:
                cur.execute(
                    insert,
                    (item["zone_id"], model_id, Json(item["water_level"])),
                )
        conn.commit()


def update_zone_risk_status(database_url: str, summary: dict) -> None:
    """
    Update zone risk status (risk_score, risk_level, color_code, last_updated) based on prediction summary.
    Increment active_alerts if severity is HIGH or CRITICAL.
    
    Called after predictions are written to synchronize zone table with latest risk data.
    """
    if not database_url or not summary:
        return
    
    zone_id = summary.get("zone_id")
    severity = summary.get("severity")
    prediction_payload = {
        "flood_probability_percent": round(min(100.0, max(0.0, summary.get("risk_score", 0.0))), 1),
        "predicted_peak_level_m": summary.get("predicted_peak_level_m"),
        "estimated_flood_time": summary.get("estimated_flood_time"),
        "confidence_percent": None,
        "model_version": summary.get("model_version"),
    }
    
    # If HIGH or CRITICAL, increment active_alerts
    increment_alerts = 1 if severity in {"HIGH", "CRITICAL"} else 0
    
    update_query = """
        UPDATE zones
        SET 
            risk_score = %s,
            risk_level = %s,
            color_code = %s,
            prediction = %s,
            active_alerts = CASE 
                WHEN %s > 0 THEN active_alerts + %s
                ELSE active_alerts
            END,
            last_updated = NOW()
        WHERE zone_id = %s
    """
    
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    update_query,
                    (
                        summary.get("risk_score"),
                        severity,
                        summary.get("color_code"),
                        Json(prediction_payload),
                        increment_alerts,
                        increment_alerts,
                        zone_id,
                    ),
                )
            conn.commit()
            if increment_alerts > 0:
                print(f"Zone {zone_id} alert count incremented due to {severity} prediction")
    except Exception as e:
        print(f"WARNING: Could not update zone risk status for {zone_id}: {e}")