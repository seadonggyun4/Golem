# Golem

**Awaken the worker.**

Golem is the product implementation of `AWE — Agentic Work Engine`.

AWE is the academic/category name. Golem is the product name.

## Public Alpha

The C17 runtime and CLI are available for **local noop evaluation** on macOS
and Linux. This is an alpha engineering milestone, not a production or security
certification. No provider account, API key, Python runtime package, Node.js,
UI or external optimizer is required to run the C CLI.

Prerequisites: C17 compiler, Git, CMake 3.21+, Ninja, Python 3.11+ for tests,
OpenSSL 3 development files, pkg-config and json-c 0.15+.

```sh
# Debian/Ubuntu dependencies:
sudo apt-get install build-essential git cmake ninja-build python3 libssl-dev pkg-config libjson-c-dev
# macOS alternative (with Xcode command-line tools installed):
# brew install cmake ninja openssl@3 pkg-config json-c python

git clone https://github.com/seadonggyun4/Golem.git
cd Golem
cmake --preset release
cmake --build --preset release
ctest --preset release

# New private directories; existing runs are never overwritten.
GOLEM_ALPHA_ROOT="$(mktemp -d)"
GOLEM_ALPHA_ROOT="$(cd "$GOLEM_ALPHA_ROOT" && pwd -P)"
printf 'Alpha workspace: %s\n' "$GOLEM_ALPHA_ROOT"
build/release/golem init "$GOLEM_ALPHA_ROOT/project"
build/release/golem capsule validate "$GOLEM_ALPHA_ROOT/project/capsule.json"
build/release/golem run --noop "$GOLEM_ALPHA_ROOT/project/capsule.json" --output "$GOLEM_ALPHA_ROOT/run"
build/release/golem replay "$GOLEM_ALPHA_ROOT/run"
build/release/golem cost report "$GOLEM_ALPHA_ROOT/run"
```

Expected: `SUCCEEDED`, `simulation: "verified_noop"`, six cost entries with
known-zero usage and cost, and `acceptance_verified: false`. Replay of the
complete bundle verifies its manifest, stage evidence and predecessor links.
Noop completion does **not** mean real work or business acceptance was verified.
Keep the printed/private temporary path for inspection; no cleanup is automatic.

Run `python3 tools/verify_alpha.py` for the reproducible acceptance gate. It
copies only Git-visible C build inputs (including pending local source changes)
into a temporary source tree, builds without a previous CMake cache, runs all C
tests, installs the library/CLI, and tests the installed C consumer and CLI.
The installed CLI contract covers init, validation, noop, evidence verification,
journal replay, cost reconstruction, policy rejection and corruption rejection.
Temporary gate data is deleted on exit; nothing is published or uploaded.
This is a clean-source check, not a secret scanner or distribution packager.
CI runs it from fresh Git checkouts on macOS/Linux.

Alpha API/ABI and storage formats may change; no automatic migration or stable
compatibility promise is made. Use disposable non-sensitive workspaces. Real
provider execution, authenticated runner enrollment, hostile-process sandboxing,
verified business gates and distributed exactly-once effects are not provided.
Bindings remain optional. A license must be selected by the repository owner
before representing this code as licensed open-source software.

## Name and Role

**Golem (골램) implements AWE.** Its responsibility is durable, policy-bounded work execution.

Golem assembles agents, tools, policies, and execution stages into a working whole.

Development is driven by real work execution, service improvements, and measured engineering results.

The runtime CLI, Python import, and C API use `golem`, and the CMake package is `Golem`.

Golem is a headless execution engine that lets multiple agent providers run the same work cycle. It is not a document-writing tool. It is a headless work runtime that helps agents carry work through to completion, while recording every execution as documents and evidence.

## Product Boundary

Golem stays headless until the execution engine is useful on its own.

- No UI client in the runtime package.
- CLI, JSON, and Markdown projection are allowed.
- Every execution must leave evidence.
- Agent providers must share the same `run_stage(input) -> result/evidence` contract.
- Local autonomy is explicit and policy bounded.

## Runtime Direction

Golem implements a C work runtime kernel plus CLI, daemon, evidence CAS, adapter protocol, cost layer, and policy layer.

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
not authentication. Core mutations and journal writes remain separate APIs;
the local runtime and daemon below define their durable execution ordering.

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
- `core.optimization`: optional cost/budget/usage interfaces for independent advisors, with no optimizer dependency.

