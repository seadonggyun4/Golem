# Current-agent conformance and distribution qualification

Golem coordinates the current agent through the existing C runtime and JSON CLI.
It does not need another provider process to author Markdown, edit code, observe
QA, classify failures, or finish a Work. The Python programs in `tools/` are
maintainer test tooling, not a replacement runtime or a provider dependency.

## Three distinct evidence levels

| Level | What it demonstrates | What it does not demonstrate |
| --- | --- | --- |
| `FIXTURE_CONFORMANCE` | Scripted contracts against the exact supplied CLI, including real local C build/tests | Model ability, real research quality, independent agent identity |
| `WORK_OBSERVATION` | The runtime currently validates a supplied Work's completion, source, documents and receipts | Who authored it, whether an LLM ran, or independent semantic review |
| Human-reviewed current-agent canary | The current agent's actual trajectory and bounded task outcome, linked to a Work observation | Cross-provider compatibility, benchmark improvement or global release readiness |

Never relabel a fixture as an actual agent run. `actual_agent_verified` and
`release_ready` are always false in the machine reports: the tool cannot
authenticate the author's identity or decide every release requirement. A real
canary is recorded separately with its provenance and limitations. Unknown
token usage and cost are JSON `null`, not zero.

## Installed CLI fixture checks

Prerequisites: Python 3.11+, Git at `/usr/bin/git`, a C compiler, and a built or
installed Golem executable from this source revision. Tests use disposable local
repositories, not another user's product repository. No API key is needed.

From a source checkout, using your chosen installation prefix:

```sh
mkdir -p .golem/conformance
python3 tools/verify_agent.py fixture \
  --cli /absolute/install/prefix/bin/golem \
  --cc /usr/bin/cc \
  --output .golem/conformance/installed-001
```

The output directory must not exist. Keep its parent private; the tool rejects
symlink output paths, creates the directory with mode 0700 and files with 0600,
and never overwrites a prior report. It writes `report.json`, `report.md`, and
private stdout/stderr logs. Timeout defaults to 900 seconds (allowed range
1..3600). Output monitoring stops oversized runs around a 32 MiB per-stream
limit; polling can overshoot. The tool terminates its process group on timeout,
failure during capture, or launcher exit. A child which deliberately escapes
the process group requires an OS sandbox and is outside this guarantee.

| Scenario | Executable check |
| --- | --- |
| E28-01 | Session-bound real QA FAIL, failure context, plan r2, patch, PASS, completion; retain earlier FAIL |
| E28-02 | Applicable UX/publishing documents are direct development-plan parents |
| E28-03 | Internal work omits interface documents; document-only work cannot fabricate development completion |
| E28-04 | Expired session, replacement context, adopt an already registered output, reject the old token, no duplicate revision |
| E28-05 | Source or upstream document change invalidates current completion without deleting history |
| E28-06 | Invalid QA evidence requires investigation; exhausted attempts block further work |
| E28-07 | Separate snapshots of dirty repositories preserve staged, unstaged and untracked bytes |
| E28-08 | Research prose/commands do not execute or authorize an unapproved gate |

E28-08 tests the runtime boundary, not an LLM's universal resistance to prompt
injection. E28-04 uses real CLI processes and local leases, not proof that any
particular GUI can resume itself after it has been closed. Environment/permission
and reentry route matrices remain covered by the broader Phase 21-27 suites.

A passing fixture report requires all eight named cases, no skips, unittest's
successful summary, successful process exit, an unchanged binary, and unchanged
Python/sample suite inputs. The report hashes the binary, compiler, top-level
suite and suite inputs. It does not hash every dynamically linked host dependency.
Record the compiler/toolchain and Conan lockfile separately for release review.

## Current-agent canary procedure

1. Choose one authorized small defect. Record user scope, agent/application/model
   if known, engine binary digest, host, repository revision and existing dirty
   changes. Unknown model or usage stays unknown. Do not extract secrets to prove
   that secrets were excluded.
2. Use [discovery](discovery.md) to capture allowlisted source, read actual primary
   references, reproduce the issue, and register discovery/research/scope Markdown.
   Record which excerpts were read; paper reputation is not local defect evidence.
3. Register the [stage selection](workflow.md). Keep UX/publishing only where
   applicable, with explicit non-applicability reasons otherwise.
4. Through [current-agent sessions](agent-session.md), claim/context/begin each
   required document, author it, register it, and submit its receipt. Use returned
   generations, sequences, input digests and token identities, not guessed values.
5. Review and approve the [execution contract](execution.md). Pin protected tests
   and snapshot paths before editing. The current agent performs the edit; Golem
   records the observed diff and executes the approved QA argv.
6. Preserve a real FAIL or ERROR. Classify it through [reentry](reentry.md), revise
   only affected documents, and keep the same acceptance gates for the repair.
   Environment, permission, budget and uncertain-effect failures are not permission
   to rewrite product requirements or lower thresholds.
