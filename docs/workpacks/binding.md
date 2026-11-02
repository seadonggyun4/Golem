# Work Pack M4: native document binding

Implemented, experimental **native-documents-v1 only**. This is an opt-in immutable
reference to an existing native document-role obligation. It is not a general Pack
executor, semantic release verifier or new owner identity protocol. The native contract
is now exposed through [common MCP resolve/bind/explain routes](mcp.md).

```sh
golem pack resolve WORK REQUEST.json
golem pack bind WORK REQUEST.json --approve-binding EXACT_BINDING_DIGEST
golem pack explain WORK
```

`golem_workpack_resolve`, `golem_workpack_bind`, `golem_workpack_explain` implement the
native contract. CLI only loads inputs, opens the native shared/exclusive Work handle,
passes the separately supplied approval digest, emits full JSON and closes the store.
Existing optional native/CLI command recording remains active under its own contract.

## Explicit request and supported mapping

The request is strict JSON, <=128 KiB, with exactly seven fields:

```json
{"schema_version":1,"key":"bind-one","selection_id":"selection","expected_generation":4,"mapping":"native-documents-v1","role_contract_digest":"<existing native role validate digest>","pack_json":"<exact manifest JSON encoded as a string>"}
```

The manifest remains the M1 schema and <=64 KiB. Its exact string bytes, including
whitespace, identify it. Duplicate keys, NUL/invalid UTF-8, unknown fields/mapping,
invalid IDs, missing/stale generation, unsupported Core version or changed role hash
fail. A stored event is additionally bounded by the native 256 KiB record limit.

All of these must hold; unsupported cases return native errors, never successful
placeholder bindings:

| Requirement | Supported evidence |
| --- | --- |
| Selection | Native CURRENT stage-selection in `documents` mode |
| Role mapping | Already enrolled immutable native role contract for the same selection; exact digest; `allowed_effects:NONE`; all predicates MARKDOWN and no independent-review requirement |
| Pack roles | Exact set of enrolled native rule role names; no automatic enrollment or custom role inference |
| Pack inputs | Exactly `["selection"]` |
| Pack evidence | Exactly `["native-role-assessment"]` |
| Pack capabilities | Nonempty subset of `document.read` and `role.evaluate`; existing native read/evaluation APIs, no execution dispatch |
| Pack prohibited effects | Nonempty subset of `execution.run`, `network.upload`, `release.publish`; the binding mapping provides none of these effects |
| Owner/fence | Trusted local caller plus exact reviewed digest; **any session history blocks** because this mapping cannot authenticate a session owner/fence |
| Policy | Existing DENY and ASK_ALWAYS block; native deadline/boot checks remain in force |

The reference Truthound release Pack is **not bindable** by this first mapping.
External tools, development/QA execution mappings, custom roles, independent principals
and semantic release evaluation remain unsupported; they are not merely untested.
A binding neither expands nor rewrites existing Work permissions. Its capability set
is the ceiling of this mapping, not a new global interceptor for unrelated native
commands. Later native operations retain their original gates and completion predicate.
READY_FOR_RELEASE is still a manifest declaration, not proof that a release is safe.
Only existing native completion can decide its own document Work completion; semantic
Pack completion/release authorization is not evaluated by M4.

## Approval, persistence and replay

Resolve performs no CAS/event writes. It returns REVIEW_REQUIRED, authorized:false,
and a `binding_digest` over a native-generated, domain-separated scope containing the
exact request digest, Work specification digest, previous Work frame, manifest digest
and current selection manifest digest. The request pins the existing role contract.
An event added after resolve changes the scope even when document generation does not.
The owner must separately select the exact digest. Execution/role approval digests and
M2 drafts cannot substitute for it. Local attestation is not cryptographic human identity.

Bind requires the native writable lock and generation precondition. It stores exact
manifest bytes in existing CAS, prepares the bounded record/reply and publishes a
single `workpack-binding` schema_version 1 event with request_json, scope and
approved_binding through the existing hash chain. One binding per Work, no overwrite,
unbind, migration, policy application or automatic rollback. A different key/content
cannot bypass that invariant. Exact raw request and matching approval return the
historical receipt without publication; this is not renewed or current authority.

Open/replay validates request, mapping at the historical prefix, exact scope/digest,
CAS bytes and uniqueness before adoption. Legacy Works without the event still open.
A pre-M4 reader rejects the new event; it must not silently ignore the binding.
Preserve the new reader and records after opting in. No production Work was opted in
by the implementation task.

Any native publication I/O error poisons the writer. Close/reopen is required, not an
automatic retry; a failure can leave unreferenced CAS or a committed event whose reply
was lost. Fault fixtures cover failure before publication and after durable publication.
They retain output sentinels and prove that poisoned handles reject another call;
read-only reopen observes absent/present history without redispatch or repair.

## Explain and validation

Explain returns the historical binding/receipt and separately current_mapping,
current_generation and a native blocker. It rechecks current selection identity,
policy/role mapping, session/deadline state and manifest CAS integrity. A revised
selection can make current applicability BLOCKED while the historical receipt remains
unchanged. Ordinary document progress need not change the selection identity.
`execution_authorized:false` and `pack_completion:NOT_EVALUATED_USE_NATIVE_COMPLETION`
are explicit. APPLICABLE means this limited mapping still matches, never QA PASS/DONE.

Fixtures use disposable document Works only. They cover exact/missing/wrong approval,
read-only mutation denial, DENY/ASK_ALWAYS, key/content conflicts, lock contention,
role-event drift, selection drift, unsupported requirements, session history, CAS
tampering, old-reader rejection, replay and pre/post-publication I/O uncertainty.
Set CMake `GOLEM_WORKPACK_BASELINE_CLI` to a reviewed pre-M4 native executable to run
old-reader comparison; without one the fixture explicitly prints that comparison
NOT_RUN, while current-native tests still execute. See [validation](development-plan.md).

The exact approval scope also pins the native Core version used at binding. Replay validates compatibility against that historical version; `explain` checks the current reader version separately. A later incompatible Core therefore keeps the historical receipt readable and reports `BLOCKED`, without granting current applicability.
