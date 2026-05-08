#!/bin/bash

# Kong Data Plane Setup for DigitalOcean - Automated Script
# Run on droplet: bash setup-kong-droplet.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Check root
if [[ $EUID -ne 0 ]]; then
    log_error "Run as root: sudo bash setup-kong-droplet.sh"
    exit 1
fi

log_info "Kong Data Plane Setup Starting..."
echo ""

# Phase 1: System
log_info "Phase 1: System Setup"
apt-get update > /dev/null 2>&1
apt-get upgrade -y > /dev/null 2>&1
apt-get install -y docker.io curl openssl jq nginx > /dev/null 2>&1
systemctl start docker
systemctl enable docker > /dev/null 2>&1
log_info "Docker installed and running"

# Phase 2: Kong directory
log_info ""
log_info "Phase 2: Kong Configuration"
mkdir -p /opt/kong-data-plane
cd /opt/kong-data-plane

# Phase 3: Docker compose
cat > docker-compose.yml << 'DOCKER'
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
    restart: unless-stopped

networks:
  kong-network:
    driver: bridge
DOCKER

log_info "docker-compose.yml created"

# Phase 4: Certificates
log_info ""
log_info "Phase 3: Certificate Generation"
mkdir -p certs
cd certs

openssl req -x509 -newkey rsa:2048 -keyout tls.key -out tls.crt -days 365 -nodes \
    -subj "/C=LK/ST=Western/L=Colombo/O=FloodSense/CN=kong-data-plane" > /dev/null 2>&1

chmod 644 tls.crt tls.key
log_info "Self-signed certificates generated"

# Phase 5: .env
cd /opt/kong-data-plane
log_info ""
log_info "Phase 4: Kong Konnect Configuration"

read -p "Enter Kong Konnect Token (kpat_...): " KONNECT_TOKEN
read -p "Enter domain (e.g., stg.floodsense.lk): " DOMAIN

cat > .env << EOF
KONNECT_TOKEN=${KONNECT_TOKEN}
KONNECT_ADDR=https://in.api.konghq.com
DOMAIN=${DOMAIN}
EOF

log_info "Configuration saved to .env"

# Phase 6: Start Kong
log_info ""
log_info "Phase 5: Starting Kong Container"
docker-compose pull > /dev/null 2>&1
docker-compose up -d
log_info "Kong container starting (waiting 10s)..."
sleep 10

# Check Kong
if docker-compose exec kong kong health > /dev/null 2>&1; then
    log_info "Kong is healthy"
else
    log_warn "Kong still starting... check logs with: docker-compose logs kong"
fi

# Phase 7: Nginx
log_info ""
log_info "Phase 6: Nginx Setup"

cat > /etc/nginx/sites-available/kong-gateway << 'NGINX'
upstream kong {
    server localhost:8000;
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
NGINX

ln -s /etc/nginx/sites-available/kong-gateway /etc/nginx/sites-enabled/ 2>/dev/null || true
rm /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t > /dev/null 2>&1
systemctl start nginx
systemctl enable nginx > /dev/null 2>&1
log_info "Nginx configured and running"

# Verification
log_info ""
log_info "Phase 7: Verification"
sleep 5

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    log_info "Kong proxy responding"
fi

if curl -s https://localhost/health -k > /dev/null 2>&1; then
    log_info "Nginx responding"
fi

# Summary
DROPLET_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "YOUR_IP")

echo ""
echo "=================================================="
echo -e "${GREEN}✓ KONG SETUP COMPLETE!${NC}"
echo "=================================================="
echo ""
echo "📍 Droplet IP: $DROPLET_IP"
echo "🌐 Domain: $DOMAIN"
echo ""
echo "Next Steps:"
echo "1. Configure DNS A record:"
echo "   Host: stg"
echo "   Type: A"
echo "   Value: $DROPLET_IP"
echo ""
echo "2. Wait 5-15 minutes for DNS propagation"
echo ""
echo "3. Test from external machine:"
echo "   curl -k https://$DOMAIN/health"
echo ""
echo "Commands:"
echo "  View status:  docker-compose -f /opt/kong-data-plane/docker-compose.yml ps"
echo "  View logs:    docker-compose -f /opt/kong-data-plane/docker-compose.yml logs -f"
echo "  Restart:      docker-compose -f /opt/kong-data-plane/docker-compose.yml restart"
echo ""
echo "🔗 Kong Admin API: http://localhost:8001"
echo "📊 Kong Status: http://localhost:8100"
echo ""
