# Current dependency context

Decision before implementation, 2026-10-20; reviewed predecessor:
`ef8078ca5d73b28fb5e1ff3420894830dbf6cc59`. Earlier snapshot results remain
separate in [the follow-up record](lightweight-awe-decision.md).

## Bounded Selection

Add explicit recipe `current-v1`, renderer 2 only. It includes full input bodies
like `original-v1`, but selects model-facing document metadata using existing
native contracts, not prose inference. Existing recipes and CAS bytes stay frozen.
Use current-v1 in the default example; callers explicitly retaining original-v1
continue to get full metadata. No implicit request rewriting or count reuse.

`document/schema.c` closes metadata schemas 1..5; `document/registry.c` verifies
revision/supersedes identity and replays every original body/metadata. In
`workflow/graph.c`, SUPERSEDED means a newer revision of the same document exists;
STALE propagates through explicit parents. Neither is a semantic QA assertion.
`workflow/query.c` selects required current roots and their full parent closure.
This supplies a safe **bounded** exclusion rule, not globally minimal memory.

Keep full metadata for every CURRENT or STALE document and for all non-plan kinds
(including scope/selection, QA, results, completion, research and failure). Also
retain the transitive parents and digest references of retained metadata and the
Work specification/input manifest/next action. Only superseded schema-4 planning,
UX, publishing or development-plan metadata outside that closure may be archived.
The supersedes field is lineage, not an active parent edge: retain that reference
in the archive inventory without treating it as a request for full old metadata.

For each archived revision keep every original metadata field except the obsolete
derived `input_manifest`, plus manifest/metadata/body digests. This includes source,
requirements, parents, lineage, producer and policy/template versions. Name the
single omitted field explicitly; do not summarize prose or drop base constraints.
Schema-1 metadata has no embedded manifest and stays full. Make retrieval explicit
(`golem --output-mode full document inspect
WORK ID REVISION`). No body, CAS, journal, receipt or stored metadata is deleted.
The entire registry graph/replay is still validated before selection. Full metadata
can always be requested with original-v1. Never treat an archive reference as the
original metadata or interpret historical PASS as current acceptance.

Read and validate the complete native session stream. If an attempt is active,
or native `as_unreceipted` identifies an unsubmitted output, use full metadata.
Retain the current session checkpoint and complete acknowledged-output references
in the selection inventory; bind the session sequence/head into projection bytes.
An acknowledgment reference is not an active parent dependency; its identity is
retained even when its superseded plan metadata is archived. A corrupt/missing
required stream blocks rather than silently claiming an idle state.

Any reentry/completion/research, runtime/admission/role/approval history or execution
policy/attempt/receipt directory causes full fallback. Unsupported registry schemas
block before selection; future unhandled metadata versions or reference-walk
complexity fall back. This intentionally does not prune
non-document histories or guess which failures/effects were resolved. Missing,
stale or corrupt required inputs and insufficient budgets still block. Fallback
does not waive budgets. The selection inventory states the exact mode/reason.

## Alternatives and Limits

Reject recent-N slicing and model-scored relevance. Do not trim native replay,
authority checks or current source bodies. Do not claim every historical item is
necessary; conversely a parent DAG alone cannot resolve arbitrary non-document
judgments. Start with the closed plan-metadata case and explicit conservative
fallback rather than a new meaning model, cache, daemon or distributed system.

Digest lookup uses a sorted index and a bounded work queue; traverse each retained
metadata object once. Reference recursion is bounded; complexity overflow retains
full metadata. Archives still grow with history, but do not repeat full manifests.
Selection is deterministic and versioned by recipe; changed session/head/selection
changes native bytes and invalidates old proofs. No new execution authority.

## Sources Actually Inspected

Read 2026-10-20. Andrey Mokhov, Neil Mitchell and Simon Peyton Jones,
*Build Systems a la Carte*, PACMPL 2/ICFP, 2018, DOI
[10.1145/3236774](https://doi.org/10.1145/3236774),
[author-hosted original paper](https://simon.peytonjones.org/assets/pdfs/build-systems-original.pdf),
sections 2.1-2.2: dependency completeness governs selective work and hidden dynamic
dependencies require conservative handling. Application here is an engineering
analogy for model representation selection, not a build-system correctness proof
or semantic completeness theorem for Golem. Selected sections, not the whole paper,
were read. No license or build engine is changed.

The earlier actual readings of Parnas (1972), Saltzer/Schroeder (1975), RFC 8785
(2020), *Pro Git* (2014, chapter 10.2), and *Software Engineering at Google*
(2020, chapter 13) inform module boundaries, fail-closed fallbacks, exact identity,
retained originals and real native fixtures. See their explicit reading/access
limits in the two preceding decision records; no whole-book claim is made.

## Required Negative Checks

Unreferenced superseded plans compact; their originals remain inspectable.
Stale child dependencies retain the superseded parent metadata. Current QA and
non-plan history stay full. Active/recovery/unsubmitted or execution/history state
falls back; corrupt session/Work/CAS blocks without writes. Recipe/session changes
invalidate old counts. Compare full/current on the same fixture and inspect actual
provider request bytes; fake counts are not token/billing measurements. Keep
lease/fencing/sequence/binding/idempotency/recovery/completion regression tests.

## Local Verification

On macOS arm64, the final selected native regression run passed 19/19 CTest
entries (including all 23 context cases); Release and ASan/UBSan each passed
3/3 selected entries. The host Python tool suite passed 483/483 tests.
Native suites are focused suites, not a full-platform claim.
The final dev binary SHA-256 was
`20d3221870af8ba3db4264a1caed36264edff02da75f374a496f3e597fbfd742`.
Against the retained f7613b6 binary, renderer-1 candidate bytes were identical
and reading its existing projection CAS left the fixture unchanged.

On one shared Work/preflight/full-body fixture, production provider-input encoding
was 205128 bytes for original-v1 and 194536 for current-v1, with six archived
metadata manifests. Test source SHA-256 was
`519d342f2bf179faf287d8e0a2c97a1249aa4a4ec61b085018913ffdd1a76409`.
This is encoding-only evidence: no network, model calls, token savings or billing
measurements. A separate native adapter fixture exercised a selected archive
through fenced resume with a fake count; this does not establish provider quality.
The earlier lifecycle fixture measured one wrapper invocation, three internal
native calls and compact/full outputs of 576/775 bytes; those are distinct metrics,
not model-turn measurements or measurements of this archive fixture.

### Permission Failure Boundaries

An earlier parallel run failed execution/completion cases while dev (-j3), ASan
(-j2), Release (-j2) and Python suites overlapped. Its preserved JUnit reported
INCOMPLETE_WORK and cleanup kill-group EPERM observations. Isolated unchanged
reruns passed, but the original child-level evidence was not retained and the
primary cause remains unresolved. No retry, timeout relaxation or permission
bypass was added. Supervisor/execution/completion code is unchanged from f7613b6.

A controlled comparison used the same execution failure-modes and completion
cases on both the retained f7613b6 and current binaries. Execution passed on both
profiles/binaries. Completion failed under the restricted profile on both and
passed on the host on both. The restricted failure was specifically session-start
`session.boot_identity_clock`, `sysctlbyname`, errno 1, before effects. This supports
that clock permission diagnosis only, not an explanation of the original parallel
cleanup observation. Source snapshots, test logs and comparison reports were kept
separately outside the repository; no product/Work evidence was imported.

Windows, Linux local execution, real provider generation and arbitrary semantic
history minimization were not validated locally. Non-document/authority history
deliberately retains full metadata. The feature changes model representation only;
full native replay and original evidence remain authoritative.
