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

## API Gateway (Kong)

This repository now includes a Kong declarative configuration file at `api-gateway-spec.yaml`.

- External entry points:
  - `/api/*` → backend `api` service
  - `/auth/*` → auth service placeholder
- Rate limiting is configured for `/api/*` with a local limit of 30 requests per minute.
- `kong` is configured in DB-less mode and reads `api-gateway-spec.yaml` at startup.

### Run Kong with the gateway spec

For local development (existing compose):

```bash
docker compose up --build
```

For deployment with Kong as the gateway service:

```bash
docker compose -f docker-compose.deploy.yml up -d --build
```

### Verify Kong is running

```bash
curl http://localhost:8001/
```

### Confirm configured services and routes

```bash
curl http://localhost:8001/services
curl http://localhost:8001/routes
```

### Test proxy behavior

```bash
curl http://localhost:8000/api/ping
curl http://localhost:8000/health
```

## Health check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{ "status": "ok", "service": "flood-backend" }
```

## Enforced commit message format

This repository blocks commits that do not follow the agreed structure.

Format:

```text
type(scope optional): short description
```

Example:

```text
fix: add githooks and branch protection
```

Setup once after cloning:

```bash
bash scripts/setup-git-hooks.sh
```

## Branch protection setup (GitHub)

Apply protection for `main`, `stg`, and `dev` (PR required, admin enforcement, no force push):

```bash
bash scripts/apply-branch-protection.sh
```

Prerequisites:

- Install GitHub CLI (`gh`)
- Authenticate once with `gh auth login`
