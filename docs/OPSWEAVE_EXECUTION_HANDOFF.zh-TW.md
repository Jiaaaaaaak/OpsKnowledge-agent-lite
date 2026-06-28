# OpsWeave 總交接文件

[English](OPSWEAVE_EXECUTION_HANDOFF.md) | 繁體中文

更新日期：2026-06-28  
文件目的：作為 `feat/opsweave-foundation` 的單一續作交接來源；內容已依目前實際工作區狀態更新。Task 3–7 皆已提交——**foundation 里程碑（Task 1–7）已完成**。接下來是路線圖上的較大里程碑（見 roadmap 文件）。

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
HEAD = 238aced（Task 7 已提交——foundation 完成）
```

也就是說：

- `238aced` 是目前最後一個已提交 commit（Task 7：foundation 驗證 + 文件）
- Task 3–7 已完整提交，worktree 沒有 foundation 任務殘留
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
- 需登入的 `GET /operations/health`（經 `get_current_admin`；Task 6 由
  `/api/operations/health` 改名以符合代理慣例），回傳
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

### Task 5：React 登入邊界

已提交 commit：

```text
4999a4e feat: 建立 OpsWeave 前端登入邊界
```

已完成內容（均在 `frontend/src/`）：

- `context/AuthContext.tsx`：`AuthProvider` 載入 `GET /auth/me`，提供
  `administrator`、`loading`、`login`、`logout`；401 視為未登入
- `components/auth/ProtectedRoute.tsx`：bootstrap 期間等待，未登入導向 `/login`，
  已登入才渲染外殼
- `pages/LoginPage.tsx`：帳號／密碼欄位、通用錯誤訊息、不在 web storage 存任何
  token；已登入者導回 `/`
- `services/api.ts`：axios `withCredentials: true`；`getCurrentAdministrator`、
  `login`、`logout`
- `App.tsx`：以 `AuthProvider` 包覆、新增 `/login` route、外殼置於
  `ProtectedRoute`；`App.test.tsx` 預設視為已登入
- `context/AuthContext.test.tsx`：未登入導向、通用錯誤、登入成功三項測試

審查：規格——無 Critical/Important；品質——無 Critical/Important。延後的 minor：
`logout` 尚未清除 `ProjectContext` 持久化的專案選擇，待 Task 6 接 logout 按鈕時處理
（目前 `logout` 尚無 UI 入口）。

既有驗證結果：

```text
frontend：6 tests passed（3 auth + 3 既有）
tsc --noEmit：clean
git diff --check：clean
```

環境注意事項：前端測試環境需在 `frontend/` 執行 `npm install`（預設無 `node_modules`）。

### Task 6：Bento 儀表板與固定狀態列

已提交 commit：

```text
d27bee5 feat: 建立 OpsWeave Bento 營運介面
```

已完成內容：

- `frontend/src/pages/DashboardPage.tsx`：四張 Bento 卡——System Pulse（CPU／記憶體／
  磁碟／uptime + 更新時間，取自 `getOperationalHealth` 即時值）、Knowledge Metrics、
  Agent Workload、Activity & Alerts。無後端領域的群組誠實顯示 `0` + `尚無資料`，不捏造
- `frontend/src/components/layout/StatusBar.tsx`：固定頂部狀態列（整體、PostgreSQL、
  向量、模型 `not_configured`、進行中任務 `0`）；點擊展開可存取的細節面板
  （`role="region"`、`aria-expanded`）；切換鈕無障礙名稱為 `系統正常／系統降級`；含登出
- 登出會清除持久化的 `ProjectContext` 專案選擇，且伺服器登出失敗仍清本地狀態
  （清掉 Task 5 延後 minor 與品質審查 Important 的未處理 reject）
- `Sidebar.tsx`：重整為 Workspace／AI Team／Operations（完全依設計）；未實作目的地為停用
  佔位；移除系統狀態項；品牌改為 OpsWeave。`/dashboard` 設為 index
- 後端 `/api/operations/health` 改名為 `/operations/health`，與其餘未前綴路由及前端 `/api`
  代理一致（Task 4 測試同步更新）

審查：規格——無 Critical，一個 Important（PostgreSQL 標籤／狀態無障礙名稱）已修；
品質——無 Critical，一個 Important（登出未處理 reject）已修，minor 也補。

既有驗證結果：

```text
frontend：12 tests passed
npm run build：exit 0
backend 完整 suite：239 passed
git diff --check：clean
live stack：經代理驗證 login + GET /operations/health
```

### Task 7：整體 stack 驗證與文件

已提交 commit：

```text
238aced docs: 完成 OpsWeave 平台基礎驗證流程
```

已完成內容：

- `LoginPage.tsx`：依 `/auth/status` 的 `bootstrap_required` 切換「建立管理員
  （bootstrap）」與「登入」；狀態確定前不渲染表單（無閃動、e2e 可穩定定位）。
  `api.ts` 新增 `getAuthStatus` + `bootstrap`；`AuthContext` 新增 `bootstrap`
- `DashboardPage` 標題為 `Dashboard`
- Playwright e2e（`frontend/e2e/admin-foundation.spec.ts`、`playwright.config.ts`、
  `@playwright/test@1.53.1`、`test:e2e`）：bootstrap → Dashboard → 展開狀態列 →
  驗證 PostgreSQL/Redis，並含登出再登入。**idempotent**（無管理員時 bootstrap、
  已存在時登入，同一組固定憑證），可重複執行
- `vite.config.js` 把 vitest 範圍限定 `src/`；`e2e/` 交由 Playwright；
  `test-results/` 已 gitignore
- README／README.zh-TW／Makefile 品牌改為 OpsWeave（保留 `make clean` 破壞性確認）

審查：規格——無 Critical/Important（所有 e2e 選擇器皆與實際畫面字串吻合）；
品質——無 Critical，一個 Important（e2e 非 idempotent）已用 bootstrap-或-login 設計解決。

既有驗證結果（live stack）：

```text
docker compose config --quiet：exit 0
backend 完整 suite：239 passed
frontend 單元：13 passed
npm run build：exit 0
Playwright e2e：2 passed（重跑亦通過——idempotent）
GET /health：200；backend/postgres/redis healthy
```

注意：e2e 的 bootstrap 路徑在「首次」執行需資料庫無管理員；重跑會走登入路徑。要重置成
全新 bootstrap 狀態：
`docker compose exec -T postgres psql -U opsuser -d opsweave -c "DELETE FROM administrators;"`。

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

### 6.1 下一個：路線圖里程碑（foundation 已完成）

foundation（Task 1–7）已完成並提交（HEAD 為 `238aced`）。接下來是較大的路線圖里程碑——
見 `docs/superpowers/plans/2026-06-28-opsweave-roadmap.zh-TW.md`。每個里程碑同樣走：
TDD → 規格審查 → 品質審查 → 提交 → 更新本交接文件。

本機操作注意：live stack 走 Docker Desktop，dev 容器在 WSL2 下不會穩定 hot-reload，改完
程式請 `docker compose restart backend frontend`。舊／重複的 compose stack 可能蓋住主機
8000/8501 埠——用 `docker compose ps` 確認，並確認 `curl localhost:8000/openapi.json`
的 title 是 `OpsWeave`。

### 6.2 foundation 之後的大項

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

續作時先做這幾件事：

1. 確認 `HEAD` 為 `238aced`；foundation（Task 1–7）已完成
2. backend 測試環境需 `argon2-cffi`、`pytest_asyncio`、`redis`、`psutil`；
   前端測試環境需在 `frontend/` 執行 `npm install`，e2e 另需
   `npx playwright install chromium`
3. 從 roadmap 文件挑下一個里程碑

## 8. 建議恢復提示詞

如需下一次直接接手，可使用：

```text
請依 docs/OPSWEAVE_EXECUTION_HANDOFF.zh-TW.md 繼續，分支 feat/opsweave-foundation。
foundation（Task 1–7）已完成（HEAD 238aced）。從
docs/superpowers/plans/2026-06-28-opsweave-roadmap.zh-TW.md 挑下一個里程碑，
依 TDD → 規格審查 → 品質審查 → 提交。
```
