# CLAUDE.md — 18-rule template

These rules apply to every task in this project unless explicitly overridden.
Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.
Rule 1–13：工作方式與語言規範
Rule 14–18：專案安全與工程實務

## Rule 1 — Think Before Coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.

## Rule 2 — Simplicity First
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked. No abstractions for single-use code.
Test: would a senior engineer say this is overcomplicated? If yes, simplify.

## Rule 3 — Surgical Changes
Touch only what you must. Clean up only your own mess.
Don't "improve" adjacent code, comments, or formatting.
Don't refactor what isn't broken. Match existing style.

## Rule 4 — Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps. Define success and iterate.
Strong success criteria let you loop independently.

## Rule 5 — Use the model only for judgment calls
Use me for: classification, drafting, summarization, extraction.
Do NOT use me for: routing, retries, deterministic transforms.
If code can answer, code answers.

## Rule 6 — Token budgets are not advisory
Per-task: 4,000 tokens. Per-session: 30,000 tokens.
If approaching budget, summarize and start fresh.
Surface the breach. Do not silently overrun.

## Rule 7 — Surface conflicts, don't average them
If two patterns contradict, pick one (more recent / more tested).
Explain why. Flag the other for cleanup.
Don't blend conflicting patterns.

## Rule 8 — Read before you write
Before adding code, read exports, immediate callers, shared utilities.
"Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.

## Rule 9 — Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.

## Rule 10 — Checkpoint after every significant step
Summarize what was done, what's verified, what's left.
Don't continue from a state you can't describe back.
If you lose track, stop and restate.

## Rule 11 — Match the codebase's conventions, even if you disagree
Conformance > taste inside the codebase.
If you genuinely think a convention is harmful, surface it. Don't fork silently.

## Rule 12 — Fail loud
"Completed" is wrong if anything was skipped silently.
"Tests pass" is wrong if any were skipped.
Default to surfacing uncertainty, not hiding it.

## Rule 13 — 語言規範
程式碼本身（識別字、語法）維持原樣。其餘內容依類型分流：
- 文件（README、docs/*.md）：主文件以**英文**為準，繁體中文放在對應的 `.zh-TW.md`（例如 `docs/API.md` ↔ `docs/API.zh-TW.md`），並在頁首加上語言切換連結。
- 註解（comments）：繁體中文。
- 對使用者的回覆：繁體中文。
- commit message：繁體中文。


## Rule 14 — Project Commands Are Source of Truth
Use only the commands documented in this repository unless explicitly told otherwise.
Before running install, build, test, migration, or deployment commands, check README, Makefile, package scripts, docker-compose files, or existing CI config.

Do not invent commands.
If multiple command sources conflict, prefer CI config first, then Makefile, then README, then package scripts.
Surface the conflict before proceeding.

## Rule 15 — Data Safety First
Never delete, reset, or migrate databases, volumes, generated data, or user files without explicit permission.
Destructive commands require a clear warning and confirmation.

Examples of destructive actions:
- docker volume rm
- docker compose down -v
- database reset/drop/truncate
- migration rollback
- deleting uploaded files, embeddings, or indexed documents

## Rule 16 — Debug Before Fixing
When debugging, first identify the failing boundary:
- configuration
- environment
- dependency
- database
- network
- application logic
- test expectation

Do not patch symptoms before explaining the suspected root cause.
Prefer one focused diagnostic command before editing code.

## Rule 17 — Secrets and Environment Files
Never commit real secrets, API keys, passwords, tokens, or private URLs.
Keep `.env.example` safe, minimal, and documented.
When adding a new environment variable:
- add it to `.env.example`
- document its purpose
- provide a safe default when possible
- update validation logic if the project has one

## Rule 18 — Preserve Public Contracts
Do not change API routes, response shapes, database schemas, environment variable names, CLI arguments, or file formats unless required by the task.
If a contract must change, identify all affected callers, tests, docs, and migration needs.
