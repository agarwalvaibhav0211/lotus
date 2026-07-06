# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Lotus

Lotus is an open-source pricing and billing infrastructure platform for SaaS companies. It supports usage-based pricing, subscriptions, invoicing, and payment processor integrations (Stripe, Braintree).

## Development Setup

Copy the env template and start all services:
```bash
cp env/.env.dev.example env/.env.dev
./scripts/dev.sh
```

Optional flags for `dev.sh`:
- `--no-events` — skip Redpanda and Go event services
- `--no-beat` — skip Celery Beat scheduler
- `--no-webhooks` — skip Svix server
- `--force-recreate` — recreate containers
- `--no-build` — skip image builds

Services run at: backend `localhost:8000`, frontend `localhost:3000`, event-ingestion `localhost:7998`, event-guidance `localhost:7999`.

## Common Commands

### Backend (Django/Python)
```bash
cd backend
pytest                          # run all tests
pytest metering_billing/tests/  # run specific test directory
pytest -k "test_name"           # run single test
black .                         # format code
ruff check .                    # lint
python manage.py migrate        # apply migrations
python manage.py shell          # Django shell
```

### Frontend (React/TypeScript)
```bash
cd frontend
yarn dev                        # start dev server
yarn build                      # production build
yarn lint                       # ESLint
yarn pretty                     # Prettier format
yarn cypress:run                # headless E2E tests
yarn cypress:open               # interactive E2E tests
```

### Go services
```bash
cd go
go test ./...                   # run all Go tests
go build ./event-ingestion/...  # build event-ingestion
go build ./event-guidance/...   # build event-guidance
```

## Generating OpenAPI Specs

Run this after any API change (new/modified endpoints, serializers, or views) to keep the schema and frontend types in sync.

```bash
# 1. Generate the OpenAPI schema from Django (backend)
cd backend
python manage.py generate_schema

# 2. Regenerate frontend TypeScript types from the schema
cd gen
yarn update-types
```

Step 1 (`backend/metering_billing/management/commands/generate_schema.py`) runs `drf_spectacular` and writes `docs/openapi_full.yaml`, then splits it by path prefix into `docs/openapi.yaml` (public) and `docs/openapi_private.yaml` (internal `/api/*`), plus JSON equivalents — all deterministically sorted. Uses hooks defined in `backend/metering_billing/openapi_hooks.py`.

Step 2 (`gen/bump.ts`) runs `openapi-typescript` against `docs/openapi_private.yaml` to produce `frontend/src/gen-types.ts`, then converts it to camelCase as `frontend/src/gen-types-camel.ts`.

## Architecture

### Service Map
```
Frontend (React/Vite)
    └─► Django REST API (backend/)
            ├─► PostgreSQL + TimescaleDB  (time-series event data)
            ├─► Redis                     (cache + Celery broker)
            ├─► Celery Workers            (background jobs)
            ├─► Celery Beat               (scheduled tasks)
            └─► Svix                      (webhook delivery)

External events ──► Go event-ingestion ──► Redpanda (Kafka) ──► Celery workers
```

### Key Backend Files
- `backend/metering_billing/models.py` — all ORM models (very large, ~157KB)
- `backend/api/views.py` — all REST API endpoints (~104KB)
- `backend/metering_billing/invoice.py` — invoice generation logic
- `backend/metering_billing/payment_processors.py` — Stripe/Braintree abstraction
- `backend/metering_billing/tasks.py` — Celery async/scheduled tasks
- `backend/metering_billing/aggregation/` — usage aggregation engine
- `backend/lotus/settings.py` — Django settings, feature flags, integration keys

### Frontend Structure
- `frontend/src/pages/` — route-level page components
- `frontend/src/components/` — shared UI components
- `frontend/src/api/` — API client (uses React Query)
- `frontend/src/gen-types.ts` — auto-generated TypeScript types from OpenAPI spec
- `frontend/src/hooks/` — custom React hooks

### Go Microservices
- `go/event-ingestion/` — receives usage events, forwards to Redpanda
- `go/event-guidance/` — validates and guides event structure
- `go/pkg/types/` — shared types across Go services
- `go/go.work` — Go workspace config linking both services

### Event Flow
1. Client sends usage events to the Go event-ingestion service (`:7998`)
2. Events are published to Redpanda (Kafka-compatible, `:9092`)
3. Celery workers consume from Redpanda and persist/aggregate in PostgreSQL (TimescaleDB)
4. Aggregated usage drives invoice calculation via `metering_billing/aggregation/`

### Multi-tenancy
All major models are scoped to an `Organization`. The `Customer` model represents end-customers of Lotus users. Plans and subscriptions link customers to pricing structures.

## Tech Stack
- **Backend**: Python 3.9, Django 4.0.5, DRF, Celery, Poetry
- **Frontend**: React 18, TypeScript, Vite, Ant Design, TailwindCSS, React Query
- **Go services**: Go 1.20, Echo (HTTP), franz-go (Kafka client)
- **Databases**: PostgreSQL 14 + TimescaleDB, Redis 7
- **Messaging**: Redpanda (Kafka-compatible)
- **Webhooks**: Svix v0.74
- **Payments**: Stripe, Braintree
