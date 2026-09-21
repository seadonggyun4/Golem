# AWE Concepts in Golem

`AWE — Agentic Work Engine` is the category name. `Golem` is the product and implementation.

Golem implements a headless runtime model for evidence-bound agent work. The central planning object is a `Work Capsule`; each execution is a `WorkRun` made of provider-specific `StageRun` attempts.

## Promoted Concepts

- `Work Capsule`: goal, scope, permissions, stage graph, acceptance criteria, expected artifacts, and required gates.
- `WorkRun`: one execution of a Work Capsule, with receipts for every stage.
- `StageRun`: one provider attempt at one stage, including status, attempt, lease, budget, evidence, and failure type.
- `Stage Graph`: default ordered graph of `planning -> ux -> publishing -> development -> qa -> audit`, with project override support.
- `Context Package`: stage input plus predecessor evidence digests.
- `Evidence`: content-addressed execution records, logs, artifact digests, test results, diff attestations, and reviewer output.
- `Decision`: policy outcome of `ALLOW`, `ASK`, or `DENY`.
- `Receipt`: evidence digest returned by a stage and attached to a WorkRun.

## Runtime Discipline

Golem keeps the runtime small and evidence-bound:

- status, attempt, budget, evidence, retry, and cancel shape
- lease and heartbeat checks
- stale lease rejection
- append-only evidence
- predecessor evidence digest requirements
- local runner enrollment, signed envelopes, and capability probes for adapters
