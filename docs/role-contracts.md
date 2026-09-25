# Role Contracts and Deliverable Assessments

Golem can require role-specific evidence before document Work completion. The
current agent authors and submits documents; these APIs never spawn an agent,
execute a QA command, grant a lease, or approve code changes.

## Contract

`golem role template NAME` emits a versioned, validated data template. Combine
rules into one reviewed contract before enrollment; templates are not scripts.

| Template / role | Kind | Predicate | Required evidence |
| --- | --- | --- | --- |
| `implementer` | development-result | DEVELOPMENT | Current registered result, issued development receipt, checkpoint v4/v5 change inventory, live source |
| `no-change` | development-result | NO_CHANGE | DEVELOPMENT plus identical checkpoint baseline and observed final snapshot |
| `qa` | qa-result | QA_PASS | Issued QA receipt, declared cases, observed PASS, exact generated Markdown, live source |
| `reviewer` | completion | REVIEW | Exact input closure, structured findings/decision, bound development inventory and QA receipt in development mode |
| `researcher` | planning | MARKDOWN | Registered, structurally valid, current Markdown and verified reference closure |
| `doc-only` | planning by default | MARKDOWN | Same structural checks; kind/stage may select another documentary deliverable |

Researcher/doc-only templates default to `documents`; other templates default to
`development`. `development` is also an alias for the implementer template.
One kind may have only one rule. The existing stage selection still determines
all required documents: a single rule does not delete other required stages.

```json
{
  "schema_version": 1,
  "id": "implementation-and-qa",
  "mode": "development",
  "allowed_effects": "NONE",
  "max_assessments": 16,
  "rules": [
    {"role":"implementer","stage":"development","kind":"development-result","predicate":"DEVELOPMENT","independent_review":false},
    {"role":"qa","stage":"qa","kind":"qa-result","predicate":"QA_PASS","independent_review":false}
  ]
}
```

Contracts/requests are bounded at 64 KiB, with at most 64 rules and 1..32
assessments. Unique kinds currently further limit a contract to eight rules.
The Work reserves 64 role event slots independently of document revisions.
Unknown fields/versions, duplicate keys, executable predicates, incompatible
stage/kind/role combinations and rules for omitted stages are rejected.

## Enrollment and CLI

```sh
golem role template implementer
golem role validate contract.json
golem role call /path/to/work enroll.json --approve-contract "$APPROVED_DIGEST"
golem role call /path/to/work assess.json
golem workflow next /path/to/work selection
```

The operator reviews the contract and obtains `contract_digest` from `validate`.
Enrollment requires that digest through a trusted local caller. Like execution
contract approval, this is not a signature or an authenticated human identity.
The digest hashes engine-serialized JSON with original member order, not raw
whitespace and not RFC 8785 canonical JSON. Use the same contract object.

`enroll.json` has exactly `schema_version:1`, `operation:"enroll"`,
`selection_id`, unique `key`, `expected_generation`, and the `contract` object.
Generation is the current document generation, not the role-event count.

Enrollment is **one immutable Work obligation**, bound to a selection ID across
its revisions. It cannot be deleted, replaced, or bypassed with another selection
or the old completion predicate. Mode changes fail closed. Correct a mistaken
contract by starting a separately approved Work, not editing the journal.
`DENY` and `ASK_ALWAYS` continue to block writes; the digest flag cannot override
them. Durable approval/independent identity protocols are separate features.

Example `assess.json` (replace generation):

```json
{"schema_version":1,"operation":"assess","selection_id":"selection","key":"assessment-1","expected_generation":9,"review":null}
```

`evaluate` has the same fields but performs a live, read-only assessment without
writing a receipt or consuming an attempt. It cannot satisfy the completion
receipt requirement. `status` takes only `schema_version:1`, `operation:"status"`
and `selection_id`; it returns historical enrollment/latest assessment, not a
new live verdict. Exact parsed-request retries return the original receipt;
reuse of a key with different request values is rejected.

