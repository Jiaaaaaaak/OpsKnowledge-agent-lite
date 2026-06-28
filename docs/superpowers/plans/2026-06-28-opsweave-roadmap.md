# OpsWeave Delivery Roadmap

[繁體中文](2026-06-28-opsweave-roadmap.zh-TW.md)

The approved rewrite is divided into independently testable plans. Each plan
must keep Docker Compose bootable and all earlier tests green.

1. **Platform foundation** — OpsWeave branding, PostgreSQL/Redis control-plane
   dependencies, administrator authentication, health aggregation, React
   application shell, sticky status bar, and Bento dashboard.
2. **Durable task engine** — Task, dependency, attempt, event, artifact,
   Dramatiq dispatch, leases, retries, cancellation, SSE, and recovery.
3. **Agent protocol and Manager** — versioned manifests, JSON Schema,
   registry, A2A client/server contract, Core MCP, ToolGrant allowlists, model
   providers, plan confirmation, and task-scoped callbacks.
4. **Knowledge Agent** — knowledge bases, ingestion, OCR, hybrid retrieval,
   reranking, citations, and Manager delegation.
5. **Coding and Business Analysis Agents** — isolated workspaces, artifact
   publication, code execution contract, analysis/report contract, and result
   envelope validation.
6. **WebChat and identity approval** — conversations, messages, attachments,
   pending identities, approvals, live progress, callbacks, and artifact
   download.
7. **External channels** — Telegram, Discord, and LINE adapters implementing
   the common channel contract and independent credential-free startup.
8. **Project and automation modules** — Epic, Story, Kanban/queue, reminders,
   recurring work, diary, skills, API registry, and encrypted integration
   headers.
9. **Operational completion** — Runs and Logs, settings, responsive polish,
   Playwright flows, worker-restart recovery, four-channel smoke tests,
   documentation, and release verification.

The detailed executable plan for item 1 is:
`2026-06-28-opsweave-foundation-implementation.md`.
