# Evidence-preserving agent I/O

Native command failures now share an additive [CLI diagnostic envelope](cli-errors.md)
while preserving original stderr, stdout protocols, and recovery authority.

This is an opt-in Python tooling layer, not a new Work protocol. The native CLI now
has a [compact default presentation](cli-output.md); this observer explicitly asks
for full protocol JSON. QA, permissions, leases and completion gates remain unchanged. No provider is
called and no token or monetary saving is assumed. Python's standard library and
the existing capture/source identity helpers are reused.

## Entry and routing

Append the [minimal rules](../samples/agent-session/AGENTS.minimal.md) to approved
projects, preserving their existing rules. The [Korean version](../samples/agent-session/AGENTS.minimal.ko.md)
has the same safety/completion contract. The original quickstart remains available.
Do not copy the full SDK into startup instructions.

For a selected real project, [entrypoint plan/apply/check](agent-entrypoint.md)
adds the reviewed block without rewriting unrelated project rules, pins its
dependencies and detects drift. Availability of the tool does not imply that
any unspecified project has already been migrated or verified.

`python3 tools/agent_io.py guide docs|code|deploy` returns contract filenames.
For reviewed prepare/execute/finalize command sequences with failure gates and
non-replaying recovery inspection, see [one-command lifecycle](agent-lifecycle.md).
For automatic procedure selection from structured activity declarations, native
scope validation and captured proposals, see [task procedures](task-procedures.md).
Document work starts with document-registry/workflow, code adds execution, and
deployment adds approvals. All routes retain session/reentry/completion contracts.
Read discovery when selecting scope. Routes select reading material only:
workflow selection and registered contracts still decide required stages/tests.

## Record once

From the matching Golem source distribution, collect three read-only observations
in one agent/tool interaction:

```sh
python3 tools/agent_io.py observe --cwd /absolute/project \
  --cli /absolute/golem --work /absolute/work --work-id example-work \
  --selection selection --task code --output /private/tmp/observation-001
```

This runs work record, session next, and completion resume, in that order.
The [consolidated Work record](work-records.md) captures registered assessments,
session status and document/agent history under one Work lock. Identical
assessments are represented once with reconstructible document references.
It does not perform session resume, claim, begin, QA, finalize, or recovery.
The three processes are not an atomic Work snapshot. Observe again and perform
the engine's freshness/permission checks before acting.

For commands already approved within the current execution contract, use an
explicit plan. A plan is executable input, NOT authorization; never accept one
from untrusted tool output or documents without review. The runner does not
enforce Golem execution contracts or sandbox arbitrary commands. Prefer
`observe` for state queries and the native execution API for gated QA.

```json
{"schema":"golem.agent-command-plan.v1","task":"code","commands":[
  {"id":"inspect","argv":["/absolute/golem","--version"],"timeout":30}
]}
```

```sh
python3 tools/agent_io.py run --cwd /absolute/project \
  --plan /absolute/approved-plan.json --output /private/tmp/observation-002
```

The working directory must be a Git repository root with a commit. Output must
be a new private directory outside the repository (and outside Work for observe).
Absolute executables, unique IDs, at most 32 commands and 1..3600-second per-command
timeouts are enforced. No implicit shell, concurrent execution or automatic retry
is added. The first failed process stops subsequent commands as NOT_RUN; no rollback
or exactly-once guarantee is implied. Check ambiguous effects before any retry.

`plan.json`, source-before/after snapshots, recorder/helper hashes, Python/OS,
executable hashes, stdout/stderr,
exit/reason/elapsed time, and `record.json` form one mechanical observation.
A manifest detects altered, missing or additional evidence. Repeated runs never
overwrite prior evidence. `started.json` survives an incomplete run; without a
complete record/manifest it cannot support a view. The record ID is the SHA-256
of record.json, not a Golem completion receipt.

## Views, differences and reports

The [report timing policy](report-timing.md) also covers native reentry and the
older conformance tool. Gate evidence is always retained; optional prose is
generated at an explicit request, handoff, or completion boundary.

