# GitHub Actions - Staging Deployment Configuration

## Required GitHub Secrets

Set these secrets in your GitHub repository settings for the CI/CD pipeline to work:

### Digital Ocean SSH Configuration

1. **`DO_HOST`** - Digital Ocean Droplet IP Address
   - Value: `157.245.102.69`
   - Type: Secret

2. **`DO_USER`** - SSH User (usually `root` for Digital Ocean)
   - Value: `root`
   - Type: Secret

3. **`DO_SSH_KEY`** - Private SSH Key
   - Value: Content of your private key (C:\Users\rashm\digital)
   - Type: Secret
   - How to set:
     ```bash
     # On Windows, read the private key
     type C:\Users\rashm\digital | clip
     # Then paste in GitHub Secrets
     ```

### Environment Variables

4. **`STG_ENV_VARS`** - All staging environment variables
   - Type: Secret (multi-line)
   - Value: Content of `.env.stg` file
   - How to set:
     ```bash
     cat > env_vars.txt << 'EOF'
     APP_NAME=Flood Backend - Staging
     APP_ENV=staging
     APP_HOST=0.0.0.0
     APP_PORT=8000
     APP_DEBUG=false
     LOG_LEVEL=info
     
     STAGING_DOMAIN=stg.floodsense.lk
     STAGING_URL=https://stg.floodsense.lk
     FRONTEND_URL=https://stg-web.floodsense.lk
     
     ALLOWED_ORIGINS=https://stg-web.floodsense.lk,https://stg.floodsense.lk
     
     POSTGRES_USER=flood_stg_user
     POSTGRES_PASSWORD=<your-secure-password>
     POSTGRES_DB=flooddb_stg
     DATABASE_URL=postgresql+psycopg://flood_stg_user:<your-secure-password>@postgres:5432/flooddb_stg
     
     INFLUXDB_URL=http://influxdb:8086
     INFLUXDB_USERNAME=admin
     INFLUXDB_PASSWORD=<your-influx-password>
     INFLUXDB_ORG=flood-staging
     INFLUXDB_BUCKET=telemetry-stg
     INFLUXDB_TOKEN=<your-influx-token>
     INFLUXDB_PORT=8086
     INFLUXDB_HOST=influxdb
     
     CLERK_JWKS_URL=https://useful-hen-13.clerk.accounts.dev/.well-known/jwks.json
     CLERK_ISSUER=https://useful-hen-13.clerk.accounts.dev
     CLERK_WEBHOOK_SECRET=<your-webhook-secret>
     
     MQTT_BROKER=mosquitto
     MQTT_PORT=1883
     MQTT_TOPIC=flood/sensors/#
     MQTT_USERNAME=mqtt_stg_user
     MQTT_PASSWORD=<your-mqtt-password>
     
     KAFKA_BROKER=kafka:9092
     KAFKA_TOPIC=flood-sensor-data
     KAFKA_SECURITY_PROTOCOL=PLAINTEXT
     
     SENSOR_OFFLINE_MINUTES=15
     
     LOG_FORMAT=json
     LOG_OUTPUT=stdout
     
     HEALTH_CHECK_INTERVAL=30
     HEALTH_CHECK_TIMEOUT=10
     EOF
     # Now copy content to GitHub Secrets
     ```

## Setting Secrets in GitHub

### Method 1: Using GitHub Web UI

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret:
   - Name: `DO_HOST`
   - Value: `157.245.102.69`
5. Click **Add secret**
6. Repeat for other secrets

### Method 2: Using GitHub CLI

```bash
# Login to GitHub
gh auth login

# Set secrets
gh secret set DO_HOST --body "157.245.102.69"
gh secret set DO_USER --body "root"
gh secret set DO_SSH_KEY < C:\Users\rashm\digital
gh secret set STG_ENV_VARS < env_vars.txt
```

## Workflow Files

### 1. `deploy-stg.yml` - Automatic Deployment

**Triggered by:**
- Push to `stg` branch
- Manual workflow dispatch

**Steps:**
1. ✅ Lint & validate configurations
2. 🐳 Build Docker images
3. 📤 Push to GitHub Container Registry
4. 🚀 Deploy to Digital Ocean via SSH
5. 🏥 Run health checks
6. 📢 Notify completion

**Usage:**
```bash
# Automatic on push
git push origin stg

# Or manual trigger
# Go to: GitHub → Actions → Deploy to Staging → Run workflow
```

### 2. `manual-deploy-stg.yml` - Manual Control

**Triggered by:**
- Manual workflow dispatch only

