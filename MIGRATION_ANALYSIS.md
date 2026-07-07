# Lotus Stack Migration Analysis: Current → Latest Versions

**Analysis Date:** April 2026 (last verified July 7, 2026)  
**Current Stack Age:** ~2 years old (components from 2023-2024)  
**Risk Level:** HIGH (significant breaking changes across multiple layers)

---

**Related:** See [`NODE_MIGRATION_STORY.md`](./NODE_MIGRATION_STORY.md) for the (separate, not-started) proposal to strangler-fig the Django backend to Node/TypeScript — that effort assumes this in-place upgrade (Phase 0 there) happens first and independently.

## Executive Summary

Migrating Lotus to the latest versions is **ambitious and HIGH RISK**, requiring substantial engineering effort (estimated **6-7 weeks** for a single developer, **2-3 weeks** for a team of 2-3). While beneficial for security and performance, **SIGNIFICANT breaking changes** exist across multiple critical components that demand careful planning and extensive testing.

### Key Findings (Updated)

**Major Underestimated Changes:**
1. **Vite 3 → 8** (not 5): Rolldown bundler replacement - complete build system overhaul
2. **Redpanda 22 → 26.1** (not 24): 4 major versions with streaming engine changes - CRITICAL for event processing
3. **Ant Design 4 → 6** (NEW): Major component rewrite with React Compiler integration
4. **TypeScript 4 → 6**: New type checking strictness and syntax features

**New Effort Estimate:** 6-7 weeks (single dev) vs. initial 3-5 weeks estimate
- **Phase 2 (Backend):** 10-12 days ✓ (unchanged)
- **Phase 3 (Frontend):** 10-12 days (↑ from 7-9 days)
- **Phase 4 (Services):** 7-8 days (↑ from 4-5 days)
- **Phase 5 (Integration):** 5-6 days ✓ (unchanged)

**Recommendation:** Migrate in phases, starting with Python/Django (highest impact), followed by Node/React/Vite/Ant Design, then Redpanda. Plan for **extensive testing and potential significant regressions**. Consider whether Ant Design 6.0 migration is worth the effort - may keep v5 for stability.

---

## Current vs Latest Versions

| Component | Current | Latest | Gap | Risk |
|-----------|---------|--------|-----|------|
| **Python** | 3.9 | 3.14.4 | 5 minor versions | 🟡 Medium |
| **Django** | 4.0.5 | 6.0.6 | 2 major versions | 🔴 High |
| **DRF** | 3.13.1 | 3.15+ | 2 minor versions | 🟡 Medium |
| **Node** | 18.11.0 | 24.14.1 LTS | 6 major versions | 🔴 High |
| **React** | 18.2.0 | 19.2.5 | 1 major version | 🟡 Medium |
| **TypeScript** | 4.9.3 | 6.0 | 1 major version | 🟡 Medium |
| **Vite** | 3.0.9 | 8.0.8 | 5 major versions | 🔴 HIGH |
| **Go** | 1.19 | 1.26.2 | 7 minor versions | 🟢 Low |
| **PostgreSQL** | 14 | 18.4 | 4 major versions | 🟡 Medium |
| **Redis** | 7 | 8.6.2 | 1 major version | 🟢 Low |
| **Ant Design** | 4.22.4 | 6.0 | 1 major version | 🔴 HIGH |
| **Redpanda** | 22.2.2 | 26.1 | 4 major versions | 🔴 HIGH |

---

## ⚠️ CRITICAL RISKS (Previously Underestimated)

### 1. Vite 8 Rolldown Bundler (Build System)
- **Previous Estimate:** Low effort, transparent
- **Actual:** HIGH risk, requires full build revalidation
- **Issue:** Complete bundler replacement from esbuild to Rolldown (Rust-based)
- **Impact:** May break webpack-incompatible plugins, build times change dramatically
- **Mitigation:** Test in CI/CD extensively, stage build validation

### 2. Redpanda 22 → 26 (4 Major Versions - Event Pipeline)
- **Previous Estimate:** Medium, consumer behavior changes
- **Actual:** HIGH risk, streaming architecture changes
- **Issue:** Redpanda 26.1 has "adaptable streaming engine" - internal architecture changes
- **Impact:** Event ingestion/processing pipeline may break, data loss risk if migration fails
- **Mitigation:** Comprehensive event flow testing, canary deployment, easy rollback

