# Registered Output Rejection

Design recorded before implementation, 2026-10-20. This is separate from the
bounded context-selection change at 265a83a. Use a reviewed SDK containing the
implementation and tests below; an older installed SDK does not acquire this API
merely because this document exists.

## Failure and Boundary

A RUNNING managed attempt can have a registered output of the wrong kind or an
incompatible pinned manifest. Existing submit/ADOPT_OUTPUT correctly refuses it;
NO_EFFECTS would be false because immutable registration already occurred.
Simply clearing the attempt would leave an unreceipted output and could let
workflow consumers treat the wrong revision as current. Do not edit history,
forge a QA failure, migrate the Work or create a replacement Work to bypass it.

Add an explicit session `reject_output` operation only after lawful resume into
RECOVERY_REQUIRED. Bind the existing token, sequence, source and input digest,
the exact registered output, current document generation, Work specification digest, CAS evidence and a
closed approval artifact. The artifact binds the Work, original input generation,
selection reference, current token/sequence and every request reference. It states
REJECT_REGISTERED_OUTPUT and NONE_IDENTIFIED_AFTER_INSPECTION for external effects.
An UNKNOWN declaration or known native execution history blocks this bounded
operation; broader effect reconciliation is not introduced here. Cooperative
local approval is not authenticated identity or proof of an absence of effects.

Only an attributable, demonstrably incompatible registered output may be rejected.
Do not turn a compatible output into a failure to avoid its normal checks. All
outputs attributed to the attempt must be accounted for; this first operation
handles exactly one. Additional outputs or unknown effects stay blocked.

Publish one schema-4 agent event with outcome REJECTED_UNSUCCESSFUL. Store the
reviewed approval once in CAS; the event binds its digest and observed evidence.
The replayed `rejected_outputs` view retains token, output, approval digest,
registered generation, trust, reason and outcome rather than duplicating the
approval/evidence body. Retrieve the approval before inspecting its assertions.
Keep this list separate from accepted `completed` outputs. End the attempt
without PASS, NO_EFFECTS or DONE. Rejection consumes the original attempt budget;
it does not reset revision, attempt, time or policy limits.
Identical request retries return the same receipt; changed bytes under the same
key fail. Existing policy, lifetime lock, clock, lease, owner, binding and sequence
checks remain in force. Session readers without schema-4 support fail closed.
Lease-bound agent mutations also recheck the trusted clock/boot and live lease
after evidence validation, immediately before shared frame publication. This
covers begin, heartbeat, submit, reconcile and reject_output; a lifetime flock
does not extend an expired lease. Prepared CAS objects without a published frame
are not committed dispositions and must not be deleted to guess a recovery.
Old raw document readers do not understand dispositions and must not be used for
current acceptance decisions. Do not downgrade the engine after using this API.

## Consumers and Prevention

An exact rejection disposition accounts for that registered output when checking
unreceipted effects; it is not an acceptance receipt. Current workflow queries must
mark the rejected revision and its dependent current descendants stale, never
promote an older PASS or revision. Repair by ordinary fresh claims and immutable
replacement revisions. Completion must still require real current QA and normal
outcome adjudication. Context selection keeps the rejection and uses full fallback.

Keep historical document replay unchanged: validate every original document against
its original registration prefix. Apply dispositions only to current views and
new writes after full store replay; do not apply future session events while
validating an earlier document prefix. Session replay revalidates each disposition
against retained originals and its recorded generation, not today's generation.

Before new registration of any active-attempt-attributed document, check
kind and exact pinned manifest. Refuse new outputs attributed to a rejected
attempt. Keep bootstrap and unrelated historical registration compatible; this
guard is not a new global claim that all documents require an active session.

## Request and Approval Contract

Use `golem --output-mode full session call WORK REQUEST.json`, or
`golem_agent_session_call`. Request schema remains 1; persisted rejection event
schema is 4. Header feature macro `GOLEM_AGENT_REJECT_OUTPUT_VERSION` is 1.
Request fields are exactly schema_version, operation (`reject_output`), work_id,
key, expected_sequence, token, input_digest, source_snapshot, expected_generation,
output, evidence and approval_digest. Evidence is 1..64 unique existing CAS digests;
output is the exact document_id/revision/digest reference. Use the content digest
returned by `evidence put`, not its distinct receipt_digest, for approval_digest.

The approval JSON has exactly these fields:

