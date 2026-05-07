# Kong Deployment: provisioning consumer keys securely

Purpose: describe secure, repeatable ways to create Kong consumers and key-auth credentials without committing secrets to the repository.

Recommended approaches

- Use the Kong Admin API during deployment (CI/CD) and store keys in your CI/CD secret store.
- Use a secret manager (HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager) to hold API keys and deliver them at deploy/runtime.
- In Kubernetes, keep credentials in `Secret` objects and inject them into deployment jobs (not in code or declarative config stored in git).

Example 1 — create consumer and key via Kong Admin API (CI job)

1. Create consumer:

```bash
curl -sS -X POST "$KONG_ADMIN_URL/consumers" \
  --header "Kong-Admin-Token: $KONG_ADMIN_TOKEN" \
  --data "username=flood-backend-consumer"
```

2. Create key-auth credential (let CI generate the key and store it as a secret):

```bash
NEW_KEY=$(openssl rand -hex 16)
curl -sS -X POST "$KONG_ADMIN_URL/consumers/flood-backend-consumer/key-auth" \
  --header "Kong-Admin-Token: $KONG_ADMIN_TOKEN" \
  --data "key=$NEW_KEY"
# Store $NEW_KEY in your secret store (e.g., GitHub Actions secret, Vault, etc.) for consumers to use.
```

Example 2 — Kubernetes: create a secret and use a deploy-time job to register the key

```bash
kubectl create secret generic kong-consumer-key \
  --from-literal=KONG_CONSUMER_KEY="$NEW_KEY" \
  -n kong-namespace

# In your deployment job, read the secret and call Kong Admin API to attach it to the consumer.
```

Example 3 — GitHub Actions snippet (high level)

```yaml
jobs:
  register-kong-key:
    runs-on: ubuntu-latest
    steps:
      - name: Call Kong Admin API
        env:
          KONG_ADMIN_URL: ${{ secrets.KONG_ADMIN_URL }}
          KONG_ADMIN_TOKEN: ${{ secrets.KONG_ADMIN_TOKEN }}
          NEW_KEY: ${{ secrets.NEW_KEY }}
        run: |
          curl -sS -X POST "$KONG_ADMIN_URL/consumers/flood-backend-consumer/key-auth" \
            --header "Kong-Admin-Token: $KONG_ADMIN_TOKEN" \
            --data "key=$NEW_KEY"
```

Security notes and best practices

- Do NOT commit API keys or production credentials to git. Replace any placeholder values (e.g., `CHANGE_ME_IN_DEPLOYMENT`) during CI or with a secret manager at deploy time.
- Use `hide_credentials: true` in `key-auth` plugin config (already enabled per-service) so Kong does not echo credentials back to clients.
- Avoid using `policy: local` rate-limiting in multi-node production — prefer a shared backend (Redis) or Kong Enterprise features for distributed rate-limiting.
- Restrict access to the Kong Admin API by network controls and an admin token; never expose it publicly.

Where to update in this repo

- The consumer placeholder is in `kong-plugins.yml` — do not replace it with real keys in the repo. Provision keys at deploy time instead.
- Service-level `key-auth` is applied in `kong.yml` to keep auth control explicit per service.

If you want, I can:
- Add a small deploy script (`scripts/register_kong_consumer.sh`) that reads secrets and registers a consumer/key via the Kong Admin API.
- Add a short GitHub Actions workflow example to the repo that provisions the key from repository secrets.

---
Last updated: 2026-05-07
