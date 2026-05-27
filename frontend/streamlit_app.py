import streamlit as st

st.set_page_config(
    page_title="OpsKnowledge Agent Lite",
    page_icon="🤖",
    layout="wide",
)

PAGES = {
    "Upload": "upload",
    "Chat": "chat",
    "Dashboard": "dashboard",
    "Agent Logs": "logs",
}

with st.sidebar:
    st.title("OpsKnowledge Agent")
    st.caption("v0.1.0 — IT Ops AI POC")
    st.divider()
    page = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")

if page == "Upload":
    st.header("Upload Documents & Incident Data")
    st.info("Upload PDF manuals / SOPs or CSV/Excel/JSON incident tickets here.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("PDF Documents")
        st.file_uploader("Choose a PDF", type=["pdf"], disabled=True)
        st.caption("RAG pipeline — coming in Step 2")
    with col2:
        st.subheader("Incident Records")
        st.file_uploader("Choose CSV / Excel / JSON", type=["csv", "xlsx", "json"], disabled=True)
        st.caption("ETL pipeline — coming in Step 3")

elif page == "Chat":
    st.header("Knowledge Q&A")
    st.info("Ask questions against uploaded documents using RAG.")
    st.text_input("Ask a question...", disabled=True, placeholder="e.g. What is the escalation procedure?")
    st.caption("RAG chat — coming in Step 2")

elif page == "Dashboard":
    st.header("Incident Analysis Dashboard")
    st.info("AI-generated insights, severity scores, and action items.")
    st.caption("Dashboard — coming in Step 5")

elif page == "Agent Logs":
    st.header("Agent Run Logs")
    st.info("Every AI tool call and LLM invocation is logged here for observability.")
    st.caption("Observability layer — coming in Step 5")
