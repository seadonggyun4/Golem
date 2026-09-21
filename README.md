# Golem

Golem is the product implementation of `AWE — Agentic Work Engine`.

AWE is the academic/category name. Golem is the product name.

## Name and Role

**Golem (골램) = AWE. Hatchling (헤츨링) = AWO.** These product names were reassigned on 2026-09-21; the work-engine and optimizer responsibilities did not change.

Golem expresses assembling agents, tools, policies, and execution stages into a working whole. Hatchling is the independent cost optimizer, inspired by a young dragon guarding a hoard of gold: it conserves service execution spending while respecting quality and safety requirements.

The work engine is developed first, followed by the optimizer, and both are used to improve the owner's services. Research and patent candidates are collected from real engineering problems and measured improvements, not treated as prerequisites for product development.

The runtime CLI, Python import, and C API now use `golem`, and the CMake package is `Golem`. See [the naming and migration decision](docs/product-naming.md). Hatchling must not be used as an alias for this runtime.

Golem is a headless execution engine that lets multiple agent providers run the same work cycle. It is not a document-writing tool. It is a headless work runtime that helps agents carry work through to completion, while recording every execution as documents and evidence.

## Product Boundary

Golem stays headless until the execution engine is useful on its own.

- No UI client in the runtime package.
- CLI, JSON, and Markdown projection are allowed.
- Every execution must leave evidence.
- Agent providers must share the same `run_stage(input) -> result/evidence` contract.
- Local autonomy is explicit and policy bounded.

## Runtime Direction

Golem is moving toward a C implementation of a work runtime kernel plus CLI, daemon, evidence CAS, adapter protocol, cost layer, and policy layer.

The current Python package is a smoke-testable prototype for the core model.

## Runtime MVP

The C foundation lives under `include/golem/`, `src/common/`, and `src/core/`.
The core implements owned WorkCapsule/WorkRun models, StageRun snapshots,
sequential StageGraph overrides, validated lifecycle transitions, bounded
failure reentry, cancellation, and stale attempt-result rejection.
The journal subsystem implements versioned binary frames, CRC32 checksums,
strict readers, a POSIX append-only file writer, and transactional Core replay.
The replay engine accepts arbitrarily split input chunks, publishes a WorkRun
only after successful final validation, and returns an explicit recovery report.
Locked file recovery reuses the journal descriptor and retains its writer lock.
The evidence subsystem provides SHA-256 content-addressed storage, streaming
artifact import, versioned binary receipts, and a C verification CLI. Objects use
`objects/sha256/<first-two-hex>/<remaining-62-hex>` under a caller-owned store.
Publication never overwrites existing keys; duplicate writes reverify content.
The lineage model connects stage inputs, context blocks, tool results, artifacts
and evidence in an append-only dependency DAG. Each execution is identified by
WorkRun ID, sequence, stage and attempt. Direct/transitive predecessor queries
retain retry and reentry history; equal content used by different attempts keeps
distinct node identities. Sealed graphs have a versioned binary format and can
be stored in CAS, loaded, and verified together with all referenced content.
Other subsystem headers still reserve opaque types for future implementation.

Policy Core returns structured `ALLOW`, `ASK`, or `DENY` decisions with stable
reason codes. The actual StageRun start gate reevaluates permissions from the
run's immutable Capsule. Unknown effects and explicit authorization rejection
deny execution; a grant never overrides a DENY stage. Permission checks and
stage-start gating perform no heap allocation or I/O.

Core operations perform no I/O and allocate only when creating model owners.
Allocator-aware constructors copy per-object allocator callbacks; existing
constructors retain the default C heap behavior. Matching destructors use the
stored allocator. Optional caller-owned diagnostics require no allocation.
Capsules and runs copy their inputs; runtime mutations do not allocate.
Reentry invalidates downstream completion while retaining attempt counts.
Policy, stale-lease, and budget failures block automatic reentry.

