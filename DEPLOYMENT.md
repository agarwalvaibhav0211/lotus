# Lotus Deployment Guide

Complete step-by-step guide to deploy Lotus on an existing Docker Compose + Caddy stack with strict network isolation.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Step 1: Environment Setup](#step-1-environment-setup)
5. [Step 2: Configure Lotus Environment](#step-2-configure-lotus-environment)
6. [Step 3: Configure Caddy](#step-3-configure-caddy)
7. [Step 4: Prepare Your Existing Stack](#step-4-prepare-your-existing-stack)
8. [Step 5: Deploy Lotus](#step-5-deploy-lotus)
9. [Step 6: Initialize Database](#step-6-initialize-database)
10. [Step 7: Verification](#step-7-verification)
11. [Troubleshooting](#troubleshooting)
12. [Post-Deployment](#post-deployment)

---

## Prerequisites

### Required Software
- Docker & Docker Compose (v1.29+)
- Caddy (v2.0+) running on your existing stack
- Bash shell
- `curl` for testing APIs
- Text editor for configuration files

### System Requirements
- **CPU**: 2-4 cores minimum
- **RAM**: 4-8GB recommended
- **Disk**: 20GB+ for data and logs
- **Network**: Ports 80/443 available (Caddy), others handled internally

### Access Requirements
- SSH or direct access to the deployment server
- Root or sudo privileges for Docker operations
- Write access to Docker volumes directory

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    External Traffic (HTTPS)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼─────┐
                    │   Caddy     │ (Your existing stack)
                    │ Reverse     │ Listens on :80, :443
                    │ Proxy       │
                    └──────┬──────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
    ┌─────▼────────┐            ┌──────────▼──────────┐
    │  SHARED NET  │            │  LOTUS-INTERNAL NET │
    │  (external)  │            │  (isolated)         │
    │              │            │                     │
    │ - Caddy      │◄──────────►│ - Frontend:80       │
    │              │            │ - Backend:8000      │
    │              │            │ - Event-Ingestion   │
    │              │            │ - Event-Guidance    │
    │              │            │ - Redis, DB, etc.   │
    └──────────────┘            │ - Workers           │
                                └─────────────────────┘
                                       (Isolated)
```

**Key Points:**
- Only `frontend` is exposed to the shared network
- All internal Lotus infrastructure is completely isolated
- Caddy proxies all requests to `lotus-frontend:80`
- Frontend Nginx handles internal routing via lotus-internal network

---

## Pre-Deployment Checklist

- [ ] Docker & Docker Compose installed and working
- [ ] Caddy service running on your existing stack
- [ ] Shared network (`shared`) already created by your existing docker-compose.yml
- [ ] DNS/domain pointing to your server
- [ ] HTTPS certificates configured in Caddy
- [ ] 4GB+ free RAM available
- [ ] 20GB+ free disk space
- [ ] Backup of existing configurations

---

## Step 1: Environment Setup

### 1.1 Verify Your Existing Stack

Check that your existing docker-compose has the shared network configured:

```bash
cd /path/to/your/stack
docker network ls | grep shared
```

Expected output:
```
xxxxx        shared           bridge      local
```

If the network doesn't exist, add it to your docker-compose.yml:

```yaml
networks:
  shared:
    driver: bridge

services:
  caddy:
    networks:
      - shared
  # ... other services
```

Then run:
```bash
docker-compose up -d
```

### 1.2 Verify Your Caddy Setup

Test that Caddy is running:

```bash
docker ps | grep caddy
```

Check Caddy's logs for errors:

```bash
docker logs <caddy-container-id>
```

---

## Step 2: Configure Lotus Environment

### 2.1 Copy Environment Template

Navigate to the Lotus directory:

```bash
cd /path/to/lotus
```

Copy the production environment template:

```bash
cp env/.env.prod.example env/.env.prod
```

### 2.2 Edit Environment Variables

Open `env/.env.prod` in your editor:

```bash
nano env/.env.prod
```

Configure the following critical variables:

**Database:**
```
POSTGRES_USER=lotus
POSTGRES_PASSWORD=<generate-strong-password>
POSTGRES_DB=lotus
```

**Django Security:**
```
SECRET_KEY=<generate-with: openssl rand -hex 32>
SELF_HOSTED=True
DOCKERIZED=True
DJANGO_SETTINGS_MODULE=lotus.settings
```

**Admin Credentials:**
```
ADMIN_USERNAME=<your-admin-username>
ADMIN_EMAIL=<your-email>
ADMIN_PASSWORD=<your-admin-password>
```

**Frontend:**
```
NODE_ENV=production
VITE_API_URL=https://yourdomain.com/
VITE_NANGO_PK=<your-nango-pk-if-using>
```

**Payment Processors (Optional):**
```
STRIPE_LIVE_SECRET_KEY=sk_live_...
STRIPE_LIVE_CLIENT=ca_...
STRIPE_TEST_SECRET_KEY=sk_test_...
STRIPE_TEST_CLIENT=ca_...
STRIPE_WEBHOOK_SECRET=whsec_...

BRAINTREE_LIVE_MERCHANT_ID=...
BRAINTREE_LIVE_PUBLIC_KEY=...
BRAINTREE_LIVE_SECRET_KEY=...
```

**AWS (Optional, for file uploads):**
```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

**Optional Integrations:**
```
TAXJAR_API_KEY=...
SVIX_JWT_SECRET=<generate-strong-password>
```

### 2.3 Generate Secure Passwords

```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate SVIX_JWT_SECRET
openssl rand -hex 32

# Generate POSTGRES_PASSWORD
openssl rand -hex 16
```

### 2.4 Verify Environment File

Check that all required variables are set:

```bash
grep -E "change_me|^$" env/.env.prod
```

Only comments and empty lines should appear. If you see `change_me`, update those values.

---

## Step 3: Configure Caddy

### 3.1 Update Your Caddyfile

Edit your Caddy configuration file (typically `Caddyfile` or `caddy/Caddyfile`):

```caddyfile
# Your existing services can stay as-is

# Add Lotus routing
yourdomain.com {
  # Lotus - all requests proxy to frontend
  # Frontend Nginx handles internal routing
  reverse_proxy lotus-frontend:80 {
    header_uri -X-Forwarded-Proto http
    header_uri -X-Forwarded-For
    header_uri -X-Url-Scheme
  }
}
```

**If you have multiple domains/subdomains:**

```caddyfile
yourdomain.com {
  # Lotus runs on root domain
  reverse_proxy lotus-frontend:80 {
    header_uri -X-Forwarded-Proto http
    header_uri -X-Forwarded-For
  }
}

api.yourdomain.com {
  # Your other services continue here
  reverse_proxy your-service:port
}
```

### 3.2 Reload Caddy

After updating the Caddyfile:

```bash
# If Caddy is in a container
docker exec <caddy-container-id> caddy reload

# If Caddy is running locally
caddy reload
```

Verify no errors:

```bash
docker logs <caddy-container-id> | tail -20
```

---

## Step 4: Prepare Your Existing Stack

### 4.1 Verify Shared Network

Ensure your existing docker-compose.yml has:

```yaml
networks:
  shared:
    driver: bridge

services:
  # All services should have:
  service-name:
    networks:
      - shared
```

### 4.2 Update All Services (If Needed)

Every service in your existing stack should connect to the shared network:

```yaml
services:
  caddy:
    networks:
      - shared
    # ... rest of config
  
  your-service:
    networks:
      - shared
    # ... rest of config
```

### 4.3 Restart Existing Stack

```bash
cd /path/to/your/stack
docker-compose up -d
```

Verify all services are running:

```bash
docker-compose ps
```

---

## Step 5: Deploy Lotus

### 5.1 Build Docker Images

Navigate to Lotus directory:

```bash
cd /path/to/lotus
```

Build all Lotus services:

```bash
docker-compose -f docker-compose.prod.yaml build
```

This may take 10-15 minutes depending on your internet speed and system performance.

Monitor build progress:

```bash
# In another terminal, watch Docker
docker ps
docker images | grep lotus
```

### 5.2 Start Lotus Services

Start all services in the background:

```bash
docker-compose -f docker-compose.prod.yaml up -d
```

### 5.3 Verify Services Are Starting

Check service status:

```bash
docker-compose -f docker-compose.prod.yaml ps
```

Expected output:
```
NAME                COMMAND                  SERVICE             STATUS              PORTS
lotus-backend       "sh -c './scripts/..."   backend             Up 2 minutes
lotus-celery        "bash -c 'while !..."    celery              Up 2 minutes
lotus-celery-beat   "bash -c 'while !..."    celery-beat         Up 2 minutes
lotus-db            "postgres"               db                  Up 3 minutes
lotus-event-guidance "event-guidance"        event-guidance      Up 2 minutes
lotus-event-ingestion "/app/app"             event-ingestion     Up 2 minutes
lotus-frontend      "nginx -g daemon off"    frontend            Up 2 minutes
lotus-redis         "redis-server"           redis               Up 3 minutes
lotus-redpanda      "/entrypoint.sh"         redpanda            Up 3 minutes
lotus-svix-server   "svix-server"            svix-server         Up 2 minutes
```

All services should show `Up`.

### 5.4 Check Logs for Errors

```bash
# Check all logs
docker-compose -f docker-compose.prod.yaml logs -f

# Check specific service logs
docker-compose -f docker-compose.prod.yaml logs -f backend
docker-compose -f docker-compose.prod.yaml logs -f frontend
```

Wait 30-60 seconds for services to fully initialize. You may see some initial errors as services wait for dependencies—this is normal.

---

## Step 6: Initialize Database

### 6.1 Run Migrations

Apply Django database migrations:

```bash
docker-compose -f docker-compose.prod.yaml exec backend python manage.py migrate
```

Expected output:
```
Operations to perform:
  Apply all migrations: ...
Running migrations:
  Applying ... OK
```

### 6.2 Create Admin User

Create the superuser account:

```bash
docker-compose -f docker-compose.prod.yaml exec backend python manage.py createsuperuser
```

Follow the prompts to set username and password (use values from env/.env.prod).

Alternative (non-interactive):

```bash
docker-compose -f docker-compose.prod.yaml exec backend python manage.py createsuperuser \
  --username=$ADMIN_USERNAME \
  --email=$ADMIN_EMAIL \
  --noinput
```

Then set the password:

```bash
docker-compose -f docker-compose.prod.yaml exec backend python manage.py changepassword $ADMIN_USERNAME
```

### 6.3 Collect Static Files

```bash
docker-compose -f docker-compose.prod.yaml exec backend python manage.py collectstatic --noinput
```

---

## Step 7: Verification

### 7.1 Test Web Access

Open your browser and navigate to:

```
https://yourdomain.com
```

You should see the Lotus login page.

### 7.2 Login

Log in with:
- Username: `ADMIN_USERNAME` from env/.env.prod
- Password: `ADMIN_PASSWORD` from env/.env.prod

### 7.3 Verify Services Are Healthy

**Check backend API:**

```bash
curl -X GET https://yourdomain.com/api/health/
```

Expected response (if health endpoint exists):
```json
{"status": "ok"}
```

**Check event ingestion:**

```bash
curl -X POST https://yourdomain.com/api/track \
  -H "Content-Type: application/json" \
  -d '{"test": "event"}'
```

### 7.4 Check Service Logs

Monitor logs for any errors:

```bash
docker-compose -f docker-compose.prod.yaml logs --tail=50
```

### 7.5 Test Admin Panel

Navigate to:

```
https://yourdomain.com/admin
```

Log in with admin credentials.

---

## Troubleshooting

### Services Won't Start

**Symptom:** Services show `Exit` or `Restarting`

**Solution:**

1. Check logs:
   ```bash
   docker-compose -f docker-compose.prod.yaml logs backend
   ```

2. Common issues:
   - Database not initialized: Run migrations again
   - Port conflict: Check if ports are already in use
   - Network issues: Verify lotus-internal network exists

### Database Connection Errors

**Symptom:** Backend logs show `could not connect to server`

**Solution:**

1. Verify database is running:
   ```bash
   docker-compose -f docker-compose.prod.yaml ps db
   ```

2. Check database logs:
   ```bash
   docker-compose -f docker-compose.prod.yaml logs db
   ```

3. Check environment variables:
   ```bash
   cat env/.env.prod | grep POSTGRES
   ```

4. Restart database:
   ```bash
   docker-compose -f docker-compose.prod.yaml restart db
   ```

### Frontend Not Loading

**Symptom:** Browser shows connection refused or blank page

**Solution:**

1. Verify frontend is running:
   ```bash
   docker-compose -f docker-compose.prod.yaml ps frontend
   ```

2. Check Nginx configuration:
   ```bash
   docker-compose -f docker-compose.prod.yaml exec frontend nginx -t
   ```

3. Check Caddy is routing correctly:
   ```bash
   docker logs <caddy-container> | grep lotus
   ```

### API Calls Failing

**Symptom:** Frontend loads but API requests fail

**Solution:**

1. Check backend is running:
   ```bash
   docker-compose -f docker-compose.prod.yaml ps backend
   ```

2. Test backend directly:
   ```bash
   docker-compose -f docker-compose.prod.yaml exec frontend \
     curl http://backend:8000/api/
   ```

3. Check frontend Nginx routing:
   ```bash
   docker-compose -f docker-compose.prod.yaml exec frontend nginx -T
   ```

### Event Ingestion Not Working

**Symptom:** Events are not being processed

**Solution:**

1. Check event-ingestion logs:
   ```bash
   docker-compose -f docker-compose.prod.yaml logs event-ingestion
   ```

2. Verify Redpanda is running:
   ```bash
   docker-compose -f docker-compose.prod.yaml ps redpanda
   ```

3. Check Celery workers:
   ```bash
   docker-compose -f docker-compose.prod.yaml logs celery
   ```

### Caddy SSL/TLS Issues

**Symptom:** HTTPS shows certificate errors

**Solution:**

1. Check Caddy logs:
   ```bash
   docker logs <caddy-container>
   ```

2. Verify DNS is pointing to your server:
   ```bash
   nslookup yourdomain.com
   ```

3. Reload Caddy with new certificates:
   ```bash
   docker exec <caddy-container> caddy reload
   ```

---

## Post-Deployment

### 6.1 Backup Configuration

Backup your configuration files:

```bash
# Backup environment file
cp env/.env.prod env/.env.prod.backup

# Backup Caddyfile
cp /path/to/Caddyfile /path/to/Caddyfile.backup

# Backup docker-compose files
cp docker-compose.prod.yaml docker-compose.prod.yaml.backup
```

### 6.2 Setup Log Monitoring

Monitor logs continuously:

```bash
# Watch all Lotus logs
docker-compose -f docker-compose.prod.yaml logs -f

# Watch specific service
docker-compose -f docker-compose.prod.yaml logs -f backend
```

Or use a log aggregation tool.

### 6.3 Setup Backups

Create a backup script for PostgreSQL:

```bash
#!/bin/bash
BACKUP_DIR="/backups/lotus"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

docker-compose -f docker-compose.prod.yaml exec -T db \
  pg_dump -U lotus lotus > $BACKUP_DIR/lotus_$TIMESTAMP.sql

# Keep only last 7 days
find $BACKUP_DIR -mtime +7 -delete
```

Schedule with cron:

```bash
crontab -e
# Add: 0 2 * * * /path/to/backup.sh
```

### 6.4 Monitor Resources

Watch system resources:

```bash
# Watch Docker stats
docker stats

# Check disk usage
df -h

# Check memory
free -h
```

### 6.5 Create Admin Users

To create additional admin users:

```bash
docker-compose -f docker-compose.prod.yaml exec backend \
  python manage.py createsuperuser
```

### 6.6 Test Payment Processor Integration (If Using)

1. Log in to admin panel
2. Navigate to Settings → Payment Processors
3. Add Stripe or Braintree credentials
4. Run a test transaction

### 6.7 Setup Webhooks (If Using Svix)

1. Configure webhook endpoints in Lotus admin
2. Test webhook delivery
3. Monitor webhook logs

### 6.8 Performance Tuning

Monitor backend performance:

```bash
# Check Django settings
docker-compose -f docker-compose.prod.yaml exec backend \
  python manage.py check
```

Scale Celery workers if needed:

```bash
# Increase replicas in docker-compose.prod.yaml
# Then restart
docker-compose -f docker-compose.prod.yaml up -d celery
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Check logs for errors
- Verify web accessibility
- Monitor disk space

**Weekly:**
- Review backup completion
- Check resource usage
- Test admin panel access

**Monthly:**
- Review and archive logs
- Update Docker images (if needed)
- Test disaster recovery procedures

### Updating Lotus

To update to a new version:

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker-compose -f docker-compose.prod.yaml build

# Restart services
docker-compose -f docker-compose.prod.yaml down
docker-compose -f docker-compose.prod.yaml up -d

# Run migrations
docker-compose -f docker-compose.prod.yaml exec backend python manage.py migrate
```

### Stopping Lotus

To gracefully stop all Lotus services:

```bash
docker-compose -f docker-compose.prod.yaml down

# Keep volumes/data intact
# To remove volumes too (careful!):
# docker-compose -f docker-compose.prod.yaml down -v
```

---

## Support

For issues or questions:

1. **Check logs first:**
   ```bash
   docker-compose -f docker-compose.prod.yaml logs
   ```

2. **Review this guide** for common issues

3. **Check Lotus documentation:** https://docs.uselotus.io/

4. **Open an issue:** https://github.com/agarwalvaibhav0211/lotus/issues

---

## Quick Reference

### Common Commands

```bash
# Start all services
docker-compose -f docker-compose.prod.yaml up -d

# Stop all services
docker-compose -f docker-compose.prod.yaml down

# View logs
docker-compose -f docker-compose.prod.yaml logs -f

# Restart a service
docker-compose -f docker-compose.prod.yaml restart backend

# Execute command in container
docker-compose -f docker-compose.prod.yaml exec backend python manage.py shell

# View service status
docker-compose -f docker-compose.prod.yaml ps
```

### Network Isolation Verification

```bash
# List networks
docker network ls

# Inspect shared network
docker network inspect shared

# Inspect lotus-internal network
docker network inspect lotus-internal

# Check which containers are on each network
docker network inspect shared --format='{{json .Containers}}' | jq .
```

---

**Deployment completed!** 🎉

Your Lotus instance is now running with strict network isolation, properly integrated with your existing Docker Compose + Caddy stack.
