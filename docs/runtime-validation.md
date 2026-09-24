# Runtime Validation

Phase 30G separates contract regressions, fault injection, bounded exploration,
measurements and real current-agent evidence. A successful fixture suite is not
proof of model behavior, a production SLO, or release readiness.

For verification bundles, isolated worktrees, package boundaries and an
interactive current-agent canary, see [Isolation qualification](isolation-validation.md).

## Development Baseline Status

The Phase 30A-30G development baseline is closed. Delivered modules cover runtime
profiles, harness descriptors, admission, workers, context projections, diagnostics
and repeatable validation tools. This is a scoped development milestone, not a
claim that all original acceptance conditions have been satisfied.

Follow-up work remains explicit: implement the full end-to-end performance matrix
(profile caching, lane contention, worker saturation and slow observers), collect
stable-runner baselines, and requalify the complete Phase 30 flow with real current
Codex and Claude sessions. The existing event-ring microbenchmark and scripted
canary do not substitute for these tasks. Continue field validation without
weakening completion gates or promoting fixture evidence to live-agent evidence.

## Feature Enrollment and Rollback

| Feature | Enrollment and compatibility | Rollback boundary |
| --- | --- | --- |
| Runtime profile | Legacy Work identity stays UNKNOWN. Explicit registration or Work spec v2 enrolls it. Claims pin generations through session records v2. | No removal/downgrade. Finish with a compatible writer; keep original store and evidence. |
| Descriptor | Capability v1 and JSON/MessagePack fixtures remain readable. Host-observed capabilities are separate from claims. | Stop new dispatch; a profile alone does not enable the descriptor gate. |
| Admission | Explicit namespace/store and Work binding; separate ledger, no implicit legacy enrollment. | Reconcile uncertain dispatch before release, not delete-and-retry. |
| Worker | Opt-in bounded pool; synchronous legacy executor remains available. | Confirm process termination before reclaiming reservations. |
| Context | Optional derived projection tied to original closure and renderer. | Read original documents; never replace original revisions with a summary. |
| Events | Read-only derived page; transient ring may lose records with explicit gaps. | Stop observation without changing Work execution or journal schema. |

Binary journal framing is unchanged. New mandatory document/session records are
not rewritten for old writers. Compatibility testing must exercise an actual old
binary against disposable copies, not assume that sharing a version string means
sharing a schema. The cross-binary tool below first requires successful legacy
creation/submission, then verifies rejection and unchanged content after profile
enrollment. It covers that supplied binary, not every historical release.

## Repeatable Contract Run

```sh
cmake --preset release -DGOLEM_BUILD_BENCHMARKS=ON
cmake --build --preset release
python3 tools/verify_runtime.py --build build/release --output build/runtime-validation
```

Use a new output directory each time. Existing results are never overwritten.
The runner requires exact CTest names, retains JUnit/log digests and checks that
the CLI and directly invoked test inputs did not change. Missing, skipped,
duplicated, failed and timed-out tests fail the aggregate. A PASS refers only to
the listed local contract groups. It always reports `actual_agent_verified=false`
and `release_ready=false`; it is not an automatic release authority.

Raw logs/inventories contain local paths and host metadata. Directories are private
and ignored under `build/`. Do not automatically publish them as CI artifacts.
Reports hash directly invoked files, not a hermetic closure of all Python imports,
shared libraries or operating system dependencies.

```sh
python3 tools/verify_runtime_legacy.py \
  --current build/release/golem --legacy /absolute/path/to/old/golem \
  --source . --output build/legacy-validation
```

This creates a fresh Work, never migrates a user's existing store, and retains
command outputs on rejection/failure. Exit status must be checked; absence of a
final PASS report means validation is incomplete. Review the binary's provenance
before running it. The tool does not download or trust a binary for you.

## Safety, Faults and Fairness

