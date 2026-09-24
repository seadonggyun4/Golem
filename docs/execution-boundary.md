# Verification execution boundary

Golem executes reviewed project code, not a sandbox. A contract digest is a local
host approval input, not a signature or proof of human review. Never deserialize
agent-supplied approval into the host API or automatically approve validation output.

## Contract v3

Version 3 retains v2 fields and log retention. Each gate requires `execution`:
See [the v3 template](../samples/execution/contract-v3.json); its zero digests and
placeholder paths must be replaced and reviewed. Validation alone is not approval.

```json
{"kind":"DIRECT","executable_digest":"<sha256 of argv[0]>"}
```

For a reviewed shell script:

```json
{
  "kind":"SHELL_SCRIPT",
  "executable_digest":"<sha256 of shell executable>",
  "script":"qa/verify.sh",
  "script_digest":"<sha256 of complete script>"
}
```

Use `argv: ["/absolute/shell", "/approved/root/qa/verify.sh", ...]`.
The script must be in both repository `paths` and gate `protected_paths`.
Use a regular executable path, not a symlink; resolve `/bin/sh` where necessary.
No `-c`, `-s`, login flags, implicit command-string conversion, environment
override or script path search is supported. Extra argv entries are literal
script positional parameters. Script syntax is not classified as safe: review
the entire script, sourced code and possible effects.

Both approvals are required on **each prepare and run**:

```sh
golem execution validate contract.json
# Review contract, script, arguments, cwd and effects before approving.
golem execution call WORK request.json \
  --approve-contract REVIEWED_DIGEST \
  --approve-shell-contract REVIEWED_DIGEST
```

Both digests cover the complete contract, including cwd, argv, executable/script
hashes, expected cases and limits. Changes invalidate old approval. Request JSON
cannot grant approval. C callers use `golem_execution_call_authorized` with
version-1 `golem_execution_approval`; pointers are borrowed for the call. Unknown
sizes/versions fail without changing the reply. The legacy API cannot approve shells.

Hashes are checked at preparation and dispatch. Source snapshots, protected
paths and executable hashes are checked after execution and between gates.
Changes require a reviewed contract and normal reentry/rebase, not checkpoint edits.
Historical v1/v2 receipts and Markdown remain readable. Legacy direct execution
continues; new dispatch of a commonly named shell under v1/v2 requires migration
to v3. The extra flag cannot implicitly upgrade an old contract.

## Trust and limits

- The common shell-name guard is a convenience, **not an interpreter detector**.
  Renamed binaries, interpreters, runners and compilers can run other programs
  or cause external effects. Review them and use OS isolation for hostile code.
- Checks are not descriptor-bound execution. Concurrent filesystem replacement,
  undeclared files, dynamic libraries and child effects are outside the guarantee.
  Use a trusted, quiescent workspace. Approved cwd text is not directory identity.
- Gates receive only `PATH=/usr/bin:/bin`, `LANG=C`, `LC_ALL=C`. Golem never
  PATH-searches argv[0]; the fixed PATH is for reviewed child programs.
- Timeout, lease expiry and process-group cleanup reuse supervisor. Cancellation
  tests cover its API; no new cross-process cancellation command for synchronous
  `execution call` is added. Escaped process groups are not contained.
- A started attempt without done is not automatically rerun. Mid-gate failure
  can leave an uncertain attempt. Completed duplicates return original evidence.
- v3 QA retains v2's mandatory log receipts and deterministic bundle checks.
  Bundle inspection executes nothing and does not imply product acceptance.

## Process-entry inventory

| Source | Purpose |
| --- | --- |
| `execution/runner.c` | Reviewed argv/cwd/fixed env through supervisor |
| `discovery/snapshot.c` | Fixed `/usr/bin/git`: `rev-parse HEAD`, `ls-files --stage`, `ls-tree HEAD`; literal pathspec, no pager/hooks/fsmonitor; fixed env, no global/system config |
| `workspace/git.c` | Host-authorized worktree lifecycle: fixed Git argv for config inspection, status/index/HEAD, detached add, initial read-tree, unlock and non-force remove; see [workspace contract](workspaces.md) |
| `adapter_protocol/descriptor_probe.c` | Existing host-selected capability probe |
| `daemon/worker.c` | Existing bounded worker supervision |
| `cli/daemon_worker.c` | Existing daemon worker protocol, not report execution |
| `daemon/supervisor.c` | Sole native spawn site; no automatic shell fallback |
| `daemon/resource.c` | Explicit host-owned Linux cgroup limits, supervisor launch and observed empty-scope cleanup; not automatic verification approval |
| `daemon/cgroup_exec.c` | Trusted Linux trampoline joins the preconfigured scope through inherited fd 3 before target `execve`; no shell fallback or setuid |

`execution_inventory` guards these source call sites. It is an architectural
tripwire, not proof against macros/function pointers/arbitrary C. Existing worker
and probe APIs are separate host-authorized surfaces, not verification approval.
Candidate worktree operations use this boundary through the explicit C host API;
they do not inherit verification approval or grant shell execution rights.
The [resource backend](resource-execution.md) is opt-in for managed commands;
normal QA/current-agent paths do not silently acquire OS limits. Git inventory
bulk reads use a separate bounded stream without relaxing adapter response caps.

## References

Design applications, not formal verification or standards-conformance claims:

- Saltzer and Schroeder (1975), *The Protection of Information in Computer Systems*,
  [I.A.3](https://www.cs.virginia.edu/~evans/cs551/saltzer/): fail-safe defaults and
  complete mediation motivate absent-approval rejection and dispatch rechecks.
- Ross Anderson (2020), *Security Engineering*, third edition,
  [chapter 6](https://www.cl.cam.ac.uk/archive/rja14/Papers/SEv3-ch06.pdf): application
  versus OS controls and confused-deputy risks motivate separating host authority
  from agent data. Relevant sections were examined, not the entire book.
- [OWASP OS Command Injection Defense](https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html):
  argv separation is necessary but does not authorize a program's behavior.
- Linux man-pages [posix_spawn](https://man7.org/linux/man-pages/man3/posix_spawn.3.html)
  and [execve](https://man7.org/linux/man-pages/man2/execve.2.html): explicit argv/env
  and execution semantics, not evidence of identical behavior on every OS.
