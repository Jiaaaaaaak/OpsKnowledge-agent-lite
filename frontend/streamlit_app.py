"""
OpsKnowledge Agent Lite — Streamlit 前端。

設計原則：
- 一個檔案 + api_client 就跑完全部 demo flow，不引入 multipage routing
- 用 st.session_state 持有 project_id，跨頁不掉
- 後端 URL 由 BACKEND_URL 取（docker-compose 注入 http://backend:8000）
- 所有後端呼叫經 APIError 統一錯誤呈現，UI 不會 traceback
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from api_client import (
    APIError,
    BACKEND_URL,
    analyze_incidents,
    chat,
    create_project,
    get_dashboard,
    list_agent_runs,
    list_projects,
    list_tool_calls,
    upload_document,
    upload_tickets,
)

st.set_page_config(page_title="OpsKnowledge Agent Lite", page_icon="🤖", layout="wide")

PAGES = [
    "Project Setup",
    "Upload",
    "Knowledge Chat",
    "Incident Analysis",
    "Dashboard",
    "Agent Logs",
]


def _safe(fn, *args, **kwargs):
    """跑後端呼叫；失敗回 None 並 st.error。"""
    try:
        return fn(*args, **kwargs)
    except APIError as exc:
        st.error(f"❌ {exc}")
        return None


def _selected_project_id() -> str | None:
    return st.session_state.get("project_id")


def _selected_project_name() -> str:
    return st.session_state.get("project_name", "(none selected)")


def _require_project() -> str | None:
    pid = _selected_project_id()
    if not pid:
        st.warning("請先到 **Project Setup** 建立或選擇一個 project。")
        return None
    return pid


# ── Sidebar ──────────────────────────────────────────────────

with st.sidebar:
    st.title("🤖 OpsKnowledge")
    st.caption("IT Ops AI POC — v0.1.0")
    st.divider()
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("Active project")
    st.code(f"{_selected_project_name()}\n{_selected_project_id() or '-'}", language=None)
    st.caption(f"Backend: `{BACKEND_URL}`")


# ── Page 1: Project Setup ───────────────────────────────────

if page == "Project Setup":
    st.header("Project Setup")
    st.caption("Pick an existing project or create a new one. All other pages operate on the selected project.")

    col_pick, col_new = st.columns(2)

    with col_pick:
        st.subheader("Select existing")
        projects = _safe(list_projects) or []
        if not projects:
            st.info("尚無 project — 在右側建立第一個。")
        else:
            labels = {f"{p['name']}  ·  {p['id'][:8]}…": p for p in projects}
            choice = st.selectbox("Project", list(labels.keys()), index=0, label_visibility="collapsed")
            if st.button("Use this project", type="primary"):
                p = labels[choice]
                st.session_state["project_id"] = p["id"]
                st.session_state["project_name"] = p["name"]
                st.success(f"已選擇 {p['name']}")
                st.rerun()

    with col_new:
        st.subheader("Create new")
        with st.form("create_project"):
            name = st.text_input("Name", placeholder="IT Operations Demo")
            desc = st.text_area("Description (optional)", height=80)
            submit = st.form_submit_button("Create", type="primary")
        if submit:
            if not name.strip():
                st.error("Name 不可為空。")
            else:
                created = _safe(create_project, name.strip(), desc.strip() or None)
                if created:
                    st.session_state["project_id"] = created["id"]
                    st.session_state["project_name"] = created["name"]
                    st.success(f"已建立並選擇 {created['name']}")
                    st.rerun()


# ── Page 2: Upload ──────────────────────────────────────────

elif page == "Upload":
    st.header("Upload")
    project_id = _require_project()
    if project_id:
        tab_docs, tab_tickets = st.tabs(["📄 PDF Documents", "🎫 Incident Tickets"])

        with tab_docs:
            st.caption("PDF 會被切 chunk → embed → 存入 ChromaDB，作為 Knowledge Chat 的 RAG 來源。")
            pdf = st.file_uploader("Choose a PDF", type=["pdf"], key="pdf_uploader")
            if pdf and st.button("Upload PDF", type="primary", key="upload_pdf"):
                with st.spinner("Uploading & embedding..."):
                    result = _safe(upload_document, project_id, pdf.name, pdf.getvalue(), pdf.type or "application/pdf")
                if result:
                    st.success("✅ PDF 已上傳並建立向量索引")
                    st.json(result)

        with tab_tickets:
            st.caption("CSV / Excel / JSON 經 ETL 正規化欄位，寫入 cleaned_records，後續供 Incident Analysis 使用。")
            ticket_file = st.file_uploader(
                "Choose CSV / Excel / JSON", type=["csv", "xlsx", "json"], key="ticket_uploader"
            )
            if ticket_file and st.button("Upload Tickets", type="primary", key="upload_tickets"):
                with st.spinner("Parsing & inserting..."):
                    result = _safe(
                        upload_tickets,
                        project_id,
                        ticket_file.name,
                        ticket_file.getvalue(),
                        ticket_file.type or "application/octet-stream",
                    )
                if result:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Raw rows", result.get("raw_count", 0))
                    c2.metric("Cleaned", result.get("cleaned_count", 0))
                    c3.metric("Failed", result.get("failed_count", 0))
                    if result.get("errors"):
                        with st.expander(f"⚠️ {len(result['errors'])} row(s) failed"):
                            st.dataframe(pd.DataFrame(result["errors"]), use_container_width=True)


# ── Page 3: Knowledge Chat ──────────────────────────────────

elif page == "Knowledge Chat":
    st.header("Knowledge Chat (RAG)")
    project_id = _require_project()
    if project_id:
        st.caption("問題會在 ChromaDB 做向量檢索 → 拿 top-k chunk 組 prompt → LLM 在 context 內回答；所有未進 context 的內容不會被引用。")
        question = st.text_input("Question", placeholder="e.g. Docker volume disappeared after restart — what should I check?")
        top_k = st.slider("top_k (chunks retrieved)", min_value=1, max_value=10, value=5)
        if st.button("Ask", type="primary", disabled=not question.strip()):
            with st.spinner("Retrieving + asking the LLM..."):
                result = _safe(chat, project_id, question.strip(), top_k)
            if result:
                st.subheader("Answer")
                st.write(result.get("answer", "(empty)"))
                citations = result.get("citations", [])
                st.subheader(f"Citations ({len(citations)})")
                if not citations:
                    st.caption("無引用 — 通常代表 context 不足，模型回了標準拒答。")
                for i, c in enumerate(citations, 1):
                    with st.expander(f"[{i}] {c.get('filename', '?')} · chunk {c.get('chunk_index', '?')}"):
                        st.caption(f"document_id: `{c.get('document_id', '')}`  ·  chunk_id: `{c.get('chunk_id', '')}`")
                        st.write(c.get("snippet", ""))


# ── Page 4: Incident Analysis ───────────────────────────────

elif page == "Incident Analysis":
    st.header("Incident Analysis Agent")
    project_id = _require_project()
    if project_id:
        st.caption(
            "啟動 4-tool agent：classify_incidents → analyze_severity → generate_insights → create_action_items。"
            "結果寫入 incident_analysis / insights / action_items；本次執行的 agent_run + 4 個 tool_calls 也會被記錄供 Agent Logs 查詢。"
        )
        if st.button("▶️ Run Incident Analysis", type="primary"):
            with st.spinner("Running agent (4 tools)..."):
                result = _safe(analyze_incidents, project_id)
            if result:
                summary = result.get("summary", {})
                status = result.get("status", "unknown")
                if status == "success":
                    st.success(f"✅ Agent run 完成（{status}）")
                elif status == "partial":
                    st.warning(f"⚠️ Agent run 部分成功（{status}）— 有 tool 驗證失敗，請看 Agent Logs。")
                else:
                    st.error(f"Agent run 狀態：{status}")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Records analyzed", summary.get("records_analyzed", 0))
                c2.metric("Needs review", summary.get("needs_review", 0))
                c3.metric("Insights created", summary.get("insights_created", 0))
                c4.metric("Action items", summary.get("action_items_created", 0))
                st.caption(f"agent_run_id: `{result.get('agent_run_id')}`")


# ── Page 5: Dashboard ───────────────────────────────────────

elif page == "Dashboard":
    st.header("Dashboard")
    project_id = _require_project()
    if project_id:
        data = _safe(get_dashboard, project_id)
        if data:
            c1, c2 = st.columns(2)
            c1.metric("Ticket count", data.get("ticket_count", 0))
            c2.metric("Needs review", data.get("needs_review_count", 0))

            chart_l, chart_r = st.columns(2)
            with chart_l:
                st.subheader("Category distribution")
                cat = data.get("category_distribution", [])
                if cat:
                    df = pd.DataFrame(cat).set_index("category")
                    st.bar_chart(df)
                else:
                    st.caption("(empty — run Incident Analysis first)")
            with chart_r:
                st.subheader("Severity distribution")
                sev = data.get("severity_distribution", [])
                if sev:
                    df = pd.DataFrame(sev).set_index("severity")
                    st.bar_chart(df)
                else:
                    st.caption("(empty — run Incident Analysis first)")

            st.subheader("Top insights")
            insights = data.get("top_insights", [])
            if insights:
                for ins in insights:
                    with st.expander(f"💡 {ins.get('title', '')}"):
                        st.write(ins.get("summary", ""))
                        st.markdown(f"**Recommendation:** {ins.get('recommendation', '')}")
            else:
                st.caption("(none yet)")

            st.subheader("Open action items")
            items = data.get("open_action_items", [])
            if items:
                df = pd.DataFrame(items)[["title", "priority", "owner_role", "status", "description"]]
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.caption("(none yet)")

            st.subheader("Recent agent runs")
            runs = data.get("recent_agent_runs", [])
            if runs:
                df = pd.DataFrame(runs)[["created_at", "task_type", "model_name", "status", "latency_ms"]]
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.caption("(none yet)")


# ── Page 6: Agent Logs ──────────────────────────────────────

elif page == "Agent Logs":
    st.header("Agent Logs")
    project_id = _require_project()
    if project_id:
        st.caption("所有 agent_runs（chat / analyze_incidents 都會留紀錄）。選一筆 run 看它呼叫了哪些 tool。")
        runs = _safe(list_agent_runs, project_id, 50) or []
        if not runs:
            st.info("尚無 agent run — 試試 Knowledge Chat 或 Incident Analysis。")
        else:
            run_summary_df = pd.DataFrame(
                [
                    {
                        "created_at": r["created_at"],
                        "task_type": r["task_type"],
                        "model": r["model_name"],
                        "status": r["status"],
                        "latency_ms": r["latency_ms"],
                        "id": r["id"],
                    }
                    for r in runs
                ]
            )
            st.dataframe(run_summary_df, use_container_width=True, hide_index=True)

            labels = {f"{r['created_at']}  ·  {r['task_type']}  ·  {r['status']}  ·  {r['id'][:8]}…": r for r in runs}
            choice = st.selectbox("Drill into a run", list(labels.keys()))
            run = labels[choice]

            c1, c2, c3 = st.columns(3)
            c1.metric("Status", run["status"])
            c2.metric("Latency (ms)", run["latency_ms"] or 0)
            c3.metric("Model", run["model_name"])
            if run.get("error_message"):
                st.error(f"error_message: {run['error_message']}")
            with st.expander("input_json"):
                st.json(run.get("input_json", {}))
            with st.expander("output_json"):
                st.json(run.get("output_json", {}))

            st.subheader("Tool calls (execution order)")
            tool_calls = _safe(list_tool_calls, run["id"]) or []
            if not tool_calls:
                st.caption("(no tool calls — this run did not invoke any tool)")
            else:
                for tc in tool_calls:
                    badge = "🟢" if not tc.get("error_message") else "🔴"
                    with st.expander(f"{badge} {tc['tool_name']}  ·  {tc.get('latency_ms') or 0} ms"):
                        if tc.get("error_message"):
                            st.error(tc["error_message"])
                        col_in, col_out = st.columns(2)
                        with col_in:
                            st.caption("input_json")
                            st.json(tc.get("input_json", {}))
                        with col_out:
                            st.caption("output_json")
                            st.json(tc.get("output_json", {}))
