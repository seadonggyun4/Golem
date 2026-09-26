# Environment-scoped verification evidence

`tools/verify_environment.py` binds a configure/build/test invocation to its
source, executable, environment observations and original outcomes. It reuses
`verify_agent` process/log helpers and `verify_runtime` JUnit/input checks.
CTest remains the executor. Work receipts and completion authority are unchanged.

## Running

Choose a new output directory with an existing parent. In-repository output must
be Git-ignored. These examples run from the repository root:
On macOS use `/private/tmp` for output (`/tmp` is a symlink, which private output
creation deliberately rejects).

```sh
python3 tools/verify_environment.py --preset dev --profile restricted-sandbox \
  --root /tmp --output /tmp/golem-diagnostic-001
python3 tools/verify_environment.py --preset dev --profile local-dev \
  --root /tmp --output /tmp/golem-full-001
python3 tools/verify_environment.py --preset release --profile full-ci \
  --root /tmp --output /tmp/golem-release-001 \
  --define GOLEM_BUILD_BENCHMARKS=ON --define GOLEM_BUILD_BINDINGS=ON
python3 tools/verify_environment.py --check-bundle /tmp/golem-full-001
```

Each invocation configures and builds before doctor and CTest. `--timeout`
bounds each phase (default 3600 seconds). Existing output is never overwritten.
After building, `ctest --preset restricted-diagnostic` is a fast shortcut without
the complete bundle. Existing dev/release/asan presets still select full suites.

## Result semantics

| Field | Meaning |
| --- | --- |
| `environment` | Doctor: PASS, UNSUPPORTED_ENVIRONMENT, ERROR, or NOT_RUN |
| `diagnostic_suite` | Diagnostic assertions: PASS, FAIL, or NOT_RUN |
| `full_suite` | Selected build's complete inventory: PASS, FAIL, or NOT_RUN |
| `status` | Requested profile requirements satisfied or failed |
| `inputs_unchanged` | Source snapshot and recorded test inputs unchanged at end |
| `product_acceptance` | Always false; no release or Work completion authority |

Restricted mode requires the diagnostic label's exact cases and mandatory
baseline to pass, plus a well-formed identity-matched doctor observation. It may
report PASS / UNSUPPORTED_ENVIRONMENT / diagnostic PASS / full NOT_RUN. This
certifies diagnostic assertions only; the profile name does not attest that the
caller actually runs inside a sandbox.

Full/local modes require supported observations and complete full-suite PASS.
Doctor failure does not suppress the requested full run. Product failures retain
their actual verdict without inferred causality. Missing or malformed doctor
evidence is ERROR. The diagnostic subset can pass within a failed full run if
CTest completed and those exact cases passed.

Exit zero alone is insufficient: inventory must be nonempty and unique; JUnit
must contain exactly the selected tests, run without failure/error/skipped
markers. Inventory is collected without preset filters, so a later preset
exclusion cannot silently shrink full coverage. Timeout and input changes fail
the invocation. Full PASS covers the
recorded configuration, not every optional Golem feature.

## Evidence and limitations

- Before/after source commit, dirty state, tracked/nonignored untracked hashes,
  symlink target hashes, executable bits and tracked deletions. Diff hashes
  identify dirty work without exporting raw diff contents. Submodules are
  rejected pending an explicit recursive identity policy.
- Configure/build arguments and logs, CMake/CTest versions, CMake cache and
  presets, generated compiler identification/version in `toolchain.json`,
  OS/kernel/architecture/Python version, allowlisted CI identity.
- CLI SHA-256, selected executable/script and generated CTest file hashes.
- Doctor JSON in `doctor/stdout.log`, phase exits in `*/result.json`, CTest JSON
  inventory, stdout/stderr logs and `results.xml` JUnit.
- `report.json` and a SHA-256 `manifest.json` covering all evidence files.

`--check-bundle` detects modified/missing/extra files and rejects symlinks. An
intact FAIL bundle passes integrity checking: success and integrity differ.
The manifest is unsigned; replacement of both files and manifest can forge it.
This is not signed provenance, a SLSA level, or independent reproduction.

Snapshots are non-atomic and cannot detect reverted intermediate changes.
Ignored dependencies, system libraries and arbitrary imports are not exhaustively
traced. Existing CMake cache values are recorded, not reset; use a clean build
for independent reproduction. Avoid concurrent builds/source edits during a run.

