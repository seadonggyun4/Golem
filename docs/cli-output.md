# Native CLI output contract

The C CLI now defaults to `compact`, on terminals **and pipes**. This is a
presentation change, not a Work/API schema change. Existing integrations that
parse native response fields must select `full` explicitly. Engine permissions,
leases, revisions, receipts, QA and completion predicates are unchanged. The
Python prototype CLI and separately pinned installations are not upgraded by
changing this source checkout.

## Commands and compatibility

```sh
# Default presentation; may return a compact observation.
golem session call WORK REQUEST.json

# Original protocol payload for scripts and integrations.
golem --output-mode full session call WORK REQUEST.json

# Optional dedicated private output store. Its parent must already exist.
golem --output-store /absolute/private-output session call WORK REQUEST.json

# Retrieve the saved payload by its hash, never by repeating the operation.
golem --output-store /absolute/private-output output read SHA256
```

Global controls precede the command. They deliberately do not reuse `--format`
or `--output`, which existing subcommands use for artifact formats/destinations.
Duplicate/missing/invalid controls fail with exit 2 before command dispatch.
`GOLEM_CLI_OUTPUT=full|compact` and `GOLEM_CLI_OUTPUT_STORE=/absolute/path` support
process-scoped configuration; explicit flags take precedence. The default store
is `$HOME/.golem-cli-output`. Missing/unusable HOME triggers lossless fallback,
not a write into the current directory. No TTY heuristic changes the contract.

For scripts, pin the matching executable revision and pass `--output-mode full`.
Do not discover compatibility by retrying a mutating command. Old binaries do not
support these global flags. Current observer/benchmark consumers and shared
protocol-test helpers have been migrated; externally installed consumers must be
reviewed before adopting this binary. C API/FFI replies remain unchanged.

## What is compacted

The shared JSON emitter and operational reply writers handle document/Work,
workflow, context render, session/binding/history, execution calls/bundle inspect,
approval, role calls, candidate status/diff/host calls, research calls/status/metrics,
completion/reentry calls, runtime profiles, journal inspection and legacy operational
JSON. Small outputs at or below 2048 payload bytes remain byte-identical.

A larger valid JSON object is eligible only when its compact representation is
smaller and at most 2048 bytes (plus the existing newline framing). The projection:

- identifies itself as `golem.cli-output.v1`, `view: compact`, `partial: true`;
- preserves short top-level fields and small structured fields as `fields`;
- always retains top-level status/state/action/reason/next, permissions,
  authorization, lease, approval, acceptance, requirements and diagnostics;
- lists omitted top-level keys without truncating their underlying data;
- includes the exact original payload SHA-256, byte size and private store;
- supplies a read-only `next_read_argv`, never a mutation/retry instruction;
- declares `read_before_action: true` and `execution_authority: false`.

Fields are observations from the original result, not newly inferred QA or
completion verdicts. Generation/sequence/commit and existing evidence IDs remain
visible when present; no comparison against previous invocations is invented.
Do not use a partial view as verified context, an approval, a QA receipt or an
independent claim of completion. Read the original before acting on omitted data.

Nested negative outcomes (including BLOCKED/FAIL/ERROR/STALE/SKIPPED), nonempty
diagnostics/reasons/requirements, denied authorization and invalid leases bypass
compaction conservatively. Protected data exceeding the budget also forces full
output. This fallback is not a universal semantic classifier of arbitrary future
fields or free text. Unknown fields remain recoverable in the original, and an
unrecognized response shape must not be treated as authorization.

Non-object/invalid/oversized JSON, explicit Markdown reports/renderings, role and
workflow template source, proof packs, research observability exports, context
read, JSONL/event streams, adapter binary/wire output, evidence hashes, version
strings and lineage trace output are not truncated or wrapped. Requested `report`
commands keep their output. Standard error and nonzero runtime error paths are
not suppressed. Consequently compact mode is **not a universal hard output cap**.

## Original payload integrity

Successful compaction first stores exact pre-presentation JSON bytes through the
existing evidence CAS implementation: hash verification, no-replace publication,
private files and fsync behavior are reused. CAS de-duplicates identical payloads;
it does not merge observations, infer provenance or establish freshness.

The store root must be owned by the current effective user with no group/other
permissions. A missing final directory is created with mode 0700; its parent is
not created recursively. Symlink components and traversal are refused, not fixed.
CAS objects are published as 0400. Existing permissions are never widened or
silently repaired. Concurrent same-payload publication is tested.

`output read` opens the selected store read-only, verifies the entire payload hash
before emitting anything and does not open/mutate the originating Work. It uses
the existing 2 MiB CLI JSON read bound. The digest covers the payload, not the
final CLI newline framing. Retrieval adds the normal newline; it does not claim
to capture stderr or the whole process transcript. Use the observation runner
when command/exit/stderr/source provenance is required.