7. Author the completion document, call [finalize and report](completion.md), and
   require current `DONE`, not merely `RECORDED`. Inspect both regression and
   fail-to-pass cases, preserved user changes and upstream links.
8. Observe the completed Work from a fresh CLI invocation:

```sh
python3 tools/verify_agent.py observe \
  --cli /absolute/install/prefix/bin/golem \
  --work /absolute/private/work \
  --selection selection \
  --output .golem/conformance/observed-001
```

Observation output must be outside the Work store. It calls only completion
`resume`; no finalization, report regeneration, lease acquisition, test dispatch
or repair is performed. The CLI may acquire its normal store lock. A missing
projection or stale completion returns `BLOCKED`/exit 1, not a manufactured PASS.
Repair the underlying condition explicitly before another observation.

Retain the private Work, Markdown, command trajectory, failure history and engine
observation. Have a reviewer distinguish agent-authored decisions from harness
bootstrap and synthetic fixtures. A single assisted canary is not a statistically
valid model comparison and must not be advertised as one.

## Clean distribution gate

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
python3 tools/verify_alpha.py
```

The alpha gate selects tracked and untracked nonignored public build inputs,
creates a clean temporary source tree, builds with warnings as errors, runs the
whole default CTest suite, installs, audits the default static C/CLI inventory,
builds an installed C consumer, and runs noop plus E28 against the installed CLI.
The clean source filter rejects symlinks, unsafe paths, hidden/private/runtime
components and unsupported file types. This is not a secret scanner: sensitive
content placed inside an otherwise legitimate source file still needs review.

The default install audit accepts the static library, CLI, public headers, CMake
package files and license notices only. Optional binding distributions have their
own existing package/consumer tests. Conan `with_cli=False` remains library-only;
do not run installed-CLI checks against that variant. Conan exports only its
explicit build-source patterns, not this documentation, private Work stores or
conformance output. The tools perform no publish, push or global installation.

The existing Linux/macOS public-alpha CI job invokes this same gate. Tests never
upload raw evidence, prompts, repository snapshots or logs as public artifacts.
Do not add upload-artifact globs over `.golem`, temporary directories, or private
project-docs. Even sanitized digests can reveal correlation; review summaries
before public release.

## Compatibility and release limits

This phase adds no C ABI or persisted runtime schema. Golem remains Alpha 0.1.0;
use the exact matching source revision and executable, not version text alone.
Conformance JSON is separately versioned as `golem.conformance.v1`. Its summaries
are observations, not importable authority, runner signatures or migration input.
Unsupported response schemas fail closed. No Work journal is auto-converted.
Use a new install prefix for upgrades and preserve old stores; downgrade is not
supported for records an older binary cannot understand.

Release review must separately record Linux/macOS, sanitizer/fuzz, Conan variants,
binding consumers, actual-agent cases and known unsupported scenarios. Missing
evidence is `NOT_RUN`, never PASS. Documents-only semantic completion remains a
separate predicate; this phase only verifies that it cannot counterfeit a
development result. Remote runners, Windows, universal agent attestation and
independent natural-language acceptance are not qualified by these checks.

For comparisons of agent-only, Markdown-only and Golem-assisted workflows, fix
tasks, model, toolchain, budgets and oracles before collecting multiple runs.
Retain failures and report fail-to-pass, pass-to-pass regression, false completion,
stale acceptance, resume success, repeated failures, unnecessary revisions and
known usage/time separately. Do not infer improved productivity from this suite.

## Research basis

- [SWE-bench, ICLR 2024](https://arxiv.org/html/2310.06770v3), task construction and
  evaluation sections: use executable fail-to-pass and regression outcomes rather
  than prose claims. This suite is not a SWE-bench run or a comparable score.
- [SWE-agent, NeurIPS 2024](https://arxiv.org/html/2405.15793v3), ACI design sections:
  explicit actions and focused feedback motivate the current-agent handoff and
  recovery checks. We do not import its agent or transfer its reported gains.
- [Site Reliability Engineering: Testing for Reliability](https://sre.google/sre-book/testing-reliability/),
  test hierarchy: distinguish deterministic integration tests, system checks and
  limited canaries. A local canary cannot replace independent operational testing.
- [Site Reliability Engineering: Release Engineering](https://sre.google/sre-book/release-engineering/),
  continuous build and packaging: test the packaged executable and identify build
  inputs. This is not a hermetic-build proof or an implementation of Google's stack.
- [AgentDojo, NeurIPS 2024](https://arxiv.org/html/2406.13352v3), threat model and
  environment design: distinguish utility from security and test untrusted tool
  data separately. E28-08 is a narrow inert-data test, not an AgentDojo evaluation.
- [SLSA provenance v1.1](https://slsa.dev/spec/v1.1/provenance), builder and resolved
  dependencies: artifact digests and authenticated build provenance are different
  assurances. Local conformance hashes are not signed SLSA attestations.