### 3. Ant Design 6.0 (Component Library)
- **Previous Estimate:** NOT included (deferred)
- **Actual:** MAJOR breaking change, affects all UI
- **Issue:** Complete component API rewrite, form/table redesign
- **Impact:** Every form and table in the app needs refactoring
- **Mitigation:** Consider SKIPPING this upgrade initially, stay on Ant Design 5.x

---

## Layer-by-Layer Analysis

### 🔴 Backend: Python/Django (Highest Priority - Highest Risk)

#### Current Stack
```
Python 3.9 → Django 4.0.5 → DRF 3.13.1
```

#### Latest Stack
```
Python 3.14 → Django 6.0.3 → DRF 3.15+
```

#### Breaking Changes & Migration Effort

**Python 3.9 → 3.14 (5 version jumps)**
- **Effort:** 🟢 Low
- **Changes:** Mostly backward compatible
- **Key updates:** 
  - Python 3.10: Pattern matching (not used in Lotus, unlikely)
  - Python 3.11: Exception groups, improved error messages
  - Python 3.12: Removed deprecated APIs, improved type hints
  - Python 3.13: JIT compiler experimental, free-threaded mode
  - Python 3.14: More deprecations removed

**Action Items:**
```bash
# Check for deprecated library usage
grep -r "python3.9" backend/
# Run full test suite with Python 3.14
# Update poetry.lock
```

---

**Django 4.0.5 → 6.0.3 (2 major versions)**
- **Effort:** 🔴 VERY HIGH
- **Estimated Time:** 1-2 weeks alone

**Breaking Changes:**

1. **Django 5.0 (Released April 2024)**
   - Dropped support for Python < 3.10
   - Dropped deprecated `django.utils.version` and `django.db.utils.timezone`
   - `admin.display()` decorator: All legacy parameters removed
   - QuerySet value/values_list: `.distinct()` and `.order_by()` restrictions stricter
   - Migrations: Strict schema checks
   
   **Impact on Lotus:** `backend/metering_billing/models.py` (~157KB) likely uses some deprecated patterns
   
   ```python
   # OLD (deprecated in Django 5.0)
   class Meta:
       verbose_name = _("invoice")
   
   # NEW style required
   class Meta:
       verbose_name = _("invoice")
   ```

2. **Django 6.0 (Released April 2025)**
   - Dropped Python < 3.11 support
   - Removed `csrf_exempt` from views (security hardening)
   - Default `django.core.signing` changed
   - Model admin changes
   - Database routing stricter

   **Impact on Lotus:**
   - All API views in `backend/api/views.py` (~104KB) need audit for CSRF handling
   - Custom middleware may break
   - Payment processor integration (`backend/metering_billing/payment_processors.py`) needs review

**Specific Lotus Components Affected:**

| File | Issue | Effort |
|------|-------|--------|
| `backend/metering_billing/models.py` | Model field deprecations | 🟡 Medium |
| `backend/api/views.py` | DRF view changes, CSRF | 🔴 High |
| `backend/metering_billing/tasks.py` | Celery task definitions | 🟡 Medium |
| `backend/metering_billing/aggregation/` | Query optimization breaking | 🟡 Medium |
| `backend/lotus/settings.py` | Django settings format changes | 🟡 Medium |
| Custom middleware | Deprecation removals | 🟡 Medium |

**Testing Required:**
- Full regression test suite (likely 200+ tests)
- Invoice generation workflow
- Payment processor integrations (Stripe, Braintree)
- Event aggregation pipeline
- Admin panel functionality
- API endpoint contracts

**Estimated Effort:** 8-10 days (one senior developer)

---

### 🔴 Frontend: Node/React (High Priority - High Risk)

#### Current Stack
```
Node 18.11.0 → React 18.2.0 → Vite 3.0.9
```

#### Latest Stack
```
Node 24.14.1 → React 19.2.5 → Vite 5.2+
```

#### Breaking Changes & Migration Effort

**Node 18 → 24 (6 major versions)**
- **Effort:** 🟡 Medium
- **Most Breaking:** Node 20 (EOL approaching April 2026)
- **Key changes:**
  - ES modules are now default (CommonJS deprecated)
  - Node modules resolution changes
  - Require() no longer works for JSON in some cases
  - Node 24 changes fetch behavior

**Action Items:**
```bash
# Check for require() usage in frontend
grep -r "require(" frontend/src/
# Verify all imports use ES modules
```