The default stage graph is:

```text
planning -> ux -> publishing -> development -> qa -> audit
```

Projects may override it, but downstream stages must receive predecessor evidence digests.

See [AWE concepts](docs/awe-concepts.md) and [MVP runtime](docs/mvp-runtime.md).

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
replay does not restore estimates, charges or budget settings. The noop bundle
CLI reconstructs known-zero costs from verified stage results; generic durable
billing recovery, corrections and active-call budget enforcement remain future work.

## Optimizer Boundary

`include/golem/optimization.h` defines an optional advisor boundary without
linking an optimizer or provider. Advisors may propose `NOOP`, `ROUTE`, `CACHE` or
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

The boundary does not contact external advisors, execute adapters, verify signatures or persist
proposals. External advisor contact must itself be authorized before it happens.
Host attestations are not cryptographic proof; normal completion gates still run.
Journal v1 does not restore optimizer policies/counts, and actual optimizer charges
must be reported explicitly rather than inferred from estimates. Wire codecs,
durable decision receipts, signed policy artifacts and external advisor bridges remain
separate follow-up work.

## Adapter Protocol

`include/golem/adapter_protocol.h` defines versioned capability, `run_stage`,
and stage-result envelopes. An adapter is a copied callback table with a borrowed
implementation context. The Core does not link provider SDKs or optimizer implementations. Inputs
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

## Fuzz And Hardening

Five Clang libFuzzer targets instrument the Golem library with ASAN/UBSAN and
coverage feedback. Sanitizers and testing must both be enabled for fuzz builds.
Normal Dev/Release/ASAN CTest also exercises the same harnesses with fixed-seed
mutations, truncation, trailing bytes, random data and size-limit boundaries;
these checks stay active with `NDEBUG`. Existing 15000 JSON and 30000 MessagePack
mutation checks remain enabled.

| Target suffix | Input and invariants |
| --- | --- |
| `adapter_json` | Strict JSON, output preservation, JSON/MessagePack canonical roundtrip |
| `adapter_msgpack` | Compact envelope lengths/types, output preservation, cross-format roundtrip |
| `journal` | CRC/framing, raw event and CREATED payloads, whole/chunked replay equivalence |
| `parser` | Receipt, digest and lineage decoding, canonical re-encoding and owned graph cleanup |
| `policy_artifact` | Versioned permission artifact, output preservation, DENY/UNKNOWN/external-effect gates |

Journal payloads are additionally reframed with a correct CRC so random mutation
can reach semantic parsers without having to guess a checksum. Synthetic seeds
come from public test fixtures and codecs, never local execution data. Deterministic
seed files, evolving corpora and crash reproducers stay under ignored `build/`.

Use Clang with libFuzzer installed (Homebrew LLVM on macOS, rather than the
default Command Line Tools). Override `CMAKE_C_COMPILER` on initial configure
when necessary:

```bash
cmake --preset fuzz
cmake --build --preset fuzz
ctest --preset fuzz
```

AppleClang installations without a bundled libFuzzer may explicitly set
`GOLEM_LIBFUZZER_LIBRARY` to an installed macOS libFuzzer archive. This uses the
Apple compiler's ASAN/UBSAN runtime and only the supplied archive's fuzz engine;
it never disables sanitizers. Use a separate build directory when changing
compilers and verify the selected toolchain on the host OS.

Each smoke target runs 10000 iterations with fixed seed, bounded input size,
10-second per-input timeout and 1 GiB RSS limit. CTest has a separate 180-second
timeout per target. Linux CI runs the same smoke suite without artifact uploads.
Standard sanitizer regression still covers the CLI, daemon and crash recovery.
External shared json-c/OpenSSL libraries are not rebuilt with instrumentation
by this project.

For a longer campaign, run e.g. `build/fuzz/fuzz/golem_fuzz_journal` with
`-max_total_time=3600`, a writable build-directory corpus, the generated seeds as
a second corpus and an `-artifact_prefix` under `build/`. Reproduce a finding by
passing its file directly to the matching executable with `-runs=1`. Minimize
with libFuzzer `-minimize_crash=1`; add only a reviewed, synthetic reproducer to
regression fixtures after fixing the bug. Do not upload private input data.
Smoke success is a bounded regression signal, not proof of parser security.

