# DigitalOcean Droplet Deployment Guide

## 📋 Prerequisites

Before starting, ensure you have:

- [ ] DigitalOcean account
- [ ] Created a Droplet (Ubuntu 22.04, 2GB RAM minimum)
- [ ] SSH key added to droplet
- [ ] Kong Konnect control plane configured
- [ ] Personal Access Token (from Kong Konnect)
- [ ] Domain name (stg.floodsense.lk or similar)

---

## PHASE 1: Initial Droplet Setup (10 minutes)

### Step 1.1: SSH into your droplet

```bash
ssh root@YOUR_DROPLET_IP
```

### Step 1.2: Update system packages

```bash
apt-get update
apt-get upgrade -y
```

### Step 1.3: Install required tools

```bash
apt-get install -y \
  git \
  curl \
  wget \
  docker.io \
  docker-compose \
  openssl \
  jq \
  htop
```

### Step 1.4: Enable Docker daemon

```bash
systemctl start docker
systemctl enable docker
```

### Step 1.5: Verify Docker installation

```bash
docker --version
docker-compose --version
```

**Expected Output:**

```
Docker version 24.x.x
Docker Compose version 2.x.x
```

---

## PHASE 2: Clone Repository & Setup (5 minutes)

### Step 2.1: Clone the repository

```bash
cd /opt
git clone https://github.com/YOUR_USERNAME/flood_managment.git
cd flood_managment/flood-backend
```

### Step 2.2: Verify key files exist

```bash
ls -la | grep -E "(docker-compose|\.env|Dockerfile)"
```

**Expected files:**

- `docker-compose.stg.yml`
- `.env` (to be created next)
- `Dockerfile`

---

## PHASE 3: Configure Environment (10 minutes)

### Step 3.1: Create .env file on droplet

```bash
cat > .env << 'EOF'
# Application Config
APP_NAME="Flood Backend"
DEBUG=False
ENVIRONMENT=staging

# Database
DB_USER=postgres
DB_PASSWORD=your_db_password_here
DB_HOST=db
DB_PORT=5432
DB_NAME=flood_management

# InfluxDB
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_ORG=floodsense
INFLUXDB_BUCKET=flood_data
INFLUXDB_TOKEN=your_influx_token_here

# Kafka
KAFKA_BROKER=kafka:9092
KAFKA_TOPIC=flood-sensor-data

# Services URLs
API_SERVICE_URL=http://api:8000
SENSOR_SERVICE_URL=http://sensor-service:8002
INTELLIGENCE_SERVICE_URL=http://intelligence-service:8003
ZONE_SERVICE_URL=http://zone-service:8004

# Kong Konnect Configuration
export KONNECT_TOKEN=kpat_YOUR_TOKEN_HERE
export KONNECT_ADDR=https://in.api.konghq.com
export CONTROL_PLANE_NAME=Flood-Management-Gateway
export KONNECT_NODE_NAME=flood-stg-node
export KONNECT_CLUSTER_CERT_PATH=/opt/flood_managment/flood-backend/certs/tls.crt
export KONNECT_CLUSTER_KEY_PATH=/opt/flood_managment/flood-backend/certs/tls.key

# Clerk Auth
CLERK_SECRET_KEY=your_clerk_secret_key
CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key

# JWT
JWT_SECRET=your_jwt_secret_key
JWT_ALGORITHM=HS256

# ML Service
ML_MODEL_PATH=/models/xgb_model.pkl
ANOMALY_THRESHOLD=0.75
EOF
```

### Step 3.2: Update .env with your actual values

```bash
nano .env
```

**Replace these values:**

- `YOUR_TOKEN_HERE` → Your Kong Konnect Personal Access Token
- `your_db_password_here` → Your PostgreSQL password
- `your_influx_token_here` → Your InfluxDB token
- `your_clerk_secret_key` → Your Clerk secret
- `your_clerk_publishable_key` → Your Clerk public key
- `your_jwt_secret_key` → Generate with: `openssl rand -base64 32`

### Step 3.3: Verify environment variables are set

```bash
source .env
echo "Kong Token: $KONNECT_TOKEN"
echo "Kong Address: $KONNECT_ADDR"
echo "Control Plane: $CONTROL_PLANE_NAME"
```

---

## PHASE 4: SSL Certificates (10 minutes)

### Step 4.1: Create certificates directory

```bash
mkdir -p /opt/flood_managment/flood-backend/certs
cd /opt/flood_managment/flood-backend/certs
```

