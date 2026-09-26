# Runtime environment diagnostics

For configure/build/test evidence, distinct full and restricted profiles, and CI
artifact retention, see [Environment-scoped verification](environment-verification.md).

Golem requires more than writable files. Work sessions and admission require
stable OS boot identity and monotonic time. Candidate transport also requires
local UNIX sockets. A restricted process may be able to build Golem while being
unable to run those paths. Never equate an environment failure with product PASS.

## Commands

```sh
golem doctor clock
golem doctor work /absolute/path/to/existing/work
python3 tools/doctor_environment.py --binary build/release/golem \
  --root /tmp --profile local-dev
```

Repeat `--root` for each intended scratch filesystem; on macOS compare `/tmp`,
`/private/tmp`, and `$TMPDIR`. Reports preserve the requested root spelling while
using resolved paths for the engine's no-symlink contract. Output contains local
paths and must be reviewed before publication. No secrets or boot ID values are
printed. Each root receives a private disposable directory that is cleaned up.

`golem doctor admission ABSOLUTE_DISPOSABLE_DIRECTORY` exercises real admission
initialization/replay, owner lock, randomness, boot identity, event publication
and close. **It is mutating. Never point it at an existing production ledger.**
`doctor work` instead opens the existing document store read-only and replays it;
it does not grant completion, alter claims or repair corruption.
The Python wrapper creates a fresh directory for it and also checks filesystem
sync/link/no-follow, exclusive flock and UNIX socket bind/listen.

The declared profiles `full-ci`, `local-dev`, `restricted-sandbox` and
`read-only-observation` label observations; they do not grant authority, disable
checks, or certify a sandbox. Even an observation-labelled probe writes its own
scratch directory. Use `doctor clock` alone when no scratch writes are permitted.
PASS means only the measured prerequisites passed, not Work or product acceptance.
UNSUPPORTED_ENVIRONMENT returns nonzero and must not be relabelled PASS/SKIPPED.

## Diagnostics and compatibility

The additive C API `golem_admission_open_diagnostic` preserves the old API and
status values. The optional diagnostic is caller-owned and contains a stable
operation plus captured errno. Root, owner lock, replay, initial commit,
boot/clock, RNG and epoch commit are distinguished. The combined boot/clock probe
does not yet distinguish every syscall within those operations. Logical failures
may have errno zero; status remains authoritative. No global last-error buffer.
The boot/clock prerequisite is now checked before the initial durable event.

Session CLI emits an additional JSON stderr record on errors, separating request
read/parse, Work open/replay and session operation. Session diagnostics distinguish
log replay, boot/clock, policy, prepare, CAS/event construction and commit. Existing
exit codes and stdout success envelopes remain unchanged. Host serve failures also
emit JSON stderr; admission failures include the operation. A SIGKILL or broken
stderr cannot guarantee a final frame. Peer disconnect never proves termination
and must not release an uncertain reservation.

CPU model is optional benchmark metadata. An unavailable probe records `cpu: null`
and `cpu_probe_error`; measured workloads still run. Required executable, filesystem,
clock or test failures remain fatal. Missing CPU metadata is not proof of comparable
hardware and should not justify cross-host performance claims.

## Regression and triage

`doctor_cli` covers clock, real open/reopen, symlink rejection, owner exclusion and
invalid arguments, read-only Work byte preservation, and structured session/host
startup failures. `admission_open_diagnostics` injects root, lock, replay, clock,
RNG and initial/epoch commit failures; clock failure must publish no commit.
`doctor_environment` exercises prerequisites in CTest; CI also
runs a preflight step before its full suite. No skip conversion is installed.
`golden_workflow` repeats two real-CLI paths three times: current-agent
completion/recovery/idempotency, and current-agent real C QA FAIL -> classified
revision -> fresh QA claim -> repair -> PASS -> completion. These remain bounded
paths, not proof of all interleavings or live provider behavior.

```sh
ctest --preset release --output-junit results.xml
python3 tools/classify_failures.py --environment environment.json --junit results.xml
```

The classifier retains failures, skips and unclassified tests. Its six groups are
triage hypotheses, not causal proof. It never discounts a test because admission
or an environment probe failed. Empty/duplicate inventories are invalid evidence.
Match commit, binary hash, build options, host permissions and timestamps before
joining independently collected reports. The classifier does not establish that
provenance for the caller or assert that JUnit contains the entire expected suite.

## Research Basis and Remaining Scope

- Yuan et al., [OSDI 2014](https://www.usenix.org/conference/osdi14/technical-sessions/presentation/yuan):
  motivates testing error-handling paths and keeping triggering context, rather
  than counting only happy-path features. Its findings are not Golem measurements.
- Musuvathi et al., [CHESS](https://www.microsoft.com/en-us/research/publication/chess-a-systematic-testing-tool-for-concurrent-software/):
  motivates reproducible, bounded concurrency exploration. Repeating this smoke
  does not implement CHESS or explore all schedules.
- Lamport, [Specifying Systems](https://lamport.azurewebsites.net/tla/book.html):
  supports separating safety invariants from progress/environment assumptions.
  In particular, uncertain termination must retain reservations. No formal proof
  is claimed for this implementation.
- Perry and Luebbe, [Testing for Reliability, SRE chapter 17](https://sre.google/sre-book/testing-reliability/):
  informs the distinction between prerequisite tests, integration tests and
  operational confidence. A green unit suite is not a release certification.

Still required for the full stabilization proposal: per-syscall fault-injected
admission-open diagnostics; finer completion prerequisite
diagnostics; uniform readiness handshake across test and product hosts; all-stage
kill/restart matrix; independently reproduced evaluator environment and Linux runs.
Existing QA receipts already carry reasons such as NONZERO_EXIT, CASE_FAILED and
INVALID_OR_MISSING_CASES; keep those records rather than replacing them with a
single aggregate FAIL. Do not claim all 50 reported failures fixed from this work.