`golem_policy_artifact_encode/decode` exposes a bounded, allocation-free GPOL v1
format for a positive revision and six autonomy permissions. Unknown versions,
flags, reserved bytes, invalid permission codes and trailing data are rejected.
The public header documents ownership and the byte layout; a golden test pins
the format. Decode does **not** authenticate, install policy, grant approval or
protect against rollback. Hosts must authenticate and authorize explicit policy
adoption; signed artifacts and optimizer-policy serialization remain deferred.

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
supervision and automatic crash recovery are not part of this bundle command.
The separate daemon commands below add lease-bound local scheduling and recovery.

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
callback cannot be killed by this API; the separate subprocess supervisor below
provides bounded local worker execution.

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

## Local Daemon MVP

`include/golem/daemon.h` provides a persistent local queue and a serialized,
single-process scheduler. `include/golem/supervisor.h` provides a reusable POSIX
subprocess supervisor. Neither depends on an optimizer, provider SDK, or UI.

```bash
build/dev/golem daemon init /absolute/private/path/new-queue
build/dev/golem daemon submit /absolute/private/path/new-queue /absolute/private/path/project/capsule.json
build/dev/golem daemon status /absolute/private/path/new-queue
build/dev/golem daemon run /absolute/private/path/new-queue --worker /absolute/path/to/build/dev/golem --once
build/dev/golem daemon run /absolute/private/path/new-queue --worker /absolute/path/to/build/dev/golem --drain
build/dev/golem daemon run /absolute/private/path/new-queue --worker /absolute/path/to/build/dev/golem
```

`--once` attempts one stage; `--drain` runs until no eligible job is observed.
Without either flag, the foreground daemon polls until SIGINT/SIGTERM. It does
not fork into the background or install an OS service. A lifetime advisory lock
excludes cooperating second owners. Queue submission has a separate short lock;
jobs can be submitted while the daemon runs. Concurrent lock contention can
return BUSY to submit/status; clients may retry. Every scheduler tick selects
one eligible job in ticket-order round robin. The cursor is process-local and
resets on restart; continuous forced restarts do not guarantee fairness.

Submission syncs immutable identity, capsule context, bounded runtime options,
and the initial journal before publishing a job directory by rename. Failed
submissions may leave hidden unpublished directories, never executable jobs.
Each step replays the job journal while holding its writer lock, reconstructs
attempt/dispatch counters, acquires a fresh lease, and runs through the existing
policy gate. READY and recorded FAILED states can resume. RUNNING, blocked,
corrupt, or uncertain jobs are reported as `attention` and are never blindly
redispatched. Complete jobs are retained and skipped. Verified journal prefixes
can be repaired as described below; no truncation or inferred execution result
is allowed. A job failure does not prevent other jobs
from progressing; inability to persist quarantine stops the scheduler handle.

The CLI host only accepts an explicitly selected **trusted local.noop simulation
worker** implementing `adapter noop probe` and `adapter noop run STORE`. It probes
capabilities, sends JSON through bounded stdin, verifies the returned identity
and CAS evidence, and persists stdout/stderr and canonical result envelopes
before FINISHED. Previous result context/predecessor links and CAS bytes are
rechecked before continuation. A durable per-attempt dispatch marker prevents
sequence reuse if a whole journal suffix is lost but the marker survives.
This is not authenticated history or exactly-once execution: coordinated loss
of journal and sidecars still requires external recovery metadata.

The supervisor polls lease ownership, renews the 60-second lease at approximately
one-second intervals, bounds each output stream to 16 KiB, and applies the stage
deadline across probe and execution. It kills the process group and reaps its
direct child on timeout, interruption, protocol failure, or exit. SIGKILL of the
daemon itself cannot run cleanup: surviving children require operator handling,
and the unfinished job stays quarantined. Escaped sessions, remote effects,
privilege-changing children, and hostile workers are not sandboxed or fenced.
Workers inherit the host environment; do not launch untrusted executables.

CLI submissions default to 3 attempts/stage, 64 total stage runs, and a 30-second
stage deadline; the C submission API accepts bounded overrides. Queue v1 retains
at most 256 jobs, accepts at most 1024 attempts/stage and 1024 total dispatches,
and limits a deadline to one hour and a journal read to 16 MiB. Scheduling and
history validation deliberately favor correctness over large-queue throughput.
Only one stage executes at a time; no parallel workers or automatic job eviction.

