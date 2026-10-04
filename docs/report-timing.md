# Report timing and durable evidence

This policy separates evidence needed to determine or recover state from optional
human presentation. A filename containing `report` does not make its content
optional. JSON verdicts, JUnit, logs, digests, decisions and acceptance predicates
remain mandatory. No report timing choice grants authority, turns FAIL into PASS,
or permits dropping raw records.

## Reviewed boundaries

| Production path | Timing | Retained contract |
| --- | --- | --- |
| `tools/agent_io.py` capture, observe, lifecycle | No automatic Markdown; explicit `report` | Raw execution records, manifest, failure stop, integrity-checked view |
| `tools/verify_agent.py` fixture/observe | Markdown deferred by default; optional `--report-at requested`, `handoff`, `completion` after capture | Durable `report.json`, command records and raw logs regardless of presentation |
| `tools/verify_agent.py report` | Explicit read-only render of a saved observation | Input SHA-256 and renderer ID in output; no commands replayed |
| Native reentry decide/status/replay, event v2 | No Markdown | Complete decision, request, observations, hypothesis, budgets, renderer version in journal/CAS |
| Native reentry report | Explicit sequence-bound render; optional projection via API | Immutable decision remains authoritative; projection conflicts are not overwritten |
| Session context after v2 reentry | Structured `failure_record`, no Markdown | Manifest v3 binds decision digest and failure receipt; CAS bytes count against budget |
| Historical reentry event v1 | Original rendering/digest validation retained | Existing evidence and context byte contracts must not be silently weakened |
| Completion finalize / historical replay | Required at completion / integrity verification | Existing acceptance, report digest, recovery and DONE gates unchanged |
| Discovery/research/metrics/context/execution report APIs | Explicit report/render/export request | Deterministic request-scoped projection, no implicit background work |
| Proof and research bundles | Explicit artifact request | Checksums, redaction and evidence inventory remain required |
| Runtime/environment/isolation/resource/preflight/orchestration validation | Machine gate evidence always generated | Existing JSON/JUnit consumers and CI decisions unchanged |

Authored QA/development/completion documents are required workflow inputs, not
optional summaries. This change does not suppress them. Context rendering requested
by a caller is likewise not an automatic per-attempt report.

## Version and failure behavior

New reentry events use schema 2 with `renderer_version: 1` instead of
`report_digest`. The frozen renderer consumes the validated recorded decision,
never current source files, current wall time, or a new provider response. Replay
still recomputes decisions against their original document prefix. Unknown renderer
versions fail closed. Context manifest v3 exports the complete structured event;
older manifest v2 retains its original `failure_markdown` behavior.

Completion resume's failure-history entries retain `report_digest` for v1 decisions;
v2 entries expose `report_policy: ON_REQUEST` and `renderer_version` with their
decision digest. The policy does not assert whether someone has already projected
a file. Presentation is not a new workflow event and never changes the decision
identity, counters, authorization, or journal head.

No cache or background queue is introduced. Explicit requests may render again.
Failure to write the projected file is a presentation failure; the durable decision
is still available. An existing different file is preserved and rejected. Missing
v1 report evidence remains an integrity error, not permission to regenerate history.
Old readers cannot consume v2 events/v3 manifests: upgrade consumers together;
there is no automatic migration, downgrade, or rewrite of live Work stores.

Conformance's optional Markdown is written only after its JSON observation has
been durably saved. Rendering failure returns an error while retaining that JSON
and raw logs. Its separate `report` mode prints a deterministic projection without
mutating the original directory. A hash identifies observed input bytes, not their
authenticity; unsigned observations are not trusted approvals. A requested
`completion` presentation boundary can still describe BLOCKED or FAIL.

## Research trace

Selected sections below were read, not entire textbooks. These are design inputs,
not experimental evidence of Golem token savings or a formal proof.

| Source | Sections reviewed and application | Boundary |
| --- | --- | --- |
| Zhou, Larson, Elmongui, [Lazy Maintenance of Materialized Views](https://www.vldb.org/conf/2007/papers/research/p231-zhou.pdf), VLDB 2007, pp. 231-242 | 2.2, 2.3, 6.1-6.2: separate source updates from presentation work; retain sufficient inputs for later reconstruction | No SQL incremental maintenance algorithm or paper's speedups claimed; required integrity checks remain eager |
| Hellerstein, Stonebraker, Hamilton, [Architecture of a Database System](https://dsf.berkeley.edu/papers/fntdb07-architecture.pdf), Foundations and Trends in Databases 1(2), 2007, scholarly monograph | 4.6.2-4.6.3: pin an immutable source version and distinguish logical from materialized views | Report freshness is tied to a specific decision/observation, not inferred from file time |
| Abelson and Sussman with Sussman, [Structure and Interpretation of Computer Programs, section 3.5.1](https://sicp.sourceacademy.org/chapters/3.5.1.html), original text in the Comparison Edition | Separate construction of a durable input from demand-driven evaluation of its presentation | This is a design analogy, not a stream implementation; no persistent memoization cache is introduced |
| W3C, [PROV-DM](https://www.w3.org/TR/prov-dm/), 2013 Recommendation | 2.1 and 5.2.1: distinguish input entity, derivation and generated entity | Source digest plus pinned renderer describe derivation; not an assertion of PROV serialization conformance or trusted authorship |

The lazy-view paper explicitly notes deferred-work errors and cases where eager
maintenance is preferable. Accordingly, completion acceptance and historical
integrity verification are not deferred merely to reduce presentation work.

## Regression and extension

`report_timing_cli` injects renderer allocation failure while requiring decision
commit and replay to succeed. It checks absent per-attempt Markdown, deterministic explicit
rendering, read-only generation, projection collision/recovery, stable journal/CAS,
mixed v1/v2 histories, historical session context, exact context-byte accounting,
missing historical evidence, and unknown/tampered records.
`reentry_cli` exercises structured context through repair and QA; completion tests
retain DONE/report recovery checks. `test_verify_agent.py` checks default deferral,
boundary opt-in, render-failure evidence retention, and no replay in report mode.

`reporting_inventory` pins known native renderer reference sites and Python AST
call sites. It is an architecture tripwire, not a proof about arbitrary new code
or aliases. New renderers require a timing classification here and tests at their
call boundary. A changed renderer needs a new version, not edits to historical
byte definitions. New consumers must support versioned structured context.

No token/cost or end-to-end latency reduction is asserted without measurement.
Structural JSON may be larger than Markdown; this change removes unsolicited
formatting, not necessary evidence or context-budget accounting.
