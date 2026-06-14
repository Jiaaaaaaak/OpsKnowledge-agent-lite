# Guided Workflows UI/UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build guided Event Insights and Knowledge Q&A workflows with staged loading, run-specific analysis results, and simplified primary navigation.

**Architecture:** Add backend run-result and workflow-status APIs first, then build shared frontend workflow primitives, then compose Event and Knowledge workflow pages. Keep legacy routes available during migration while removing them from the primary sidebar.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React 18, React Router, TypeScript, Tailwind CSS, lucide-react.

---

## Execution Log

2026-06-15:

- Consolidated the pre-existing tracked dirty work on `main` into three commits:
  - `822e504 chore: switch local stack to pgvector and ollama`
  - `2f5c947 feat: move document vectors into pgvector`
  - `de5b227 docs: update pgvector and ollama guidance`
- Pushed `main` to `origin/main`; local `main` and `origin/main` both point to `de5b227`.
- Created the feature branch `guided-workflows-uiux` from the pushed `main`.
- `.superpowers/` remains an untracked local visual-brainstorming cache. It is intentionally not committed or pushed.
- Implementation progress on `guided-workflows-uiux`:
  - Task 1 completed and committed as `63dd727 feat: link analysis outputs to agent runs`.
  - Task 2 completed and committed as `621ae92 feat: 新增工作流程狀態與分析結果 API`. Fixed a test bug where `first in (Document, DocumentChunk)` triggered SQLAlchemy `__eq__` coercion on a `func.count(...)` expression; that branch was dead (the endpoint queries `func.count(Document.id)`, not the bare class) so it was removed. `tests/test_analyze.py tests/test_dashboard.py` pass (49 passed).
  - Note: Rule 13 requires Traditional Chinese commit messages; Task 2 onward uses 繁中 commit subjects even though the plan text and Task 1 used English.
  - Task 3 committed as `3dfeb0c feat: 新增共用工作流程前端元件` (api helpers + 5 shared workflow components; `npm run build` passes).
  - Task 4 committed as `c8ce4aa feat: 新增事件洞察工作流程與分析結果頁` (EventInsightsWorkflowPage, AnalysisResultPage, routes; legacy routes kept).
  - Task 5 committed as `4d1ceed feat: 新增知識庫問答工作流程` (KnowledgeWorkflowPage with embedded RAG chat; legacy routes kept).
  - Task 6 committed as `8bb98d4 feat: 側邊欄改以工作流程為主要導覽`. Spec primary nav lists 5 entries and omits 專案設定; to keep project setup reachable, the persistent project-status box at the sidebar top was made a link to `/projects`. Legacy routes remain available (no redirect), per the approved migration strategy.
  - Task 7 verification: focused backend tests pass (54 passed); full backend suite passes (268 passed); `frontend npm run build` passes. Manual docker-compose smoke test left to the operator since it requires running dev services.

---

## File Structure

Backend:

- Modify `backend/migrations/001_initial_schema.sql`: add nullable `agent_run_id` columns and indexes for `insights` and `action_items`.
- Modify `backend/app/models/analysis.py`: add `agent_run_id` columns and relationships.
- Modify `backend/app/models/agent.py`: add relationships from `AgentRun` to insights/action items.
- Modify `backend/app/services/analysis_service.py`: set `agent_run_id` when creating insights and action items.
- Modify `backend/app/api/dashboard.py`: add response schemas and endpoints for analysis run result and workflow status.
- Modify `backend/app/schemas/analysis.py`: include `agent_run_id` in read/create schemas.
- Modify `backend/tests/test_analyze.py`: verify generated outputs are linked to the run.
- Modify `backend/tests/test_dashboard.py`: test analysis result and workflow status endpoints.

Frontend:

- Modify `frontend/src/services/api.ts`: add `getWorkflowStatus` and `getAnalysisResult`.
- Create `frontend/src/components/workflow/WorkflowStepper.tsx`: shared stepper.
- Create `frontend/src/components/workflow/ProjectRequiredState.tsx`: no-project state.
- Create `frontend/src/components/workflow/UploadPanel.tsx`: reusable upload panel.
- Create `frontend/src/components/workflow/WorkflowStatusPanel.tsx`: status summary.
- Create `frontend/src/components/workflow/AnalysisProgressPanel.tsx`: staged incident analysis progress.
- Create `frontend/src/pages/EventInsightsWorkflowPage.tsx`: event workflow orchestration.
- Create `frontend/src/pages/KnowledgeWorkflowPage.tsx`: RAG workflow orchestration and chat integration.
- Create `frontend/src/pages/AnalysisResultPage.tsx`: run-specific result page.
- Modify `frontend/src/pages/ChatPage.tsx`: optionally reuse a chat surface component or redirect legacy route.
- Modify `frontend/src/App.tsx`: add new routes and legacy redirects.
- Modify `frontend/src/components/layout/Sidebar.tsx`: expose only new primary workflow entries plus dashboard/observability.

