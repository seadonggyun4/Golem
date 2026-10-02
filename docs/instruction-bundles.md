# Reviewed workspace instruction bundles

This is the explicit migration path for existing, non-Git parent workspaces with
child Git repositories. The ordinary `agent_entrypoint.py` managed-block installer
continues to handle Git-root projects. Neither installer upgrades Golem engines,
changes runtime policy, launches agents, grants permission or proves task success.

## Why a separate migration path

Existing human-authored AGENTS/CLAUDE files may contain unique product freezes,
research isolation, private-data rules and completion gates. Automatically
summarizing them or appending another generic block is unsafe. The workspace tool
accepts explicitly reviewed prose and a closed output scope instead. It never
writes child repositories, engine binaries, SDK files or project.json. All old
entrypoint bytes are backed up before either root file changes. Detailed policy
sections should be extracted without modification, with a coverage inventory;
any deliberate correction must be listed separately and justified by evidence.

Keep mandatory authority, privacy, product boundaries and completion rules at
the root. Route detailed procedures by the action that needs them, with a
mandatory read *before* that action. Unknown scope requires full relevant policy
review. A short CLAUDE pointer avoids maintaining a second policy copy. Preserve
other application-specific entrypoints and global/nested instruction discovery.
Existing higher-priority project rules must still be read, even if that reduces
the possible startup savings. A coverage hash proves byte preservation, not
semantic equivalence of the shortened root; that requires careful review.

## Manifest and commands

Keep the manifest private and outside public source exports. It has exactly:

```json
{
  "schema": "golem.instruction-bundle.v1",
  "project": "/absolute/non-git-parent",
  "repositories": ["product", "trials"],
  "cli": ".golem/bin/golem",
  "pins": {".golem/bin/golem": "LOWERCASE_SHA256"},
  "files": {
    "AGENTS.md": {"before": "LOWERCASE_SHA256", "text": "Reviewed rules\n"},
    "CLAUDE.md": {"before": "LOWERCASE_SHA256", "text": "Read AGENTS.md\n"},
    ".golem/entrypoints/bundle/policies/work.md": {
      "before": null, "text": "Exact detailed rules\n"
    }
  }
}
```

Use real hashes, not the illustrative placeholders. Pin project configuration,
the installed CLI, referenced protocol documents, wrapper and mandatory project
rules. CLI links are allowed: the plan binds both content and resolved path.
Pinning the installed binary does not establish its build provenance. Deliberate
SDK references must match the already installed integration, not this installer's
revision. There is no requirement to copy a modern SDK into an older workspace.

```sh
python3 tools/instruction_bundle.py plan --manifest /private/reviewed.json
python3 tools/instruction_bundle.py apply --manifest /private/reviewed.json \
  --expected REVIEWED_PLAN_SHA256
```

`plan` is read-only and returns the full proposed files. Its hash binds original
and proposed bytes, dependency hashes/paths and installer/helper source hashes.
`apply` requires that exact reviewed hash, preserves originals and modes, creates
private policies and a frozen local three-file checker, then publishes the receipt.
Repeating the same successful apply is read-only and idempotent. Startup uses:

```sh
python3 .golem/entrypoints/bundle/instruction_bundle.py check --project .
```

Run from the selected parent workspace. The check is read-only: no engine commands,
Work creation, capsule smoke runs, network operations or model calls. It detects
missing/changed instructions, tools, dependencies, root overrides and repository
boundaries. Its compact result explicitly leaves runtime environment, product
acceptance, actual model loading and token savings unverified.

## Safety, recovery and maintenance

- Only AGENTS.md, CLAUDE.md and files below the dedicated private policies directory
  are eligible manifest writes. Installed checker files are selected by the tool.
  Root instructions are capped at 8192 bytes each; excess is rejected, not truncated.
- Parent workspace must be outside all Git worktrees; children must be explicitly
  listed Git roots. No Git initialization/configuration or ignore editing occurs.
  Parent ignore patterns are not upload controls: private files still require
  actual package/export inventory review before any authorized publication.
- Outputs reject symlink components and hardlinked/nonregular files. An exclusive
  apply lock blocks concurrent installers; it is never automatically cleared.
- Backups are `.golem/entrypoints/bundle/<sha256>.before`. The final `state.json`
  binds root files, policies, backups, checker and read-only dependencies.
- Publication is atomic per file, not a transaction across files. Interruption
  before receipt publication leaves check BLOCKED, with original backups retained.
  Inspect all partial outputs and preserve intervening edits. Restore only reviewed
  prior bytes/modes or prepare a fresh explicit migration; never force-rebind.
- Existing installed receipts are not overwritten by a new manifest. Policy
  upgrades require an explicit migration design/review and backup of the installed
  bundle. Automatic in-place upgrades/rollback are intentionally unsupported.
- Hashes provide local integrity, not signed authenticity or protection from a
  hostile filesystem writer. Full power-loss durability is not claimed. No checker
  can prove that a model read/followed instructions, or resolve prose contradictions.

## Evaluation and references

See the primary-source reading record in [agent-entrypoint.md](agent-entrypoint.md#research-rationale).
The implementation follows the documentation layering in *Software Engineering
at Google*, chapter 10, and keeps effectiveness separate from efficiency as in
*Introduction to Information Retrieval*, chapter 8. The two AGENTS.md studies
report different empirical outcomes: no universal token or correctness benefit is
assumed. This is a controlled migration mechanism, not a replication of either study.

Report actual before/after root bytes, whether CLAUDE forces additional startup
reads, unchanged engine identity, policy coverage and check results separately.
Do not count archived full-policy bytes as startup unless they are actually read;
do not omit mandatory project rules or nested instructions from session-level cost.
Paired authorized sessions are still needed to evaluate retrieval overhead,
task success, real input/output tokens, latency and total spend. Never launch paid
agents merely to make a static installation report appear complete.

Tests cover real multi-repository-shaped temporary workspaces, executable frozen
checker use, byte-exact backups, idempotency, stale inputs, binary/path/tool/policy
drift, overrides, traversal, symlinks, Git parent rejection, interruption, locks,
invalid JSON and byte budgets. Actual deployments and their private receipts must
be reported separately from these synthetic tests.
