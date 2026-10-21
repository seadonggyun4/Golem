# D1: Local Project Approval and Read-Only Backend

This implements the schema, local project-approval registry and fixed read-only
backend slice of the [integration design](integration-layer-design.md). It is
**not an MCP server, client auto-installer, session hook, remote authentication
service, native mutation API, or Work migration**. Existing projects/Works and
the selected native executable must already exist. Nothing is installed in TRAP.

## Contracts

`tools/integration_contract.py` holds the closed contract definitions used by the
runtime validators and generated JSON Schema 2020-12 documents in
`samples/integration/*.schema.json`. It is a bounded domain validator, not a
general-purpose JSON Schema interpreter. No remote schema references execute.
The committed schemas are checked against their generators by tests.

| Schema | Meaning |
| --- | --- |
| `golem.integration-description.v1` | Owner-selected existing paths to describe/pin; launches nothing |
| `golem.integration-project.v1` | Canonical root, `.golem`, directory identities, executable/SDK hashes, enumerated Works |
| `golem.integration-grant.v1` | One principal/client pair, permitted Works/operations, LOCAL_HOST destination |
| `golem.integration-client-binding.v1` | The selected principal/client/project and exact approval generation |
| `golem.integration-enrollment.v1` | Project plus up to 32 separately scoped client grants |
| `golem.integration-read.v1` | Fixed read operation, selected Work, bounded history page and opaque native cursor |

The schemas reject unknown/missing fields. Runtime additionally rejects duplicate
JSON keys, invalid UTF-8/surrogates/NUL, non-finite numbers, excessive depth,
duplicate Work IDs/paths, duplicate principal/client pairs and grants for absent
Works. Integer fields reject booleans and floats, including JSON `1.0`; a JSON
Schema consumer alone does not enforce this lexical/native integer distinction.
Cross-field, filesystem and authority constraints remain runtime checks.

Requests are at most 256 KiB, depth 24, 512 array items and 256 object fields.
Project/SDK/Work arrays have additional bounds of 32. Native stdout/stderr each
use the existing recorder's 32 MiB monitored limit; native result decoding keeps
the same structural bounds. Large consolidated histories may therefore block
rather than silently truncate. Native errors and original streams remain retained.
History uses native schema 2 with 1..256 events per stream and `has_more`.
Every D1 query still requires the consolidated identity observation first, so
history pagination does not bypass a Work that exceeds that preflight's bounds.
Removing that whole-record cost needs a separately verified native identity API,
not an adapter shortcut around replay or corruption checks.

## Trust and Scope

This POSIX implementation is **LOCAL_COOPERATIVE**, not authenticated identity.
An owner-side CLI/API caller chooses principal/client IDs; merely matching a
label is not proof of a real person or a particular app. Same-user hostile code
can edit the registry or invoke native CLI directly. No independent QA or
provider authentication claim is made. Future MCP must not expose these admin
operations or accept self-asserted labels as authenticated identity.

All native writes, provider calls and external destinations are absent from the
D1 grant vocabulary. Execution authority stays false. Each read validates the
current generation, client/principal/Work/operation, root identities, engine/SDK
pins and Work lineage. No model-supplied shell, argv, environment or native
operation dispatcher exists. The history cursor is only a native reading hint.

The Work pin is the **SHA-256 of exact first document-event frame bytes**, plus
its directory identity and declared Work ID. The frame commits the original CAS
specification reference; native replay verifies the store and the returned Work
ID before a selected view. This is not a replacement or reserialization of the
native specification digest, a new Work ID, or authenticated store provenance.
Moving/replacing a store requires a new explicit reviewed enrollment.

All grants here authorize local observation of their selected Work, including
the retained identity/preflight record. The operation list restricts available
queries, not field-level secrecy inside that Work. Per-artifact disclosure,
cloud forwarding and externally readable evidence URIs belong to later stages.

## Owner Workflow

Use a **new, explicitly selected private registry outside the project**. Example
absolute paths below are placeholders. Do not apply this to an installed product
without its owner's separate approval. Input files must be private, bounded,
single-link regular files; paths must be canonical with no symlink components.

