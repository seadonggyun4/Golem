# Applying lightweight project instructions

Scope: candidate 1, installing and checking minimal startup guidance in an
explicitly selected real project. This does not make every optimization in
[agent I/O](agent-efficiency.md) complete, or prove lower model cost.

For a non-Git parent containing multiple product repositories and existing
project-specific instructions, use the separately reviewed
[workspace migration procedure](instruction-bundles.md). Do not initialize Git,
replace a pinned runtime, or pretend that parent instructions automatically load
when an agent starts directly in a child repository.

## Ownership and inputs

The project owner chooses the actual project root and approves this change.
Never treat archived experiment copies as live projects. The tool edits only
that root's `AGENTS.md` and private `.golem/entrypoints` metadata, and creates the
chosen private Work directory if absent. It does not edit CLAUDE.md, global
instructions, nested rules, Git configuration or ignore rules, install binaries,
start agents, or create a Work. Preserve other project changes.

Before using the tool, review the existing AGENTS.md, parent/nested rules and
any CLAUDE.md. Human-authored project rules outside the managed block must remain
byte-for-byte intact. This tool cannot detect semantic contradictions between
arbitrary project prose and the Golem rules. Unmarked Golem headings/placeholders
are refused rather than automatically summarized or duplicated. Review and
explicitly migrate such a section first; do not wrap unrelated rules in markers.

Use a Git root and explicitly ignore `.golem/` (review any tracked runtime files;
ignore rules do not untrack them). Keep SDK docs, samples and tools from the same
reviewed source checkout. The CLI must already exist and be executable. The
version string alone does not establish binary/source provenance.

Create `.golem-agent.json` in the selected project using real paths:

```json
{
  "schema": "golem.agent-entrypoint.v1",
  "language": "ko",
  "sdk": "/absolute/Golem",
  "cli": "/absolute/Golem/build/dev/golem",
  "work_root": ".golem/workspace/works",
  "repositories": ["."]
}
```

Language is `en` or `ko`. Paths are literal, absolute or relative to the project
root; no shell/environment expansion occurs. The SDK supplies templates and
on-demand documents. Repository entries must be unique existing Git roots.
Work must be below this project's `.golem/`, not in entrypoint metadata. There
are no credential fields. Absolute machine paths may be private: decide whether
to track or ignore the config, but never publish the private state/backup files.
This config is for this tool, not a newly discovered engine configuration format.

## Review, apply, verify

Run from the matching Golem checkout, replacing the target path explicitly:

```sh
python3 tools/agent_entrypoint.py plan --project /absolute/target
python3 tools/agent_entrypoint.py apply --project /absolute/target \
  --expected PLAN_SHA256_FROM_REVIEWED_OUTPUT
python3 tools/agent_entrypoint.py check --project /absolute/target
python3 tools/agent_entrypoint.py check --project /absolute/target --probe
```

1. `plan` is read-only. Review its full candidate, byte counts, current file hash
   and plan hash. The plan hash binds the target root, prior and resulting bytes,
   config, SDK files, renderer/helper and CLI identities. It is not authorization.
2. `apply` requires that exact reviewed plan hash. It appends one marked block or
   replaces that block only. Existing prefix/suffix bytes remain unchanged; an
   initial append adds a separating newline. Prior bytes are saved before writing.
   Repeating a fresh identical plan is a no-op: no duplicate blocks or backups.
3. `check` compares actual instructions with the deterministic rendering and
   pinned config/SDK/binary hashes. Missing files, changed safety text, external
   rule edits, overrides, or identity drift block. Never silently re-pin on startup.
4. Optional `--probe` invokes only the explicitly selected executable's
   `--version`, with bounded capture. It does not call providers, probe runtime
   permissions, run QA, or assert any Work is DONE.

The entrypoint itself contains the real `check` command and resolved project
settings. It retains mandatory permission, lease, evidence, failure and completion
rules; detailed SDK documents are looked up only when the relevant task needs
them. The managed block has a 4096-byte cap. The total file has a conservative
32768-byte cap. Exceeding a budget fails; neither user rules nor safety gates are
truncated. These are byte bounds, not tokenizer budgets or measured savings.

## Discovery and proof limits

OpenAI's documented discovery gives AGENTS.override.md precedence over AGENTS.md
at the same directory, loads instructions along the root-to-working-directory
path, and applies a combined byte budget. Therefore this tool refuses a nonempty
root override. It does not remove overrides or change user-level Codex settings.
Starting outside the target repository may not load its root file. Nested/global
rules and host configuration still require review; this is a root static check,
not a complete emulation of every agent's instruction loader.

