# Automatic mechanical execution records

The owned Python execution boundary now records every invocation that reaches
`execution_record.capture` or its checked `run` adapter. Existing callers of
`verify_agent.capture` inherit this behavior without a new opt-in flag. Native
Work receipts remain authoritative for their own contracts; these records are
private, unsigned observations, not approvals, QA verdicts or replay instructions.

## Recorded lifecycle

Each command has separate `stdout.log`, `stderr.log` and an `execution/` directory:

| File | Observation |
| --- | --- |
| `started.json` | Unique invocation ID, exact argv, canonical cwd, UTC start, timeout/output policy, executable path/hash, recorder hash and runtime version |
| `source-before.json` | Git commit, dirty state, status/diff hashes and tracked/nonignored untracked content inventory, or explicit UNAVAILABLE |
| `source-after.json` | Same observation after the process; never inferred from HEAD alone |
| `result.json` | Child return code, termination reason, elapsed time, log references, input-change observations, finish time and non-acceptance marker |
| `manifest.json` | Fixed inventory with byte counts and SHA-256 for metadata, stdout/stderr and any explicitly declared additional logs |

Additional flat `.log` names are validated before launch, stored in the intent,
monitored against the same per-file soft output limit, synced and included in
manifest verification. Undeclared or missing additional logs fail verification.
The [explicit Linux syscall runner](syscall-recording.md) uses this extension for
`syscalls.log`; ordinary callers still capture only stdout/stderr. Version-1
records without the optional `extra_logs` field retain their original inventory.

The source observer is shared with `verify_environment`, avoiding competing
definitions of dirty-worktree identity. Symlinks are identified by their target
text; file contents and executable bits, deletions and untracked files contribute.
Ignored files, submodules, libraries, network inputs and arbitrary dependencies
are not traced. Source scans are not atomic. An unavailable Git root/HEAD,
unsupported submodule or nonignored in-source output is recorded as UNAVAILABLE,
not a clean revision. `source_unchanged: null` means unknown, not unchanged.

By default source observation uses the child's cwd, resolving its enclosing Git
root. Callers may pass `source=` explicitly: fixture/legacy checks use the selected
SDK source; clean-source validation records its origin checkout; guard mutation
commands select their disposable, non-Git copy and therefore report unavailable
Git identity, with mutated-file hashes retained in their existing report. This
does not claim that the origin checkout is a hermetic description of an exported
build. The actual executable selected through PATH is resolved and hashed before
and after execution, but this is not a race-free executable attestation.

The child exit code is kept separately from recording completeness. A nonzero
exit, signal, timeout or output-limit breach is recorded without converting it
into PASS. Launch errors retain metadata when storage remains available and are
re-raised to existing callers. Failure to write the initial record prevents the
launch. Finalization failure returns `recording: INCOMPLETE`,
`reason: RECORDING_ERROR`, the original `process_reason` and child return code;
the checked adapter fails. It never reruns the command to reconstruct evidence.
Do not retry mutating operations merely because recording failed.

Missing finish/manifest files, including after SIGKILL or power loss, are not
completed observations. Files use exclusive creation, mode 0600 and fsync;
directories are private 0700. Earlier records are not overwritten. Same-user
malicious interference, escaped process groups and storage/power-loss behavior
outside the filesystem's guarantees are not solved. Logs use a monitored soft
limit (32 MiB per stream), which can overshoot before the process is stopped.
This is not a disk quota. SIGKILL of the recorder can leave its child running:
inspect running work and existing effects before recovery, never automatically
replay an incomplete record.

## Existing-path coverage

| Entry point | Automatic recording and retention |
| --- | --- |
| `agent_io`, `verify_agent`, `verify_environment` | Existing output directories contain command records; existing reports keep their distinct judgments |
| `verify_runtime`, `verify_preflight`, `verify_isolation`, `verify_orchestration` | CTest inventory and selected group launches; delegating wrappers inherit the common boundary |
| `verify_runtime_legacy` | Each old/current binary call, including expected rejection |
| `benchmark_runtime`, `benchmark_orchestration` | Every warmup and measured invocation beneath the selected output |
| `bench/benchmark.py run` | Calibration and samples beside `--output` in `<filename>.records/`; direct Python collection uses a retained directory under scratch |
| `verify_alpha` | Every build/test/install/consumer command in `--output`, or a printed retained temporary directory outside its deleted build workspace |
| `verify_resource` | Four kernel fixture modes in `--output`, or a printed retained temporary directory |
| `doctor_environment` | Clock/admission child commands in a retained private directory referenced by the report; filesystem/socket probes remain direct measurements |
| `agent_entrypoint check --probe` | Version probe retained below `.golem/entrypoints/probe-*`, including failed probes |
| `check_guard_mutations` | Each configure/build/CTest command below the requested output |
| `install_conan_cli` | Conan and version-check records retained beside the install destination even if staging is removed |
| `isolation_canary` | Direct workspace-helper launch; imported synthetic fixtures retain their existing Work evidence, not a new per-subprocess trace |

