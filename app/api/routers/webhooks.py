"""
Clerk Webhook Handler
Syncs Clerk user lifecycle events → PostgreSQL users table.
Events: user.created, user.updated, user.deleted
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from svix import Webhook, WebhookVerificationError

from app.core.config import settings
from app.db.pg import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


def verify_clerk_webhook(request: Request, payload: bytes) -> dict:
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
        webhook = Webhook(secret)
        webhook.verify(
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


@router.post("/clerk")
async def clerk_webhook(request: Request) -> dict:
    """
    Receives Clerk webhook events and syncs user data to PostgreSQL.
    Configure this URL in your Clerk Dashboard → Webhooks.
    """
    payload = await request.body()

    try:
        payload_data = verify_clerk_webhook(request, payload)
    except HTTPException:
        raise

    event_type = payload_data.get("type")
    data = payload_data.get("data", {})

    if not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event type",
        )

    clerk_id = data.get("id")
    email_addresses = data.get("email_addresses", [])
    primary_email_id = data.get("primary_email_address_id")
    email = next(
        (
            e.get("email_address")
            for e in email_addresses
            if e.get("id") == primary_email_id
        ),
        email_addresses[0].get("email_address") if email_addresses else "",
    )
    first_name = data.get("first_name", "") or ""
    last_name = data.get("last_name", "") or ""
    full_name = f"{first_name} {last_name}".strip() or email
    public_metadata = data.get("public_metadata", {}) or {}
    role = public_metadata.get("role", "citizen")

    try:
        with get_connection() as conn:
            if event_type == "user.created":
                conn.execute(
                    """
                    INSERT INTO users (clerk_id, email, full_name, role, is_active)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (clerk_id) DO UPDATE
                    SET email = EXCLUDED.email,
                        full_name = EXCLUDED.full_name,
                        role = EXCLUDED.role,
                        is_active = TRUE
                    """,
                    (clerk_id, email, full_name, role),
                )
                logger.info("User created/synced: %s (%s)", clerk_id, email)

            elif event_type == "user.updated":
                conn.execute(
                    """
                    UPDATE users
                    SET email = %s, full_name = %s, role = %s
                    WHERE clerk_id = %s
                    """,
                    (email, full_name, role, clerk_id),
                )
                logger.info("User updated: %s (%s)", clerk_id, email)

            elif event_type == "user.deleted":
                conn.execute(
                    "UPDATE users SET is_active = FALSE WHERE clerk_id = %s",
                    (clerk_id,),
                )
                logger.info("User soft-deleted: %s", clerk_id)

            conn.commit()

    except Exception as exc:
        # Log but don't fail — DB might not have users table yet
        logger.warning("Webhook DB sync failed (non-fatal): %s", exc)

    return {"status": "ok", "event": event_type}
