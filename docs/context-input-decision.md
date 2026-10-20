# Phase 1: single-copy context facts

Decision recorded before implementation, 2026-10-20. Baseline:
`f7613b6d35adc6241d66049ca3c725f95d8f0056`; initial working tree clean.

## Decision and scope

Use the existing projection builder with an explicit renderer version 2. Retain
the complete `mandatory_facts` JSON exactly once, alongside all existing source
inventory, quoted source excerpts, request, Work head, warnings and untrusted
note. Version 2 omits only the builder-generated second rendering of those facts
inside `markdown`; it does not summarize or filter facts. The complete JSON, not
its Markdown field alone, is the model input. Native token callbacks continue to
receive the complete returned JSON. No new engine, service or provider gateway.

Request schema stays 1; renderer 1/output schema 1 remain byte-compatible.
Renderer 2/output schema 2 explicitly identifies the changed Markdown contract.
Provider configuration v2 selects renderer 2; v1 selects the unchanged renderer 1.
Old engines reject renderer 2 rather than silently falling back. No old CAS,
journal, receipt, document revision or history is rewritten. New optional CAS
objects have their own digests using the existing serializer and storage path.

Alternatives rejected: adapter string surgery on Markdown (couples transport to
rendering syntax); Markdown-only handoff (loses structured inventory/request
fields); changing v1 in place (invalidates old object identities); proxy-counting
a different view while native checks full v1 JSON (changes the tokenizer contract);
semantic compression (outside scope and no exact fact-preservation guarantee).

`projection_digest` identifies exact native projection bytes. `input_sha256`
identifies the exact serialized provider envelope, including model/instructions.
They are not interchangeable. Versioned count identity binds representation,
provider, model and instructions; the projection digest additionally binds current
Work/request/source state. Validate count observation against the exact envelope
before issuing the ordinary native proof. Rebuild and compare the native handoff,
then verify that it reconstructs the same envelope. No old count reuse after a
representation/instruction change; no inferred billing or automatic generation.
The existing trusted-host proof is not an authenticated provider attestation.

Risks: v2 Markdown alone is incomplete; old consumers must opt in explicitly.
JSON member ordering/escaping are hash inputs. Keep json-c serialization for native
objects, Python's existing encoding for provider envelopes; do not claim RFC 8785
conformance or silently replace either serializer. Native byte/token limits,
freshness, fencing, policy, expected sequence, duplicate receipt handling, RUNNING
reconciliation and completion authority remain unchanged. Smaller bytes do not
prove fewer tokens, lower billing or equivalent model decisions.

## Evidence-to-design record

All access below is 2026-10-20. Claims are paraphrases; **application** is an
engineering inference, not a reported experiment on Golem.