Stage success currently requires a caller attestation that acceptance,
artifacts, gates, and evidence requirements are satisfied. This is an in-memory
model contract, not evidence-store verification or durable execution history.
CAS-verified adapter dispatch is available; connecting verified results to
completion gates and real provider execution remain future work. Optional local
runtime lease enforcement is available through the C API described below.
Journal replay reconstructs the current model from recorded attestations.

Common memory APIs provide a caller-backed fixed-capacity arena, borrowed byte
and string views, checked slices, and caller-owned buffer writes. Short buffers
are left untouched and report the required size; text sizes include the trailing
NUL. Ownership and lifetime contracts are documented in the installed headers.

Each journal stores one WorkRun. Its first record includes the Capsule, graph,
permissions, run ID, and attempt limit. Later records describe stage starts,
finishes, reentry, and cancellation. The v1 format uses explicit little-endian
fields, contiguous sequence numbers, a 32-byte header, and bounded payloads.

The file backend currently targets macOS/Linux. It holds an advisory writer lock,
opens with append semantics, and syncs each successful append. It rejects corrupt
or partial existing streams without truncation. CRC32 is corruption detection,
not authentication. Core mutations and journal writes are still separate APIs;
a durable execution coordinator must define their ordering in a later phase.

Recovery preserves unfinished attempts. A recovered RUNNING stage requires
reconciliation with its external execution; it is never automatically retried.
Sequence gaps detect missing middle records. Optional expected run identity and
an exact record-count/byte-length boundary detect the wrong stream and complete
tail-record loss. Without separately retained endpoint metadata, a complete
record prefix cannot be distinguished from an intentionally unfinished run.

The Python prototype lives under `src/golem/`:

- `core`: Work Capsule, WorkRun, StageRun, Stage Graph, Context Package, Decision, and EvidenceRef models.
- `runtime`: loop controller and lease/heartbeat primitives.
- `evidence`: content-addressed evidence store with redaction checks.
- `adapters`: provider contract plus a local no-op adapter for smoke runs.
- `policies`: autonomy boundaries such as `AUTO_LOCAL`, `ASK_ON_EXTERNAL_EFFECT`, `ASK_ALWAYS`, and `DENY`.
- `core.optimization`: optional cost/budget/usage interfaces for optimizers such as Hatchling, with no runtime dependency.

The default stage graph is:

```text
planning -> ux -> publishing -> development -> qa -> audit
```

Projects may override it, but downstream stages must receive predecessor evidence digests.

See [AWE concepts](docs/awe-concepts.md), [MVP runtime](docs/mvp-runtime.md), and [Hatchling integration boundary](docs/hatchling-integration-boundary.md).

## Development

The C build requires CMake 3.21+, Ninja, a C17 compiler, OpenSSL 3 development
headers/libraries (Crypto component), pkg-config, and json-c 0.15+.
No provider or optimizer dependency is required.
Install `openssl@3`, `pkg-config`, and `json-c` with Homebrew on macOS, or
`libssl-dev`, `pkg-config`, and `libjson-c-dev` on Debian/Ubuntu.
For nonstandard installations, pass `-DOPENSSL_ROOT_DIR=/path/to/openssl` to CMake.

