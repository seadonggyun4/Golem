# D4 Typed Mutations and Owner-Approved QA

D4 is an **explicit, opt-in local stdio adapter**, not an extension of startup
hooks into autonomous execution. It reuses the unchanged [D1 registry](integration-d1.md),
[D2 transfer policy and reads](integration-d2.md), native session/document/context
APIs and [scoped approval API](approvals.md). [D3 hooks](integration-d3.md) remain
read-only. Nothing installs client settings or selects/resumes a Work automatically.

## Authority and Scope

An agent decides what work to do. Golem checks the collaboration contract. D4
adds an owner-reviewed mapping from one D1 principal/client/project/Work to exact
native actions. It does **not** upgrade D1 read grants into blanket mutation
permission. D2 disclosure permission is still required to return native material.

The owner prepares an immutable private action and pins its bytes in a separate
mutation policy. The model receives only a typed tool and these arguments:

```json
{"project_id":"project","work_id":"work","action_id":"reviewed-claim","request_id":"stable-request-1"}
```

The model cannot supply a filesystem path, argv, environment, native request,
issuer, approval flag, session identity or policy generation. Each action fixes
its native session mapping; an enrolled binding also fixes its native binding ID.
Native v1/v2, token, owner, sequence, lease, manifest, source, document generation,
policy and protected-file checks remain authoritative. No binding attach,
heartbeat, Work creation, registered-output rejection or completion finalize is
added to the MCP surface. Those require their original explicit procedures.

| Typed tool | Fixed native mapping |
| --- | --- |
| `golem_session_claim` | `session call`, exact claim v1 or enrolled v2 |
| `golem_session_begin` | Exact token/input/sequence begin |
| `golem_session_resume` | `session resume` with complete renderer-v2 context and count proof |
| `golem_session_reconcile` | Explicit ADOPT_OUTPUT or evidence-backed NO_EFFECTS declaration |
| `golem_session_submit` | Exact registered output/input/source/evidence submit |
| `golem_document_submit` | Original metadata/body registration, separate from session submit |
| `golem_execution_request` | Receipted prepare/finish/run through the opt-in trusted local host |

All seven tools have separate closed schemas, although their opaque-reference
arguments are identical. Only tools with approved actions are listed. Every call
rechecks its exact action, D1 generation/identity/pins and D2 destination. Native
request member order/bytes are retained, not reconstructed from a model payload.
Document metadata and execution contracts retain their existing native schemas;
the adapter does not duplicate the native reducers or QA parser.

An action is explicit owner consent to those exact local bytes, **not** proof of
authenticated human identity. This is the existing LOCAL_COOPERATIVE, same-UID
trust boundary. An agent with unrestricted local filesystem/shell access can
bypass an integration API. Separate accounts/OS isolation are required for a
stronger adversarial boundary. No OAuth, remote authentication, signatures or
credential forwarding are implemented here.

## Owner Configuration

The stdlib service requires Python 3.11+ on macOS/Linux. The optional transport
uses the same pinned `tools/requirements-mcp.txt` SDK as D2. Build the QA host
only when it is wanted; its option defaults to OFF:

```sh
cmake -S . -B build/integration -DGOLEM_BUILD_INTEGRATION_HOST=ON
cmake --build build/integration --parallel 2
python3 tools/integration_mutation_contract.py schema --kind policy
python3 tools/integration_mutation_contract.py schema --kind action
python3 tools/integration_mutation_contract.py schema --kind decision
```

Keep all policies, action files, owner decisions and integration records private
and outside the approved project. Existing D1 registry/file identity, no-symlink,
single-link, private-mode and producer-pin rules remain unchanged. Do not store
secrets in requests, argv, Markdown or evidence. Stage a **new** action/decision
file for a new review rather than replacing historical inputs.

An action has exactly these fields (native JSON is a string to preserve bytes):

