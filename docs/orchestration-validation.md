# Orchestration validation

The 32G tools collect **derived validation evidence**, not runtime authority.
A successful fixture suite does not certify a provider, authorize execution,
or prove arbitrary migration and power-loss safety.

## Contract matrix

Build with the optional event bridge enabled, then run:

```sh
cmake -S . -B build/validation -DGOLEM_BUILD_EVENT_BRIDGE=ON -DGOLEM_ENABLE_SANITIZERS=ON
cmake --build build/validation --parallel 2
python3 tools/verify_orchestration.py --build build/validation --output build/validation-evidence
```

The output directory must be new. Preserve it privately; logs and inventory may
contain local paths and Work data. Do not upload it as a public CI artifact.
The command checks an exact CTest inventory before executing the groups. Missing,
duplicate, skipped, failed or unreported tests cannot produce PASS. Each finished
group retains its process result and JUnit digest even if a later group stops.
The final report checks that pinned executable/test inputs did not change.
Python discovery suites and wrapper sibling/package helpers are included in the
input inventory. Empty groups and duplicate required test names fail closed.
This local inventory is not a hermetic dependency trace or signed attestation.
An interrupted invocation without a final report is **not completed**; restart
with a new directory. Reusing evidence is not rerunning a failed command.

| Group | Contract exercised |
| --- | --- |
| migration | Historical completion fixture; legacy workflow; immutable template selection |
| authority | Role evidence, forged approvals, one-use consumption, session fencing |
| recovery | Real C FAIL -> revision -> PASS -> review -> completion/report recovery; pinned candidate diff |
| observation | Read-only event access, slow subscribers, cursor/reconnect and HTTP restrictions |
| hardening | Report adjudication, allocator failure, parser mutations, standalone public headers |

These are complementary scenarios, not a single exhaustive simultaneous-fault
model. In particular, old fixture readability is not proof that an old executable
can safely modify a new store. Unsupported selection versions are rejected
without changing the store. Never downgrade a writable production store without
a separately tested migration/backup procedure.

## Reproducible performance evidence

```sh
ctest --test-dir build/validation --output-on-failure -R '^orchestration_benchmark$'
```

This creates a small candidate fixture with real C QA, seals a metadata-redacted
diff, and records 30 samples each of history, events, diff and template reads.
The raw samples live in a uniquely named build-directory subdirectory printed
by the test. Setup and warmup are excluded. Workload order is deterministically
randomized. CLI startup and replay are included, so these are not pure C API
microbenchmark numbers. Output digests must remain identical throughout the run.
The collector also pins existing command input files, its helper modules and the
adjacent CMake cache when available. Changed inputs invalidate the measurement
even if projection bytes happen to remain identical.

For an existing quiescent fixture:

```sh
python3 tools/benchmark_orchestration.py --cli build/validation/golem \
  --work "$WORK" --history-request "$HISTORY_REQUEST" --admission "$ADMISSION" \
  --candidates "$PARENT_WORK" --group group --candidate a --output "$NEW_PRIVATE_DIR"
```

Only four fixed read commands are constructed; no arbitrary shell template is
accepted. The history request controls the page size; pin it and the fixture when
comparing runs. Median, p95, p99 and relative MAD are descriptive statistics.
`performance_gate=NOT_EVALUATED`: no portable speedup, SLO or regression threshold
is asserted from a developer machine. Establish comparable stable-runner baselines
before using these numbers as a release gate. Small samples cannot reliably
characterize rare latency spikes.

## Real current-agent canary

Do not relabel synthetic host identities as authenticated Codex or Claude runs.
Use a separate disposable project and explicitly authorized execution contract:

1. Record the installed CLI digest, descriptor/binding and whether identity is
   host-observed or self-reported. Keep native thread identifiers private.
2. Let the current agent register scope, template, documents and role enrollment.
   Human approvals remain separate; never automatically approve the canary.
3. Preserve an actual failing QA receipt, reentry decision, revised document
   digests, a passing QA receipt, exact review and completion receipt.
4. Reopen from a fresh client and check report recovery without redispatching.
5. Observe the resulting Work with the existing collector:

```sh
python3 tools/verify_agent.py observe --cli "$GOLEM" --work "$WORK" \
  --selection selection --output "$NEW_PRIVATE_OBSERVATION_DIR"
```

Observation alone does not prove authorship or the full canary sequence. Keep the
receipt inventory and operator observation alongside it. No provider is launched
by the 32G fixture runner. Installed Python/TypeScript package tests remain in the
separate language-binding/release workflows.

## Research basis

- [SLSA provenance](https://slsa.dev/spec/v1.2/provenance): motivates recording
  the inputs and process behind results. These local derived reports are not
  SLSA attestations or a claim of SLSA certification.

- [Mohan et al., OSDI 2018, B3](https://www.usenix.org/conference/osdi18/presentation/mohan):
  motivates small, explicit crash-boundary workloads. Our process-fault fixtures
  do not reproduce CrashMonkey's filesystem power-loss exploration.
- [Lamport, Specifying Systems (2002)](https://lamport.azurewebsites.net/tla/book.html):
  motivates checking invariants across transitions and replay, not just a happy
  path. No TLA+ proof is claimed.
- [Google Benchmark user guide](https://google.github.io/benchmark/user_guide.html):
  motivates separate warmup, repetitions, randomized interleaving and careful
  treatment of measurement variance. The collector measures CLI wall time using
  Python's monotonic performance clock; it does not depend on Google Benchmark.