Storage, integrity or formatting failure during compaction emits a structured
`golem.cli-output-error.v1` stderr diagnostic with status_code, `fallback: full`
and `retry_effect: false`, then prints the original payload. It does not convert
an already successful mutation into a retry request or falsify its status. Actual
stdout write failures still fail. A stored response may outlive a failed terminal
write; there is no automatic replay or exactly-once claim.

The output store is private diagnostic data, not the authoritative Work CAS.
Responses can contain sensitive content: never add this store to Git, packages,
CI artifacts or public exports. Hashes and private modes are not encryption,
redaction or authenticity. There is no automatic pruning that silently breaks
evidence references and no total disk quota; follow a reviewed retention policy.
Once a record is removed, its reference is unavailable. Preserve needed original
responses before deliberate cleanup; never rerun effects to reconstruct them.

## Verification and measurement

`cli_output_default` exercises the production formatter and native CLI with clean
output-mode environment variables. It covers TTY and pipe defaults, full parity,
negative/approval preservation, protected-field overflow, malformed data, option
validation, private path boundaries, fallback, corruption, concurrent publication,
raw retrieval and a real document commit whose request files are then removed.
Readback must preserve Work events and match the full inspection response.
The same test runs in the restricted-diagnostic profile and sanitizer builds.
Existing protocol suites explicitly request full fields; they do not replace the
separate default-mode regression suite.

Retain a synthetic native-CLI measurement in a new private directory:

```sh
python3 tests/c/output_integration.py build/dev/golem \
  build/dev/tests/c/golem_output_helper . \
  --evidence-root /private/tmp/new-cli-output-evidence
```

The receipt records full/compact byte counts, payload and executable/test hashes,
readback equality and unchanged Work events. It deliberately leaves provider
tokens and end-to-end savings unmeasured. Raw reads add context and disk/CPU cost;
small/negative outputs may see no reduction. Paired real-agent evaluation must
include subsequent retrievals, task correctness, failure recovery, latency and
actual token usage. Do not extrapolate fixture byte reduction to total cost.

On 2026-10-02 the synthetic document submission produced 2410 full bytes and
1095 compact bytes (54.56% smaller, including newline framing). Hash-checked
readback was identical and Work events were unchanged by retrieval. The tested
native executable SHA-256 was
`80ba5319abcc33a35c67b3f99ce1440a9ae65f148416eed27a8a7d6b0adf78d9`;
the test source SHA-256 was
`7e9ecee2fa39140e05f27e326a38e2c8eeda02f0fc2a21a207ceff82c242640c`.
These identify one local fixture observation, not a portable binary, benchmark
guarantee or measured token/cost saving.

## Primary-source reading record

Reviewed 2026-10-02; the scopes below were read, not entire books. No source code
was copied. Research motivates the design; it does not validate this change.

| Reference and reading scope | Decision and limitation |
| --- | --- |
| Yang et al., *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*, NeurIPS 2024, sections 2-3, feedback/viewer/history interfaces ([paper v3](https://arxiv.org/html/2405.15793v3)) | Provide concise observations with clear state and retrieval. Interface evidence is task/model dependent; published agent performance does not measure Golem's benefit. |
| Lindenbauer et al., *The Complexity Trap*, 2025, introduction, section 3.1 and appendix C ([paper v1](https://arxiv.org/html/2508.21433v1)) | Deterministic observation reduction merits evaluation alongside summarization, but some model configurations lose task accuracy. The paper masks older observations; projecting a current CLI response is a different intervention and not a replication. |
| Liu et al., *Lost in the Middle*, TACL 2024, abstract ([primary publication](https://aclanthology.org/2024.tacl-1.9/)) | Long-context retrieval depends on information position. This motivates focused observations, not a claim that arbitrary field omission preserves correctness or safety. |
| *Command Line Interface Guidelines*, Basics and Output sections ([primary guide](https://clig.dev/#output)) | Brief success feedback, structured machine output, separate stderr and explicit formats. We intentionally use compact on pipes too because agents commonly use pipes; this requires an explicit full-mode migration. |
| Winters, Manshreck, Wright (eds.), *Software Engineering at Google*, O'Reilly 2020, chapter 1, Hyrum's Law/churn/CI discussion ([book](https://abseil.io/resources/swe-book/html/ch01.html)) | Observable output is a compatibility surface. Migrate owned consumers centrally and retain regression coverage instead of assuming nobody parses incidental details. |
| Manning, Raghavan, Schutze, *Introduction to Information Retrieval*, Cambridge 2008, chapter 8 introductory evaluation discussion ([academic textbook](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-in-information-retrieval-1.html)) | Measure utility/correctness separately from output size and retrieval speed. Only the public introductory section was used; this is not a replication of IR ranking experiments. |

The implementation deliberately uses deterministic JSON projections and the
existing CAS rather than an LLM summarizer, another runtime, or stdout scraping.
Future semantic summaries require schema-specific tests and explicit evidence
that safety/completion information cannot be lost; simply lowering a byte budget
is not sufficient.