Status and `complete` are journal attestations, not independently verified
business acceptance; status explicitly reports `acceptance_verified: false`.
The embedding callback owns its real acceptance/evidence contract. Daemon queues
are not Phase 12 bundles: use `replay JOB/journal.bin` for raw state; generic
daemon cost-report reconstruction and full lineage graph recovery are deferred.
Keep queues outside the checkout (or in ignored `.golem/`), on a trusted local
filesystem with stable, non-symlink parents. No encryption, remote listener,
signed runner enrollment, or multi-host locking is provided.

## Crash Recovery

```bash
build/dev/golem daemon recover /absolute/private/path/queue
```

Daemon startup automatically performs the same recovery sweep. This command
does not launch workers, grant approval, or restore old leases. It reports job
counts for `repaired`, `ready`, `complete`, `attention`, and `busy`, alongside
normal job status. Per-job rejection is reported as attention, not a successful
repair; an owner-lock or recovery write/fsync failure returns an operation error.

New submissions retain immutable write-ahead journal frames, beginning with
CREATED. Every later event is durably published before its journal append. The
recovery metadata binds runtime options by SHA-256; the first frame binds the
run identity and capsule context. Recovery validates the entire contiguous
transcript, CRCs, identity, metadata, and Core transitions before making changes.
An existing journal must be an exact byte prefix of that transcript. Only its
missing suffix is appended and synced, including a partial final frame. There
is no truncation, in-place rewrite, checksum bypass, or guessed event.
Unpublished temporary files are preserved and ignored. New publications use
unique temporary names so an orphan cannot permanently block an unstarted event.

| Interruption | Recovery |
| --- | --- |
| Before STARTED intent | Resume the not-yet-started stage through normal admission |
| STARTED/dispatch claim exists, no durable FINISHED | Attention; never rerun the uncertain attempt |
| Valid FINISHED intent, missing/partial journal append | Restore the exact event; continue after the finished attempt |
| Journal already matches | No bytes/files rewritten; repeated recovery is idempotent |
| Conflicting bytes, missing/corrupt intents, invalid transitions | Preserve data and report attention |
| Recovery itself interrupted | Validate the longer prefix and append only what remains |

Every embedding executor also receives a durable no-overwrite execution claim
before its callback. Retained claims prevent redispatch of the same attempt even
if both journal and intent tails are lost. CLI-specific dispatch markers remain
an additional guard. Completed attempts, historical retry counters, and the
original execution limits survive recovery. Existing attention markers are not
removed automatically, even if an event can be restored.

**This is not a distributed exactly-once guarantee.** A result is recoverable
only after its validated FINISHED event reaches durable write-ahead storage.
An external effect followed by a crash before that point still needs explicit
reconciliation. Coordinated loss of journal, intents, and claims cannot be
detected without independently retained checkpoints. The host's FINISHED event
is an acceptance attestation, not a new verification of business results or CAS.
CRC and local digests do not authenticate a hostile storage owner.

Phase 15 jobs without the new recovery metadata are preserved but not
automatically scheduled; inspect their original journal with `replay` and
reconcile separately. There is no automatic adoption of potentially incomplete
legacy history. The new records are additive: standalone journal v1 replay and
Phase 12 bundles retain their previous strict, read-only behavior.

Recovery shares the daemon-owner lock and holds each journal lock throughout
verification and append. Status holds a shared journal lock while comparing
intents. Startup briefly retries queue-publication contention (up to 100 ten-ms
waits); another daemon owner still fails immediately. Pre-dispatch journal lock
contention yields a scheduler tick without quarantining the job. Foreground mode
polls again; `--once`/`--drain` can return with ready jobs when readers contend.
Limits remain 256 jobs and 16 MiB per transcript, with at most 4096
recovery frames; buffers grow with actual data size. Keep the whole queue,
including recovery records, outside the checkout or in ignored `.golem/`.

## Language Bindings

Python and TypeScript/Node call the **same C engine in-process** through an
optional versioned shared ABI. No CLI subprocess, provider SDK, duplicate work
model, agent execution or UI is involved. Supported operations are capsule JSON
validation and read-only journal-byte replay. Both use the existing C parser,
Core and replay implementation; CLI projection semantics remain unchanged.

