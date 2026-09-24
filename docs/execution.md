# Document-driven development and observed QA

Golem keeps the current agent in control of editing. It does not launch another
agent, execute Markdown code blocks, or interpret reference documents as grants.
The C API is `include/golem/execution.h`; CLI commands use `golem execution`.
This is a bounded local execution contract, not a general acceptance oracle.
Opt-in contract v2 adds [verification bundles and log retention](verification-bundles.md)
without rewriting historical v1 receipts or Markdown.
Contract v3 adds [explicit shell approval and the execution boundary](execution-boundary.md).
Optional isolated candidates use the [workspace C host API](workspaces.md);
workspace ownership does not replace execution approval or QA acceptance.

## Workflow

1. Register current planning, applicable UX/publishing, and development-plan
   Markdown through the document registry. The plan should identify edit locations,
   compatibility, requirement-linked tests, risks and non-goals. Structural validity
   does not prove the plan's semantic quality.
2. Review a structured execution contract, including every argv, repository root,
   protected test/configuration path and expected case. `execution validate`
   returns its approval digest. Supply that digest from the trusted host, not from
   an unreviewed tool response. Validation executes nothing; prepare only runs
   bounded read-only Git probes, never QA gates.
3. `prepare` pins the document closure, contract, executable digests and allowlisted
   Git baseline before edits. It enrolls that selection revision in observed-result
   mode. Subsequent development-result/qa-result submissions cannot downgrade to
   schema 4. Contract changes require a new selection revision and reviewed digest;
   there is no silent relaxation of criteria on retry.
4. The current agent edits source. `finish` observes the post-edit snapshot and
   issues a development receipt. Generate and register its schema-5 Markdown.
5. Author/register qa-plan against that development result. `run` executes the
   pinned gates and returns an immutable QA receipt, including failures.
6. Generate/register schema-5 qa-result. FAIL/ERROR prevents completion input
   construction. Classify the failure, revise affected documents, edit, finish,
   revise qa-plan and run with a new attempt ID. No automatic failure classification
   or reentry selection is introduced by the execution API itself. The optional
   [reentry controller](reentry.md) records classified hypotheses and enforces
   affected revisions, bounded attempts and preserved gate contracts.
7. `verify` re-observes source and checks the document closure. Old PASS is not
   valid for changed bytes. Completion remains a separate semantic decision.

When a Phase-24 session exists, prepare/finish/run additionally require its current
`token` and a RUNNING claim for the corresponding result kind. Claim/begin
development-result before prepare; claim/begin qa-result before run. Manifests
must match the active claim. During commands the supervisor checks the same boot
identity/monotonic lease, stops on expiration, and does not renew it implicitly.
Choose a sufficient bounded TTL before starting. The Work writer lock is held
through execution, so another process cannot heartbeat it concurrently.
Standalone execution without a session requires the same explicit contract
approval but has no session lease. It is not a session-authorized stage receipt.

## CLI and schemas

```sh
golem execution validate contract.json
golem execution call "$WORK" prepare.json --approve-contract "$REVIEWED_DIGEST"
golem execution call "$WORK" finish.json
golem execution render "$WORK" development-result.json
golem execution call "$WORK" run.json --approve-contract "$REVIEWED_DIGEST"
golem execution render "$WORK" qa-result.json
golem execution call "$WORK" verify.json
```

Render prints Markdown. Register those exact bytes with the existing
`golem document submit WORK METADATA BODY KEY` command. The registered projection
is `WORK/documents/DOCUMENT_ID/rNNNN.md`; JSON/CAS receipts live in the same Work.
All runtime data must remain outside source control. No installation is replaced.

The example `samples/execution/contract.json` contains deliberately non-runnable
paths and document digest. Replace them with reviewed project values.
All JSON rejects unknown/duplicate fields, invalid UTF-8, NUL and excessive depth.
Contract validation performs no filesystem or subprocess operations.

| Request | Required fields beyond `schema_version: 1`, `operation` |
| --- | --- |
| `prepare` | `contract` object |
| `finish` | `checkpoint` receipt SHA256 |
| `run` | `checkpoint`, `attempt_id` |
| `verify` | `receipt` SHA256 (development or QA) |