| Field | Required value/source |
| --- | --- |
| schema_version | 1 |
| domain | golem.registered-output-rejection.v1 |
| work_id | Exact immutable Work ID |
| work_spec_digest | Active attempt's policy_digest (the immutable Work spec) |
| expected_sequence | Current session sequence, also used in the request |
| token | Exact current epoch/attempt_id/session_id, not an arbitrary past token |
| input_digest | Active attempt's manifest_digest |
| input_generation | Active attempt's original input_generation |
| registered_generation | Current document generation, also request expected_generation |
| source_snapshot | Original active attempt's source_snapshot |
| selection | Exact selection reference in its pinned context manifest |
| output | Exact rejected output reference, equal to request output |
| evidence | Equal to request evidence |
| decision | REJECT_REGISTERED_OUTPUT |
| external_effects | NONE_IDENTIFIED_AFTER_INSPECTION; UNKNOWN does not qualify |
| reason | WRONG_KIND or PINNED_INPUT_MISMATCH, checked against original metadata |

Read status/next first. If the attempt is RUNNING, lawfully resume it into
RECOVERY_REQUIRED; never force a live foreign owner. Export its pinned context
using the new token. Independently inspect the registered effect and original
approval/evidence; create/import the explicit approval only after review. CAS
import does not advance session sequence or document generation. Neither engine
nor wrapper manufactures approval from a failed submit. A compatible output must
use normal ADOPT_OUTPUT; it cannot be rejected by this operation.

Call reject_output with the exact current sequence/generation and pinned source.
This historical source identifies the unsuccessful attempt; it is not permission
to execute stale code. If ownership expires or the state changes, inspect again,
lawfully resume if needed, and obtain a new approval for the new tuple. Preserve
the old artifact. For ambiguous I/O, reopen and retry identical key/request bytes;
do not invent another key or rerun effects. A duplicate receipt is historical,
not a renewed lease. Follow next and normal fresh source/selection/claim gates
after successful disposition. A remaining gate or budget denial is not bypassed.

Inspect the approval with `golem_evidence_read`, or, for an already private owned
Work root, `golem --output-store WORK output read APPROVAL_SHA256`. This is a
read-only existing CAS path; never change Work permissions to make it succeed.

## Version Mixing

All writers must use a verified SDK supporting this contract before it is used.
Do not downgrade or mix writers afterward; do not automatically terminate other
clients. Against the retained f7613b6 macOS binary, session status/claim and native
completion resume/finalize reject the new agent event without mutation. Historical
document inspection remains possible. The old workflow view is not disposition
aware and does not authorize execution.
That older reader reports CORRUPT_JOURNAL at session.log_replay for the unsupported
event. Check the pinned engine and schema support; this is not permission to edit
or remove the new event. Qualification used the actual retained f7613b6 binary
SHA-256 `fc19f68d34bc19bb4a8eb301a58effc89d5b2558d28c9f02f4fea306cb0ad4cf`.

Importantly, the older trusted raw document registration API can still append a
legacy document without reading the newer agent stream. That is registration,
not an acceptance receipt. If it adds another output attributed to the rejected
attempt, the new reader blocks the now-unaccounted effect; it does not silently
accept it. This is an availability risk under unsupported mixed-version writers,
not a claim of universal old-reader fencing. Preserve that evidence and stop;
the single-output contract cannot dispose of the new effect automatically.
No permission changes, broad historical-read ban or silent Work migration is added.

The supported qualification driver is
`tests/c/rejected_output_compatibility.py NEW_CLI SOURCE AGENT_CLIENT CC OLD_CLI NEW_EVIDENCE_DIRECTORY`.
It uses only synthetic Work, preserves command outputs and binary hashes, and
tests reads, authority calls and raw registration separately. Tests on f7613b6
do not establish behavior of every prior SDK or every public entry point.

## Acceptance

First reproduce wrong-kind registration and blocked adoption with a disposable
legacy-format fixture. Preserve its complete CAS/journal prefix through rejection;
do not change permissions or existing evidence. Verify a fresh correct claim and
normal eventual completion, no false QA PASS, exact idempotency/reopen replay,
stale owner/sequence/generation/input/output rejection, missing/changed approval,
unknown effects and rejection of new wrong-kind registrations. Preserve old
session formats and assert older engines reject the new event. Test local native
and sanitizer builds; distinguish actual platform runs from source portability.

## Sources Actually Inspected

Read/revisited 2026-10-20. Saltzer and Schroeder (1975), *The Protection of
Information in Computer Systems*, DOI 10.1109/PROC.1975.9939,
[author-hosted Basic Principles](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html),
principles a-c: keep the mechanism small, default to refusal and mediate recovery
as well as normal operations. These are design warnings, not a security proof.

