# Bounded lightweight AWE follow-up

Decision recorded before follow-up implementation, 2026-10-20. Base source is
`f7613b6d35adc6241d66049ca3c725f95d8f0056` plus the preserved phase-1 diff described
in [single-copy facts](context-input-decision.md). No unrelated changes are owned.

## Decisions

1. Keep the existing reviewed lifecycle plan and one controller invocation.
   It already records facts, checks immutable inputs and prevents replay after
   interruption. Add a small default CLI view derived from its existing result;
   retain full results, per-step evidence and explicit full output. Do not merge
   dispatch records into completion records: those represent different facts.
2. Tighten the new, not-yet-released provider config v2 handoff. Require explicit
   `original-v1` and zero omitted source bytes rather than inferring what prose is
   important. Reuse the native transitive dependency closure/current-source checks.
   Keep all metadata/history for now: pruning them without a proven dependency
   contract would discard failures or decisions. Insufficient byte/token budgets
   block; the caller must explicitly review larger budgets or original retrieval.
3. Include the full read-only status/next observations in the v2 counted input,
   retaining pending attempts, recovery hints and recent failures. Bind those
   observations into tokenizer identity as well as the exact envelope hash. They
   describe pre-resume state, not post-resume permission; the native receipt must
   still be inspected after mutation. Legacy config v1 stays byte-compatible.
4. Reuse short coded error/recovery mappings in saved evidence and CLI errors.
   Never turn a failed or ambiguous mutation into automatic retry. No new daemon,
   provider, memory engine, gateway or automatic execution is introduced.

Alternatives rejected: recent-N history truncation; keyword-based completeness
claims; implicit recipe changes; treating preflight queries as a lock; counting
an input different from the delivered envelope; replacing native gates with
wrapper success. One wrapper invocation is not an atomic transaction and FINISHED
is not DONE. Config v2 requires explicit adoption; renderer v1 and persisted data
remain unchanged. Version 2 Markdown alone remains incomplete.

## Reading and reasoning

Inspected on 2026-10-20; applications below are engineering decisions, not results
reported by these sources. This supplements phase 1's nine-source record.

| Source and reading scope | Source observation and bounded application |
| --- | --- |
| Jerome H. Saltzer and Michael D. Schroeder, *The Protection of Information in Computer Systems*, Proceedings of the IEEE 63(9), 1975, DOI 10.1109/PROC.1975.9939; [author-hosted Basic Principles section](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html), principles a-c, f-h. | Small mechanisms, fail-safe defaults and repeated authority checks motivate retaining native mediation and blocking incomplete inputs. These principles are not a proof that every access path is mediated. The accessible section, not the entire paper, was inspected. |
| Mike Burrows, *The Chubby lock service for loosely-coupled distributed systems*, OSDI 2006; [original USENIX text](https://www.usenix.org/legacy/event/osdi06/tech/full_papers/burrows/burrows_html/), section 2.4. | Delayed requests can outlive ownership; recipients validate generation-bearing sequencers. Application: keep native fencing after read-only preflight, not add distributed locking. No Chubby semantics/compliance claim. |
| Niall Murphy with John Looney and Michael Kacirek, edited by Betsy Beyer, in Betsy Beyer, Chris Jones, Jennifer Petoff and Niall Richard Murphy (eds.), *Site Reliability Engineering*, O'Reilly, 2016; [chapter 7, The Evolution of Automation at Google](https://sre.google/sre-book/automation-at-google/), consistency and platform/use-case discussion. | Bounded automation benefits from predictable behavior and exposed failures. Application: derive a compact view from existing durable facts without replacing recovery. Accessible chapter sections only; no whole-book claim or measured productivity inference. |

The phase-1 reading of Parnas (1972), RFC 8785 (2020), PROV-DM (2013),
*Software Engineering at Google* (2020, chapter 13), and provider counting guidance
also applies: keep rendering/transport boundaries, preserve exact identities,
distinguish observed facts from authority, and test native behavior rather than
only mocks. No semantic compression, billing savings or general model-quality
claim follows from those readings.

## Checks required before publication

Reproduce incomplete body/preflight handoff first; block before provider calls.
Verify v2 preflight mutation changes identity and cannot reuse a count; preserve
full mandatory facts, source bodies and command paths in native fixtures.
Verify compact/full lifecycle views have equal status/identity and do not replay
or rewrite evidence. Run native stale source/QA, lease, binding, sequence,
idempotency, recovery and completion regressions, plus Python and sanitizer tests.
Real providers remain untested; fake transport is labeled. Publish only after
source/secret review; record exact pushed SHA and all remote CI conclusions.

## Observed local results

macOS arm64, 2026-10-20; no real provider or paid generation experiment.

| Check | Observed result |
| --- | --- |
| Whole Python tools discovery, host execution | 483 passed; final strengthened preflight subassertion also passed in the 14-test adapter rerun |
| Native context integration, final retained fixture | 17 passed |
| Lifecycle unit tests | 18 passed, including compact/full equivalence, non-mutation, stopped and uncertain states |
| Dev influence set | Initial 15/17 passed; execution_cli and completion_cli failed with INCOMPLETE_WORK/cleanup EPERM observations; unchanged isolated rerun passed both |
| ASan/UBSan context/session/binding | 5/5 passed |
| Release context/session/binding | 3/3 passed |
| Legacy binary compatibility (phase 1, same native changes) | v1 bytes identical and old CAS read unchanged |

The initial Python discovery in the restricted process had four socket-bind
EPERM errors. Host execution passed all 483 without changing or skipping tests.
For the two native failures, isolated success is not proof of the parallel EPERM
root cause or its resolution. Preserve both JUnit results; remote CI is separate.

Local JUnit files: `/private/tmp/golem-lightweight-followup-dev.xml` (initial
failures), `golem-lightweight-followup-recheck.xml` (isolated rerun),
`golem-lightweight-followup-asan.xml`, `golem-lightweight-followup-release.xml`
(all under `/private/tmp`). Python totals were observed in command output, not
fabricated JUnit. These temporary host files are not a durable CI archive.

The final same-fixture comparison uses `original-v1` for both versions. V2 also
includes its full preflight observations. Actual production request bytes equal
the saved handoff bytes; HTTP responses are fake, counts are the constant 800,
and generation is never executed. No token/billing savings follow from this.

| Adapter | v1 envelope bytes | v2 envelope bytes |
| --- | ---: | ---: |
| `openai.responses.v1` | 132705 | 128496 |
| `anthropic.messages.v1` | 132702 | 129748 |

Each handoff still uses four native CLI phases (status, next, candidate, resume)
and one fake count request. The existing lifecycle still uses one controller
invocation and the explicitly planned commands; no subprocess-count or latency
reduction is claimed. Full mandatory facts/source inventory remain equal across
renderers; v2 additionally carries preflight state/recent events. RUNNING/recovery
handoff keeps RECOVERY_REQUIRED, never grants execution or silently reruns work.
Evidence: `/private/tmp/golem-lightweight-comparison-final/`, including captured
argv, provider input, native proof, receipt and comparison JSON.

Review found existing native `session context` already exports the pinned
manifest, full required bodies, claim and recent events; reentry records retain
observations and decisions. These mechanisms were reused, not reimplemented.
No verification core, journal, CAS, receipt, approval, lease/fencing or native
completion implementation changed. No historical Work migration or installation
was performed. Independent review and real-provider/model-quality evaluation
are not established by these fixture tests. Linux remote CI results must be read
from the exact pushed SHA; Windows runtime support is not introduced.