```bash
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

Use the `asan` preset for combined AddressSanitizer/UndefinedBehaviorSanitizer checks,
or `release` for optimized builds. Both use the same configure/build/test commands.
Project targets compile with `-Wall -Wextra -Wpedantic -Werror` on GCC/Clang.
Warning flags stay private to Golem; sanitizer link requirements propagate to consumers.
Tests keep their checks enabled in Release builds.

The static library installs with public headers and a relocatable CMake package:

```bash
cmake --install build/release --prefix "$PWD/build/install"
cmake -S tests/consumer -B build/consumer -G Ninja -DCMAKE_PREFIX_PATH="$PWD/build/install"
cmake --build build/consumer
ctest --test-dir build/consumer --output-on-failure
```

Consumers use `find_package(Golem CONFIG REQUIRED)` and link `Golem::golem`.
The installed CMake package resolves its OpenSSL and json-c dependencies automatically.
The pre-1.0 public API is experimental; binary compatibility is not promised.

## Evidence CLI

The C executable is `build/dev/golem`, installed as `bin/golem`.
Set `GOLEM_BUILD_CLI=OFF` for a library-only build. Commands emit JSON on
success, diagnostics on stderr on failure, and return 0 (success), 1 (operation
failure), or 2 (usage error).

```bash
build/dev/golem evidence hash ARTIFACT_FILE
build/dev/golem evidence put EXISTING_STORE_DIRECTORY ARTIFACT_FILE
build/dev/golem evidence verify EXISTING_STORE_DIRECTORY SHA256_HEX
build/dev/golem evidence verify-receipt EXISTING_STORE_DIRECTORY RECEIPT_SHA256_HEX
```

`put` stores the artifact and a canonical receipt as separate CAS objects,
returning both digests. `verify` hashes the object without modifying the store;
`verify-receipt` also checks the receipt's schema and the artifact's recorded size.
Keys are exactly 64 lowercase hexadecimal characters. Files and all path
components must be non-symlinks; parent traversal (`..`) is rejected.

Use a privately controlled local store. SHA-256 verifies bytes against an expected
key, not provenance or authorization. Inputs are not automatically redacted.
Successful publication syncs files and directories; an I/O failure may still
leave a complete object, and a process crash can leave an unreferenced temporary
file. Automatic cleanup and atomic journal/receipt association are not yet implemented.

## Lineage CLI

```bash
build/dev/golem lineage verify EXISTING_STORE_DIRECTORY GRAPH_SHA256_HEX
build/dev/golem lineage trace EXISTING_STORE_DIRECTORY GRAPH_SHA256_HEX STAGE_SEQUENCE
build/dev/golem lineage trace EXISTING_STORE_DIRECTORY GRAPH_SHA256_HEX STAGE_SEQUENCE --direct
```

Both commands are read-only and verify the graph plus referenced evidence before
emitting JSON. Trace results contain predecessor node IDs, producer stages,
sequences, attempts, content digests and sizes. The graph digest scopes the result;
the C API also exposes the graph's WorkRun ID.

Use the C lineage API to begin tracking a RUNNING StageRun, append dependent
nodes, and seal it against its terminal Core snapshot. Each stage requires an
input and at least one evidence node. Later attempts explicitly select earlier
evidence as predecessors; selection records provenance relationships, not policy
approval or proof that an earlier successful attempt is still current.
Graphs preallocate caller-selected bounded capacities. Sealed graph checkpoints
are independent of journal transactions; automatic runtime attachment, active
branch policy and recovery of an unsealed draft remain future work.

Run the Python prototype regression tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Run a local no-op stage cycle:

```bash
PYTHONPATH=src python3 -m golem.cli smoke-run
```

## Policy Core

`include/golem/policy.h` exposes immutable standalone policies for planning
and the execution-gate APIs `golem_work_run_permission_request` and
`golem_work_run_begin_authorized`. A new policy spec initializes all stages
to DENY. Standalone policy tables can be copied into Capsule permissions; an
unrelated permissive policy object cannot override an existing run's Capsule.

| Stage Permission | Local, No Grant | External, No Grant | Valid Caller Grant |
| --- | --- | --- | --- |
| DENY | DENY | DENY | DENY |
| AUTO_LOCAL | ALLOW | ASK | ALLOW for known effects |
| ASK_ON_EXTERNAL_EFFECT | ALLOW | ASK | ALLOW for known effects |
| ASK_ALWAYS | ASK | ASK | ALLOW for known effects |

UNKNOWN effects always deny; explicit REJECTED authorization denies even local
autonomous work. `ASK` signals the caller to obtain authorization, without opening
a dialog or requiring an enterprise human-approval system. It returns
`GOLEM_ERR_APPROVAL_REQUIRED`; DENY returns `GOLEM_ERR_POLICY_DENIED`.
Neither consumes an attempt or changes the READY run. The new request must match
the next run ID/stage/sequence/attempt. Retrying an old request after reentry is
rejected, and a fresh request starts without a grant.

Effect classification and authorization are trusted caller attestations, not
signed capabilities or a sandbox. Callers must reauthorize changed scope/effects
and enforce permissions on later adapter/tool actions. The old boolean
`golem_work_run_begin` uses the same evaluator but retains its legacy combined
POLICY_DENIED result for ASK/DENY; it does not provide scoped approval checking.
Journal v1 remains compatible and retains Capsule permissions on replay. Policy
decision persistence, authenticated grants/revocation and OS-level sandboxing are
not yet implemented. Adapter dispatch enforces the admitted effect boundary.

## Budget and Cost Core

`include/golem/cost.h` provides provider-independent token usage, integer
nano-currency amounts, estimates, actual provider reports and per-attempt ledgers.
Input/cache-read and output/reasoning buckets are disjoint; adapters must normalize
provider-specific totals before submitting them. Rates are caller-supplied, with
provider/model/price-revision metadata retained on each actual report.

Enable accounting with `golem_work_run_cost_enable` before the first attempt.
Set currency, entry/report capacities and optional run/stage budgets. Storage is
allocated once with the WorkRun allocator and released with the run. Every
successful start, including the legacy API, then creates one ledger entry.
Failed admission creates none. Retries get separate sequence/attempt identities;
failed and cancelled attempts retain their charges.

1. Plan the next sequence with `golem_work_run_cost_plan`.
2. Start through the normal policy gate; configured budgets also check admission.
3. Append incremental provider calls using `golem_work_run_cost_report`.
4. Finish/cancel the attempt, then call `golem_work_run_cost_settle` when all
   provider reports have arrived. A known-zero report explicitly accounts for no-op work.
5. Query entry, provider report, stage totals or run totals as copied values.

Unknown is not zero. Enforced budgets reject incomplete required estimates or
prior accounting. Actual over-budget charges are recorded, not discarded;
subsequent admission checks use actual cumulative totals, including retries.
Identical duplicate report IDs within an attempt are idempotent; conflicting
duplicates and new reports after settlement are rejected. One first-report slot
is reserved per admitted attempt; adapters must bound additional calls before
dispatch. Capacity/overflow errors never silently drop an accepted report.

Start, settlement, totals and entry lookup are O(1); report deduplication scans
only that attempt's reports. No allocations occur after accounting is enabled.
Unconfigured legacy runs remain unmetered, not free. Journal v1 has no cost events:
replay does not restore estimates, charges or budget settings. Durable cost
receipts, billing recovery, corrections, active-call budget enforcement and a
cost-report CLI remain future work. Hatchling is not a dependency.

## Optimizer Boundary

`include/golem/optimization.h` defines an optional advisor boundary without
linking Hatchling or any provider. Advisors may propose `NOOP`, `ROUTE`, `CACHE` or
`FALLBACK`; they cannot supply grants, replace Capsule permissions, change budgets
or waive acceptance/evidence gates. Route IDs are host-resolved adapter references,
never executable commands.

Enable cost accounting, then `golem_work_run_optimization_enable` on a pristine
run. The copied policy defaults to no optimization and configures allowed actions
per stage, minimum savings and fallback triggers/counts. Host-trusted context
contains verified routes, prices, effects, quality requirements and cache checks.
Do not deserialize an advisor response into that trusted context.

`golem_work_run_optimization_evaluate` is a side-effect-free selection query.
Its `APPLY` result is not execution permission. `golem_work_run_begin_optimized`
evaluates again and calls the same Capsule permission and budget gate as ordinary
starts, atomically recording the selected estimate only on success. Failed starts
preserve counters, cost entries and any pending cost plan. Approval must name the
selected route; the host must reauthorize changed scope/effects/context.

- Missing advisor, explicit NOOP or insufficient net savings keeps an available
  baseline. Equal savings and overhead is NOOP. Advisor overhead remains included.
- Cache break-even uses checked integers: setup plus reads times cached-read cost
  must be strictly below reads times uncached-read cost. Only this attempt's reads
  count; cache verification is a separate host responsibility.
- Fallback has an immutable trigger allowlist, optional local-only restriction and
  a per-stage cumulative count. Policy denial and quality failure cannot trigger
  it; changing a fallback proposal's label to ROUTE/CACHE does not bypass the checks.
  These host-observed failures also reject absent-advisor, disabled and NOOP paths;
  they cannot implicitly resume an available baseline.
- Effective effects conservatively include baseline, selected route and advisor.
  A cheaper local proposal cannot silently downgrade a required external approval.

The boundary does not contact Hatchling, execute adapters, verify signatures or persist
proposals. External advisor contact must itself be authorized before it happens.
Host attestations are not cryptographic proof; normal completion gates still run.
Journal v1 does not restore optimizer policies/counts, and actual optimizer charges
must be reported explicitly rather than inferred from estimates. Wire codecs,
durable decision receipts, signed policy artifacts and a Hatchling-side bridge remain
separate follow-up work.

## Adapter Protocol

`include/golem/adapter_protocol.h` defines versioned capability, `run_stage`,
and stage-result envelopes. An adapter is a copied callback table with a borrowed
implementation context. The Core does not link provider SDKs or Hatchling. Inputs
reference context/predecessor CAS objects; results bind the original attempt and
return an evidence receipt, terminal outcome, simulation flag and normalized usage.

Runtime dispatch accepts only an admitted RUNNING attempt. It checks identity,
supported stage, admitted effects and input CAS before invoking the implementation,
then validates response identity and evidence. Optimized starts also bind the
selected route ID to the adapter ID and retain context/predecessor digests.
Register route-specific handles when one provider serves multiple routes.
Preflight rejection permits correction; once invoked, the attempt cannot dispatch
again, even after callback failure. Replayed unfinished attempts require explicit
reconciliation, never blind redispatch.

```bash
build/dev/golem adapter noop probe
build/dev/golem adapter noop run EXISTING_STORE_DIRECTORY < request.json
```

The standalone noop worker accepts one bounded JSON request on stdin and returns
one result on stdout. It verifies inputs and writes deterministic simulation
evidence. It is a transport fixture, not a WorkRun authorization entry point.
`simulation=true` in the C API (`"simulation":"1"` on the wire) means no real task
was performed. Neither the worker nor dispatch finishes stages or settles billing;
the host must evaluate acceptance and record provider/currency-specific usage.

JSON v1 is a flat string-valued object, capped at 16 KiB. Numeric fields use
canonical unsigned decimal strings to preserve uint64 precision. The public C
codec is the reference schema: message types are capability=1, run_stage=2,
stage_result=3; other enums match the installed headers. IDs are bounded portable
ASCII. Missing, unknown or duplicate keys, nested values, embedded NUL, invalid
UTF-8 and trailing documents are rejected. CAS verifies bytes, not provenance.
Callbacks are trusted, serialized in-process implementations, not a sandbox.
Dispatch markers are in memory; journal v1 does not promise exactly-once effects.
Signed enrollment, real subprocess supervision, gRPC and automatic
lineage/cost/result persistence remain separate work.

## Compact Transport

`golem_adapter_msgpack_encode/decode` translates the same envelopes without
heap allocation or recursive parsing. JSON and MessagePack share field definitions,
range checks and semantic validation. Existing JSON v1 output is unchanged.
The bounded MessagePack profile uses a flat map with unsigned integer keys,
unsigned numbers, native booleans, ASCII ID strings and 32-byte binary digests.
It follows the [MessagePack format specification](https://github.com/msgpack/msgpack/blob/master/spec.md)
but deliberately rejects types outside this protocol, including signed integers,
floats, arrays, nested maps, nil and extensions. This is not a general-purpose parser.

Encoding is deterministic: ascending keys and minimal integer/length widths.
Decoding accepts reordered keys and wider unsigned/length encodings. It rejects
duplicates, missing/unknown fields, wrong types, invalid IDs, oversized lengths
and trailing bytes. Binary input is capped at 4096 bytes. Binary `required` is the
exact byte length without a terminator; short buffers remain untouched.

Stable v1 field IDs (never renumbered):

| IDs | Fields, In Order |
| --- | --- |
| 0..4 | type, version, request_id, run_id, adapter_id |
| 5..10 | stage, sequence, attempt, context_version, context_algorithm, context_size |
| 11..16 | context_digest, has_predecessor, predecessor_digest, stages, effect, simulation |
| 17..22 | outcome, failure, evidence_version, evidence_algorithm, evidence_size, evidence_digest |
| 23..30 | input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, tool_calls, nano_cost, usage_known, cost_known |

Capability requires IDs 0,1,4,14,15,16; request requires 0..13; result requires
0..13 and 16..30. Enums retain the public C values. Sample capability/request/result
fixtures occupy 23/115/180 bytes versus 96/390/744 JSON bytes; real sizes vary.

```bash
build/dev/golem adapter noop probe --format msgpack
build/dev/golem adapter convert json msgpack < request.json > request.msgpack
build/dev/golem adapter noop run EXISTING_STORE_DIRECTORY --format msgpack < request.msgpack > result.msgpack
build/dev/golem adapter convert msgpack json < result.msgpack
```

Binary stdout has no newline or framing; stdin accepts exactly one envelope.
Conversion validates structure, not authorization or CAS references. No format
auto-detection, network listener or automatic fallback to unsigned input exists.

`include/golem/gateway.h` provides an in-memory signed-envelope **placeholder**:
version, explicit encoding, borrowed immutable payload, exact-byte SHA-256 digest
and reserved signature metadata. Preparation creates only unsigned wrappers.
`GOLEM_GATEWAY_REQUIRE_SIGNATURE` is the zero/default trust mode and always
returns POLICY_DENIED in this phase. Local tooling must explicitly select
`GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL`; even then, any signature/key claim is
rejected. Digest validation is not authentication, and no verified flag is accepted.
The wrapper is not a serialized frame. Actual signing requires a specified signed
transcript, trusted key enrollment, freshness/replay controls and a real verifier.

An optional Clang libFuzzer target exercises JSON/MessagePack roundtrips (the
existing target name is retained). Normal CTest also runs deterministic mutations
without libFuzzer: 15000 JSON and 30000 MessagePack inputs. The fuzz target requires
a compiler installation that includes libFuzzer (on macOS, Homebrew LLVM rather
than the default Command Line Tools; set `CMAKE_C_COMPILER` accordingly):

```bash
cmake -S . -B build/fuzz -G Ninja -DGOLEM_BUILD_FUZZERS=ON -DGOLEM_ENABLE_SANITIZERS=ON -DBUILD_TESTING=OFF -DGOLEM_BUILD_CLI=OFF
cmake --build build/fuzz
cmake -E copy_directory fuzz/corpus/adapter_json build/fuzz/corpus
build/fuzz/golem_fuzz_adapter_json -runs=10000 -max_len=16385 build/fuzz/corpus
```

Use a disposable build-directory corpus; do not use source seeds as writable output.

## C CLI MVP

The C executable is `build/dev/golem`, distinct from the retained Python
prototype entry point. It requires no Python at runtime; Python 3 is used by
the black-box integration tests when `BUILD_TESTING` and the CLI are enabled.

```bash
build/dev/golem init /absolute/private/path/new-project
build/dev/golem capsule validate /absolute/private/path/new-project/capsule.json
build/dev/golem run --noop /absolute/private/path/new-project/capsule.json --output /absolute/private/path/new-run
build/dev/golem replay /absolute/private/path/new-run
build/dev/golem cost report /absolute/private/path/new-run
build/dev/golem evidence verify /absolute/private/path/new-run/evidence SHA256
build/dev/golem replay /absolute/private/path/new-run/journal.bin --require-terminal
```

Parents must exist; `init` and `run` require NEW target directories and never
overwrite an existing run. Keep capsules, runs and internal development documents
outside the checkout. Symlink components and `..` are rejected. The CLI does not
encrypt files or provide a sandbox against a hostile owner of the parent directory.
New directories use mode 0700 and projection files 0600, subject to umask.

Capsule JSON v1 contains `id`, `goal`, `scope`, `permissions`, `stages`,
`acceptance`, `expected_artifacts`, and `required_gates`. `schema_version: 1` is
recommended; omission supports the existing sample. Unknown/duplicate fields,
invalid UTF-8, ambiguous types and missing active-stage permissions are rejected.
Acceptance supports strings or sample-compatible `{id,text,required_gates}` objects;
referenced gates must be declared. The Core currently retains acceptance text,
not an executable acceptance evaluator. Unique stage subsets/reordering are allowed.
Input capsules are limited to 128 KiB; JSON depth is capped at 16.

Noop execution uses the real policy, stage lifecycle, adapter dispatch, CAS and
cost ledger. It never grants approval: ASK_ALWAYS and DENY cannot execute.
Each successful stage has a `stage-N.json` result with context and predecessor
evidence receipts. The bundle stores the original capsule, `journal.bin`,
`evidence/`, `cost.json` and a final `complete.json` digest manifest. Journal
STARTED is synced before dispatch; FINISHED follows the persisted result.
The completion marker is published last without overwrite. Failed operations may
leave an incomplete directory for inspection; no automatic deletion or retry occurs.

**SUCCEEDED means the noop simulation completed, not that the user's task was
accepted.** JSON explicitly reports `simulation: "verified_noop"` and
`acceptance_verified: false`. Actual providers, business gates, leases, daemon
supervision and automatic crash recovery are not part of this CLI MVP.

Bundle replay and cost reports are read-only. They validate capsule/journal
agreement, policy admission, exact stage order, result identities, predecessor
links, CAS digests/sizes and the completion manifest. Cost is rebuilt from the
recorded known-zero local/noop usage through the ledger and compared with the
stored report, never inferred from absence. The generated v1 bundle projections
are canonical exact-byte records: manual reformatting invalidates the bundle.
Digest manifests detect corruption, not authenticity or trusted agent provenance.

Without a completion marker, replay inspects only the journal and returns
`bundle_verified: false`; cost reporting refuses incomplete bundles. Raw journal
replay accepts valid unfinished prefixes unless `--require-terminal` is supplied.
Partial frames, sequence gaps and invalid transitions fail. A valid prefix alone
cannot prove that a whole-record tail was not lost. Read-only CLI files are capped
at 2 MiB; larger long-running streams require a future streaming command.

Successful data commands emit one JSON object to stdout. Diagnostics use stderr;
exit codes are 0 (success), 1 (validation/runtime/I/O failure), 2 (usage error).
Token/cost counters use decimal strings, not imprecise JSON floating-point values.

## Local Runtime Loop

`include/golem/runtime.h` exposes an embeddable, single-process C execution
loop. `golem_runtime_create` owns a fresh WorkRun; `step` runs at most one
attempt and `drive` runs until success or a latched stop. Callbacks provide a
durable journal sink, synchronous local execution and optionally a monotonic clock.
The executor can use the existing adapter dispatch and CAS APIs. A required record
sink prevents execution without a journal integration; no network, daemon or UI
is introduced. Runtime construction performs no I/O.

Every attempt uses Core policy admission with LOCAL effects and no approval grant.
Retries use the capsule's StageGraph, not a hard-coded development fallback:

| QA Failure | Default Reentry |
| --- | --- |
| PLANNING_GAP | planning |
| UX_MISMATCH | ux |
| PUBLISHING_GAP | publishing |
| IMPLEMENTATION_DEFECT | development |
| QA_FLAKE | qa |
| AUDIT_GAP | planning |
| TIMEOUT | current stage |

Graph overrides are respected; missing/forward targets and unclassified failures
stop. Core per-stage attempt limits include invalidated passes; a separate total
dispatch cap bounds the loop. Policy, stale-lease and budget failures never reenter.
Lease ownership is an explicit opt-in binding described below; the runtime does
not automatically acquire or renew ownership.

The sink receives CREATED before execution, STARTED before the executor, FINISHED
after a valid result, and REENTERED before the next admission. It can directly call
`golem_journal_append`. Any sink, clock or executor error permanently stops that
runtime instance: effects might already exist, so there is no blind retry. Inspect
`golem_runtime_report_get` and reconcile the durable journal externally.
Cancellation is supported between steps and is journaled; it is not an interrupt.

Timeout is a **cooperative deadline**, not process termination. The callback must
return with its work quiescent. A valid result returning at/after the deadline
becomes a classified TIMEOUT (blocking failures keep their stronger classification).
An executor error is never converted into retryable timeout. A hung in-process
callback cannot be killed by this API; subprocess supervision is future work.

Acceptance and durable evidence remain explicit trusted-host responsibilities.
Returning PASSED does not infer acceptance: `requirements_met` must be attested.
Journal v1 still does not persist generic cost ledgers or timeout configuration.
The Phase 12 `run --noop` bundle command retains its fixed simulation contract;
this new embedding API does not silently change its format or enable CLI retries.
`tests/c/test_runtime_adapter.c` exercises the complete runtime/adapter/CAS/file
journal path with simulated classified QA failures and restart-time replay.

## Lease and Heartbeat

`include/golem/lease.h` provides one serialized, in-process authority per work
resource. Acquire returns a value token with a random authority incarnation and
monotonically increasing fencing generation. A live lease cannot be acquired again,
even by the same owner; heartbeat renews it. Expiry equality is stale. Release or
expired-lease reacquisition invalidates the old token, including late heartbeat
and release calls. Heartbeat cannot resurrect an expired token or shorten its TTL.

Use `golem_runtime_lease_bind` once before the first step, with the WorkRun ID
as the lease resource. The runtime borrows the authority and copies the token;
free the runtime before freeing the authority. Runtime and authority must share
one monotonic clock domain. `golem_runtime_heartbeat` is explicit and can be
called inside the synchronous executor; `golem_runtime_checkpoint` guards
custom tool continuations. There is no background renewal thread.

Bound runs enforce ownership at admission, reentry, cancellation, Core completion,
and before/after adapter callbacks. Expiry, takeover, release, backward clocks or
ambiguous heartbeat persistence stop the runtime permanently. Ignoring an executor
checkpoint error cannot turn a late result into success. A stopped instance cannot
rebind to a new token. Its unfinished journal must be reconciled, not blindly retried.
Already-written evidence and actual external effects are not rolled back.

An append-only audit sink is mandatory for acquire/heartbeat/release. It receives
versioned token/snapshot values, ordered event sequence and monotonic observation
time; its success must mean durable storage. Serialize fields explicitly, never
native C struct bytes. Sink errors poison the authority because commit outcome may
be uncertain. These records are distinct from journal v1 work events; replaying a
work journal never restores a lease. A new authority incarnation rejects old tokens.

**Scope:** this is not a cross-process/distributed lock or cryptographic credential.
All access must be serialized by a trusted host sharing the same authority object.
Two independent authorities for the same resource do not coordinate. Long-running
callbacks must checkpoint cooperatively; no hard preemption exists. Core acceptance
is checked before mutation, but the work journal and lease audit are not one atomic
transaction: expiry during journal I/O may leave a committed event and a stopped
runtime requiring reconciliation. Remote effects need downstream fencing support.
Existing unbound runtime callers and CLI noop bundles retain their prior behavior.

## Next Development Order

1. Extend the noop coordinator with durable provider dispatch/reconciliation records.
2. Add executable acceptance/gate evaluators and preserve structured acceptance identity.
3. Add provider adapters for Codex, Claude, Gemini, and local CLI.
4. Generalize persisted billing and add cross-process lease authority/recovery without reusing old tokens.
5. Add Markdown and JSON projections for run receipts.
6. Extend the capability protocol with signed runner enrollment and envelopes.
7. Add optional optimizer wire bridges and durable decision receipts using the implemented boundary.