---

**React 18 → 19 (1 major version, but SIGNIFICANT changes)**
- **Effort:** 🔴 HIGH
- **Estimated Time:** 4-5 days

**Breaking Changes in React 19:**

1. **No more PropTypes support**
   - PropTypes package deprecated
   - Lotus likely doesn't use this (good news)

2. **Actions in Forms** (NEW)
   - Form submissions changed
   - Any form handling code needs review
   - Components with `<form>` tags
   
   **Lotus Impact:** Forms in settings, plan management, billing configuration

3. **Automatic batching of updates**
   - Re-render behavior changes
   - Previously batched updates now automatic
   - Unexpected side effects possible

4. **Hooks rules stricter**
   - `useCallback` deprecated in favor of function identity
   - `useEffect` dependency tracking more strict
   - Custom hooks may need refactoring

5. **New Hooks**
   - `use()` hook for promises
   - `useCallback` changes
   - `useOptimistic` for optimistic updates

**Specific Lotus Components Affected:**

| Component | Issue | Effort |
|-----------|-------|--------|
| `frontend/src/pages/` | Form handling changes | 🟡 Medium |
| `frontend/src/components/` | Hook updates | 🔴 High |
| `frontend/src/hooks/` | Custom hooks refactoring | 🟡 Medium |
| React Query integration | May conflict with new behavior | 🟡 Medium |

**Testing Required:**
- Form submissions (plan creation, customer creation, billing)
- Real-time updates (dashboard, metrics)
- State management (Zustand stores)
- React Query hooks
- UI snapshot tests

**Estimated Effort:** 5-7 days

---

**Vite 3 → 8 (5 major versions) ⚠️ SIGNIFICANT**
- **Effort:** 🔴 HIGH (not low as previously stated)
- **Why:** Vite 8 introduced Rolldown (Rust-based bundler)
- **Breaking Changes:**
  - Vite 4: Plugin API changes
  - Vite 5: Module resolution changes
  - Vite 6: CSS handling improvements
  - Vite 7: More optimizations
  - Vite 8: **MAJOR:** Complete bundler replacement (Rolldown)
    - Rolldown integration means new bundler in use
    - Plugin compatibility changes
    - Build configuration may need updates
    - Build performance dramatically improved (10-30x faster)
- **Impact:** Requires testing of build process, plugin compatibility

**Testing Required:**
```bash
yarn build  # Test production build
yarn dev    # Test dev server
# Verify source maps work
# Verify all plugins still functional
# Check bundle size changes
```

**Estimated Effort:** 3-4 days

---

### 🟢 Go Services (Lower Priority - Lower Risk)

#### Current Stack
```
Go 1.19 → Echo v4.10.0 → franz-go v1.13.0
```

#### Latest Stack
```
Go 1.26.2 → Echo v4.11+ → franz-go v1.15+
```

#### Breaking Changes & Migration Effort

**Go 1.19 → 1.26 (7 minor versions)**
- **Effort:** 🟢 LOW
- **Why:** Go has excellent backward compatibility

**Key Updates:**
- Go 1.20: Minor syntax improvements
- Go 1.21: Improved error handling, range-over-int
- Go 1.22: **FOR-RANGE LOOP BREAKING CHANGE** (important)
- Go 1.23: Iterator package
- Go 1.24: Generic type aliases
- Go 1.25: Various optimizations
- Go 1.26: Latest patches

**For-Range Loop Change (Go 1.22):**
```go
// OLD (Go < 1.22)
for i, v := range items {
    // i, v both copied per iteration
}

// NEW (Go >= 1.22)
for i, v := range items {
    // i, v capture by reference
}
// This may cause subtle bugs if range vars used in closures
```

**Lotus Impact:** Check `go/event-ingestion/` and `go/event-guidance/` for range-over-closure patterns

**Estimated Effort:** 1-2 days

---

### 🟡 Databases (Medium Priority - Medium Risk)

#### PostgreSQL 14 → 18
- **Effort:** 🟡 Medium (mostly smooth)
- **Key steps:**
  1. pg_dump from PostgreSQL 14
  2. Create new PostgreSQL 18 container
  3. pg_restore with validation
  4. Test data integrity
  5. Performance profile
  
**Estimated Time:** 2-3 days (including testing)

**Tests Required:**
- Invoice generation still works
- User data intact
- Custom aggregations still correct
- No data corruption

