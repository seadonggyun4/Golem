# Cost and Optimizer Boundary

Hatchling absorbs cost and budget primitives, not an optimizer product.

## Imported Concepts

From cost-optimizer research, Hatchling should include:

- token and cost ledger
- budget policy
- provider price normalization
- trace lineage
- fallback policy
- cache break-even calculation
- no-op optimizer contract
- quality-constrained optimization
- versioned policy artifact loading

## Hatchling-Owned Types

### `TokenUsage`

Tracks:

- input tokens
- cached input tokens
- output tokens
- reasoning tokens
- tool cost

### `ProviderUsage`

Tracks:

- provider
- model
- provider model revision when available
- normalized usage
- raw usage digest

### `CostLedger`

Records expected and actual cost per `StageRun`.

### `BudgetPolicy`

Defines stage-level limits:

- input budget
- output budget
- reasoning budget
- tool budget
- retry budget
- total billed cost budget

### `OptimizationProposal`

Represents an optional recommendation:

- `NO_OP`
- `ROUTE_PROVIDER`
- `COMPRESS_CONTEXT`
- `USE_CACHE`
- `FALLBACK`
- `ADJUST_BUDGET`

## No-Op Contract

If optimization overhead is greater than expected savings, Hatchling must choose `NO_OP`.

## Quality Constraint

Cost reduction is valid only if it preserves:

- acceptance criteria
- required evidence
- policy gates
- safety constraints
- replayability

## Dependency Rule

Hatchling may expose interfaces that an optimizer can implement.

Hatchling must not depend on Golem or any optimizer implementation.