Local directories are private. Logs, cache and arguments may contain paths or
caller-supplied values; this is not a public redaction format. Arbitrary environment
variables and credentials are not enumerated. CI retains bundles for 14 days,
including failed runs. Hard kill/disk failure may leave only `started.json` and
phase logs; an incomplete bundle cannot establish PASS.

## Coverage and extension

The explicit `restricted-diagnostic` label contains:

- `admission_open_diagnostics`: translation-unit injection for open/lock/replay/
  clock/randomness/publication; deterministic clock; repeated clock denial
  preserves existing event bytes and prevents new event publication.
- `restricted_diagnostics`: real CLI exit/JSON checks; actual boot permission
  denial must identify the precise errno/operation and leave no durable event
  across retries. Unexpected errors fail; supported hosts exercise success.
- `diagnostic_tools`: socket create/bind and filesystem injection, triage
  preservation, evidence failure/identity/integrity regression tests.

Add the label at a new test's CTest definition. JSON discovery includes additions;
a small mandatory baseline guards against accidental removal of the contract.
No production injection environment flags or authority bypasses are introduced.
Socket injection covers the doctor probe, not every host transport syscall.

CI creates separate Linux/macOS full dev/release/ASan and diagnostic artifacts.
Hosted diagnostic jobs exercise injection, not Codex sandbox isolation. Real
sandbox observations are a separate local evidence set.

## Research rationale

Reviewed 2026-09-26. Relevant sections were reviewed, not every book chapter or
every cited work. No external source code was copied.

| Primary reference | Design application and boundary |
| --- | --- |
| Torres-Arias et al., **in-toto**, USENIX Security 2019, sections 2 and 4 ([paper](https://www.usenix.org/system/files/sec19-torres-arias.pdf)) | Link materials/products and execution byproducts: source/build/test identities, logs, exit values. No signed-layout guarantees claimed. |
| Yuan et al., **Simple Testing Can Prevent Most Critical Failures**, OSDI 2014, error-handling findings ([paper](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf)) | Test error paths deterministically and assert state preservation. The paper's empirical failure percentages are not extrapolated to Golem. |
| Winters, Manshreck, Wright (eds.), **Software Engineering at Google**, O'Reilly 2020, chapter 11 ([chapter](https://abseil.io/resources/swe-book/html/ch11.html)) | Distinguish test scope from execution constraints; keep diagnostic contracts and host integration separate. Not a fully hermetic suite. |
| Beyer et al. (eds.), **Site Reliability Engineering**, O'Reilly 2016, chapter 17 ([chapter](https://sre.google/sre-book/testing-reliability/)) | Layered testing and deliberate failures support bounded reliability confidence; full recovery matrix remains separate. |
| Ammann and Offutt, **Introduction to Software Testing**, 2nd ed., Cambridge, chapter 3 public Test Automation summary ([publisher](https://www.cambridge.org/highereducation/books/introduction-to-software-testing/95E57CCADEA697EC8594F03729F47311/test-automation/56A0DED2D0401EC6F5B9AD7F973AA0BA)) | Setup, execution, expected-outcome comparison and reporting motivate an explicit inventory/JUnit oracle. Only the publisher's indexed summary was accessible, not the full chapter. |
| [SLSA v1.2 build provenance](https://slsa.dev/spec/v1.2/build-provenance) | Separate build definition, run details and byproducts in a versioned native report; no SLSA attestation/conformance claim. |
| [CMake 3.21 CTest manual](https://cmake.org/cmake/help/v3.21/manual/ctest.1.html) | JSON inventory, labels and JUnit avoid scraping human summaries; retain CMake 3.21 minimum. |
| [GitHub artifact documentation](https://docs.github.com/en/actions/tutorials/store-and-share-data) | Persist per-OS/preset evidence on failure, with finite retention and artifact transport digest. |

ACM's artifact-badging policy returned HTTP 403; no unverified claims from that
page are used as implementation requirements.

## Remaining work

Historical 330/330 claims without matching bundles remain reported historical
host observations. New invocations establish their own identities and counts.
Per-syscall diagnostics, host readiness unification, completion prerequisites,
the full kill/recovery matrix and independent evaluation remain separate work.
Linux CI coverage does not itself establish independent reproduction.
