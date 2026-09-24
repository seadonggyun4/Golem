# Isolated candidate workspaces

For group budgets, parallel admission and result comparison, see
[bounded isolated candidates](candidates.md). Workspace lifecycle remains a
separate component; neither API automatically dispatches agents.

`golem_workspace_call` in [workspace.h](../include/golem/workspace.h) manages
opt-in Git worktrees for a Work. This is a **C host API**, not a new automatic
agent dispatcher or an OS sandbox. No CLI approval shortcut is provided.

## Host integration

The host supplies a version-1 `golem_workspace_host`, registered repository ID,
canonical main-repository path and existing private worktree root. The normal
root is `<project>/.golem/worktrees`; an external root is allowed only by the
same trusted host registration. Do not build this authority from agent JSON.

The host must hold repository-wide session/global admission throughout the call.
`check` revalidates policy and the candidate's permission before Git commands.
`pulse` supplies bounded heartbeat/cancellation checks during supervision.
SEAL, RETAIN and REMOVE also require observed worker termination. Neither a
candidate state nor a Work store lock proves process termination. The existing
admission dispatcher can own this call as its execute operation; its publisher,
lease guard and termination proof remain the host's responsibility. A callback
that always returns OK is suitable only for isolated tests, not production.

All borrowed inputs last for the call. The caller owns the value-only result;
failures leave it unchanged. Use an exclusive writable Work store. No allocation
escapes through the result. Root/candidate identifiers and directory device/inode
identities are pinned in durable registration. A replaced or moved root is denied;
there is no implicit migration or prefix-based containment check.

Integration outline (callbacks below belong to your existing trusted coordinator):

```c
golem_workspace_host host = {
    .struct_size = sizeof(host), .version = 1,
    .repository_id = registered_repository_id,
    .repository_root = canonical_repository_root,
    .worktree_root = registered_worktree_root,
    .check = check_policy_admission_and_worker_state,
    .pulse = heartbeat_and_check_cancellation,
    .context = coordinator
};
golem_workspace_result result;
golem_status status = golem_workspace_call(work_store, &host,
    GOLEM_WORKSPACE_CREATE, "candidate-1", reviewed_commit_oid,
    NULL, &result, &diagnostic);
/* On success, require READY before handing result.path to an executor.
 * After failure/restart reopen the Work and use RESUME, not CREATE again. */
```

On RESUME pass NULL for the commit and evidence parameters. ATTENTION is a
successful inspection of an uncertain operation, not a ready-to-execute result.
Do not treat `status == GOLEM_OK` alone as permission to dispatch an agent.

## Lifecycle

| Operation | Preconditions / result |
| --- | --- |
| CREATE | Explicit full 40/64-character lowercase commit OID; absent candidate; durable CREATING intent, detached locked worktree, verified metadata, READY receipt |
| RESUME | Verifies ledger, registration, ownership and Git backlinks; READY/ACTIVE/SEALED/RETAINED retain their states; interrupted creation/removal returns ATTENTION without repeating effects |
| ACTIVATE | READY to ACTIVE, fresh host permission; does not grant or renew a lease |
| SEAL | ACTIVE to SEALED, host proves workers stopped; not an immutable filesystem snapshot |
| RETAIN | SEALED to RETAINED, verifies an explicit evidence digest already in the Work CAS |
| REMOVE | RETAINED only, explicit host authorization; clean index/worktree including ignored and untracked files, unchanged base HEAD; removal intent followed by non-force Git remove |

The path is `<registered-root>/<work-id>/<candidate-id>`. IDs use ASCII letters,
digits, `_` and `-`, length 1..64. Mutable branch names, absolute candidate paths,
dot components, symlink roots and canonical-path aliases are rejected.

Creation records the main workspace dirty flag and raw NUL-delimited status in
the private Work CAS. It copies no pending changes and never stashes, resets,
commits or merges the main workspace. Review filenames before exporting this
private evidence. Partial creation is preserved; do not recursively delete it.

