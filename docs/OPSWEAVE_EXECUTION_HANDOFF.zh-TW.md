# OpsWeave 總交接文件

[English](OPSWEAVE_EXECUTION_HANDOFF.md) | 繁體中文

更新日期：2026-06-28  
文件目的：作為 `feat/opsweave-foundation` 的單一續作交接來源；內容已依目前實際工作區狀態更新。Task 3（auth）與 Task 4（營運健康）已提交，下一個待辦為 Task 5。

## 1. 專案目標

將原 `OpsKnowledge-agent-lite` 乾淨重寫為 **OpsWeave**，產品流程與資訊架構參考
CoStaff，但不得複製其 AGPL 原始碼。

第一期目標：

- FastAPI control plane
- React Modern Bento 前端
- PostgreSQL / pgvector
- Redis
- 管理員登入與伺服器端 session
- 營運健康狀態列與 Dashboard 骨架

產品方向已鎖定：

- 產品名稱：`OpsWeave`
- 既有 `OpsKnowledge-agent-lite` 可不保留為獨立產品
- 既有 RAG 能力保留為內建 `Knowledge Agent`
- 主要內建 Agent：Manager、Knowledge、Coding、Business Analysis
- 通路：WebChat、Telegram、Discord、LINE

## 2. 分支與工作區

主要規格分支：

```text
feat/opsweave-rewrite
```

第一期實作分支：

```text
feat/opsweave-foundation
```

隔離 worktree：

```text
/home/jia/python_workstation/OpsKnowledge-agent-lite/.worktrees/opsweave-foundation
```

恢復工作前先確認：

```bash
cd /home/jia/python_workstation/OpsKnowledge-agent-lite/.worktrees/opsweave-foundation
git status --short --branch
git log --oneline --decorate -12
```

目前實際狀態：

```text
## feat/opsweave-foundation
HEAD = 7b19d1e（Task 4 已提交）
```

也就是說：

- `7b19d1e` 是目前最後一個已提交 commit（Task 4：營運健康聚合）
- Task 3、Task 4 已完整提交，worktree 沒有 Task 3/4 殘留
- 唯一未提交的是這兩份 handoff 文件（正在更新中）

原始 checkout 仍有使用者未提交文件：

```text
docs/ARCHITECTURE.md
docs/ARCHITECTURE.zh-TW.md
```

不得覆蓋、還原、納入 OpsWeave commit。

## 3. 已有規格與計畫文件

設計規格：

- `docs/superpowers/specs/2026-06-28-opsweave-rewrite-design.zh-TW.md`
- `docs/superpowers/specs/2026-06-28-opsweave-rewrite-design.md`

路線與計畫：

- `docs/superpowers/plans/2026-06-28-opsweave-roadmap.zh-TW.md`
- `docs/superpowers/plans/2026-06-28-opsweave-roadmap.md`
- `docs/superpowers/plans/2026-06-28-opsweave-foundation-implementation.md`

這份 handoff 的定位是：

- 規格與長期方向看 `spec` / `roadmap`
- 實作切分看 `implementation plan`
- 當前真實狀態、未提交進度、恢復步驟看這份 handoff

## 4. 已完成提交

### Task 1：Runtime、Redis、安全預設

已提交 commits：

```text
81ec78d feat: 建立 OpsWeave runtime 設定
a18e4ef fix: 移除未證實的 AnyIO pin
6e8c490 fix: 強化 OpsWeave runtime 安全預設
8d79c07 fix: 校正 OpsWeave Compose 操作預設
```

已完成內容：

- app 預設名稱改為 `OpsWeave`
- 新增 `redis`、`argon2-cffi`、`psutil`
- Compose 新增 Redis service 與 healthcheck
- Redis 不暴露 host port，只走 internal network
- backend 等 Redis healthy 才啟動
- `.env` 對 Compose 為 optional
- 補上 session cookie / TTL 設定
- Compose 預設 database / container 名稱改為 OpsWeave
- `make psql` 相關預設已校正

既有驗證結果：

```text
backend/tests/test_health.py：4 passed
docker compose config --quiet：exit 0
git diff --check：exit 0
```

### Task 2：Administrator / AdminSession schema

已提交 commits：

```text
b779304 feat: 新增管理員與工作階段模型
dc7171b test: 補強管理員 schema migration contract
```

已完成內容：

- `Administrator` ORM
- `AdminSession` ORM
- `password_hash` / `token_hash` 欄位
- cascade session relationship
- `expires_at`、`revoked_at`
- migration `0003_opsweave_foundation`
- offline Alembic SQL contract tests

既有驗證結果：

```text
focused auth/model/migration suite：12 passed
Alembic head：0003
offline upgrade / downgrade SQL：成功
```

### Task 3：Auth service 與 API

已提交 commit：

```text
d2242c8 feat: 實作管理員登入與伺服器端 session
```

已完成內容：

- `backend/app/services/auth_service.py`：`hash_password`、`verify_password`、
  `hash_token`、`generate_token`、`bootstrap_required`、`authenticate`、
  `create_session`、`resolve_session`、`revoke_session`
- 使用 Argon2id；session raw token 由 `secrets.token_urlsafe(32)` 生成；
  DB 僅存 `SHA-256` token hash
- unknown user 走 dummy Argon2 verify（timing）；unknown user / wrong password /
  inactive admin 在 service 層都回 `None`
- expired / revoked / inactive admin session 會拒絕
- `backend/app/api/auth.py`：`GET /auth/status`、`POST /auth/bootstrap`、
  `POST /auth/login`、`POST /auth/logout`、`GET /auth/me`
