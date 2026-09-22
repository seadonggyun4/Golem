# Project Discovery, Research and Scope

Phase 22 supports the **current agent**. It does not launch another model,
browse the web, execute project tests, or generate development actions. The
agent explores and researches; Golem captures bounded local identities,
validates the submitted relationships, renders Markdown drafts, and registers
immutable artifacts through the existing document registry.

## Workflow

1. Choose explicit, non-sensitive repository paths and a capture time budget.
2. Capture a snapshot. The original files and Git index are not changed.
3. Investigate the candidate, execute authorized reproductions separately, and
   store reviewed/redacted evidence with `golem evidence put WORK LOG`.
4. Author an assessment with questions, reading scope, findings and selections.
5. Validate it and generate/edit discovery, research and scope Markdown.
6. Register each document with schema 2 metadata, the assessment, and exact
   parent links. Later workflow gates consume these records; registration alone
   cannot authorize development.

```sh
# Use the freshly built CLI, not a previously installed version.
build/dev/golem discovery snapshot /private/path/plan.json
build/dev/golem discovery validate samples/discovery/assessment.json
build/dev/golem discovery report samples/discovery/assessment.json discovery
build/dev/golem discovery report samples/discovery/assessment.json research
build/dev/golem discovery report samples/discovery/assessment.json scope
```

Snapshot and validation commands emit JSON. `report` emits Markdown bytes on
stdout. Direct output to a NEW private draft file; the command does not choose
or overwrite files. Reports reproduce the agent's supplied claims and explicit
limitations, not invented investigation. The sample is deliberately synthetic,
OFFLINE and UNCONFIRMED, with no selected work. It must not be represented as a
real project inspection. Snapshot plans contain private absolute paths; never
publish them or raw runtime evidence by accident.

## Snapshot Contract

`samples/discovery/plan.json` is the exact plan shape: schema_version 1,
timeout_seconds 1-60, and 1-8 repositories. Each repository has a unique id,
absolute root, 1-64 explicit relative file paths, toolchain and test_configuration.
Toolchain and test configuration are declared by the agent, not executed probes.

The C implementation invokes only `/usr/bin/git` with fixed arguments through
the existing bounded supervisor. Git commands are rev-parse, ls-files --stage
and ls-tree; optional locks, fsmonitor, replacement objects and hooks are disabled. No shell, filters,
tests, reset, checkout, network or cleanup runs. GIT_* environment overrides are
rejected to avoid silently selecting another index/worktree. `/usr/bin/git` must
be available, the repository must have a HEAD commit, and files must exist.

Each snapshot contains:

- Root identity digest (supplied absolute path plus device/inode), HEAD identity.
- Digest of the selected paths' staged Git records, not the full index file.
- Per-file SHA-256, byte size, tracked flag and conservative raw-byte dirty flag.
- Declared toolchain/test context, without source text or full diff contents.

Dirty means raw worktree blob/mode, index and HEAD differ; Git's content filters
or line-ending normalization are intentionally not executed. Thus this flag may
differ from `git status`. Full tracked diff text is not exported, avoiding raw
source/secret collection. Relevant staged identity plus worktree digests bind
the observed differences. Unselected files, deletions, submodule contents and
ignored directories are not silently claimed as covered. Missing selected files
fail capture; narrow or revise the explicit plan instead of accepting a partial
snapshot. Git reports over 16 KiB per command also fail rather than truncate.

Traversal rejects `..`, absolute file paths, symlinks and common sensitive/cache
components such as .git, .env, .golem, .ssh, secrets, build and node_modules.
This is defense in depth, not a secret detector. Review the allowlist: an ordinary
source filename can still contain secrets. Files are read to hash, not copied to
CAS. Paths and digests can themselves be sensitive.

Limits: 1 MiB per file, 16 MiB total selected bytes, 60 seconds overall. Capture
repeats HEAD, selected index/file observations and root identity checks. These
detect ordinary concurrent edits but do not provide atomic multi-repository
isolation or protection against malicious same-user ABA rewrites. Keep relevant
inputs quiescent. Capture failure returns no success snapshot and writes nothing
to the project. The host/supervisor is not a sandbox.

## Assessment Schema 1

`samples/discovery/assessment.json` demonstrates all required top-level fields.
Unknown/duplicate fields, unsupported versions and invalid UTF-8 fail. JSON is
bounded to 256 KiB, including when embedded in document metadata.

| Field | Contract |
| --- | --- |
| schema_version, scope_revision | Integer 1 |
| work_id | Same ASCII identifier contract as the document registry |
| snapshot | Snapshot object described above |
| questions | 1-64 unique research questions |
| references | 0-64 unique references |
| findings | 1-64 unique candidate findings |
| selections | Exactly one decision per finding, no missing/duplicate candidates |
| permission | ALLOW, ASK or DENY; proposal assessment, not a permission grant |
| non_goals | Explicit non-scope explanation |

Question fields: id, question, requirement_id, source_budget (1-64),
seconds_budget (1-86400), elapsed_seconds (0-86400), status, conclusion,
search_strategy, eligibility, omissions. All explanatory fields are required.
Status is ANSWERED, BUDGET_EXHAUSTED, OFFLINE or OPEN. ANSWERED requires at least
one adopted, actually claimed-as-read reference and elapsed time within budget.
BUDGET_EXHAUSTED requires a source or time limit to have been reached. Exceeding
the source count rejects the record; reaching it is valid and may remain
unresolved. Unresolved questions remain visible, never implicitly answered.
Recorded elapsed time is a host claim; this validator cannot time or stop the
current agent's external browsing. The host must stop acquisition at its limit.

