# Hatchling Project Docs

This directory is the development documentation engine for Hatchling.

Hatchling is moving toward a C implementation of a headless work runtime kernel. The documents here define the durable engineering boundary, subsystem ownership, API rules, testing gates, and implementation phases.

## Document Map

- [Product and Runtime Boundary](specs/01-product-runtime-boundary.md)
- [C Subsystem Architecture](specs/02-c-subsystem-architecture.md)
- [Public C API and Ownership Rules](specs/03-public-c-api-and-ownership.md)
- [Journal, Evidence, and Replay](specs/04-journal-evidence-replay.md)
- [Cost and Optimizer Boundary](specs/05-cost-optimizer-boundary.md)
- [Testing and Quality Gates](specs/06-testing-quality-gates.md)
- [Implementation Roadmap](roadmap/01-c-runtime-roadmap.md)
- [ADR Template](decisions/ADR-TEMPLATE.md)

## Source of Truth

`project-docs/` governs future implementation structure. The existing Python package is a prototype and smoke-testable model, not the long-term runtime architecture.

`docs/` remains product-facing conceptual documentation. `project-docs/` is for maintainers and implementation agents.

## Maintenance Rules

- Keep Hatchling independent from Golem and every other optimizer/runtime.
- Keep the runtime headless: CLI, daemon, JSON, MessagePack, gRPC, and Markdown projection are allowed; UI is out of core scope.
- Prefer small stable C subsystems over a monolithic application.
- Record non-trivial architecture changes as ADRs under `project-docs/decisions/`.
- Every new subsystem must define ownership, public API, persistence impact, and tests before broad implementation.
