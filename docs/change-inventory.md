# Change inventory

Execution contract **v4** adds policy-scoped HEAD/index/worktree observations to
the declared-file snapshots of v1-v3. Old receipts retain their original scope;
they do not acquire stronger guarantees on replay.

## Enable

Start from a v3 execution contract (including `log_retention` and each gate's
`execution` descriptor), set its `schema_version` to `4`, set
`snapshot_plan.schema_version` to `2`, and add `change_policy` to **each** repository:

```json
{
  "schema_version": 1,
  "protected": [
    {"kind": "EXACT", "pattern": "CMakeLists.txt"},
    {"kind": "DIR_PREFIX", "pattern": "tests"},
    {"kind": "SEGMENT_GLOB", "pattern": "**/credentials?.json"}
  ],
  "excluded": [
    {"kind": "DIR_PREFIX", "pattern": ".golem"},
    {"kind": "DIR_PREFIX", "pattern": "build"}
  ],
  "limit": {"mode": "BOUNDED", "max_changed_paths": 20}
}
```

These are illustrative exclusions, not automatically trusted defaults. Review
them against the actual project before approving the contract. Do not execute
unobserved source/test inputs from an excluded directory and claim complete input
coverage. Keep the Work store outside the source scope, or explicitly exclude
its directory, otherwise Golem's own receipts change the next observation.
Declared snapshot input paths cannot be excluded unless protection overrides that
exclusion. Their content digests and HEAD must agree with the full inventory.

Use the existing `golem execution validate` and `execution call` commands with
explicit contract approval; shell execution still needs the separate shell
approval described in [execution-boundary.md](execution-boundary.md). Changing
scope or limits changes the approved contract digest. There is no implicit policy
upgrade or automatic baseline reset. See [execution.md](execution.md) for the
prepare/finish/run/verify lifecycle.

## Semantics

| Property | Contract |
| --- | --- |
| Baseline | Checkpoint pins root device/inode, HEAD and per-path index/worktree identities. Preexisting edits are retained, not attributed to the attempt. |
| Scope | HEAD, index and filesystem path union; ignored files are included unless explicitly excluded. Root Git administrative `.git` is excluded. Empty directories are not file changes. |
| Identity | Paths are lowercase hexadecimal **raw bytes**, never trimmed or normalized. Decode only for display; do not use a lossy display string as identity. |
| Count | Per-repository unique paths whose tuple changed since the checkpoint. Staged plus unstaged changes count once. A rename counts old and new separately; no similarity inference. |
| Limit | `BOUNDED` with zero forbids changes. `UNLIMITED` omits `max_changed_paths` and removes only the policy count limit, not resource limits. |
| Protected | Matching a changed path denies, including deleted or newly added paths. Protection takes precedence over exclusion. |
| File types | Regular file bytes/executable bit and symlink target bytes; links are not followed. Unsupported special files, submodules and unmerged index fail closed. |
| Freshness | Reobserve before development submission, before QA, between gates, after QA and during live result/completion checks. QA self-mutation is an error. |
| Evidence | Checkpoint and execution snapshots are in issued CAS records. Allowed/denied policy findings are retained in CAS and indexed by `Work/change-findings/<digest>`. Read-only live checks do not publish. |

Findings receipts contain checkpoint digest, observed snapshot, per-repository
policy digest and path findings. Use the normal evidence/CAS reader to inspect
the indexed digest. A policy denial does not issue a successful development
receipt. Incomplete collection returns an error, not an `allowed` finding.
Historical receipt replay remains historical; it does not rerun commands or
assert that the workspace is still current.
An observed delta is not proof of which human or agent authored the change.
Hex-encoded paths are identities, not redaction; review findings before export.

## Matcher v1

- `EXACT`: literal, case-sensitive byte equality.
- `DIR_PREFIX`: exact directory name or a descendant separated by `/`.
- `SEGMENT_GLOB`: anchored entire path; `*` matches zero or more non-slash
  bytes, `?` one non-slash byte, and a whole-component `**` spans components.
  `a/**/b` matches `a/b` and `a/x/b`; `a/*` does not match `a/x/b`.
- Absolute paths, empty/dot/parent components and `.git` components are invalid.
  No regex, negation, character classes or escape grammar. This is **not** the
  Git ignore grammar. `pattern_hex` can replace `pattern` for byte paths.
- At most 32 protected and 32 excluded rules, 256 bytes per pattern. The matcher
  uses bounded dynamic programming, not recursive backtracking.

## Host API And Limits

`<golem/inventory.h>` exposes policy validation, capture, comparison and reply
release. Inputs are borrowed; successful replies are caller-owned and must be
released with `golem_inventory_reply_free`. Failed calls leave outputs unchanged.
Pure comparison validates structure, not the provenance of arbitrary caller JSON.
Only the execution layer ties observations to an enrolled, issued checkpoint.