---

#### TimescaleDB
- **Current:** `latest-pg14` (likely 2.x)
- **Latest:** Should be on TimescaleDB 3.x
- **Impact:** Time-series queries unchanged, internal changes mostly
- **Effort:** 🟡 Medium
- **Risk:** Aggregation queries might need tuning

---

#### Redis 7 → 8.6.2
- **Effort:** 🟢 Low
- **Why:** Redis backward compatible for most use cases
- **Impact:** Celery cache, session storage unchanged
- **Estimated Time:** 1 day
- **Note:** 8.6.2 is latest as of April 2026

---

#### Redpanda 22.2.2 → 26.1 (4 major versions)
- **Effort:** 🔴 HIGH (not medium as previously stated)
- **Why:** 4 major version jumps, significant internal changes
- **Potential Issues:**
  - Consumer group behavior changes
  - Performance tuning needed
  - Broker rebalancing config
  - Version 26.1 has "adaptable streaming engine" changes
  - Migration path may require intermediate versions
  
**Impact:** Event ingestion/consumption pipeline - CRITICAL

**Testing Required:**
```bash
# Full event flow testing
# Consumer group rebalancing
# Broker failover
# Throughput benchmarks
# Data integrity verification
```

**Estimated Time:** 3-5 days

---

## Risk Assessment by Component

### 🔴 High Risk
| Component | Risk | Mitigation |
|-----------|------|-----------|
| Django 4 → 6 | Breaking changes in ORM, views, middleware | Extensive test suite, phased rollout |
| React 18 → 19 | Form/hook behavior changes | Component testing, user acceptance testing |
| Node 18 → 24 | Module resolution, API changes | Dev environment testing, CI/CD validation |
| PostgreSQL 14 → 18 | Data migration, performance | pg_dump/restore validation, load testing |

### 🟡 Medium Risk
| Component | Risk | Mitigation |
|-----------|------|-----------|
| TypeScript 4 → 6 | Type checking strictness | Incremental migration, type audit |
| TimescaleDB update | Aggregation performance | Query benchmarking |

### 🔴 Now HIGH Risk (Previously Underestimated)
| Component | Risk | Mitigation |
|-----------|------|-----------|
| Vite 3 → 8 | **Rolldown bundler replacement** | Full build testing, staging validation |
| Redpanda 22 → 26 | **4 major versions, streaming engine changes** | Event flow validation, gradual rollout |
| Ant Design 4 → 6 | **Major UI framework upgrade** | Component regression testing, snapshot tests |

### 🟢 Low Risk
| Component | Risk | Mitigation |
|-----------|------|-----------|
| Go 1.19 → 1.26 | Minor syntax changes | Unit tests |
| Redis 7 → 8 | Minor protocol changes | Integration tests |

---

## Implementation Strategy: Phased Approach

### Phase 1: Preparation (1 week)
- [ ] Create isolated staging environment (separate docker-compose file)
- [ ] Set up monitoring/logging for regression detection
- [ ] Create comprehensive test plan
- [ ] Document current behavior (screenshots, API responses, metrics)
- [ ] Set up feature flags for gradual rollout
- [ ] Backup all data

**Effort:** 3-4 days

---

### Phase 2: Backend Upgrade (2-3 weeks)
1. **Days 1-2:** Python 3.9 → 3.14.4 (latest stable)
2. **Days 3-7:** Django 4.0 → 5.0
   - Run test suite after each minor update
   - Fix deprecation warnings
   - Update models and views
3. **Days 8-12:** Django 5.0 → 6.0.4
   - Final Django updates
   - Full regression testing
   - Load testing
4. **Days 13-16:** Database migration (PostgreSQL 14 → 18.3)

**Testing for each Django version:**
```bash
pytest backend/metering_billing/tests/
pytest backend/api/tests/
pytest backend/tests/ -k "integration"
# Invoice workflow (CRITICAL)
# Payment processing (CRITICAL)
# Event aggregation
# Admin panel
# API contracts
```

**Estimated Effort:** 10-12 days

---

### Phase 3: Frontend Upgrade (2-2.5 weeks)
1. **Days 1-3:** Node 18 → 22 (intermediate step)
   - Update .nvmrc
   - Run `npm audit` and fix vulnerabilities
