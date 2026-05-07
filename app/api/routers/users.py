"""
User Management Endpoints (admin-only)

CRUD operations for user accounts — synced with Clerk and PostgreSQL.

Endpoints:
  POST   /api/admin/users              Create a new user
  GET    /api/admin/users              List all users
  PATCH  /api/admin/users/{clerk_id}   Update user details
  DELETE /api/admin/users/{clerk_id}   Soft-delete (deactivate)
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.auth.clerk import require_roles
from app.core.config import settings
from app.db.pg import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/users",
    tags=["user-management"],
    dependencies=[Depends(require_roles(["admin"]))],
)

CLERK_API_BASE = "https://api.clerk.com/v1"


# ── Request Models ───────────────────────────────────────────────────


class UserCreatePayload(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    zone_id: Optional[str] = None


class UserUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    zone_id: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────


def _clerk_headers() -> dict:
    """Authorization headers for Clerk Backend API."""
    return {
        "Authorization": f"Bearer {settings.clerk_secret_key}",
        "Content-Type": "application/json",
    }


def _validate_zone_rules(role: str, zone_id: Optional[str]) -> None:
    """Enforce zone_id business rules per role."""
    if role == "admin" and zone_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin users must not have a zone_id.",
        )
    if role == "field_officer" and not zone_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field officers must be assigned a zone_id.",
        )
    if role == "citizen" and zone_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Citizen users must not have a zone_id.",
        )


def _split_name(full_name: str) -> tuple[str, str]:
    """Split 'Kasun Perera' → ('Kasun', 'Perera')."""
    parts = full_name.strip().split(None, 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def _iso(dt) -> str | None:
    """Convert a datetime to ISO-8601 string."""
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _serialize_user(row: dict) -> dict:
    """Normalise a database row into an API-friendly dict."""
    return {
        "clerk_id": row["clerk_id"],
        "full_name": row.get("full_name"),
        "email": row["email"],
        "role": row.get("role", "citizen"),
        "zone_id": row.get("zone_id"),
        "is_active": row.get("is_active", True),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


# ── POST /api/admin/users ───────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreatePayload) -> dict:
    """
    Create a user in Clerk first, then insert into PostgreSQL.

    Atomicity: if the Postgres INSERT fails the Clerk user is deleted
    so the two systems never drift out of sync.
    """
    _validate_zone_rules(payload.role, payload.zone_id)

    first_name, last_name = _split_name(payload.full_name)

    # ── Step 1: Create user in Clerk ─────────────────────────────────
    clerk_body = {
        "first_name": first_name,
        "last_name": last_name,
        "email_address": [payload.email],
        "password": payload.password,
        "public_metadata": {
            "role": payload.role,
            "zone_id": payload.zone_id,
        },
    }

    with httpx.Client(timeout=15) as client:
        clerk_resp = client.post(
            f"{CLERK_API_BASE}/users",
            headers=_clerk_headers(),
            json=clerk_body,
        )

    if clerk_resp.status_code != 200:
        detail = clerk_resp.json().get("errors", clerk_resp.text)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clerk user creation failed: {detail}",
        )

    clerk_data = clerk_resp.json()
    clerk_id = clerk_data["id"]

    # ── Step 2: Insert into PostgreSQL ───────────────────────────────
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users
                        (clerk_id, email, full_name, role, zone_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (clerk_id) DO NOTHING
                    RETURNING *
                    """,
                    (
                        clerk_id,
                        payload.email,
                        payload.full_name,
                        payload.role,
                        payload.zone_id,
                    ),
                )
                row = cur.fetchone()

                # If ON CONFLICT hit (webhook already inserted), fetch the row
                if row is None:
                    cur.execute(
                        "SELECT * FROM users WHERE clerk_id = %s", (clerk_id,)
                    )
                    row = cur.fetchone()

    except Exception as exc:
        # ── Step 3: Atomicity — roll back Clerk user on PG failure ───
        logger.error(
            "PG insert failed for %s, rolling back Clerk user: %s",
            clerk_id,
            exc,
        )
        try:
            with httpx.Client(timeout=10) as client:
                client.delete(
                    f"{CLERK_API_BASE}/users/{clerk_id}",
                    headers=_clerk_headers(),
                )
        except Exception as rollback_exc:
            logger.error("Clerk rollback also failed: %s", rollback_exc)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation failed — rolled back Clerk user.",
        ) from exc

    return {
        "status": "success",
        "message": f"User {payload.email} has been successfully created.",
        "data": _serialize_user(row),
    }


# ── GET /api/admin/users ────────────────────────────────────────────


@router.get("")
def list_users() -> dict:
    """Return all rows from the users table."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = cur.fetchall()

    return {
        "status": "success",
        "count": len(rows),
        "data": [_serialize_user(r) for r in rows],
    }


# ── PATCH /api/admin/users/{clerk_id} ───────────────────────────────


@router.patch("/{clerk_id}")
def update_user(clerk_id: str, payload: UserUpdatePayload) -> dict:
    """
    Update role, full_name, and/or zone_id in both Clerk and PostgreSQL.
    Enforces the same zone_id business rules as POST.
    """
    # Fetch current user
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE clerk_id = %s", (clerk_id,))
            existing = cur.fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    # Merge payload with existing values
    new_full_name = (
        payload.full_name
        if payload.full_name is not None
        else existing["full_name"]
    )
    new_role = (
        payload.role if payload.role is not None else existing["role"]
    )

    # Determine zone_id: explicit payload value wins, otherwise keep existing.
    # If role is changing to admin/citizen, zone_id must be cleared.
    if payload.zone_id is not None:
        new_zone_id = payload.zone_id
    elif payload.role in ("admin", "citizen"):
        new_zone_id = None
    else:
        new_zone_id = existing.get("zone_id")

    _validate_zone_rules(new_role, new_zone_id)

    # ── Update Clerk ─────────────────────────────────────────────────
    first_name, last_name = _split_name(new_full_name or "")
    clerk_body = {
        "first_name": first_name,
        "last_name": last_name,
        "public_metadata": {
            "role": new_role,
            "zone_id": new_zone_id,
        },
    }

    with httpx.Client(timeout=15) as client:
        clerk_resp = client.patch(
            f"{CLERK_API_BASE}/users/{clerk_id}",
            headers=_clerk_headers(),
            json=clerk_body,
        )

    if clerk_resp.status_code != 200:
        detail = clerk_resp.json().get("errors", clerk_resp.text)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clerk user update failed: {detail}",
        )

    # ── Update PostgreSQL ────────────────────────────────────────────
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET full_name  = %s,
                    role       = %s,
                    zone_id    = %s,
                    updated_at = NOW()
                WHERE clerk_id = %s
                RETURNING *
                """,
                (new_full_name, new_role, new_zone_id, clerk_id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=404, detail="User not found after update"
        )

    return {
        "status": "success",
        "message": f"User {clerk_id} has been successfully updated.",
        "data": _serialize_user(row),
    }


# ── DELETE /api/admin/users/{clerk_id} ──────────────────────────────


@router.delete("/{clerk_id}")
def deactivate_user(clerk_id: str) -> dict:
    """Soft delete — set is_active = false. Do NOT delete from Clerk."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET is_active  = FALSE,
                    updated_at = NOW()
                WHERE clerk_id = %s
                RETURNING updated_at
                """,
                (clerk_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "status": "success",
        "message": f"User {clerk_id} has been successfully deactivated.",
        "deactivated_at": _iso(row["updated_at"]),
        "note": "User record preserved in PostgreSQL. is_active set to false.",
    }
