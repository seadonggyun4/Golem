# Hatchling

Hatchling is the product implementation of `AWE — Agentic Work Engine`.

AWE is the academic/category name. Hatchling is the product name.

Hatchling is a headless execution engine that lets multiple agent providers run the same work cycle. It is not a document-writing tool. It is a headless work runtime that helps agents carry work through to completion, while recording every execution as documents and evidence.

## Product Boundary

Hatchling stays headless until the execution engine is useful on its own.

- No UI client in the runtime package.
- CLI, JSON, and Markdown projection are allowed.
- Every execution must leave evidence.
- Agent providers must share the same `run_stage(input) -> result/evidence` contract.
- Local autonomy is explicit and policy bounded.

## Runtime Direction

Hatchling is moving toward a C implementation of a work runtime kernel plus CLI, daemon, evidence CAS, adapter protocol, cost layer, and policy layer.

The current Python package is a smoke-testable prototype for the core model. The long-term implementation structure is governed by [project-docs](/Volumes/Extreme SSD/Hatchling-project/Hatchling/project-docs/README.md).

## Runtime MVP

The first product engine structure lives under `src/hatchling/`.

- `core`: Work Capsule, WorkRun, StageRun, Stage Graph, Context Package, Decision, and EvidenceRef models.
- `runtime`: loop controller and lease/heartbeat primitives.
- `evidence`: content-addressed evidence store with redaction checks.
- `adapters`: provider contract plus a local no-op adapter for smoke runs.
- `policies`: autonomy boundaries such as `AUTO_LOCAL`, `ASK_ON_EXTERNAL_EFFECT`, `ASK_ALWAYS`, and `DENY`.
- `core.optimization`: optional cost/budget/usage interfaces for optimizers such as Golem, with no runtime dependency.

The default stage graph is:

```text
planning -> ux -> publishing -> development -> qa -> audit
```

Projects may override it, but downstream stages must receive predecessor evidence digests.

See [docs/awe-concepts.md](/Volumes/Extreme SSD/Hatchling-project/Hatchling/docs/awe-concepts.md), [docs/mvp-runtime.md](/Volumes/Extreme SSD/Hatchling-project/Hatchling/docs/mvp-runtime.md), and [docs/golem-integration-boundary.md](/Volumes/Extreme SSD/Hatchling-project/Hatchling/docs/golem-integration-boundary.md).

## Development

Run the current smoke tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Run a local no-op stage cycle:

```bash
PYTHONPATH=src python3 -m hatchling.cli smoke-run
```

## Next Development Order

1. Load `samples/work-capsules/basic.json` into typed `WorkCapsule` objects.
2. Add durable append-only `WorkRun` and `StageRun` journals.
3. Add provider adapters for Codex, Claude, Gemini, and local CLI.
4. Add budget accounting and stale lease rejection to the loop controller.
5. Add Markdown and JSON projections for run receipts.
6. Add signed runner envelopes and capability probes for local and external adapters.
7. Keep optimizer integrations optional and policy-gated.
