#!/usr/bin/env bash
set -euo pipefail

# Register a Kong consumer and key-auth credential, optionally store the key in Kubernetes.
# Usage (env vars):
#  KONG_ADMIN_URL (required) e.g. http://kong-admin:8001
#  KONG_ADMIN_TOKEN (optional) — if your Kong Admin API requires a token
#  CONSUMER_USERNAME (optional, default: flood-backend-consumer)
#  NEW_KEY (optional) — if not provided the script will generate one
#  KUBE_NAMESPACE and KUBE_SECRET_NAME (optional) — to store key in k8s
#  OUTPUT_FILE (optional) — write the key to a local file

CONSUMER_USERNAME=${CONSUMER_USERNAME:-flood-backend-consumer}
KONG_ADMIN_URL=${KONG_ADMIN_URL:-}
KONG_ADMIN_TOKEN=${KONG_ADMIN_TOKEN:-}
NEW_KEY=${NEW_KEY:-}
KUBE_NAMESPACE=${KUBE_NAMESPACE:-}
KUBE_SECRET_NAME=${KUBE_SECRET_NAME:-}
OUTPUT_FILE=${OUTPUT_FILE:-}

if [[ -z "$KONG_ADMIN_URL" ]]; then
  echo "Error: KONG_ADMIN_URL is not set. Export KONG_ADMIN_URL and retry."
  exit 2
fi

if [[ -z "$NEW_KEY" ]]; then
  NEW_KEY=$(openssl rand -hex 16)
fi

AUTH_HEADER=()
if [[ -n "$KONG_ADMIN_TOKEN" ]]; then
  AUTH_HEADER=( -H "Kong-Admin-Token: $KONG_ADMIN_TOKEN" )
fi

http() {
  curl -sS -w "\n%{http_code}" "$@"
}

echo "Registering consumer '$CONSUMER_USERNAME' at $KONG_ADMIN_URL"

# Check if consumer exists
RESP=$(http -X GET "${KONG_ADMIN_URL%/}/consumers/${CONSUMER_USERNAME}" "${AUTH_HEADER[@]}" )
STATUS=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

if [[ "$STATUS" == "200" ]]; then
  echo "Consumer already exists."
else
  echo "Creating consumer..."
  RESP=$(http -X POST "${KONG_ADMIN_URL%/}/consumers" "${AUTH_HEADER[@]}" --data "username=${CONSUMER_USERNAME}")
  STATUS=$(echo "$RESP" | tail -n1)
  if [[ "$STATUS" =~ ^2 ]]; then
    echo "Consumer created."
  else
    echo "Failed to create consumer. Response:"
    echo "$RESP"
    exit 3
  fi
fi

echo "Attaching key-auth credential..."
RESP=$(http -X POST "${KONG_ADMIN_URL%/}/consumers/${CONSUMER_USERNAME}/key-auth" "${AUTH_HEADER[@]}" --data "key=${NEW_KEY}")
STATUS=$(echo "$RESP" | tail -n1)
if [[ "$STATUS" =~ ^2 ]]; then
  echo "Key-auth credential created for consumer $CONSUMER_USERNAME." 
else
  # If 409 conflict, it may already exist
  echo "Key creation response:"
  echo "$RESP"
fi

if [[ -n "$KUBE_NAMESPACE" && -n "$KUBE_SECRET_NAME" ]]; then
  echo "Storing key in Kubernetes secret '$KUBE_SECRET_NAME' (namespace: $KUBE_NAMESPACE)"
  kubectl create secret generic "$KUBE_SECRET_NAME" \
    --from-literal=KONG_CONSUMER_KEY="$NEW_KEY" \
    -n "$KUBE_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
  echo "Kubernetes secret applied."
fi

if [[ -n "$OUTPUT_FILE" ]]; then
  echo "$NEW_KEY" > "$OUTPUT_FILE"
  chmod 600 "$OUTPUT_FILE"
  echo "Wrote key to $OUTPUT_FILE (mode 600)."
fi

echo "Done."
echo "Consumer: $CONSUMER_USERNAME"
echo "Key: $NEW_KEY"

cat <<EOF

Security notes:
- Do not commit the generated key. Prefer to store it in a secrets manager or CI secret.
- Run this script in CI or in a secure environment with network access to the Kong Admin API.

Example run (generate and store in k8s):

KONG_ADMIN_URL=http://kong-admin:8001 KONG_ADMIN_TOKEN=... KUBE_NAMESPACE=kong KUBE_SECRET_NAME=kong-consumer-key ./scripts/register_kong_consumer.sh

EOF

exit 0
