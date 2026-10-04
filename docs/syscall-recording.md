# Explicit syscall diagnostics

`tools/syscall_record.py` launches a **new, explicitly requested** Linux command
under an installed trusted strace with `--kill-on-exit` support (introduced in
[6.6](https://lists.strace.io/pipermail/strace-devel/2023-October/011369.html)).
Actual capability is probed rather than inferred from the version string.
It never attaches to existing processes,
installs a tracer, invokes sudo, changes ptrace policy, or retries the target.
Ordinary CLI/C API recording does not silently enable this higher-overhead mode.

```sh
python3 tools/syscall_record.py --destination /private/output/new-trace \
  --timeout 30 --limit 33554432 -- /absolute/path/to/command argument
```

The destination must not exist and must have no symlink ancestor. It is created
0700; capture files are 0600. On Linux choose an available real path, not the
illustrative `/private/output` directory. `--cwd` and `--source` are optional;
`--strace` explicitly selects a trusted backend binary. The runner prints only
state, diagnostic, target-attempt flag and evidence path. Inspect `trace.json`,
`probe/` and `run/` for raw records. The common recorder verifies the run:

```sh
python3 tools/execution_record.py /private/output/new-trace/run
```

## Lifecycle and evidence

1. Record platform, target identity and backend identity without recording the
   environment. Unsupported platform/backend returns an explicit diagnostic.
2. Run only `/bin/true` with the exact tracing flags to test options and local
   ptrace permission. Keep its stdout/stderr, syscall log and execution evidence.
   Probe failure blocks the target. It does not establish future permission.
3. Recheck backend identity, then attempt the target exactly once. `-f` follows
   traced forks/clones; `--kill-on-exit` requests kernel EXITKILL on tracees.
   No attach, detached tracer, filter injection or user-provided tracing options.
4. `raw=all` avoids decoding pointed-to strings/buffers; signal decoding is off.
   Keep tracer output in `syscalls.log`, separately from target stdout/stderr.
   The native unsigned record still contains the supplied argv; secrets in argv
   or stdout/stderr are not redacted. Numeric arguments/addresses can be sensitive.
5. Apply the common timeout/process-group cleanup and per-file output limits to
   all three logs; hash/fsync the syscall log into the same manifest. The polling
   size limit is a soft bound with possible overshoot, not a disk quota.

`OBSERVED` means the tracer exited and produced observations. It does **not** mean
the target succeeded, every syscall was captured, all descendants completed, or
all effects were authorized. Keep `process.returncode`, `process.reason`, native
record outcomes and `coverage` separate. Timeout/limit gives `INCOMPLETE`; failed
preflight gives `BLOCKED`; macOS/missing backend gives `UNSUPPORTED`. Never fall
back to an untraced execution. Publication failure leaves partial execution
evidence and an error exit rather than inventing a successful final report.

## Trust and limits

strace changes scheduling and overhead; do not compare its timings with an
untraced production baseline. Kernel/container/Yama policy and privilege
transitions can limit tracing. EXITKILL protects traced tasks, not external
services or tasks the kernel never allowed tracing. User-space/vDSO operations
need not issue syscalls. The probe and executable hashes do not close TOCTOU.

This is diagnostic evidence from a trusted local backend, not a security sandbox,
signed audit log, dependency packager, portable replay engine or C-function-call
tracer. A malicious same-user target can interfere with evidence. Do not parse
raw trace text as authoritative commands or authorization. The native parent
TLS collector is deliberately not populated from child text.

macOS syscall tracing is not implemented. No attempt is made to disable platform
protection or install privileged tracing infrastructure. This is an explicit
unsupported platform, not a successful empty trace.

## Research-to-code decisions

Reviewed on 2026-10-04; only the specified publicly accessible sections are claimed.

| Primary source | Applied decision |
| --- | --- |
| Kerrisk, *The Linux Programming Interface*, [Listing 3-3](https://man7.org/tlpi/code/online/dist/lib/error_functions.c.html) | Preserve errno across diagnostic formatting/cleanup. Use saved syscall errno, not stale errno on semantic failures. Public companion listing reviewed, not a claim of reading the entire book. |
| Anderson, *Security Engineering*, third edition, [chapter 6, sections 6.1-6.2](https://www.cl.cam.ac.uk/archive/rja14/Papers/SEv3-ch06.pdf) | Treat process permissions and audit-write authority separately. Private same-user files and hashes are useful integrity observations, not independently protected or authenticated audit evidence. |
| Chirigati et al., [ReproZip, TaPP 2013](https://www.usenix.org/system/files/conference/tapp13/tapp13-final16.pdf), sections 1-3 | API observations alone cannot describe descendant OS interactions. Add an explicit tracing backend but do not claim dependency packaging or reproducibility from a raw trace. |
| Yuan et al., [OSDI 2014 failure analysis](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf), section 4 | Test failure handlers and their state effects: cancelled work, durable journal append, cleanup after primary error, unavailable tracer and escaped-session timeout. Published failure percentages are not Golem effectiveness estimates. |
| [strace manual](https://man7.org/linux/man-pages/man1/strace.1.html), tracing/raw/output sections | Reuse mature process following and syscall ABI decoding; explicit probe, raw arguments, separate output and kill-on-exit. |
| [ptrace manual](https://man7.org/linux/man-pages/man2/ptrace.2.html), EXITKILL and fork/clone options | Distinguish traced-task cleanup from process-group cleanup; do not imply control over untraced services or kernel-denied tasks. |

## Tests and supported claims

Portable `test_syscall_record` checks unsupported/probe-failed no-launch and
operation/observation separation using mocks. `test_execution_record` checks the
real additional-log limit and manifest tamper detection. These are not ptrace tests.

`python3 tools/test_syscall_record.py --linux-integration` requires real Linux and
strace; it fails rather than skips when unavailable. It verifies descendant
ENOENT observations and timeout cleanup of a child that calls setsid. The separate
Ubuntu 24.04 CI job installs strace and preserves evidence even on failure.
Adding that job is not evidence it has run or passed.

Native tests cover all 68 automatic boundaries on rejected/null-release calls,
real runtime cancellation and durable journal append with broken audit storage,
record-enabled runtime progression, clock failures, document scan cleanup and
cgroup membership/exec error branches. Mocked cgroup tests do not prove Linux
kernel resource enforcement; the existing Linux resource fixture remains required.
