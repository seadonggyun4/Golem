# C Subsystem Architecture

Hatchling should be implemented as a C runtime kernel plus CLI, daemon, protocol tools, and language bindings.

## Target Layout

```text
hatchling/
  include/
    hatchling/
      core.h
      cli.h
      daemon.h
      evidence.h
      adapter_protocol.h
      cost.h
      policy.h
      journal.h
      error.h
      types.h

  src/
    core/
    evidence/
    adapter_protocol/
    cost/
    policy/
    daemon/
    cli/
    common/

  bindings/
    python/
    typescript/

  docs/
  project-docs/
  samples/
  tests/
  fuzz/
  bench/
```

## Subsystems

### `core`

The execution model.

Owns:

- `WorkCapsule`
- `WorkRun`
- `StageRun`
- `StageGraph`
- stage transition validation
- loop controller
- retry, cancel, timeout state
- completion preconditions

Does not own:

- provider SDKs
- file-system persistence
- optimizer internals
- UI

### `evidence`

The proof and receipt layer.

Owns:

- content-addressed storage
- digest calculation
- receipt creation
- artifact hash
- lineage records
- evidence verification
- append-only evidence record format

### `adapter_protocol`

The provider execution boundary.

Owns:

- `run_stage(input) -> result/evidence` envelope
- adapter capability probe
- JSON envelope
- MessagePack envelope
- signed envelope format
- subprocess adapter contract
- future gRPC bridge contract

The C core should prefer external adapter processes over embedding every provider SDK.

### `cost`

The common cost model.

Owns:

- `TokenUsage`
- `ProviderUsage`
- `CostEstimate`
- `CostLedger`
- `ProviderPriceBook`
- expected versus actual cost
- cache break-even calculation

This subsystem may expose optimizer-friendly data, but must not depend on any optimizer.

### `policy`

The decision boundary.

Owns:

- autonomy policy
- budget policy
- fallback policy
- optimization policy
- quality-constrained optimization
- no-op optimizer contract
- versioned policy artifact loading
- `ALLOW`, `ASK`, `DENY`

### `daemon`

The long-running local runtime.

Owns:

- local work queue
- concurrent work runs
- lease and heartbeat
- stale lease recovery
- adapter process supervision
- crash recovery
- journal replay

MVP may start with a single-process scheduler before introducing a background service.

### `cli`

The operational surface.

Owns commands such as:

- `hatchling init`
- `hatchling capsule validate`
- `hatchling run --noop`
- `hatchling stage`
- `hatchling evidence verify`
- `hatchling cost report`
- `hatchling replay`

### `common`

The C foundation.

Owns:

- error model
- arena allocator
- string/span primitives
- path safety
- clock
- file I/O wrappers
- logging
- JSON wrapper
- test helpers

`common` must stay boring, portable, and heavily tested.
