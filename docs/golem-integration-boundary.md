# Golem Integration Boundary

Hatchling and Golem are separate projects.

Hatchling is a headless work runtime engine. Its job is to carry agent work to completion through `WorkCapsule`, `WorkRun`, `StageRun`, stage graph, lease, retry, evidence, and completion policy.

Golem is an optimizer/proxy/ledger for reducing agent execution cost. It is not itself a work agent. Its job is to observe execution, normalize provider usage, advise routing/cache/compression/fallback, and record cost lineage.

## Boundary

Hatchling asks:

> What state is this work in, and which stage should run next?

Golem asks:

> Can this execution be made cheaper while preserving quality and evidence constraints?

The two projects must not depend on each other at build time. Hatchling may expose stable optimization interfaces. Golem may implement those interfaces in an adapter package.

## Hatchling Keeps Final Authority

Golem may propose:

- provider route
- context compression
- cache use
- fallback path
- budget adjustment

Hatchling decides whether the proposal is allowed. It must reject any proposal that violates autonomy policy, required evidence, acceptance gates, stage graph rules, or budget constraints.

## Interfaces Hatchling Can Expose

- `ProviderUsage`
- `BudgetPolicy`
- `CostLedgerEntry`
- `OptimizationProposal`
- `OptimizationAdvisor`

These interfaces are intentionally small. They let an optimizer plug in without pulling Golem's proxy, learning pipeline, dashboard, or traffic gateway assumptions into Hatchling.

## Non-Goals

- No merged product core.
- No shared runtime dependency.
- No UI console.
- No optimizer-owned completion decision.
- No assumption that all traffic is intercepted through a proxy.