### Step 4.2: Generate self-signed certificate (for initial testing)

```bash
openssl req -x509 -newkey rsa:2048 -keyout tls.key -out tls.crt -days 365 -nodes \
  -subj "/C=LK/ST=Western/L=Colombo/O=FloodSense/CN=stg.floodsense.lk"
```

### Step 4.3: Verify certificates

```bash
ls -la /opt/flood_managment/flood-backend/certs/
openssl x509 -in tls.crt -text -noout | grep -A 2 "Subject:"
```

**Note:** For production, replace with Let's Encrypt certificate (see Step 6)

---

## PHASE 5: Start Services (10 minutes)

### Step 5.1: Navigate to backend directory

```bash
cd /opt/flood_managment/flood-backend
```

### Step 5.2: Pull Docker images

```bash
docker-compose -f docker-compose.stg.yml pull
```

### Step 5.3: Start all services

```bash
docker-compose -f docker-compose.stg.yml up -d
```

### Step 5.4: Verify all containers are running

```bash
docker-compose -f docker-compose.stg.yml ps
```

**Expected Output:**

```
NAME                    STATUS
flood-backend-db-1      Up 2 minutes
flood-backend-api-1     Up 1 minute
flood-backend-kong-1    Up 1 minute
flood-backend-nginx-1   Up 1 minute
```

### Step 5.5: Check Kong logs

```bash
docker-compose -f docker-compose.stg.yml logs kong | head -50
```

**Look for:**

```
Kong gateway started in hybrid mode (data plane)
Connected to control plane successfully
```

---

## PHASE 6: Configure Nginx (5 minutes)

### Step 6.1: Create Nginx config

```bash
cat > /etc/nginx/sites-available/flood-gateway << 'EOF'
upstream kong {
    server localhost:8000;
}

server {
    listen 80;
    server_name stg.floodsense.lk;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name stg.floodsense.lk;

    ssl_certificate /opt/flood_managment/flood-backend/certs/tls.crt;
    ssl_certificate_key /opt/flood_managment/flood-backend/certs/tls.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://kong;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

### Step 6.2: Enable Nginx site

```bash
ln -s /etc/nginx/sites-available/flood-gateway /etc/nginx/sites-enabled/flood-gateway
rm /etc/nginx/sites-enabled/default 2>/dev/null || true
```

### Step 6.3: Test Nginx configuration

```bash
nginx -t
```

**Expected Output:**

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### Step 6.4: Start Nginx

```bash
systemctl start nginx
systemctl enable nginx
```

---

## PHASE 7: Verify Connectivity (5 minutes)

### Step 7.1: Check Kong is responding (locally)

```bash
curl -i http://localhost:8000/health
```

**Expected Response:**

```
HTTP/1.1 200 OK
```

### Step 7.2: Check Kong is connected to Konnect

```bash
docker exec flood-backend-kong-1 kong config db_import /dev/stdin 2>&1 | head -20
```

### Step 7.3: Verify local Nginx

```bash
curl -k https://localhost/health
```

### Step 7.4: Test API through Kong

```bash
curl -i -k https://localhost/api/ping
```

---

## PHASE 8: DNS Configuration (varies by registrar)

### For your domain registrar (GoDaddy, Namecheap, etc.):

1. Go to DNS settings
2. Create an A record:
   - **Host**: `stg` (for stg.floodsense.lk)
   - **Type**: A
   - **Value**: YOUR_DROPLET_IP
   - **TTL**: 3600

3. Save and wait 15-30 minutes for DNS propagation

### Step 8.2: Verify DNS resolution

```bash
# Wait 15 mins then test from another machine
nslookup stg.floodsense.lk
# or
dig stg.floodsense.lk
```

---

## PHASE 9: Testing from External Machine (5 minutes)

### Step 9.1: Test from your local machine (after DNS propagates)

```bash
curl -k https://stg.floodsense.lk/api/ping
```

**Expected Response:**

```json
{ "status": "pong" }
```

### Step 9.2: Test with Kong authentication

```bash
# Using the consumer API key created earlier
curl -k https://stg.floodsense.lk/api/users \
  -H "apikey: your-secret-api-key-12345"
```

### Step 9.3: Monitor live logs

```bash
# From droplet terminal
docker-compose -f docker-compose.stg.yml logs -f api
```

---

## PHASE 10: Maintenance & Monitoring (ongoing)

### Step 10.1: Monitor container health

```bash
# Check status
docker-compose -f docker-compose.stg.yml ps

