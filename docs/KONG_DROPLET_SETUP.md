# Kong Data Plane Setup for DigitalOcean Droplet

Quick guide to deploy Kong data plane connected to Kong Konnect control plane.

---

## Prerequisites

- [ ] DigitalOcean droplet (Ubuntu 22.04, 1GB RAM minimum)
- [ ] Kong Konnect account with control plane created
- [ ] Kong Konnect Personal Access Token (kpat\_...)
- [ ] SSH access to droplet

---

## PHASE 1: Initial Droplet Setup (3 minutes)

### Step 1.1: SSH into droplet

```bash
ssh root@YOUR_DROPLET_IP
```

### Step 1.2: Update system

```bash
apt-get update && apt-get upgrade -y
```

### Step 1.3: Install Docker & required tools

```bash
apt-get install -y docker.io curl openssl jq
```

### Step 1.4: Start Docker

```bash
systemctl start docker
systemctl enable docker
docker --version
```

---

## PHASE 2: Create Kong Configuration (5 minutes)

### Step 2.1: Create configuration directory

```bash
mkdir -p /opt/kong-data-plane
cd /opt/kong-data-plane
```

### Step 2.2: Create docker-compose.yml for Kong

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  kong:
    image: kong:3.4-alpine
    container_name: kong-data-plane
    environment:
      KONG_ROLE: data_plane
      KONG_DATABASE: off
      KONG_CLUSTER_CONTROL_PLANE: in.api.konghq.com:443
      KONG_CLUSTER_TELEMETRY_ENDPOINT: in.telemetry.konghq.com:443
      KONG_CLUSTER_CERT: /etc/kong/certs/tls.crt
      KONG_CLUSTER_CERT_KEY: /etc/kong/certs/tls.key
      KONG_CLUSTER_MTLS_ENABLED: "on"
      KONG_LOG_LEVEL: info
      KONG_PROXY_LISTEN: "0.0.0.0:8000, 0.0.0.0:8443 ssl"
      KONG_ADMIN_LISTEN: "127.0.0.1:8001"
      KONG_STATUS_LISTEN: "0.0.0.0:8100"
    ports:
      - "8000:8000"
      - "8443:8443"
      - "8100:8100"
    volumes:
      - ./certs/:/etc/kong/certs:ro
    networks:
      - kong-network
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

networks:
  kong-network:
    driver: bridge
EOF
```

### Step 2.3: Create certificates directory

```bash
mkdir -p certs
```

---

## PHASE 3: Generate Certificates (5 minutes)

### Step 3.1: Generate self-signed certificate

```bash
cd /opt/kong-data-plane/certs

openssl req -x509 -newkey rsa:2048 -keyout tls.key -out tls.crt -days 365 -nodes \
  -subj "/C=LK/ST=Western/L=Colombo/O=FloodSense/CN=kong-data-plane"

ls -la
```

**Output:**

```
tls.crt
tls.key
```

### Step 3.2: Fix permissions

```bash
chmod 644 tls.crt
chmod 644 tls.key
```

---

## PHASE 4: Configure Kong Connection (2 minutes)

### Step 4.1: Create .env file with Kong Konnect credentials

```bash
cd /opt/kong-data-plane

cat > .env << 'EOF'
KONNECT_TOKEN=kpat_YOUR_TOKEN_HERE
KONNECT_ADDR=https://in.api.konghq.com
EOF
```

### Step 4.2: Update with your actual token

```bash
nano .env
```

Replace `kpat_YOUR_TOKEN_HERE` with your actual Kong Konnect token from the dashboard.

### Step 4.3: Verify token is set

```bash
source .env
echo "Token: $KONNECT_TOKEN"
echo "Address: $KONNECT_ADDR"
```

---

## PHASE 5: Start Kong Data Plane (2 minutes)

### Step 5.1: Pull Kong image

```bash
cd /opt/kong-data-plane
docker-compose pull
```

### Step 5.2: Start Kong

```bash
docker-compose up -d
```

### Step 5.3: Check Kong is running

```bash
docker-compose ps
```

**Expected output:**

```
NAME                   STATUS
kong-data-plane        Up 2 minutes
```

### Step 5.4: Wait for Kong to connect

```bash
sleep 10
docker-compose logs kong | grep -i "cluster\|connected"
```

**Look for:**

```
Kong gateway started in hybrid mode (data plane)
Successfully connected to control plane
```

---

## PHASE 6: Verify Connection (3 minutes)

### Step 6.1: Check Kong health locally

```bash
curl -i http://localhost:8000/health
```

**Expected response:**

```
HTTP/1.1 200 OK
```

### Step 6.2: Check Kong is connected to Konnect

```bash
docker-compose exec kong kong config db_import /dev/stdin 2>&1 | head -20
```

### Step 6.3: View Kong status

```bash
curl http://localhost:8100/v1/status
```

**Should show:** Data plane is connected

---

## PHASE 7: Configure Nginx Reverse Proxy (3 minutes)

### Step 7.1: Install Nginx

```bash
apt-get install -y nginx
```

### Step 7.2: Create Nginx config

```bash
cat > /etc/nginx/sites-available/kong-gateway << 'EOF'
upstream kong {
    server localhost:8000;
    server localhost:8443;
}