- bootstrap 僅允許首次安裝，否則回 `409`
- login / bootstrap 成功設 HTTP-only session cookie；logout 撤銷並清 cookie
- wrong password / unknown user 共用同一組通用 `401 detail`
- `backend/app/schemas/auth.py`：`BootstrapRequest`、`LoginRequest`、`AdminRead`、
  `AuthStatus`、`MessageResponse`——回應不含 password / session hash
- `auth_router` 已接入 `backend/app/main.py`
- `backend/tests/conftest.py`：in-memory SQLite + `StaticPool`，只建立 auth 兩張表，
  API 測試走 `httpx.ASGITransport`（避開已知 TestClient / AnyIO 卡死）

安全強化（品質審查，清掉一個 Important）：

- session cookie 內含原始 bearer token，因此 `session_cookie_secure` 預設改為
  `True`（secure-by-default）；本機 HTTP 開發以 `.env` 的
  `SESSION_COOKIE_SECURE=false` 覆蓋
- 此修正一併動到 `backend/app/core/config.py` 與 Task 1 的預設斷言
  `backend/tests/test_health.py`

審查：

- 規格審查：無 Critical / Important 缺口
- 品質審查：無 Critical；一個 Important（不安全的 cookie 預設）已修正；
  minor 測試品質缺口也補強（token hash 不變式、dummy verify 行為、強制 reload 的
  datetime 防護）

既有驗證結果：

```text
tests/test_auth.py：20 passed
完整 backend suite：231 passed（無卡死）
git diff --check：clean
```

環境注意事項：

- `argon2-cffi`（已列於 `backend/requirements.txt`）與 `pytest_asyncio` 必須安裝在
  測試環境；先前曾因共享 venv 缺 `pytest_asyncio` / `argon2` 而卡關。執行 auth
  測試前請先安裝 backend requirements。

### Task 4：營運健康聚合

已提交 commit：

```text
7b19d1e feat: 聚合 OpsWeave 營運健康狀態
```

已完成內容：

- `backend/app/services/health_service.py`：module 層 `check_database`、
  `check_vector`、`check_redis`，以及 `build_operational_health`
- 需登入的 `GET /api/operations/health`（經 `get_current_admin`），回傳
  `status`、`services{api,database,vector,redis}`、`pulse{cpu_percent,
  memory_percent,disk_percent,uptime_seconds}`、`checked_at`
- 公開 `/health` liveness 不變（DB/pgvector 掛掉仍回 503）
- Redis `PING` 帶 1 秒 connect/read 逾時並明確關閉連線；psutil pulse 於 import
  時先 prime 基準；任一依賴失敗只降級、不外拋
- 已清品質審查 Important：`_pulse()` 以 try/except 包覆，主機 metrics 取不到時回
  `None` 而非 500，維持「健康端點不外拋」契約
- `redis` 與 `psutil`（已列於 `backend/requirements.txt`）需安裝於測試環境

既有驗證結果：

```text
tests/test_health.py：12 passed
完整 backend suite：239 passed（無卡死）
git diff --check：clean
```

審查：規格——無 Critical/Important；品質——無 Critical，一個 Important
（`_pulse()` 未防護）已修，minor 也補（1 秒逾時斷言、cpu 預熱、關閉連線）。

## 5. 已知 baseline 問題

共享 venv 組合：

```text
FastAPI 0.115.5
Starlette 0.41.3
HTTPX 0.28.1
AnyIO 4.13.0
```

已知問題：

- Starlette `TestClient` / AnyIO blocking portal 可能間歇性卡死
- 最小 FastAPI 程式也可重現，並非 OpsWeave 邏輯導致
- AnyIO 4.12 / 4.9 先前都未穩定解決，因此沒有提交 pin

後續 API 測試原則：

- 優先使用 `httpx.AsyncClient + ASGITransport`
- 不要為了掩蓋問題而任意 pin 依賴

## 6. 後續執行順序

### 6.1 下一個：Task 5

Task 3、Task 4 已完成並提交（`d2242c8`、`7b19d1e`）。接著依 implementation plan
進行 Task 5（React 登入邊界）：使用新的實作代理、走 TDD，提交前先做規格審查與品質審查。

### 6.2 剩餘 foundation 任務

剩餘 foundation 任務：

```text
Task 5：React 登入邊界
Task 6：Modern Bento Dashboard 與固定狀態列
Task 7：整體 stack 驗證與文件
```

foundation 之後的大項：

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

## 7. 恢復執行規範

續作時維持以下規則：

- 每個 Task 走 TDD：RED → GREEN → REFACTOR
- 完成一個 Task 後先做規格審查，再做品質審查
- Critical / Important 未清零不得往下
- 不覆蓋原始 checkout 的未提交文件
- 宣告完成前必須重新執行驗證命令

續作時先做這三件事：

1. 確認 `HEAD` 為 `7b19d1e`，worktree 沒有 Task 3/4 殘留
2. 確認 backend 測試環境已安裝 `argon2-cffi`、`pytest_asyncio`、`redis`、`psutil`
3. 依 implementation plan 開始 Task 5

## 8. 建議恢復提示詞

如需下一次直接接手，可使用：

```text
請依 docs/OPSWEAVE_EXECUTION_HANDOFF.zh-TW.md 繼續，分支 feat/opsweave-foundation。
Task 3、Task 4 已提交（d2242c8、7b19d1e）。開始 Task 5（React 登入邊界），走 TDD，
提交前先做規格審查與品質審查。
```
