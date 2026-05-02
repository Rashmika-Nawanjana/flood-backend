# Keycloak Authentication Setup

## Overview

This backend uses Keycloak as the authentication provider using OAuth2 / OpenID Connect.

Keycloak is responsible for:

* User authentication
* Issuing JWT tokens
* Managing user roles

The FastAPI backend will validate JWT tokens and enforce role-based access control (RBAC).


## Local Keycloak Deployment

Run Keycloak using Docker:

```bash
docker run -p 8080:8080 -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin quay.io/keycloak/keycloak:latest start-dev
```

Access Keycloak at: http://localhost:8080

```
Admin credentials (development only):
Username: admin
Password: admin
```

---

## Client Configuration

```
Client type: OpenID Connect
Client ID: flood-frontend

Root URL: http://localhost:3000
Home URL: http://localhost:3000

Valid redirect URIs:
http://localhost:3000/*

Valid post logout redirect URIs:
http://localhost:3000/*

Web origins:
http://localhost:3000
```

---

## Defined Roles

The following roles are defined in the system:

```
admin
field_officer
citizen
```

---

## OIDC Discovery URL

```
http://localhost:8080/realms/flood-management/.well-known/openid-configuration
```

This endpoint provides all OAuth2 / OpenID Connect metadata including:

* Authorization endpoint
* Token endpoint
* Public keys for JWT verification

---

## Backend Environment Variables

Add the following to `.env` or `.env.example`:

```env
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=flood-management
KEYCLOAK_CLIENT_ID=flood-frontend
KEYCLOAK_JWKS_URL=http://localhost:8080/realms/flood-management/protocol/openid-connect/certs
OIDC_DISCOVERY_URL=http://localhost:8080/realms/flood-management/.well-known/openid-configuration
```

---

## Notes

* Login is handled by Keycloak, not the backend
* The frontend receives tokens from Keycloak
* The frontend sends tokens to FastAPI using:

```
Authorization: Bearer <access_token>
```

* FastAPI will validate the token before allowing access
* Role-based access control (RBAC) will be implemented in the backend using roles from the token
