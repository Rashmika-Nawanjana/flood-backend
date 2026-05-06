from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app


def test_create_sensor_admin_route_returns_success():
    app.dependency_overrides[routes.get_current_user] = lambda: {
        "user_id": "admin-user",
        "roles": ["admin"],
    }

    with patch("app.api.routers.admin.get_connection") as mock_conn:
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"sensor_id": "SNR-TEST-001"}
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cursor
        mock_conn.return_value = conn

        client = TestClient(app)
        response = client.post(
            "/api/v1/admin/sensors",
            json={
                "sensor_id": "SNR-TEST-001",
                "name": "Test Sensor",
                "location": {
                    "lat": 6.9271,
                    "lng": 79.8612,
                    "zone_id": "ZONE-1",
                    "address": "Test address",
                },
                "installed_date": "2026-05-01",
                "firmware_version": "v1.0.0",
                "thresholds": {
                    "watch_m": 1.2,
                    "advisory_m": 1.5,
                    "warning_m": 2.0,
                    "critical_m": 3.0,
                },
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["data"]["sensor_id"] == "SNR-TEST-001"


def test_webhook_route_accepts_clerk_events(monkeypatch):
    from app.api.routers import webhooks

    monkeypatch.setattr(
        webhooks,
        "verify_clerk_webhook",
        lambda request, payload: {
            "type": "user.created",
            "data": {
                "id": "user_abc",
                "email_addresses": [{"email_address": "test@example.com"}],
            },
        },
    )
    monkeypatch.setattr(
        webhooks,
        "get_connection",
        lambda: MagicMock(
            __enter__=lambda self: self,
            __exit__=lambda self, exc_type, exc, tb: False,
            execute=MagicMock(),
            commit=MagicMock(),
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/webhooks/clerk",
        json={"type": "user.created", "data": {"id": "user_abc"}},
        headers={
            "svix-id": "dummy",
            "svix-timestamp": "dummy",
            "svix-signature": "dummy",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["event"] == "user.created"
