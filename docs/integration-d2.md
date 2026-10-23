# D2 Read-Only MCP and Explicit Handoff

Implemented slice: owner-launched **local stdio** MCP, D1-approved Work reads,
complete native context candidates, and explicitly addressed handoff preparation.
It also provides bounded committed-reference evidence reads and native current
selection completion checks, without finalize or projection repair.
Optional [D3 command hooks](integration-d3.md) reuse this service for bounded
startup/resume notices; they do not turn a context reference into complete input.
The native core, D1 v1 schemas, project approval records and native evidence are
unchanged. This is not automatic client installation, a resume hook, a remote
gateway, a worker daemon, or permission to execute a Work.
Explicit mutations use the separate [D4 owner-reviewed adapter](integration-d4.md);
the D2 server and its transfer consent remain native read-only.

## Layers and Authority

| Layer | Implementation | Responsibility |
| --- | --- | --- |
| Owner disclosure policy | `tools/integration_transfer.py` | Closed schema, exact reviewed bytes, one declared client, destination and recipients |
| Domain service | `tools/integration_service.py` | Fixed queries, D1 reauthorization, native candidate binding, bounded inline delivery |
| Protocol adapter | `tools/integration_mcp.py` | Official SDK objects and stdio, not a second JSON-RPC implementation |
| Native authority | Existing D1 backend and CLI | Replay, owner/lease/sequence/binding, source/selection, protected files and evidence |

The owner must approve **both** the D1 enrollment and the separate D2 disclosure
policy. `LOCAL_HOST` in a D1 grant is not silently upgraded to model-service
disclosure. D2 allows `LOCAL_HOST` or `MODEL_SERVICE`, with an explicit
`destination_id` and `data_class: APPROVED_WORK_CONTENT`. The latter means the
owner reviewed disclosure of the selected Works' full content, including paths,
session fields and embedded instructions. It is not redaction or secret scanning.
Private audit directories and sibling preflight records are not returned as
generic file-reading capabilities.

This is **LOCAL_COOPERATIVE** consent, not an authenticated human, model identity,
or an OS isolation boundary. A same-user process can launch its own program.
`clientInfo`, roots, model arguments and text inside documents confer no rights.
The host must enforce that the configured destination is its actual destination;
the local server cannot prove a host's subsequent use or onward transmission.

## Owner Setup

Use Python 3.11+ on the supported POSIX host. Install optional dependencies in a
dedicated virtual environment, not into the native engine or a global client:

```sh
python3 -m venv /private/owner-mcp-venv
/private/owner-mcp-venv/bin/python -m pip install -r tools/requirements-mcp.txt
python3 tools/integration_transfer.py schema
```

The server requires official `mcp==2.3.0` and `mcp-types==2.3.0`; it refuses another
version. Transitive SDK dependencies follow their package constraints, not a
fully hashed environment lock. Review dependency updates separately from engine
and client configuration updates. Other Golem Python tools do not require MCP.

First create the existing [D1 registry and approvals](integration-d1.md). A D2
policy has exactly these fields; all example paths and IDs are placeholders:

```json
{
  "schema": "golem.integration-transfer.v1",
  "registry": "/private/owner-registry",
  "registry_identity": {"device": 1, "inode": 2},
  "destination": "MODEL_SERVICE",
  "destination_id": "reviewed-client",
  "data_class": "APPROVED_WORK_CONTENT",
  "max_result_bytes": 8388608,
  "scopes": [{
    "binding": {
      "schema": "golem.integration-client-binding.v1",
      "project_id": "project", "generation": 1,
      "principal_id": "owner", "client_id": "client-a",
      "assurance": "LOCAL_COOPERATIVE"
    },
    "work_ids": ["work"],
    "tools": ["projects_list", "work_inspect", "history_read", "context_get", "handoff_prepare", "evidence_read", "completion_check"],
    "recipients": [{
      "schema": "golem.integration-client-binding.v1",
      "project_id": "project", "generation": 1,
      "principal_id": "owner", "client_id": "client-b",
      "assurance": "LOCAL_COOPERATIVE"
    }]
  }],
  "producer": {}
}
```

Use actual D1 root identity/generation/bindings, never the placeholders. The
owner-only `plan --input /private/policy-input.json` command fills `producer`
with the current five D1 and three D2 module hashes and outputs the complete
policy. Retain that output in an owner-private, single-link regular file (0600),
outside enrolled project roots. Review the entire policy and its exact file
SHA-256. Policy planning does not grant authority, invoke native commands, write
the registry, or configure a client. Producer equality, field closure and size
are verified again at launch and every call.