---

### Task 1: Backend Schema And Model Links

**Files:**
- Modify: `backend/migrations/001_initial_schema.sql`
- Modify: `backend/app/models/analysis.py`
- Modify: `backend/app/models/agent.py`
- Modify: `backend/app/schemas/analysis.py`

- [ ] **Step 1: Update SQL schema**

In `backend/migrations/001_initial_schema.sql`, add `agent_run_id` to both `insights` and `action_items`:

```sql
agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
```

Add indexes after each table's existing indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_insights_agent_run_id ON insights(agent_run_id);
CREATE INDEX IF NOT EXISTS idx_action_items_agent_run_id ON action_items(agent_run_id);
```

Because `agent_runs` is currently declared after `insights` and `action_items`, move the `agent_runs` table definition before `insights`, or add the new columns with `ALTER TABLE` after `agent_runs` is created. Prefer moving `agent_runs` before `insights` to keep initial schema direct.

- [ ] **Step 2: Update ORM models**

In `backend/app/models/analysis.py`, import `AgentRun` relationship target by string only and add columns:

```python
agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
```

Add table indexes:

```python
Index("idx_insights_agent_run_id", "agent_run_id")
Index("idx_action_items_agent_run_id", "agent_run_id")
```

Add relationships:

```python
agent_run = relationship("AgentRun", back_populates="insights")
agent_run = relationship("AgentRun", back_populates="action_items")
```

In `backend/app/models/agent.py`, add:

```python
insights = relationship("Insight", back_populates="agent_run")
action_items = relationship("ActionItem", back_populates="agent_run")
```

- [ ] **Step 3: Update Pydantic schemas**

In `backend/app/schemas/analysis.py`, add optional `agent_run_id` to `InsightCreate`, `InsightRead`, `ActionItemCreate`, and `ActionItemRead`:

```python
agent_run_id: UUID | None = None
```

- [ ] **Step 4: Run focused schema-adjacent tests**

Run:

```bash
cd backend && pytest tests/test_db_init.py tests/test_schema_metadata.py -q
```

Expected: tests pass, or fail only where they need assertions updated for the new columns.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/001_initial_schema.sql backend/app/models/analysis.py backend/app/models/agent.py backend/app/schemas/analysis.py
git commit -m "feat: link analysis outputs to agent runs"
```

---

### Task 2: Backend Run Result And Workflow Status APIs

**Files:**
- Modify: `backend/app/services/analysis_service.py`
- Modify: `backend/app/api/dashboard.py`
- Modify: `backend/tests/test_analyze.py`
- Modify: `backend/tests/test_dashboard.py`

- [ ] **Step 1: Write analysis service test**

In `backend/tests/test_analyze.py`, extend the orchestrator success test or add a new test that asserts created `Insight` and `ActionItem` rows have the same `agent_run_id` as the returned `agent_run_id`:

```python
assert all(ins.agent_run_id == response.agent_run_id for ins in created_insights)
assert all(item.agent_run_id == response.agent_run_id for item in created_action_items)
```

Use the existing test's added-object inspection pattern. If the existing test uses a real test database, query by `agent_run_id`.

- [ ] **Step 2: Implement run linking**

In `backend/app/services/analysis_service.py`, when adding `Insight`, include:

```python
agent_run_id=agent_run_id,
```

When adding `ActionItem`, include:

```python
agent_run_id=agent_run_id,
```

- [ ] **Step 3: Add API response models**

In `backend/app/api/dashboard.py`, add Pydantic models:

```python
class AnalysisResultRun(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    task_type: str
    model_name: str
    status: str
    latency_ms: int | None
    created_at: Any
    error_message: str | None


class AnalysisResultSummary(BaseModel):
    records_analyzed: int = 0
    needs_review: int = 0
    insights_created: int = 0
    action_items_created: int = 0


class AnalysisRunResultResponse(BaseModel):
    run: AnalysisResultRun
    summary: AnalysisResultSummary
    insights: list[InsightBrief]
    action_items: list[ActionItemBrief]


class EventWorkflowStatus(BaseModel):
    cleaned_ticket_count: int
    analyzed_ticket_count: int
    unanalyzed_ticket_count: int
    latest_run_id: uuid.UUID | None
    latest_run_status: str | None


class KnowledgeWorkflowStatus(BaseModel):
    document_count: int
    total_pages: int
    total_chunks: int
    can_chat: bool


class WorkflowStatusResponse(BaseModel):
    project_id: uuid.UUID
    event: EventWorkflowStatus
    knowledge: KnowledgeWorkflowStatus
```

- [ ] **Step 4: Add result endpoint**

In `backend/app/api/dashboard.py`, add:

```python
@router.get(
    "/agent-runs/{agent_run_id}/analysis-result",
    response_model=AnalysisRunResultResponse,
    summary="Get run-specific incident analysis result",
)
def get_analysis_run_result(agent_run_id: uuid.UUID, db: Session = Depends(get_db)) -> AnalysisRunResultResponse:
    run = db.query(AgentRun).filter(AgentRun.id == agent_run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")

    insights = (
        db.query(Insight)
        .filter(Insight.agent_run_id == agent_run_id)
        .order_by(Insight.created_at.asc())
        .all()
    )
    action_items = (
        db.query(ActionItem)
        .filter(ActionItem.agent_run_id == agent_run_id)
        .order_by(ActionItem.created_at.asc())
        .all()
    )
    output = run.output_json or {}
    return AnalysisRunResultResponse(
        run=AnalysisResultRun(
            id=run.id,
            project_id=run.project_id,
            task_type=run.task_type,
            model_name=run.model_name,
            status=run.status,
            latency_ms=run.latency_ms,
            created_at=run.created_at,
            error_message=run.error_message,
        ),
        summary=AnalysisResultSummary(
            records_analyzed=int(output.get("records_analyzed", 0) or 0),
            needs_review=int(output.get("needs_review", 0) or 0),
            insights_created=int(output.get("insights_created", 0) or 0),
            action_items_created=int(output.get("action_items_created", 0) or 0),
        ),
        insights=[
            InsightBrief(id=i.id, title=i.title, summary=i.summary, recommendation=i.recommendation)
            for i in insights
        ],
        action_items=[
            ActionItemBrief(
                id=a.id,
                title=a.title,
                description=a.description,
                priority=a.priority,
                owner_role=a.owner_role,
                status=a.status,
            )
            for a in action_items
        ],
    )
```

- [ ] **Step 5: Add workflow status endpoint**

In `backend/app/api/dashboard.py`, import `Document` and `DocumentChunk`, then add:

```python
@router.get(
    "/projects/{project_id}/workflow-status",
    response_model=WorkflowStatusResponse,
    summary="Get project workflow readiness status",
)
def get_workflow_status(project_id: uuid.UUID, db: Session = Depends(get_db)) -> WorkflowStatusResponse:
    _project_or_404(db, project_id)

    cleaned_count = db.query(func.count(CleanedRecord.id)).filter(CleanedRecord.project_id == project_id).scalar() or 0
    analyzed_count = db.query(func.count(IncidentAnalysis.id)).filter(IncidentAnalysis.project_id == project_id).scalar() or 0
    latest_run = (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id, AgentRun.task_type == "analyze_incidents")
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    document_count = db.query(func.count(Document.id)).filter(Document.project_id == project_id).scalar() or 0
    page_total = db.query(func.coalesce(func.sum(cast(Document.metadata["page_count"].astext, INTEGER)), 0)).filter(Document.project_id == project_id).scalar() or 0
    chunk_total = (
        db.query(func.count(DocumentChunk.id))
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .scalar()
        or 0
    )

    return WorkflowStatusResponse(
        project_id=project_id,
        event=EventWorkflowStatus(
            cleaned_ticket_count=int(cleaned_count),
            analyzed_ticket_count=int(analyzed_count),
            unanalyzed_ticket_count=max(int(cleaned_count) - int(analyzed_count), 0),
            latest_run_id=latest_run.id if latest_run else None,
            latest_run_status=latest_run.status if latest_run else None,
        ),
        knowledge=KnowledgeWorkflowStatus(
            document_count=int(document_count),
            total_pages=int(page_total),
            total_chunks=int(chunk_total),
            can_chat=int(document_count) > 0 and int(chunk_total) > 0,
        ),
    )
```

