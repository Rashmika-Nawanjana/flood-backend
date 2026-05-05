# FloodSense Staging Deployment - README

## Overview

This directory contains configurations for deploying the FloodSense backend to Digital Ocean staging environment. The setup removes all local development tools (like ngrok, PgAdmin, and debug ports) and optimizes for production deployment.

## Files

- **`docker-compose.stg.yml`** - Production-optimized Docker Compose configuration
  - Removes local port bindings
  - Adds health checks for all services
  - Sets resource limits and restart policies
  - Uses Alpine images for smaller footprint
  - Removes development services

- **`.env.stg`** - Staging environment variables
  - Production-ready configuration
  - Staging domain setup
  - Database and service credentials (placeholders)
  - SSL configuration for staging

- **`DIGITAL_OCEAN_DEPLOYMENT.md`** - Complete deployment guide
  - Step-by-step setup instructions
  - Prerequisites and requirements
  - SSL/TLS configuration
  - Backup and monitoring setup
  - Troubleshooting guide

- **`deploy-stg.sh`** - Automated deployment script
  - Validates prerequisites
  - Checks out stg branch
  - Builds and starts containers
  - Runs database migrations
  - Performs health checks

## Quick Start

### Option 1: Manual Deployment

```bash
# 1. SSH into Digital Ocean droplet
ssh root@<your-droplet-ip>

# 2. Navigate to project directory
cd /opt/flood-backend
git checkout stg

# 3. Configure environment
cp .env.stg .env.stg.local
# Edit .env.stg.local with your secrets

# 4. Deploy
docker-compose -f docker-compose.stg.yml up -d

# 5. Check status
docker-compose -f docker-compose.stg.yml ps
```

### Option 2: Automated Deployment

```bash
# Make script executable
chmod +x deploy-stg.sh

# Run deployment
./deploy-stg.sh

# Script will:
# - Validate prerequisites
# - Verify stg branch
# - Build containers
# - Start services
# - Run migrations
# - Perform health checks
```

## Architecture

```
┌─────────────────────────────────────────┐
│      Digital Ocean (Staging)            │
├─────────────────────────────────────────┤
│  Nginx (Reverse Proxy + SSL)            │
│         ↓                               │
│  Kong API Gateway (port 80/443)         │
│         ↓                               │
├─────────────────────────────────────────┤
│  Microservices (Internal Network)       │
├─────────────────────────────────────────┤
│  • API Service (port 8000)              │
│  • Sensor Service (port 8002)           │
│  • Intelligence Service (port 8003)     │
│  • Zone Service (port 8004)             │
├─────────────────────────────────────────┤
│  Data Services                          │
├─────────────────────────────────────────┤
│  • PostgreSQL (port 5432)               │
│  • InfluxDB (port 8086)                 │
│  • Kafka (port 9092)                    │
│  • Zookeeper (port 2181)                │
├─────────────────────────────────────────┤
│  Bridges                                │
├─────────────────────────────────────────┤
│  • MQTT-Kafka Bridge                    │
│  • Kafka-InfluxDB Bridge                │
└─────────────────────────────────────────┘
```

## Key Changes from Development

### Removed Services
- ❌ ngrok (not needed with domain)
- ❌ PgAdmin (use SSH tunnel if needed)
- ❌ Debug ports for services

### Added Features
- ✅ Health checks for all services
- ✅ Resource limits (CPU/Memory)
- ✅ Restart policies (`unless-stopped`)
- ✅ Alpine base images (smaller size)
- ✅ JSON logging
- ✅ Service dependencies with health conditions
- ✅ Volume persistence
- ✅ Network isolation

## Environment Variables

### Required (Set in .env.stg)
```
POSTGRES_PASSWORD_STG=<strong-password>
INFLUXDB_PASSWORD_STG=<strong-password>
INFLUXDB_TOKEN_STG=<generated-token>
CLERK_WEBHOOK_SECRET_STG=<webhook-secret>
MQTT_BROKER_HOST=<mqtt-host>
MQTT_USERNAME_STG=<mqtt-user>
MQTT_PASSWORD_STG=<mqtt-password>
```