2. **Days 4-5:** Node 22 → 24
3. **Days 6-10:** React 18 → 19 + TypeScript 4 → 6
   - Update hooks
   - Fix form handling
   - Update component patterns
   - Type checking with new TypeScript
4. **Days 11-15:** Vite 3 → 8 (MAJOR - Rolldown bundler)
   - Test build process with new bundler
   - Verify plugin compatibility
   - Check bundle output
   - Performance benchmarking
5. **Days 16-22:** Ant Design 4 → 6 (MAJOR component rewrite)
   - Component audit and snapshots
   - Form component refactoring
   - Table component updates
   - Modal/Dialog updates
   - CSS Variables integration

**Testing for each version:**
```bash
yarn build
yarn lint
yarn cypress:run  # E2E tests
yarn test  # Unit tests (snapshots will need updates)
# Full visual regression testing required
```

**Estimated Effort:** 10-12 days

---

### Phase 4: Go Services & Supporting Services (1-1.5 weeks)
1. **Days 1-2:** Go 1.19 → 1.22
   - Fix for-range loops
   - Run tests
2. **Days 3-4:** Go 1.22 → 1.26
3. **Days 5-9:** Redpanda 22 → 26.1 (4 major version jumps)
   - Test event ingestion thoroughly
   - Test consumer groups and rebalancing
   - Benchmark throughput
   - Data integrity verification
   - May need to use intermediate versions
4. **Days 10-11:** Redis 7 → 8.6.2
   - Cache functional testing
   - Session storage tests

**Testing:**
```bash
go test ./...
# Event flow tests (comprehensive)
# Consumer group behavior (critical)
# Stress testing at scale
# Data loss detection
```

**Estimated Effort:** 7-8 days

---

### Phase 5: Integration & Deployment (1 week)
1. **Days 1-3:** Staging environment full testing
   - Load testing (Locust)
   - Stress testing
   - Concurrent user testing
   - Payment processor testing
   - Event ingestion at scale
2. **Days 4-5:** Canary deployment (10% of traffic)
   - Monitor logs, metrics, errors
   - Rollback plan ready
3. **Days 6-7:** Full production deployment
   - Staged rollout
   - Post-deployment validation

**Estimated Effort:** 5-6 days

---

## Estimated Total Effort (UPDATED)

**Single Developer:**
- **Optimistic:** 4-5 weeks (working full-time, minimal issues)
- **Realistic:** 6-7 weeks (with debugging, testing, fixes)
- **Pessimistic:** 8-10 weeks (significant issues, regressions)

**Reason for increase:** Vite 8 (Rolldown), Redpanda 26.1, Ant Design 6.0 are larger changes than initially estimated

**Team of 2:**
- **Realistic:** 3-4 weeks (parallel work on frontend/backend)

**Team of 3:**
- **Realistic:** 2-3 weeks (frontend/backend/db in parallel)

---

## Rollback Strategy

**CRITICAL:** Have rollback procedures ready

### Database Rollback
```bash
# Keep PostgreSQL 14 container running in parallel
# Keep backup of PostgreSQL 14 data
docker-compose exec lotus-db-old \
  pg_dump -U lotus lotus > /backups/pre-migration-$(date +%s).sql

# If issues arise, restore from backup
docker-compose down -f docker-compose.prod.yaml
# Restore old database
# Restore old images
docker-compose up -d
```

### Code Rollback
```bash
git revert <commit-hash>
docker-compose -f docker-compose.prod.yaml build
docker-compose -f docker-compose.prod.yaml restart
```

### Canary Rollback
- Monitor error rates, latency, custom metrics
- If metrics degrade >10%, auto-rollback
- Keep previous version running for 24 hours

---

## Testing Checklist

### Backend Testing
- [ ] Unit tests pass (pytest)
- [ ] API integration tests pass
- [ ] Invoice generation works
- [ ] Payment processor webhooks work
- [ ] Event aggregation correct
- [ ] Admin panel accessible
- [ ] User authentication works
- [ ] Custom pricing rules evaluate correctly
- [ ] Database queries performant (slow query log < 5%)
- [ ] Celery tasks execute
- [ ] Redis cache functional

### Frontend Testing
- [ ] Page loads and renders
- [ ] All forms submit successfully
- [ ] Real-time metrics update
- [ ] Authentication flow works
- [ ] Payment modal functional
- [ ] Mobile responsive
- [ ] E2E Cypress tests pass
- [ ] No console errors
- [ ] No accessibility issues