If `Document.metadata` does not contain `page_count`, use `Document.page_count` if available in the current branch. Prefer the real field used by `listDocuments`.

- [ ] **Step 6: Write endpoint tests**

In `backend/tests/test_dashboard.py`, add tests for:

```python
def test_analysis_run_result_happy_path(client): ...
def test_analysis_run_result_404(client): ...
def test_workflow_status_happy_path(client): ...
def test_workflow_status_404(client): ...
```

Use the existing mocked query-chain pattern. Assert run-specific result only includes rows with matching `agent_run_id`.

- [ ] **Step 7: Run backend tests**

Run:

```bash
cd backend && pytest tests/test_analyze.py tests/test_dashboard.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/analysis_service.py backend/app/api/dashboard.py backend/tests/test_analyze.py backend/tests/test_dashboard.py
git commit -m "feat: add workflow status and analysis result APIs"
```

---

### Task 3: Frontend API Types And Shared Workflow Components

**Files:**
- Modify: `frontend/src/services/api.ts`
- Create: `frontend/src/components/workflow/WorkflowStepper.tsx`
- Create: `frontend/src/components/workflow/ProjectRequiredState.tsx`
- Create: `frontend/src/components/workflow/UploadPanel.tsx`
- Create: `frontend/src/components/workflow/WorkflowStatusPanel.tsx`
- Create: `frontend/src/components/workflow/AnalysisProgressPanel.tsx`

- [ ] **Step 1: Add API helpers**

In `frontend/src/services/api.ts`, add:

```ts
export const getWorkflowStatus = (projectId: string) =>
  get(`/projects/${projectId}/workflow-status`);

export const getAnalysisResult = (agentRunId: string) =>
  get(`/agent-runs/${agentRunId}/analysis-result`);
```

- [ ] **Step 2: Create `WorkflowStepper`**

Create a compact stepper that accepts:

```ts
export interface WorkflowStep {
  id: string;
  label: string;
  description?: string;
  status: 'complete' | 'current' | 'available' | 'locked';
}
```

Render numbered circles with `CheckCircle2` for complete steps and disabled styling for locked steps. Use buttons for clickable available/current steps.

- [ ] **Step 3: Create `ProjectRequiredState`**

Create a centered state with `ShieldAlert`, explanatory text, and a `Link` to `/projects`.

- [ ] **Step 4: Create `UploadPanel`**

Build a reusable upload component with props:

```ts
interface UploadPanelProps {
  title: string;
  description: string;
  accept: string;
  idleLabel: string;
  loadingLabel: string;
  selectedFileLabel: string;
  onUpload: (file: File) => Promise<any>;
  renderResult?: (result: any) => React.ReactNode;
}
```

Manage local file, loading, result, and error state inside this component.

- [ ] **Step 5: Create `WorkflowStatusPanel`**

Render event and knowledge counts from workflow status with small metric rows. Accept `status: any` initially to match the existing untyped frontend pattern.

- [ ] **Step 6: Create `AnalysisProgressPanel`**

Use `useEffect` with an interval to advance through four fixed stages while `active` is true. Stop estimated progress below 92 until parent reports completion.

- [ ] **Step 7: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/components/workflow
git commit -m "feat: add shared workflow frontend components"
```

---

### Task 4: Event Insights Workflow And Result Page

**Files:**
- Create: `frontend/src/pages/EventInsightsWorkflowPage.tsx`
- Create: `frontend/src/pages/AnalysisResultPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create event workflow page**

Implement `EventInsightsWorkflowPage`:

- Load `getWorkflowStatus(currentProject.id)` when a project is selected.
- Determine active step:
  - no project: project
  - no cleaned tickets: upload
  - unanalyzed tickets > 0: analyze
  - latest run exists: result
  - fallback: upload
- Use `UploadPanel` with `uploadTickets`.
- Use `AnalysisProgressPanel` while calling `analyzeIncidents`.
- On success, navigate to `/analysis/result/${res.agent_run_id}`.
- On no analyzable records, show import-more and latest-result actions.

- [ ] **Step 2: Create analysis result page**

Implement `AnalysisResultPage`:

- Read `agentRunId` with `useParams`.
- Fetch `getAnalysisResult(agentRunId)`.
- Render summary metrics, insight cards, action item table, run metadata, and CTAs.
- Show not-found/error state with CTA to `/insights/workflow`.

- [ ] **Step 3: Add routes**

In `frontend/src/App.tsx`, add:

```tsx
<Route path="insights/workflow" element={<EventInsightsWorkflowPage />} />
<Route path="analysis/result/:agentRunId" element={<AnalysisResultPage />} />
```

Keep existing `/incident-upload` and `/analysis` routes for now.

- [ ] **Step 4: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/EventInsightsWorkflowPage.tsx frontend/src/pages/AnalysisResultPage.tsx frontend/src/App.tsx
git commit -m "feat: add event insights workflow"
```

---

### Task 5: Knowledge Q&A Workflow

**Files:**
- Create: `frontend/src/pages/KnowledgeWorkflowPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create knowledge workflow page**

Implement `KnowledgeWorkflowPage`:

- Load `getWorkflowStatus(currentProject.id)` and `listDocuments(currentProject.id)`.
- Determine active step:
  - no project: project
  - no documents or cannot chat: knowledge
  - documents and chunks exist: ask
- Use `UploadPanel` with `uploadDocument`.
- After upload, refresh workflow status and documents, then move to ask.
- Embed the current chat behavior from `ChatPage`: local draft persistence by project, Top K slider, messages, citations, and submit handler using `chat`.
- Prevent submit when `can_chat` is false.

- [ ] **Step 2: Add route**

In `frontend/src/App.tsx`, add:

```tsx
<Route path="knowledge/workflow" element={<KnowledgeWorkflowPage />} />
```

Keep `/document-upload` and `/chat` for compatibility.

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/KnowledgeWorkflowPage.tsx frontend/src/App.tsx
git commit -m "feat: add knowledge qa workflow"
```

---

### Task 6: Sidebar Navigation And Legacy Route Handling

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Optionally modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update sidebar groups**

Replace the current Flow 1 and Flow 2 entries with:

```ts
{
  title: '工作流程',
  items: [
    { name: '事件洞察流程', to: '/insights/workflow', icon: PlaySquare },
    { name: '知識庫問答流程', to: '/knowledge/workflow', icon: MessageSquare },
  ],
},
{
  title: '結果與可觀測性',
  items: [
    { name: '分析儀表板', to: '/dashboard', icon: LayoutDashboard },
    { name: 'Agent 執行紀錄', to: '/agent-runs', icon: ListTree },
    { name: '系統狀態', to: '/status', icon: Activity },
  ],
}
```

Keep project status visible at the top of the sidebar.

- [ ] **Step 2: Choose legacy route behavior**

For this version, keep old routes available rather than redirecting. This matches the approved migration strategy and avoids breaking deep links while removing old pages from primary navigation.

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx frontend/src/App.tsx
git commit -m "feat: simplify navigation around workflows"
```

---

### Task 7: Full Verification And Cleanup

**Files:**
- Modify only if verification finds issues.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd backend && pytest tests/test_analyze.py tests/test_dashboard.py tests/test_db_init.py tests/test_schema_metadata.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 3: Check git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only files intentionally modified by this plan are staged or unstaged. Existing unrelated dirty files may remain; do not revert them.

- [ ] **Step 4: Manual smoke test if dev services are available**

Run:

```bash
docker compose up -d
```

Then open the frontend and verify:

- `/insights/workflow` renders.
- `/knowledge/workflow` renders.
- Sidebar primary entries point to the two workflows.
- Event analysis success navigates to `/analysis/result/:agentRunId`.
- Knowledge chat displays citations after a successful answer.

- [ ] **Step 5: Commit any verification fixes**

```bash
git add <only-files-fixed-during-verification>
git commit -m "fix: stabilize guided workflow verification"
```

---

## Self-Review

Spec coverage:

- Event guided workflow: Tasks 3, 4, 6.
- Knowledge guided workflow: Tasks 3, 5, 6.
- Staged loading: Tasks 3, 4, 5.
- Run-specific event result page: Tasks 1, 2, 4.
- Workflow status API: Task 2.
- Sidebar simplification: Task 6.
- Legacy route compatibility: Tasks 4, 5, 6.
- Testing and verification: Tasks 2, 4, 5, 6, 7.

Placeholder scan:

- No TBD/TODO placeholders are intentionally left in this plan.

Type consistency:

- Backend endpoint names match frontend API helper names.
- Route `/analysis/result/:agentRunId` matches `getAnalysisResult(agentRunId)`.
- Route `/insights/workflow` matches sidebar and Event workflow.
- Route `/knowledge/workflow` matches sidebar and Knowledge workflow.
