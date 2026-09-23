# Harness Capability Descriptor

Golem separates adapter metadata from permission to execute. No descriptor or
probe receipt creates an approval, a lease, or a completion receipt.

## Contracts

| Contract | Source | Meaning |
| --- | --- | --- |
| `golem_adapter_descriptor` | Adapter/current agent | Claimed protocol, stage, feature, input, tool and sandbox facts |
| `golem_harness_probe_result` | Golem supervisor | Process exit, duration, stdout/stderr digests; decoded stdout remains a claim |
| `golem_harness_observation` | Trusted host callback | Checked capabilities, evidence, profile/binding/clock-domain/epoch, expiry |
| `golem_harness_requirements` | Trusted stage policy | Required subset, not additional authority |
| `golem_harness_guard` | Host | Live identity and revalidation boundary for checked dispatch |

API: `include/golem/adapter_descriptor.h`. Existing adapter capability v1 structs
and JSON/MessagePack formats are unchanged. New value structs are version-1
types, not serialized layouts; incompatible future layouts need new types.
Options carry exact `size` and `version` and reject mismatches.

## Wire Schema

See `samples/adapter-descriptor.json`. All fields required; unknown/duplicate keys,
embedded NUL, invalid UTF-8, invalid masks, unsupported versions and trailing
documents rejected. IDs follow the existing 1..95 ASCII ID grammar, preserving
case. Only unknown version/session may be empty. Credentials, prompts, arbitrary
environment maps and commands are not schema fields.

| Field | Values |
| --- | --- |
| `schema_version`, `protocol_version` | `1` |
| `domain` | `golem.adapter-descriptor.v1` |
| `current_agent` | Integer `0` or `1`, not JSON boolean |
| `stages` | Nonempty subset of the six existing stage bits; maximum `63` |
| `features_known/supported` | resume=`1`, cancel=`2`, stream=`4`; supported is a subset of known |
| `inputs_known/supported` | JSON=`1`, MessagePack=`2`, Markdown=`4`, context reference=`8` |
| `simulation`, `hidden_prompt_known` | unknown=`0`, no=`1`, yes=`2` |
| `sandbox` | unknown=`0`, none=`1`, process=`2`, OS sandbox=`3`, container=`4`, VM=`5` |
| `effect` | unknown=`0`, local=`1`, external=`2` |
| `tools` | 0..64 unique `{id,digest}` contracts; lowercase SHA-256 |

Encoded input/output is bounded to 16 KiB. Empty tools grants nothing. Unknown is
distinct from unsupported; neither meets a requirement. Sandbox categories use
exact matching, not a security-strength ranking. PROCESS is not an OS sandbox.

Canonical bytes use fixed lexical object key order, integer masks/enums, compact
json-c encoding and tools sorted by ID. SHA-256 of those bytes is the descriptor
digest. This schema-specific form is not general RFC 8785 JCS. Golden bytes and
an independent Python encoder comparison pin it. Tool ordering is set-like here,
not a change to the array-order contract of runtime profiles.
CLI adds a newline for display; it is not part of the canonical descriptor digest.
Use C encode bytes for CAS/profile registration, not raw CLI stdout with its
delimiter. A probe's stdout digest intentionally differs when its JSON formatting
differs, while its canonical descriptor digest remains stable.

## Read-only Description

```sh
golem adapter describe noop
golem adapter describe samples/adapter-descriptor.json
golem adapter describe --current codex
golem adapter describe --current claude SESSION_ID
```

No agent launch, enrollment, lease or Work mutation. Current-agent output describes
an existing caller-supplied session, never authenticates it. Version, hidden
prompt knowledge, sandbox, effect, simulation and feature/input support remain
unknown by default. Stages indicate workflow participation, not host verification.
No privilege is attached to the names Codex or Claude.

`from_v1` copies only ID/stages/effect/simulation; it does not infer transport,
resume/cancel/stream, sandbox or tools. `to_v1` rejects lossy conversions and
unknown effect/simulation. Existing noop JSON/MessagePack bytes are preserved.

## Explicit Metadata Probe

```sh
golem adapter probe /absolute/trusted-helper EXPECTED_SHA256 \
  /absolute/working-directory 5000 --allow-process
```

This is an enrolled metadata-helper contract, **not** a flag assumed to exist in
Codex or Claude. The only argv is `[executable,"--golem-describe"]`; stdin empty;
child environment exactly `LANG=C`, `LC_ALL=C`. No shell, PATH search, inherited
HOME/credentials, agent prompt or tool arguments. Positive timeout at most 30 s;
stdout/stderr independently capped at 16 KiB. Overflow is failure, not truncation
accepted as success. The existing supervisor owns/reaps the process group.
The timeout bounds the child process, not potentially blocking filesystem I/O
while hashing the executable; trusted-host observation callbacks also must return
promptly rather than relying on an in-process preemption mechanism.

Executable SHA-256 is checked before/after. The executable must be trusted and
quiescent: pathname hashing is not atomic `fexecve` pinning or protection against
a malicious same-user writer. Metadata argv and environment scrubbing cannot
prevent a malicious program from working or accessing the network. No OS sandbox
is added; escaped/remote children retain existing supervisor limitations. Default
description never starts a process.

