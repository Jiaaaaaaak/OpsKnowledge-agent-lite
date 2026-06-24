# RAG-Focused Interview Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reposition OpsKnowledge Agent Lite as a focused interview demo for IT document RAG, with incident analysis removed from the main product story.

**Architecture:** Implement this in two phases. Phase 1 is the recommended interview-safe path: remove incident analysis from primary UI, demo docs, and workflow status while preserving backend code so existing data and tests are not destabilized. Phase 2 is optional cleanup after the demo path is stable: remove incident ETL and analysis endpoints, models, schemas, tests, and database tables.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, FastAPI, SQLAlchemy, PostgreSQL + pgvector, pytest, Vitest.

---

## Scope Decision

Use Phase 1 for the next demo branch. It gives a clean RAG-first narrative without a high-risk backend/schema removal.

Defer Phase 2 until after Phase 1 is merged and verified. Phase 2 is intentionally separate because it touches migrations, test fixtures, dashboard APIs, and sample data.

## File Structure

Phase 1 files:

- Modify `frontend/src/components/layout/Sidebar.tsx`: remove incident workflow and analysis dashboard entries from primary navigation.
- Modify `frontend/src/App.tsx`: redirect legacy incident routes to the RAG workflow or keep them unlinked during the transition.
- Modify `frontend/src/pages/ProjectPage.tsx`: change the selected-project CTA from incident upload to knowledge workflow.
- Modify `frontend/src/components/layout/Header.tsx`: remove incident-first page descriptions from visible product story.
- Modify `frontend/src/services/api.ts`: stop exposing incident-only client helpers used only by removed primary UI.
- Modify `backend/app/api/dashboard.py`: simplify `workflow-status` response to knowledge readiness for RAG-first frontend use.
- Modify `frontend/src/pages/KnowledgeWorkflowPage.test.tsx`: update mocks if `event` is removed from workflow status.
- Modify `backend/tests/test_dashboard.py`: update workflow-status expectations.
- Modify `README.md`, `README.zh-TW.md`, `docs/PRD.md`, `docs/PRD.zh-TW.md`, `docs/ARCHITECTURE.md`, `docs/ARCHITECTURE.zh-TW.md`, `docs/DEMO_SCRIPT.md`, `docs/DEMO_SCRIPT.zh-TW.md`: rewrite product story around RAG.

Phase 2 optional files:

- Delete `backend/app/api/analyze.py`.
- Delete `backend/app/services/analysis_service.py`.
- Delete `backend/app/services/analysis_constants.py`.
- Delete `backend/app/services/etl_service.py`.
- Delete `backend/app/tools/incident_analysis.py`.
- Delete `backend/app/models/analysis.py`.
- Delete `backend/app/models/record.py`.
- Delete `backend/app/schemas/analysis.py`.
- Delete `backend/app/schemas/record.py`.
- Delete incident frontend pages: `IncidentUploadPage.tsx`, `AnalysisPage.tsx`, `EventInsightsWorkflowPage.tsx`, `AnalysisResultPage.tsx`, `DashboardPage.tsx`.
- Delete incident tests: `backend/tests/test_analyze.py`, `backend/tests/test_etl.py`, `backend/tests/test_audit_gaps.py`, `frontend/src/pages/EventInsightsWorkflowPage.test.tsx`, `frontend/src/pages/AnalysisResultPage.test.tsx`.
- Replace `backend/migrations/001_initial_schema.sql` with a RAG-only schema after deciding whether existing local volumes can be reset.

---

## Phase 1: RAG-First Product Surface

### Task 1: Update Primary Navigation

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Write the failing expectation manually**

Run the frontend tests after changing no code:

```bash
cd frontend
npm test -- --run
```

Expected before the task: existing tests pass, but there is no assertion for the RAG-only sidebar.

- [ ] **Step 2: Modify sidebar nav groups**

Change the imports to remove unused incident/dashboard icons:

```tsx
import { Activity, BookOpen, MessageSquare, ListTree } from 'lucide-react';
```

Replace `navGroups` with:

```tsx
const navGroups = [
  {
    title: '主要流程',
    items: [
      { name: '知識庫問答流程', to: '/knowledge/workflow', icon: MessageSquare },
    ],
  },
  {
    title: '可觀測性',
    items: [
      { name: 'Agent 執行紀錄', to: '/agent-runs', icon: ListTree },
      { name: '系統狀態', to: '/status', icon: Activity },
    ],
  },
];
```

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend
npm test -- --run
```

Expected: tests pass, with no TypeScript errors from removed imports.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx
git commit -m "feat: focus navigation on RAG workflow"
```

### Task 2: Route Legacy Incident Pages Away From Main Demo

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace incident route imports**

Remove these imports:

```tsx
import DashboardPage from './pages/DashboardPage';
import IncidentUploadPage from './pages/IncidentUploadPage';
import AnalysisPage from './pages/AnalysisPage';
import EventInsightsWorkflowPage from './pages/EventInsightsWorkflowPage';
import AnalysisResultPage from './pages/AnalysisResultPage';
```

- [ ] **Step 2: Redirect legacy incident routes**

Replace these routes:

```tsx
<Route path="dashboard" element={<DashboardPage />} />
<Route path="incident-upload" element={<IncidentUploadPage />} />
<Route path="analysis" element={<AnalysisPage />} />
<Route path="insights/workflow" element={<EventInsightsWorkflowPage />} />
<Route path="analysis/result/:agentRunId" element={<AnalysisResultPage />} />
```

with:

```tsx
<Route path="dashboard" element={<Navigate to="/knowledge/workflow" replace />} />
<Route path="incident-upload" element={<Navigate to="/knowledge/workflow" replace />} />
<Route path="analysis" element={<Navigate to="/knowledge/workflow" replace />} />
<Route path="insights/workflow" element={<Navigate to="/knowledge/workflow" replace />} />
<Route path="analysis/result/:agentRunId" element={<Navigate to="/knowledge/workflow" replace />} />
```

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend
npm test -- --run
```

Expected: tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: redirect incident routes to RAG workflow"
```

### Task 3: Make Project Selection Lead To RAG

**Files:**
- Modify: `frontend/src/pages/ProjectPage.tsx`

- [ ] **Step 1: Change selected-project CTA route and label**

Replace:

```tsx
navigate('/incident-upload');
```

with:

```tsx
navigate('/knowledge/workflow');
```

Replace:

```tsx
下一步：匯入事件紀錄
```

with:

```tsx
下一步：建立知識庫
```

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend
npm test -- --run
```

Expected: tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectPage.tsx
git commit -m "feat: start projects in knowledge workflow"
```

### Task 4: Simplify Header Copy

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`

- [ ] **Step 1: Keep RAG, observability, and system status page descriptions**

Keep descriptions for:

```tsx
'/projects'
'/document-upload'
'/chat'
'/knowledge/workflow'
'/agent-runs'
'/status'
```

Map legacy incident paths to RAG-first neutral copy:

```tsx
'/dashboard': { title: '知識庫問答流程', description: '上傳技術文件、建立向量索引，並使用 RAG 取得附引用來源的回答。' },
'/incident-upload': { title: '知識庫問答流程', description: '上傳技術文件、建立向量索引，並使用 RAG 取得附引用來源的回答。' },
'/analysis': { title: '知識庫問答流程', description: '上傳技術文件、建立向量索引，並使用 RAG 取得附引用來源的回答。' },
'/insights/workflow': { title: '知識庫問答流程', description: '上傳技術文件、建立向量索引，並使用 RAG 取得附引用來源的回答。' },
```

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend
npm test -- --run
```

Expected: tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/Header.tsx
git commit -m "feat: align header copy with RAG demo"
```

### Task 5: Simplify Workflow Status API

**Files:**
- Modify: `backend/app/api/dashboard.py`
- Modify: `backend/tests/test_dashboard.py`
- Modify: `frontend/src/pages/KnowledgeWorkflowPage.test.tsx`

- [ ] **Step 1: Update backend test expectations**

In `backend/tests/test_dashboard.py`, update workflow status assertions to expect only:

```python
assert payload["project_id"] == str(project.id)
assert payload["knowledge"]["document_count"] == 0
assert payload["knowledge"]["total_pages"] == 0
assert payload["knowledge"]["total_chunks"] == 0
assert payload["knowledge"]["can_chat"] is False
assert "event" not in payload
```

- [ ] **Step 2: Remove event status models and queries**

In `backend/app/api/dashboard.py`, remove:

```python
class EventWorkflowStatus(BaseModel):
    cleaned_ticket_count: int
    analyzed_ticket_count: int
    unanalyzed_ticket_count: int
    latest_run_id: uuid.UUID | None
    latest_run_status: str | None
