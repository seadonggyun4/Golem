# AWE Concepts in Golem

`AWE — Agentic Workflow Engine` is the category name. `Golem` is the product and implementation.

`Workflow` denotes the governed stages, transitions, verification, recovery, and
completion of agentic activity. `Work` denotes an individual managed unit of
work; existing Work types, API names, schemas, and stored evidence retain their
names. This terminology clarification does not change runtime behavior.

Golem is a lightweight headless engine for agents to collaborate through work
state and verification evidence. Agents decide what to do and how; Golem checks
state, dependencies, ownership, handoffs and configured acceptance contracts.
External CLI/API clients do not require a daemon or engine-owned agent launcher.
See the [responsibility contract](agent-golem-boundary.md).

The lower-level runtime represents a `Work Capsule` and `WorkRun` containing
`StageRun` attempts. Those types do not imply that Golem launches a provider for
every stage; the current-agent session/document workflow is a separate entry path.

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
- explicit adapter capabilities and trusted-host runner contracts where adopted;
  authenticated enrollment and signed envelopes are not universal guarantees
