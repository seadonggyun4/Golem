# Project Agent Entrypoints

[한국어](agent-setup.ko.md) · **English**

Golem is a document-driven work protocol for the Codex or Claude agent already
working in the project. Installing Golem does not inject project instructions or
start development automatically. Use this guide only for projects whose owner has
approved Golem-based work.

## Quick Application

1. Prepare a current CLI with [the installation guide](runtime-reference.md#conan-package).
   Check both `golem --version` and the source revision used for installation.
   Identical version strings can still hide different functionality; keep `docs/`
   and `samples/` from the same revision.
2. Append the [common rules block](../samples/agent-session/AGENTS.quickstart.md)
   to the project's existing `AGENTS.md`. Do not overwrite the existing file with
   the template. If the project uses a separate `AGENT.md`, confirm that the tool
   you use actually reads that entrypoint.
3. Append the [Claude entry block](../samples/agent-session/CLAUDE.quickstart.md)
   to the existing `CLAUDE.md`. It should reference the same-root `AGENTS.md`
   instead of duplicating all common rules. Preserve filename casing.
4. Replace the placeholders below with real paths. Create the Work root and
   exclude runtime data from Git.
5. Ask the current agent to read the entrypoint files, and state the task scope
   and Golem usage explicitly, as in the request example below. Do not rely only
   on automatic file discovery.

| Placeholder | Example value |
| --- | --- |
| `<GOLEM_EXECUTABLE>` | `/absolute/install/bin/golem` or the project's `.golem/bin/golem` |
| `<GOLEM_WORK_ROOT>` | `.golem/workspace/works` |
| `<GOLEM_DOCS_DIR>` | `/absolute/Golem/docs` or copied `.golem/sdk/<revision>/docs` |
| `<TARGET_REPOSITORIES>` | The current repository `.` or a list of real sub-repositories |

Example paths do not install anything. Point to an executable and documentation
that actually exist. Project-local `.golem/project.json` or `.golem/work.py`
files are optional local helpers, not a built-in configuration contract that
Golem automatically discovers.

From the project root:

```sh
mkdir -p .golem/workspace/works
```

Add `.golem/` to the existing `.gitignore` without duplicates. If the entrypoints
themselves are private, exclude `AGENTS.md` and `CLAUDE.md` too. Ignore rules do
not hide files already tracked by Git, so review the index separately. Do not
delete tracked files automatically. Ignore rules are not encryption or upload
access control.

## Request Example

```text
Read the Golem settings and work rules in AGENTS.md first.
Explore [target feature] in the current project and select the improvement scope.
Register the Markdown required for the selected stages and develop against it.
Record real QA results; if they fail, revise affected documents and re-check.
Verify completion conditions and leave a completion report.
Preserve existing changes and do not commit, push, or deploy.
```

## Verification

- Confirm that the chosen CLI installation includes `work`, `document`,
  `session`, `execution`, `reentry`, and `completion`.
- Run the [README registration example](../README.md#quick-start) in a fresh test
  Work and confirm that the `.md` file appears at the path you selected.
- Select real task acceptance, required stages, QA argv, protected tests, and
  permissions after discovery. Do not reuse synthetic sample output as project QA.
- On resume, inspect the existing session and Work first. Completion requires a
  current DONE backed by fresh documents, source, QA, and report.

Detailed contracts: [documents](document-registry.md), [workflow](workflow.md),
[sessions](agent-session.md), [execution](execution.md), [reentry](reentry.md),
and [completion](completion.md). Templates are collaboration instructions, not a
mandatory sandbox.
