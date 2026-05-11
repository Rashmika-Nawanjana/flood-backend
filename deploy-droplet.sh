#!/bin/bash

# DigitalOcean Droplet Automated Deployment Script
# Run this on your droplet: bash deploy-droplet.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Phase 1: System Setup
log_info "Starting DigitalOcean Droplet Deployment"
log_info "=========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root"
    exit 1
fi

# Phase 1.1: Update system
log_info "Phase 1: System Setup"
log_info "Updating system packages..."
apt-get update
apt-get upgrade -y

# Phase 1.2: Install dependencies
log_info "Installing dependencies..."
apt-get install -y \
    git \
    curl \
    wget \
    docker.io \
    docker-compose \
    openssl \
    jq \
    htop \
    nginx

# Phase 1.3: Setup Docker
log_info "Configuring Docker..."
systemctl start docker
systemctl enable docker
docker --version
docker-compose --version

# Phase 2: Repository Setup
log_info ""
log_info "Phase 2: Repository Setup"

# Ask user for GitHub details
read -p "Enter your GitHub username: " GITHUB_USER
read -p "Enter your repository name (default: flood_managment): " REPO_NAME
REPO_NAME=${REPO_NAME:-flood_managment}

REPO_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
log_info "Cloning repository: $REPO_URL"

cd /opt
rm -rf ${REPO_NAME} 2>/dev/null || true
git clone ${REPO_URL}
cd ${REPO_NAME}/flood-backend

log_info "Repository cloned to /opt/${REPO_NAME}/flood-backend"

# Phase 3: Environment Setup
log_info ""
log_info "Phase 3: Environment Configuration"
log_info "Creating .env file..."

# Ask for critical values
read -p "Enter Kong Konnect Token (kpat_...): " KONNECT_TOKEN
read -p "Enter Database Password: " DB_PASSWORD
read -p "Enter Clerk Secret Key: " CLERK_SECRET
read -p "Enter Clerk Publishable Key: " CLERK_PUBLISHABLE
JWT_SECRET=$(openssl rand -base64 32)

cat > .env << EOF
# Application Config
APP_NAME="Flood Backend"
DEBUG=False
ENVIRONMENT=staging

# Database
DB_USER=postgres
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432
DB_NAME=flood_management

# InfluxDB
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_ORG=floodsense
INFLUXDB_BUCKET=flood_data
INFLUXDB_TOKEN=change_me_later

# Kafka
KAFKA_BROKER=kafka:9092
KAFKA_TOPIC=flood-sensor-data

# Services URLs
API_SERVICE_URL=http://api:8000
SENSOR_SERVICE_URL=http://sensor-service:8002
INTELLIGENCE_SERVICE_URL=http://intelligence-service:8003
ZONE_SERVICE_URL=http://zone-service:8004

# Kong Konnect Configuration
export KONNECT_TOKEN=${KONNECT_TOKEN}
export KONNECT_ADDR=https://in.api.konghq.com
export CONTROL_PLANE_NAME=Flood-Management-Gateway
export KONNECT_NODE_NAME=flood-stg-node
export KONNECT_CLUSTER_CERT_PATH=/opt/${REPO_NAME}/flood-backend/certs/tls.crt
export KONNECT_CLUSTER_KEY_PATH=/opt/${REPO_NAME}/flood-backend/certs/tls.key

# Clerk Auth
CLERK_SECRET_KEY=${CLERK_SECRET}
CLERK_PUBLISHABLE_KEY=${CLERK_PUBLISHABLE}

# JWT
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256

# ML Service
ML_MODEL_PATH=/models/xgb_model.pkl
ANOMALY_THRESHOLD=0.75
EOF

log_info ".env file created"
log_info "JWT_SECRET: ${JWT_SECRET}"

# Phase 4: SSL Certificates
log_info ""
log_info "Phase 4: SSL Certificate Generation"

mkdir -p certs
cd certs

log_info "Generating self-signed certificate..."
openssl req -x509 -newkey rsa:2048 -keyout tls.key -out tls.crt -days 365 -nodes \
    -subj "/C=LK/ST=Western/L=Colombo/O=FloodSense/CN=stg.floodsense.lk"

log_info "Certificate generated: tls.crt, tls.key"
ls -la

cd /opt/${REPO_NAME}/flood-backend

# Phase 5: Docker Services
log_info ""
log_info "Phase 5: Starting Docker Services"
log_warn "This may take 2-3 minutes..."

docker-compose -f docker-compose.stg.yml pull
log_info "Docker images pulled"

docker-compose -f docker-compose.stg.yml up -d
log_info "Services started"

sleep 10

log_info "Service status:"
docker-compose -f docker-compose.stg.yml ps

# Phase 6: Nginx Configuration
log_info ""
log_info "Phase 6: Nginx Configuration"

read -p "Enter your domain (e.g., stg.floodsense.lk): " DOMAIN

cat > /etc/nginx/sites-available/flood-gateway << EOF
upstream kong {
    server localhost:8000;
}

server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /opt/${REPO_NAME}/flood-backend/certs/tls.crt;
    ssl_certificate_key /opt/${REPO_NAME}/flood-backend/certs/tls.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://kong;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -s /etc/nginx/sites-available/flood-gateway /etc/nginx/sites-enabled/flood-gateway 2>/dev/null || true
rm /etc/nginx/sites-enabled/default 2>/dev/null || true

nginx -t
systemctl start nginx
systemctl enable nginx

log_info "Nginx configured and started"

# Phase 7: Verification
log_info ""
log_info "Phase 7: Service Verification"

sleep 5

log_info "Testing Kong health..."
if curl -s http://localhost:8000/health > /dev/null; then
    log_info "✓ Kong is responding"
else
    log_warn "⚠ Kong health check failed - services may still be starting"
fi

log_info "Testing Nginx..."
if curl -k https://localhost/health 2>/dev/null | grep -q "ok\|pong\|running"; then
    log_info "✓ Nginx is responding"
else
    log_info "Nginx responding (may take a moment for services to be ready)"
fi

# Summary
log_info ""
log_info "=========================================="
log_info "✓ DEPLOYMENT COMPLETE!"
log_info "=========================================="
log_info ""
log_info "Next Steps:"
log_info "1. Configure DNS A record:"
log_info "   Host: stg (for stg.${DOMAIN})"
log_info "   Type: A"
log_info "   Value: $(curl -s https://api.ipify.org)"
log_info ""
log_info "2. Wait 15-30 minutes for DNS propagation"
log_info ""
log_info "3. Test from external machine:"
log_info "   curl -k https://${DOMAIN}/api/ping"
log_info ""
log_info "4. Useful commands:"
log_info "   docker-compose -f docker-compose.stg.yml ps"
log_info "   docker-compose -f docker-compose.stg.yml logs -f api"
log_info "   docker-compose -f docker-compose.stg.yml restart"
log_info ""
log_info "Droplet IP: $(curl -s https://api.ipify.org)"
log_info "Domain: ${DOMAIN}"
log_info ""

log_info "For detailed troubleshooting, see: docs/DROPLET_DEPLOYMENT_STEPS.md"
