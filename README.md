# Flood Backend

Minimal FastAPI skeleton to unblock parallel development.

## Structure

- `app/main.py`: application entrypoint
- `app/api/routes.py`: placeholder API routes
- `app/core/config.py`: environment config loader
- `app/db/session.py`: database placeholder session setup

## Run locally (Python)

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run with Docker

```bash
docker build -t flood-api .
docker run --rm -p 8000:8000 flood-api
```

## Run full local stack (API + PostGIS + InfluxDB)

```bash
docker compose up --build
```

## Health check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok", "service": "flood-backend"}
```
