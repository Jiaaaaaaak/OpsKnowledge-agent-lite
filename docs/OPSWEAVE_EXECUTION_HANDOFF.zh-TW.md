# OpsWeave 執行與交接文件

[English](OPSWEAVE_EXECUTION_HANDOFF.md) | 繁體中文

更新日期：2026-06-28  
狀態：依使用者要求暫停，工作區乾淨，沒有 Task 3 半成品。

## 1. 目標

將原 OpsKnowledge Agent Lite 乾淨重寫為 **OpsWeave**：以 CoStaff 的產品流程
作為參考，但不複製其 AGPL 原始碼。

第一版包含：

- Manager、Knowledge、Coding、Business Analysis 四個獨立 Agent。
- A2A 派工、MCP 工具白名單。
- WebChat、Telegram、Discord、LINE。
- FastAPI Control Plane、React Modern Bento Dashboard。
- PostgreSQL／pgvector、Redis、Dramatiq。
- Epic、Story、Task、Reminder、Recurring Work、Diary、Skill/API Registry。
- Gemini、OpenAI-compatible、Ollama。

## 2. Git 與工作區

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

恢復工作：

```bash
cd /home/jia/python_workstation/OpsKnowledge-agent-lite/.worktrees/opsweave-foundation
git status --short --branch
git log -8 --oneline
```

預期：

```text
## feat/opsweave-foundation
HEAD = dc7171b
```

原始 checkout 中存在使用者尚未提交的：

```text
docs/ARCHITECTURE.md
docs/ARCHITECTURE.zh-TW.md
```

不得覆蓋、還原或納入 OpsWeave commit。

## 3. 規格與計畫

- 設計規格：
  `docs/superpowers/specs/2026-06-28-opsweave-rewrite-design.zh-TW.md`
- 英文設計：
  `docs/superpowers/specs/2026-06-28-opsweave-rewrite-design.md`
- 總體路線圖：
  `docs/superpowers/plans/2026-06-28-opsweave-roadmap.zh-TW.md`
- 第一期詳細計畫：
  `docs/superpowers/plans/2026-06-28-opsweave-foundation-implementation.md`

## 4. 已完成項目

### Task 1：Runtime、Redis 與安全預設

完成內容：

- 應用預設名稱改為 OpsWeave。
- 新增 Redis、Argon2、psutil dependency。
- 新增 Redis Compose service 與 healthcheck。
- Redis 僅供 Compose internal network 使用，不發布 host port。
- Backend 在 Redis healthy 後啟動。
- `.env` 對 Compose 設為 optional，可在 clean checkout 驗證。
- 新增 session cookie 與 TTL 設定。
- Compose container／database defaults 改為 OpsWeave。
- `make psql` 使用 `opsuser`／`opsweave`。

相關 commits：

```text
81ec78d feat: 建立 OpsWeave runtime 設定
a18e4ef fix: 移除未證實的 AnyIO pin
6e8c490 fix: 強化 OpsWeave runtime 安全預設
8d79c07 fix: 校正 OpsWeave Compose 操作預設
```

驗證：

```text
backend/tests/test_health.py：4 passed
docker compose config --quiet：exit 0（沒有 .env）
git diff --check：exit 0
```

規格與品質審查均通過；沒有 Critical／Important 問題。

### Task 2：Administrator／AdminSession schema

完成內容：

- `Administrator` ORM。
- `AdminSession` ORM。
- Argon2 password hash 儲存欄位。
- 僅儲存 session token SHA-256 hash。
- timezone-aware expiry／revocation 欄位。
- Administrator cascade session relationship。
- `administrator_id`、`expires_at` indexes。
- Alembic `0003_opsweave_foundation` upgrade／downgrade。
- 真實 Alembic offline SQL contract tests。

相關 commits：

```text
b779304 feat: 新增管理員與工作階段模型
dc7171b test: 補強管理員 schema migration contract
```

驗證：

```text
Auth/model/migration focused suite：12 passed
Alembic head：0003
Offline upgrade／downgrade SQL：成功
```

規格與品質審查通過；Critical／Important／Minor 均為零。

## 5. 已知 baseline 問題

本機共享 Python venv 中：

```text
FastAPI 0.115.5
Starlette 0.41.3
HTTPX 0.28.1
AnyIO 4.13.0
```

Starlette `TestClient`／AnyIO blocking portal 會間歇性卡死。最小 FastAPI
程式也可重現，並非 OpsWeave 應用邏輯造成。

曾測試 AnyIO 4.12.0 與 4.9.0，但都無法穩定消除問題，因此**沒有提交未證實
的 AnyIO pin**。

後續 API 測試應優先使用：

```python
httpx.AsyncClient(
    transport=httpx.ASGITransport(app=app),
    base_url="http://test",
)
```

不得用任意 dependency pin 掩蓋問題。

## 6. 下一步：Task 3

Task 3 尚未開始，沒有未提交檔案。

需要建立：

```text
backend/app/schemas/auth.py
backend/app/services/auth_service.py
backend/app/api/auth.py
backend/tests/test_auth.py
```

需要修改：

```text
backend/app/main.py
```

功能：

- Argon2id hash／verify。
- `secrets.token_urlsafe(32)` 產生 session token。
- DB 只保存 SHA-256 token hash。
- `POST /auth/bootstrap`
- `GET /auth/status`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- HTTP-only、SameSite cookie。
- unknown user／wrong password 使用相同 401。
- unknown user 執行 dummy Argon2 verify，降低 timing 差異。
- inactive、expired、revoked session 拒絕。
- Pydantic response 不得暴露 password/session hash。

測試必須先 RED，再 GREEN，並使用 ASGITransport，避免已知 TestClient hang。

## 7. 後續任務

```text
Task 3：Auth service 與 API
Task 4：營運健康聚合
Task 5：React 登入邊界
Task 6：Modern Bento Dashboard 與固定狀態列
Task 7：整體 stack 驗證與文件
```

第一期完成後依總體路線圖繼續：

```text
Durable Task Engine
Agent Protocol／Manager
Knowledge Agent
Coding／Business Analysis Agent
WebChat／Identity Approval
Telegram／Discord／LINE
Projects／Automation／Diary／Registry
Operational Completion
```

## 8. 執行規範

- 每個功能遵循 TDD：RED → GREEN → REFACTOR。
- 每個 Task 使用新的實作代理。
- 實作後先做規格審查，再做品質審查。
- Critical／Important 未清零不得進下一 Task。
- 不並行啟動會修改同一 worktree 的代理。
- 不修改原始 checkout 的未提交文件。
- 完成宣告前必須重新執行驗證命令。

## 9. 恢復執行提示

可使用以下指令恢復：

```text
請依 docs/OPSWEAVE_EXECUTION_HANDOFF.zh-TW.md，
從 feat/opsweave-foundation 的 Task 3 繼續。
使用 subagent-driven-development、TDD、規格審查與品質審查。
```
