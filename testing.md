# Flood Backend Testing Guide

This document explains how to run unit tests, integration tests, and system tests for the `flood-backend` service.

## What was created

- `pytest.ini` — test discovery and `PYTHONPATH` configuration for backend tests.
- `tests/conftest.py` — shared pytest fixture for the FastAPI test client.
- `tests/unit/test_auth.py` — unit tests for auth logic and role validation.
- `tests/unit/test_webhook.py` — unit tests for Clerk webhook verification behavior.
- `tests/integration/test_api_routes.py` — integration tests for API endpoint routing and auth flows.
- `tests/integration/test_admin_routes.py` — integration tests for admin route behavior and Clerk webhook route.
- `tests/system/test_health.py` — system tests for service health and public API availability.

## Test categories

### Unit tests

Unit tests validate isolated code paths without external services. They use mocks for external systems like Clerk auth and webhook verification.

Run unit tests:

```bash
cd flood-backend
source .venv/bin/activate
pytest tests/unit
```

### Integration tests

Integration tests exercise the FastAPI application and route wiring. They verify request/response behavior while mocking external dependencies like auth and database connections.

Run integration tests:

```bash
cd flood-backend
source .venv/bin/activate
pytest tests/integration
```

### System tests

System tests confirm the live application endpoints and health check paths behave as expected with the application running.

Run system tests:

```bash
cd flood-backend
source .venv/bin/activate
pytest tests/system
```

## Run all tests

```bash
cd flood-backend
source .venv/bin/activate
pytest
```

## Setup prerequisites

1. Create and activate the virtual environment:

```bash
cd flood-backend
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
pip install pytest
```

If your environment is missing `fastapi` or `requests`, install them as well:

```bash
pip install fastapi[all] requests python-jose
```

## Notes

- The tests use `fastapi.testclient.TestClient` to execute HTTP requests against the app.
- The auth unit tests patch Clerk JWT validation to keep tests fast and self-contained.
- The webhook unit tests patch `svix.Webhook` behavior to avoid external webhook signing requirements.
- The integration tests override `get_current_user` and patch database connections so tests do not require a real Clerk token or production database.
- The `pytest.ini` file ensures test discovery works from the backend root and that `app` can be imported correctly.