The host's owner-controlled server command is:

```sh
/private/owner-mcp-venv/bin/python tools/integration_mcp.py \
  --policy /private/reviewed-transfer.json \
  --reviewed-policy-sha256 REVIEWED_EXACT_FILE_SHA256 \
  --approve-data-transfer
```

Use absolute paths to the interpreter and script in real host configuration.
These are launcher arguments, **not model-supplied tool parameters**. D2 does
not edit Codex/Claude settings or activate a plugin automatically. One process
has one principal/client pair across its explicit projects; another client needs
its own reviewed policy/launcher. Up to 32 projects, Works per scope and recipient
bindings are supported by bounded contracts; there is no filesystem discovery.

Deleting/changing the policy stops future calls on a running server. Revoke a
D1 grant through its existing reviewed revoke plan/apply procedure; the running
server rechecks it, without caching a positive authorization. Calls hold a shared
registry lock through the observation/delivery preparation. Revoke may return
REGISTRY_BUSY while a bounded read is in progress; do not bypass that lock.
Already returned data cannot be recalled. Module, CLI, SDK or root changes require
review; do not auto-repin an installation. D1 module bytes were not changed by D2.

## MCP Contract

The official SDK handles discovery, initialize, capability negotiation and errors.
Two actual stdio SDK client profiles are tested: modern `2026-07-28` discovery
and legacy `2025-11-25` initialize. This is not a claim of activation in every
Codex/Claude/ChatGPT host. HTTP, OAuth, sampling, elicitation, tasks and subscriptions
are not enabled. No custom protocol fallback expands native authority.

| Tool | Required arguments beyond explicit project_id/work_id | Result |
| --- | --- | --- |
| `golem_projects_list` | None; empty closed object | Approved scope IDs only; revoked/invalid scopes omitted |
| `golem_work_inspect` | `view`: status, next or record | Current native view and observation hash |
| `golem_history_read` | `limit` 1..256, opaque `cursor` or null | Original native FULL/DELTA, cursor, has_more semantics |
| `golem_context_get` | selection_id, source_snapshot, target_kind, recipe | Complete renderer-v2 candidate and status/next preflight |
| `golem_handoff_prepare` | Context arguments plus recipient_client_id | Same complete input, addressed to an explicitly approved recipient |
| `golem_evidence_read` | digest (64 lowercase hex), max_bytes (1..1048576) | Complete hash-verified bytes, base64 encoded, with committed Work reference roles |
| `golem_completion_check` | selection_id | Unmodified native current selection completion observation, not finalize or report |

Every input is closed; boolean integers, unknown fields, model-selected binding,
principal, path, shell command or approval are rejected. No administrative or
mutation tool exists. List results require a current D1 record grant. Individual
reads additionally require their original operation; context requires record,
status and next. Evidence reads require record; completion checks require record,
status and next. Both also require explicit D2 tool consent. A tool listed for a broad scope may still be blocked for an
individual operation whose D1 grant is narrower. No current-project selection
state is held on the MCP connection.

Tools are the inline retrieval fallback, so clients need not support resources.
No arbitrary-path, global-CAS or cached-resource reader is exposed. Native Work
record/history/context carry their existing evidence and judgment references;
D2 does not merge external assessment files into a new memory database or invent
truth/QA verification for referenced material. Arbitrary resource/file retrieval
and automatic host consumption remain outside this slice.

### Evidence and Completion Reads

`evidence_read` uses the native replay-verified Work record to allow only explicit
committed `documents[].digest` (manifest), `documents[].body_digest` (body), and
`journal[].payload_digest` references. Returned `references` identify their roles,
document revision/freshness or journal stream/sequence. Historical committed
references remain historical; reading them does not make them current. The tool
does not recursively interpret document text, metadata or arbitrary hex strings.
Frame/event hashes, normalized assessment hashes, raw stream hashes and orphan
CAS objects are not disclosure capabilities. Transitive receipt/log retrieval is
not implicitly granted; use its separately specified native evidence contracts.

