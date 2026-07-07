# Backend Migration Story: Django → Node/TypeScript

**Status:** Proposal / not started
**Scope:** This document is about *rewriting* the backend runtime (Django → Node+TS), via the strangler-fig pattern — incrementally replacing slices of `backend/` with a Node service while Django keeps running.

This is a different effort from [`MIGRATION_ANALYSIS.md`](./MIGRATION_ANALYSIS.md), which covers upgrading the *existing* Python/Node/Go stack in place to current dependency versions. That upgrade should happen **first and independently** — see Phase 0 below — regardless of whether the Node rewrite proceeds.

---

## Why strangler-fig, not a rewrite

A big-bang rewrite of a billing system is high risk: `models.py` (~157KB) and `views.py` (~104KB) encode years of edge-case handling for invoicing, proration, and usage aggregation that isn't documented anywhere except the code itself. A full rewrite means re-deriving all of that correctness from scratch, with no way to validate parity until the very end.

Strangler-fig instead migrates one narrow slice of functionality at a time, with Django and Node running side by side against the same database, so:
- The system is always fully functional — never "half-rewritten and broken."
- Each slice can be validated against the old implementation before cutover.
- The riskiest code (invoicing, aggregation) is migrated last, once the pattern is proven on lower-risk slices.
- The effort can be paused or abandoned after any slice without leaving the system in a broken state.

---

## Phase 0 — Stabilize before splitting (do this regardless of the Node decision)

Don't strangler-fig a system that's simultaneously rotting. Per `MIGRATION_ANALYSIS.md`, Python 3.9 is EOL and Django 4.0 is two majors behind. Do the in-place upgrade to Python 3.11+/Django 5.x LTS first. This also gives you a cleaner Django codebase to read while porting logic to Node.

---

## Phase 1 — Build the routing seam

Introduce a routing layer in front of Django so individual paths can be redirected to a new Node service without the frontend knowing:
- Simplest option: path-based routing in the existing reverse proxy (`proxy/` — check what's already there, likely Caddy per `docker-compose.prod.yaml`).
- Decide DB ownership model up front: **Django remains the schema/migration owner** for the entire migration. Node reads/writes the same Postgres instance via introspected models (Prisma `db pull` or Drizzle introspection), but never runs its own migrations until a table's ownership is fully cut over. This avoids dual-migration-authority bugs.
- Keep the OpenAPI contract as the source of truth for request/response shapes on migrated endpoints, so the frontend's generated types (`frontend/src/gen-types.ts`) don't need to change when an endpoint moves runtime.

---

## Phase 2 — First slices: low write-coupling, no money math

Ranked from `backend/api/views.py`, roughly safest to riskiest:

| Order | Endpoint / ViewSet | Why it's safe first |
|---|---|---|
| 1 | `Ping`, `Healthcheck` (`views.py:2142, 2177`) | Zero business logic — good smoke test for the seam itself |
| 2 | `PlanViewSet` (`views.py:508`) | Reference data, no invoice/proration math (recently touched: `484a0e51`, `6fec38fd`) |
| 3 | Feature list/create (`ebcafd59`) | Standalone, recently added, low write coupling |
| 4 | `MetricAccessView`, `FeatureAccessView` (`views.py:1976, 2076`) | Read-heavy access checks |
| 5 | `CustomerViewSet` (`views.py:187`) reads (GET only) | CRUD but no billing computation on read paths |

**Do not migrate yet:** `SubscriptionViewSet` (`766`), `InvoiceViewSet` (`1590`), `CustomerBalanceAdjustmentViewSet` (`1757`), anything under `metering_billing/aggregation/` (`billable_metrics.py`, `*_query_templates.py`), or `metering_billing/invoice.py`. These carry the proration/aggregation logic with the highest cost-of-being-subtly-wrong.

---

## Phase 3 — Stand up the Node service

- Framework: NestJS (closer structurally to Django's app/serializer/view separation) or Fastify (leaner, if you want less ceremony).
- DB access: introspect the existing Postgres schema rather than hand-writing models, so Node's models can't silently drift from what Django's migrations produce. Re-generate after every Django migration touching a shared table.
- Auth: replicate Django's session/API-key auth (`djangorestframework-api-key`, `django-rest-knox`) at the Node layer before moving any authenticated endpoint — this is infrastructure every slice depends on, so get it right once.
- Reuse the existing `docs/openapi_private.yaml` contract for migrated endpoints; regenerate it from Node's route definitions once a slice is fully cut over, same as today's `generate_schema` step.

---

## Phase 4 — Migrate in increasing order of risk

1. Reference data (Plans, Features, Ping/Healthcheck)
2. Read-only reporting (customer invoice breakdown table, `c378154e`)
3. Simple CRUD (Customer, AddOn)
4. Customer balance adjustments
5. Subscription lifecycle (`SubscriptionViewSet`) — has real proration logic, treat as its own multi-step slice
6. Event access / usage views (`GetCustomerFeatureAccessView`, `GetCustomerEventAccessView`)
7. Webhook/event consumption paths (coordinate with the existing Go `event-ingestion`/`event-guidance` services — these already own high-throughput event handling; decide whether Node absorbs any of this or leaves it alone)
8. **Last:** `metering_billing/aggregation/` and `metering_billing/invoice.py` — only once the pattern is proven and you have parity tooling (below) trusted on lower-risk slices

Celery tasks (`metering_billing/tasks.py`) migrate alongside their corresponding endpoints, not as a separate blanket effort — don't try to share a task queue between Celery and a Node equivalent (BullMQ/Agenda); each slice owns its own async jobs once cut over.

---

## Phase 5 — Parity validation per slice, before cutover

For each slice, before flipping the router:
- Shadow traffic or a diffing script: send the same request to both Django and Node, compare responses byte-for-byte (or with tolerance for decimal/rounding differences in money fields).
- Specifically watch for Django ORM semantics that don't have obvious Node equivalents: implicit `NULL` handling, `Decimal` precision in money fields, timezone-aware datetime serialization (relevant given the recent timezone bug fix in `b7d57f22`).
- Only cut traffic over once parity holds for a full billing cycle where practical (subscriptions/invoices in particular).

---

## What NOT to do

- Don't attempt a shared-ORM tool (e.g., Prisma + `prisma-client-py`) to keep one model definition across both languages — it couples the two stacks together, which defeats the point of an incremental strangler-fig migration and forces Python code onto Prisma's semantics for logic you're trying to move away from anyway.
- Don't let Node take ownership of schema migrations while Django still owns any part of the schema — pick one migration authority for the whole effort until full cutover.
- Don't start with `aggregation/` or `invoice.py` to "get the hard part out of the way" — validate the pattern on boring endpoints first.
- Don't run this in parallel with the Phase 0 in-place upgrade — do Phase 0 first, then start stranglering the now-current Django codebase.

---

## Open questions to resolve before starting

- Does Node absorb any responsibility from the existing Go `event-ingestion`/`event-guidance` services, or do those stay untouched? (Leaning: untouched — they're not Django, and there's no forcing reason for three runtimes to become two.)
- What's the actual database-access library for Node — Prisma, Drizzle, or raw `pg` with generated types? Affects how introspection/parity works in Phase 3.
- Who owns `django-simple-history` audit-trail equivalence once a model moves to Node? No 1:1 replacement exists; needs a decision per migrated model.