`READY` means this entrypoint and its pinned dependencies match. Results explicitly
set `model_instruction_loading_verified: false`, `build_provenance_verified: false`,
`runtime_environment: NOT_CHECKED`, and `product_acceptance: false`. A successful
version probe changes only `cli_probe`. To verify model loading, explicitly inspect
the instruction sources in a fresh authorized agent session in the target project;
do not launch a paid/provider session automatically for this purpose.

If the project previously had no AGENTS.md, installing guidance increases startup
bytes relative to zero. Comparing a minimal template to the expanded template is
not proof of savings against that project's previous state. Assess correctness,
retrieval overhead, actual provider usage and latency together before claiming
an end-to-end improvement.

## Failure and recovery

- `STALE`: the reviewed plan no longer matches; review a new plan, do not force it.
- `UNMANAGED_GOLEM` / `MARKERS`: inspect old rules or malformed markers manually;
  never infer which prose can be deleted.
- `DRIFT` / `SDK_TOOL_MISMATCH`: inspect changed dependencies/rules and update only
  with approval. The tool/helper must match the configured SDK.
- `OVERRIDE`: review the higher-priority root file; it is never auto-deleted.
- `TRACKED_RUNTIME` / missing ignore rules: review private-state exposure first.
- `BUSY`: an exclusive apply lock exists. Check the owning process before manually
  removing an abandoned lock; there is no automatic stale-lock recovery.
- `CLI_PROBE`: inspect the installed executable/environment. Do not bypass engine
  checks or infer completion from a version string.

Before images live in `.golem/entrypoints/<sha256>.before.md`. The active binding is
`state.json`. Managed instructions publish by same-directory atomic replacement;
there is no cross-file transaction with the receipt. An interruption may leave a
new AGENTS.md without matching state: check blocks, the backup remains, and an
explicitly reviewed new plan can repair the binding. No automatic rollback deletes
intervening edits. File fsync is used for replacement, but full power-loss durability,
hostile concurrent filesystem writers and signed authenticity are not guaranteed.
Symlink/hardlink instruction files, duplicate markers and unsafe path text fail
closed. Local hash records are integrity checks, not an adversarial security boundary.

## Research rationale

Reviewed 2026-10-02. The reading scopes are stated to distinguish original research
from vendor guidance and avoid implying that whole books were read.

| Primary reference / scope read | Implementation decision and limits |
| --- | --- |
| Lulla et al., *On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents*, arXiv v1, sections 3-4 ([paper](https://arxiv.org/html/2601.20404v1)) | Paired same-task/source evaluation motivates preserving baseline identity. The study measured efficiency and performed a limited output sanity check, not comprehensive semantic correctness; its improvements are not assumed for this project. |
| *Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?*, arXiv v1, sections 4-5 ([paper](https://arxiv.org/html/2602.11988v1)) | Counterevidence against adding redundant overviews/procedures. Human guidance had different quality/cost tradeoffs from generated guidance. Python-heavy benchmarks do not establish the effect for Golem or a new target project. |
| Winters, Manshreck, Wright (eds.), *Software Engineering at Google*, O'Reilly 2020, chapter 10, reference/tutorial/landing-page sections ([book](https://abseil.io/resources/swe-book/html/ch10.html)) | A small entrypoint routes to single-source detailed contracts; executable setup and regression checks keep instructions maintained with code. |
| Manning, Raghavan, Schutze, *Introduction to Information Retrieval*, Cambridge 2008, chapter 8 introduction ([academic textbook](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-in-information-retrieval-1.html)) | Separate retrieval/effectiveness measures from resource efficiency. Byte reduction alone does not establish task success. Only the public chapter introduction was used. |
| OpenAI, *Custom instructions with AGENTS.md*, discovery/verification sections ([official documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md)) | Root placement, override detection, bounded instructions and explicit fresh-session verification. Static READY does not attest actual model loading. |

The regression suite tests both languages, real subprocess entry commands, spaces
in paths, preservation/backups, idempotency, stale plan inputs, missing dependencies,
SDK/CLI drift, overrides, private-state exclusions, byte budgets, symlinks/hardlinks,
lock contention and interrupted metadata publication. Actual target application
must be reported separately; disposable tests are not a substitute for it.