The pinned CLI runs `evidence read APPROVED_WORK DIGEST MAX_BYTES`, opening CAS
read-only and using `golem_evidence_read` to verify the complete object before
publication. The service independently validates canonical base64, exact size and
SHA-256. Empty and binary evidence are supported. Missing, corrupt or oversize
objects fail without truncation. `verification: SHA256_INTEGRITY_NOT_CONTENT_TRUTH`
and `content_role: UNTRUSTED_DATA` distinguish integrity from authenticity, semantic
truth, approval and instructions. Full selected Work content consent is required;
this is not redaction or secret detection.

`completion_check` constructs the closed native v1 `operation: resume` request and
calls `completion check APPROVED_WORK REQUEST.json`. This new local CLI entrypoint
validates the request, rejects finalize, opens the document store read-only and
reuses `golem_completion_call`. It is **completion observation**, not session resume.
It does not call `completion report`, materialize missing projections, reconcile,
claim, renew a lease, execute QA or finalize. The nested native result remains the
authority: WAIT, recovery/revalidation actions and historical receipts are not
promoted to DONE. `acceptance_verified` is true only for native current DONE;
even DONE is not external product certification or authorization to execute.
The returned selection ID/revision/digest must match a committed reference in
the surrounding Work record as well as the explicitly requested selection ID.

Both tools read the native Work record before and after the query and require
identical encoded observations. A changed record is OBSERVATION_STALE, with no
automatic retry. Source files can change outside the Work lock, so this is not an
atomic snapshot or a guarantee about future state. Original native failure
stdout/stderr and private delivery records remain under the bounded registry spool;
they are not generic model-readable file paths. Encoded delivery must fit the
owner's result budget or fail intact. No native evidence is created or repaired.

**Upgrade:** changed CLI/SDK producer pins require existing D1/D5 owner review;
changed D2 module bytes require a newly reviewed transfer policy. Adding these
tools to the enum does not add them to existing policies. Keep narrower allowlists
unless the owner explicitly approves the new disclosures. D4 and D6 reuse the
same service; D6 additionally requires `golem.read` and its delegate tool allowlist.

Results have schema `golem.integration-delivery.v1`, state AVAILABLE,
`native_state_changed: false`, `execution_authorized: false`,
`ownership_transferred: false`, `observations_atomic: false`, declared destination
and `model_consumption: NOT_OBSERVED`. The MCP response carries JSON as a text
content block. It does not duplicate a large context into structuredContent.
Receiving a response proves availability to the host, not complete model input,
understanding, token-budget verification or acceptance of the Work.

All tool annotations conservatively use `readOnlyHint: false`,
`destructiveHint: false`, `idempotentHint: false`, `openWorldHint: false`: reads
write private integration audit files, even though they never mutate the native
Work. Annotations are hints, not permission checks. projects_list itself only reads.

## Context and Handoff Safety

1. Read native Work record, status and next using the original D1 backend.
2. Require matching native status/next sequence; do not select tokens or resume.
3. Render **candidate**, never publish, with renderer 2 and current-v1/original-v1.
4. Verify exact candidate_json SHA-256 against native projection_digest, parsed
   projection identity, request equality and zero omitted bytes in every source.
5. Reread the Work record and require byte-identical encoded observations before
   preparing delivery. Changes during observation are OBSERVATION_STALE, not a
   reason for an implicit retry. This is not a lock against unrelated source edits.
6. Write only a private immutable delivery.json beneath the registry audit spool.
   Return complete context inline or fail; never truncate required sources.

The candidate is a **READING_AID**, `execution_ready: false`, provider budget
UNKNOWN. Native exact bytes and projection digest are distinct from the handoff
payload digest and transfer-policy digest. There is no provider/model call,
token-count claim or generic summary fallback. A later authorized execution
handoff must use the existing [context-resume adapter](context-resume.md), its
provider counting and native freshness/fence checks; this MCP stage does not
perform that mutation.

For handoff, the requested recipient must appear in the owner policy. Its own
current D1 record/status/next grant, project, Work and generation are checked.
The resulting `golem.integration-handoff.v1` contains both sender and recipient
bindings, exact context and native preflight, and current record/policy digests.
Preparation is **not automatic transmission, ownership transfer or a receipt**.
The host explicitly conveys the prepared input to that destination. The receiver
must use its own policy and re-read current native state; a sender's payload never
delegates grants. Self-addressed preparation is allowed, not automatic renewal.

A live foreign owner, expired lease, RUNNING/unknown effects, reboot, rollback,
DONE and policy failures retain the original native preflight. D2 does not infer
no-effects, extend a lease, force takeover, reconcile, migrate, execute or rewrite
any event. Complete context does not turn WAIT/RECOVERY_REQUIRED into execution.

