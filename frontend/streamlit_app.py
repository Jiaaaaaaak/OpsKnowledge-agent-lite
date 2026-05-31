"""
OpsKnowledge Agent Lite — Streamlit 前端。

設計原則：
- 一個檔案 + api_client 就跑完全部 demo flow，不引入 multipage routing
- 用 st.session_state 持有 project_id，跨頁不掉
- 後端 URL 由 BACKEND_URL 取（docker-compose 注入 http://backend:8000）
- 所有後端呼叫經 APIError 統一錯誤呈現，UI 不會 traceback

注意：本檔僅含前端 UI 文字。所有後端 API 路徑、request / response 欄位名、
Python identifier（函式 / 變數 / 類別 / 模組）一律保持英文，與後端 schema 對齊。
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

st.set_page_config(page_title="OpsKnowledge Agent Lite — IT 維運知識代理", page_icon="🤖", layout="wide")

# 頁面名稱：使用繁體中文標籤；page 變數用此字串做 dispatch
PAGES = [
    "專案設定",
    "資料上傳",
    "知識庫問答",
    "事件分析",
    "儀表板",
    "Agent 執行紀錄",
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
    return st.session_state.get("project_name", "（尚未選擇）")


def _require_project() -> str | None:
    pid = _selected_project_id()
    if not pid:
        st.warning("請先到 **專案設定** 建立或選擇一個專案。")
        return None
    return pid


# ── Sidebar ──────────────────────────────────────────────────

with st.sidebar:
    st.title("OpsKnowledge")
    st.caption("IT 維運 AI POC — v0.1.0")
    st.caption(
        "本作品為**企業 IT 維運知識檢索與事件分析**的個人作品集 POC："
        "整合 RAG 文件問答、ETL 事件正規化、Agent 多工具事件分析與可觀測性紀錄。"
    )
    st.divider()
    page = st.radio("導覽", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("目前專案")
    st.code(f"{_selected_project_name()}\n{_selected_project_id() or '-'}", language=None)
    st.caption(f"後端：`{BACKEND_URL}`")


# ── Page 1: 專案設定 ────────────────────────────────────────

if page == "專案設定":
    st.header("專案設定")
    st.caption("選擇既有專案或建立新專案。其他頁面都會以目前選擇的專案為操作對象。")

    col_pick, col_new = st.columns(2)

    with col_pick:
        st.subheader("選擇既有專案")
        projects = _safe(list_projects) or []
        if not projects:
            st.info("尚無專案 — 請在右側建立第一個。")
        else:
            labels = {f"{p['name']}  ·  {p['id'][:8]}…": p for p in projects}
            choice = st.selectbox("專案", list(labels.keys()), index=0, label_visibility="collapsed")
            if st.button("使用此專案", type="primary"):
                p = labels[choice]
                st.session_state["project_id"] = p["id"]
                st.session_state["project_name"] = p["name"]
                st.success(f"已選擇 {p['name']}")
                st.rerun()

    with col_new:
        st.subheader("建立新專案")
        with st.form("create_project"):
            name = st.text_input("名稱", placeholder="例如：IT 維運示範專案")
            desc = st.text_area("描述（選填）", height=80)
            submit = st.form_submit_button("建立", type="primary")
        if submit:
            if not name.strip():
                st.error("名稱不可為空。")
            else:
                created = _safe(create_project, name.strip(), desc.strip() or None)
                if created:
                    st.session_state["project_id"] = created["id"]
                    st.session_state["project_name"] = created["name"]
                    st.success(f"已建立並選擇 {created['name']}")
                    st.rerun()


# ── Page 2: 資料上傳 ────────────────────────────────────────

elif page == "資料上傳":
    st.header("資料上傳")
    project_id = _require_project()
    if project_id:
        tab_docs, tab_tickets = st.tabs(["📄 技術文件 PDF", "🎫 事件紀錄檔"])

        with tab_docs:
            st.caption("PDF 會被切 chunk → embed → 存入 ChromaDB，作為「知識庫問答」的 RAG 來源。")
            pdf = st.file_uploader("選擇 PDF 檔", type=["pdf"], key="pdf_uploader")
            if pdf and st.button("上傳技術文件 PDF", type="primary", key="upload_pdf"):
                with st.spinner("上傳中並建立向量索引…"):
                    result = _safe(upload_document, project_id, pdf.name, pdf.getvalue(), pdf.type or "application/pdf")
                if result:
                    st.success("✅ PDF 已上傳並建立向量索引")
                    st.json(result)

        with tab_tickets:
            st.caption("CSV / Excel / JSON 經 ETL 正規化欄位，寫入 cleaned_records，後續供「事件分析」使用。")
            ticket_file = st.file_uploader(
                "選擇 CSV / Excel / JSON 檔", type=["csv", "xlsx", "json"], key="ticket_uploader"
            )
            if ticket_file and st.button("上傳事件紀錄檔", type="primary", key="upload_tickets"):
                with st.spinner("解析與寫入中…"):
                    result = _safe(
                        upload_tickets,
                        project_id,
                        ticket_file.name,
                        ticket_file.getvalue(),
                        ticket_file.type or "application/octet-stream",
                    )
                if result:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("原始列數", result.get("raw_count", 0))
                    c2.metric("清理後筆數", result.get("cleaned_count", 0))
                    c3.metric("失敗筆數", result.get("failed_count", 0))
                    if result.get("errors"):
                        with st.expander(f"⚠️ 共 {len(result['errors'])} 筆驗證失敗"):
                            st.dataframe(pd.DataFrame(result["errors"]), use_container_width=True)


# ── Page 3: 知識庫問答 ──────────────────────────────────────

elif page == "知識庫問答":
    st.header("知識庫問答（RAG）")
    project_id = _require_project()
    if project_id:
        st.caption(
            "問題會在 ChromaDB 做向量檢索 → 取 top-k chunk 組 prompt → "
            "LLM 僅就 context 內容回答；未進 context 的內容不會被引用。"
        )
        question = st.text_input("輸入問題", placeholder="例如：Docker volume 重啟後消失，該檢查哪些設定？")
        top_k = st.slider("top_k（擷取的 chunk 數）", min_value=1, max_value=10, value=5)
        if st.button("送出問題", type="primary", disabled=not question.strip()):
            with st.spinner("向量檢索並呼叫 LLM 中…"):
                result = _safe(chat, project_id, question.strip(), top_k)
            if result:
                st.subheader("回答")
                st.write(result.get("answer", "（空）"))
                citations = result.get("citations", [])
                st.subheader(f"引用來源（{len(citations)}）")
                if not citations:
                    st.caption("無引用 — 通常代表 context 不足，模型回了標準拒答措辭。")
                for i, c in enumerate(citations, 1):
                    with st.expander(f"[{i}] {c.get('filename', '?')} · chunk {c.get('chunk_index', '?')}"):
                        st.caption(f"document_id：`{c.get('document_id', '')}`  ·  chunk_id：`{c.get('chunk_id', '')}`")
                        st.write(c.get("snippet", ""))


# ── Page 4: 事件分析 ────────────────────────────────────────

elif page == "事件分析":
    st.header("事件分析 Agent")
    project_id = _require_project()
    if project_id:
        st.caption(
            "啟動 4-tool agent：classify_incidents → analyze_severity → "
            "generate_insights → create_action_items。"
            "結果寫入 incident_analysis / insights / action_items；本次執行的 "
            "agent_run 與 4 筆 tool_calls 也會被記錄，可在「Agent 執行紀錄」頁面回查。"
        )
        if st.button("▶️ 執行事件分析", type="primary"):
            result = None
            with st.spinner("Agent 執行中（4 個工具依序呼叫）…"):
                try:
                    result = analyze_incidents(project_id)
                except APIError as exc:
                    # 400 是 endpoint 的 idempotent 保護（沒可分析的事件）— 對 demo
                    # 觀眾來說「紅字 + 英文 detail」太唬人，改成黃色提示與具體下一步
                    if exc.status_code == 400:
                        st.warning(
                            "目前沒有可分析的事件 — 請先到「資料上傳」分頁上傳事件紀錄檔"
                            "（CSV / Excel / JSON），或此專案的事件已全部分析過。"
                        )
                    else:
                        st.error(f"❌ {exc}")
            if result:
                summary = result.get("summary", {})
                status = result.get("status", "unknown")
                if status == "success":
                    st.success(f"✅ Agent 執行完成（{status}）")
                elif status == "partial":
                    st.warning(
                        f"⚠️ Agent 部分成功（{status}）— 有工具驗證失敗，"
                        "請至「Agent 執行紀錄」頁面查看。"
                    )
                else:
                    st.error(f"Agent 執行狀態：{status}")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("已分析筆數", summary.get("records_analyzed", 0))
                c2.metric("需要人工複核", summary.get("needs_review", 0))
                c3.metric("產生洞察數", summary.get("insights_created", 0))
                c4.metric("行動項目數", summary.get("action_items_created", 0))
                st.caption(f"agent_run_id：`{result.get('agent_run_id')}`")


# ── Page 5: 儀表板 ──────────────────────────────────────────

elif page == "儀表板":
    st.header("儀表板")
    project_id = _require_project()
    if project_id:
        data = _safe(get_dashboard, project_id)
        if data:
            c1, c2 = st.columns(2)
            c1.metric("工單總數", data.get("ticket_count", 0))
            c2.metric("需要人工複核", data.get("needs_review_count", 0))

            chart_l, chart_r = st.columns(2)
            with chart_l:
                st.subheader("類別分布")
                cat = data.get("category_distribution", [])
                if cat:
                    df = pd.DataFrame(cat).set_index("category")
                    st.bar_chart(df)
                else:
                    st.caption("（尚無資料 — 請先執行「事件分析」）")
            with chart_r:
                st.subheader("嚴重程度分布")
                sev = data.get("severity_distribution", [])
                if sev:
                    df = pd.DataFrame(sev).set_index("severity")
                    st.bar_chart(df)
                else:
                    st.caption("（尚無資料 — 請先執行「事件分析」）")

            st.subheader("重點洞察")
            insights = data.get("top_insights", [])
            if insights:
                for ins in insights:
                    with st.expander(f"💡 {ins.get('title', '')}"):
                        st.write(ins.get("summary", ""))
                        st.markdown(f"**建議行動：** {ins.get('recommendation', '')}")
            else:
                st.caption("（尚無資料）")

            st.subheader("未處理行動項目")
            items = data.get("open_action_items", [])
            if items:
                df = (
                    pd.DataFrame(items)[["title", "priority", "owner_role", "status", "description"]]
                    .rename(
                        columns={
                            "title": "標題",
                            "priority": "優先度",
                            "owner_role": "負責角色",
                            "status": "狀態",
                            "description": "說明",
                        }
                    )
                )
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.caption("（尚無資料）")

            st.subheader("最近 Agent 執行紀錄")
            runs = data.get("recent_agent_runs", [])
            if runs:
                df = (
                    pd.DataFrame(runs)[["created_at", "task_type", "model_name", "status", "latency_ms"]]
                    .rename(
                        columns={
                            "created_at": "建立時間",
                            "task_type": "任務類型",
                            "model_name": "模型",
                            "status": "狀態",
                            "latency_ms": "延遲（毫秒）",
                        }
                    )
                )
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.caption("（尚無資料）")


# ── Page 6: Agent 執行紀錄 ──────────────────────────────────

elif page == "Agent 執行紀錄":
    st.header("Agent 執行紀錄")
    project_id = _require_project()
    if project_id:
        st.caption(
            "列出所有 agent_runs（知識庫問答與事件分析皆會留紀錄）。"
            "選一筆紀錄，可看它呼叫了哪些工具與每個工具的 input / output。"
        )
        runs = _safe(list_agent_runs, project_id, 50) or []
        if not runs:
            st.info("尚無 Agent 執行紀錄 — 請先到「知識庫問答」或「事件分析」操作一次。")
        else:
            run_summary_df = pd.DataFrame(
                [
                    {
                        "建立時間": r["created_at"],
                        "任務類型": r["task_type"],
                        "模型": r["model_name"],
                        "狀態": r["status"],
                        "延遲（毫秒）": r["latency_ms"],
                        "id": r["id"],
                    }
                    for r in runs
                ]
            )
            st.dataframe(run_summary_df, use_container_width=True, hide_index=True)

            labels = {f"{r['created_at']}  ·  {r['task_type']}  ·  {r['status']}  ·  {r['id'][:8]}…": r for r in runs}
            choice = st.selectbox("選擇一筆紀錄查看詳細", list(labels.keys()))
            run = labels[choice]

            c1, c2, c3 = st.columns(3)
            c1.metric("狀態", run["status"])
            c2.metric("延遲（毫秒）", run["latency_ms"] or 0)
            c3.metric("模型", run["model_name"])
            if run.get("error_message"):
                st.error(f"錯誤訊息：{run['error_message']}")
            with st.expander("input_json（輸入）"):
                st.json(run.get("input_json", {}))
            with st.expander("output_json（輸出）"):
                st.json(run.get("output_json", {}))

            st.subheader("工具呼叫紀錄（執行順序）")
            tool_calls = _safe(list_tool_calls, run["id"]) or []
            if not tool_calls:
                st.caption("（無工具呼叫 — 本次執行未呼叫任何工具）")
            else:
                for tc in tool_calls:
                    badge = "🟢" if not tc.get("error_message") else "🔴"
                    with st.expander(f"{badge} {tc['tool_name']}  ·  {tc.get('latency_ms') or 0} ms"):
                        if tc.get("error_message"):
                            st.error(tc["error_message"])
                        col_in, col_out = st.columns(2)
                        with col_in:
                            st.caption("input_json（輸入）")
                            st.json(tc.get("input_json", {}))
                        with col_out:
                            st.caption("output_json（輸出）")
                            st.json(tc.get("output_json", {}))