The [native recorder](native-recording.md) now covers configured direct CLI
dispatch, 68 reviewed C API boundaries, and all supervisor variants, including
pre-launch adapter rejection and owned worker-context handoff. Required
cancel/lease/release controls and selected recovery queries preserve their
operation even if recording fails; that failure remains separately observable. Python capture
automatically binds native observations to its source-identity bundle. Hosts can
wrap other C API operations with `golem_record_call`. Enabled direct C callers
inspect the versioned `golem_record_last_api_outcome` immediately after automatic
boundaries: operation success and recording success are separate results.

The C execution engine already persists attempt/checkpoint/QA receipts and
contract-selected logs. Its authorization, retention/redaction policy and public
ABI are unchanged. Arbitrary shell commands, CMake/Conan hooks, and uninstrumented
processes inside CTest/fixture commands do **not** gain separate native records.
Direct CLI stream interception and automatic interposition of every C function
are not provided. A recorded parent is not proof of complete descendant
coverage. Native CLI output CAS entries are payloads, not execution transcripts.

An AST regression check inventories direct subprocess launches in owned
non-test `tools/*.py` and the benchmark collector. Only reviewed low-level process
execution, read-only Git discovery and the optional CPU-name probe are exceptions.
The check prevents ordinary new bypasses; it is not a Python security sandbox or
a proof against aliases, dynamic imports or shell execution in other languages.
Add a new execution path through the shared API and exercise its integration,
rather than expanding the exception list to make a failing test pass.

## Inspection and compatibility

Verify a single command directory without re-executing it:

```sh
python3 tools/execution_record.py /absolute/private-run/step-001
```

`integrity: PASS` means the fixed inventory and hashes match. It does not mean
the process succeeded, inputs were unchanged, tests passed or provenance is
authentic. Inspect the separate process and source observations. Missing or
corrupt records fail this check. No report text, raw logs or environment values
are copied to its concise output.

Existing capture return keys and stdout/stderr files remain available; added
record metadata is additive. The observation delta excludes the per-run record
path from semantic comparison. Source/export and instruction-bundle tooling
include the shared recorder as an explicit dependency; deployed frozen bundles
are not silently upgraded or repinned.

Benchmark workloads retain their internal timers. CLI wall-clock collection now
uses a versioned supervised timing scope that excludes source hashing and final
metadata writes, but includes capture/supervision overhead. Do not compare it
directly with the earlier uninstrumented wall-clock baseline. Recording does not
measure provider tokens, establish cost savings or improve task correctness by
itself.

## Privacy and operational limits

Exact argv, cwd, source filenames and raw child logs can contain secrets. The
recorder intentionally does not dump environment variables or guess a redaction
policy. Do not place credentials in argv or print them, and treat records as
private. No new automatic upload is added. Existing CI artifact collection must
be reviewed when it includes these directories. This change does not encrypt,
sign, rotate or prune records; operators must apply a reviewed retention policy.
Deleting an old bundle invalidates its references. Hashes are not authentication
and are not a substitute for an independent trusted collector.

## Research and design record

Reviewed 2026-10-02. The stated scopes, not entire books, were read. No source code
was copied; no published performance result is claimed for Golem.

| Primary source / reading scope | Applied decision / limitation |
| --- | --- |
| [W3C PROV-DM](https://www.w3.org/TR/prov-dm/), overview/core structures and entity/activity distinction | Separate command activities, input/output identities and derived judgments. This local JSON schema is not a claim of PROV conformance or trusted attribution. |
| [SLSA 1.2 Build Provenance](https://slsa.dev/spec/v1.2/build-provenance), model, build definition, run details and dependencies | Record actual parameters, resolved executable, invocation and byproducts; explicitly mark incomplete input knowledge. No SLSA level, signature or hermetic-build claim. |
| Chirigati, Shasha, Freire, [ReproZip, TaPP 2013](https://www.usenix.org/system/files/conference/tapp13/tapp13-final16.pdf), introduction and sections 2-3 | Automatic capture reduces reliance on manually reconstructed experiment descriptions. Ordinary capture does not trace syscalls or package dependencies; the separate explicit syscall runner adds Linux diagnostic observations, not a reproducible environment package. |
| Moreau and Groth, *Provenance: An Introduction to PROV*, Morgan & Claypool 2013, [authors' public introduction and chapter outline](https://www.provbook.org/) | Treat generation, validation and management as distinct concerns. Book text was not available here; only the public overview was consulted, with detailed data-model decisions checked against PROV-DM. |
| Beyer et al. (eds.), *Site Reliability Engineering*, O'Reilly 2016, [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/), definitions and monitoring philosophy | Keep observations interpretable and separate symptoms from causes; a recorded return code is not a semantic acceptance verdict. |

Regression tests cover normal/nonzero/signal exits, timeout/output bounds, launch
failure, pre/post-write failure, dirty/untracked changes, missing Git, executable
drift, privacy, corruption/symlinks, concurrent invocations, interrupted recording
and checked-adapter compatibility. Existing tool suites and native integration
tests remain necessary: collector unit tests alone do not establish route coverage.