v1 capture is bounded: 1024 included paths, 1024 bytes/path, 64 MiB content per
pass, 4096 filesystem visits, 64 directory levels and 60 seconds. HEAD/index
listings use bounded streaming (64 MiB each, one partial record in memory);
other Git commands retain their 16 KiB response limit. A whole `DIR_PREFIX` exclusion prunes filesystem traversal only
when no protected exact/prefix rule overlaps it. Any protected glob conservatively
disables pruning. An `EXACT` exclusion never hides directory descendants. The
no-follow walk supplies untracked/ignored entries without a redundant bounded
`ls-files --others` listing. Large tracked excluded trees no longer overflow the
adapter-sized response buffer. Included paths still have the v1 limit; this is
not unlimited large-repository support.
Pruning changes collection work, not the included-path identity or persisted v1
inventory schema. It does not approve a new policy or invalidate old baselines.
The expanded 1024-path bound is a reader/capture capacity change, not a new wire
schema. Older binaries may reject snapshots above their original 256-path bound.
The independent 1 MiB encoded inventory limit still applies; 1024 long paths are
not guaranteed to fit. The capacity regression uses real tracked files, verifies
a protected change at the bound, and rejects one additional included path.
Execution v4 additionally reserves a third of its 256 KiB record budget for the
inline snapshot. Execution v5 removes that inventory/receipt coupling using the
bounded CAS references below. Exceeding any limit fails closed; there is no
truncation or promise that every 1024-path inventory fits the 1 MiB object budget.

## Large Inventory QA: Execution v5

Use contract `schema_version: 5` and `snapshot_plan.schema_version: 3` together.
All v4 policy, approval, gate and declared-input fields remain required. Revalidate
the new contract and approve its new digest; do not rewrite an issued checkpoint.
The v1-v4 readers and inline receipt formats remain unchanged.

Each snapshot repository replaces inline `inventory` with `inventory_ref`:

```json
{"schema_version":1,"type":"golem.inventory.v1","size":123456,"digest":"<64 hex SHA256>"}
```

The digest addresses the exact compact JSON bytes in the Work CAS. Each inventory
has its own 1 MiB bound. Receipts remain at 256 KiB, their compact snapshots at one
third of that, and plans at eight repositories / 64 declared inputs per repository.
The referenced object preserves the full HEAD/index/worktree observation, policy
digest and root identity, not a summary. Capture publishes CAS dependencies before
the parent receipt; a failed attempt may leave harmless unreferenced objects.

Receipt loading verifies every reference's type, byte count and content digest.
Policy comparison resolves baseline/current objects one repository at a time and
uses the same inventory validator and protected-path/count rules as v4. Prepare,
finish, actual QA commands, result Markdown, bundle inspection and live completion
checks use this path. Read-only verification hashes a fresh observation without
publishing it; changed references mean stale evidence, never baseline adoption.
Missing or corrupt referenced evidence blocks reuse, including historical rendering.

Change-findings v2 receipts use `findings_ref` with type
`golem.change-findings-array.v1` instead of embedding the array. This object is
bounded at 8 MiB across all repositories, so a large delta cannot overflow the
small policy receipt. The reference contains the same version/size/digest fields.
Copy the transitive CAS objects when moving a Work; a receipt alone is not a backup.
Derived/redacted proof packs are not self-contained original-evidence backups.
Candidate patch-selection contracts currently remain explicitly v4-only; this
extension is the document execution/QA contract, not an implicit candidate upgrade.

### Storage Design Basis

- [Quinlan and Dorward, Venti, FAST 2002, section 3](https://www.usenix.org/legacy/events/fast02/quinlan/quinlan.pdf):
  content-addressed immutable objects and read-time fingerprint verification inform
  the reference design. Golem uses SHA-256, not Venti's historical SHA-1 choice.
- [Arpaci-Dusseau and Arpaci-Dusseau, OSTEP, Crash Consistency](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf):
  persistence ordering motivates publishing dependencies before their receipt.
  This is not a claim of transactional multi-object publication or power-loss testing.
- [Torres-Arias et al., in-toto, USENIX Security 2019](https://www.usenix.org/system/files/sec19-torres-arias.pdf):
  step-linked material/product identities inform binding QA observations to their
  source checkpoint. Hashes alone do not establish signer identity or authenticity.

Git tree/index records are incrementally assembled across arbitrary read boundaries
and parsed by a separately fuzzed, allocation-free parser. A partial final record
or failed child invalidates the entire observation; no partial result is published.
It requires a final NUL, exact metadata grammar and full object identity; rejects
embedded NULs, truncated records and nonzero/oversized index stages; and preserves
tabs/newlines in filename bytes. Parser errors leave the output unchanged.

The implementation makes two equal complete observations and checks file metadata
during reads. This is **not atomic isolation**, nor detection of all transient
change-and-restore races. The host must ensure a quiescent, privately owned source
root and preserve lease/admission boundaries. It does not monitor the whole host,
network, ACLs/xattrs, external symlink targets or excluded inputs. Case-folding
collisions are conservatively rejected for ASCII; Unicode normalization identity
is not claimed. Git filters are not executed; raw working bytes may differ from
normalized index content (for example line-ending conversion).

## Design References

These are design inputs, not proofs of Golem's correctness or measured speedups.

- [Git ls-files](https://git-scm.com/docs/git-ls-files) and
  [ls-tree](https://git-scm.com/docs/git-ls-tree): NUL records and index/tree identity.
- [Mokhov et al., Build Systems a la Carte, section 4.2.2](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf):
  hash-based dependency traces motivate rechecking observed inputs before reuse.
- [Saltzer and Schroeder, design principles](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html):
  fail-safe defaults and repeated authorization checks motivate blocking unknown
  observations and separating policy from observation. Inventory is not a sandbox.
- [Arpaci-Dusseau and Arpaci-Dusseau, OSTEP, Files and Directories, section 39.15](https://pages.cs.wisc.edu/~remzi/OSTEP/file-intro.pdf):
  distinguish symlink contents from the target object and preserve filesystem identity.
