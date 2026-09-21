# Testing and Quality Gates

C Hatchling must treat correctness, memory safety, replayability, and persistence compatibility as release gates.

## Compiler Gates

Required warning policy:

```text
-Wall
-Wextra
-Werror
-Wpedantic
```

Recommended sanitizer gates:

```text
ASAN
UBSAN
leak checks
```

## Test Layers

### Unit Tests

Cover:

- stage graph transitions
- policy decisions
- budget calculations
- digest verification
- path safety
- allocator behavior

### Golden Replay Tests

Cover:

- journal schema compatibility
- valid work run replay
- invalid transition rejection
- corrupt record handling
- missing evidence handling

### Fuzz Tests

Fuzz:

- journal parser
- JSON envelope parser
- MessagePack envelope parser
- evidence receipt parser
- policy artifact loader

### Integration Tests

Cover:

- CLI command behavior
- no-op adapter execution
- evidence CAS verification
- cost report generation
- replay from recorded journal

### Benchmarks

Measure:

- `StageRun` transition replay throughput
- evidence digest throughput
- journal append/read throughput
- adapter envelope encode/decode
- daemon queue throughput

## Release Gate

A release candidate must pass:

- compile with warnings as errors
- unit tests
- golden replay tests
- sanitizer tests
- parser fuzz smoke
- CLI smoke
- no forbidden runtime dependencies

## Forbidden Shortcuts

- Do not make JSON the internal state format.
- Do not make optimizer advice authoritative.
- Do not bypass evidence receipt creation.
- Do not continue from a stale lease.
- Do not add UI dependencies to the runtime core.
