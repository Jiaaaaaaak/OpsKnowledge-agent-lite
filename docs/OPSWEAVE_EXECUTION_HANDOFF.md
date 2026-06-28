# OpsWeave Execution Handoff

English | [繁體中文](OPSWEAVE_EXECUTION_HANDOFF.zh-TW.md)

Updated: 2026-06-28  
Purpose: this is the single handoff source for continuing work on
`feat/opsweave-foundation`. It reflects the actual current worktree state.
Tasks 3 (auth), 4 (operational health) and 5 (React login boundary) are
committed; next is Task 6.

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
HEAD = 4999a4e (Task 5 committed)
```

This means:

- `4999a4e` is the latest committed change (Task 5: React login boundary)
- Tasks 3, 4 and 5 are fully committed; the worktree has no Task 3/4/5 leftovers
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
- authenticated `GET /api/operations/health` (via `get_current_admin`) returning
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

### Next: Task 6

Tasks 3, 4 and 5 are complete and committed (`d2242c8`, `7b19d1e`, `4999a4e`).
Start Task 6 (Modern Bento dashboard and sticky status bar) per the
implementation plan, using a fresh implementation agent, TDD, then spec review
and quality review before committing. When wiring the logout button, also clear
the persisted `ProjectContext` selection (deferred Task 5 minor).

### Remaining Foundation Tasks

```text
Task 6: Modern Bento dashboard and sticky status bar
Task 7: full-stack verification and documentation
```

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

1. Confirm `HEAD` is `4999a4e` and the worktree has no Task 3/4/5 leftovers.
2. Backend test env needs `argon2-cffi`, `pytest_asyncio`, `redis`, `psutil`;
   frontend test env needs `npm install` in `frontend/`.
3. Begin Task 6 from the implementation plan.

## Suggested Resume Prompt

```text
Continue from docs/OPSWEAVE_EXECUTION_HANDOFF.md on feat/opsweave-foundation.
Tasks 3, 4 and 5 are committed (d2242c8, 7b19d1e, 4999a4e). Start Task 6
(Modern Bento dashboard and sticky status bar) using TDD, then run spec review
and quality review before committing.
```