Receipt projection records digests, exit/signal, timeout, duration and status with
`execution_authorized=false`, `host_capabilities_verified=false`. No raw stderr
is printed. The caller-owned C result includes bounded raw logs for explicit
retention/redaction decisions. No logs/CAS objects are automatically published.
Preflight denial yields no process receipt. Failed invocation may yield a failure
receipt, never an observed capability suitable for authorization.

## Checked Dispatch

1. Resolve the descriptor pinned by `adapter_descriptor_digest` in the 30A profile.
   Host obtains expected profile/binding/epoch from the real admitted attempt,
   not untrusted adapter input. Canonical descriptor bytes can be stored with the
   existing evidence API; no second descriptor store is introduced.
2. Build requirements from trusted stage policy. Require at least one input form
   and stage. Tools match both ID and contract digest.
3. Provide live host `observe`, monotonic `now`, and a nonzero boot/instance
   `clock_domain`. Host owns actual capability checks, revocation and publication
   of measurement evidence. IDs/digests alone are not authentication.
4. Call `golem_adapter_dispatch_checked`. Existing RUNNING identity, lease,
   admitted-effect, context/predecessor CAS and one-dispatch checks still apply.
   Descriptor digest must match the expected value; ID/stages/effect/simulation
   must agree with the actual adapter v1 probe.
5. Before stage invocation and after successful result verification, query the
   host again. Require matching profile/binding/epoch/clock-domain, fresh lifetime
   and hash-valid measurement CAS. Recheck time after evidence I/O. Only the
   intersection of claimed and observed capabilities can meet requirements.

No capability widens admitted effects. Preflight failure does not consume the
attempt; post-dispatch failure preserves output but consumes dispatch, since
effects may remain. Reconcile instead of blindly retrying. Lease ownership is
also checked after the host callback.

Callbacks are trusted in-process code, must return promptly and must not
reenter/mutate borrowed state. CAS verifies measurement bytes, not semantic truth.
`golem_harness_observation_encode` projects host facts and their underlying
measurement reference for explicit storage. There is no decoder restoring live
authority. Host restart requires a new clock domain; saved observations must not
be replayed as fresh checks.

Legacy `golem_adapter_dispatch` remains unenrolled. Registering a 30A profile does
not automatically route every daemon/current-agent operation through this new
guard. Hosts opt in; this phase does not claim global enforcement across legacy
entry points or implement provider-native resume/cancel/stream behavior.

## Ownership and Bindings

Structs are independent caller-owned values. No input pointers are retained and
input/output must not alias. Encode excludes NUL and reports `required`; short
buffers are untouched. Decode/digest errors preserve outputs. Probe is the
documented exception: it publishes invocation failure details. Temporary json-c
allocations use its allocator; no new global cache or owner handle is introduced.

Binding operation `3` adds read-only canonicalization without changing ABI v1
signatures/old operations. Both wrappers call the same C codec, return detached
values, cap input at 16 KiB, and cannot probe or authorize execution. Older native
libraries reject the operation instead of inventing support.

```python
descriptor = engine.describe_adapter(descriptor_json)
```
```typescript
const descriptor = engine.describeAdapter(descriptorJson);
```

## Research and Tests

Reviewed the sections/files below, not entire books; no formal proof, upstream
code copying or additional provider SDK dependency is claimed.

| Primary source and read scope | Application and limit |
| --- | --- |
| [OpenClaw host-capability-types.ts, fixed commit 01457af](https://github.com/openclaw/openclaw/blob/01457af6876f1c4be61f492d86b0ac7fc596853e/src/agents/harness/host-capability-types.ts) | Active-host assertions, scoped tools/environment/approvals motivate separating authority from metadata. No gateway dependency. |
| [Watson et al., Capsicum, USENIX Security 2010, sections 1-3](https://www.cl.cam.ac.uk/research/security/capsicum/papers/2010usenix-security-capsicum-website.pdf) | OS-enforced rights differ from feature descriptions. Golem JSON masks are not unforgeable capabilities or Capsicum sandboxes. |
| [Saltzer and Schroeder, 1975, Basic Principles](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html) | Fail-safe defaults and complete mediation motivate unknown rejection and repeated checks; no proof of global mediation across legacy APIs. |
| [OSTEP, chapter 5, sections 5.2-5.4](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf) | Wait/exec/environment separation motivate reusing the bounded supervisor. Process creation alone is not isolation. |
| [MCP lifecycle, pinned 2025-11-25 edition](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) | Separate protocol version, declared features and negotiated use. This is not an MCP implementation/interoperability claim. |

Tests cover canonical bytes, tool bounds, strict schema, 512 feature
intersections, legacy formats, unknown current sessions, epoch/binding/clock
domain mismatch, missing CAS, timeout/overflow/failed probe, post-execution
revocation, denied effects and unchanged outputs. Adapter JSON fuzzing checks
descriptor round trips too. Native ABI/Python/Node tests use the same codec.
Fixtures do not attest real providers or OS sandbox enforcement.

```sh
ctest --preset release -R 'adapter_descriptor|adapter_guarded|adapter_codec|adapter_cli'
ctest --preset asan -R 'adapter_descriptor|adapter_guarded|mutation_adapter_json'
```
