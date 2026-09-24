# Isolation qualification

Phase 31G qualifies the existing verification, worktree, inventory, proof and
candidate contracts. It does not grant execution permissions or create a new
authority for completion. Work journals and CAS remain authoritative.

## Automated matrix

```sh
cmake --preset bindings
cmake --build --preset bindings
python3 tools/verify_isolation.py --build build/bindings \
  --bindings build/bindings --output /absolute/private/new-validation
python3 tools/verify_alpha.py
```

The output directory must not exist and its parents must exist without symlinks.
Reports are derived, private, append-only observations. Do not upload raw logs:
they may contain local paths or compiler diagnostics. The CLI, helper binaries,
Python fixture dependencies, CMake cache and CTest definitions are hashed and
rechecked. Each required test must be present exactly once in JUnit, executed,
and successful. Missing, skipped, duplicated or interrupted tests cannot PASS.
Process cleanup denial also fails qualification, even if a launcher exited zero.

| Group | Contract |
| --- | --- |
| Git | Dirty-main preservation, linked worktree, binary changes, rename/delete, explicit unsupported inputs |
| Crash | Proof publication syscall faults, journal faults, candidate recovery and no inferred success |
| Security | Literal argv, explicit shell approval, inventory limits, mutation seeds and allocator fault cases |
| Compatibility | Historical completion fixture, QA/proof contracts, independent public headers |
| Language | Existing C ABI, Python and TypeScript validation/replay contracts |
| Installation | Clean-source build/test/install, external C consumer, installed CLI bundle/boundary/inventory/proof tests |

Python/TypeScript tests certify the existing binding surface, not new bindings
for every phase-31 API. Fault injection covers named boundaries, not every
allocation or real power loss. Git worktrees are not OS sandboxes.

CI runs the qualification on Linux and macOS in the language-bindings job.
The clean-source gate separately verifies installed binaries. Neither gate
invokes a paid provider, sets `actual_agent_verified`, nor declares a release ready.

## Current-agent observation

```sh
python3 tools/isolation_canary.py --cli build/bindings/golem --source . \
  --cc /usr/bin/cc \
  --workspace-helper build/bindings/tests/c/golem_workspace_helper \
  --output /absolute/private/new-canary
```

Use a trusted checkout and built fixture helper. This interactive developer tool
creates a disposable synthetic Git repository and a Golem-owned detached
worktree. Its host callback authorizes that fixture only; it is not production
enrollment. It never launches an agent, supplies a repair, or contacts a provider.

1. Read the reported failed QA and candidate source.
2. Write plain paragraphs to the requested `revision.md`, without extra headings.
3. Enter `PLAN`. Golem registers an immutable development-plan revision and pins
   execution inputs before any repair.
4. The current agent/operator edits only the candidate's `logic.c`.
5. Enter `VERIFY`. Real compilation and pinned assertions run; completion and
   proof rendering/publication require a new PASS receipt. The old FAIL Markdown
   and main-repository user changes must remain unchanged.

The observation keeps workspace, failure, decision, success and proof references.
Synthetic discovery/planning scaffolding is explicitly not independent research.
`actual_agent_verified=false` means identity is not externally attested, even when
a current agent visibly performs the edit. Do not substitute this small exercise
for a provider efficacy study. Interruptions keep evidence and require a new
output directory; the tool does not replay side effects automatically. Active
claims expire after five minutes. Review cost/permissions before any separate
provider invocation; no subscription usage is authorized by this tool.

## Source and package boundary

`source_policy.py` is shared by the clean-source gate and Conan recipe. Data
fixtures have exact reviewed paths, not extension-wide JSON/Markdown inclusion.
Hidden/private directories, ignored files, symlinks and build/runtime outputs
are excluded or rejected. `src/workspace` is an explicit public module exception,
not permission to export arbitrary directories named `workspace`. Git environment
overrides are removed during inventory collection. Existing destination files
are never overwritten.

New fixtures require a deliberate policy update and tests. The source root must
be quiescent and trusted: path filtering is not a semantic secret scanner. Review
code and license assets before publishing. A local Conan create/install test and
each supported platform's CI results are separate evidence, not inferred from
successful CMake installation.

## Research basis

- [OSTEP, Crash Consistency: FSCK and Journaling](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf), section 42.3: separate transaction data, commit and recovery. Applied to publication-boundary tests, not a claim of filesystem certification.
- [Pillai et al., All File Systems Are Not Created Equal, OSDI 2014](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-pillai.pdf): persistence behavior depends on filesystem assumptions. Syscall injection does not prove power-loss durability.
- [SWE-bench](https://arxiv.org/html/2310.06770v3), evaluation appendix: both formerly failing and regression tests must be present and pass. Applied to exact test inventories and the two-case canary; this is not a SWE-bench result.
- [in-toto, USENIX Security 2019](https://www.usenix.org/system/files/sec19-torres-arias.pdf), sections 3.3 and 4: check artifact flow and the required steps, not only final bytes. Applied to dependency hashes and installed consumers; these unsigned reports are not in-toto attestations.
