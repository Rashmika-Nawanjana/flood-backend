# How to Get Kong Konnect Configuration Values

## Overview

This guide walks you through obtaining each environment variable needed for Kong Konnect integration.

---

## 1️⃣ KONNECT_TOKEN - API Personal Access Token

### Where to Get It

1. Go to **https://cloud.konghq.com**
2. Click your **Profile Avatar** (top-right corner)
3. Select **Settings** or **Personal Access Tokens**
4. Click **Generate New Token** (or **Create New Token**)
5. Choose settings:
   - **Token Name**: `flood-deployment-token` or `flood-stg`
   - **Expiration**: Choose based on your preference (90 days, 1 year, etc.)
   - **Scopes**: Select appropriate permissions (usually "Admin" for full access)
6. Click **Generate**
7. **Copy the token immediately** - it only shows once!

### Example

```bash
export KONNECT_TOKEN="kpat_abcdef1234567890_1234567890abcdef"
```

### ⚠️ Security Notes

- **Store securely** - never commit to git
- **Rotate regularly** - every 90 days recommended
- **Different tokens per environment** - have separate tokens for staging and production
- **Revoke old tokens** - delete tokens you no longer use

### What If I Lost My Token?

No problem! Generate a new one. The old token becomes invalid automatically.

---

## 2️⃣ KONNECT_ADDR - Kong Konnect API Address

### Standard Values (Choose One)

| Region           | Address                     | Usage             |
| ---------------- | --------------------------- | ----------------- |
| **US (Default)** | `https://in.api.konghq.com` | Most users        |
| **EU**           | `https://eu.api.konghq.com` | EU data residency |
| **AU**           | `https://au.api.konghq.com` | Australia region  |

### How to Find Your Region

1. Log into **https://cloud.konghq.com**
2. Look at the URL in your browser:
   - If it contains `cloud.konghq.com` → Use `https://in.api.konghq.com`
   - If it contains `eu.cloud.konghq.com` → Use `https://eu.api.konghq.com`
   - If it contains `au.cloud.konghq.com` → Use `https://au.api.konghq.com`

### Example

```bash
export KONNECT_ADDR="https://in.api.konghq.com"  # For US region
```

---

## 3️⃣ CONTROL_PLANE_NAME - Your Gateway Control Plane

### Where to Find It