```

Change `WorkflowStatusResponse` to:

```python
class WorkflowStatusResponse(BaseModel):
    project_id: uuid.UUID
    knowledge: KnowledgeWorkflowStatus
```

In `get_workflow_status`, delete the `cleaned_count`, `analyzed_count`, and `latest_run` queries. Return:

```python
return WorkflowStatusResponse(
    project_id=project_id,
    knowledge=KnowledgeWorkflowStatus(
        document_count=int(document_count),
        total_pages=int(page_total),
        total_chunks=int(chunk_total),
        can_chat=int(document_count) > 0 and int(chunk_total) > 0,
    ),
)
```

- [ ] **Step 3: Update frontend workflow test mock**

In `frontend/src/pages/KnowledgeWorkflowPage.test.tsx`, change:

```tsx
return {
  project_id: 'p1',
  event: {},
  knowledge: { document_count: 0, total_pages: 0, total_chunks: 0, can_chat: false, ...knowledge },
};
```

to:

```tsx
return {
  project_id: 'p1',
  knowledge: { document_count: 0, total_pages: 0, total_chunks: 0, can_chat: false, ...knowledge },
};
```

- [ ] **Step 4: Run backend and frontend targeted tests**

```bash
cd backend
PYTHONPATH=. pytest tests/test_dashboard.py -v
```

Expected: dashboard tests pass.

```bash
cd frontend
npm test -- --run src/pages/KnowledgeWorkflowPage.test.tsx
```

Expected: knowledge workflow tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/dashboard.py backend/tests/test_dashboard.py frontend/src/pages/KnowledgeWorkflowPage.test.tsx
git commit -m "feat: simplify workflow status for RAG demo"
```

### Task 6: Remove Incident Client Helpers From Main API Surface

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Remove exports used only by incident pages**

Remove:

```ts
export const uploadTickets = (projectId: string, file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return post(`/projects/${projectId}/upload/tickets`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  });
};

export const analyzeIncidents = (projectId: string) => 
  post(`/projects/${projectId}/analyze/incidents`, null, { timeout: 600000 });

export const getDashboard = (projectId: string) => 
  get(`/projects/${projectId}/dashboard`);

export const getAnalysisResult = (agentRunId: string) =>
  get(`/agent-runs/${agentRunId}/analysis-result`);
```

Keep `listAgentRuns` and `listToolCalls` because RAG chat writes `agent_runs` and `tool_calls`.

- [ ] **Step 2: Run TypeScript build**

```bash
cd frontend
npm run build
```

Expected: build passes. If deleted incident page files still import removed helpers, either keep the helpers until Phase 2 or delete/redirect those pages in the same commit. For Phase 1, prefer keeping helpers if TypeScript includes all page files in compilation.

- [ ] **Step 3: Commit only if build passes**

```bash
git add frontend/src/services/api.ts
git commit -m "chore: hide incident helpers from RAG UI"
```

### Task 7: Rewrite Demo Documentation Around RAG

**Files:**
- Modify: `README.md`
- Modify: `README.zh-TW.md`
- Modify: `docs/PRD.md`
- Modify: `docs/PRD.zh-TW.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ARCHITECTURE.zh-TW.md`
- Modify: `docs/DEMO_SCRIPT.md`
- Modify: `docs/DEMO_SCRIPT.zh-TW.md`

- [ ] **Step 1: Rewrite product positioning**

Use this concise positioning in English docs:

```md
OpsKnowledge Agent Lite is an interview-ready RAG knowledge base for IT operations documents. It ingests PDF SOPs and manuals, chunks and embeds them into PostgreSQL + pgvector, answers operational questions with citations, and records AI runs for auditability.
```

Use this concise positioning in Traditional Chinese docs:

```md
OpsKnowledge Agent Lite 是一個面向 IT 維運文件的面試展示型 RAG 知識庫系統。它能匯入 PDF SOP 與技術手冊，切塊並嵌入 PostgreSQL + pgvector，透過附引用來源的 RAG 回答維運問題，並記錄 AI 執行過程以利稽核。
```

- [ ] **Step 2: Remove incident analysis from MVP and success criteria**

