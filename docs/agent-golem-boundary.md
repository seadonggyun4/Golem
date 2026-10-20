# Agent and Golem Responsibilities

## Positioning

Golem is a lightweight headless engine that lets different AI agents collaborate
by handing off work state and verification evidence. AWE means **Agentic Workflow
Engine**. Work remains the individual managed unit; existing API/schema names
are unchanged.

An external agent calling the CLI/API is already a headless orchestration client.
A daemon and universal provider launcher are not prerequisites. An assistant or
secretary is one possible client above the engine, not its required identity.
Codex and Claude have documented integrations; this is not a claim that every
provider is already integrated or that GUI conversation state is controlled.

## Responsibility Contract

| Party | Responsibility | Not implied |
| --- | --- | --- |
| Agent | Interpret intent, choose plans and interventions, author documents, edit code and use tools within user authority | Its judgment or declaration alone establishes native acceptance |
| Golem | Manage state, dependencies, ownership, handoffs and evidence; mechanically validate submissions, freshness and configured completion predicates | Understand every requirement semantically, authenticate every actor, or certify a defect-free product |
| Trusted host/client | Configure permissions, reviewed execution contracts and provider adapters; deliver input and retain exact identities/receipts | Switching clients grants takeover, retry or migration authority |
| Optional executor | Run explicitly authorized local development/QA commands and retain observations | All Markdown commands are executable authority, or noop means real work |

Golem may compute the next admissible workflow action and reject stale or
incomplete results without choosing the agent's solution. Approved QA execution
does not contradict this division. The same ownership, sequence, binding,
source, lease and evidence checks apply regardless of who launches a process.
Cooperative local labels and hashes are not authenticated identity or truth.

## Implementation Map

Source reviewed against `6b73dba` on 2026-10-20; this is a documentation
clarification, not a change to execution behavior or persisted contracts.

| Path | Actual contract | Product boundary |
| --- | --- | --- |
| [Session coordinator](../src/agent_session/coordinator.c), [session protocol](agent-session.md) | External caller drives claim/context/begin/submit/resume; native gates validate transitions | No provider spawn, GUI control or implicit background heartbeat |
| [Workflow](../src/workflow/model.c), [completion](completion.md) | Derive required next actions and current acceptance from registered inputs/evidence | Historical PASS and client success are not current DONE |
| [Execution API](../include/golem/execution.h), [execution contract](execution.md) | Explicitly approved local development/QA commands with durable attempt/receipt boundaries | Real execution, not a universal agent launcher or sandbox |
| [Worker API](../include/golem/worker.h), [worker executor](worker-executor.md) | Opt-in bounded external-process execution for a trusted embedding host | Host supplies the operation and actual integration; API presence is not provider support |
| [Daemon API](../include/golem/daemon.h), [CLI daemon host](../src/cli/daemon_worker.c) | C scheduler accepts a trusted execute callback; CLI dispatch requires `local.noop` simulation capability and result | Optional queue, not the normal session prerequisite; CLI does not dispatch arbitrary providers |
| [Lifecycle wrapper](agent-lifecycle.md), [context handoff](context-resume.md) | Explicit reviewed plans and provider input adapters reuse native contracts | Not atomic completion, automatic model generation or universal Hosted interception |

If an integration promises direct agent execution, it must supply a real,
non-noop worker and qualify its dispatch, effects, evidence and acceptance paths.
Neither a callback signature nor simulation success satisfies that promise.
This requirement is conditional on that integration's promise, not a reason to
add a mandatory daemon to the core.

## Lightweight Boundary

Preserve the orchestration core while reducing the procedures and inputs an
agent must handle. Reuse compact views with original retrieval, mechanical
execution records, dependency-bound current context and explicit lifecycle
entrypoints. Do not remove required evidence, truncate uncertain history, infer
approval, retry ambiguous effects, or relax native fencing to reduce input size.

These are design and implementation boundaries. They do not establish measured
token savings, lower bills, fewer model turns or better agent decisions.

## Research and Documentation Use

Use the positioning and responsibility table in introductions, architecture
descriptions and paper materials. Evaluate separately: agent task judgment,
engine contract enforcement, actual executor integration, and operational or
business acceptance. Specify the client, exact revision, execution path and
evidence trust level for each experiment. A simulation can test transitions but
cannot demonstrate real agent work; hash integrity cannot establish truth.

See [research positioning](research-positioning.md) for reusable paper wording
and claim boundaries. Preserve frozen experiments, quotations, CAS, journals and
historical design records. Explain older execution-centric wording as historical
scope rather than retroactively changing what ran or what was measured.