```json
{
  "schema":"golem.integration-native-action.v1",
  "native_json":"{\"schema_version\":1,\"operation\":\"begin\",\"work_id\":\"work\",\"key\":\"begin-1\",\"expected_sequence\":2,\"token\":{\"epoch\":2,\"attempt_id\":\"attempt-2\",\"session_id\":\"mapped-owner\"},\"input_digest\":\"REPLACE\"}\n",
  "body":"",
  "context_json":"",
  "count_json":"",
  "approval":null
}
```

This example is deliberately non-runnable: replace every scope, token and digest
using the actual original protocol and reviewed evidence. `body` is nonempty only
for document submission. `context_json` and `count_json` are nonempty only for
resume. `approval` is non-null only for execution. Unknown/duplicate fields,
versions, invalid strings and oversized values fail closed.

The policy contains `schema: golem.integration-mutations.v1`, an exact D2
`transfer_policy: {path,sha256}`, `producer` module hashes and up to 32 actions.
Each entry has `action_id`, `project_id`, `work_id`, `tool`, `session_id`,
`native_binding_id` (empty only for a legacy unbound session), and an `action`
file pin. Do not infer the mapping from clientInfo, cwd or recent conversation.

`plan` fills current producer hashes without dispatching; it is not approval or
live validation. Review its output and retain the resulting private policy.
`check` verifies the exact saved policy and its actions without native writes:

```sh
python3 tools/integration_mutation_contract.py plan --input /private/policy-draft.json
python3 tools/integration_mutation_contract.py check --input /private/mutations.json \
  --reviewed-policy-sha256 REVIEWED_SHA256 --approve-mutations
python3 tools/integration_mutation_mcp.py --policy /private/mutations.json \
  --reviewed-policy-sha256 REVIEWED_SHA256 --approve-mutations
```

Paths/digests above are placeholders. Launch is owner-controlled; no installer or
model-facing approve/configure/revoke tool is exposed. D2 and D3 need not be
reconfigured and their production modules/native contracts are unchanged.

## Preflight and Resume

Every first mutation reads original status and next. Inconsistent sequence or a
session request based on an old sequence stops before dispatch. Resume also
rejects DONE and a live foreign owner. These observations are **not reservations**:
the original native operation rechecks all fences under the Work lock.

Resume uses the existing `golem_agent_session_resume_context` entry point, not
legacy bare resume. It requires `current-v1` or `original-v1`, renderer 2,
no excerpts, positive token budget and a separately prepared count proof. Native
code verifies the exact current projection/count binding. Obtain count evidence
through the existing [context/provider adapter](context-resume.md); never invent
counts, strip mandatory sources or treat a count as billing evidence. D4 does not
contact a provider or claim that a staged count authenticates that provider.
The native handoff contains the complete projection; availability is not model
understanding or whole-conversation budget proof.

A RUNNING resume enters RECOVERY_REQUIRED. It never creates a runnable replacement
claim or infers no effects. Reconciliation is a distinct reviewed action using
the new native token and actual surviving evidence. D3 startup/resume notices
cannot authorize any of these mutations.

## Separate QA Approval Channel

The existing CLI deliberately cannot approve requests. Use its read-only
`approval describe` and explicit `approval call` request procedure first. Preserve
the generated action, its member order, execution JSON and request receipt.
The owner reviews the complete scope/argv/protected files/effects outside MCP.

The opt-in `golem-integration-host` uses **only public C APIs**. Its synchronous
`decide` reads an already collected private decision, checks the exact action
digest, issuer and policy epoch, and accepts only the `approve` operation. It
does not wait for input under a Work lock. A decision has exactly:

```json
{"action_digest":"REPLACE","issuer":"REPLACE","operation":"approve","policy_epoch":1,"schema":"golem.integration-local-decision.v1"}
```

Use valid lowercase SHA-256 values and the exact ASCII sorted-key encoding from
`integration_contract.encoded`, including its trailing newline. The C adapter
requires that encoding as well as exact file hash/private identity; duplicate,
unknown or alternative decision encodings are refused. An issuer is an
owner-declared local authority label, not a signed person identity.