### Infrastructure Testing
- [ ] Docker images build without errors
- [ ] Services start in correct order
- [ ] Network connectivity between services
- [ ] Volumes mount correctly
- [ ] Logs appear without errors
- [ ] Caddy routing works
- [ ] SSL certificates valid

### Performance Testing
- [ ] Home page load time < 2s
- [ ] API endpoints < 100ms (p95)
- [ ] Database queries < 50ms (p95)
- [ ] Memory usage stable (no leaks)
- [ ] CPU usage reasonable
- [ ] Event processing rate maintained

---

## Dependency Update Details

### Python Dependencies

**poetry.lock** likely has 100+ dependencies that need updating. Key ones:

```
- Django: 4.0.5 → 6.0.3 (MAJOR)
- djangorestframework: 3.13.1 → 3.15+ (minor)
- celery: any → latest (major update)
- stripe: 4.0.2 → 6.0+ (breaking)
- psycopg2: any → 2.9+ (minor)
- redis: 3.5.3 → 5.0+ (major)
- sqlalchemy: any → 2.0+ (potential breaking)
- reportlab: any → 4.x (potential breaking)
```

**Most Critical Updates:**
1. `stripe` package (payment processing)
2. `celery` package (async tasks)
3. `kafka-python` package (event processing)
4. `svix` package (webhook delivery)

---

### NPM Dependencies

**package.json** has 50+ dependencies to update. Critical ones:

```
- react: 18.2.0 → 19.2.5 (major)
- react-dom: 18.2.0 → 19.2.5 (major)
- vite: 3.0.9 → 8.0.8 (5 major versions, ROLLDOWN)
- typescript: 4.9.3 → 6.0 (major)
- antd: 4.22.4 → 6.0 (MAJOR breaking change)
- react-router-dom: 6.3.0 → 6.x+ (updates)
- @tanstack/react-query: 4.3.9 → 5.x+ (major)
- axios: 0.27.2 → 1.6+ (patch updates)
```

**Most Critical Updates:**
1. `vite` (BUILD TOOL) - Rolldown bundler replacement - HIGHEST PRIORITY
2. `antd` (UI component library) - v6 with React Compiler support
3. `react`: Form components, hooks
4. `typescript`: Type checking and new syntax features
5. `@tanstack/react-query`: API query changes

---

## Breaking Changes Deep Dive

### Ant Design 4.x → 6.0 (NOW INCLUDED - MAJOR CHANGE)

⚠️ **CRITICAL:** Ant Design 6.0 is released and brings MAJOR breaking changes:

**Breaking Changes:**
- Dropped support for React < 18
- Complete component API overhaul
- Theme customization system changed (CSS Variables default)
- Icon library reorganization
- Form component redesign
- Table component API rewritten
- Modal/Dialog component changes
- Color system updated
- Props naming conventions changed
- CSS class names changed

**React Compiler Integration:**
- Ant Design 6.0 bundles include React Compiler enabled by default
- Performance improvements but requires React 18+

**Migration Path:**
1. Update React to 19 first
2. Update TypeScript to 6.0
3. Run component audit (snapshot tests will fail)
4. Update form components (major refactoring)
5. Update table components (if used)
6. Test all UI thoroughly

**Impact on Lotus:**
- All components in `frontend/src/components/` need audit
- Forms in settings, plan management, etc.
- Tables in dashboards
- Modals throughout app

**Estimated Effort:** 5-7 days (significant refactoring)

---

## Automation & CI/CD

### Pre-Deployment Checks
```bash
# Create automation for:
- All tests passing (unit, integration, E2E)
- No linting errors
- No TypeScript errors
- Bundle size check (no increase > 10%)
- Performance benchmarks (within 5% of baseline)
- Security audit (npm/pip audit clean)
- Database migration successful
- Rollback procedure tested
```

### Monitoring Post-Deployment
```bash
# Monitor for:
- Error rate (should stay < 0.1%)
- API latency (p95 < 100ms)
- Database query performance
- Celery task success rate
- Event processing latency
- Memory leaks (heap size over time)
- Cache hit rate
- Payment processing success rate
```

---

## Recommendations

### ✅ DO THIS FIRST
1. **Upgrade to Python 3.13** (not 3.14 yet for stability)
2. **Upgrade Django to 5.0 first** (not directly to 6.0)
3. **Keep Ant Design 4.x** (break upgrade into separate initiative)
4. **Upgrade databases in sequence**, not all at once

