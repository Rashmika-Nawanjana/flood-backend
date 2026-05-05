# Microservices Architecture & API Gateway Specification

## 1. Current State

We have successfully transitioned the project into the initial phase of a microservices architecture. Currently, we have:

- **API Gateway**: Kong (deployed in DB-less mode).
- **Core Backend**: `flood-api` (historically a monolith containing sensors, zones, admin, and intelligence).
- **Auth Service**: `flood-auth` (dedicated authentication service).
- **Databases**: PostgreSQL (PostGIS) and InfluxDB.

## 2. Proposed Breakdown (What I will do next)

To fully realize the microservices architecture, we will split the remaining generic `flood-api` into domain-specific microservices. Based on the existing routers, I propose creating the following distinct services:

1. **Sensor Service (`sensor-service`)**
   - **Responsibility**: Handle IoT telemetry ingestion, sensor metadata, and health updates.
   - **Routes**: `/api/sensors/*`

2. **Intelligence Service (`intelligence-service`)**
   - **Responsibility**: Provide ML predictions, risk assessment, and anomaly detection.
   - **Routes**: `/api/intelligence/*` and `/api/anomalies/*`

3. **Zone & Facility Service (`zone-service`)**
   - **Responsibility**: Manage geographical zones, shelters, and evacuation routes.
   - **Routes**: `/api/zones/*` and `/api/shelters/*`

## 3. API Gateway Configuration

The Kong API Gateway must act as the single entry point. I will update the Gateway specifications to route traffic accordingly:

- `api-gateway-spec.yaml` (Kong Declarative Config)
- `api-gateway-openapi.yaml` (OpenAPI Contract)
- `kong.yml` (Local config fallback)

**Routing Table:**

- `GET/POST /auth/*` ➔ `flood-auth:8001`
- `GET/POST /api/sensors/*` ➔ `sensor-service:8002`
- `GET/POST /api/intelligence/*` ➔ `intelligence-service:8003`
- `GET/POST /api/zones/*` ➔ `zone-service:8004`

## 4. Execution Steps

1. **Scaffold Services**: Create new folders (`sensor-service`, `intelligence-service`, `zone-service`) with individual `Dockerfile`, `requirements.txt`, and FastAPI `main.py` files.
2. **Migrate Code**: Move the respective endpoints from the current `flood-api` router to their new microservices.
3. **Update Docker Compose**: Add the new services into `docker-compose.yml` and `docker-compose.deploy.yml`, wiring them to databases and the Kong gateway.
4. **Update API Gateway**: Modify Kong definitions to implement the routing table defined above.
5. **Validate**: Run configuration checks to ensure everything is wired up seamlessly.
