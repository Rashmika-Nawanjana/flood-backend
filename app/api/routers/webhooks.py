"""
Clerk Webhook Handler
Syncs Clerk user lifecycle events → PostgreSQL users table.

Events handled:
  user.created  → INSERT (ON CONFLICT DO NOTHING to avoid duplicates)
  user.updated  → UPDATE email, full_name, role, zone_id, updated_at
  user.deleted  → soft-delete (is_active = false)
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from svix import Webhook, WebhookVerificationError

from app.core.config import settings
from app.db.pg import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


# ── Helpers ──────────────────────────────────────────────────────────


def _extract_user_fields(data: dict) -> dict:
    """Extract normalised user fields from a Clerk webhook event payload."""
    email_addresses = data.get("email_addresses", [])
    email = (
        email_addresses[0].get("email_address", "") if email_addresses else ""
    )

    first_name = data.get("first_name") or ""
    last_name = data.get("last_name") or ""
    full_name = f"{first_name} {last_name}".strip() or None

    public_metadata = data.get("public_metadata") or {}
    role = public_metadata.get("role", "citizen")
    zone_id = public_metadata.get("zone_id") or None

    return {
        "clerk_id": data.get("id"),
from fastapi import APIRouter, HTTPException, Request, status
from svix import Webhook, WebhookVerificationError

from app.core.config import settings
from app.db.pg import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


# ── Helpers ──────────────────────────────────────────────────────────


def _extract_user_fields(data: dict) -> dict:
    """Extract normalised user fields from a Clerk webhook event payload."""
    email_addresses = data.get("email_addresses", [])
    email = (
        email_addresses[0].get("email_address", "") if email_addresses else ""
    )

    first_name = data.get("first_name") or ""
    last_name = data.get("last_name") or ""
    full_name = f"{first_name} {last_name}".strip() or None

    public_metadata = data.get("public_metadata") or {}
    role = public_metadata.get("role", "citizen")
    zone_id = public_metadata.get("zone_id") or None

    return {
        "clerk_id": data.get("id"),
        "email": email,
        "full_name": full_name,
        "role": role,
        "zone_id": zone_id,
    }


def _verify_webhook(request: Request, payload: bytes) -> dict:
    """Verify the Clerk webhook signature via svix, return parsed body."""
    secret = settings.clerk_webhook_secret.strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_WEBHOOK_SECRET is not configured",
        )

    svix_id = request.headers.get("svix-id")
    svix_timestamp = request.headers.get("svix-timestamp")
    svix_signature = request.headers.get("svix-signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Clerk webhook signature headers",
        )

    try:
        wh = Webhook(secret)
        wh.verify(
            payload.decode("utf-8"),
            {
                "svix-id": svix_id,
                "svix-timestamp": svix_timestamp,
                "svix-signature": svix_signature,
            },
        )
    except WebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Clerk webhook signature",
        ) from exc

    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        ) from exc


# ── Endpoint ─────────────────────────────────────────────────────────


@router.post("/clerk")
async def clerk_webhook(request: Request) -> dict:
    """
    Receives Clerk webhook events and syncs user data to PostgreSQL.
    Configure this URL in your Clerk Dashboard → Webhooks.
    """
    payload = await request.body()

    # Signature verification — raises 400 on failure
    payload_data = _verify_webhook(request, payload)

    event_type = payload_data.get("type")
    data = payload_data.get("data", {})

    if not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event type",
        )

    try:
        with get_connection() as conn:
            if event_type == "user.created":
                fields = _extract_user_fields(data)
                conn.execute(
                    """
                    INSERT INTO users
                        (clerk_id, email, full_name, role, zone_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (clerk_id) DO NOTHING
                    """,
                    (
                        fields["clerk_id"],
                        fields["email"],
                        fields["full_name"],
                        fields["role"],
                        fields["zone_id"],
                    ),
                )
                logger.info(
                    "user.created → %s (%s)", fields["clerk_id"], fields["email"]
                )

            elif event_type == "user.updated":
                fields = _extract_user_fields(data)
                conn.execute(
                    """
                    UPDATE users
                    SET email      = %s,
                        full_name  = %s,
                        role       = %s,
                        zone_id    = %s,
                        updated_at = NOW()
                    WHERE clerk_id = %s
                    """,
                    (
                        fields["email"],
                        fields["full_name"],
                        fields["role"],
                        fields["zone_id"],
                        fields["clerk_id"],
                    ),
                )
                logger.info(
                    "user.updated → %s (%s)", fields["clerk_id"], fields["email"]
                )

            elif event_type == "user.deleted":
                clerk_id = data.get("id")
                conn.execute(
                    """
                    UPDATE users
                    SET is_active = FALSE, updated_at = NOW()
                    WHERE clerk_id = %s
                    """,
                    (clerk_id,),
                )
                logger.info("user.deleted → soft-deleted %s", clerk_id)

            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unrecognised event type: {event_type}",
                )

            conn.commit()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Webhook DB sync failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database sync failed",
        ) from exc

    return {"status": "ok", "event": event_type}