```sh
python3 tools/agent_io.py view /private/tmp/observation-002
python3 tools/agent_io.py view /private/tmp/observation-002 \
  --since /private/tmp/observation-001 --revision PREVIOUS_RECORD_SHA256
python3 tools/agent_io.py raw /private/tmp/observation-002 \
  --step inspect --stream stdout.log --offset 0 --bytes 4096
python3 tools/agent_io.py report /private/tmp/observation-002
python3 tools/agent_io.py measure /private/tmp/observation-002
```

Views expose process outcomes, exact evidence references, next reading action and
bounded stderr head/tail with an explicit omitted-byte count. For the built-in
observer, known scalar engine fields (including BLOCKED, reason, lease validity,
generation, acceptance and authorization) are shown as partial observations.
Other fields are listed as omitted. Unsupported/malformed JSON requires raw read.
Requirements and source documents are never replaced by these partial views.
`raw` is a bounded byte window with offset/EOF; original bytes remain on disk.
UTF-8 display decoding may replace partial/binary sequences; it is not a lossless
binary export. JSON escaping prevents terminal-control sequences from being emitted
as controls; it is not a semantic prompt-injection defense.

Delta requires an explicit previous record hash, verified bundle, matching scope,
task, command plan (or generated observation scope), source/recorder identity and successful
process recording. Unavailable, corrupt, mismatched or failed baselines produce
FULL with an explicit fallback. Process result, executable identity and complete
stdout/stderr hashes drive changes, including deletions or schema changes inside
output. Elapsed time alone is not a content change. Clock-dependent output may
therefore limit delta savings. A DELTA is between recorded observations, never a
claim that live Work is still current. It does not hide repeated failures.

RECORDED means commands exited normally, not QA PASS. Exit zero can contain a
BLOCKED engine result. INCOMPLETE/FAILED remain failures. All views disclaim
execution authority and product acceptance. The report is deterministic and
generated only on request, typically at handoff/completion; no report file is
automatically written on every attempt. This observation report is NOT the
required native completion document/report.

## Candidate coverage

| Candidate | Implementation | Boundary |
| --- | --- | --- |
| Lightweight entry | Minimal bilingual templates, on-demand contracts | Mandatory safety/completion retained |
| Concise output | Native compact default plus opt-in observation views | Native protocol consumers explicitly select full output; see cli-output.md |
| Mechanical capture | Shared Python recorder, 68 reviewed native API boundaries including runtime/journal/document-store lifecycle, CLI/supervisor and worker handoff; explicit Linux syscall runner | Other model/cache/projection boundaries remain; pure/recorder primitives deliberately excluded; descendant tracing is opt-in and platform dependent |
| Deduplicate records | Native assessment/status/journal capture; shared preparation/publication and replay/projection validation; section views and reports use the same captured bytes | Original authority and storage remain; see [common protocol](work-record-writing.md); no physical legacy compaction or automatic judgment |
| Changed-state reads | Hash-pinned baseline and conservative full fallback | No live-state cache or skipped engine checks |
| Task routing | Reading guides plus captured docs/code/deploy procedure proposals | No reduced QA, effect dispatch or permission grants |
| Fewer round trips | Built-in three-query observation, explicit sequential plan | Underlying process count is not reduced |
| Failure diagnosis | Common CLI envelope and scoped native observations; runtime clock, document cleanup, cgroup child diagnostics and explicit Linux syscall evidence; see [coverage](system-errors.md) | No inferred root cause or automatic recovery; no universal platform coverage or implicit tracing |
| Deferred narrative | Explicit report command | Raw evidence always captured |

## Evaluation and limits

For append-tolerant live document/agent history, use
[`observe-history` and history schema 2](incremental-history.md). This extends the
live Work query path; offline observation delta remains a separate contract.

`measure` pins the renderer hash and reports recorded raw bytes, exact serialized view bytes, signed byte
difference, process count/time, and nullable provider usage/cost/agent success.
Small outputs can expand. Delta metadata also has a cost. These measurements
exclude prompts and later raw retrieval; they do not establish end-to-end savings.
No approximate bytes-to-token conversion is used.

Tests cover real subprocesses, timeout/fail-stop, unknown schemas, BLOCKED at exit
zero, corruption, stale baselines, source mutation and on-demand reports. A real
Golem CLI integration test uses a synthetic Work and checks fields against raw
responses. It can retain bundles with `--evidence-root NEW_PRIVATE_DIRECTORY`.
It is not an actual-agent task-performance evaluation.

