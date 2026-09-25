# Pre-use behavioral validation

This is a bounded, local audit, not a claim that phases 30-32 are defect-free.
No production repository or provider account is needed. Integration tests create
disposable repositories, run real compilers/QA commands, and use controlled host
fixtures for agent behavior. Existing test deadlines and sanitizer failures remain
hard failures.

## Reproduce

Build an observation-enabled sanitizer configuration (requires libevent and the
normal development dependencies):

```sh
cmake -S . -B build/preflight -G Ninja -DCMAKE_BUILD_TYPE=Debug \
  -DGOLEM_ENABLE_SANITIZERS=ON -DGOLEM_BUILD_EVENT_BRIDGE=ON
cmake --build build/preflight --parallel 4
python3 tools/verify_preflight.py --build build/preflight --output /private/control/new-preflight
python3 tools/check_guard_mutations.py --output /private/control/new-mutations
```

Use a private existing parent and a new output directory. Reports contain local
paths and execution logs; do not publish them without review/redaction. On Linux,
use an appropriate private absolute output path instead of `/private/control`.
Do not edit or rebuild inputs while the collector is running. It pins its test
inputs and fails if they change. This does not make the build hermetic.

## Coverage and independent checks

The preflight matrix is the exact deduplicated union of runtime (30G), isolation
(31G core), and orchestration (32G) matrices, plus independent parser/admission
checks. Missing, duplicate, skipped, timed-out or failed cases cannot produce PASS.
Each completed group preserves a private result even if a later group fails.

| Area | Exercise | Limit |
| --- | --- | --- |
| Runtime | profile/capability, leases, worker cancellation, replay/fault fixtures | Not all thread interleavings |
| Isolation | worktree cleanup, inventory, actual QA, proof publication, candidate recovery | Host must quiesce external writers |
| Orchestration | role evidence, session fences, scoped approvals, SSE, pinned diffs, templates | Trusted-host identity is not provider authentication |
| Independent transition oracle | 9 states x 6 operations x 4 identity variants | One ticket; multi-ticket tests remain separate |
| Parser escapes | 1-12 backslash parity in keys and values; NUL/duplicate rejection | Strict local JSON subset, not all RFC inputs |
| Guard-removal experiments | epoch fence, patch content equality, approval schema version | Three curated mutants, not a coverage percentage |

The mutation tool changes only a disposable source copy. Every mutant requires a
passing baseline and a successful build. A selected assertion failure is counted
as detected; compile errors, missing tests, timeouts and crashes are not. A stale
or ambiguous mutation site fails closed. Original checkout files are never edited.

## Confirmed regressions

- The parser rejected literal backslash + `u0000` data as decoded NUL. Escape-aware
  scanning now preserves valid literals while refusing actual NUL and NUL keys.
- Candidate cancellation after host restart failed before delivering its notice:
  admission correctly retained `RECONCILE_REQUIRED`, but the controller tried an
  invalid cancel transition. It now delivers authorized cancellation under the
  new token without freeing uncertain resources. The CLI regression kills the
  host, retries cancellation, rejects old tokens, and requires claim reconciliation
  before settlement.

## Research basis

- [Lamport, Specifying Systems (2002)](https://lamport.azurewebsites.net/tla/book.html):
  specify state transitions and invariants independently of implementation.
  The table test is not a TLA+ proof.
- [Musuvathi, Qadeer and Ball, CHESS (2007)](https://www.microsoft.com/en-us/research/publication/chess-a-systematic-testing-tool-for-concurrent-software/):
  prefer reproducible schedules over stress-only evidence. Controlled restart and
  stale-token scenarios apply this principle; this suite is not a CHESS scheduler.
- [Mohan et al., OSDI 2018](https://www.usenix.org/conference/osdi18/presentation/mohan):
  bounded crash testing motivates explicit publication fault points. Process
  kills and injected syscall failures are not actual filesystem power-loss tests.
- [Mutation Testing Repository](https://mutationtesting.uni.lu/): fault-seeding
  measures test sensitivity. Three detected mutants do not imply complete testing.
- [RFC 8259, section 7](https://www.rfc-editor.org/rfc/rfc8259.html#section-7):
  escaped backslashes and Unicode escapes have different decoded semantics.

Live provider operation, actual billing, cross-platform runs not recorded here,
physical power loss, hostile same-UID containment and exhaustive fault schedules
remain separate verification work. Report the specific build and observed results,
not a blanket implementation-complete or production-ready verdict.
