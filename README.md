<div align="center">
  <img width="650" alt="Golem Banner" src="assets/Golem.png" />
</div>

<h1 align="center">Golem — Agentic Workflow Engine</h1>

<p align="center">
  <strong>A lightweight headless engine for AI agents to collaborate through work state and verification evidence</strong>
</p>

<p align="center"><em>Awaken the worker.</em></p>

[![CI](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml/badge.svg)](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml)
[![C17](https://img.shields.io/badge/core-C17-blue)](CMakeLists.txt)
[![Alpha](https://img.shields.io/badge/status-alpha-orange)](docs/conformance.md)
[![Agents](https://img.shields.io/badge/agents-Codex%20%7C%20Claude-327866)](docs/agent-session.md)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue)](LICENSE)

[한국어](README.ko.md) · **English** · [Installation](docs/runtime-reference.md#conan-package) · [Agent protocol](docs/agent-session.md)

## What Golem Does

**Supported agent integrations: Codex and Claude.** External agents collaborate by calling Golem's CLI/API and handing off work state and verification evidence. This is headless orchestration without requiring Golem to launch every agent or run a daemon.

The agent interprets user intent, plans, edits code and uses tools. Golem manages work state, dependencies, ownership, handoffs and evidence, and mechanically checks which submissions and completion claims satisfy the configured contracts. **AWE (Agentic Workflow Engine) is the category; Golem is the product.** It provides a C17 engine, CLI, JSON and Markdown, without a UI client.

| Responsibility | Owner |
| --- | --- |
| Decide what to do and how; perform the task | AI agent, within user authority |
| Enforce state transitions, ownership, input freshness and acceptance contracts | Golem |
| Run explicitly approved development/QA commands and record observations | Golem's optional execution path |
| Offer an assistant, UI or provider-specific launcher | Client/host integration, not a required engine service |

The goal is to preserve the orchestration core while reducing agent-facing procedures and inputs, not weaken evidence or safety gates. "Lightweight" describes this boundary, not a measured token, billing or performance result. See [roles and execution boundaries](docs/agent-golem-boundary.md).

## MCP

Golem provides locally installed MCP access for **Codex and Claude**, with
owner-approved project scope and explicit context disclosure. Codex installs
from the GitHub-backed marketplace and includes **Golem Setup**; Claude uses MCPB.

![Golem local Codex plugin, developed by Donggyun Seo](assets/Golem-codex-plugin.png)

[Codex plugin setup](docs/integration-codex-plugin.md) ·
[Claude Desktop setup](docs/integration-mcpb.md#install-and-configure)

The screenshot shows the verified synthetic-only installation, not a public
marketplace listing. Installation does not grant project access or execution.

## Architecture

```mermaid
flowchart TD
    A["External agent: judgment, edits and tools"] -->|"Direct CLI / C API"| C["Native C17 core: state, ownership, dependencies and evidence"]
    A --> L["Local Codex plugin / Claude MCPB"]
    L -->|"stdio MCP: approved reads and context"| I["Python integration layer: D1-D6"]
    A -->|"Separately opt-in supported hooks"| I
    O["Owner-reviewed client, project, disclosure and action policies"] --> I
    I -->|"Pinned CLI / fixed JSON requests"| C
    C --> E["Approved execution, QA and current completion"]
    C --> S["Explicit Work store, commonly under .golem"]
    E --> S
    S --> J["Durable events and receipts / content-addressed originals"]
    S --> M["Derived Markdown and reports"]
```

The integration layer connects clients; it does not replace native acceptance.
D1 handles approval and reviewed installation, D2 scoped reads/context/handoff,
D3 read-only startup/resume notices, D4 separately approved typed mutations,
D5 owner-controlled updates/reload/recovery, and D6 an optional authenticated TLS
gateway. They are not six engines or mandatory background services. Work paths
are explicit; a `.golem` directory alone grants no access. Client labels are not
authenticated identities, and context delivery does not prove model consumption.

The local packages reuse D1/D2 and add no automatic hook, Work resume or write
authority. `AVAILABLE` describes data delivery, not native `DONE`. Actual desktop
calls and client-specific display limits are recorded in the setup guides.

See [implemented architecture, storage authority and code/test map](docs/architecture.md)
for the complete process and [integration contracts](docs/integration-layer-design.md)
for per-client support, approval and deployment limits.

## Work Cycle

Representative **development** path for an explicitly created/enrolled Work:

```mermaid
flowchart TD
    S["Read status / next; review preflight"] --> G{"Current action admissible?"}
    G -->|"No / effects uncertain"| B["Wait or explicit recovery; no blind retry"]
    G -->|"Yes"| P["Per-artifact claim / context / begin; current plans; approved prepare"]
    P --> A["Agent edits source"]
    A --> D["Finish observation; register and submit development result"]
    D --> Q["QA plan and own QA claim; approved gates; register and submit result"]
    Q --> R{"QA outcome"}
    R -->|"FAIL / ERROR"| F["Agent classifies failure and revises affected inputs"]
    F --> S
    R -->|"PASS"| V["Recheck current source, documents and evidence"]
    V --> C["Explicit finalize and required report projection"]
    C --> N["Native DONE only when current conditions hold"]
```

Each claim covers one required artifact, not this entire cycle. The standard
stage-selection workflow requires planning, development, QA and completion
verification; UX/publishing are conditional on scope. Documents mode and enrolled
role contracts have their own predicates, not fabricated code/test success.
Downstream inputs bind exact upstream revisions. Changed source or parents can
invalidate earlier evidence: registration, QA PASS and current DONE are distinct.
Startup hooks and preflight do not automatically resume, execute or take ownership;
handoff preserves explicit state/evidence, not every client's entire conversation.

| Capability | Behavior | Details |
| --- | --- | --- |
| Markdown artifacts | Stored bodies, immutable revisions and parent references | [Document contract](docs/document-registry.md) |
| Discovery and scope | Record research evidence and improvement scope | [Discovery](docs/discovery.md) |
| Current-agent integration | Claim, submit, heartbeat and resume | [Sessions](docs/agent-session.md) |
| Development and QA | Bind source changes and approved real tests to evidence | [Execution](docs/execution.md) |
| Failure reentry | Revise affected documents with bounded repair budgets | [Reentry](docs/reentry.md) |
| Completion and recovery | Check current documents, QA and source; restore reports | [Completion](docs/completion.md) |
| Research records | Immutable case/attempt hypotheses, interventions, observations and next decisions | [ResearchCase / AttemptDecision](docs/research.md) |
| Outcome adjudication | Block completion on missing, skipped, failed or stale required assessments | [OutcomeAdjudication](docs/outcome.md) |
| Research metrics | Replay-based counts, latest assessments and explicitly bounded recovery measures | [Metrics](docs/metrics.md) |
| Comparison cohorts | Fixed non-use/partial/full-use groups, observation revisions and replay comparisons | [Cohorts](docs/cohort.md) |
| Case study bundles | Structural redaction, scoped evidence inventory and checksum-verified private export | [Bundles](docs/bundle.md) |
| Derived observability | Read-only OTLP snapshot logs and PROV-JSON, separate from authoritative CAS/journal | [OTel / PROV](docs/observability.md) |

## Quick Start

### Execution and Optional Features

The normal path is the native CLI/JSON session and document workflow, driven by
the current client. [Observed execution](docs/execution.md) runs explicitly
configured local development/QA commands under existing approval and source gates;
the [worker executor](docs/worker-executor.md) is a trusted-host C API, not an
automatic agent launcher. A new client must retain exact Work/source/sequence,
owner/binding, input references and native receipts; changing clients grants no
takeover or replay authority. Use [context-aware resume](docs/context-resume.md)
and its recovery instructions for handoff.
The default [current context recipe](docs/current-context-selection.md) retains
active dependencies and explicit archive references, with full fallback when
history/effect interpretation is uncertain; originals and native replay stay full.

The [bounded lifecycle wrapper](docs/agent-lifecycle.md) is optional: one reviewed
prepare/execute/finalize invocation, not an atomic transaction or automatic DONE.
Research records, cohorts, detailed metrics, observability exports and provider
usage adapters are optional surfaces, not documents every ordinary task must write.
Native QA/evidence/completion requirements remain mandatory where configured.

The local daemon is optional, not a prerequisite for agent collaboration.
`run --noop` and the CLI daemon's `local.noop` worker simulate runtime stages;
their success does not mean a real agent executed the user's task. The historical
Python `golem-prototype` is not the native `golem` engine. Existing local command
execution is real, but authenticated remote runners, arbitrary provider dispatch
and Windows runtime support are not promised by these examples. See the
[runtime reference](docs/runtime-reference.md) for individual supported contracts.

Owned Python verification and benchmark launchers automatically retain private
[mechanical execution records](docs/execution-recording.md).
[Consolidated Work records](docs/work-records.md) connect assessment, status and
journal views without rewriting their authoritative sources. Coverage and
exceptions are explicit; recorded execution is not product acceptance.

The native CLI defaults to compact presentation for large operational JSON replies.
For scripts parsing protocol fields, use `golem --output-mode full COMMAND ...`.
Compact replies link to hash-verified original payloads without reexecuting the
command. See [output modes and migration](docs/cli-output.md).

Requires macOS or Linux, a C17 compiler, CMake 3.21+, Ninja, Python 3.11+, OpenSSL 3, pkg-config, json-c 0.15+ and MD4C 0.4.8+. See [platform dependencies](docs/runtime-reference.md#build-and-run) or [Conan installation](docs/runtime-reference.md#conan-package).

json-c must pass strict Unicode parsing at configuration; unpatched 0.18 is unsupported. CI/Conan pin 0.17; see the dependency notes for the separate upstream 0.19 Release-build leak.

```sh
git clone https://github.com/seadonggyun4/Golem.git
cd Golem
cmake --preset release
cmake --build --preset release
ctest --preset release
build/release/golem --version
```

Create a new Work and register sample Markdown in a location you choose:

```sh
mkdir -p .golem/workspace
WORK="$(cd .golem/workspace && pwd -P)/first-work"
build/release/golem work start "$WORK" samples/documents/work.json
build/release/golem document validate samples/documents/planning.json samples/documents/planning.md
build/release/golem document submit "$WORK" samples/documents/planning.json samples/documents/planning.md planning-first
build/release/golem document inspect "$WORK" planning 1
```

Output: `.golem/workspace/first-work/documents/planning/r0001.md`.
This is a **registration example**, not automatic development or QA acceptance. Use a new path rather than overwriting a Work. Exclude `.golem/` from Git in your target project too.

For real work, configure project scope, QA commands and permissions, then connect Codex or Claude using the [agent instruction example](samples/agent-session/AGENTS.fragment.md) and [session protocol](docs/agent-session.md).

## Agent Entrypoints

Append the [common rules template](samples/agent-session/AGENTS.quickstart.md) to your existing **`AGENTS.md`**, then add the [Claude entry block](samples/agent-session/CLAUDE.quickstart.md) to **`CLAUDE.md`**. Preserve existing instructions. Korean translations are available as [`AGENTS.quickstart.ko.md`](samples/agent-session/AGENTS.quickstart.ko.md) and [`CLAUDE.quickstart.ko.md`](samples/agent-session/CLAUDE.quickstart.ko.md).

Replace the executable, Work root, protocol docs and target repository placeholders with real paths. Explicitly ask the current Codex or Claude agent to read the entrypoints. Select project-specific QA and permissions within the task's scope.

**[Setup guide, path examples and request template](docs/agent-setup.md)**

## Installation and Documentation

| Goal | Guide |
| --- | --- |
| Install the Conan package and CLI from GitHub source | [Conan installation](docs/runtime-reference.md#conan-package) |
| Embed the C/C++ library | [Build and install Golem::golem](docs/runtime-reference.md#development) |
| Review multi-client integration and MCP architecture | [Design](docs/integration-layer-design.md), [D1 approval/read backend](docs/integration-d1.md), [owner config installer/bootstrap](docs/integration-install.md), [D2 read-only MCP](docs/integration-d2.md), [D3 opt-in hooks](docs/integration-d3.md) |
| Explicit typed mutations and owner-approved QA | [D4 local MCP and approval host](docs/integration-d4.md) (separate opt-in; hooks remain read-only) |
| Owner-reviewed update, reload and uncertain-result recovery | [D5 maintenance](docs/integration-d5.md) (staged pins, no automatic native resume or effect retry) |
| Opt-in remote TLS gateway | [D6 authentication and disclosure](docs/integration-d6.md) (external AS, scoped grants; no automatic Hosted setup) |
| Use Python or TypeScript | [Language bindings](docs/runtime-reference.md#language-bindings) |
| Select stages and check document freshness | [Workflow](docs/workflow.md) |
| Enforce role deliverables before completion | [Role contracts](docs/role-contracts.md) |
| Understand qualification and verification | [Conformance](docs/conformance.md) |
| Runtime, performance and operations | [Technical reference](docs/runtime-reference.md) |
| Journal inspection, salvage and compatibility | [Integrity and recovery](docs/runtime-integrity.md) |

Distribution currently uses **GitHub + a Conan recipe**. It does not depend on a ConanCenter listing or a public Golem package server.

## Status

**Public Alpha.** Small local Codex and Claude cases exercised Markdown → QA FAIL → revision and repair → PASS → completion. Each project needs its own QA and permissions. Passing declared tests is not independent verification of every claim in a document. See [conformance](docs/conformance.md) for scope and reproduction procedures.

## License

Copyright 2026 Donggyun Seo. Golem is **source-available**, under the [PolyForm Noncommercial License 1.0.0](LICENSE), not an OSI-approved open-source license. Its exact terms govern permitted noncommercial use, modification and redistribution.

Uses outside those permissions require a separate written license from Donggyun Seo. See [commercial licensing](COMMERCIAL-LICENSE.md), [NOTICE](NOTICE) for attribution and third-party scope, or contact [seadonggyun@gmail.com](mailto:seadonggyun@gmail.com). An inquiry alone grants no additional rights. Dependencies retain their own licenses and ownership.
