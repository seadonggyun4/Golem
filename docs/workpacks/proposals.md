# M5: role evaluation and untrusted verifier proposals

Implemented for existing **native-documents-v1 bindings only**. M5 adds no role,
principal authentication, permission, binding format or persisted event. It connects
the enrolled native document roles to their existing live `evaluate` operation and
keeps verifier statements separate. General development/external/session-owner and
independent-principal mappings remain unsupported, as in M4.

```sh
golem pack proposal-validate proposal.json
golem pack assess WORK proposal.json [other-proposal.json ...]
```

The native APIs are `golem_workpack_proposal_validate` (pure borrowed bytes) and
`golem_workpack_assess` (read-only shared Work handle). CLI uses the M2 no-follow,
regular-file, single-link, bounded snapshot reader. No Python runtime/reducer,
network, provider setup, subprocess, model invocation or client update is involved.
CLI exits 0 on successful observation, 1 on native/input/output error, 2 on usage.
Successful observation does not mean the proposal is true or the Work is complete.

## Closed proposal v0

See the [structural sample](../../samples/workpacks/verifier-proposal.json). Its
placeholder hashes make it structurally valid but unusable against an actual Work.
The proposal is strict UTF-8 JSON <=64 KiB, with exactly these fields:

| Field | Contract |
| --- | --- |
| `schema` | `golem.workpack.verifier-proposal.v0` |
| `proposal_id` | Existing native ID grammar, <=64 ASCII bytes |
| `work` | Exactly `identity` (native Work ID), `generation` (1..4097) |
| `pack_digest` | Exact bound manifest SHA-256 |
| `binding_receipt` | Exact native binding receipt; Work ID alone is insufficient |
| `contract_digest` | Existing enrolled native role contract digest |
| `artifacts` | 1..32 unique `{digest,size}` pairs; native document body SHA-256 and 1..1 MiB byte count |
| `verifier` | Exactly `principal_ref`, `model_declared`, `provider_declared` (native ID tokens), `status` |
| `findings` | 0..32 unique `{id,severity,summary,evidence_refs}` |
| `confidence` | `UNCERTAIN`, `LIMITED`, `SUPPORTED`; not a calibrated probability |
| `limitations`, `unresolved_questions` | 0..32 narrative strings each |
| `recommendation` | `NEEDS_OWNER_REVIEW`, `REJECT_PROPOSAL`, `NO_BLOCKING_FINDING_OBSERVED` |

Status is `SUCCEEDED`, `FAILED` or `UNKNOWN`, always caller-declared. FAILED/UNKNOWN
must use NEEDS_OWNER_REVIEW. Findings severity is INFO/WARNING/BLOCKING; each finding
has 1..32 distinct references to digests in that proposal's artifacts. Narrative
strings are nonblank, <=2048 UTF-8 bytes, without ASCII control bytes. Unknown fields,
duplicate JSON keys, invalid UTF-8/NUL, duplicate artifact/finding IDs, unresolved
references and values beyond bounds fail closed. No executable/path/API-key/raw
reasoning fields exist. Text is inert data; this is **not semantic secret detection
or prompt-injection sanitization**. Callers must omit secrets, hidden reasoning and
unnecessary data values before supplying input.

Validation returns an exact-byte digest, not approval or verified provenance. The CLI
report explicitly sets `authorized:false` and `identity_verified:false`. No input file
is rewritten, and native output stays unchanged on error.

## Work-bound assessment

Assessment accepts 1..8 proposals. It first reuses M4 explain to require a currently
applicable binding (including native policy, deadline, session-history and selection
checks). It compares each proposal's Work/generation, binding receipt, manifest and
role contract to that store. The binding is never recreated or implicitly selected.

Allowed evidence comes from the current bound selection, existing enrolled role
outputs and their transitive native document parents. Existing native graph selection,
freshness, CAS verification and projection integrity checks are reused. Every supplied
`{digest,size}` must match a body in that closure. Arbitrary CAS objects, foreign or
stale documents and mismatched sizes are rejected. This is not a general evidence
reader or a caller-defined allowlist. It observes byte identity and current native
bindings, not truth, source authorship or actual model inspection.

Two proposals with the same proposal ID or declared principal token are rejected,
including byte-identical duplicates. Different tokens **do not prove different
workers or independent owners**. Owner/self-approval fields are rejected; no statement
can satisfy identity, separation of duties, approval or a missing execution receipt.
M4 continues to block bindings requiring unsupported identities/session ownership.

The existing `golem_role_call` **evaluate** path produces `native_role_evaluation`.
It remains read-only and cannot substitute for a persisted native assessment receipt.
M5 never dispatches assess/enroll, executes QA or calls completion. Existing explicitly
configured native/CLI recording may append its separate audit; M5 does not enable or
bypass it. Fixture environments disable that optional recording when checking that
Work files remain unchanged.

JSON `golem.workpack.assessment.v0` includes:

- `claims`: each proposal in full plus its exact input digest, retaining FAILED/UNKNOWN
  and all limitations, findings and questions. Serialization is not the original bytes.
- `native_role_evaluation`: the separate existing native structured result, even if
  SATISFIED while a proposal failed, or UNSATISFIED despite a reassuring proposal.
- `declared_disagreement`: recommendations or findings differ across the supplied
  batch. This is a syntactic comparison, not semantic agreement detection or a global
  registry of previous proposals. Findings order can make it true.
- `identity_status:UNVERIFIED_DECLARATIONS`, `model_truth:NOT_EVALUATED`,
  `authorized:false`, `completion_evaluated:false`, `decision:NEEDS_OWNER_REVIEW`.

No voting, averaging, automatic approval or conversion to QA PASS/DONE occurs.
A single reassuring proposal still requires owner review. Replies use the existing
256 KiB native bound; oversized combined reports fail without truncation or success
output. Caller files and earlier results remain untouched; no result persistence,
export or retry mechanism is added. Stdout failure can leave partial bytes, which must
not be treated as a successful report. Saved proposals must be rechecked against
current Work before later use. No new storage migration or permission choice is
required for this non-authoritative observation path.

## Validation scope

Fixtures cover native SATISFIED/UNSATISFIED vs claims, FAILED/UNKNOWN and disagreement,
exact bytes, stale generation, foreign binding/contract/artifact, duplicate workers,
forged authority fields, unknown fields, UTF-8 byte/count/size boundaries, output
limits, locks, CAS tampering and unchanged Work/output on failure. The existing M4
suite separately covers unknown session ownership, policy denial and binding drift.
Public API consumer and Work Pack mutation smoke include the new parser. Native
contracts remain canonical. Common MCP proposal_validate/assess delivery is implemented
and covered by protocol/native fixtures; these operations have not received their own
Desktop model E2E. Semantic truth and independent identity are not certified. See
[current verification](mcp.md#verification-status) and [historical results](development-plan.md).
