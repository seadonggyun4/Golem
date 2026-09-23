# Runtime Profile and Execution Identity

See [Runtime Validation](runtime-validation.md) for enrollment compatibility,
cross-binary checks, bounded exploration and current-agent canary limits.

For structured adapter metadata and opt-in live compatibility checks, see
[Harness Capability Descriptor](adapter-descriptor.md). A profile digest alone
does not activate that execution gate.

Golem records the runtime conditions selected for a current-agent attempt without
starting another agent. A profile is identity metadata, **not permission, a
sandbox, proof of provider honesty, or a reproducible remote model image**.

## Identity contracts

| Record | Authority and lifetime |
| --- | --- |
| RuntimeProfile v1 | Immutable canonical JSON in Work CAS; domain `golem.runtime-profile.v1` |
| Prepared generation | Work registration event digest; refers to profile, Work spec, generation number, and admission sequence |
| ExecutionBinding v1 | Work spec digest, selection revision/digest, input manifest, original claim epoch/session/attempt, profile and generation digests |
| Optional WorkRun link | Separate immutable event referencing the binding, journal snapshot digest, explicit run ID, stage sequence, and verified checkpoint |

The document Work identity is its existing ID **plus compact serialized Work
specification digest**, not its directory basename. Copying a complete store
copies that Work's identity. It does not create a new independently identified
Work. Runtime profile generation does not increment the document revision counter.

Every enrolled claim gets a binding before the agent claim event is published.
An orphan CAS object from interrupted publication is not a claim. Session claim
events with a binding use schema 2; the request protocol remains schema 1.
Other session events keep their existing schema. The document event chain and
binary HWJRv1 encoding are unchanged. Older binaries reject these new records;
they must not be used to write an enrolled store.

Refreshing a default affects **future claims only**. Registration records the
agent sequence at publication; replay checks the generation admitted before the
claim, rejecting a retroactive/default-generation swap. Resume keeps the original
binding as historical provenance while existing session fencing issues a new
authority epoch. The binding's `claim_epoch` never grants continuation permission.

## Schema and canonicalization

See [the synthetic example](../samples/runtime-profile.json). Replace fixture
digests and identities with actual measurements before use. Nothing automatically
probes an installed Codex/Claude binary or a provider account in this feature.

All fields in that example are required; extra fields are rejected. Identifiers
are case-sensitive. No environment dump, prompt, credential, access token, or
arbitrary configuration object is accepted. Allowlisted text fields can still be
misused by a caller to contain a secret: callers must keep secrets out of values
and out of referenced CAS objects. Hashing a secret is not safe redaction.

`provider_reported`/`model_reported` are declared labels. The separate observed
labels must either both be empty with an empty `observation_digest`, or both be
nonempty with a retrievable observation receipt. A receipt's existence is **not**
authentication of its content; a trusted harness must establish its provenance.
Contradictory reported/observed labels are preserved, not silently reconciled.

The v1 canonical form is deliberately schema-specific, **not general RFC 8785
JCS**: sort the fixed ASCII object keys lexicographically, preserve array order,
emit positive integer scalars in decimal and strings using json-c compact
escaping (`JSON_C_TO_STRING_PLAIN`). Preserve Unicode code points and opaque ID
case. Float values, duplicate/unknown keys, embedded NUL, malformed UTF-8, invalid
versions, oversized fields and numeric overflow are rejected. Tool IDs are unique.
Tool array order is part of identity. SHA-256 covers the complete canonical UTF-8
JSON, including the required domain; that digest is also its CAS address. Changing
canonicalization requires a new schema/domain. Existing execution-contract
hashing is not changed. Tests compare independent encoding for the ASCII golden
fixture and reordered-key equivalence.

Limits: 64 KiB input/canonical profile, 256 tools, 256 bytes per label; retrievable
adapter descriptors are limited to 16 KiB. This stores descriptor identity, not
the capability enforcement to be implemented separately.

