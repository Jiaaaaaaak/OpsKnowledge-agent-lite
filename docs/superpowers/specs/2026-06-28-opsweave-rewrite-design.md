# OpsWeave Rewrite Design

English | [繁體中文](2026-06-28-opsweave-rewrite-design.zh-TW.md)

## 1. Objective

Rewrite this repository as **OpsWeave**, a self-hosted, single-organization AI
operations platform. OpsWeave uses a manager agent to coordinate independent
specialist agents, exposes their work through WebChat and external chat
channels, and gives operators a React control plane for agents, tasks,
knowledge, automation, users, integrations, and audit data.

CoStaff is a product and workflow reference only. OpsWeave is a clean-room
implementation: it must not copy CoStaff source code or assets. The existing
OpsKnowledge data does not need to be migrated. Its RAG capability is retained
as the built-in Knowledge Agent.

## 2. Product Scope

### 2.1 Included in the first release

- Manager, Knowledge, Coding, and Business Analysis agents.
- Independent agent containers communicating through A2A.
- MCP-based tool access with per-agent allowlists.
- WebChat, Telegram, Discord, and LINE channel adapters.
- Dashboard, Chat, Projects, Tasks, Knowledge, Agents, Automation, Diary,
  Channels, Integrations, Users, Runs and Logs, and Settings.
- Epic, Story, Task, dependency, comment, attempt, and event tracking.
- Reminders and recurring agent work.
- API and reusable skill registries.
- PostgreSQL with pgvector for application and knowledge data.
- Redis and Dramatiq workers for dispatch, retries, schedules, callbacks, and
  notifications.
- Gemini, OpenAI-compatible, and Ollama model providers through one provider
  interface, with model selection per agent.
- Docker Compose deployment on one host.

### 2.2 Explicitly excluded

- Migration of existing OpsKnowledge projects, chunks, vectors, or audit runs.
- Multi-tenancy and organization-level data partitioning.
- Multi-core switching.
- Commercial license enforcement.
- Kubernetes and multi-host orchestration.
- ERP, CRM, or other enterprise service lifecycle controls.

## 3. Architecture

### 3.1 Control plane

The FastAPI control plane owns authentication, authorization, identity
approval, conversations, projects, tasks, agent registration, configuration,
knowledge management, and operator APIs. It is the authoritative API for the
React application and channel adapters.

The control plane does not run substantive agent work inside an HTTP request.
It validates commands, persists intent, and dispatches durable jobs.

### 3.2 Durable execution

PostgreSQL is the source of truth for all business state. Redis is only the
transport for queued work and temporary worker coordination. Dramatiq workers
perform:

- task dispatch and A2A calls;
- retry and timeout handling;
- dependency release;
- scheduled and recurring work;
- result callbacks to the originating conversation;
- outbound channel delivery.

Workers use task leases, heartbeats, database locks, and idempotency keys so a
job can be retried after worker loss without completing the same task twice.

### 3.3 Agent runtime

Each agent is built and deployed independently:

- **Manager Agent**: classifies requests, proposes plans, receives approval,
  and dispatches work. It coordinates but does not perform specialist work.
- **Knowledge Agent**: ingests and retrieves operational documents using
  PostgreSQL full-text search, pgvector, hybrid fusion, optional reranking,
  and grounded citations.
- **Coding Agent**: performs isolated code and file work in a restricted
  workspace.
- **Business Analysis Agent**: interprets data and produces business-facing
  summaries, visualizations, and reports.

Agents expose A2A endpoints and declare their metadata in an OpsWeave agent
manifest. Agent manifests are versioned and JSON-Schema validated. The control
plane discovers endpoints from registry data, never from hard-coded container
names.

### 3.4 MCP and tool grants

Core MCP exposes cross-agent primitives such as progress reporting, task
comments, artifact publishing, file listing, and user notification. Every
agent receives an explicit `ToolGrant` allowlist. A new agent starts with no
optional tools.

The Manager sees orchestration tools and registered A2A agents. It does not
inherit each specialist's internal MCP tools. Specialists receive their own
domain tools plus the minimum shared tools required for progress and artifact
handoff.

### 3.5 Channels

WebChat, Telegram, Discord, and LINE adapters implement one channel contract:

- normalize inbound messages and attachments;
- resolve or create an opaque channel identity;
- forward the message to the correct conversation;
- receive asynchronous text, progress, and artifact deliveries;
- preserve the originating conversation when callbacks arrive.

Adapters can be disabled independently. Missing external channel credentials
must not prevent WebChat or the control plane from starting.

## 4. Data Model

### 4.1 Identity and conversation

- `User`: approved platform user and profile.
- `ChannelIdentity`: channel, opaque external identity, encrypted reversible
  routing value, approval state, and latest conversation reference.
- `Conversation`: channel-independent conversation boundary.
- `Message`: normalized user, assistant, tool, callback, and system messages.

The original platform identifier is never used as a public application ID.
An HMAC-derived opaque identifier is used for lookups. Reversible routing data
is encrypted at rest.

### 4.2 Agent registry

- `AgentDefinition`: stable identifier, display data, protocol version, and
  capability description.
- `AgentEndpoint`: A2A URL, health path, version, and enabled state.
- `ModelConfig`: provider, model, endpoint reference, and agent assignment.
- `ToolGrant`: agent-to-MCP-tool allowlist.

### 4.3 Project work

- `Epic` contains Stories and direct Tasks.
- `Story` represents a milestone inside an Epic.
- `Task` represents user intent and current state.
- `TaskDependency` supports multiple upstream and downstream relationships
  using foreign keys.
- `TaskComment` is an immutable human or agent audit entry.
- `TaskAttempt` records each execution and retry independently.
- `TaskEvent` is an immutable state-transition and progress stream.
- `Artifact` records produced files, media type, checksum, size, owner, and
  publication state.

### 4.4 Knowledge

- `KnowledgeBase`, `Document`, and `DocumentChunk`.
- `DocumentChunk` stores text, retrieval metadata, search vector, and pgvector
  embedding.
- `Citation` links an answer or agent run to the exact chunks used.

### 4.5 Automation and integration

- `Reminder` for one-time notification.
- `RecurringWork` and `RecurringWorkRun` for cron-driven agent work.
- `Diary` for per-agent daily, weekly, or monthly summaries.
- `SkillConfig` for reusable instruction templates.
- `ApiConfig` for approved outbound HTTP integrations with encrypted headers
  and URL safety policy.

## 5. Task State Machine

The primary path is:

```text
backlog -> queued -> running -> succeeded
```

Additional states are:

- `retry_scheduled`: a retryable attempt failed and is waiting for backoff.
- `failed`: retries are exhausted or the error is non-retryable.
- `cancelled`: an operator or user cancelled work before completion.

A dependency-blocked task stays in `backlog`; dependency state is derived from
`TaskDependency`, not encoded as an unvalidated task ID string. When all
upstream tasks succeed, a transaction moves the dependent task to `queued`.
If an upstream task fails or is cancelled, the dependent task remains blocked
and the UI presents retry, replace dependency, skip, or cancel actions.

Every transition writes a `TaskEvent`. Every worker execution creates a
`TaskAttempt`. Retries never overwrite previous attempt errors or metrics.

## 6. Dispatch and Callback Flow

1. A channel adapter or WebChat app sends a normalized message.
2. The Manager classifies it as conversation, immediate work, future reminder,
   recurring work, or project work.
3. Substantive work is presented as a plan when confirmation is required.
4. Approval creates one Task or an atomic dependency graph.
5. The dispatcher enqueues the first runnable Task.
6. The worker calls the assigned agent over A2A using a task-scoped session.
7. Progress is persisted as TaskEvents and streamed to the UI.
8. The agent returns a structured Result Envelope.
9. OpsWeave verifies declared artifacts and persists the attempt result.
10. The callback worker injects a system callback into the originating
    conversation. The Manager summarizes it in the user's language.
11. The notifier sends the message and attachments through the originating
    channel.
12. Successful completion releases dependent tasks.

The Result Envelope contains:

- `status`: `ok` or `failed`;
- `summary`;
- `artifacts`: path, media type, checksum, and optional title;
- `error_code` and safe `error_message`;
- execution metrics and optional structured result data.

## 7. Frontend

### 7.1 Application shell

The React application uses a modern Bento visual language. A compact,
sticky top bar shows overall health, PostgreSQL, vector, model, and active-task
status. Clicking it expands service details. System Status is not a separate
navigation item.

The sidebar is grouped as follows:

- **Workspace**: Dashboard, Chat, Projects, Tasks, Knowledge.
- **AI Team**: Agents, Automation, Diary.
- **Operations**: Channels, Integrations, Users, Runs and Logs, Settings.

On mobile, the sidebar becomes a drawer and dashboard cards become a true
single-column layout.

### 7.2 Dashboard

The Dashboard keeps all four approved groups:

- System Pulse: CPU, memory, disk, uptime, and refresh time.
- Knowledge Metrics: knowledge bases, documents, chunks, indexing status.
- Agent Workload: queued, running, succeeded, failed, and dependency chains.
- Activity and Alerts: recent completions, failures, and direct recovery links.

### 7.3 Main workflows

- **Conversation dispatch**: request, Manager plan, approval, asynchronous
  Task, live progress, callback in the original conversation.
- **Project execution**: Epic and Story planning, dependency graph, Kanban or
  queue view, attempt history, comments, and artifacts.
- **Knowledge work**: create a knowledge base, upload and index documents,
  retrieve with citations, or hand retrieved data to Business Analysis.

Task and agent state arrives over server-sent events. The client falls back to
polling after a stream failure.

The default UI language is Traditional Chinese. Code identifiers, database
fields, environment variables, and API contracts remain English.

## 8. Security

- Administrator passwords use Argon2id.
- Browser authentication uses secure, HTTP-only, SameSite session cookies.
- New channel identities start in `pending` and cannot execute agent tools
  until approved.
- Secrets and integration headers are encrypted at rest and never returned by
  read APIs.
- Outbound integration URLs are protected by scheme, DNS, redirect, loopback,
  private-network, and metadata-endpoint checks.
- Uploads enforce extension, MIME type, size, page, and safe-path limits.
- Agent workspaces are private by default. Artifacts become deliverable only
  after explicit publication into a shared area.
- Errors returned to clients contain a correlation ID, not a stack trace.
- Destructive UI operations require explicit confirmation.

## 9. Failure Recovery

- Retryable errors use exponential backoff with a default maximum of three
  attempts.
- Worker heartbeat and lease expiry recover work after process loss.
- Duplicate jobs are rejected using idempotency keys and transactional locks.
- Callback and notification delivery have independent attempts and retries.
- A task is not `succeeded` until every declared artifact passes existence,
  location, size, and checksum validation.
- Failed dependency chains do not auto-run downstream work.
- Operators can retry an attempt, retry from a selected task, cancel a chain,
  or replace a failed dependency.

## 10. Testing and Completion Criteria

Implementation follows test-driven development.

- Unit tests cover state transitions, identity derivation, Result Envelope
  parsing, tool grants, URL policy, and provider selection.
- Integration tests cover PostgreSQL, pgvector, Redis, Dramatiq, schedules,
  leases, retries, and callback delivery.
- Contract tests cover A2A manifests and envelopes, MCP tools, and the channel
  adapter contract.
- Frontend tests use Vitest and Testing Library.
- Playwright covers administrator onboarding, identity approval, WebChat
  dispatch, task progress, callback, artifacts, and recovery actions.
- Telegram, Discord, and LINE each have adapter smoke tests; credential-free
  startup is also tested.

The first release is complete only when a fresh Docker Compose deployment can:

1. create an administrator;
2. start with WebChat while external channel tokens are absent;
3. configure and enable external channels independently;
4. approve a new channel user;
5. register and health-check all four agents;
6. dispatch work to each agent;
7. show live progress and attempt history;
8. return a callback and artifact to the originating conversation;
9. execute reminders and recurring work;
10. restart a worker during a task and recover without duplicate completion.

## 11. Repository and Delivery Strategy

Development occurs on `feat/opsweave-rewrite`. The existing application may be
replaced rather than migrated, but the rewrite is delivered in independently
verifiable vertical slices. Each slice must leave Docker Compose and automated
tests in a runnable state.

The implementation plan must sequence foundational contracts before UI breadth:

1. repository and runtime foundation;
2. identity and control-plane authentication;
3. task state machine and worker reliability;
4. A2A/MCP contracts and Manager dispatch;
5. Knowledge, Coding, and Business Analysis agents;
6. WebChat and callback flow;
7. external channel adapters;
8. projects, automation, diary, and registries;
9. full Modern Bento frontend and operational hardening.
