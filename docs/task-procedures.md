# Task-specific procedure selection

`agent_io.py procedure` automatically chooses a procedure from structured task
declarations and invokes the existing native workflow selector. Unlike `guide`,
it produces a scope-bound selection proposal and ordered procedural actions,
with the command, producer/source identities, exit code and original logs captured
by the existing observation runner. No new scheduler or permission system is added.

## Contract

Create an intent using the exact registered scope reference:

```json
{
  "schema": "golem.procedure-intent.v1",
  "activities": ["docs", "code"],
  "scope": {"document_id": "scope", "revision": 1, "digest": "REPLACE_WITH_MANIFEST_SHA256"}
}
```

```sh
python3 tools/agent_io.py procedure --intent intent.json --cli "$GOLEM" \
  --work "$WORK" --cwd "$REPOSITORY" --output "$NEW_PRIVATE_BUNDLE"
python3 tools/agent_io.py procedure-view "$NEW_PRIVATE_BUNDLE"
python3 tools/agent_io.py raw "$NEW_PRIVATE_BUNDLE" --step selection
```

Use absolute CLI/Work paths; output must be new and outside both repository and
Work. The example digest is deliberately not valid. Intent fields are closed;
unknown versions/activities/fields, duplicate activities and invalid references
fail before command dispatch. Activity declarations are caller judgments, not
facts inferred from file extensions, natural-language requests or README text.
An inaccurate declaration is not detected by this classifier.

| Activities | Selected procedure | Additional obligations |
| --- | --- | --- |
| docs only | documents | Managed document QA, review, completion |
| code, optionally docs | development | Reviewed contract, prepare/finish, observed QA |
| deploy, with any others | development plus deployment handoff | Exact-action host approval, effect reconciliation |

The finite precedence table is `docs < code < deploy`. All seven nonempty subsets
and their permutations are tested. No arbitrary expressions, plugin hooks or
shell snippets enter the routing table. New routes require a reviewed policy
change and tests, not an unchecked configuration file. Policy and intent hashes
identify the decision basis; reordered declarations may have different intent
hashes despite selecting the same procedure.

## Execution Boundary

The only automatically executed command is native `workflow select`. It validates
scope readiness/freshness and derives UX/publishing applicability. The adapter
does not duplicate that logic or remove mandatory planning, QA and audit stages.
The returned scope reference must match the complete supplied reference, including
digest. A successful subprocess with a mismatching reference is not a proposal.

`procedure` lists ordered actions, all `NOT_EVALUATED`. They are a procedure
recipe, not a resumed execution state machine. Register the embedded selection
through the existing document policy, then use native `workflow next`, session
and execution APIs. Their current-state checks govern each actual transition,
including claims, leases, reviewed contracts, source freshness, reentry and
completion. These actions must not be executed blindly as a fixed linear script.
Conditional stages and failures can require additional work or revision.

Deploy explicitly returns `BLOCKED_PENDING_SCOPED_HOST_INTEGRATION`. The CLI cannot
authenticate an operator or grant an approval; a project host must bind the exact
external action to the existing receipted execution API. The procedural checklist
is not a new enforced deployment gate. No production deployment, rollback,
automatic retry, permission grant or completion claim occurs here.

Documents mode still requires QA documents but never invents executable QA PASS.
Review/completion obligations are unchanged even for small documentation tasks.
The generated selection has no new schema; existing registration checks remain
authoritative and prevent stale proposals from becoming current inputs.

## Evidence and Failure

Intent, route, plan, raw streams and producer/source identities share the existing
bundle inventory. `procedure-view` verifies the inventory and regenerates the
route under the current policy before rendering. Policy changes fail closed;
inspect original logs with matching tooling or create a new observation. Hashes
are local integrity/identity checks, not signatures against a malicious writer.
An offline proposal is historical, not live readiness or a reusable approval.

Native failure, timeout or incomplete capture produces no proposal. A digest
mismatch preserves even a successful native output for investigation; its raw
observation may say `RECORDED`, while procedure validation fails with
`PROCEDURE_EVIDENCE`. Neither status means QA PASS. Original failure logs remain
available through `view`/`raw`. No effects are retried. Existing commands, explicit
command plans and `guide` document routing retain their behavior.

## Research Basis

- [Calvanese et al., Semantics and Analysis of DMN Decision Tables (2016)](https://arxiv.org/html/1603.07466v1),
  introduction and sections 2.1-2.2: decision logic is separate from control flow;
  missing and overlapping rules are correctness concerns. Applied here as a small
  closed decision domain with exhaustive permutation tests, not the paper's
  geometric algorithms or a general DMN implementation.
- [OMG DMN 1.4 specification landing page](https://www.omg.org/spec/DMN/1.4/About-DMN):
  versioned decision-model reference. The PDF retrieval failed in this research
  session; this adapter does not claim DMN conformance or full-specification review.
- [Lamport, Specifying Systems (2002), section 5.7, printed pp. 61-62](https://lamport.azurewebsites.net/tla/book-21-07-04.pdf):
  invariance distinguishes properties of states from preservation by transitions.
  Applied as explicit non-authorization and non-weakening test properties. No
  TLA+ specification, model checking or formal proof was performed.
- [van der Aalst and van Hee, Workflow Management: Models, Methods, and Systems](https://mitpress.mit.edu/9780262720465/workflow-management/):
  publisher description and bibliographic details reviewed, not the full book.
  Useful modeling context, not independent evidence for implementation correctness.

The implementation decisions above are engineering inferences from these sources
and the repository's existing workflow, execution and approval contracts. No
token/cost reduction, semantic task-classification accuracy or deployment safety
improvement has been empirically measured. Automatic procedure *selection* is
implemented; automatic effect execution and general autonomous task classification
remain out of scope.