### Optional
- `APP_DEBUG` - Set to `false` for production
- `LOG_LEVEL` - Set to `info` or `warn` for production
- `STAGING_DOMAIN` - Your staging domain
- `ALLOWED_ORIGINS` - CORS origins

## Deployment Commands

### Check Service Status
```bash
docker-compose -f docker-compose.stg.yml ps
```

### View Logs
```bash
docker-compose -f docker-compose.stg.yml logs -f <service-name>
docker-compose -f docker-compose.stg.yml logs -f --tail=100
```

### Enter Service Container
```bash
docker-compose -f docker-compose.stg.yml exec <service> bash
docker-compose -f docker-compose.stg.yml exec postgres psql -U flood_stg_user -d flooddb_stg
```

### Restart Services
```bash
docker-compose -f docker-compose.stg.yml restart
docker-compose -f docker-compose.stg.yml restart <service-name>
```

### Stop Services
```bash
docker-compose -f docker-compose.stg.yml stop
```

### Remove Everything and Rebuild
```bash
docker-compose -f docker-compose.stg.yml down -v
docker-compose -f docker-compose.stg.yml up -d
```

## Monitoring

### Container Health
```bash
docker stats
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Service Connectivity
```bash
# Test Kong gateway
curl -i http://localhost:8001/status

# Test API
curl http://localhost:8000/health

# Test database
docker-compose -f docker-compose.stg.yml exec postgres pg_isready

# Test InfluxDB
docker-compose -f docker-compose.stg.yml exec influxdb influx ping
```

## Backup & Restore

### Backup Database
```bash
docker-compose -f docker-compose.stg.yml exec -T postgres \
    pg_dump -U flood_stg_user flooddb_stg | gzip > backup-$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore Database
```bash
docker-compose -f docker-compose.stg.yml exec -T postgres \
    psql -U flood_stg_user flooddb_stg < backup-YYYYMMDD_HHMMSS.sql
```

## SSL/TLS Configuration

This setup requires Nginx and Let's Encrypt SSL certificates. See `DIGITAL_OCEAN_DEPLOYMENT.md` for detailed SSL setup instructions.

## Troubleshooting

### Services not starting
```bash
# Check logs
docker-compose -f docker-compose.stg.yml logs

# Verify configuration
docker-compose -f docker-compose.stg.yml config

# Check resource availability
docker stats
```

### Database connection issues
```bash
# Verify PostgreSQL
docker-compose -f docker-compose.stg.yml exec postgres psql -U flood_stg_user -c "\l"

# Check environment variables
docker-compose -f docker-compose.stg.yml exec api printenv | grep DATABASE_URL
```

### Health check failures
```bash
# Check service health
docker-compose -f docker-compose.stg.yml exec api curl localhost:8000/health
docker-compose -f docker-compose.stg.yml exec postgres pg_isready -U flood_stg_user
```

## Security Checklist

- [ ] Change default passwords in .env.stg
- [ ] Enable firewall rules (UFW/Digital Ocean Cloud Firewall)
- [ ] Setup SSH key authentication
- [ ] Disable password SSH login
- [ ] Enable automatic security updates
- [ ] Setup monitoring and alerts
- [ ] Regular backup automation
- [ ] SSL/TLS certificates installed
- [ ] Rate limiting configured in Kong
- [ ] Database backups automated and tested

## Support

For detailed deployment steps, see `DIGITAL_OCEAN_DEPLOYMENT.md`

For troubleshooting and additional information, refer to:
- Docker documentation: https://docs.docker.com/
- Docker Compose documentation: https://docs.docker.com/compose/
- Kong documentation: https://docs.konghq.com/
- Digital Ocean guides: https://docs.digitalocean.com/