Reference fields: id, question_id, url, title, authors, version, published,
accessed, read_scope, locator, claim, applicability, limitations, counterevidence,
decision, source_type, decision_reason. URL is HTTPS (DOIs use https://doi.org/...).
Credentials/control characters are rejected; URLs are never fetched by Golem.
Store concise summaries and permitted excerpts, not unlicensed full-text copies.
Dates are YYYY-MM-DD; published can be `unknown`. Source type is STANDARD,
OFFICIAL_DOC, PAPER, BOOK or OTHER. Reading scope is UNREAD, ABSTRACT, EXCERPT
or FULL_TEXT. Decisions are ADOPT, REJECT or DEFER. UNREAD cannot be adopted;
ABSTRACT/EXCERPT never contribute to the full_text_references count. Same
question/URL/version cannot be counted repeatedly under different IDs.
Prefer primary sources and explicitly assess contrary evidence. This is a
bounded research record, not a claim of exhaustive systematic review.

Finding fields: id, status, observation, hypothesis, uncertainty, repository_id,
path, requirement_id, reproduction, reference_ids, rationale. Status is
CONFIRMED, UNCONFIRMED or NOT_APPLICABLE. The repository/path must occur in the
snapshot. Reference IDs must exist and address the finding's requirement via
their question. Semantic relevance is still a reviewer responsibility.

Reproduction fields: command, expected, actual, result, evidence_digest. Command
is inert text, never executed by validation, rendering or registration. Result is
REPRODUCED, ENVIRONMENT_FAILURE or NOT_RUN. Only REPRODUCED carries a SHA-256
evidence digest; the other states use an empty string. CONFIRMED requires
REPRODUCED. A paper alone or an environment failure cannot confirm a local
defect. At registration and replay, every reproduction digest must resolve to a
nonempty, intact object in the Work CAS. This verifies bytes, not the truth of
the claimed execution; signed/session-bound observations are a later contract.

Selection fields: finding_id, decision (INCLUDE/DEFER/EXCLUDE), reason, size
(SMALL/MEDIUM/LARGE), acceptance, needs_ux, needs_publishing. INCLUDE requires
CONFIRMED; every candidate needs a recorded decision and reason. Acceptance
text supplements, never replaces, the Work's requirement criterion. Non-goals
are not converted to tasks. No development action is generated by Phase 22.

`scope_ready` is true only for an ALLOW proposal with selected confirmed findings
and all questions ANSWERED. `execution_authorized` and `acceptance_verified`
remain false regardless. Work policy, later stage gates and the user's actual
authorization remain authoritative.

## Markdown and Immutable Registration

Metadata schema 1 remains compatible. Schema **2** is the Phase 22 extension:
all existing metadata fields plus an `assessment` object containing the entire
validated assessment. Kinds discovery/research/scope use stage planning. Their
extra H2 sections are Observations/Sources/Selection respectively, in addition
to the nine common template sections. Other kinds continue to use schema 1.
Legacy schema-1 research remains a document, not a Phase 22 assessment.

Set source_snapshot to the digest emitted by `discovery validate`. It hashes
the snapshot object's JSON-C compact serialization, preserving input member
order; this is not an order-insensitive canonical JSON standard. Obtain it from
the CLI/API instead of guessing a serializer. The embedded work_id must match
metadata, and metadata requirement_ids must cover every question/finding ID;
the registry then checks those requirements against the immutable Work.

The agent attaches the assessment object and fills metadata as in Phase 21:

```sh
build/dev/golem document validate /private/path/meta.json /private/path/discovery.md
build/dev/golem document submit /private/path/work /private/path/meta.json /private/path/discovery.md discovery-first
build/dev/golem document inspect /private/path/work discovery 1
```

The assessment is retained in the metadata CAS and bound by the same immutable
manifest as the Markdown body. Inspect returns it. Replay revalidates structure
and reproduction CAS objects. Existing generation, parent, idempotency,
supersedes and projection-repair rules are unchanged. A missing CAS log cannot
be bypassed by using `document submit` instead of a discovery command.

`report` creates a draft with no parents; add exact `golem-doc:` parent links and
matching metadata before registering a downstream handoff. The renderer escapes
source prose so headings/HTML/link syntax in a reference cannot inject report
structure. It is not an agent prompt-injection detector: the agent must still
treat all source claims and commands as untrusted data. JSON metadata remains
the authoritative structured selection; contradictory manually authored prose
requires reviewer rejection, not automatic semantic inference.

Scope revision stays 1 to match Phase 21. Subsequent assessment/document revisions
can refine observations and selection within the same Work requirements. They
do not amend original Work scope or expand permissions. A material expansion
requires a new Work pending the later scope-change/invalidation coordinator.

## Public API and Tests

`include/golem/discovery.h` exposes validate, snapshot and report. Validate is
pure; snapshot returns allocator-owned JSON; report uses caller-owned buffers
with size queries and unchanged short buffers. No global mutable state or new
runtime dependency was introduced. The existing JSON parser, MD4C, CAS,
document transaction and process supervisor are reused.

Tests cover dirty multi-repository preservation, filter/fsmonitor non-execution,
path/secret/symlink/size denial, malformed metadata, research limits, reading
scope, evidence-only confirmation, permission readiness, report escaping,
registration, CAS corruption/replay and C ownership. Discovery schemas also run
through the document mutation/fuzz harness; it never runs snapshot subprocesses.
