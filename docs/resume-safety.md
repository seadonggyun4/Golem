# Resume safety review and installation handoff

## Reviewed baseline

Baseline `76b6857025978be3ba8399f05bc9e1ecd1354f3a` added read-only
`resume_preflight` to native status/next. Idle boot changes and committed monotonic
rollback block misleading claim guidance; expiry and recovery are distinct;
verified completion remains DONE. Owner, sequence, token, binding, source and
publication fences remain separate authority checks. A hint grants no execution
permission and cannot discover whether external effects occurred.

Source review found that neither direct resume nor the context resume mutation
called status/next. The context adapter selected/count-checked a projection, then
called resume. Thus the field existed but was not an automatic mutation-entry
check. Regressions reproduced a new resume event on a completed Work and a live
foreign-owner rejection only at event commit. The common native call now performs
the existing preflight before preparation and rejects these two cases without
resume writes. It still permits explicit lawful recovery, never auto-resumes,
reconciles, retries effects, picks a token or migrates a Work.

Old event formats/replay and exact duplicate request semantics are unchanged.
This does not add conversation-start hooks to clients outside the engine. The
context adapter now calls status/next before projection/provider token counting,
retains both observations, and blocks on DONE, foreign live owners, review
blockers or sequence disagreement. Native checks still run after provider counting
and can reject intervening changes. Provider input preparation is not execution approval.

## Boundary coverage

The session regression fixture covers idle reboot/rollback, expiry equality,
RUNNING recovery and explicit output adoption/no-effects rejection, another live
owner, concurrent claims/resumes, a stale sequence after observation, duplicate
historical receipts, old tokens, wrong input/source, changed parents, policy denial,
corrupt/missing journals, unknown fields and completed Work without writes.
Injected boot/clock values are trusted test callbacks, not CLI overrides. They
simulate reboot/rollback; they do not constitute physical reboot testing.
Session-binding and context suites retain the enrolled v2 contract checks.

Protected-baseline tests preserve byte-change rejection and add a byte-identical
dirty-to-clean commit transition. The native runner distinguishes metadata from
byte change without relaxing object equality, contract approval or enrollment.
Discovery tests reject inherited GIT_PAGER, suppress its value, and demonstrate
read-only capture after an explicitly cleaned invocation. All fixture writes are
to disposable repositories/Works, not installed product evidence.

Local verification results are recorded below. Native support
is macOS/Linux (POSIX locks, boot identity and supervisor); Windows native runtime
is not claimed. A Windows product test/VM is outside this engine review.

The preserved baseline runtime was also used to generate three disposable
synthetic Works (idle, CLAIMED, RUNNING). The new engine read status/next without
changes, preserved all old files, and explicitly resumed them to IDLE, IDLE and
RECOVERY_REQUIRED respectively. This checks compatibility with `76b6857`, not
every historical engine version or automatic migration of installed Works.

## Verification results

Local host: macOS / arm64, 2026-10-13. All native suites used the permitted host
environment, not a restricted boot-identity/socket sandbox.

| Check | Result |
| --- | --- |
| Native session suite / observed gate | 24/24 PASS; live-owner and stale-sequence rejection, concurrent resume and DONE no-write included |
| Impact CTest selection | 45/45 PASS; affected context/execution tests rerun after final test extensions |
| Python provider-count/preflight unit suite | 10/10 PASS |
| Entire Python tool suite | 477/477 PASS |
| ASan/UBSan focused CTest | 8/8 PASS; context and execution rerun with final regression extensions |
| Release focused CTest | 4/4 PASS; execution rerun with reviewed-baseline recovery extension |
| Previous-engine synthetic compatibility | 3/3 states PASS; original files preserved |
| Clean validation source export | 605 allowlisted files; no installed project evidence included |

Local Release CLI SHA-256:
`fc19f68d34bc19bb4a8eb301a58effc89d5b2558d28c9f02f4fea306cb0ad4cf`.
This identifies the tested local artifact, not a reproducible-build or product
acceptance claim. Linux validation belongs to the exact-commit CI result and is
not inferred from local PASS. Windows native runtime, physical reboot/power-loss,
all historical engines and distributed/network filesystems were not verified.

Before the fix, the DONE regression observed a committed resume event; the live
foreign-owner case returned `session.event_commit`, and the protected metadata /
Git pager cases returned generic policy denial. Those failures motivated the
small prospective guard and diagnostic changes; no original test gate was weakened.

## Installer handoff (separate product thread)

No product engine, instruction bundle, Work, registered revision or product test
was modified by this review. Installation remains a separately approved action.

1. Quiesce cooperating writers and inventory/hash the current engine, SDK,
   instruction bundle and the explicitly reviewed Works. Preserve the old runtime
   and its installation manifest. Confirm a permitted local host with `golem doctor`.
2. Build the exact approved commit using `cmake --preset release` and
   `cmake --build --preset release`. Run relevant session/binding/context/execution/
   discovery regressions on that host before installation; do not infer Linux or
   Windows validation from a macOS build.
   Stage the native install without touching the active runtime:

   ```sh
   cmake --install build/release --prefix "$STAGING_ROOT/runtime"
   shasum -a 256 "$STAGING_ROOT/runtime/bin/golem"
   ```

   `STAGING_ROOT` must be a new owner-approved directory, not the active engine
   or a historical evidence directory. Supply the matching source SDK through
   the project's existing reviewed installation process; runtime-only staging
   does not update instruction identity or SDK contracts.
3. Stage the runtime and matching SDK in a new versioned destination using the
   project's reviewed installer. Record commit, binary SHA-256, source/runtime
   inventory and actual tests. Review instruction identity changes explicitly;
   do not auto-repin an instruction bundle or overwrite historical manifests.
4. Switch the engine only after approval. Query full native status/next read-only
   on each approved Work and compare before/after inventories. Inspect completion
   read-only for DONE; do not session-resume it. Installation readiness alone is
   not Work completion, QA acceptance or product certification.
5. For unfinished Work, inspect full preflight and original evidence. Respect
   live owners; construct explicit resume using current sequence, reviewed identity,
   TTL and, if enrolled, the exact v2 binding/token. RUNNING requires effect
   inspection and explicit reconcile before any new claim. No uncertain rerun.
6. For protected metadata changes, preserve the rejection and original baseline.
   Review byte hashes and tracked/dirty deltas separately. Use the documented
   selection revision/contract approval/new checkpoint flow; produce fresh receipts.
   This review does not authorize rebaselining any installed Work.
7. On compatibility failure, stop mutations and preserve diagnostics. If no new
   events were written, the preserved runtime can be restored only by the project
   owner after compatibility review. If new evidence/events exist, do not blindly
   downgrade or restore old state; inspect compatibility and effects first.

The installed baseline's two historical Work inventories (212 files) and SDK
manifest (741 source files plus runtime inventory) were read and hash-checked
without running recovery on those Works. They matched the retained evidence.
Private installation evidence is not copied into this public repository.