`token` is allowed on mutations and required if a session exists. Its fields are
the unchanged session `{epoch, attempt_id, session_id}`. Approval is a C parameter
or CLI flag, never a field in these JSON requests. `DENY` cannot be overridden;
`ASK_ALWAYS` remains blocked pending a separate approval protocol. AUTO_LOCAL and
ASK_ON_EXTERNAL_EFFECT still require contract approval because tests are code.

Contract v1 fixes one or more gates. Each has `id`, positive `version`, a snapshot
`repository` ID, absolute executable as `argv[0]`, `timeout_ms`, ordered `cases`
and `protected_paths`. Cases bind `id` to `requirement_id`; all selected requirements
must have a case. Protect all test scripts, fixtures, wrappers and configuration
which could weaken the oracle. Golem cannot infer every transitive dependency.
Changed protected bytes or executable digests stop dispatch. Paths are an explicit
allowlist, not shell patterns. Approval hashes json-c compact serialization with
original member order, not raw input whitespace or RFC 8785 canonical JSON.

The gate's stdout must be **only** this versioned result, with exactly the pinned
case IDs in order. stderr is not parsed as a test result:

```json
{"schema_version":1,"cases":[{"id":"reproduction","status":"PASS"}]}
```

Contract v1 admits PASS/FAIL; v2 also admits ERROR, which makes the gate ERROR.
Empty/missing/duplicate, extra, skipped or reordered cases are ERROR, even with
exit 0. No shell is inserted
and PATH is not used for the executable. A reviewed adapter/wrapper may translate
CTest/JUnit/TAP to this contract; those parsers are not built into this version.
Golem cannot prove that a malicious test wrapper actually tested its assertion.

## Receipts and Markdown

Schema 5 extends managed schema 4 with one SHA256 `execution_receipt`, only for
development-result/qa-result. The receipt binds the exact `input_manifest`; the
document generation, upstream references, requirements and producer attempt retain
their existing checks. `source_snapshot` in metadata is the **planning baseline**
identity. The independent observed after-snapshot is in the execution receipt;
they are deliberately not conflated.

`execution render` generates all required sections, parent links, baseline dirty
flags, before/after file digests, expected/observed case tables and evidence IDs.
Registration AND journal replay require byte-for-byte equality with that generated
projection. Rewriting FAIL as PASS or attaching another manifest is rejected.
Agent commentary/deviation analysis belongs in separately referenced authored
documents, not an editable replacement for structured observations.

QA receipts bind the checkpoint, manifest, observed source, attempt, gate versions,
monotonic start/end, exit code, signal, timeout, case outcomes, normalized observation
CAS receipts and raw output digests/sizes. argv/cwd/tool configuration is retained
in the pinned contract. Executable bytes are hashed; declared toolchain descriptions
are not independently verified version probes. Every API reply keeps
`acceptance_verified: false`: passing these cases is not whole-product acceptance.

The command environment is exactly `PATH=/usr/bin:/bin`, `LANG=C`, `LC_ALL=C`.
No parent secrets or raw environment are copied. The default log policy persists
only normalized case IDs/statuses and fixed diagnostics. Raw stdout/stderr are
discarded; their hashes refer to observed bytes, not retrievable CAS objects.
On overflow these are bounded prefixes, explicitly not complete logs. Configuration
paths and argv are retained: never put credentials or private data in them.

## Failure and recovery

Results distinguish PASS, FAIL and ERROR. Nonzero exit is FAIL unless a higher
priority execution error or v2 case ERROR is observed; signal, timeout,
lease expiry, output overflow, parser problems and snapshot changes cannot pass.
Missing cases display UNKNOWN in Markdown; no skipped test is promoted to PASS.
`verify` means freshness/integrity only and can succeed for a fresh FAIL receipt.
Always inspect the structured status separately.

Before dispatch an immutable `execution-attempts/ID.started` binds the checkpoint
and manifest. `ID.done` points to the completed CAS result. Repeating the same
request returns historical evidence without dispatch. Different inputs under the
same ID conflict. A started marker with no done result returns incomplete work;
there is no automatic retry. Preserve it, inspect surviving processes/effects and
explicitly reconcile outside this API. A fresh attempt ID is a deliberate new run,
not evidence that the old effects stopped. Whole-directory deletion is not defended.

