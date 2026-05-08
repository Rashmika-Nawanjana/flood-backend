# FloodSense - Digital Ocean Staging Deployment Guide

## Prerequisites

1. **Digital Ocean Account** with a Droplet (Ubuntu 22.04 or later recommended)
2. **Docker & Docker Compose** installed on the droplet
3. **Domain** configured with Digital Ocean DNS (stg.floodsense.lk)
4. **SSL Certificate** (Let's Encrypt via Certbot recommended)

## Deployment Steps

### 1. Prepare Digital Ocean Droplet

```bash
# SSH into your droplet
ssh root@<your-droplet-ip>

# Update system packages
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version
```

### 2. Clone Repository and Prepare

```bash
# Navigate to deployment directory
cd /opt/flood-backend
git clone https://github.com/Rashmika-Nawanjana/flood-backend.git
cd flood-backend
git checkout stg

# Create secrets file (or use environment variables)
cp .env.stg .env.stg.local
nano .env.stg.local  # Edit with your staging secrets

# Set proper permissions
chmod 600 .env.stg.local
```

### 3. Configure Environment Variables

Set the following secrets in Digital Ocean or your system:

```bash
# Set secure passwords (use strong passwords)
export POSTGRES_PASSWORD_STG="<strong-postgres-password>"
export INFLUXDB_PASSWORD_STG="<strong-influxdb-password>"
export INFLUXDB_TOKEN_STG="<generated-token>"
export CLERK_WEBHOOK_SECRET_STG="<your-clerk-webhook-secret>"
export MQTT_BROKER_HOST="<your-mqtt-broker>"
export MQTT_USERNAME_STG="<mqtt-user>"
export MQTT_PASSWORD_STG="<mqtt-password>"
```

### 4. Deploy with Docker Compose

```bash
# Build and start all services
docker-compose -f docker-compose.stg.yml up -d

# Verify services are running
docker-compose -f docker-compose.stg.yml ps

# Check logs
docker-compose -f docker-compose.stg.yml logs -f

# Monitor health checks
docker-compose -f docker-compose.stg.yml exec postgres pg_isready -U flood_stg_user
docker-compose -f docker-compose.stg.yml exec influxdb influx ping
```

### 5. Setup Nginx as Reverse Proxy

```bash
# Install Nginx
apt install nginx -y

# Create Nginx config for Kong proxy
cat > /etc/nginx/sites-available/flood-stg << 'EOF'
upstream kong {
    server 127.0.0.1:80;
}

server {
    listen 443 ssl http2;
    server_name stg.floodsense.lk;

    ssl_certificate /etc/letsencrypt/live/stg.floodsense.lk/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/stg.floodsense.lk/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 100M;

    location / {
        proxy_pass http://kong;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

server {
    listen 80;
    server_name stg.floodsense.lk;
    return 301 https://$server_name$request_uri;
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/flood-stg /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Test and reload Nginx
nginx -t
systemctl reload nginx
```

### 6. Setup SSL Certificate with Let's Encrypt

```bash
# Install Certbot
apt install certbot python3-certbot-nginx -y

# Get certificate (replace email and domain)
certbot certonly --nginx \
  -d stg.floodsense.lk \
  -d stg-web.floodsense.lk \
  -m admin@floodsense.lk \
  --agree-tos \
  --non-interactive

# Auto-renewal
systemctl enable certbot.timer
systemctl start certbot.timer
```

### 7. Database Migrations

```bash
# Run database migrations
docker-compose -f docker-compose.stg.yml exec api alembic upgrade head

# Verify database
docker-compose -f docker-compose.stg.yml exec postgres psql -U flood_stg_user -d flooddb_stg -c "\dt"
```

### 8. Health Checks & Monitoring

```bash
# Check Kong gateway
curl -i http://localhost:8001/status

# Check API health
curl -i https://stg.floodsense.lk/api/health

# Monitor container logs
docker-compose -f docker-compose.stg.yml logs -f api kong postgres

# Resource usage
docker stats
```

### 9. Backup Strategy

```bash
# Create backup directory
mkdir -p /backups/flood-stg

# Backup PostgreSQL (automated daily)
cat > /usr/local/bin/backup-flood-stg.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/flood-stg"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker-compose -f /opt/flood-backend/docker-compose.stg.yml exec -T postgres \
    pg_dump -U flood_stg_user flooddb_stg | gzip > $BACKUP_DIR/flood-db-$TIMESTAMP.sql.gz
EOF

chmod +x /usr/local/bin/backup-flood-stg.sh

# Schedule daily backup
echo "0 2 * * * /usr/local/bin/backup-flood-stg.sh" | crontab -
```

### 10. Troubleshooting

```bash
# View detailed logs
docker-compose -f docker-compose.stg.yml logs --tail=100 <service-name>

# Restart specific service
docker-compose -f docker-compose.stg.yml restart <service-name>

# Re-initialize database
docker-compose -f docker-compose.stg.yml down -v
docker-compose -f docker-compose.stg.yml up -d

# Check network connectivity
docker-compose -f docker-compose.stg.yml exec api ping postgres
docker-compose -f docker-compose.stg.yml exec api ping influxdb
```

## Key Differences from Local Development

| Aspect | Local (docker-compose.yml) | Staging (docker-compose.stg.yml) |
|--------|---------------------------|----------------------------------|
| **Services** | All (incl. PgAdmin, dev tools) | Production only |
| **Ports** | Exposed for dev | Kong on 80/443 only |
| **Ngrok** | Used for webhooks | None (direct domain) |
| **Environment** | `.env` with defaults | `.env.stg` with production values |
| **Health Checks** | None | Enabled |
| **Resource Limits** | None | CPU & memory limits set |
| **Logging** | Console | JSON formatted |
| **SSL** | None | Let's Encrypt |
| **Restart Policy** | No | `unless-stopped` |

## Deployment Checklist

- [ ] Digital Ocean droplet created and configured
- [ ] Docker & Docker Compose installed
- [ ] Repository cloned with `stg` branch
- [ ] `.env.stg` secrets configured
- [ ] Database migrations completed
- [ ] Services healthy and running
- [ ] Nginx reverse proxy configured
- [ ] SSL certificate installed
- [ ] DNS records pointing to server
- [ ] Backups automated
- [ ] Monitoring/logging setup
- [ ] Tested API endpoints

## Rollback Procedure

```bash
# If deployment fails, rollback to previous version
docker-compose -f docker-compose.stg.yml down
git checkout HEAD~1
docker-compose -f docker-compose.stg.yml up -d
```

## Support & Monitoring

- Monitor via: `docker stats` and container logs
- Set up uptime monitoring with UptimeRobot or similar
- Configure alerts for service failures
- Enable firewall rules to restrict access as needed
