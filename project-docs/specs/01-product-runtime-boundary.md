# Product and Runtime Boundary

Hatchling is the product implementation of `AWE — Agentic Work Engine`.

AWE is the category name. Hatchling is the product name.

## Product Definition

Hatchling is a headless work runtime engine. It exists to help agent providers carry work through a common lifecycle until the work reaches evidence-backed completion.

Hatchling is not:

- a UI client
- a document authoring tool
- an optimizer/proxy product
- a multi-tenant SaaS control plane by default
- a wrapper around one agent provider

## Runtime Responsibility

Hatchling owns:

- `WorkCapsule`
- `WorkRun`
- `StageRun`
- `StageGraph`
- lease and heartbeat
- retry, cancel, timeout, and reentry
- evidence requirement enforcement
- append-only journal and replay
- policy-gated adapter execution

Hatchling asks:

> What state is this work in, and which stage should run next?

## External Optimizer Boundary

An external optimizer such as Golem may propose lower-cost routing, cache use, compression, fallback, or budget changes.

Hatchling keeps final authority. It must reject optimizer proposals that violate:

- autonomy policy
- stage graph rules
- acceptance criteria
- evidence requirements
- safety boundaries
- budget rules

No Hatchling core subsystem may depend on Golem.