Owner-only approval invocation (the dashes are unused fields for this mode):

```sh
golem-integration-host approve WORK APPROVE_REQUEST.json DECISION.json DECISION_SHA - - - - -
```

This approval request is the original native approve JSON, including its own key,
request_receipt and identifier-shaped reason. The model cannot invoke this mode
through MCP. The execution action's `approval` object pins `host`, `decision`,
`request_receipt`, `contract` and `shell_contract` (empty denies shell; otherwise
an independently reviewed complete contract digest). It does not deserialize a
native host callback or approvals from tool arguments.

Before dispatch, a read-only native approval status must be APPROVED. Missing
decisions/PENDING stay PENDING_APPROVAL. Expired, denied or consumed receipts do
not dispatch. At consumption, dispatch and supervisor heartbeats, native
`golem_execution_call_receipted` calls `recheck`. The adapter rereads the decision
and exact D4 policy/D2 policy/D1 current-generation pointer pins. Removing/changing
the decision or revoking/reapproving enrollment prevents further authorized
dispatch and can cancel a running QA command. It does **not undo prior effects**.
Native TTL/boot/clock checks, absolute DENY and separate shell approval remain.

QA FAIL/ERROR is a successfully recorded native result, not acceptance. Native
one-use consumption, attempt markers and `approval recover` determine whether
the result is RECORDED or consumption remains UNCERTAIN. An integration transport
failure does not override that original evidence.

## Durability, Concurrency and Recovery Boundary

Admission order is integration registry lock, then native Work lock. A short
exclusive registry admission durably writes an intent binding principal/client,
project/Work lineage, tool, stable request ID and exact native bytes/action/policy
hashes. This unfinished intent excludes other D4 writers to the same Work across
processes/clients. Short native mutations retain a shared registry admission lock
through dispatch and native return, serializing revocation against that accepted
call. The lock is released before long QA execution, so an owner can revoke
enrollment; native authority is rechecked during QA. A regression first reproduced
the unlocked short-dispatch revocation race, then verified this shared-lock fix.

The stable ID is not the JSON-RPC ID. Reusing it with different bytes or scope
is REQUEST_CONFLICT. Identical calls return verified historical integration
results without redispatch or lease renewal. Results and hash references are
immutable no-overwrite, fsynced private files. Native stdout/stderr and the
existing execution recorder are retained; a compact response does not replace
the native receipt.

| Integration state | Meaning |
| --- | --- |
| NOT_DISPATCHED | Rejected before dispatch intent; no native mutation attempted |
| PENDING_APPROVAL | Missing owner decision or native pending approval; no automatic approval |
| NATIVE_RESULT_RECORDED | Original complete native reply retained; historical, not current completion |
| COMMIT_UNKNOWN | Dispatch intent exists without trustworthy final evidence, or post-dispatch failure/revocation |

Crash after admission, response loss, nonzero native exit, truncation, audit
failure or missing/corrupt final result cannot become empty success. A failure
after dispatch is conservatively uncertain even when a native diagnostic may
show a pre-effect rejection. New request IDs cannot bypass an unresolved Work.
Cancellation/disconnection does not prove the child/effects stopped. There is no
automatic retry, re-keying, native repair, response-derived approval or rollback.

