# OpsWeave Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current product shell with a bootable OpsWeave control-plane foundation containing administrator authentication, PostgreSQL and Redis health, a compact sticky status bar, and the approved Modern Bento dashboard.

**Architecture:** Keep FastAPI and React, replace the current product routes incrementally, and use PostgreSQL as durable state. Add Redis now as a health-checked dependency so the durable task plan can attach workers without changing the platform contract. Authentication uses an Argon2id password hash and an opaque server-side session stored in PostgreSQL and delivered through an HTTP-only cookie.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 + pgvector, Redis 7, argon2-cffi, React 18, TypeScript, Tailwind CSS, Vitest, pytest, Docker Compose.

---

## Locked File Structure

- `backend/app/core/config.py`: OpsWeave settings, database and Redis URLs, cookie policy.
- `backend/app/models/identity.py`: Administrator and AdminSession ORM models.
- `backend/app/schemas/auth.py`: Login and current-administrator contracts.
- `backend/app/services/auth_service.py`: Argon2 verification and opaque session lifecycle.
- `backend/app/services/health_service.py`: API, database, Redis, vector, and host pulse checks.
- `backend/app/api/auth.py`: bootstrap, login, logout, and current-session endpoints.
- `backend/app/api/health.py`: public liveness and authenticated operational summary.
- `backend/app/main.py`: middleware and router assembly.
- `backend/migrations/versions/0003_opsweave_foundation.py`: identity/session schema.
- `frontend/src/context/AuthContext.tsx`: session bootstrap and auth actions.
- `frontend/src/components/layout/StatusBar.tsx`: compact sticky health bar and detail popover.
- `frontend/src/components/layout/Sidebar.tsx`: grouped OpsWeave navigation.
- `frontend/src/components/layout/AppLayout.tsx`: responsive shell.
- `frontend/src/pages/LoginPage.tsx`: administrator login.
- `frontend/src/pages/DashboardPage.tsx`: four approved Bento sections.
- `frontend/src/services/api.ts`: credentialed auth and health clients.

### Task 1: Rename Runtime Configuration and Add Redis

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `backend/tests/test_health.py`

- [ ] **Step 1: Write a failing settings test**

Add to `backend/tests/test_health.py`:

```python
def test_opsweave_settings_expose_redis_and_secure_cookie_defaults():
    from app.core.config import Settings

    cfg = Settings(_env_file=None)
    assert cfg.app_name == "OpsWeave"
    assert cfg.redis_url == "redis://localhost:6379/0"
    assert cfg.session_cookie_name == "opsweave_session"
    assert cfg.session_cookie_samesite == "lax"
```

- [ ] **Step 2: Verify the test fails**

Run: `cd backend && PYTHONPATH=. pytest tests/test_health.py::test_opsweave_settings_expose_redis_and_secure_cookie_defaults -q`

Expected: FAIL because `redis_url` and session cookie settings do not exist.

- [ ] **Step 3: Implement the minimum configuration**

Add `redis==5.2.1`, `argon2-cffi==23.1.0`, and `psutil==6.1.0` to
`backend/requirements.txt`. Change the application defaults and add:

```python
app_name: str = "OpsWeave"
app_version: str = "0.1.0"
redis_url: str = "redis://localhost:6379/0"
session_cookie_name: str = "opsweave_session"
session_cookie_secure: bool = False
session_cookie_samesite: str = "lax"
session_ttl_hours: int = 24
```

Add matching documented values to `.env.example`. Add a `redis:7-alpine`
service with `redis-cli ping` healthcheck to `docker-compose.yml`, set backend
`REDIS_URL=redis://redis:6379/0`, and rename compose containers and default
database values from `opsknowledge_*` to `opsweave_*`.

- [ ] **Step 4: Verify the test and compose model**

Run:

```bash
cd backend && PYTHONPATH=. pytest tests/test_health.py::test_opsweave_settings_expose_redis_and_secure_cookie_defaults -q
cd .. && docker compose config --quiet
```