`admission_explore` examines three tickets across 64 fixed Work/session lane
assignments. Grant, bind, start, run, cancel, settle and release are individual
actions. The visited-state key includes binding presence, ticket states and
foreground bypass count; fixed configuration and fixed proof bytes are explicit
model bounds. On an invariant failure, stderr records the assignment seed and
operation/ticket path. Preserve that log as the regression input.

This is exploration of the C arbiter under bounded inputs, not an independent
TLA+ refinement proof. Restart/storage faults are separate tests. Fairness is
checked separately under finite execution and eventual release assumptions; a
hung process cannot be assumed to release resources merely because time passed.
No universal starvation-freedom or exhaustive operating-system schedule claim is
made. Existing seeded JSON/MessagePack/document/admission mutations, allocator
failures, syscall faults and supervisor races remain required regressions.

Linux/macOS dev/release/ASan+UBSan jobs run the CTest suites; Linux also runs leak
checks and libFuzzer smoke. Release jobs additionally run the aggregate verifier.
Local macOS results do not stand in for Linux or remote CI results.

## Performance Evidence

```sh
python3 tools/benchmark_runtime.py \
  --binary build/release/bench/golem_runtime_bench \
  --profile samples/runtime-profile.json --pairs 30 --seed 30 \
  --output build/runtime-measurement
```

The C workload appends 100,000 events and performs 0, 1 or 32 synchronous observer
pulls every 16 appends. Warmup is excluded. Mode order is deterministically shuffled
within each pair. Keep all samples, including slower results; the collector emits
median, nearest-rank p95/p99, relative MAD, paired ratios and RSS high-water in
bytes, plus binary/profile-file/build-cache/collector hashes. These are *batch
average nanoseconds per append*, not individual event latency percentiles.

The sample profile is an input fingerprint, not a runtime observation or proof of
provider availability. A build-cache hash identifies configuration but does not
establish equivalent hardware. Use an idle Release build on matched hardware for
comparison; sanitized/debug results are correctness diagnostics only.

No automatic performance PASS is issued. The proposed 5% end-to-end observer
overhead and 20% inspect/cancel regression limits require an end-to-end baseline
on a stable runner. Applying them to an isolated append loop is invalid. Cold/warm
profile discovery, session-capacity matrices, hung-worker control latency and
semantic context fidelity still need dedicated performance/agent experiments.

## Current-Agent Canary

`runtime_canary` combines profile enrollment and binding assertions with real C QA
execution, FAIL -> document revision -> fix -> PASS -> completion, restart/adopt
without duplicate output, and stale-source completion rejection. Decisions and
source fixes in this regression are scripted; it is not a real Codex/Claude
reasoning evaluation. Cancellation/resource release is exercised separately in
worker tests, not represented as an unsupported session cancellation command.

For actual-agent validation, the currently working agent must operate a separate
disposable Work through the normal [session contract](agent-session.md), register
its honestly reported profile, author/revise Markdown, run actual QA and collect
completion evidence. Record session identity as reported, not authenticated.
Retain the Work, failed and passing receipts, source snapshots and final report.
Use `tools/verify_agent.py observe` with that Work for read-only observation;
observation alone does not authenticate authorship. Missing actual-agent evidence
must stay NOT_DONE, never be replaced with synthetic PASS receipts.

## Research Basis

- [Lamport, Specifying Systems, Chapter 8](https://lamport.azurewebsites.net/tla/book-21-07-04.pdf): safety and fairness are separate obligations. Applied to bounded exploration and explicit liveness assumptions, not a full implementation proof.
- [SRE, Testing for Reliability, Chapter 17](https://sre.google/sre-book/testing-reliability/): preserve fault histories/seeds and test anticipated misbehavior. Applied to failure traces and nonempty, non-skipped verification gates.
- [Maricq et al., Taming Performance Variability, OSDI 2018](https://www.usenix.org/system/files/osdi18-maricq.pdf): repeated measurements and environment variability affect confidence. Applied to raw paired samples and refusal to treat 30 observations as a reliable tail/SLO proof.

Only the relevant publicly available chapters/sections were reviewed. Their
findings motivate these tests; they do not certify Golem's correctness or speed.
