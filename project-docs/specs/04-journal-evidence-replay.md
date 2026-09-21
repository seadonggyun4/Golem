# Journal, Evidence, and Replay

Hatchling must be replayable.

The runtime should be able to reconstruct `WorkRun` state from append-only records and verify that evidence receipts still match their content.

## Journal

The journal records state transitions, not arbitrary logs.

Initial record types:

- `WORK_RUN_CREATED`
- `STAGE_RUN_STARTED`
- `STAGE_RUN_COMPLETED`
- `STAGE_RUN_FAILED`
- `STAGE_REENTRY_SELECTED`
- `LEASE_ACQUIRED`
- `LEASE_HEARTBEAT`
- `LEASE_STALE`
- `POLICY_DECISION`
- `EVIDENCE_RECEIPT_ATTACHED`
- `COST_LEDGER_RECORDED`

## Binary First

The internal journal should be compact and deterministic.

JSON projection may be generated for inspection, but replay should use the durable binary journal or a carefully versioned compact format.

## Evidence CAS

Evidence storage is content-addressed.

Evidence records should include:

- schema version
- evidence kind
- digest algorithm
- digest
- payload length
- created timestamp
- optional stage/run linkage
- optional predecessor evidence digests

## Lineage

Trace lineage connects:

- stage input
- context block
- tool result
- adapter output
- artifact digest
- evidence digest
- cost ledger entry

Lineage is not just observability. It is part of replay, audit, and optimizer safety.

## Replay Gates

Replay must detect:

- corrupt record
- unknown schema version
- invalid transition
- missing evidence
- digest mismatch
- stale lease continuation
- cost ledger inconsistency

## Golden Tests

Every journal schema version must have golden replay fixtures.

A fixture should include:

- input records
- expected final state
- expected receipts
- expected cost ledger
- expected replay diagnostics