D4 deliberately has **no quarantine-clear/delete/repair tool**. Preserve the
original intent/logs and use original read-only status, record, approval recover
and surviving effect evidence for owner investigation. Native recovery remains
available through its original explicit API; do not invent a new QA attempt to
escape uncertainty or discard the integration ledger. Re-enabling D4 after an
ambiguous/crashed request requires the separately owner-reviewed
[D5 recovery procedure](integration-d5.md#commit_unknown-clearance). It preserves
the original uncertain result and retires the original logical action; no new
registry, replacement request ID, or model-facing tool bypasses the quarantine.
The D5-enabled D4 producer also fences maintenance admission and holds managed
server/writer descriptors. Existing D4 policies require explicit producer review;
D1/D2/D3 and native Work schemas are unchanged.

Limits: 32 reviewed actions/policy, 128 retained mutation intents/registry, existing
D1 16,384-entry/128-MiB audit admission limits, 256-KiB action/request envelope,
32-MiB captured native output bound and D2's smaller disclosure budget. Whole
responses must fit; nothing truncates required input. These are cooperative
admission/capture bounds, not an OS disk quota or sandbox. Pending/unknown records
are never automatically garbage-collected.

## Verification and Support

`tools/test_integration_mutations.py` exercises closed policies, owner mappings,
revocation, exact replay/conflict, ambiguous dispatch, damaged/missing result
references, new-key exclusion, admission and complete resume requirements.
`tools/verify_mutation_schema.py` independently checks the public JSON Schemas.
`tests/c/integration_d4_mutations.py` uses real native temporary Works for
claim/begin/document/session submit, resume/reconcile, foreign-owner blocking,
corrupt CAS no-repair, concurrent admission, committed response loss, receipted
prepare/finish/QA PASS/real compiler FAIL, protected-file refusal, pending approval
and live registry revocation. `--mcp` additionally uses actual pinned SDK clients
over modern/legacy stdio; it does not use paid providers or product Works.

CTest's `integration_typed_mutations` is enabled only with the optional host and
has no MCP SDK dependency. CI's observation workflow builds that host with
ASan/UBSan and runs the actual SDK gate separately on macOS/Linux. Existing native
session/binding/approval/resume regressions remain separate authoritative tests.
Windows, network filesystems, physical power loss, all historical engines,
Desktop/Hosted activation and authenticated remote approval are NOT_VERIFIED.
No TRAP installation, migration, real Work execution or VM/UACTT is part of D4.

Local macOS review, 2026-10-21 (not a claim of Desktop/Hosted activation):

| Gate | Observed result |
| --- | --- |
| Full Python regression, including execution-record coverage | 555/555 PASS |
| D4 focused unit tests, included above | 19/19 PASS |
| Actual modern/legacy MCP plus native D4, ASan/UBSan | 15/15 PASS |
| Actual modern/legacy MCP plus native D4, Release | 15/15 PASS |
| D1/D3/D4 CTest entries | 3/3 PASS; optional SDK case is separate |
| Existing session/binding/approval/context CTests | 8/8 PASS |
| Independent public-schema assertions | 30/30 PASS |

Per-revision remote results are retained in GitHub Actions. A local result is
not substituted for a pending/failed CI job. The implementation also preserves
native ERROR on live revocation: recover may return a recorded ERROR without
redispatch, or UNCERTAIN after consumption; neither is a successful effect.

## Design Basis

These are engineering inferences, not proofs of exactly-once effects:

- [MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools):
  closed typed tools and explicit human control; annotations are not enforcement.
- [RFC 9396](https://www.rfc-editor.org/rfc/rfc9396.html): concrete structured action
  scope; no OAuth implementation is claimed.
- [Burrows, Chubby, OSDI 2006](https://research.google.com/archive/chubby-osdi06.pdf):
  accepting-service ownership fences, not a second distributed lease protocol.
- [Saltzer and Schroeder, 1975](https://web.mit.edu/Saltzer/www/publications/protection/):
  least privilege, fail-safe defaults and complete mediation; owner administration
  is not a model-facing mutation.
- [Anderson, Security Engineering 3e, chapter 6](https://www.cl.cam.ac.uk/archive/rja14/Papers/SEv3-ch06.pdf):
  authorization and enforcement boundaries; a same-UID file is not remote identity.
- [Existing approval contract and references](approvals.md): one-use consumption,
  durable uncertainty and recovery reuse, without a duplicate approval reducer.