Remove references to:

```text
incident ETL
ticket upload
incident classification
severity scoring
insights
action items
analysis dashboard
```

Keep references to:

```text
PDF ingestion
chunking
embedding
semantic search
RAG chat
citations
agent_runs
tool_calls
Docker Compose
mock / Ollama / OpenAI providers
```

- [ ] **Step 3: Update demo route**

Use this demo flow:

```text
1. Create or select a project.
2. Upload sample SOP PDFs or generated demo PDFs.
3. Confirm document count, pages, and chunks.
4. Ask an operational question in the RAG chat.
5. Inspect citations.
6. Open Agent Runs and Tool Calls to show retrieval observability.
7. Explain provider switchability: mock, Ollama, OpenAI-compatible.
```

- [ ] **Step 4: Run documentation grep**

```bash
rg -n "incident|ticket|severity|insight|action item|事件|工單|嚴重度|洞察|行動項目" README.md README.zh-TW.md docs
```

Expected: matches remain only in archived historical plans/specs under `docs/superpowers/` or in clearly marked optional/future-work sections.

- [ ] **Step 5: Commit**

```bash
git add README.md README.zh-TW.md docs/PRD.md docs/PRD.zh-TW.md docs/ARCHITECTURE.md docs/ARCHITECTURE.zh-TW.md docs/DEMO_SCRIPT.md docs/DEMO_SCRIPT.zh-TW.md
git commit -m "docs: reposition project as RAG interview demo"
```

### Task 8: Final Phase 1 Verification

**Files:**
- No source edits unless verification exposes failures.

- [ ] **Step 1: Run backend tests**

```bash
cd backend
PYTHONPATH=. pytest tests/test_documents_api.py tests/test_document_service.py tests/test_vector_store.py tests/test_chat.py tests/test_dashboard.py -v
```

Expected: all selected RAG and observability tests pass.

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend
npm test -- --run
```

Expected: all frontend tests pass, or incident-only tests are deleted/updated in Phase 2 if they no longer match product scope.

- [ ] **Step 3: Run frontend build**

```bash
cd frontend
npm run build
```

Expected: build passes.

- [ ] **Step 4: Commit verification fixes if any**

```bash
git add <changed-files>
git commit -m "test: align RAG demo verification"
```

Only run this commit step if verification required source or test changes.

---

## Phase 2: Optional Physical Removal

Do this only after Phase 1 is stable and you no longer need legacy incident data.

### Task 9: Remove Incident Backend Routers And Services

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/uploads.py`
- Delete: `backend/app/api/analyze.py`
- Delete: `backend/app/services/analysis_service.py`
- Delete: `backend/app/services/analysis_constants.py`
- Delete: `backend/app/services/etl_service.py`
- Delete: `backend/app/tools/incident_analysis.py`

- [ ] **Step 1: Remove analyze router from app startup**

In `backend/app/main.py`, remove:

```python
from app.api.analyze import router as analyze_router
```

and:

```python
app.include_router(analyze_router)
```

- [ ] **Step 2: Remove ticket upload endpoint**

In `backend/app/api/uploads.py`, either delete the file if no endpoints remain or remove the `/upload/tickets` endpoint and its imports.

- [ ] **Step 3: Delete incident service files**

```bash
git rm backend/app/api/analyze.py backend/app/services/analysis_service.py backend/app/services/analysis_constants.py backend/app/services/etl_service.py backend/app/tools/incident_analysis.py
```

- [ ] **Step 4: Run backend import check**

```bash
cd backend
PYTHONPATH=. python -m compileall app
```

Expected: no imports reference deleted incident modules.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/api/uploads.py
git commit -m "refactor: remove incident analysis backend services"
```

### Task 10: Remove Incident Models, Schemas, Tests, And Demo Data

**Files:**
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/__init__.py`
- Delete: `backend/app/models/analysis.py`
- Delete: `backend/app/models/record.py`
- Delete: `backend/app/schemas/analysis.py`
- Delete: `backend/app/schemas/record.py`
- Delete: `backend/tests/test_analyze.py`
- Delete: `backend/tests/test_etl.py`
- Delete: `backend/tests/test_audit_gaps.py`
- Delete: `demo_data/tickets/sample_incidents.csv`
- Delete: `demo_data/tickets/sample_incidents.json`
- Delete: `demo_data/tickets/sample_incidents_messy_columns.csv`