`execution-receipts/` identifies locally issued receipts; a random CAS upload
cannot masquerade as an issued receipt. `execution-policies/` prevents contract
replacement for a selection revision. These are durable no-overwrite sidecars
which pin the entire first checkpoint, including its baseline: repeating prepare
cannot bless changed tests under an unchanged contract. They use
the existing atomic publish/fsync implementation, not signatures or a new
distributed journal. A cooperative local owner can still edit its own storage.

## Bounds and limitations

- JSON: 256 KiB; max 8 repositories, 64 declared files each, 8 gates,
  32 argv strings, 64 cases per gate, 256 execution attempts per Work;
  each command 1 ms to 60 seconds. Retained attempt markers count toward the limit.
- Snapshot limits and duplicate observations reuse the discovery implementation.
  HEAD, selected index identity, bytes and declared configuration are observed.
  Baseline dirty/untracked files remain identifiable; the report does not attribute
  preexisting user edits to the agent. It is a byte-digest delta, not a unified patch.
- Only existing regular, nonsymlink allowlisted files are captured. Missing/deleted
  files fail closed; paths added outside the list are not silently included.
  This is not a complete repository inventory or an atomic filesystem snapshot.
- Source checks detect changed observations, not adversarial change-and-restore
  races. Use immutable isolated worktrees/containers for stronger reproducibility.
- A process group timeout is not sandboxing: tests can access the host/network,
  spawn escaped children or modify files outside the allowlist. Trusted hosts must
  also mark their unrelated descriptors close-on-exec. SIGKILL of the host cannot
  guarantee cleanup. Approval must account for these effects.
- Older schema-4 records remain structurally readable but are not observed QA.
  Enrollment prevents new result downgrades, not historical data migration.
  Independent reviewer semantics, source patch attribution, automatic causal reentry,
  universal gate parsers and final semantic acceptance are not claimed.

## Policy-scoped inventory (v4/v5)

Opt in to execution contract v4 for HEAD/index/worktree change inventories,
protected patterns, per-repository changed-path limits and live completion
freshness checks. [Change inventory](change-inventory.md) documents the schema,
findings receipts, exclusions and conservative resource limits. The declared-file
scope limitations above continue to apply to contracts v1-v3.

For larger inventories use execution contract v5 with snapshot plan v3. This
keeps full inventories in bounded CAS objects and records typed digest/size
references in checkpoints, development and QA receipts. Actual QA, Markdown
rendering and live completion checks verify the referenced evidence. See the
[v5 contract and limits](change-inventory.md#large-inventory-qa-execution-v5).
Existing v4 records are not rewritten or silently upgraded.

## Research basis

The implementation choices below are engineering inferences, not claims that
these sources prove Golem correct or improve its benchmark scores.

| Primary source and inspected scope | Applied decision / limitation |
| --- | --- |
| [Agentless v2, sections 3.2-3.3](https://arxiv.org/html/2407.01489v2) | Separate repair from reproduction/regression validation; the integration fixture really fails before repair and passes afterward. No benchmark performance transfer is assumed. |
| [MetaGPT v7, sections 3.2-3.3](https://arxiv.org/html/2308.00352v7) | Explicit predecessor artifacts plus executable feedback. Its multi-agent architecture is not imported; the current agent continues working. |
| [Adzic, Specification by Example, public chapter 1](https://manning-content.s3.amazonaws.com/download/0/e31349c-e7f9-457d-834d-3a29e71e9136/adzic_ch01.pdf) | Keep requirement examples connected to executable outcomes and living documentation. The full book was not accessed; its case studies are not controlled evidence for this engine. |
| [W3C PROV-DM, sections 2 and 5.1-5.2](https://www.w3.org/TR/prov-dm/) | Separate input entities, execution activities and derived reports. A digest establishes byte identity, not truth or author independence. |
| [CTest manual, no-tests behavior](https://cmake.org/cmake/help/latest/manual/ctest.1.html) | Exit success alone is insufficient; require the explicit nonempty case inventory. A CTest adapter must also prevent zero-test success. |
| [Bazel hermeticity](https://bazel.build/basics/hermeticity) | Explicit inputs/environment matter. This local runner is intentionally not described as hermetic. |

Tests live in `tests/c/execution_integration.py` and `test_execution.c`;
the pure contract parser also participates in document fuzz/mutation tests.
