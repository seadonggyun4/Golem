# Public C API and Ownership Rules

The C implementation must expose a stable, explicit, boring API.

## Naming

All public symbols must use the `hatchling_` prefix.

Examples:

```c
hatchling_work_capsule_validate(...)
hatchling_stage_graph_next(...)
hatchling_evidence_verify(...)
hatchling_journal_replay(...)
```

Subsystem-private symbols must not be exported from public headers.

## Headers

Public headers live under `include/hatchling/`.

Internal headers may live under `src/<subsystem>/`.

## Ownership

Every function that returns allocated memory must make ownership obvious.

Recommended suffixes:

- `_init`: initializes caller-owned memory
- `_free`: releases owned resources
- `_borrow`: returns a non-owning view
- `_clone`: returns caller-owned copy
- `_from_*`: parses or constructs a value
- `_write_*`: writes into caller-provided buffer

## Error Handling

Public functions should return `hatchling_status`.

```c
typedef enum hatchling_status {
  HATCHLING_OK = 0,
  HATCHLING_ERR_INVALID_ARGUMENT,
  HATCHLING_ERR_OUT_OF_MEMORY,
  HATCHLING_ERR_PARSE,
  HATCHLING_ERR_POLICY_DENIED,
  HATCHLING_ERR_IO,
  HATCHLING_ERR_CORRUPT_JOURNAL
} hatchling_status;
```

Detailed diagnostics should be carried through a caller-owned `hatchling_error` or `hatchling_diagnostic` object.

## Allocation

The runtime should support caller-provided allocators.

Default allocation is allowed for CLI tools, but the core library should be embeddable.

Preferred patterns:

- arena allocation for short-lived parse/build operations
- explicit heap allocation for long-lived runtime objects
- caller-provided output buffers for serialization

## ABI Discipline

Public structs should either be:

- small plain value structs with fixed layout, or
- opaque handles with constructor/destructor functions

Do not expose unstable internal layout for large runtime objects.

## Serialization Boundary

Internal core uses C structs and binary journal records.

External boundaries may use:

- JSON for human-readable interop
- MessagePack for compact local adapter envelopes
- gRPC for future remote adapter/runtime communication

The core state machine must not depend on JSON as its internal format.
