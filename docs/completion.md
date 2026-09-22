# Completion and Interruption Recovery

Golem verifies declared development acceptance, records an immutable completion
receipt, and restores Markdown projections without rerunning an agent or test.
The current Codex/Claude/other client remains the worker.

## Contract

`golem.completion.development.v1` requires:

- A current development-mode stage selection and its entire required document
  closure, including the agent-authored completion document. Parent references
  and CAS bytes must match. Conditional UX/publishing decisions are preserved.
- Engine-issued schema-5 development and QA results for the same checkpoint and
  source snapshot. QA must be PASS, with the enrolled gate identities/versions.
  The live source is observed again; old PASS plus new code is rejected.
- No active session, unresolved dispatch, unissued execution receipt, or
  unsubmitted QA attempt in this Work. Earlier failed results may remain, but
  must have been registered. Expired ownership is not completion.
- No declared blocking issue. Nonblocking issues require existing evidence.
  These classifications are agent statements, not independent adjudication.
- Existing permission and reentry limits. Receipt issuance does not authorize
  execution, change gates, grant a lease, or reset a repair budget.

Noop/schema-4 claims and document-only selections cannot receive a development
completion receipt. Document-only acceptance needs a separate predicate; this
version fails closed rather than labelling it real development completion.
Passing declared gates is not proof that the user's prose requirement is fully
implemented or that all defects are absent. Independent review is explicitly
`false`; an authored audit document does not authenticate an independent reviewer.

## CLI

After registering the final schema-5 QA result and authored completion document:

```sh
golem completion validate finalize.json
golem completion call /path/to/work finalize.json
golem completion report /path/to/work 1
golem completion call /path/to/work resume.json
golem workflow next /path/to/work selection
```

`finalize.json` (replace generation with the current document generation):

```json
{
  "schema_version": 1,
  "operation": "finalize",
  "selection_id": "selection",
  "key": "completion-1",
  "expected_generation": 9,
  "issues": []
}
```

An issue has exactly `id`, boolean `blocking`, `description`, and SHA-256
`evidence_digest`. Blocking issues reject finalization. At most 32 issues, 4096
bytes per description, 64 completion records per Work, and existing JSON/body
limits apply. Unknown/duplicate fields, wrong types, and malformed digests fail.

`resume.json`:

```json
{"schema_version":1,"operation":"resume","selection_id":"selection"}
```

`finalize` returns `RECORDED`, not DONE. Its receipt digest identifies the event
in the Work journal. Retry the exact key and request after an uncertain response;
the original receipt is returned, even if it has since become historical.
Changing a request under that key fails. Changing only the key cannot duplicate
a completion at the same selection/document generation.

`resume` is read-only and reports current action, document refs, failure history,
session boundary, dispatch states, current/stale result evidence, and the latest
historical completion when one exists. Source inspection may run the existing
read-only Git probes; it never claims a session or dispatches an agent/QA gate.

| Action | Meaning |
| --- | --- |
| AUTHOR_DOCUMENT / REVISE_DOCUMENT | Continue existing workflow with current inputs |
| CLASSIFY_FAILURE / INVESTIGATE / BLOCKED | Follow Phase 26 diagnosis/policy |
| VERIFY_COMPLETION | Required documents exist; finalization is still required |
| WAIT | An existing live claim owns work |
| RECONCILE_SESSION | Use the session resume/reconcile protocol; no old lease restoration |
| RECONCILE_EXECUTION | Inspect attempts; do not automatically retry an uncertain command |
| RECOVER_REPORT | Receipt is current, but required Markdown projection is missing |
| REVALIDATE_COMPLETION | Historical receipt cannot establish current completion |
| DONE | Acceptance is current and required Markdown bytes are materialized |

An attempt marked `RECOVER_EXECUTION_RECEIPT` has a durable done marker but no
issued receipt. Use the original execution request/attempt, subject to its existing
contract checks; completion does not manufacture a QA result. `SUBMIT_RESULT`
means an issued QA receipt lacks a registered result document. A `.started`
without `.done` is an uncertain effect, not permission to rerun. There is no
automatic operator override for this boundary in this version.