# View logs
docker-compose -f docker-compose.stg.yml logs api

# Resource usage
docker stats
```

### Step 10.2: Restart services (if needed)

```bash
# Restart one service
docker-compose -f docker-compose.stg.yml restart api

# Restart all services
docker-compose -f docker-compose.stg.yml restart
```

### Step 10.3: Update .env and redeploy

```bash
cd /opt/flood_managment/flood-backend
nano .env  # Make changes
docker-compose -f docker-compose.stg.yml up -d  # Redeploy
docker-compose -f docker-compose.stg.yml ps  # Verify
```

### Step 10.4: View Kong Konnect status

```bash
# From droplet
curl -s http://localhost:8100/v1/status | jq .
```

**Expected output shows:** data plane connected to control plane

---

## 🚨 Troubleshooting

### Issue: Kong not connecting to Konnect

```bash
# Check Kong logs
docker logs flood-backend-kong-1 | grep -i "control\|error"

# Verify token is correct
source .env
echo $KONNECT_TOKEN
echo $KONNECT_ADDR
```

### Issue: Certificate errors

```bash
# Renew certificate
cd /opt/flood_managment/flood-backend/certs
openssl x509 -in tls.crt -text -noout | grep "Not After"

# For Let's Encrypt (recommended for production)
apt-get install -y certbot python3-certbot-nginx
certbot certonly --nginx -d stg.floodsense.lk
```

### Issue: Nginx connection refused

```bash
# Check Nginx status
systemctl status nginx

# Restart Nginx
systemctl restart nginx

# Check logs
tail -50 /var/log/nginx/error.log
```

### Issue: Services not starting

```bash
# Check Docker daemon
systemctl status docker

# Check resource usage
free -h
df -h

# View detailed errors
docker-compose -f docker-compose.stg.yml logs
```

---

## ✅ Post-Deployment Checklist

- [ ] All containers running: `docker-compose -f docker-compose.stg.yml ps`
- [ ] Kong connected to Konnect: `docker logs flood-backend-kong-1 | grep -i connected`
- [ ] Nginx responding: `curl -k https://localhost/health`
- [ ] DNS resolves: `nslookup stg.floodsense.lk`
- [ ] External test passes: `curl -k https://stg.floodsense.lk/api/ping`
- [ ] Logs are clean: `docker-compose -f docker-compose.stg.yml logs | grep -i error`
- [ ] SSL certificate valid: `openssl x509 -in certs/tls.crt -noout -dates`
- [ ] Rate limiting works: Create consumer and test 31 requests
- [ ] Authentication working: Test with JWT token from Clerk

---

## 📞 Quick Reference

### Important Paths

```
Repository: /opt/flood_managment/flood-backend
Config File: .env
Certificates: /opt/flood_managment/flood-backend/certs/
Nginx Config: /etc/nginx/sites-available/flood-gateway
Docker Compose: docker-compose.stg.yml
```

### Important Ports

```
Kong Admin API (internal): 8001
Kong Proxy (internal): 8000
Kong Status: 8100
Nginx HTTP: 80
Nginx HTTPS: 443
PostgreSQL: 5432 (internal)
InfluxDB: 8086 (internal)
```

### Important Commands

```bash
# View status
docker-compose -f docker-compose.stg.yml ps

# View logs
docker-compose -f docker-compose.stg.yml logs -f [service_name]

# Restart services
docker-compose -f docker-compose.stg.yml restart

# Stop all services
docker-compose -f docker-compose.stg.yml down

# Rebuild containers
docker-compose -f docker-compose.stg.yml up -d --force-recreate
```

---

## 🎯 Next Steps After Deployment

1. **Update DNS records** with your domain registrar
2. **Test the gateway** from external network
3. **Create additional Kong consumers** for different clients
4. **Setup monitoring** (Kong Manager, Prometheus, etc.)
5. **Configure automated backups** for PostgreSQL/InfluxDB
6. **Setup log aggregation** (ELK Stack, Datadog, etc.)
7. **Deploy frontend** to CDN or separate server
8. **Setup CI/CD pipeline** for automated deployments

---

## 📝 Notes

- Keep `.env` file secure and never commit to Git
- Backup `.env` and certificates before major updates
- Monitor disk space regularly: `df -h`
- Update Docker images monthly: `docker-compose pull`
- Check Kong Konnect dashboard for configuration changes
- Test endpoint functionality regularly

**Total Setup Time: ~45 minutes**

Good luck with your deployment! 🚀