| Source / inspected section | Source claim / application / limit |
| --- | --- |
| David L. Parnas, *On the Criteria To Be Used in Decomposing Systems into Modules*, CACM 15(12), 1972, DOI [10.1145/361598.361623](https://doi.org/10.1145/361598.361623). Original paper text in [university HTML transcription](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html), “The Criteria” and “Improvement in Circular Shift Module”. | Hiding changeable design decisions motivates modular interfaces. Application: keep native rendering decisions in its existing builder, provider envelope rules in the adapter. Transcription inspected, not publisher PDF; not empirical evidence about this patch. |
| Anders Rundgren, Bret Jordan, Samuel Erdtman, [RFC 8785, JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html), 2020, DOI 10.17487/RFC8785, sections 3.1–3.2.4 and 5. | Repeatable hashing requires invariant bytes; JCS specifies string, number and UTF-16 ordering constraints. Application: explicit representation version and exact-byte hashes; no replacement of existing serialization. Existing json-c/Python formats are not asserted to implement JCS. |
| Scott Chacon and Ben Straub, *Pro Git*, 2nd ed., Apress, 2014, [10.2 Git Objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects), “Git Objects”, “Commit Objects”, “Object Storage”. | Content identifies objects; commit metadata and object bytes affect identities. Application: preserve old objects and identify new projections separately. Accessible online chapter inspected, not the entire book; Golem uses its own SHA-256 CAS, not Git's illustrated object format. |
| Roy Fielding, Mark Nottingham, Julian Reschke (eds.), [RFC 9111, HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html), 2022, DOI 10.17487/RFC9111, sections 4.1 and 4.3.1. | Reuse depends on matching nominated request fields and validation metadata. Application: count identity must vary with representation/model/instructions and exact projection. Analogy only: this patch adds no HTTP cache or new count cache. |
| Luc Moreau and Paolo Missier (eds.), [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/), W3C Recommendation, 2013, sections 2.1.1–2.1.2. | Distinguishes entities, usage/generation and derivation. Application: projection object and provider envelope retain separate identities and an explicit derivation. Not a PROV-conformance or truth/authentication claim. |
| Malcolm Featonby, [Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/), Amazon Builders' Library, publication year not established from retrieved page, “Late arriving requests” and “Same client request ID, different intent”. | Changed intent under an old request identity must not be treated as a harmless duplicate. Application: keep native exact-key/request behavior, never retry resume automatically after ambiguity. AWS service semantics do not prove exactly-once external effects here. |
| OpenAI, [Build a per-run spending controller with the Responses API](https://developers.openai.com/cookbook/articles/per_run_spending_controller_responses_api#check-the-budget-before-each-request), live official documentation, “Check the budget before each request”; publication year not established. | Token counting must use the same model/input and supported instructions/context fields as the intended request. Application: bind and check the exact prepared envelope; this patch sends no generation. Reference endpoint page retrieval failed (404 / oversized page); the named cookbook section was fetched and read. |
| Huiqiang Jiang, Qianhui Wu, Chin-Yew Lin, Yuqing Yang, Lili Qiu, *LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models*, EMNLP 2023, DOI [10.18653/v1/2023.emnlp-main.825](https://aclanthology.org/2023.emnlp-main.825/); [author preprint HTML](https://arxiv.org/html/2310.05736v2), sections 4, 5.1, 5.3–5.5, Limitations, Appendix A. | Learned token selection/alignment was evaluated on GSM8K, BBH, ShareGPT and Arxiv-March23 with model/task-specific metrics; high compression and tokenizer mismatch have limits. Application: do not import semantic compression or its savings claims into deterministic duplicate removal. Selected original sections inspected, not every appendix figure or replicated experiment. |
| Titus Winters, Tom Manshreck, Hyrum Wright (eds.), *Software Engineering at Google*, O'Reilly, 2020, [chapter 13, Test Doubles](https://abseil.io/resources/swe-book/html/ch13.html), “How to Decide When to Use a Real Implementation” and mock-contract discussion. | Real deterministic implementations catch contract mismatches that mocks can hide. Application: native CLI/C API integration plus fake HTTP count responses, not mock-only acceptance. Accessible chapter sections inspected, not the entire textbook; no real provider measurement is claimed. |

## Planned local checks

Compare v1/v2 on the same native fixture: identical mandatory facts and decisions,
source inventory, omission accounting and originals; no repeated generated facts
in v2 Markdown; compare exact provider payload bytes and call routes. Preserve
v1 read/publish/retry behavior, reject old/tampered counts and changed instructions,
payload mutation and stale inputs. Exercise lease/binding/sequence/recovery and
completion regression suites without changing their implementations. No paid
experiments, installed-project edits, push/merge/release or follow-up refactors.

## Local verification results

This section records the phase-1 snapshot before the complete-input follow-up.
Its payload sizes and config-v2 observations must not be presented as measurements
of the later preflight-bearing handoff. See [follow-up decision](lightweight-awe-decision.md).

Verified on macOS / Apple Silicon against the baseline above, with uncommitted
phase-1 changes. Linux, Windows, remote CI, real provider token counting, model
generation and billing were not tested. No native DONE or product acceptance is
claimed; adapter success means `RESUMED_INPUT_READY` only.

| Check | Result |
| --- | --- |
| Python tools discovery | 479 tests passed |
| Focused context adapter (also rerun after SSD reconnection) | 12 tests passed |
| Native context integration | 17 tests passed |
| Dev context/session/binding/approval/execution/reentry/completion regression | 15 CTest entries passed |
| ASan/UBSan context/session/binding | 5 CTest entries passed |
| Final Release context/session/binding | 3 CTest entries passed |
| Original baseline binary versus new binary, same disposable Work | v1 candidate bytes identical; old published CAS read unchanged |

The same-fixture provider comparison uses production envelope encoding and count
request construction, with a fake HTTP response at the transport boundary. It
makes no network or generation calls. The fake count of 800 is a test constant,
not a measured token count. Captured request bytes equal the saved handoff bytes.

| Existing adapter | v1 envelope bytes | v2 envelope bytes |
| --- | ---: | ---: |
| `openai.responses.v1` | 34595 | 17331 |
| `anthropic.messages.v1` | 34592 | 17328 |

These are fixture-specific byte measurements, not token/cost savings or semantic
model-quality measurements. Both versions preserve identical mandatory facts
and source inventories. Each handoff retains the same four CLI phases: session
status, session next, context candidate, session resume; each makes one fake count
request. Saved execution-start records verify the actual command arguments.

Tests reject representation/count identity mismatch, tampered payload hashes,
mutated payload/instructions, invalid token counts and stale Work state. Native
short-buffer/token-callback behavior, corrupt-original rejection, read-only
non-mutation, publication/read compatibility and duplicate RUNNING resume receipt
handling are covered. Existing authority and completion implementations are not
changed. This is targeted coverage, not proof of every possible interleaving.

An initial Release run failed because the new test looked for `started.json`
one directory above its actual `execution/started.json` location. Only that test
path was corrected; the final Release rerun passed. The original failing JUnit
is retained, not overwritten or reclassified as success.

Local evidence (temporary host files, not a durable CI archive):
`/private/tmp/golem-context-single-copy-{impact,asan,release-final}.xml`,
`/private/tmp/golem-context-single-copy-release.xml` (initial failure),
`/private/tmp/golem-context-single-copy-comparison-v2/` (payloads, count proofs,
handoffs and execution-start records), and
`/private/tmp/golem-context-v1-compatibility/` (baseline comparison).
The direct unittest totals above were observed in command output; no JUnit is
claimed for those runs. Existing source artifacts, journals and product evidence
were not rewritten. No installation, license, credential or access-policy change,
paid experiment, commit, push or deployment is part of this phase.