```sh
python3 tools/integration_registry.py schema --kind description
python3 tools/integration_registry.py schema --kind enrollment
python3 tools/integration_registry.py schema --kind read
python3 tools/integration_registry.py init --registry /private/owner-registry \
  --approve-local-owner
python3 tools/integration_registry.py describe --input /private/description.json
```

Description input, with real existing paths:

```json
{
  "schema": "golem.integration-description.v1",
  "project_id": "project-a",
  "root": "/absolute/project",
  "cli": "/absolute/reviewed-runtime/bin/golem",
  "sdk_files": ["/absolute/matching-sdk/docs/agent-session.md"],
  "works": [{"work_id": "work-a", "path": "/absolute/project/.golem/works/work-a"}]
}
```

`describe` returns the project object, without invoking the executable or scanning
other projects. The owner must select the complete relevant SDK/instruction pin
set and verify binary/build provenance separately; one file hash alone does not
establish a complete SDK installation. Multiple repository/worktree roots and
automatic bootstrap are not inferred in this slice: enroll each approved root
explicitly. A non-Git parent project may be enrolled but is not treated as a
Git snapshot or authority for unlisted child repositories.

Construct a private enrollment with that exact returned `project` and `grants`:

```json
{
  "schema": "golem.integration-grant.v1",
  "principal_id": "local-owner",
  "client_id": "client-a",
  "operations": ["status", "next", "record", "history"],
  "work_ids": ["work-a"],
  "destination": "LOCAL_HOST",
  "assurance": "LOCAL_COOPERATIVE"
}
```

The enrollment wrapper is `schema: golem.integration-enrollment.v1`, `project`,
and `grants: [the grant above, other explicitly approved clients]`. It is not a
native Work file. Review the full candidate and returned plan hash:

```sh
python3 tools/integration_registry.py plan --registry /private/owner-registry \
  --input /private/enrollment.json
python3 tools/integration_registry.py apply --registry /private/owner-registry \
  --input /private/enrollment.json --reviewed-plan EXACT_REVIEWED_PLAN_SHA256 \
  --approve-local-owner
```

The local-owner flag explicitly acknowledges the owner-invoked control plane; it
is not an authenticated human signature and must not become a model-facing tool.
The digest binds current registry pointer/identity, generation, full enrollment
and producer-module hashes, including the recorder and JSON helper. Approved
records retain that producer identity; a changed helper blocks reads until an
explicit reviewed update. Copying/moving the registry does not preserve its
directory binding. `apply` revalidates paths and pins under an exclusive
registry directory lock. A changed plan, simultaneous writer or stale generation
fails without replacing the current record. An identical old apply is not a
renewal: it is rejected as stale after publication; prepare a fresh plan explicitly.

## Read-Only Requests

Use the actual generation returned by approval:

```json
{
  "schema": "golem.integration-read.v1",
  "binding": {
    "schema": "golem.integration-client-binding.v1",
    "project_id": "project-a",
    "generation": 1,
    "principal_id": "local-owner",
    "client_id": "client-a",
    "assurance": "LOCAL_COOPERATIVE"
  },
  "work_id": "work-a",
  "operation": "status",
  "limit": 64,
  "cursor": null
}
```

```sh
python3 tools/integration_registry.py read --registry /private/owner-registry \
  --input /private/query.json
```

Only `status`, `next`, `record`, `history` are supported. Non-history requests
require null cursor. Each query first obtains an actual native Work record for
identity/replay validation, then executes the selected query. These are separate
observations, explicitly `observations_atomic: false`, not one reserved snapshot
or a lease. Policy blockers, resume preflight, foreign owner and native errors
retain their native meanings. No start/claim/heartbeat/resume/reconcile/report
projection is invoked. A future typed mutation must still fence all intervening
changes inside the original native contract.

The exact native CLI and SDK bytes are checked before and after the observations.
Child environment is explicit LANG/LC_ALL/PATH plus recorder-owned evidence
variables; inherited GIT_PAGER, HOME, provider credentials and GOLEM_RECORD_ROOT
are not forwarded. The child uses the private audit directory as cwd. Mechanical
recording uses `observe_source=False`: no Git/source scan is performed, so
source-before/after are explicitly NOT_OBSERVED and source freshness is not claimed.
Native Work replay and pins remain checked independently.

