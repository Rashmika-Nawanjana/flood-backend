# Kong Working Flow

This document explains how requests move through the Flood backend when Kong is used as the API gateway, including the DigitalOcean deployment path.

## High-level flow

1. A client sends a request to the public gateway URL or IP.
2. Kong receives the request on its proxy port.
3. Kong matches the request path against the configured route.
4. Kong applies gateway plugins such as `rate-limiting` when configured.
5. Kong forwards the request to the upstream service container or server.
6. The upstream service processes the request and returns a response.
7. Kong sends the response back to the client.

## Local Docker flow

In local development, the gateway and services run on the same Docker network.

- `kong.yml` defines routes like `/api`, `/auth`, `/v1/sensors`, `/v1/predictions`, and `/v1/zones`.
- Each route points to a Docker service name such as `api`, `auth`, `sensor-service`, `intelligence-service`, or `zone-service`.
- Kong resolves those names through Docker networking and proxies traffic internally.
- Clerk JWT verification happens in the backend, not in Kong.

Example:

`client -> Kong -> sensor-service container`

## DigitalOcean deployment flow

When deploying to a DigitalOcean Droplet, the same logical flow applies.

### Option 1: single Droplet with Docker Compose

This is the simplest deployment model.

- Install Docker and Docker Compose on the Droplet.
- Run the backend stack on the same host.
- Keep Kong upstreams pointed at Docker service names.
- Expose Kong on port `80` or `443` for public traffic.

Flow:

`internet -> DigitalOcean Droplet -> Kong -> service container`

This works because Kong and the backend services share the same Docker network.

### Option 2: Kong separated from upstream services

Use this if the services run on different hosts, Kubernetes nodes, or managed containers.

- Change the Kong upstream URLs from Docker service names to reachable hostnames, private IPs, or load balancer addresses.
- Keep Kong public and route traffic to the DigitalOcean-hosted services over a private network when possible.

Flow:

`internet -> Kong on DigitalOcean -> upstream service on DigitalOcean/private network`

## Current gateway configuration in this repo

- `docker-compose.deploy.yml` runs Kong with `KONG_PROXY_LISTEN: 0.0.0.0:80` and exposes the proxy on port `80`.
- `docker-compose.deploy.yml` points Kong at `api-gateway-spec.yaml` in DB-less mode.
- `kong.yml` defines the service routes and plugin configuration.
- `kong-plugins.yml` defines shared plugin and consumer settings.

## Request examples

### API route

`GET /api/ping`

Result:

- Kong receives the request.
- Kong proxies it to the backend API service.
- The API service returns the response through Kong.

### Auth route

`POST /auth/login`

Result:

- Kong matches the `/auth` route.
- Kong forwards the request to the auth service.

### Sensor route

`GET /v1/sensors`

Result:

- Kong forwards the request to the sensor service.
- If `key-auth` is enabled on that route, the client must send a valid API key.

## Security notes

- Do not commit API keys in config files.
- Keep the Kong Admin API private and restricted to trusted operators or CI jobs.
- Protected backend routes fail closed with Clerk JWT verification and role checks.

## Suggested production layout on DigitalOcean

- Public entry point: Kong proxy on `80`/`443`.
- Private backend network: API, auth, sensor, intelligence, and zone services.
- Internal data services: PostgreSQL, InfluxDB, Kafka, and the bridge services.
- Secret management: CI secrets or a dedicated secret manager for Kong consumer keys and service credentials.

## Summary

Kong is the traffic gate. DigitalOcean provides the infrastructure. The application services stay behind Kong, and Kong routes each request to the correct backend service based on the path. Clerk verifies the user token in the backend.
