# OpsWeave 交付路線圖

[English](2026-06-28-opsweave-roadmap.md) | 繁體中文

重寫拆成九份可獨立驗證的計畫；每一期都必須維持 Docker Compose 可啟動，
且先前測試持續通過。

1. **平台基礎**：品牌、PostgreSQL／Redis、管理員認證、健康聚合、React
   Shell、固定狀態列、Bento Dashboard。
2. **可靠任務引擎**：Task、Dependency、Attempt、Event、Artifact、Dramatiq、
   lease、重試、取消、SSE 與恢復。
3. **Agent Protocol 與 Manager**：Manifest、Schema、Registry、A2A、Core MCP、
   ToolGrant、模型 Provider、計畫確認與 callback。
4. **Knowledge Agent**：Knowledge Base、索引、OCR、混合檢索、rerank、引用。
5. **Coding／Business Analysis Agent**：隔離 workspace、artifact、程式與報告 contract。
6. **WebChat 與身份核准**：Conversation、Message、附件、pending identity、callback。
7. **外部 Channel**：Telegram、Discord、LINE。
8. **專案與自動化**：Epic、Story、Kanban、Reminder、Recurring Work、Diary、
   Skill／API Registry。
9. **營運完成**：Runs／Logs、Settings、RWD、Playwright、worker 重啟恢復、
   Channel smoke test 與發布驗證。

第一期詳細計畫：
`2026-06-28-opsweave-foundation-implementation.md`。
