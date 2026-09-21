# C Runtime Roadmap

The goal is a C work runtime kernel with CLI, daemon, evidence CAS, adapter protocol, cost layer, and policy layer.

## Phase 0: Build System and Common

Deliver:

- C build system
- `include/hatchling/types.h`
- `include/hatchling/error.h`
- common error model
- arena allocator
- string/span primitives
- file/path wrappers
- clock and logging
- first unit test harness

Exit criteria:

- warnings-as-errors build
- sanitizer smoke test
- common unit tests

## Phase 1: Core Structs and Stage Graph

Deliver:

- `WorkCapsule`
- `WorkRun`
- `StageRun`
- `StageGraph`
- transition validator
- failure reentry selector

Exit criteria:

- stage graph tests
- invalid transition tests
- no file I/O dependency in core

## Phase 2: Binary Journal and Replay

Deliver:

- append-only journal writer
- journal reader
- replay engine
- schema version
- golden fixtures

Exit criteria:

- valid replay
- corrupt journal rejection
- invalid transition rejection

## Phase 3: Evidence CAS and Digest

Deliver:

- digest API
- content-addressed storage
- evidence receipt
- artifact digest
- verification command

Exit criteria:

- digest mismatch detection
- evidence replay integration
- CLI smoke for evidence verify

## Phase 4: Policy, Budget, and Cost

Deliver:

- autonomy policy
- budget policy
- fallback policy
- cost ledger
- provider usage normalization
- cache break-even calculation
- no-op optimizer contract

Exit criteria:

- optimizer proposal cannot bypass policy
- expected/actual cost recorded per stage
- budget violation blocks stage run

## Phase 5: Adapter Envelope

Deliver:

- `run_stage` envelope
- JSON envelope
- MessagePack envelope
- capability probe
- signed envelope placeholder
- local no-op adapter

Exit criteria:

- no-op adapter stage run
- invalid envelope rejection
- parser fuzz smoke

## Phase 6: CLI

Deliver:

- `hatchling init`
- `hatchling capsule validate`
- `hatchling run --noop`
- `hatchling evidence verify`
- `hatchling replay`
- `hatchling cost report`

Exit criteria:

- CLI integration tests
- JSON and Markdown projections

## Phase 7: Daemon

Deliver:

- local queue
- scheduler
- lease heartbeat
- stale lease recovery
- adapter process supervision
- crash recovery through journal replay

Exit criteria:

- daemon restart recovers unfinished run
- stale lease cannot continue
- concurrent run smoke test

## Phase 8: Bindings

Deliver:

- Python binding
- TypeScript binding
- stable C ABI documentation
- example embedding

Exit criteria:

- bindings call core validation and replay
- ABI compatibility smoke