```sh
cmake --preset bindings
cmake --build --preset bindings
ctest --preset bindings
cmake --install build/bindings --prefix "$PWD/build/install-bindings"
python3 -m venv build/python-binding-env
build/python-binding-env/bin/python -m pip install ./bindings/python
npm ci --prefix bindings/typescript --ignore-scripts --no-audit --no-fund
npm run --prefix bindings/typescript typecheck
```

Requires macOS/Linux, Python 3.11+ for the Python package, and Node.js 18+ with
development headers for the Node-API v8 addon (tested locally on Node 22).
Set `GOLEM_NODE_INCLUDE_DIR` when headers are not discoverable. Python-only builds
use `-DGOLEM_BUILD_BINDINGS=ON -DGOLEM_BUILD_NODE_BINDING=OFF`; both options default
off outside the `bindings` preset. The engine remains C17; TypeScript is a
development-only type checker, not a runtime dependency.

The separate Python package is `golem-runtime`, imported as `golem_runtime`.
It does not replace the earlier `golem-awe` prototype or its CLI. Example from
the repository root using the installed package and synthetic golden journal:

```python
from pathlib import Path
import sys
from golem_runtime import Engine, GolemError

name = "libgolem_binding.dylib" if sys.platform == "darwin" else "libgolem_binding.so"
engine = Engine((Path("build/install-bindings/lib") / name).resolve())
validated = engine.validate(Path("samples/work-capsules/basic.json").read_bytes())
journal = bytes.fromhex(Path("tests/c/fixtures/journal/v1_default.hex").read_text())
result = engine.replay(journal)
assert result["state"] == "SUCCEEDED"
assert result["acceptance_verified"] is False
records = int(result["journal_records"])
```

The ESM package `@golem-awe/runtime` ships JavaScript and strict TypeScript
declarations, without an automatic native download/install hook. For local
packaging, `npm pack ./bindings/typescript --ignore-scripts --pack-destination
build/bindings` creates a tarball; install it in a separate Node consumer project.
For direct repository use:

```javascript
import { Engine } from './bindings/typescript/index.mjs';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const engine = new Engine(resolve('build/install-bindings/lib/golem/node/golem_node.node'));
const validated = engine.validate(readFileSync('samples/work-capsules/basic.json'));
const journal = Buffer.from(readFileSync('tests/c/fixtures/journal/v1_default.hex', 'utf8').replace(/\s/g, ''), 'hex');
const result = engine.replay(journal);
const records = BigInt(result.journal_records);
```

In TypeScript consumers import `Engine`, `Capsule`, `ValidationResult` and
`ReplayResult` from the package using NodeNext module resolution. Native packages
are built/installed separately with CMake, not embedded in the wheel/tarball.
The installed addon resolves the shared ABI relative to its installation tree;
keep `lib/golem/node/` together with `lib/libgolem_binding*` when relocating it.
Consumers may also link the optional installed `Golem::binding` CMake target.

ABI v1 exports only version, call, free and status-message functions, documented
in `include/golem/binding.h`. Native result allocations are copied into ordinary
host values and freed by the same library. Failed calls preserve native output
parameters and become `GolemError` with a numeric `status`; host argument/loading
errors use the language's normal exceptions. Counters remain decimal strings to
avoid JavaScript uint64 precision loss. Inputs are bounded to 128 KiB capsule
JSON and 16 MiB journal bytes. Invalid projected UTF-8 is rejected, not replaced.

Load only trusted native code from an explicit absolute path. Python retains the
library and permits independent concurrent calls; results own no live Core
handles. Node calls are synchronous, so use worker threads for large replay
inputs. Mutable input buffers are copied; shared/detached Node buffers are not
supported. No implicit file access, auto-discovery or library download occurs.

`validate` checks a capsule, not permission to execute it. `replay` accepts valid
unfinished prefixes: RUNNING reports `RECONCILE_ATTEMPT`, never auto-retries.
Even SUCCEEDED is a journal attestation, not verified acceptance/CAS, a restored
lease or an authenticated checkpoint. The binding exposes no mutation or repair.

Tests cover native allocation ownership, invalid/truncated journals, unfinished
and terminal states, Python threads, Node workers, strict types and installed,
relocated consumers. ASAN/UBSAN tests exercise the native ABI in a sanitizer-linked
C executable; ordinary Python/Node host tests run in non-sanitized builds. CI
includes macOS/Linux binding and packaging jobs, with no registry publication.