server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2 default_server;
    server_name _;

    ssl_certificate /opt/kong-data-plane/certs/tls.crt;
    ssl_certificate_key /opt/kong-data-plane/certs/tls.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

### Step 7.3: Enable Nginx

```bash
ln -s /etc/nginx/sites-available/kong-gateway /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default 2>/dev/null

nginx -t
systemctl start nginx
systemctl enable nginx
```

---

## PHASE 8: Test Gateway (5 minutes)

### Step 8.1: Test locally on droplet

```bash
curl -i http://localhost:8000/health
curl -i https://localhost/health -k
```

### Step 8.2: Check that services from Konnect are available

```bash
# List services configured in Kong Konnect
curl -s http://localhost:8001/services | jq '.data[] | {name, url}'
```

### Step 8.3: Check routes

```bash
curl -s http://localhost:8001/routes | jq '.data[] | {name, paths, methods}'
```

---

## PHASE 9: Setup Domain (10 minutes)

### Step 9.1: Get your droplet IP

```bash
curl -s https://api.ipify.org
```

### Step 9.2: Add DNS A record

Go to your domain registrar (GoDaddy, Namecheap, etc.):

1. Add A record:
   - **Host**: stg (for stg.floodsense.lk)
   - **Type**: A
   - **Value**: YOUR_DROPLET_IP
   - **TTL**: 3600

2. Save and wait 5-15 minutes for DNS to propagate

### Step 9.3: Verify DNS resolution

```bash
# From another machine (or wait 5 mins then try locally)
nslookup stg.floodsense.lk
```

---

## PHASE 10: Final Testing (5 minutes)

### Step 10.1: Test from external machine (after DNS works)

```bash
curl -k https://stg.floodsense.lk/health
```

### Step 10.2: Test with your configured service

```bash
curl -k https://stg.floodsense.lk/api/ping
```

### Step 10.3: Monitor Kong in real-time

```bash
# On droplet
docker-compose logs -f kong
```

---

## 🎯 Quick Commands Reference

```bash
# Start Kong
docker-compose -f /opt/kong-data-plane/docker-compose.yml up -d

# Stop Kong
docker-compose -f /opt/kong-data-plane/docker-compose.yml down

# View logs
docker-compose -f /opt/kong-data-plane/docker-compose.yml logs -f kong

# Restart Kong
docker-compose -f /opt/kong-data-plane/docker-compose.yml restart

# Check status
docker-compose -f /opt/kong-data-plane/docker-compose.yml ps

# View Kong config
curl http://localhost:8001/config

# Check connection to Konnect
curl http://localhost:8100/v1/status
```

---

## ✅ Verification Checklist

- [ ] Docker running: `docker --version`
- [ ] Kong container running: `docker-compose ps`
- [ ] Kong health OK: `curl http://localhost:8000/health`
- [ ] Kong logs show "connected": `docker-compose logs kong | grep connected`
- [ ] Services available: `curl http://localhost:8001/services`
- [ ] Nginx running: `systemctl status nginx`
- [ ] DNS resolves: `nslookup stg.floodsense.lk`
- [ ] External test passes: `curl -k https://stg.floodsense.lk/health`

---

## 🚨 Troubleshooting

### Kong not starting

```bash
docker-compose logs kong
# Check certificate permissions
ls -la certs/
chmod 644 certs/tls.*
docker-compose restart kong
```

### Kong not connecting to Konnect

```bash
# Verify token
source .env
echo $KONNECT_TOKEN

# Check DNS
nslookup in.api.konghq.com

# View Kong error logs
docker-compose logs kong | grep -i "error\|failed"
```

### Services not showing in Kong

```bash
# They come from Konnect control plane
# Make sure they're created in Kong Konnect dashboard

# View Kong admin API
curl http://localhost:8001/services | jq .
```

### Nginx not proxying

```bash
# Test Nginx config
nginx -t

# Check Nginx logs
tail -50 /var/log/nginx/error.log

# Restart Nginx
systemctl restart nginx
```

---

## 📊 Architecture

```
Internet
    ↓
DNS (stg.floodsense.lk) → Droplet IP
    ↓
Nginx (443, 80)
    ↓
Kong Proxy (8000, 8443)
    ↓
↙           ↓           ↘
Your         Kong         Status
Services     Konnect      (8100)
             Control
             Plane
```

---

## Total Setup Time

- System setup: 3 min
- Kong config: 5 min
- Certificates: 5 min
- Kong Konnect config: 2 min
- Start services: 2 min
- Verification: 3 min
- Nginx setup: 3 min
- DNS setup: 10 min
- Testing: 5 min

**Total: ~38 minutes**

---

## Next Steps

1. **Create services in Kong Konnect** dashboard
2. **Create routes** for each service
3. **Add plugins** (rate limiting, auth, etc.)
4. **Configure consumers** for API clients
5. **Monitor** through Kong Konnect dashboard

See: [KONNECT_QUICK_REFERENCE.md](KONNECT_QUICK_REFERENCE.md) for Kong Konnect setup commands.