Fielding, Nottingham and Reschke (2022),
[RFC 9110 sections 9.2.2 and 13.1.1](https://www.rfc-editor.org/rfc/rfc9110.html):
repeat identity and explicit preconditions distinguish safe repetition from guessed
retry. Application here is an analogy for native key/sequence/generation checks;
Golem does not implement an HTTP transaction service or claim HTTP conformance.

Niall Murphy with John Looney and Michael Kacirek, edited by Betsy Beyer,
in *Site Reliability Engineering* (O'Reilly, 2016),
[chapter 7, Consistency and A Platform](https://sre.google/sre-book/automation-at-google/):
centralize a bounded procedure and its repairs rather than repeating manual state
edits. Selected accessible chapter sections, not the whole book, were read.
The earlier original Chubby sequencer reading is documented in
[the preceding decision](lightweight-awe-decision.md). These applications do not
prove external-effect truth or exactly-once execution. No private product evidence
or incident identity belongs in this document.

A. Silberschatz, H. F. Korth and S. Sudarshan, *Database System Concepts*,
7th edition (McGraw-Hill, March 2019), ISBN 9780078022159:
[authors' book site](https://db-book.com/) and
[official chapter 19 companion slides](https://db-book.com/slides-dir/PDF-dir/ch19.pdf),
slides 19.11-19.14 (PDF pages 11-14). The inspected companion sections separate
preparation from durable commit and motivate testing loss before/after that
boundary. The complete textbook was not read. Golem reuses its existing atomic
record publication; it does not implement a database undo/redo engine or roll
back external effects. No slide text, diagrams or algorithms are copied.

## Verification Record

Local platform: macOS 26.5.2 arm64. The first working implementation passed
388/388 dev CTest entries before the final CAS-reference normalization and
legacy-attribution guard tightening. The normalized native implementation passed
22/22 influence-set CTest entries, including 13 rejection cases. Keep those
snapshots distinct; final-commit CI is a separate qualification.

The rejection suite includes both a document-only completion and a separate
same-Work recovery followed by real approved C compilation/testing, native
development/QA receipts, source/checkpoint verification and normal development
completion/report publication. Its source contract covers declared files, not a
whole-project candidate inventory. Exit zero alone is not the completion gate.

Optional `GOLEM_REJECTION_EVIDENCE_OUTPUT` retains the synthetic receipt,
checkpoint, original-prefix hash inventory and copied Work/source for inspection.
Original contract roots refer to temporary fixture paths; the copy is explicitly
not a restoration/restart authority. The observed final-dev example preserved
all 67 pre-existing fixture files byte-for-byte and reached native DONE only
after the new real QA and report. No product Work or private evidence is copied.

A subsequent deterministic clock test exposed a gap between the earlier commit
clock check and frame publication: expiration during validation still committed.
After adding the shared publication guard, expiration, clock rollback and boot
change at that boundary all refuse publication and preserve existing frames.
The resulting code snapshot passed 10/10 dev influence-set tests (16 rejection
cases), 9/9 ASan/UBSan tests, 4/4 Release tests and 483/483 Python tool tests.
The retained f7613b6 public-entry-point qualification was repeated on that binary;
its raw-writer limitation above remains unchanged. These local runs precede the
recovery commit; the exact-commit full-suite and remote CI records must be
qualified separately, not inferred from the earlier 265a83a CI result.

The full CTest process at a1f342f subsequently reported 386/388: approval_cli
and its native_api_scenarios consumer both failed because the explicitly composed
Approval fixture lacked the extracted setup_execution_source helper. Restore
that delegation, not an approval bypass or a skipped test. The retained local
bundle is FAIL; it also records inputs_unchanged=false because the correction was
made after CTest exited but before bundle finalization. It is not an exact-source
qualification. The corrected approval, native-recording and rejection influence
set passed 3/3, followed by 2/2 ASan/UBSan and 2/2 Release approval/rejection
tests; the final commit still requires its own full-suite and CI results.

## SDK Handoff

Build and stage an SDK from the reviewed immutable commit, not a dirty source
tree. Record the full commit, archive/binary/header/library hashes, platform and
dependency versions alongside test evidence. A local unsigned manifest provides
integrity and attribution, not independent authentication. A macOS arm64 build
does not establish Linux binary portability or Windows support; qualify each
target separately. Do not silently change an existing project's installed pin.

Before a project adopts this API, its owner must verify that every writer uses
the new contract, preserve existing evidence and review read-only status/next
with the exact proposed SDK. Use lawful resume and the explicit approval flow
above only if its effect scope and all native gates actually permit it. Existing
native execution history, another live owner, multiple outputs or unknown effects
require stopping for an appropriately scoped decision, not altering the Work.
After a schema-4 disposition there is no supported downgrade: retain the new
reader and repair through fresh immutable revisions and real QA/completion.
Inspection copies with temporary contract roots are not restartable backups.