## Restore levels

`IDENTITY_ONLY` preserves identities without asserting local artifact availability.
`LOCAL_ARTIFACTS_AVAILABLE` requires CAS verification of engine-build artifact,
adapter executable, descriptor, allowlisted config, policy, and every tool digest.
Checks run on registration, reopening and bound session validation. Missing or
corrupt objects fail closed. Profiles containing observation receipts always
require those receipts. An old unavailable artifact is not silently removed from
history just because a newer profile exists.

Local availability does not prove executable compatibility, actual invocation,
remote provider availability, access rights, model weights, or identical results.
There is no automatic download, provider substitution, or restoration. New model
or tool choices require a new generation and a new attempt.

## Work creation and CLI

A new Work can use Work specification **schema 2**: all existing Work fields plus
`runtime_profile` containing the complete profile object. Use the normal command:

```sh
golem work start /private/work-dir /private/work-with-profile.json
```

The initial profile CAS object is durable before the Work event. Reopen fails if
that profile is missing, rather than downgrading the Work to unbound execution.
For a new Work, initially use `IDENTITY_ONLY`; once its CAS is populated, a later
generation can declare verified local artifact availability.

Existing schema-1 Work stores remain readable with `runtime_identity: UNKNOWN`.
They opt in explicitly, when no unbound claim is active:

```sh
golem profile validate /private/runtime-profile.json
golem profile register /private/work-dir /private/runtime-profile.json runtime-1
golem profile current /private/work-dir
golem session call /private/work-dir /private/claim-request.json
```

The active claim exposes `runtime_binding`; its JSON is retrievable with the
existing evidence interface. Status/context distinguish `BOUND`,
`ENROLLED_NO_ACTIVE_BINDING`, and `UNKNOWN`. Profile current returns the latest
default, not the active claim's historical profile. There is no unenrollment API.
Reusing a registration key with the same canonical profile is idempotent;
different contents conflict. Work `DENY`/`ASK_ALWAYS` still block registration.
Enrolled execution requires a live current-agent claim; deleting agent history
cannot enable a tokenless execution path.

Each Work retains at most 64 generation registrations (including the initial
generation); exhaustion fails rather than garbage-collecting referenced history.
This durable history bound is independent of the process-local memo cache below.

## Optional binary WorkRun bridge

When explicitly connecting a separately managed binary WorkRun:

```sh
golem profile link /private/work-dir BINDING_DIGEST /private/run.journal RUN_ID RECORDS BYTES CHAIN_HEAD
```

Supply checkpoint values retained independently by the WorkRun controller. Values
computed solely from the same untrusted journal cannot authenticate it. The C API
is `golem_runtime_link_run` in [runtime_profile.h](../include/golem/runtime_profile.h).
It semantically replays the complete bounded journal, verifies the supplied
checkpoint/run ID, requires a RUNNING StageRun matching the current document
stage and a live RUNNING current-agent claim, and checks lease liveness again
before committing. Journal bytes must not contain secrets: the complete snapshot
is retained in private Work CAS. Limit: 16 MiB per snapshot and 256 links per Work.

The binding is not rewritten; an additional hash-chain event records the explicit
association. Same binding and identical snapshot is idempotent; a changed snapshot
or reuse of the same run/stage sequence by another binding conflicts. Reopen
replays retained snapshots again, including semantic stage checks. Linking never
executes or resumes a binary run and does not grant lease/policy authority. Without
a link, `work_run: null` means unknown, not inferred from a matching name. An
independent WorkRun remains under its existing policy/lease controller.

## C API and cache ownership

Profile parse returns an immutable owned handle; use its matching free. Input
buffers are borrowed only during calls. Public encode/current use caller-owned
buffers with non-mutating short-buffer errors. Handle allocations use the caller
allocator; json-c retains its own allocator. Serialize store/cache calls.