- [ ] **Step 1: Remove model and schema exports**

Delete imports for analysis and record models/schemas from package `__init__.py` files.

- [ ] **Step 2: Delete files**

```bash
git rm backend/app/models/analysis.py backend/app/models/record.py backend/app/schemas/analysis.py backend/app/schemas/record.py backend/tests/test_analyze.py backend/tests/test_etl.py backend/tests/test_audit_gaps.py demo_data/tickets/sample_incidents.csv demo_data/tickets/sample_incidents.json demo_data/tickets/sample_incidents_messy_columns.csv
```

- [ ] **Step 3: Run backend tests**

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

Expected: remaining backend tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/__init__.py backend/app/schemas/__init__.py
git commit -m "refactor: remove incident data model surface"
```

### Task 11: Remove Incident Frontend Pages And Tests

**Files:**
- Modify: `frontend/src/App.tsx`
- Delete: `frontend/src/pages/IncidentUploadPage.tsx`
- Delete: `frontend/src/pages/AnalysisPage.tsx`
- Delete: `frontend/src/pages/EventInsightsWorkflowPage.tsx`
- Delete: `frontend/src/pages/AnalysisResultPage.tsx`
- Delete: `frontend/src/pages/DashboardPage.tsx`
- Delete: `frontend/src/pages/EventInsightsWorkflowPage.test.tsx`
- Delete: `frontend/src/pages/AnalysisResultPage.test.tsx`

- [ ] **Step 1: Remove legacy redirects if no longer needed**

In `frontend/src/App.tsx`, keep only RAG and observability routes:

```tsx
<Route path="projects" element={<ProjectPage />} />
<Route path="document-upload" element={<DocumentUploadPage />} />
<Route path="chat" element={<ChatPage />} />
<Route path="knowledge/workflow" element={<KnowledgeWorkflowPage />} />
<Route path="agent-runs" element={<AgentRunsPage />} />
<Route path="status" element={<SystemStatusPage />} />
```

- [ ] **Step 2: Delete incident pages**

```bash
git rm frontend/src/pages/IncidentUploadPage.tsx frontend/src/pages/AnalysisPage.tsx frontend/src/pages/EventInsightsWorkflowPage.tsx frontend/src/pages/AnalysisResultPage.tsx frontend/src/pages/DashboardPage.tsx frontend/src/pages/EventInsightsWorkflowPage.test.tsx frontend/src/pages/AnalysisResultPage.test.tsx
```

- [ ] **Step 3: Run frontend tests and build**

```bash
cd frontend
npm test -- --run
npm run build
```

Expected: tests and build pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "refactor: remove incident frontend pages"
```

### Task 12: Replace Initial Schema With RAG-Only Schema

**Files:**
- Modify: `backend/migrations/001_initial_schema.sql`
- Modify: `backend/app/db/session.py`
- Modify: `backend/tests/test_db_init.py`

- [ ] **Step 1: Confirm destructive local volume policy**

Before this task, decide that existing local PostgreSQL volumes can be recreated. This project does not currently include a migration runner for destructive table removal.

- [ ] **Step 2: Remove incident tables from initial schema**

Remove table definitions and indexes for:

```sql
raw_records
cleaned_records
incident_analysis
insights
action_items
```

Keep:

```sql
projects
documents
document_chunks
agent_runs
tool_calls
```

- [ ] **Step 3: Remove additive repair helpers for analysis schema**

In `backend/app/db/session.py`, remove analysis-specific repair code if it only exists for `insights`, `action_items`, or incident output relationships.

- [ ] **Step 4: Run database initialization tests**

```bash
cd backend
PYTHONPATH=. pytest tests/test_db_init.py tests/test_schema_metadata.py -v
```

Expected: tests pass with RAG-only schema expectations.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/001_initial_schema.sql backend/app/db/session.py backend/tests/test_db_init.py backend/tests/test_schema_metadata.py
git commit -m "refactor: reduce schema to RAG core"
```

---

## Final Recommendation

Implement Phase 1 now. It is the best fit for an interview demo because it gives a crisp product narrative while preserving the working backend in case a reviewer asks about extensibility.

Treat Phase 2 as a cleanup branch after the demo path has passed. If time is short, do not start Phase 2 before the interview.