Successful output is `golem.integration-observation.v1`, state OBSERVED, with
native result, binding, request digest, raw evidence references and false execution
authority/product acceptance. A native DONE, if present in a future view, would
not certify semantic correctness. Failed queries return BLOCKED/nonzero and the
private evidence path when dispatch occurred. No retry or error-to-empty-delta
conversion is performed.

## Persistence, Concurrency and Recovery

Registry roots are owner-owned mode 0700; files mode 0600. Symlink components,
nonregular/hardlinked input files, root replacement and changed identities fail.
The registry may not contain the project or be contained in it. Its approval
records are immutable `PROJECT.GENERATION.SHA256.json` snapshots. A private current
pointer is published last by atomic replacement after file/directory fsync.
The existing snapshot is never overwritten. Orphaned snapshots from interrupted
publication are retained; a subsequent explicit identical plan may finish pointer
publication. A failed pointer update is not a successful approval or revocation.

Reads hold a shared registry lock across their bounded native observations;
approval/revocation takes an exclusive nonblocking lock. Two readers can proceed;
a concurrent revoker gets REGISTRY_BUSY and must explicitly retry later. This
gives local cooperating requests an admission order, not distributed transactions
or protection from same-user malicious filesystem edits. Native store locks remain
authoritative and are opened by each read subprocess, never retained for a client
connection. Changed generation invalidates all old client bindings.

For revocation, use the currently retained enrollment and review its revoke plan:

```sh
python3 tools/integration_registry.py revoke-plan --registry /private/owner-registry \
  --input /private/enrollment.json
python3 tools/integration_registry.py revoke --registry /private/owner-registry \
  --input /private/enrollment.json --reviewed-plan EXACT_REVIEWED_REVOKE_SHA256 \
  --approve-local-owner
```

Revocation does not require the old project/SDK/binary still to exist or match;
it withdraws the old grant without touching the project. A later approval is a
new generation, not a silent repair. There is no historical-snapshot rollback
command, automatic migration, deletion of evidence, or stale-lock-file cleanup.
POSIX directory flock releases on process exit; no persistent lock file is used.

Each dispatched read retains a unique `read-*` directory with input, original
record/query stdout/stderr, mechanical manifests and final result or failure.
These may contain private project information; do not publish the registry.
Admission limits are 256 read directories, 16384 scanned entries and 128 MiB of
existing registry/audit files. A running read can exceed that admission threshold;
this is not an OS-enforced disk quota. New reads then block. Concurrent readers
can race at the threshold; the per-call native limits still apply. No automatic
audit/evidence GC is provided. Owner review/export/retention management is required.
Disk full/interruption is a failure, never synthetic readiness.

## Validation and Remaining Work

Unit tests use isolated projects and fake pinned executables to cover schemas,
approval/stale plans, client/Work scope, revocation, root/pin drift, symlink/hardlink,
partial publication, concurrency, malformed output, timeout, quota, inherited
environment and retained failures. The native `integration_read_backend` CTest
uses **real disposable native Works**, checks all file bytes/modes remain unchanged,
paginates history, observes an actual live claim/sequence change, rejects mutations,
and retains a corrupt-CAS native failure without repair.

The new native test participates in the normal CTest matrix and clean-source
export; unit tests participate in existing Python discovery. Source exports
explicitly allowlist the new modules and public schemas, not local registry data.
The observation CI also validates all six public schemas with the independent
`jsonschema==4.23.0` validator. This is a test-only dependency, not a runtime
requirement. Run `python3 tools/verify_integration_schema.py` in an isolated
environment containing that pinned validator to reproduce it.
Restricted host boot-clock denial is not a successful native test and is not
hidden by a skip. Run the real native path on a permitted macOS/Linux host.

Not implemented here: client config installation/removal, signed host identity,
project bootstrap, multi-root auto-discovery, handoff/context delivery, all native
write tools, MCP transport, remote/cloud access, automatic updates or Windows
native runtime. These remain separately gated work; the implementation does not
relax any core permission, fencing, protection or evidence contract.
