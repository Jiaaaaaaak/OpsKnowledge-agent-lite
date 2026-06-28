# OpsWeave Execution Handoff

English | [繁體中文](OPSWEAVE_EXECUTION_HANDOFF.zh-TW.md)

Updated: 2026-06-28  
Purpose: this is the single handoff source for continuing work on
`feat/opsweave-foundation`. It reflects the actual current worktree state.
Tasks 3–7 are committed — **the foundation milestone (Tasks 1–7) is complete**.
What follows are the larger roadmap milestones (see the roadmap doc).

## Project Goal

Rewrite `OpsKnowledge-agent-lite` into **OpsWeave** with a clean-room
implementation inspired by CoStaff's product flow, without copying AGPL code.

Foundation scope:

- FastAPI control plane
- React Modern Bento frontend
- PostgreSQL / pgvector
- Redis
- administrator auth with server-side sessions
- sticky operational status bar and dashboard shell

Locked product direction:

- product name: `OpsWeave`
- the old `OpsKnowledge-agent-lite` product does not need to be preserved
- existing RAG becomes the built-in `Knowledge Agent`
- built-in agents: Manager, Knowledge, Coding, Business Analysis
- channels: WebChat, Telegram, Discord, LINE

## Branches and Worktree

Primary design branch:

```text
feat/opsweave-rewrite
```

Foundation implementation branch:

```text
feat/opsweave-foundation
```

Isolated worktree:

```text
/home/jia/python_workstation/OpsKnowledge-agent-lite/.worktrees/opsweave-foundation
```

Resume with:

```bash
cd /home/jia/python_workstation/OpsKnowledge-agent-lite/.worktrees/opsweave-foundation
git status --short --branch
git log --oneline --decorate -12
```

Actual current state:

```text
## feat/opsweave-foundation
HEAD = 238aced (Task 7 committed — foundation complete)
```

This means:

- `238aced` is the latest committed change (Task 7: foundation verification + docs)
- Tasks 3–7 are fully committed; the worktree has no foundation-task leftovers
- the only uncommitted files are these two handoff docs (being updated now)

Do not modify or commit the user-owned files in the original checkout:

```text
docs/ARCHITECTURE.md
docs/ARCHITECTURE.zh-TW.md
```

## Source Documents

Specs:

- `docs/superpowers/specs/2026-06-28-opsweave-rewrite-design.md`
- `docs/superpowers/specs/2026-06-28-opsweave-rewrite-design.zh-TW.md`

Plans:

- `docs/superpowers/plans/2026-06-28-opsweave-roadmap.md`
- `docs/superpowers/plans/2026-06-28-opsweave-roadmap.zh-TW.md`
- `docs/superpowers/plans/2026-06-28-opsweave-foundation-implementation.md`

Use this handoff for actual current status and resume steps. Use the spec and
plan files for product direction and task breakdown.

## Committed Work

### Task 1: Runtime, Redis, Security Defaults

Commits:

```text
81ec78d feat: 建立 OpsWeave runtime 設定
a18e4ef fix: 移除未證實的 AnyIO pin
6e8c490 fix: 強化 OpsWeave runtime 安全預設
8d79c07 fix: 校正 OpsWeave Compose 操作預設
```

Delivered:

- OpsWeave runtime defaults
- Redis, argon2-cffi, psutil dependencies
- Redis compose service and healthcheck
- internal-only Redis networking
- backend waits for healthy Redis
- optional Compose `.env`
- session cookie and TTL settings
- OpsWeave compose/database naming
- corrected database shell defaults

Recorded verification:

```text
backend/tests/test_health.py: 4 passed
docker compose config --quiet: exit 0
git diff --check: exit 0
```

### Task 2: Administrator / AdminSession Schema

Commits:

```text
b779304 feat: 新增管理員與工作階段模型
dc7171b test: 補強管理員 schema migration contract
```

Delivered:

- `Administrator` ORM
- `AdminSession` ORM
- password and token hash storage
- cascade session relationship
- expiry and revocation fields
- migration `0003_opsweave_foundation`
- offline Alembic SQL contract tests

Recorded verification:

```text
focused auth/model/migration suite: 12 passed
Alembic head: 0003
offline upgrade / downgrade SQL: success
```

### Documentation Commit

Commit:

```text
1243384 docs: 新增 OpsWeave 執行交接文件
```

That older handoff content is now outdated because it claimed the worktree was
clean and Task 3 had not started.

### Task 3: Auth Service and API

Commit:

```text
d2242c8 feat: 實作管理員登入與伺服器端 session
```

Delivered:

- `backend/app/services/auth_service.py`: `hash_password`, `verify_password`,
  `hash_token`, `generate_token`, `bootstrap_required`, `authenticate`,
  `create_session`, `resolve_session`, `revoke_session`
- Argon2id password hashing; `secrets.token_urlsafe(32)` raw session tokens;
  DB stores only SHA-256 token hashes
- dummy Argon2 verify for unknown users (timing); unknown user / wrong password /
  inactive admin all return `None` at the service layer
- expired / revoked / inactive-admin sessions rejected
- `backend/app/api/auth.py`: `GET /auth/status`, `POST /auth/bootstrap`,
  `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- bootstrap allowed only before any administrator exists, otherwise `409`
- login/bootstrap set an HTTP-only session cookie; logout revokes and clears it
- unknown user and wrong password share one generic `401 detail`
- `backend/app/schemas/auth.py`: `BootstrapRequest`, `LoginRequest`, `AdminRead`,
  `AuthStatus`, `MessageResponse` — responses never expose password/session hashes
- `auth_router` wired into `backend/app/main.py`
- `backend/tests/conftest.py`: in-memory SQLite with `StaticPool`, auth tables only,
  API tests over `httpx.ASGITransport` (avoids the known TestClient/AnyIO hang)

Security hardening (from quality review, one Important finding resolved):

- the session cookie carries the raw bearer token, so `session_cookie_secure`
  now defaults to `True` (secure-by-default); local HTTP development overrides it
  with `.env` `SESSION_COOKIE_SECURE=false`
- this also touched `backend/app/core/config.py` and the Task 1 default assertion
  in `backend/tests/test_health.py`

Reviews:

- spec review: no Critical / Important gaps
- quality review: no Critical; one Important (insecure cookie default) resolved;
  minor test-quality gaps addressed (token-hash invariant, dummy-verify behavior,
  forced-reload datetime guard)

Recorded verification:

```text
tests/test_auth.py: 20 passed
full backend suite: 231 passed (no hang)
git diff --check: clean
```

Environment note:

- `argon2-cffi` (already listed in `backend/requirements.txt`) and `pytest_asyncio`
  must be installed in the test environment; an earlier run was blocked by a
  missing `pytest_asyncio` / `argon2` in the shared venv. Install backend
  requirements before running the auth suite.

### Task 4: Operational Health Aggregation

Commit:

```text
7b19d1e feat: 聚合 OpsWeave 營運健康狀態
```

Delivered:

- `backend/app/services/health_service.py`: module-level `check_database`,
  `check_vector`, `check_redis`, plus `build_operational_health`
- authenticated `GET /operations/health` (via `get_current_admin`; renamed from
  `/api/operations/health` in Task 6 for proxy consistency) returning
  `status`, `services{api,database,vector,redis}`, `pulse{cpu_percent,
  memory_percent,disk_percent,uptime_seconds}`, `checked_at`
- public `/health` liveness unchanged (still 503 when DB/pgvector down)
- Redis `PING` with a 1s connect/read timeout and explicit client close; psutil
  pulse primed once at import; any dependency failure degrades, never raises
- quality-review Important resolved: `_pulse()` is exception-guarded and reports
  `None` metrics instead of 500-ing, preserving the never-raise contract
- `redis` and `psutil` (already in `backend/requirements.txt`) must be installed
  in the test environment

Recorded verification:

```text
tests/test_health.py: 12 passed
full backend suite: 239 passed (no hang)
git diff --check: clean
```

Reviews: spec — no Critical/Important; quality — no Critical, one Important
(`_pulse()` unguarded) resolved, minors addressed (1s-timeout assertion, cpu
priming, client close).

### Task 5: React Authentication Boundary

Commit:

```text
4999a4e feat: 建立 OpsWeave 前端登入邊界
```

Delivered (all under `frontend/src/`):

- `context/AuthContext.tsx`: `AuthProvider` loads `GET /auth/me`, exposes
  `administrator`, `loading`, `login`, `logout`; 401 treated as anonymous
- `components/auth/ProtectedRoute.tsx`: waits during bootstrap, redirects
  anonymous users to `/login`, renders the shell when authenticated
- `pages/LoginPage.tsx`: username/password fields, generic invalid-credentials
  alert, no token stored in web storage; redirects authenticated users to `/`
- `services/api.ts`: axios `withCredentials: true`; `getCurrentAdministrator`,
  `login`, `logout`
- `App.tsx`: wrapped in `AuthProvider`, `/login` route, app shell under
  `ProtectedRoute`; `App.test.tsx` updated to authenticate by default
- `context/AuthContext.test.tsx`: anonymous-redirect, generic-alert, and
  successful-login tests

Reviews: spec — no Critical/Important; quality — no Critical/Important. Deferred
minor: `logout` does not yet clear the persisted `ProjectContext` selection;
handle when the logout button is wired in Task 6 (`logout` is not yet UI-reachable).

Recorded verification:

```text
frontend: 6 tests passed (3 auth + 3 existing)
tsc --noEmit: clean
git diff --check: clean
```

Environment note: the frontend test env needs `npm install` in `frontend/`
(no `node_modules` by default).

### Task 6: Bento Dashboard and Sticky Status Bar

Commit:

```text
d27bee5 feat: 建立 OpsWeave Bento 營運介面
```

Delivered:

- `frontend/src/pages/DashboardPage.tsx`: four approved Bento groups — System
  Pulse (live CPU/memory/disk/uptime + refresh time from `getOperationalHealth`),
  Knowledge Metrics, Agent Workload, Activity & Alerts. Foundation-empty groups
  render `0` + `尚無資料`, never fabricated activity
- `frontend/src/components/layout/StatusBar.tsx`: sticky top bar (overall,
  PostgreSQL, vector, model `not_configured`, active-tasks `0`); click expands an
  accessible (`role="region"`, `aria-expanded`) detail panel; toggle accessible
  name is `系統正常/系統降級`; includes logout
- logout clears the persisted `ProjectContext` selection and still clears local
  state if the server logout fails (resolves the Task 5 deferred minor and the
  quality-review Important about an unhandled rejection)
- `Sidebar.tsx`: regrouped Workspace / AI Team / Operations exactly per design;
  not-yet-built destinations are disabled placeholders; no System Status nav item;
  rebranded to OpsWeave. `/dashboard` is the index route
- backend route renamed `/api/operations/health` → `/operations/health` for
  consistency with all other unprefixed routes and the frontend `/api` proxy
  (Task 4 test updated)

Reviews: spec — no Critical; one Important (PostgreSQL labeling / accessible
status name) resolved. quality — no Critical; one Important (logout unhandled
rejection) resolved; minors addressed.

Recorded verification:

```text
frontend: 12 tests passed
npm run build: exit 0
backend full suite: 239 passed
git diff --check: clean
live stack: login + GET /operations/health verified through the proxy
```

### Task 7: Verify the Foundation as One Stack

Commit:

```text
238aced docs: 完成 OpsWeave 平台基礎驗證流程
```

Delivered:

- `LoginPage.tsx`: switches between administrator **bootstrap** and **login** by
  `/auth/status` `bootstrap_required`; the form is gated on status resolving (no
  flash, deterministic e2e). `api.ts` gains `getAuthStatus` + `bootstrap`;
  `AuthContext` gains a `bootstrap` method
- `DashboardPage` heading is `Dashboard`
- Playwright e2e (`frontend/e2e/admin-foundation.spec.ts`, `playwright.config.ts`,
  `@playwright/test@1.53.1`, `test:e2e` script): bootstrap → Dashboard → expand
  status bar → assert PostgreSQL/Redis, plus logout→login. **Idempotent**
  (bootstrap when no admin, otherwise login, fixed creds) so it can re-run
- `vite.config.js` scopes vitest to `src/`; `e2e/` runs under Playwright;
  `test-results/` is gitignored
- README / README.zh-TW / Makefile rebranded to OpsWeave (`make clean`
  confirmation kept)

Reviews: spec — no Critical/Important (all e2e selectors verified against rendered
strings). quality — no Critical; one Important (non-idempotent e2e) resolved by
the bootstrap-or-login design.

Recorded verification (live stack):

```text
docker compose config --quiet: exit 0
backend full suite: 239 passed
frontend unit: 13 passed
npm run build: exit 0
Playwright e2e: 2 passed (re-run also passed — idempotent)
GET /health: 200; backend/postgres/redis healthy
```

Note: the e2e bootstrap path needs a DB with no administrator on its very first
run; re-runs take the login path. To reset for a fresh bootstrap run:
`docker compose exec -T postgres psql -U opsuser -d opsweave -c "DELETE FROM administrators;"`.

## Known Baseline Issue

Shared local environment:

```text
FastAPI 0.115.5
Starlette 0.41.3
HTTPX 0.28.1
AnyIO 4.13.0
```

Known issue:

- Starlette `TestClient` / AnyIO blocking portal can hang intermittently
- reproduced even with a minimal FastAPI app
- AnyIO 4.12 and 4.9 did not reliably resolve it, so no pin was committed

Testing rule for later work:

- prefer `httpx.AsyncClient` with `ASGITransport`
- do not hide the issue with arbitrary dependency pins

## Execution Order

### Next: Roadmap milestones (foundation is done)

The foundation (Tasks 1–7) is complete and committed (`238aced` is HEAD). What
follows is the larger roadmap — see
`docs/superpowers/plans/2026-06-28-opsweave-roadmap.md`. Each milestone should
follow the same loop: TDD → spec review → quality review → commit → update this
handoff.

Operational note for this machine: the live stack uses Docker Desktop; dev
containers do NOT hot-reload reliably on WSL2, so run
`docker compose restart backend frontend` after editing code. Old/duplicate
compose stacks can shadow host ports 8000/8501 — verify with
`docker compose ps` and that `curl localhost:8000/openapi.json` reports title
`OpsWeave`.

Later milestones:

```text
Durable Task Engine
Agent Protocol / Manager
Knowledge Agent
Coding / Business Analysis Agent
WebChat / Identity Approval
Telegram / Discord / LINE
Projects / Automation / Diary / Registry
Operational Completion
```

## Resume Rules

- Use TDD: RED -> GREEN -> REFACTOR.
- Run spec review before quality review.
- Do not continue with unresolved Critical or Important findings.
- Do not overwrite the user's uncommitted files in the original checkout.
- Re-run verification before claiming completion.

Resume with these checks:

1. Confirm `HEAD` is `238aced`; the foundation (Tasks 1–7) is complete.
2. Backend test env needs `argon2-cffi`, `pytest_asyncio`, `redis`, `psutil`;
   frontend test env needs `npm install` in `frontend/` and, for e2e,
   `npx playwright install chromium`.
3. Pick the next roadmap milestone from the roadmap doc.

## Suggested Resume Prompt

```text
Continue from docs/OPSWEAVE_EXECUTION_HANDOFF.md on feat/opsweave-foundation.
The foundation (Tasks 1–7) is complete (HEAD 238aced). Pick the next roadmap
milestone from docs/superpowers/plans/2026-06-28-opsweave-roadmap.md and follow
TDD → spec review → quality review → commit.
```