**Actions:**
- `deploy` - Deploy latest version
- `rollback` - Rollback to previous commit
- `restart` - Restart all services
- `healthcheck` - Run health checks

**Usage:**
```
Go to: GitHub → Actions → Manual Deploy to Staging → Run workflow
→ Select action → Click "Run workflow"
```

## Deployment Flow

```
┌─────────────────────────────────────────┐
│ Code Push to stg Branch                 │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ GitHub Actions Triggered                │
│ - Lint & Test (validate configs)        │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Build & Push Docker Images              │
│ - API Service                           │
│ - Sensor Service                        │
│ - Intelligence Service                  │
│ - Zone Service                          │
│ - MQTT-Kafka Bridge                     │
│ - Kafka-InfluxDB Bridge                 │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ SSH to Digital Ocean Droplet            │
│ - Pull latest code                      │
│ - Update .env.stg                       │
│ - Stop existing services                │
│ - Start new services                    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Post-Deployment                         │
│ - Wait for services (30s)               │
│ - Run database migrations               │
│ - Run health checks                     │
│ - Display service status                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Deployment Complete ✅                  │
│ URL: https://stg.floodsense.lk          │
└─────────────────────────────────────────┘
```

## Environment-Specific Settings

### GitHub Environments

The workflow uses the `staging` environment with:

```yaml
environment:
  name: staging
  url: https://stg.floodsense.lk
```

This allows you to:
- Set environment-specific secrets
- Require approvals before deployment
- Track deployments by environment
- Set deployment branch rules

## Monitoring Deployments

### View Workflow Runs

1. Go to your repository
2. Click **Actions** tab
3. Select **Deploy to Staging** workflow
4. View run logs and status

### View Deployment History

1. Go to repository **Environments**
2. Click **Staging**
3. View deployment timeline

### SSH into Droplet for Manual Checks

```bash
ssh -i "C:\Users\rashm\digital" root@157.245.102.69

# View logs
cd /opt/flood-backend
docker compose -f docker-compose.stg.yml logs -f

# View service status
docker compose -f docker-compose.stg.yml ps

# Check Kong status
curl http://localhost:8001/status | jq
```

## Troubleshooting

### Workflow Fails on Secrets

**Error:** `"DO_HOST" is not set`

**Solution:** 
- Ensure all secrets are set in GitHub Settings → Secrets
- Check secret names match exactly (case-sensitive)
- Verify secrets aren't empty

### Deployment Fails on SSH Connection

**Error:** `Permission denied (publickey)`

**Solution:**
- Ensure `DO_SSH_KEY` contains the ENTIRE private key (including BEGIN/END lines)
- Verify key permissions: `chmod 600 ~/.ssh/id_rsa`
- Test locally: `ssh -i C:\Users\rashm\digital root@157.245.102.69`

### Services Not Starting After Deployment

**Debug:**
```bash
ssh -i "C:\Users\rashm\digital" root@157.245.102.69
cd /opt/flood-backend
docker compose -f docker-compose.stg.yml logs postgres
docker compose -f docker-compose.stg.yml logs api
```

### Rollback a Deployment

**Option 1: Via GitHub UI**
- Actions → Manual Deploy to Staging → Run workflow
- Select action: `rollback`

**Option 2: Via CLI**
```bash
ssh -i "C:\Users\rashm\digital" root@157.245.102.69
cd /opt/flood-backend
git log --oneline -10
git checkout <commit-hash>
docker compose --env-file .env.stg -f docker-compose.stg.yml restart
```

## Performance Optimization

### Docker Image Caching

The workflow uses GitHub Actions Cache for faster builds:
- `cache-from: type=gha`
- `cache-to: type=gha,mode=max`

This reduces build time significantly on subsequent runs.

### Parallel Job Execution

- Lint & Test runs first
- Build & Push runs after validation
- Deploy waits for Build & Push completion
- Notify runs regardless of other job results

## Security Best Practices

✅ **Implemented:**
- SSH key-based authentication (no passwords)
- Secrets stored in GitHub (encrypted)
- SSH agent forwarding not used
- Restricted environment permissions
- Auto-health checks post-deployment

📋 **Recommended:**
- Rotate SSH keys every 90 days
- Enable branch protection rules
- Require approvals for production
- Monitor workflow run history
- Enable audit logging

## Support & Documentation

For more information:
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Secrets Management](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [SSH Action Documentation](https://github.com/appleboy/ssh-action)
- [Docker Buildx Action](https://github.com/docker/build-push-action)
