# Hatchling Integration Boundary

Golem and Hatchling are separate projects.

Golem is a headless work runtime engine. Its job is to carry agent work to completion through `WorkCapsule`, `WorkRun`, `StageRun`, stage graph, lease, retry, evidence, and completion policy.

Hatchling is an optimizer/proxy/ledger for reducing agent execution cost. It is not itself a work agent. Its job is to observe execution, normalize provider usage, advise routing/cache/compression/fallback, and record cost lineage.

## Boundary

Golem asks:

> What state is this work in, and which stage should run next?

Hatchling asks:

> Can this execution be made cheaper while preserving quality and evidence constraints?

The two projects must not depend on each other at build time. Golem may expose stable optimization interfaces. Hatchling may implement those interfaces in an adapter package.

## Golem Keeps Final Authority

Hatchling may propose:

- provider route
- context compression
- cache use
- fallback path
- budget adjustment

Golem decides whether the proposal is allowed. It must reject any proposal that violates autonomy policy, required evidence, acceptance gates, stage graph rules, or budget constraints.

## Interfaces Golem Can Expose

- `ProviderUsage`
- `BudgetPolicy`
- `CostLedgerEntry`
- `OptimizationProposal`
- `OptimizationAdvisor`

These interfaces are intentionally small. They let an optimizer plug in without pulling Hatchling's proxy, learning pipeline, dashboard, or traffic gateway assumptions into Golem.

## Non-Goals

- No merged product core.
- No shared runtime dependency.
- No UI console.
- No optimizer-owned completion decision.
- No assumption that all traffic is intercepted through a proxy.
