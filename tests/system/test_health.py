from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "flood-backend"


def test_api_ping_is_available():
    client = TestClient(app)
    response = client.get("/api/ping")

    assert response.status_code == 200
    assert response.json()["message"] == "pong"
