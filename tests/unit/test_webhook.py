import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routers import webhooks


class DummyRequest:
    def __init__(self, headers):
        self.headers = headers


class DummyWebhook:
    def __init__(self, secret):
        self.secret = secret

    def verify(self, payload, headers):
        if not payload or headers.get("svix-signature") != "valid-signature":
            raise Exception("Invalid signature")


def test_verify_clerk_webhook_parses_valid_payload(monkeypatch):
    monkeypatch.setattr(webhooks, "Webhook", DummyWebhook)
    monkeypatch.setattr(
        webhooks, "settings", SimpleNamespace(clerk_webhook_secret=" test-secret ")
    )

    request = DummyRequest(
        {
            "svix-id": "abc",
            "svix-timestamp": "1234567890",
            "svix-signature": "valid-signature",
        }
    )
    payload = b'{"type":"user.created","data":{"id":"user_123"}}'

    result = webhooks.verify_clerk_webhook(request, payload)

    assert result["type"] == "user.created"
    assert result["data"]["id"] == "user_123"


def test_verify_clerk_webhook_raises_on_missing_headers(monkeypatch):
    monkeypatch.setattr(webhooks, "Webhook", DummyWebhook)
    monkeypatch.setattr(
        webhooks, "settings", SimpleNamespace(clerk_webhook_secret="secret")
    )

    request = DummyRequest({})
    payload = b'{"type":"user.updated","data":{}}'

    with pytest.raises(HTTPException) as exc_info:
        webhooks.verify_clerk_webhook(request, payload)

    assert exc_info.value.status_code == 400
