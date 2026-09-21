# MVP Runtime

The MVP is intentionally narrow and headless.

## Fixed Scope

1. `Work Capsule`
2. `Stage Graph`
3. `Agent Adapter`
4. `Autonomy Policy`
5. `Evidence Store`
6. `Loop Controller`

## Default Stage Graph

```text
planning -> ux -> publishing -> development -> qa -> audit
```

Projects may override the graph, but every override must still produce predecessor evidence digests for downstream stages.

## Loop Reentry

QA and audit failures do not blindly return to development. Hatchling classifies the failure and returns to the most relevant stage:

- `planning_gap` -> `planning`
- `ux_mismatch` -> `ux`
- `publishing_gap` -> `publishing`
- `implementation_defect` -> `development`
- `qa_flake` -> `qa`
- `audit_gap` -> `audit`
- `policy_denied`, `stale_lease`, `budget_exhausted`, `unknown` -> `planning`

## Headless Projections

Hatchling may emit:

- JSON records for machines
- Markdown projections for humans
- content-addressed evidence receipts

It must not grow a UI client in the runtime package.
