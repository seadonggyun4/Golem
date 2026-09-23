<div align="center">
  <img width="650" alt="Golem Banner" src="assets/Golem.png" />
</div>

<h1 align="center">Golem — Agentic Work Engine</h1>

<p align="center">
  <strong>A headless work runtime that carries Markdown and verified results through to completion</strong>
</p>

<p align="center"><em>Awaken the worker.</em></p>

[![CI](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml/badge.svg)](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml)
[![C17](https://img.shields.io/badge/core-C17-blue)](CMakeLists.txt)
[![Alpha](https://img.shields.io/badge/status-alpha-orange)](docs/conformance.md)
[![Agents](https://img.shields.io/badge/agents-Codex%20%7C%20Claude-327866)](docs/agent-session.md)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue)](LICENSE)

[한국어](README.ko.md) · **English** · [Installation](docs/runtime-reference.md#conan-package) · [Agent protocol](docs/agent-session.md)

## What Golem Does

**Supported agents: Codex and Claude.** Golem helps the agent already working with you carry Markdown documents and verification results through to completion. Launching another agent is not the central idea.

The agent researches, writes documents and edits code. Golem manages document dependencies, freshness, execution evidence, permissions and completion conditions. **AWE (Agentic Work Engine) is the category; Golem is the product.** It provides a C17 engine, CLI, JSON and Markdown, without a UI client.

## Work Cycle

```text
User request
→ Current agent starts or restores a Work in Golem
→ Explore the project, research references and select scope
→ Author and register Markdown for the necessary stages
→ Develop against validated documents
→ Run real QA and record results in Markdown
→ Classify failures
→ Revise affected documents → repeat development and QA
→ Verify completion conditions and produce a completion report
```

Select **only the necessary stages** from planning → UX → publishing → development → QA → audit. Downstream documents reference exact upstream revisions; changes trigger freshness checks on affected documents and verification results.

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

Requires macOS or Linux, a C17 compiler, CMake 3.21+, Ninja, Python 3.11+, OpenSSL 3, pkg-config, json-c 0.15+ and MD4C 0.4.8+. See [platform dependencies](docs/runtime-reference.md#build-and-run) or [Conan installation](docs/runtime-reference.md#conan-package).

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
| Use Python or TypeScript | [Language bindings](docs/runtime-reference.md#language-bindings) |
| Select stages and check document freshness | [Workflow](docs/workflow.md) |
| Understand qualification and verification | [Conformance](docs/conformance.md) |
| Runtime, performance and operations | [Technical reference](docs/runtime-reference.md) |
| Journal inspection, salvage and compatibility | [Integrity and recovery](docs/runtime-integrity.md) |

Distribution currently uses **GitHub + a Conan recipe**. It does not depend on a ConanCenter listing or a public Golem package server.

## Status

**Public Alpha.** Small local Codex and Claude cases exercised Markdown → QA FAIL → revision and repair → PASS → completion. Each project needs its own QA and permissions. Passing declared tests is not independent verification of every claim in a document. See [conformance](docs/conformance.md) for scope and reproduction procedures.

## License

Copyright 2026 Donggyun Seo. Golem is **source-available**, under the [PolyForm Noncommercial License 1.0.0](LICENSE), not an OSI-approved open-source license. Its exact terms govern permitted noncommercial use, modification and redistribution.

Uses outside those permissions require a separate written license from Donggyun Seo. See [commercial licensing](COMMERCIAL-LICENSE.md), [NOTICE](NOTICE) for attribution and third-party scope, or contact [seadonggyun@gmail.com](mailto:seadonggyun@gmail.com). An inquiry alone grants no additional rights. Dependencies retain their own licenses and ownership.
