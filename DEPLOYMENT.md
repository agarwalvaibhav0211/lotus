# Lotus Deployment Guide

Deploy Lotus using pre-built images from GitHub Container Registry (GHCR). Images are built and pushed automatically by CI on every merge to `main` and on every published release.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Step 1: Choose an Image Tag](#step-1-choose-an-image-tag)
4. [Step 2: Configure the Environment](#step-2-configure-the-environment)
5. [Step 3: Set Up the Shared Network](#step-3-set-up-the-shared-network)
6. [Step 4: Configure Caddy](#step-4-configure-caddy)
7. [Step 5: Pull and Start Services](#step-5-pull-and-start-services)
8. [Step 6: Initialize the Database](#step-6-initialize-the-database)
9. [Step 7: Verify the Deployment](#step-7-verify-the-deployment)
10. [Updating to a New Version](#updating-to-a-new-version)
11. [Building from Source](#building-from-source)
12. [Maintenance](#maintenance)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Docker Engine 24+ and Docker Compose v2 (`docker compose` plugin, not `docker-compose`)
- Caddy v2 running as a reverse proxy with access to a `caddy_net` Docker network
- A domain pointed at your server with HTTPS handled by Caddy
- 4 GB RAM, 20 GB free disk

---

## Architecture Overview

```
Internet (HTTPS)
      │
   ┌──▼──────────┐
   │    Caddy    │  ← your existing reverse-proxy stack
   └──┬──────────┘
      │ proxies to lotus-frontend:80
      │
┌─────▼──────────────────────────────────────────┐
│  caddy_net  (external Docker network)           │
│  frontend:80  ←────────────────────────────┐   │
└────────────────────────────────────────────┼───┘
                                             │
┌────────────────────────────────────────────┼───┐
│  lotus-internal  (bridge, isolated)        │   │
│                                            │   │
│  frontend ─────────────────────────────────┘   │
│      │                                         │
│      ├─► backend:8000   (Django / Gunicorn)     │
│      ├─► event-ingestion:7998  (Go)             │
│      └─► event-guidance:7999  (Go)             │
│                                                 │
│  backend ──► db:5432  (TimescaleDB/Postgres)    │
│  backend ──► redis:6379                         │
│  backend ──► redpanda:29092  (Kafka)            │
│  backend ──► svix-server:8071  (webhooks)       │
│                                                 │
│  celery, celery-beat  (same image as backend)   │
└─────────────────────────────────────────────────┘
```

Only `frontend` is on the `caddy_net` network. Everything else is isolated inside `lotus-internal`.

---

## Step 1: Choose an Image Tag

All four application images are published to GHCR under:

```
ghcr.io/agarwalvaibhav0211/lotus/{service}:{tag}
```

where `{service}` is `backend`, `frontend`, `event-ingestion`, or `event-guidance`.

| Tag | When to use |
|-----|-------------|
| `latest` | Most recent build from `main` — always up to date |
| `v1.2.3` | A specific release — recommended for production |
| `sha-a1b2c3d...` | A specific commit — useful for debugging |

To list available tags:

```bash
# requires gh CLI and repo access
gh api /orgs/agarwalvaibhav0211/packages/container/lotus%2Fbackend/versions \
  --jq '.[].metadata.container.tags[]' | head -20
```

---

## Step 2: Configure the Environment

### 2.1 Get the repository

You only need two things from the repo: `docker-compose.prod.yaml` and the `env/` directory.

```bash
git clone https://github.com/agarwalvaibhav0211/lotus.git
cd lotus
```

Or if you don't want the full source:

```bash
mkdir lotus && cd lotus
curl -O https://raw.githubusercontent.com/agarwalvaibhav0211/lotus/main/docker-compose.prod.yaml
mkdir env
curl -o env/.env.prod.example \
  https://raw.githubusercontent.com/agarwalvaibhav0211/lotus/main/env/.env.prod.example
```

### 2.2 Create the env file

```bash
cp env/.env.prod.example env/.env.prod
```

> **Why `--env-file` is required on every `docker compose` command**
>
> The compose file uses `env_file: ./env/.env.prod` inside each service definition — that injects variables into the containers at runtime. However, `svix-server` also uses Docker Compose variable interpolation (`${POSTGRES_USER}`, `${POSTGRES_PASSWORD}`) to build its database DSN at parse time. Compose resolves those from the shell or a `.env` at the project root — not from `env_file`. Passing `--env-file env/.env.prod` on every invocation covers both: it feeds the interpolation and acts as the default env file. Without it, the Svix DSN silently becomes `postgresql://:@db` and Svix fails to connect.

### 2.3 Edit `env/.env.prod`

Open `env/.env.prod` and fill in every value marked `change_me`. The table below explains each variable.

#### Required

| Variable | Example | Notes |
|----------|---------|-------|
| `POSTGRES_USER` | `lotus` | Database user |
| `POSTGRES_PASSWORD` | *(generated)* | `openssl rand -hex 16` |
| `POSTGRES_DB` | `lotus` | Database name |
| `SECRET_KEY` | *(generated)* | `openssl rand -hex 32` |
| `ADMIN_USERNAME` | `admin` | Initial superuser login |
| `ADMIN_EMAIL` | `you@example.com` | Initial superuser email |
| `ADMIN_PASSWORD` | *(generated)* | Initial superuser password |
| `VITE_API_URL` | `https://yourdomain.com/` | Must end with `/` — used by the frontend to reach the API |
| `SVIX_JWT_SECRET` | *(generated)* | `openssl rand -hex 32` |
| `FIELD_ENCRYPTION_KEY` | *(generated)* | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` — encrypts per-organization secrets at rest (e.g. Munim API keys, webhook secrets). Losing this key makes existing encrypted data unrecoverable. |

#### Fixed values (do not change)

| Variable | Value |
|----------|-------|
| `SELF_HOSTED` | `True` |
| `DOCKERIZED` | `True` |
| `DJANGO_SETTINGS_MODULE` | `lotus.settings` |
| `KAFKA_URL` | `redpanda:29092` |

#### Optional integrations

| Variable | Purpose |
|----------|---------|
| `STRIPE_LIVE_SECRET_KEY` | Stripe live key (`sk_live_…`) |
| `STRIPE_LIVE_CLIENT` | Stripe live client ID (`ca_…`) |
| `STRIPE_TEST_SECRET_KEY` | Stripe test key (`sk_test_…`) |
| `STRIPE_TEST_CLIENT` | Stripe test client ID |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_…`) |
| `BRAINTREE_LIVE_MERCHANT_ID` | Braintree merchant ID |
| `BRAINTREE_LIVE_PUBLIC_KEY` | Braintree public key |
| `BRAINTREE_LIVE_SECRET_KEY` | Braintree secret key |
| `AWS_ACCESS_KEY_ID` | S3 file uploads |
| `AWS_SECRET_ACCESS_KEY` | S3 file uploads |
| `TAXJAR_API_KEY` | Tax calculation |
| `VITE_NANGO_PK` | Nango public key — enables Nango-based integrations in the frontend |
| `MUNIM_BASE_URL` | Munim API base URL (defaults to `https://api.munim.io` if unset) |

#### Quick secret generation

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "SVIX_JWT_SECRET=$(openssl rand -hex 32)"
echo "FIELD_ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
echo "ADMIN_PASSWORD=$(openssl rand -hex 12)"
```

Verify no placeholders remain:

```bash
grep "change_me" env/.env.prod
# should print nothing
```

### 2.4 Set image tag variables

The compose file reads three optional environment variables you can export in your shell or add to a `.env` file alongside `docker-compose.prod.yaml`:

| Variable | Default | Override to… |
|----------|---------|-------------|
| `LOTUS_IMAGE_REGISTRY` | `ghcr.io/agarwalvaibhav0211/lotus` | Use your own registry mirror |
| `LOTUS_IMAGE_TAG` | `latest` | Pin to a release, e.g. `v1.2.3` |
| `LOTUS_IMAGE_PULL_POLICY` | `missing` | Set to `always` to force re-pull on every `up` |

To deploy a specific release:

```bash
export LOTUS_IMAGE_TAG=v1.2.3
export LOTUS_IMAGE_PULL_POLICY=always
```

---

## Step 3: Set Up the Shared Network

Lotus's `frontend` service must join your existing `caddy_net` Docker network so Caddy can reach it.

Check if it already exists:

```bash
docker network ls | grep caddy_net
```

If not, create it:

```bash
docker network create caddy_net
```

If your Caddy is managed by its own docker-compose file, declare the network there as external in that file:

```yaml
# your existing caddy docker-compose.yml
networks:
  caddy_net:
    driver: bridge

services:
  caddy:
    networks:
      - caddy_net
```

Then recreate that stack so Caddy joins the network:

```bash
docker compose up -d   # in your Caddy directory
```

---

## Step 4: Configure Caddy

Add a block to your `Caddyfile` that proxies all traffic to the Lotus frontend container. The frontend's Nginx handles internal routing (API calls, event ingestion, static files) without Caddy needing to know about them.

```caddyfile
yourdomain.com {
    reverse_proxy lotus-frontend:80
}
```

Reload Caddy:

```bash
# Caddy in a container
docker exec <caddy-container> caddy reload --config /etc/caddy/Caddyfile

# Caddy on the host
caddy reload
```

---

## Step 5: Pull and Start Services

### 5.1 Log in to GHCR (if images are private)

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

Public images do not require a login.

### 5.2 Pull all images

```bash
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml pull
```

This pulls `backend`, `frontend`, `event-ingestion`, and `event-guidance` from GHCR, plus `timescaledb`, `redis`, `redpanda`, and `svix-server` from their public registries.

### 5.3 Start all services

```bash
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml up -d
```

Check that every service comes up:

```bash
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml ps
```

Expected:

```
NAME                STATUS
lotus-backend       Up
lotus-celery        Up
lotus-celery-beat   Up
lotus-db            Up
lotus-event-guidance  Up
lotus-event-ingestion Up
lotus-frontend      Up
lotus-redis         Up
lotus-redpanda      Up
lotus-svix-server   Up
```

Services that depend on the database (`backend`, `celery`, `celery-beat`) will restart a few times while the DB initialises — this is normal.

---

## Step 6: Initialize the Database

Run these once on first deploy (they are idempotent, safe to re-run):

```bash
# Apply all Django migrations
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml exec backend python manage.py migrate

# Create the initial admin user from ADMIN_* env vars
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml exec backend python manage.py initadmin

# Collect Django static files into the shared volume
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml exec backend python manage.py collectstatic --noinput

# Set up Celery periodic tasks
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml exec backend python manage.py setup_tasks
```

---

## Step 7: Verify the Deployment

**Health check:**

```bash
curl -sf https://yourdomain.com/api/healthcheck/ && echo "OK"
```

**Login:** open `https://yourdomain.com` and sign in with the credentials from `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

**Admin panel:** `https://yourdomain.com/admin`

**Event ingestion (internal test):**

```bash
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml exec backend \
  curl -s http://event-ingestion:7998/healthz
```

---

## Updating to a New Version

### Recommended: pin to a release tag

```bash
# 1. Set the new tag
export LOTUS_IMAGE_TAG=v1.3.0
export LOTUS_IMAGE_PULL_POLICY=always

# 2. Pull the new images
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml pull backend frontend event-ingestion event-guidance

# 3. Recreate containers (zero-downtime order: db stays up)
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml up -d --no-deps backend celery celery-beat event-ingestion event-guidance frontend

# 4. Run any new migrations
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml exec backend python manage.py migrate
```

### Rolling back

Rollback is the same process — just set `LOTUS_IMAGE_TAG` back to the previous value. Migrations that were applied forward will remain, but Django migrations are designed to be non-destructive.

---

## Building from Source

If you need to customise the images or cannot use GHCR, build locally:

```bash
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml build backend frontend event-ingestion event-guidance
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml up -d
```

The build takes 10–15 minutes on first run. Subsequent builds use Docker layer cache and are much faster.

To push your own builds to a private registry:

```bash
export LOTUS_IMAGE_REGISTRY=registry.example.com/myorg/lotus
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml build
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml push backend frontend event-ingestion event-guidance
```

---

## Maintenance

### Database backups

```bash
#!/bin/bash
# save as scripts/backup.sh, schedule with cron: 0 2 * * *
DEST=/backups/lotus
mkdir -p "$DEST"
docker compose -f /path/to/lotus/docker-compose.prod.yaml exec -T db \
  pg_dump -U lotus lotus \
  | gzip > "$DEST/lotus_$(date +%Y%m%d_%H%M%S).sql.gz"
find "$DEST" -mtime +7 -delete
```

### Viewing logs

```bash
# All services, live
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml logs -f

# Single service
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml logs -f backend
```

### Stopping and removing

```bash
# Stop (keeps volumes)
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml down

# Stop and wipe all data (irreversible)
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml down -v
```

---

## Troubleshooting

### A service keeps restarting

```bash
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml logs <service-name> | tail -50
```

Common causes:
- `backend` / `celery`: database not yet ready (normal during first startup; waits up to ~2 min)
- Any service: wrong or missing value in `env/.env.prod`

### Database connection refused

```bash
# Is the DB container healthy?
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml ps db

# Can the backend reach it?
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml exec backend \
  python -c "import django; django.setup(); from django.db import connection; connection.ensure_connection(); print('OK')"
```

### Frontend loads but API calls fail (404 / CORS)

Verify `VITE_API_URL` ends with a `/` and matches your public domain exactly. This value is baked into the frontend image at build time — if you change it, you need a new image build.

### Cannot pull images (permission denied)

GHCR packages on a private repo require authentication:

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

Make the packages public in your GitHub repo settings under **Packages** if you want unauthenticated pulls.

### Events not appearing after ingestion

```bash
# Check event-ingestion received them
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml logs event-ingestion | grep -i error

# Check Redpanda consumer lag
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml exec redpanda \
  rpk group describe lotus-consumer-group

# Check Celery is consuming
docker compose --env-file env/.env.prod -f docker-compose.prod.yaml logs celery | tail -20
```