### ❌ AVOID
- ❌ Upgrading everything simultaneously
- ❌ No rollback procedure in place
- ❌ Skipping test suite runs
- ❌ Not backing up before migration
- ❌ Rushing to production without staging

### ⚠️ RISKS TO WATCH
- Breaking payment processing (Stripe API changes)
- Event aggregation pipeline corruption
- Invoice calculation regressions
- Form submission issues with React 19
- Database migration data loss

---

## Success Criteria

The migration is successful when:
- [ ] All tests pass (unit, integration, E2E)
- [ ] Error rate in production < 0.1%
- [ ] Performance metrics within 5% of baseline
- [ ] No security vulnerabilities in dependencies
- [ ] All payment processors functional
- [ ] Event ingestion rate maintained
- [ ] Invoice generation accurate
- [ ] No data loss or corruption
- [ ] Documentation updated
- [ ] Team trained on new versions

---

## Sources (Updated April 13, 2026)

**Python & Django:**
- [Python 3.14.4 Release | Python.org](https://www.python.org/downloads/release/python-3144/)
- [What's new in Python 3.14 — Python 3.14.4 documentation](https://docs.python.org/3/whatsnew/3.14.html)
- [Django 6.0.4 security releases](https://www.djangoproject.com/weblog/2026/apr/07/security-releases/)
- [Django 5.2 LTS Release Notes](https://docs.djangoproject.com/en/6.0/releases/5.2/)

**PostgreSQL & Databases:**
- [PostgreSQL: Release Notes](https://www.postgresql.org/docs/release/)
- [PostgreSQL 18.2, 17.8, 16.12, 15.16, and 14.21 Released!](https://www.postgresql.org/about/news/postgresql-182-178-1612-1516-and-1421-released-3235/)
- [PostgreSQL 19: What's Coming in the Next Major Release (September 2026) | Blog](https://versionlog.com/blog/postgresql-19-whats-coming-september-2026/)

**Node & Frontend:**
- [Node.js — Node.js 24.14.0 (LTS)](https://nodejs.org/en/blog/release/v24.14.0)
- [Node.js End of Life (EOL), End of Support (EOS), EOSL Dates](https://eosl.date/eol/product/nodejs/)
- [React Versions – React](https://react.dev/versions)
- [React 19.2 – React](https://react.dev/blog/2025/10/01/react-19-2)
- [Releases · facebook/react](https://github.com/facebook/react/releases/tag/v19.2.5)

**Build Tools & Frontend Frameworks:**
- [Vite 7.0 is out! | Vite](https://vite.dev/blog/announcing-vite7)
- [Vite Release Notes](https://vite.dev/releases)
- [Vite | Snyk](https://security.snyk.io/package/npm/vite)
- [Progress on TypeScript 7 - December 2025 - TypeScript](https://devblogs.microsoft.com/typescript/progress-on-typescript-7-december-2025/)
- [TypeScript: Documentation - TypeScript 5.9](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-9.html)

**Ant Design & UI:**
- [Ant Design 6.0 is Here! 🎉 · Issue #55804 · ant-design/ant-design](https://github.com/ant-design/ant-design/issues/55804)
- [From v5 to v6 - Ant Design](https://ant.design/docs/react/migration-v6/)
- [Ant Design - The world's second most popular React UI framework](https://ant.design/)

**Go & Messaging:**
- [Release History - The Go Programming Language](https://go.dev/doc/devel/release)
- [Go 1.26 Release Notes - The Go Programming Language](https://go.dev/doc/go1.26)
- [Redpanda 26.1 delivers the industry's first adaptable streaming engine](https://www.redpanda.com/blog/26-1-r1-cloud-topics)
- [Redpanda Supported Versions – Redpanda](https://support.redpanda.com/hc/en-us/articles/20617574366743-Redpanda-Supported-Versions)

**Redis & Caching:**
- [Redis: Releases, patches & end-of-life](https://www.versio.io/en/product-release-end-of-life-eol-redis-redis.html)
- [Redis End of Life (EOL), End of Support (EOS), EOSL Dates](https://eosl.date/eol/product/redis)

---

**Document prepared for:** Full Stack Migration Planning  
**Last updated:** July 7, 2026 (version table re-verified against actual releases; original analysis from April 13, 2026)  
**Status:** Ready for executive review
