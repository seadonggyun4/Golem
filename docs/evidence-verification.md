# Per-evidence Verification Contract

`tools/evidence_contract.py` defines `golem.evidence-verification.v1`.
`tools/evidence_adapters.py` derives it from concrete evidence. Shape validation
and domain interpretation are separate; neither replaces native QA/completion.
There is no numeric confidence score, ordinal trust ladder, or universal PASS.

## Independent dimensions

| Check | States | Meaning |
| --- | --- | --- |
| integrity | MATCH / MISMATCH / NOT_CHECKED | Bytes match an expected digest/inventory; not authenticity or truth |
| statement | DECLARED / NOT_PRESENT | An actor made a claim; identity is declared |
| parser | VALID / INVALID / NOT_RUN | The named parser checked the named scope; not semantic truth |
| execution | OBSERVED / INCOMPLETE / NOT_OBSERVED | Recorded process lifecycle; exit=0 is not correctness |
| independent_review | DECLARED / REJECTED / NOT_OBSERVED | A scoped review declaration; distinct IDs do not prove independent people |
| authenticity | NOT_VERIFIED | Current adapters do not authenticate producers or reviewers |

Each performed check requires its method, scope and bounded content-addressed
references. Statement/review require actor attribution. Unperformed checks cannot
contain claims of work done. Subject digest and kind bind each assessment to a
specific artifact; optional project/Work binding is explicit. A failed parser does
not erase a successful hash check, and a valid parser can describe a failing test.
Absent checks are explicit, not silently false or zero.

[Scoped evidence export](evidence-export.md) can retain the subject/check references
of this envelope as a bounded standalone graph. Missing/excluded references remain
explicit; successful export verification does not upgrade any verification dimension.

`content_truth=NOT_ESTABLISHED` and `acceptance_authorized=false` are mandatory.
The v1 contract rejects forged TRUE/authenticated/review-verified states. Validation
checks schema consistency, **not** the truth of supplied metadata. Receivers must
derive checks through a trusted adapter and retain its original inputs; an attacker
can fabricate a structurally valid unsigned observation. Hashes cannot prevent this.
Claims about identity/signatures require a separately reviewed authenticated adapter
and versioned contract extension; no caller-controlled VERIFIED flag is accepted.

Bounds: six dimensions, 32 unique SHA-256 references per check, 256 characters per
scope/method/actor, existing bounded input JSON. Unrecognized fields/states fail
closed. The common contract has no dependency on provider or research schemas.

## Domain adapters and existing consumers

- `observation`: validates an intact `agent_io` bundle and exact record revision,
  command plan and Work attribution. Stdout is its own subject when captured.
  Parser scope is the **recorder envelope**, not arbitrary stdout content. Nonzero
  exit remains observed execution; timeout/missing launch is incomplete, later
  NOT_RUN steps have no execution claim. No content truth or independent review.
- `declaration`: attributes text to a declared user/agent. Computing its hash alone
  is NOT_CHECKED integrity, not a comparison with an independent reference.
- `review`: binds a typed review statement to the expected artifact digest and Work.
  Subject mismatch or identical author/reviewer IDs is REJECTED. Distinct IDs yield
  DECLARED, never authenticated independence. APPROVE/REJECT/NEEDS_WORK are separate
  domain decisions, not a verification level. No human review is manufactured.
- `research-outcome`: projects each legacy native observation independently.
  Legacy status=PASS remains a declared case result. Parser scope covers only the
  observation fields; it does not validate the entire native research model or
  dereference CAS. A digest reference alone is NOT_CHECKED integrity and does not
  prove execution. Existing native v1 storage/predicate remains unchanged.

`judgment_record` views now include `evidence_verification` per judgment. Fact
references do not turn an interpretation into execution evidence. Its bundle hash
check covers the retained judgment snapshot/chain, not omitted original raw logs.
`revision_status` evidence rows now include `verification`: envelope hash checks,
scoped domain parser checks and observed execution remain distinct from the domain
status PASS/FAIL. Captured GitHub responses are provider statements, not authenticated
provider attestations. Native completion authority is unchanged.

This is implemented for these consumers and adapters, not a physical rewrite of
all native CAS records or every older export/report. Legacy formats remain readable.
No missing check is inferred from the legacy PASS field.

## CLI

```sh
python3 tools/evidence_adapters.py observation BUNDLE \
  --revision RECORD_SHA256 --step STEP --project-id PROJECT --work-id WORK
python3 tools/evidence_adapters.py declaration CLAIM.txt \
  --actor user --project-id PROJECT --work-id WORK
python3 tools/evidence_adapters.py research-outcome OUTCOME.json \
  --actor agent --project-id PROJECT --work-id WORK
python3 tools/evidence_adapters.py review ARTIFACT \
  --statement REVIEW.json --sha256 ARTIFACT_SHA256 --project-id PROJECT --work-id WORK
```

Review statement fields: `schema=golem.evidence-review.v1`, `subject_sha256`,
`binding` (project_id/work_id), `author`, `reviewer`, `scope`, and
`decision` (APPROVE/REJECT/NEEDS_WORK). The review CLI preserves the declared
decision separately in a review-view envelope. No command is executed except
existing local recorder operations chosen elsewhere. No report or rewritten
evidence is generated. CLI exit=0 means successful projection, not truthful content.

## Research Basis

Reviewed material and specific design applications:

- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/), core entities, activities and
  attribution: retain subject, operation and actor separately. No PROV serialization
  compliance or producer authentication follows from provenance alone.
- Bloomfield and Rushby, *Confidence in Assurance 2.0 Cases*, Springer LNCS 14780
  (2024), expanded [2025 text](https://arxiv.org/html/2409.10665v2), introduction,
  logical assessment and confidence-in-evidence sections: claims, evidence and
  reasoning have different roles; retain unresolved assumptions instead of treating
  one check as proof of the whole claim. No assurance-case calculus is implemented.
- Goodenough, Klein and Weinstock, *Measuring Assurance Case Confidence using
  Baconian Probabilities*, ASSURE 2013,
  [primary abstract](https://www.sei.cmu.edu/library/measuring-assurance-case-confidence-using-baconian-probabilities/):
  confidence concerns eliminated doubts; avoid an unvalidated scalar score. Only
  the abstract was consulted, not a claimed reproduction of the method.
- Winters, Manshreck and Wright (eds.), *Software Engineering at Google* (2020),
  [chapter 9, review roles](https://abseil.io/resources/swe-book/html/ch09.html):
  distinguish another engineer's review from ownership approval and author claims.
  Declared IDs in Golem cannot establish the real-world identity/independence that
  such a process relies on. The public chapter was consulted, not the entire book.

Tests exercise actual recorded subprocesses, invalid/valid domain results, legacy
declarations, review identity/scope mismatch, timeout and skipped execution. They
do not establish content truth or an actual independent human review.
