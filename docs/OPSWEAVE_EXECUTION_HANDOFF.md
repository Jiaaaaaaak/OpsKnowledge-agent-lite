# OpsWeave Execution Handoff

English | [繁體中文](OPSWEAVE_EXECUTION_HANDOFF.zh-TW.md)

Updated: 2026-06-28  
Status: paused by user request. The implementation worktree is clean and Task
3 has no partial changes.

## Resume Location

```bash
cd /home/jia/python_workstation/OpsKnowledge-agent-lite/.worktrees/opsweave-foundation
git status --short --branch
git log -8 --oneline
```

Expected branch: `feat/opsweave-foundation`  
Expected HEAD: `dc7171b`

The primary design branch is `feat/opsweave-rewrite`.

Do not modify or commit the user-owned changes to
`docs/ARCHITECTURE.md` and `docs/ARCHITECTURE.zh-TW.md` in the original
checkout.

## Source Documents

- Design:
  `docs/superpowers/specs/2026-06-28-opsweave-rewrite-design.md`
- Delivery roadmap:
  `docs/superpowers/plans/2026-06-28-opsweave-roadmap.md`
- Phase 1 plan:
  `docs/superpowers/plans/2026-06-28-opsweave-foundation-implementation.md`

## Completed

Task 1 established OpsWeave runtime defaults, internal-only Redis, optional
Compose `.env`, session configuration, safe Compose dependencies, and matching
database command defaults. Task 1 ends at commit `8d79c07`.

Task 2 added Administrator and AdminSession models, migration 0003, indexes,
cascade behavior, and executable Alembic offline SQL contract tests. Task 2
ends at commit `dc7171b`.

Both tasks passed spec and quality review with no unresolved Critical or
Important issues.

## Known Environment Issue

The shared local Python environment intermittently hangs inside Starlette
`TestClient` and the AnyIO blocking portal. A minimal FastAPI application
reproduces it. AnyIO 4.12.0 and 4.9.0 did not reliably eliminate the hang, so
no unproven dependency pin was committed.

Use `httpx.AsyncClient` with `httpx.ASGITransport(app=app)` for Task 3 API
tests. Do not hide the problem with an arbitrary dependency pin.

## Next Work

Resume at Task 3: Auth Service and API.

Create:

- `backend/app/schemas/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth.py`
- `backend/tests/test_auth.py`

Modify:

- `backend/app/main.py`

Implement Argon2id password handling, hashed opaque sessions, bootstrap
status, one-time administrator bootstrap, login, logout, current
administrator, secure cookie behavior, generic authentication failures,
inactive/expired/revoked checks, and response schemas that never expose
password or session hashes.

Follow the Phase 1 plan and use TDD. API tests must avoid `TestClient`.

Remaining Phase 1 tasks are operational health aggregation, React
authentication, the Modern Bento dashboard and sticky status bar, then full
stack verification and documentation.

## Execution Rules

- RED, GREEN, REFACTOR for every behavior.
- Fresh implementer for each task.
- Spec review before quality review.
- Do not continue while Critical or Important findings remain.
- Do not run concurrent writers against the same worktree.
- Re-run verification before every completion claim.