## Limits and Failures

- Policy and domain arguments: D1 256 KiB, closed bounded trees and strict values.
- Stdio frame: 512 KiB **before SDK parsing**; strict UTF-8, duplicate-key,
  non-finite, surrogate and depth checks. Malformed/oversized frames close the
  connection with a bounded stderr diagnostic; no native operation is attempted.
- Native candidate: existing 2 MiB limit; capture and D1 observation retain their
  original limits. Inline result budget is 4 KiB..8 MiB of encoded domain JSON,
  not a provider-token count or identical wire-byte count after JSON escaping.
- One in-flight service call per server; SERVICE_BUSY is returned without retry.
  Separate clients still use native locks; a busy native read remains a failure.
- Audit admission uses existing D1 bounds: 16,384 entries, 128 MiB and fewer than
  256 read directories. This is not an OS disk quota or cross-process reservation.
  No automatic deletion of pending or failed evidence occurs.
- Each subprocess has the D1 15-second limit and minimal LANG/LC_ALL/PATH
  environment. A context call comprises several bounded subprocesses, not one
  atomic snapshot. Uncertain disk/host errors remain BLOCKED, never retried.

Domain errors use `golem.integration-error.v1`, MCP isError, a stable code,
next_operation, automatic_retry_allowed false and, when available, a private
local_evidence_id. Failed native stdout/stderr remain local for owner diagnosis;
the MCP error does not echo them or private absolute audit paths. Native safety
checks are not lowered to improve readability or compensate for a sandbox.

## Verification and Boundaries

`tools/test_integration_d2.py` tests policy closure/pins/private mode, owner intent,
revocation, forged arguments, scope, candidate hash, changed observations,
recipient consent, result bounds and serialization with disposable fixtures.
`tests/c/integration_d2_mcp.py CLI SOURCE` uses **real native disposable Works**
and **two real stdio SDK clients**, not a paid provider or product Work. It checks
complete current/original context, handoff, stale source/selection, live foreign
owner, wire rejection and modern/legacy reads with a forged clientInfo and D1
revocation. It compares all native file bytes/modes and path additions/deletions.
CI runs this optional SDK/native gate on macOS and Linux under sanitizers.
The suite also covers committed body/manifest/journal reads, orphan/frame denial,
size limits, empty/binary content, CAS corruption and both new tools through real
modern/legacy stdio clients. Completion CTest covers VERIFY_COMPLETION,
RECOVER_REPORT, DONE and REVALIDATE_COMPLETION without native file changes or
projection repair; a finalize request sent to the check endpoint is rejected.
The TLS gateway gate exercises both reads through separately approved delegates.

Locally exercised platform: macOS. Linux is a distinct CI result, not inferred
from macOS. Windows native runtime, actual Codex/Claude app installation, real
Hosted consumption, physical reboot/power loss and arbitrary historical engines
remain NOT_VERIFIED by this D2 slice. No TRAP install, existing Work resume,
migration, product acceptance, VM or UACTT is performed.

Later, separately approved [Codex desktop synthetic verification](integration-codex-desktop.md)
on 2026-10-24 completed eight actual calls across the six read tools in a new
conversation. The earlier D2 slice's limits above remain historical test scope,
not a claim that no desktop integration has subsequently been exercised. The
existing conversation still lacked tool exposure; general hot reload and real
Hosted gateway consumption remain unverified.

Design and source basis: [integration design](integration-layer-design.md),
[reference review](integration-layer-references.md#d2-sdk-implementation-review).

### Local Review Record

2026-10-21, macOS, disposable data and a dedicated SDK environment:

| Gate | Observed result |
| --- | --- |
| Full dependency-free Python regression | 521/521 PASS |
| D2 focused domain tests (included above) | 11/11 PASS |
| D2 independent schema/native/two-client stdio suite with ASan/UBSan binary | 6/6 PASS |
| Existing session/binding/execution/completion/context/D1 CTests | 7/7 PASS |
| Existing six D1 schemas, independent validator | 55/55 assertions PASS |

The normal managed sandbox cannot run all native boot-identity paths; the native
gates above ran on the host with temporary synthetic stores, not by bypassing a
core check or treating a blocked test as PASS. Remote per-revision CI results are
recorded by GitHub Actions, not inferred from this local record. No existing
project approval was renewed, and no real client configuration was installed.