## Storage and Recovery

Files live under the caller-selected Work directory:

```text
WORK/
  events/NNNNNNNN.evt
  objects/sha256/xx/...
  documents/<id>/rNNNN.md
  completions/rNNNN/completion.md
```

Persistence order: acceptance observation -> report CAS -> event CAS -> durable
Work journal frame -> explicit Markdown materialization. The event commits the
request, predicate/version and policy digest, selected document refs, snapshot,
QA/development receipts, agent issue declarations, session/attempt boundary,
reentry count, timestamp, event sequence and evidence-root digest.

Report bytes are generated from the recorded assessment, not live Markdown or
new agent prose. `report` restores the recorded selected document projections as
well as `completion.md`. Existing different bytes are rejected, never replaced.
Historical reports remain recoverable after subsequent source/document changes;
recovering one does not make it current. Any new document generation conservatively
requires revalidation, even if a particular edit is unrelated.

| Interrupted boundary | Outcome |
| --- | --- |
| Before CAS | No completion; drafts and user changes remain untouched |
| CAS before event | Orphan bytes do not establish completion |
| Event before report | RECOVER_REPORT; exact original bytes can be restored |
| Projection partially restored | Repeat report; equal bytes are accepted |
| Receipt response lost | Same key returns same receipt; no new journal event |
| Command started, result not durable | Reconcile; completion never reruns it |
| Missing/corrupt event or CAS | Fail closed; never infer success from Markdown |

Replay checks the historical document prefix, policy/assessment equality, report
digest and CAS, without observing today's source or reexecuting commands.
Current verification separately checks today's source and ownership. Completed
work does not expire merely because an old repair execution deadline expires.

## C API and Boundaries

`include/golem/completion.h` exports validate/call/report. Borrow input bytes and
store for the call; output transfers malloc ownership and is released with
`golem_execution_reply_free`. Output is unchanged on failure. Store writer locking
serializes mutation. An I/O error after commit may mean a receipt exists: reopen
and retry the same key. Report restoration requires writable store access.

The predicate, durable store, recovery inspection, and Markdown projection are
separate C modules. New acceptance modes require a versioned predicate, not
weakening this version. No new database, background daemon, UI or provider SDK.
The v1 report rendering is part of replay compatibility: changes to its bytes
require an explicit version/migration rather than rewriting existing receipts.

Trust boundaries: local storage/OS and enrolled test programs are trusted; the
runner is not a sandbox. Snapshots cover configured paths, not every possible
external dependency, and concurrent external edits cannot be atomically locked
with journal commit. Timestamps are informational wall time, not authority.
Digests do not authenticate reviewers or prevent whole-store rollback by its
owner. There is no distributed exactly-once or formal correctness proof.
The retained session head and dispatched attempt markers are checked during
completion replay: losing an entire side journal is not treated as empty history.

## Research Basis

- [OSTEP, Crash Consistency: FSCK and Journaling](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf),
  journal commit/checkpoint/recovery discussion: separate committed facts from
  reconstructible projections. Applied as an application-level protocol, not as
  an implementation of a filesystem journal or ARIES.
- [Pillai et al., OSDI 2014](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-pillai.pdf),
  sections 2 and application update protocols: atomicity and persistence ordering
  depend on filesystem behavior. Reuse explicit file/directory fsync and test
  boundary states; logical fault fixtures do not prove power-loss safety.
- [Hawblitzel et al., IronFleet, SOSP 2015](https://www.microsoft.com/en-us/research/wp-content/uploads/2015/10/ironfleet.pdf),
  sections 2-3: distinguish specification, implementation and assumptions, and
  safety from eventual progress. Golem uses executable predicates/tests, not the
  paper's machine-checked proofs, and does not inherit its formal guarantees.
- [Google SRE, Data Integrity](https://sre.google/sre-book/data-integrity/):
  restoration must be exercised, not inferred from successful storage. Test
  missing reports and repeat recovery while retaining immutable originals.

These sources motivate the design; they do not establish this implementation's
correctness or certify the semantic quality of an agent's work.
