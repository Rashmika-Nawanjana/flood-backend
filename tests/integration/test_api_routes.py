from fastapi.testclient import TestClient

import app.api.routes as routes
import app.auth.clerk as clerk
from app.main import app


def test_ping_endpoint_returns_pong():
    client = TestClient(app)
    response = client.get("/api/ping")

    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


def test_auth_me_returns_authenticated_user():
    app.dependency_overrides[routes.get_current_user] = lambda: {
        "user_id": "integration-user",
        "username": "integration",
        "email": "integration@example.com",
        "roles": ["citizen"],
    }

    try:
        client = TestClient(app)
        response = client.get("/api/auth/me")

        assert response.status_code == 200
        assert response.json()["authenticated"] is True
        assert response.json()["user"]["user_id"] == "integration-user"
    finally:
        app.dependency_overrides.clear()


def test_admin_rbac_route_allows_admin_user():
    app.dependency_overrides[routes.get_current_user] = lambda: {
        "user_id": "admin-user",
        "roles": ["admin"],
    }

    try:
        client = TestClient(app)
        response = client.get("/api/rbac/admin-test")

        assert response.status_code == 200
        assert response.json()["message"] == "Admin access granted"
    finally:
        app.dependency_overrides.clear()
