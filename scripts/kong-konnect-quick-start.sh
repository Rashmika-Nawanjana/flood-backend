#!/bin/bash

# Kong Konnect Quick Start - Copy & Paste Commands
# Replace YOUR_TOKEN with your actual Kong Konnect token
# NOTE: Make sure to source .env first: source .env

# ============================================
# STEP 1: Setup & Test Connection
# ============================================

# 1.1 Set environment variables (or source from .env)
# export KONNECT_TOKEN="kpat_YOUR_TOKEN_HERE"
# export KONNECT_ADDR="https://in.api.konghq.com"
# export CONTROL_PLANE_NAME="Flood-Management-Gateway"

# 1.2 Test connectivity
curl -X GET 'https://in.api.konghq.com/v2/control-planes' \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" | jq '.data[] | {id, name}'

# ============================================
# STEP 2: Get Your Control Plane ID
# ============================================

CP_ID=$(curl -s -X GET "${KONNECT_ADDR}/v2/control-planes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" | \
  jq -r ".data[] | select(.name==\"${CONTROL_PLANE_NAME}\") | .id")

echo "Your Control Plane ID: $CP_ID"

# ============================================
# STEP 3: Create Service
# ============================================

# Example: Create the API service
curl -X POST "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/services" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "flood-api",
    "url": "http://api:8000",
    "tags": ["flood-management"]
  }' | jq .

# ============================================
# STEP 4: Create Route
# ============================================

# Create a route for the API service
SERVICE_ID=$(curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/services/flood-api" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" | jq -r '.id')

curl -X POST "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/services/${SERVICE_ID}/routes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "flood-api-route",
    "paths": ["/api"],
    "protocols": ["http", "https"],
    "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
  }' | jq .

# ============================================
# STEP 5: Create Consumer
# ============================================

curl -X POST "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/consumers" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "username": "external-api-client",
    "custom_id": "external-client-001"
  }' | jq .

# ============================================
# STEP 6: Create API Key for Consumer
# ============================================

curl -X POST "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/consumers/external-api-client/key-auth" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "key": "your-secret-api-key-12345"
  }' | jq .

# ============================================
# STEP 7: Enable Rate Limiting Plugin
# ============================================

curl -X POST "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/plugins" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "rate-limiting",
    "service": {"id": "'${SERVICE_ID}'"},
    "config": {
      "minute": 30,
      "limit_by": "consumer",
      "policy": "local"
    }
  }' | jq .

# ============================================
# STEP 8: List All Services
# ============================================

curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/services" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" | jq '.data[] | {id, name, url}'

# ============================================
# STEP 9: List All Routes
# ============================================

curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/routes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" | jq '.data[] | {id, name, paths, methods}'

# ============================================
# STEP 10: List All Consumers
# ============================================

curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/consumers" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" | jq '.data[] | {id, username, custom_id}'

# ============================================
# STEP 11: Check Data Plane Nodes
# ============================================

curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/nodes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" | jq '.data[] | {id, hostname, status}'

# ============================================
# USEFUL: Update Service URL
# ============================================

# Example: Update the API service URL
curl -X PATCH "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/services/flood-api" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "url": "http://new-api-host:8000"
  }' | jq .

# ============================================
# USEFUL: Delete a Service
# ============================================

# curl -X DELETE "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/core-entities/services/flood-api" \
#   --header "Authorization: Bearer ${KONNECT_TOKEN}" \
#   --header "Content-Type: application/json"

# ============================================
# NOTES
# ============================================

# 1. Replace YOUR_TOKEN with your actual Kong Konnect Personal Access Token
# 2. All curl commands assume jq is installed for JSON formatting
# 3. Keep your token secret - never commit it to git
# 4. Control Plane ID will be different for your account
# 5. Test commands with --data-raw to see raw responses without jq

# ============================================
# REFERENCE LINKS
# ============================================

# Kong Konnect Dashboard: https://cloud.konghq.com
# Admin API Docs: https://docs.konghq.com/konnect/reference/
# Control Planes: https://docs.konghq.com/konnect/control-planes/