Only a successful invocation of `git worktree add --detach --no-checkout --lock`
may establish the random owner nonce and metadata binding. A crash before READY
does not authorize adopting an existing directory, even if Git recognizes it.
Recovery inspects the durable intent and returns ATTENTION for operator review.

## Git effects and cleanup

Git is invoked as `/usr/bin/git` with explicit argv through the existing
supervisor. No shell string, inherited Git environment or user/system Git config
is used. Hooks, fsmonitor, automatic maintenance, recursive submodules and
protocol access are disabled. Effective local configuration is inspected before
effects: filter drivers (including LFS), partial clones, worktree config and
sparse checkout are refused. This conservative implementation does not approve
arbitrary checkout filters. Repositories requiring them need a separately
reviewed policy extension. Submodules are never initialized and LFS is not fetched.

Cleanup verifies the directory identities, `.git`/`gitdir`/`commondir` backlinks,
nonce and Git lock. It rejects hidden index modes (`assume-unchanged`,
`skip-worktree`), modified files, ignored files, untracked files and new commits.
Changed candidates are deliberately preserved, even when RETAINED: a generic
evidence digest does not prove a complete change export. No force remove, reset,
prune, branch deletion or CAS deletion is performed. A failed or interrupted
unlock/remove is ATTENTION, not permission for a second removal attempt.

An independent descriptor-relative, no-follow filesystem scan precedes removal
intent. Git status alone is not a complete filesystem inventory: FIFOs, sockets,
devices and empty directories are rejected and preserved, even with clean Git
status. Rejection leaves the candidate RETAINED. The scan is bounded to 4096
entries and 64 directory levels, checks host cancellation/heartbeat per entry,
and detects observed inode/type replacement. Ordinary tracked directories remain
removable. This check still requires the host to quiesce writers; it does not
close every check-to-delete race against a concurrent same-user adversary.

## Persistence and limits

`workspace-repositories/` holds immutable host registrations.
`workspaces/<candidate>/0001` through `0007` reference versioned CAS receipts with
sequence and predecessor digests. The Work's existing exclusive lock serializes
writers; CAS and receipt publication use existing no-replace/fsync primitives.
This ledger is separate from document acceptance events and completion verdicts.
It detects missing interior records and digest mismatches, not adversarial
deletion of an entire unanchored suffix. It is not a signature.

Git metadata and the Golem ledger are not one filesystem transaction. Process
crash boundaries are tested; power-cut durability across every filesystem is
not established. Quiescent trusted roots/config are required: concurrent
same-user path/config replacement is not contained. Git output is bounded at
16 KiB per stream; overflow fails closed, including large status/index listings.
Full change inventories, relocation migration, changed-candidate proof export,
operator repair, CLI/current-agent automatic wiring and parallel candidate
execution are not implemented by this module.

## Design references

- [Git worktree manual](https://git-scm.com/docs/git-worktree): detached creation,
  locking, metadata links and non-force removal shape the lifecycle boundaries.
- [Git attributes](https://git-scm.com/docs/gitattributes) and
  [Pro Git, Git Configuration](https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration):
  repository-local configuration can affect checkout; fixed environment alone
  is insufficient, so configured filters are denied rather than silently trusted.
- Pillai et al., [OSDI 2014](https://www.usenix.org/conference/osdi14/technical-sessions/presentation/pillai):
  persistence assumptions vary; durable intent and conservative recovery are
  used without claiming universal power-failure correctness.
- Arpaci-Dusseau and Arpaci-Dusseau,
  [OSTEP, Crash Consistency: FSCK and Journaling](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf):
  intent-before-effect and ordered receipts separate committed state from
  uncertain external effects.
- Saltzer and Schroeder,
  [The Protection of Information in Computer Systems](https://web.mit.edu/Saltzer/www/publications/protection/):
  fail-safe defaults and complete mediation motivate refusal on unknown ownership
  and repeated host permission checks. These are design applications, not proofs.