1. Log into **Kong Konnect** (https://cloud.konghq.com)
2. From the **left sidebar**, select **Gateway Manager**
3. Look at **Control Planes** section
4. You should see your control planes listed

### Create One If You Don't Have It

1. Click **+ New Control Plane**
2. Fill in details:
   - **Name**: `Flood-Management-Gateway` (or whatever you named it)
   - **Description**: `Control plane for Flood Management staging`
   - **Labels** (optional): `environment: staging`, `team: platform`
3. Click **Create**

### Example

```bash
export CONTROL_PLANE_NAME="Flood-Management-Gateway"
```

### View All Your Control Planes

1. Go to **Gateway Manager** → **Control Planes**
2. Each control plane shows:
   - Name
   - ID (looks like `7cc4c23c-1b5b-4dad-a3a5-a3450f1e5480`)
   - Status
   - Number of connected nodes

---

## 4️⃣ KONNECT_NODE_NAME - Data Plane Node Name

### What Is It?

The name of your Kong Data Plane instance running on DigitalOcean.

### Where to Get/Create It

1. Go to **Kong Konnect** → **Gateway Manager**
2. Select your **Control Plane** (e.g., `Flood-Management-Gateway`)
3. Go to **Data Planes** tab
4. If you have deployed a data plane, it will show with its name
5. If not yet deployed, you can set any name when deploying

### Common Node Names

```bash
# Examples:
export KONNECT_NODE_NAME="flood-stg-node"          # Staging
export KONNECT_NODE_NAME="flood-prod-node"         # Production
export KONNECT_NODE_NAME="flood-do-droplet-001"    # DigitalOcean specific
export KONNECT_NODE_NAME="flood-gateway-1"         # Generic
```

### How to Set It When Deploying

When you start Kong on your DigitalOcean droplet:

```bash
docker run -d \
  -e KONG_NODE_NAME="flood-stg-node" \
  -e KONG_ROLE=data_plane \
  ...
  kong:latest
```

---

## 5️⃣ KONNECT_REGION - Data Center Region (Optional)

### Available Regions

```bash
# Standard regions:
export KONNECT_REGION="us"        # United States
export KONNECT_REGION="eu"        # Europe
export KONNECT_REGION="au"        # Australia
```

### How to Find Your Region

1. In Kong Konnect dashboard, your region is shown in the URL:
   - `cloud.konghq.com` → Region is **us**
   - `eu.cloud.konghq.com` → Region is **eu**
   - `au.cloud.konghq.com` → Region is **au**

2. Or check when creating your control plane - it displays the region

### Example

```bash
export KONNECT_REGION="us"
```

---

## 📋 Complete Configuration Walkthrough

### Step-by-Step Process

**Step 1: Generate API Token**

```
Kong Konnect Dashboard → Settings → Personal Access Tokens → Generate New Token
Copy: kpat_xxx...xxx
```

**Step 2: Find/Create Control Plane**

```
Kong Konnect Dashboard → Gateway Manager → Control Planes
Find or Create: "Flood-Management-Gateway"
```

**Step 3: Determine Region**

```
Check browser URL:
- cloud.konghq.com → us
- eu.cloud.konghq.com → eu
- au.cloud.konghq.com → au
```

**Step 4: Set Node Name**

```
Choose name like: flood-stg-node
(You'll use this when deploying to DigitalOcean)
```

**Step 5: Create .env.konnect**

```bash
cp .env.konnect.template .env.konnect

cat > .env.konnect << 'EOF'
export KONNECT_TOKEN="kpat_abcdef1234567890"
export KONNECT_ADDR="https://in.api.konghq.com"
export CONTROL_PLANE_NAME="Flood-Management-Gateway"
export KONNECT_NODE_NAME="flood-stg-node"
export KONNECT_REGION="us"
EOF
```

---

## ✅ Verify Your Configuration

### Test Token & Connection

```bash
# Source your configuration
source .env.konnect

# Test connectivity
curl -s -X GET "${KONNECT_ADDR}/v2/control-planes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" \
  --header "Content-Type: application/json" | jq '.items[] | {id, name}'
```

### Expected Output

```json
{
  "id": "7cc4c23c-1b5b-4dad-a3a5-a3450f1e5480",
  "name": "Flood-Management-Gateway"
}
```

If you get this, everything is configured correctly! ✅

---

## 🎯 Kong Konnect Dashboard Quick Links

| Page           | URL                                      | Purpose                |
| -------------- | ---------------------------------------- | ---------------------- |
| Dashboard      | https://cloud.konghq.com                 | Main dashboard         |
| API Tokens     | https://cloud.konghq.com/settings/tokens | Generate/manage tokens |
| Control Planes | https://cloud.konghq.com/gateway-manager | Manage control planes  |
| Services       | `Control Plane → API Gateway → Services` | Configure services     |
| Routes         | `Control Plane → API Gateway → Routes`   | Configure routes       |
| Plugins        | `Control Plane → API Gateway → Plugins`  | Manage plugins         |
| Data Planes    | `Control Plane → Data Planes`            | Monitor nodes          |

---

## 🔧 Common Commands

### Test Configuration

```bash
source .env.konnect
./scripts/kong-konnect-setup.sh ping
```

### List All Control Planes

```bash
source .env.konnect

curl -s -X GET "${KONNECT_ADDR}/v2/control-planes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" | jq '.items[] | {name, id}'
```

### Get Control Plane Details

```bash
source .env.konnect

CP_ID=$(curl -s -X GET "${KONNECT_ADDR}/v2/control-planes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" | \
  jq -r '.items[] | select(.name=="Flood-Management-Gateway") | .id')

curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${CP_ID}" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" | jq .
```

### List Data Plane Nodes

```bash
source .env.konnect

CP_ID=$(curl -s -X GET "${KONNECT_ADDR}/v2/control-planes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" | \
  jq -r '.items[] | select(.name=="Flood-Management-Gateway") | .id')

curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${CP_ID}/nodes" \
  --header "Authorization: Bearer ${KONNECT_TOKEN}" | jq '.items[] | {hostname, status, version}'
```

---

## 📚 Full Documentation

- Kong Konnect Docs: https://docs.konghq.com/konnect/
- Control Planes: https://docs.konghq.com/konnect/control-planes/
- Deployment: https://docs.konghq.com/konnect/deployment/
- API Reference: https://docs.konghq.com/konnect/reference/

---

## ❓ Troubleshooting

### "Authentication Failed"

- ✅ Token starts with `kpat_`?
- ✅ Token not expired? (Check expiration date)
- ✅ Correct API address? (should be `https://in.api.konghq.com` for US)
- ✅ Token generated recently? (might need to regenerate if too old)

### "Control Plane Not Found"

- ✅ Control plane name matches exactly? (case-sensitive)
- ✅ Control plane created in Kong Konnect? (check dashboard)
- ✅ Using correct region API address?

### "Cannot Connect to Kong Konnect"

- ✅ Internet connection working?
- ✅ No firewall blocking HTTPS to `in.api.konghq.com`?
- ✅ Try: `curl -I https://in.api.konghq.com`

---

## Next Steps

1. ✅ Obtain all configuration values above
2. ✅ Create `.env.konnect` file with your values
3. ✅ Test connection with `./scripts/kong-konnect-setup.sh ping`
4. ✅ Create services and routes in Kong Konnect
5. ✅ Deploy Kong Data Plane to DigitalOcean
6. ✅ Verify data plane connects to control plane