For a reviewer, `review` contains exactly:

- `document`: the completion document's `{document_id, revision, digest}`.
- `targets`: exact three-field refs for **every** entry in that document's
  `input_manifest.documents`, without its additional projection fields.
- `decision`: `ACCEPT` or `REVISE`.
- `findings`: up to 32 unique `{id, blocking, description}` entries;
  descriptions are limited to 4096 bytes.
- `qa_receipt`: the referenced QA receipt digest in development mode, or `""`
  in documents mode.

Approval text alone does not count. Only ACCEPT with no blocking finding and
verified inputs satisfies REVIEW. This verifies bindings, not the truth or
completeness of a reviewer's prose. `independent_review:true` remains BLOCKED:
the present role API does not authenticate independent principals.

## Reentry and Completion

Each rule reports SATISFIED, MISSING, STALE, INVALID or BLOCKED, with its document,
input digest, declared producer attempt and issued execution receipt when present.
The aggregate is SATISFIED only if every rule passes. Declared producer IDs do not
authenticate a session. Missing/changed CAS or edited projections fail closed.

`assess` commits an immutable `roles` event through the existing hash-chained Work
ledger and CAS. Its digest is the receipt. Failed assessments identify the root
kind and dependency descendants in `affected`, never unrelated UX ancestors.
`workflow next`, and therefore current-agent next/resume, expose historical
`deliverable_feedback` plus its receipt. Existing observed-QA classification has
precedence. When the document closure is otherwise ready, unmet role evidence
selects AUTHOR_DOCUMENT / REVISE_DOCUMENT / BLOCKED instead of completion.
Unassessed or changed evidence asks for ASSESS_DELIVERABLES. Exhausted assessment
budgets block further assessment; evaluation does not reset that limit.

This feedback does not forge a failed QA result, execute a repair, or rewrite
registered revisions. The agent revises the affected documents; the existing
dependency graph makes dependent revisions stale. Then it obtains a new
assessment. Actual QA failures continue through the existing reentry protocol.

Enrolled Works use the existing completion command with **request version 2**:

```json
{"schema_version":2,"operation":"finalize","selection_id":"selection","key":"done-roles-1","expected_generation":9,"issues":[]}
```

The predicate is `golem.completion.roles.v1`, with a separate renderer. It requires
the latest recorded assessment to match a fresh SATISFIED evaluation.
Development mode additionally retains every existing development/QA/completion
gate. Documents mode validates the full required document closure without
claiming code execution or test PASS; it rejects declared issues and cannot
bypass previously enrolled research/QA obligations.
`completion report` and version-1 `resume` are unchanged. Historical receipts
remain readable; only a fresh resume can claim DONE for the current source.

Replay rechecks prefix-local integrity and preserves recorded live failures
without inspecting today's source. It is not permission to trust a stale PASS:
live finalize/resume reobserve source. Earlier evaluators/renderers and legacy
golden fixtures are unchanged. Older readers reject the unknown `roles` event
instead of silently skipping an obligation. No downgrade writer is supported.

## Library and Trust Boundary

`include/golem/role_contract.h` exposes contract/request validation, template
generation, and `golem_role_call`. Inputs are borrowed, replies are owned and
released with `golem_execution_reply_free`, and failed calls leave outputs
unchanged. Store/graph storage uses the existing allocator; JSON objects and
serialized replies retain the existing json-c/execution allocation convention.
No new provider dependency, regex engine, network service, or script evaluator
is introduced. Future predicate/schema changes require a new version, not edits
to the recorded evaluator's meaning.

This remains a cooperative local runtime. An attacker with full control of the
OS account, executable and entire ledger can replace them; digests are not
authentication. Structural Markdown checks cannot establish research validity,
semantic correctness, or defect absence. See [completion](completion.md),
[execution](execution.md) and [research outcome contracts](outcome.md).
