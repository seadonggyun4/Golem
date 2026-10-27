<!-- GOLEM_README_EDITING_RULES
Required README maintenance rules; preserve this format unless the user explicitly changes it.
1. Keep the visible order: one short latest verified status line, brief product introduction,
   Mermaid role/work flows, short MCP setup links, a small documentation table and license.
   The workspace entry README remains a brief introduction, diagram and guide links.
2. Keep technical inventories, feature lists and version history out of the README.
   Linked guides contain installation and usage steps.
3. BEFORE updating, review the README and linked Codex/Claude setup guides against verified
   installed files, manifests, source and the intended client's current CLI. Remove obsolete
   or duplicate instructions, paths, commands, marketplaces/connections, missing-adapter steps
   and profile/permission confusion. A version number or historical PASS is not current proof.
   Preserve historical evidence and ledgers instead of rewriting them as current verification.
4. Separate preparation from approval and preserve existing authority. Check required results,
   documents and QA; perform approved finalize/report actions; then read current completion_check
   for DONE. Never suggest replaying uncertain/COMMIT_UNKNOWN effects or rewriting approval pins.
5. Keep Korean/English text and diagrams aligned; check links, anchors and duplicate guidance.
   After diagram edits, check mobile/desktop and light/dark rendering. Record actual evidence
   and NOT_RUN scope; never promote unverified behavior into current installation guidance.
Keep this comment during editing. Keep the rendered README concise.
-->

> Latest verified MCP builds: **Codex 0.2.5 · Claude task 0.1.8** — isolated macOS Works completed. [Verification scope](docs/mcp-m7-m8-validation.ko.md)

<div align="center">
  <img width="650" alt="Golem Banner" src="assets/Golem.png" />
</div>

<h1 align="center">Golem — Agentic Workflow Engine</h1>

<p align="center"><strong>Connect AI work through state and verification evidence</strong></p>

[한국어](README.ko.md) · **English** · [Setup](#mcp) · [Documentation](#documentation)

## What Does Golem Do?

Codex and Claude plan and perform tasks. Golem connects progress, deliverables and verification results to check completion conditions.

```mermaid
flowchart TD
    U["User<br/>Goals and authority"] --> A["Codex · Claude<br/>Planning and work"]
    A --> G["Golem<br/>State, deliverables and evidence"]
    G -->|"Current state and next steps"| A
    G --> R["Traceable results and handoffs"]
```

## MCP

Follow your client's guide to install a reviewed package and connect it to existing approved projects, Works and actions.
Installation itself grants no access or execution authority.

- **[Codex setup and use](docs/integration-codex-plugin.md)** — connect with Golem Setup and proceed with Golem Work.
- **[Claude Desktop setup and use](docs/integration-mcpb.md#install-and-configure)** — install the needed feature package and verify the connection.

Keep **one latest verified Golem installation and one intended connection per client**.

## Work Flow

```mermaid
flowchart TD
    S["Check current state<br/>and next steps"] --> P["Prepare inputs and plan"]
    P --> A["Work within<br/>granted authority"]
    A --> Q["Check results, required<br/>documents and QA"]
    Q -->|"Requirements met"| F["Approved finalization<br/>and report actions"]
    F --> C{"Current DONE?"}
    C -->|"Yes"| D["Complete<br/>and hand off"]
    C -->|"No"| B["Wait / inspect<br/>next steps"]
```

Read the current completion decision after finalization and report actions. At any stage, stop for pending approval, stale inputs or uncertain results; do not retry automatically.

## Documentation

| Get started with | Guide |
| --- | --- |
| Project instructions and first tasks | [Agent setup](docs/agent-setup.md) |
| CLI/library installation and builds | [Runtime guide](docs/runtime-reference.md#build-and-run) |
| Work stages and completion | [Workflow](docs/workflow.md) · [Completion](docs/completion.md) |
| Internals and integration contracts | [Architecture](docs/architecture.md) · [MCP integration](docs/integration-layer-design.md) |

## License

Copyright 2026 Donggyun Seo. **Source-available · [PolyForm Noncommercial 1.0.0](LICENSE)**.
The license governs permitted noncommercial use. [Commercial use](COMMERCIAL-LICENSE.md) · [Notices](NOTICE)