Expected: one test passes and Compose exits 0.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/core/config.py backend/tests/test_health.py .env.example docker-compose.yml
git commit -m "feat: 建立 OpsWeave runtime 設定"
```

### Task 2: Add Administrator and Session Schema

**Files:**
- Create: `backend/app/models/identity.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/0003_opsweave_foundation.py`
- Create: `backend/tests/test_auth_models.py`

- [ ] **Step 1: Write failing model metadata tests**

Create `backend/tests/test_auth_models.py`:

```python
from app.models.identity import AdminSession, Administrator


def test_administrator_and_session_contract():
    assert Administrator.__tablename__ == "administrators"
    assert Administrator.username.property.columns[0].unique is True
    assert AdminSession.__tablename__ == "admin_sessions"
    assert AdminSession.token_hash.property.columns[0].unique is True
    assert AdminSession.administrator.property.mapper.class_ is Administrator
```

- [ ] **Step 2: Verify the test fails**

Run: `cd backend && PYTHONPATH=. pytest tests/test_auth_models.py -q`

Expected: collection fails because `app.models.identity` does not exist.

- [ ] **Step 3: Implement the models and migration**

Define:

```python
class Administrator(PKMixin, TimestampMixin, Base):
    __tablename__ = "administrators"
    username = Column(VARCHAR(100), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    sessions = relationship("AdminSession", back_populates="administrator", cascade="all, delete-orphan")


class AdminSession(PKMixin, TimestampMixin, Base):
    __tablename__ = "admin_sessions"
    administrator_id = Column(UUID(as_uuid=True), ForeignKey("administrators.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(VARCHAR(64), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    administrator = relationship("Administrator", back_populates="sessions")
```

Import both models in `app/models/__init__.py`. Create Alembic revision
`0003_opsweave_foundation` with unique indexes on username and token hash and
an index on session expiry.

- [ ] **Step 4: Verify model and migration tests**

Run:

```bash
cd backend && PYTHONPATH=. pytest tests/test_auth_models.py tests/test_migrations.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models backend/migrations/versions/0003_opsweave_foundation.py backend/tests/test_auth_models.py
git commit -m "feat: 新增管理員與工作階段模型"
```

### Task 3: Implement Auth Service and API

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/test_auth.py` with an in-memory session fixture matching
the existing test conventions:

```python
def test_password_hash_is_argon2_and_verifies():
    from app.services.auth_service import hash_password, verify_password

    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "correct horse battery staple") is True
    assert verify_password(encoded, "wrong") is False


def test_session_token_is_stored_only_as_sha256(db_session):
    from app.models.identity import Administrator
    from app.services.auth_service import create_session, hash_password

    admin = Administrator(
        username="admin",
        password_hash=hash_password("correct horse battery staple"),
    )
    db_session.add(admin)
    db_session.flush()
    raw, session = create_session(db_session, admin)
    assert raw not in session.token_hash
    assert len(session.token_hash) == 64
```

- [ ] **Step 2: Verify failure**

Run: `cd backend && PYTHONPATH=. pytest tests/test_auth.py -q`

Expected: collection fails because `auth_service` does not exist.

- [ ] **Step 3: Implement service and routes**

Implement Argon2 with `PasswordHasher`, generate raw tokens with
`secrets.token_urlsafe(32)`, store only `sha256(raw).hexdigest()`, and reject
revoked or expired sessions. Add:

```text
POST /auth/bootstrap  # allowed only when no administrator exists
GET  /auth/status     # {"bootstrap_required": true|false}
POST /auth/login
POST /auth/logout
GET  /auth/me
```

Set and clear the configured HTTP-only cookie. Return `409` from bootstrap
when an administrator already exists and use one generic `401` response for
unknown usernames and wrong passwords.

- [ ] **Step 4: Verify service and API behavior**

Run: `cd backend && PYTHONPATH=. pytest tests/test_auth.py -q`

Expected: password, bootstrap-once, login, logout, expiry, and generic-401
tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/services/auth_service.py backend/app/api/auth.py backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: 實作管理員登入與伺服器端 session"
```

### Task 4: Aggregate Operational Health

**Files:**
- Create: `backend/app/services/health_service.py`
- Modify: `backend/app/api/health.py`
- Modify: `backend/tests/test_health.py`

- [ ] **Step 1: Write failing aggregate-health test**

```python
def test_operational_health_degrades_when_redis_is_down(monkeypatch):
    from app.services.health_service import build_operational_health

    monkeypatch.setattr("app.services.health_service.check_database", lambda: "connected")
    monkeypatch.setattr("app.services.health_service.check_vector", lambda: "connected")
    monkeypatch.setattr("app.services.health_service.check_redis", lambda: "disconnected")
    result = build_operational_health()
    assert result["status"] == "degraded"
    assert result["services"]["redis"] == "disconnected"
```

- [ ] **Step 2: Verify failure**

Run: `cd backend && PYTHONPATH=. pytest tests/test_health.py::test_operational_health_degrades_when_redis_is_down -q`

Expected: FAIL because `health_service` does not exist.

- [ ] **Step 3: Implement health aggregation**

Keep `/health` as public liveness. Add authenticated `/api/operations/health`
returning:

```json
{
  "status": "ok",
  "services": {"api": "ok", "database": "connected", "vector": "connected", "redis": "connected"},
  "pulse": {"cpu_percent": 0, "memory_percent": 0, "disk_percent": 0, "uptime_seconds": 0},
  "checked_at": "2026-06-28T00:00:00Z"
}
```

Use `psutil` for pulse values, SQL `SELECT 1` for the database, the existing
vector check for pgvector, and Redis `PING` with a one-second socket timeout.
Any dependency failure produces `degraded`, not an exception.

- [ ] **Step 4: Verify health behavior**

Run: `cd backend && PYTHONPATH=. pytest tests/test_health.py -q`

Expected: all health tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/health_service.py backend/app/api/health.py backend/tests/test_health.py
git commit -m "feat: 聚合 OpsWeave 營運健康狀態"
```

### Task 5: Build the Authenticated React Shell

**Files:**
- Create: `frontend/src/context/AuthContext.tsx`
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/components/auth/ProtectedRoute.tsx`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/context/AuthContext.test.tsx`

- [ ] **Step 1: Write failing auth-context test**

```tsx
it('redirects an anonymous visitor to the administrator login', async () => {
  vi.spyOn(api, 'getCurrentAdministrator').mockRejectedValue(new Error('401'));
  render(<App />);
  expect(await screen.findByRole('heading', { name: '登入 OpsWeave' })).toBeInTheDocument();
});
```

- [ ] **Step 2: Verify failure**

Run: `cd frontend && npm test -- src/context/AuthContext.test.tsx`

Expected: FAIL because the auth context and login page do not exist.

- [ ] **Step 3: Implement the minimum authenticated shell**

All Axios requests use `withCredentials: true`. `AuthProvider` loads
`GET /auth/me`, exposes `administrator`, `loading`, `login`, and `logout`.
`ProtectedRoute` waits during bootstrap, redirects anonymous users to
`/login`, and renders the application shell for authenticated users.

`LoginPage` contains username and password fields, a submit button, a generic
invalid-credentials alert, and no token storage in localStorage.

- [ ] **Step 4: Verify frontend auth**

Run: `cd frontend && npm test -- src/context/AuthContext.test.tsx`

Expected: anonymous redirect and successful-login tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/context frontend/src/pages/LoginPage.tsx frontend/src/components/auth frontend/src/services/api.ts frontend/src/App.tsx
git commit -m "feat: 建立 OpsWeave 前端登入邊界"
```

### Task 6: Build the Modern Bento Dashboard and Sticky Status Bar

**Files:**
- Create: `frontend/src/components/layout/StatusBar.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/components/layout/AppLayout.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx`
- Create: `frontend/src/pages/DashboardPage.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing dashboard test**

```tsx
it('renders the four approved dashboard groups and grouped navigation', async () => {
  vi.spyOn(api, 'getOperationalHealth').mockResolvedValue({
    status: 'ok',
    services: {
      api: 'ok',
      database: 'connected',
      vector: 'connected',
      redis: 'connected',
    },
    pulse: {
      cpu_percent: 28,
      memory_percent: 61,
      disk_percent: 42,
      uptime_seconds: 3600,
    },
    checked_at: '2026-06-28T00:00:00Z',
  });
  render(<DashboardPage />);
  expect(await screen.findByText('System Pulse')).toBeInTheDocument();
  expect(screen.getByText('Knowledge Metrics')).toBeInTheDocument();
  expect(screen.getByText('Agent Workload')).toBeInTheDocument();
  expect(screen.getByText('Activity & Alerts')).toBeInTheDocument();
});
```

- [ ] **Step 2: Verify failure**

Run: `cd frontend && npm test -- src/pages/DashboardPage.test.tsx`

Expected: FAIL because `DashboardPage` does not exist.

- [ ] **Step 3: Implement the approved shell**

Create a compact sticky top bar showing overall status, database, vector,
model state (`not_configured` until the provider plan is implemented), and
active-task count (`0` until the task plan is implemented). Clicking it opens an
accessible detail panel. Group sidebar items under Workspace, AI Team, and
Operations exactly as specified in the design. Do not include a System Status
navigation item.

Create responsive Bento cards for System Pulse, Knowledge Metrics, Agent
Workload, and Activity & Alerts. Foundation-only metrics that have no backend
domain yet render `0` with a clear empty-state label rather than fabricated
activity.

- [ ] **Step 4: Verify tests and production build**

Run:

```bash
cd frontend && npm test -- src/pages/DashboardPage.test.tsx src/App.test.tsx
npm run build
```

Expected: selected tests pass and TypeScript/Vite build exits 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout frontend/src/pages/DashboardPage.tsx frontend/src/pages/DashboardPage.test.tsx frontend/src/App.tsx
git commit -m "feat: 建立 OpsWeave Bento 營運介面"
```

### Task 7: Verify the Foundation as One Stack

**Files:**
- Modify: `README.md`
- Modify: `README.zh-TW.md`
- Modify: `Makefile`
- Modify: `frontend/package.json`
- Create: `frontend/e2e/admin-foundation.spec.ts`
- Create: `frontend/playwright.config.ts`

- [ ] **Step 1: Add a failing Playwright flow**

The flow must bootstrap the first administrator, log out, log in again, open
Dashboard, expand the status bar, and assert PostgreSQL and Redis are shown.

```ts
test('administrator reaches the operational dashboard', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('使用者名稱').fill('admin');
  await page.getByLabel('密碼').fill('correct horse battery staple');
  await page.getByRole('button', { name: '建立管理員' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await page.getByRole('button', { name: /系統正常|系統降級/ }).click();
  await expect(page.getByText('PostgreSQL')).toBeVisible();
  await expect(page.getByText('Redis')).toBeVisible();
});
```

- [ ] **Step 2: Verify it fails before final wiring**

Run: `cd frontend && npx playwright test e2e/admin-foundation.spec.ts`

Expected: FAIL until the stack and bootstrap UI are fully wired.

- [ ] **Step 3: Complete bootstrap UI, scripts, and documentation**

Add `@playwright/test@1.53.1`, the `test:e2e` script, and browser configuration.
Make the login page switch to administrator bootstrap when `/auth/status`
returns `bootstrap_required=true`.
Rename README titles, service names, URLs, Make targets, and safe `.env.example`
instructions to OpsWeave. Keep `make clean` destructive confirmation intact.

- [ ] **Step 4: Run fresh verification**

Run:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose exec backend sh -c "PYTHONPATH=. pytest tests/ -q"
docker compose exec frontend npm test
cd frontend && npx playwright test e2e/admin-foundation.spec.ts
cd .. && curl -fsS http://localhost:8000/health
```

Expected: Compose is valid; postgres, redis, backend, and frontend are healthy;
backend and frontend suites have zero failures; Playwright passes; liveness
returns HTTP 200.

- [ ] **Step 5: Commit**

```bash
git add README.md README.zh-TW.md Makefile frontend/package.json frontend/package-lock.json frontend/e2e frontend/playwright.config.ts frontend/src/pages/LoginPage.tsx
git commit -m "docs: 完成 OpsWeave 平台基礎驗證流程"
```

## Phase 1 Completion Gate

Before starting the durable task-engine plan:

- `git status --short` contains no phase-owned changes.
- Full backend and frontend tests pass.
- Frontend production build passes.
- The administrator Playwright flow passes.
- Docker Compose reports PostgreSQL, Redis, backend, and frontend healthy.
- Existing user-owned changes to `docs/ARCHITECTURE.md` and
  `docs/ARCHITECTURE.zh-TW.md` remain untouched unless the user explicitly
  incorporates them.