## Performance Baselines

Opt-in benchmarks use the real C public APIs without changing the installed
runtime. Build an unsanitized Release executable:

```sh
cmake --preset bench
cmake --build --preset bench
ctest --preset bench
python3 bench/benchmark.py run --binary build/bench/bench/golem_bench --scratch build/bench --output build/bench/baseline.json --environment-id local-storage-a
python3 bench/benchmark.py run --binary build/bench/bench/golem_bench --scratch build/bench --output build/bench/candidate.json --environment-id local-storage-a
python3 bench/benchmark.py compare build/bench/baseline.json build/bench/candidate.json --thresholds bench/thresholds.json
python3 bench/benchmark.py report build/bench/baseline.json
```

The C runner reports raw `CLOCK_MONOTONIC` nanoseconds; Python handles collection,
validation, JSON reports and Markdown projection only. Each metric calibrates a
bounded batch toward 50 ms and collects seven samples in fresh processes, with
one untimed warmup operation per batch. Setup, scratch creation, process startup
and cleanup are excluded; API allocation, return checks and result validation
inside each operation are included. Medians are per complete operation, not
individual stage transitions. Fixture/workload version is fixed and hashed.

| Metric | One operation |
| --- | --- |
| `transition_cycle` | Create/free a WorkRun and complete all six stages (12 transitions) |
| `transition_replay` | Validate/reconstruct/free a completed 13-record journal |
| `journal_encode`, `journal_decode` | One 64-byte CRC-protected frame in memory |
| `journal_append_fsync` | Append one 64-byte frame and fsync an already-open private scratch journal |
| `digest_4k`, `digest_1m` | SHA-256 of a hot 4 KiB / 1 MiB deterministic buffer |
| `json_encode`, `json_decode` | One RUN_STAGE envelope with IDs and context receipt |
| `msgpack_encode`, `msgpack_decode` | The same RUN_STAGE envelope in MessagePack |

Journal append measures the framing writer, not a semantically complete work
history. It does not include directory fsync, CAS, device cache flush beyond the
platform's `fsync` contract, or daemon recovery. Digest throughput is memory
throughput, not cold file/CAS throughput. MiB/s uses 1048576 bytes. No agents,
provider requests, private evidence or production queues are used.

Default regression limits in `bench/thresholds.json` are **20% median latency
increase**, or **35% for journal fsync**. Relative MAD above 10% in either run is
inconclusive, not a pass. Exit codes: 0 pass, 1 stable regression, 2 incompatible,
invalid or noisy measurements. A stable regression takes precedence if another
metric is noisy. At least five samples and identical measurement settings are
required. Raw samples are retained; derived summaries are recomputed on read.

Comparison requires identical OS/CPU, environment tag, scratch device, compiler,
build flags, workload hash and dependency versions. Binary/source hashes are
recorded as provenance, not required to match across code changes. Use a stable
nonprivate `environment-id` to identify the same machine/storage/power setup;
matching CPU model alone is not proof of comparable hardware. Control background
load, power/thermal state and storage conditions; don't run competing tests during
measurement. A remounted device or changed toolchain may require a new reviewed
baseline. The tool refuses to overwrite existing reports or automatically bless
regressions. Never increase thresholds solely to hide a failure.

CI enables benchmark correctness tests in Dev/Release/ASAN, not a wall-clock
performance gate on shared runners. `--smoke` permits instrumented/debug binaries
for correctness, and smoke reports cannot serve as performance baselines.
Real baseline reports stay in ignored `build/` or an external private benchmark
directory; no automatic report upload is configured. Benchmarks are optional
and are not installed or added to the public ABI.

## Next Development Order

1. Extend the noop coordinator with durable provider dispatch/reconciliation records.
2. Add executable acceptance/gate evaluators and preserve structured acceptance identity.
3. Add provider adapters for Codex, Claude, Gemini, and local CLI.
4. Generalize persisted billing and add cross-process lease authority/recovery without reusing old tokens.
5. Add Markdown and JSON projections for run receipts.
6. Extend the capability protocol with signed runner enrollment and envelopes.
7. Add optional optimizer wire bridges and durable decision receipts using the implemented boundary.