The bounded 64-entry memo cache stores parsed/encoded profile handles. Its exact
request-byte digest covers config, tool, executable, policy and all other fields.
Semantically equivalent different serialization can miss the memo but yields the
same canonical profile digest. A successful acquire pins the entry until release;
all-pinned capacity exhaustion fails, and close refuses outstanding borrows.
Releasing a borrowed handle does not delete durable evidence. No TTL is treated as
authorization. **Every acquire, including hits, calls the trusted current-check
callback** for policy revocation, observed artifact identity and probe freshness.
Failures are never cached as success; borrowed handles are identity-only. No
callback result can bypass the separate session/execution policy checks. The cache
does not run probes itself, cache permission, or claim provider-discovery speedups.

## Research rationale and limits

These sources inform the design; they do not prove this implementation correct.
Read scope is the listed sections/types, not a claim to have reviewed entire books.

| Primary source | Applied result and boundary |
| --- | --- |
| [OpenClaw generation types](https://github.com/openclaw/openclaw/blob/01457af6876f1c4be61f492d86b0ac7fc596853e/src/agents/prepared-model-runtime.types.ts) and [generation scope](https://github.com/openclaw/openclaw/blob/01457af6876f1c4be61f492d86b0ac7fc596853e/src/agents/prepared-model-runtime-generation-scope.ts) | Read immutable snapshots, secret-free auth modes and lease-scoped borrowing. Applied generation pinning, not its gateway/plugin implementation; no source copied. |
| [Torres-Arias et al., in-toto, USENIX Security 2019, sections 2 and 4](https://www.usenix.org/system/files/sec19-torres-arias.pdf) | Link step identity with input artifacts and result provenance. Unlike signed in-toto metadata, this local CAS binding is not authenticated. |
| [W3C PROV-DM, entities/activities/agents and derivation](https://www.w3.org/TR/prov-dm/) | Keep profile entity, execution activity and agent session distinct. Same label is not sufficient to merge identities. |
| [Bazel hermeticity](https://bazel.build/basics/hermeticity) | Tool/config identity is explicit. Recording identities alone does not make a remote provider hermetic. |
| [RFC 8785, canonicalization constraints](https://www.rfc-editor.org/rfc/rfc8785) | Define encoding before hashing; constrain the schema. Full JCS is deliberately not claimed for this json-c codec. |
| [Saltzer and Schroeder, The Protection of Information in Computer Systems, 1975, design principles](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html) | Complete mediation: current-check on every cache acquisition; historic profile never supplies authorization. |
| [Lamport, Specifying Systems, 2002, chapters 3 and 5, invariants](https://lamport.azurewebsites.net/tla/book-21-07-04.pdf) | Tests encode invariants: admitted generation remains fixed; refresh changes only future attempts; resume epoch is distinct from provenance. No formal proof or TLC run claimed. |
| [Arpaci-Dusseau, Operating Systems: Three Easy Pieces, Crash Consistency: FSCK and Journaling](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf) | Persist referenced CAS artifacts before publishing authoritative events, reuse existing synced no-replace publication; no power-loss guarantee from unit tests alone. |

## Verification

```sh
cmake --preset release
cmake --build --preset release
ctest --preset release --output-on-failure
cmake --preset asan
cmake --build --preset asan
ctest --preset asan --output-on-failure
```

Focused tests: `runtime_profile_codec`, `runtime_profile_invalid`,
`runtime_profile_cache`, `runtime_profile_ownership`, `runtime_profile_cli`, and
`header_runtime_profile`. The CLI suite includes current-agent handoff/resume,
schema-2 Work creation, local artifact removal, explicit binary bridge/checkpoint,
and semantic binding tampering after recomputing hashes. The existing document
mutation/libFuzzer target also exercises profile parsing with a valid profile seed.
Existing historical fixtures are left unchanged. Live Codex/Claude provider
validation, automatic process measurement and capability enforcement are not
performed by these synthetic tests.