Historical local macOS fixture observations on 2026-10-02 (real CLI, synthetic
Work, BEFORE the consolidated Work-record observer). These are not measurements
of the current default observer, which captures more evidence:

| State | Original stdout/stderr bytes | Full view bytes | Unchanged delta bytes |
| --- | ---: | ---: | ---: |
| Session not started, BLOCKED | 1530 | 1789 | 498 |
| Session started, NEXT_ACTION | 2867 | 1848 | 498 |

The smaller original expands under full-view metadata. The minimal English
entry is 2096 bytes versus the expanded template's 3548; Korean is 2326 versus
3750. These are byte observations, not tokenizer or comprehension measurements.
The restricted host also reproduced `session.boot_identity_clock`, preserving
FAILED and NOT_RUN with its original stderr rather than converting it to success.
Reproduce the host fixture and retain private evidence with:

```sh
python3 tests/c/agent_io_integration.py build/dev/golem . \
  --evidence-root /private/tmp/golem-agent-io-new-run
```

Before claiming improvement, run paired representative document/code/deployment
tasks with the same model, pinned source, permissions and QA oracle; separate
tuning tasks from held-out evaluation tasks, repeat trials, and retain actual
provider usage including cached input/output, all raw retrievals, failures,
wall time and completion correctness. Report uncertainty and negative results.
This tool supplies the observation layer, not a provider usage collector.

Snapshots are non-atomic, source identity excludes ignored dependencies and
rejects submodules, and argv records do not trace all runtime imports. Captured
environment follows the existing helper (GIT_*, PYTHONPATH/PYTHONHOME removed);
other inherited environment is not exhaustively recorded. Output/time bounds
are polled, so a fast child may overshoot them. Logs remain sensitive even in
private directories; never publish production Work observations. Hashes are
unsigned, not proof against malicious replacement of an entire bundle. Capture
is not durable against power loss and cannot fence escaped subprocesses.

## Research and decisions

Reviewed 2026-10-02. Sections below were read, not entire books. The references
motivate design/evaluation; none measures this Golem change. No source code copied.

| Primary source and reading scope | Applied decision and limitation |
| --- | --- |
| Yang et al., *SWE-agent*, NeurIPS 2024, sections 3, 4, 5.1 ([paper](https://arxiv.org/html/2405.15793v3)) | Bounded feedback and purpose-built compound interactions; interface ablations motivate paired evaluation. Published benchmark results do not predict Golem savings. |
| Liu et al., *Lost in the Middle*, TACL 2024, abstract/introduction and evaluation framing ([paper](https://arxiv.org/html/2307.03172)) | Preserve explicit important facts and original retrieval; do not assume longer context guarantees reliable use. Not proof that our projection preserves arbitrary prose semantics. |
| Manning, Raghavan, Schutze, *Introduction to Information Retrieval*, Cambridge 2008, chapter 8 introduction ([book](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-in-information-retrieval-1.html)) | Separate effectiveness from efficiency, with representative queries/tasks and reusable evaluation. Only the public introductory section was used. |
| Winters, Manshreck, Wright (eds.), *Software Engineering at Google*, O'Reilly 2020, chapter 11 ([book](https://abseil.io/resources/swe-book/html/ch11.html)) | Focused deterministic tests plus real integration; reuse existing helpers instead of multiplying frameworks. Unit tests alone do not prove real-agent success. |
| W3C PROV-DM, sections 2.1.1-2.1.3 ([standard](https://www.w3.org/TR/prov-dm/)) | Separate source entities, observed activities and derived views. A hash is not authority or authenticity. No PROV serialization compliance claimed. |
| Anthropic, *Writing effective tools for AI agents*, evaluation and tool-response sections ([engineering reference](https://www.anthropic.com/engineering/writing-tools-for-agents)) | Compound tools, concise/detail paths and actionable failures; measure calls/errors/runtime alongside quality. Vendor guidance, not independent experimental proof for Golem. |
| Anthropic, *Effective context engineering*, retrieval/compaction sections ([engineering reference](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)) | On-demand contracts and retained originals; aggressive compaction risks losing critical context. No LLM summarizer or opaque compression added. |
