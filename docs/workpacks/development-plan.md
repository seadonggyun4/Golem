# Gate review, security and conformance plan

## Gate A review

Reviewed baseline f2563f5 in the user-selected Golem checkout. Initial worktree clean;
fast-forwarded four existing origin commits without replacing user changes. Existing
installed client runtime/policies are separate immutable snapshots and remain unchanged.
Existing common JSON parser rejects duplicate keys/invalid UTF-8/NUL/trailing tokens;
reuse it and `golem_digest_bytes`. Pack v0 is intentionally narrower than future role,
Evidence and binding objects. No persisted format or reducer change is needed for M1.

Consistency review: structural validity is never grant/readiness/DONE; exact bytes are
not canonical semantic JSON; range declarations are not runtime compatibility; a pack
is not a proof pack/template/plugin; Truthound has no release capability in the observed
three-tool inventory; installed MCP remains unchanged. All future effects are labelled
planned. M1 may proceed without an owner-policy decision. Native mutation M4 requires
an explicit design gate first. No broad delegated approval is introduced.

## Milestones

| Stage | Files / public contract | Persistence / rollback / acceptance |
| --- | --- | --- |
| M0 | docs/workpacks; source audit and terminology | Documentation only. Gate A consistency reviewed; revert docs only |
| M1 | include/golem/workpack.h, src/workpack, samples/workpacks, tests/c, fuzz | Pure bounded byte validator, additive API; no migration. Valid/invalid fixtures, failure output invariance, installed C consumer and mutation smoke must pass. Revert additive code before any binding exists |
| M2 | src/cli/workpack.c, src/workpack/read.c and native inspect/compatibility API | Implemented: bounded no-follow snapshot, deterministic JSON; no Work writes or migration. Path/race/lock/CLI/numeric-version tests; remove additive CLI/API before any binding exists |
| M3 | native static catalog/search | No central service. Deterministic ranking, ambiguity/duplicate/version tests; owner-selected catalog only. Implemented; results below |
| M4 | native binding/resolve, immutable reference and receipt schema | Implemented native-documents-v1 after owner design selection; immutable CAS/event binding, old-reader rejection, exact approval and generation. Session/custom/external mappings block; no automatic rollback or existing Work migration |
| M5 | native document role evaluation and proposal parser | Implemented within existing native-documents-v1 binding; separate untrusted claims and native evaluation, exact current evidence; no new identity, persisted event or model truth. General/independent mappings remain unsupported |
| M6 | Evidence manifest/export/verify | Implemented native-documents-v1 closure only; separate exact private export approval, bounded typed inventory, unsigned anchored verification; retained partial exports, no auto retry. General evidence adapters remain unsupported |
| M7 | Truthound Local capture adapter and native document scenario | Implemented limited non-authoritative observation bridge; mock/native/actual stdio tests separate. No general external-role binding, authoritative release predicate or MCP route |

Non-goals at every milestone: scheduler, merge broker, hosted service, model/provider
configuration, billing, license change, repository split and client marketplace migration.
Risks: adding public API requires binding/version/export inventory review; coarse schema
names must not be mistaken for existing capability grants; schema validation cannot
predict availability. M1 has no path API, so filesystem safety is not implemented by it.

## Threat model and test matrix

| Threat / negative case | M1 disposition / later test gate |
| --- | --- |
| oversized/malformed/YAML/non-object/trailing data/deep JSON | reject bounded strict JSON; fixture and mutation smoke |
| duplicate/escaped duplicate keys, NUL, bad UTF-8 | shared parser rejection; regression cases |
| unknown schema/extensions/fields/executable/provider/path declaration | closed manifest, fail with static diagnostic |
| ambiguous Unicode ID, traversal IDs, empty/duplicate IDs, invalid version/latest | ASCII identity grammar, exact version parser, duplicate arrays reject |
| untrusted descriptions/instruction injection/hidden network | inert bounded data, no dispatch API; no semantic sanitization claim |
| pack substitution/digest mismatch/canonical ambiguity | exact-byte digest tested; M4 compares reviewed digest and immutable source |
| symlink escape/racy file/duplicate catalog ID | no filesystem API in M1; M2/M3 tests mandatory before support |
| capability escalation/prohibited effect/unavailable tool/owner denial | declarations only in M1; M4 intersection denial tests required |
| self-approval/forged identity/foreign owner/duplicate worker | no claims in M1; M4/M5 existing native ownership/SOD tests |
| stale parent/evidence/verifier, interrupted Work/unknown effects | M4/M5 reject, preserve uncertainty; never retry effects |
| downgrade/rollback/unsupported core/replay historical binding | M2 reports compatibility; M4 exact historical pin, no migration |
| malicious verifier/disagreement/reasoning leakage | M5 bounded proposal and provenance; raw reasoning never required |
| forged receipt/missing objects/truncation/projection tampering | M6 integrity tests; unsigned provenance never authenticated |
| Korean/English positive-negative discovery/ties | M3 deterministic corpus; no embedding APIs |

M1 tests must compare output unchanged on failure, stable same-byte digest and distinct
reformatted digest; sizes/counts at and above bounds; invalid semantic versions and
range reversal; required/unknown fields; meaningful text; non-ASCII identity; full
reference fixture. Fuzz target uses public API only and deterministic mutation smoke;
coverage-guided runs are separate evidence, not implied by smoke. An installed consumer
must link only the exported C header/library. Existing native regressions remain enabled.
M1's schema draft has extra semantic constraints beyond JSON Schema; native validator
is canonical, schema text is a discovery aid and cannot grant authority.

## M1 execution record (historical, d3fc00b)

Gate A documentation committed before implementation as `c156576`. M1 now implements
`golem_workpack_validate` in `src/workpack/model.c`, with the additive installed header,
closed JSON Schema discovery aid, reference sample, seven invalid fixture files,
source-contract metadata, CTest cases and a public-API mutation/fuzz target. No existing
parser, reducer or persisted format changed. M2–M7 remain NOT_IMPLEMENTED, not merely NOT_RUN.
No unresolved policy choice blocks the pure validator. Before M4, decide binding event
schema/version compatibility, trusted role mapping, precise ceiling vocabulary and
independent identity evidence. No default owner policy is invented here.


### M1 verification, 2026-11-02 (macOS local)

| Check | Observed result |
| --- | --- |
| Debug native build, warnings as errors | PASS |
| Work Pack CTest subset, standalone header and seed/mutation prerequisite | 11/11 PASS |
| ASan + UBSan same subset | 11/11 PASS; initially header target was not built, then built and checked |
| Installed public C consumer | 1/1 PASS; exported header/library only |
| Full native/CLI/fixture regression | 414/415 PASS initially; existing diagnostic_tools exceeded its 120s limit. Unchanged binary/test/limit passed standalone in 60.32s; no unresolved failing test. Timeout cause is not established |
| M0 capability unit regression | 371 tests: 369 initially passed, two found missing new effect-review records; records added, both affected modules (25 tests) PASS |
| Full static inventory | PASS: 448 source surfaces, 345 public declarations, zero blockers. This is inventory, not execution/MCP delivery certification |
| Relative document links and source-contract sample digest | PASS |
| diff whitespace | PASS |

The first full attempt under the workspace sandbox encountered sysctl/Unix-socket
permission denials and was stopped. The host run uses temporary fixtures, not real
client Works. Initial failure/timeout logs are retained in the local validation record;
no test condition, authority check or timeout was weakened. Work Pack validation has
no MCP/CLI route, even though the existing delivery backlog remains reconciled. Its
new native-only capabilities are explicitly recorded separately in the M0 ledger.

Commands (from repository root):
```sh
cmake -S . -B build/workpack-m1 -G Ninja -DCMAKE_BUILD_TYPE=Debug -DGOLEM_WARNINGS_AS_ERRORS=ON
cmake --build build/workpack-m1 -j6
ctest --test-dir build/workpack-m1 -j6 --output-on-failure
ctest --test-dir build/workpack-m1 -R '^diagnostic_tools$' --output-on-failure
cmake -S . -B build/workpack-m1-asan -G Ninja -DCMAKE_BUILD_TYPE=Debug -DGOLEM_ENABLE_SANITIZERS=ON
cmake --build build/workpack-m1-asan --target golem_test_workpack golem_header_workpack golem_mutate_workpack golem_fuzz_seeds
ctest --test-dir build/workpack-m1-asan -R 'workpack|fuzz_seeds' --output-on-failure
cmake --install build/workpack-m1 --prefix "$PWD/build/workpack-m1-install"
cmake -S tests/consumer -B build/workpack-m1-consumer -G Ninja -DCMAKE_PREFIX_PATH="$PWD/build/workpack-m1-install"
cmake --build build/workpack-m1-consumer
ctest --test-dir build/workpack-m1-consumer --output-on-failure
python3 -m unittest discover -s tools -p 'test_capability_*.py'
(cd tools && python3 -m unittest test_capability_boundaries test_capability_inventory)
python3 tools/capability_check.py --root "$PWD" --repository-sources
```

NOT_RUN: real Codex/Claude Work calls, Truthound dataset calls, remote services,
coverage-guided libFuzzer campaign, Linux/Windows builds, Conan distribution and client
installation updates. The implemented fuzz target was exercised by deterministic
mutation smoke and sanitizers; this is not exhaustive fuzz coverage. M2–M7 are
NOT_IMPLEMENTED, including CLI inspect/compatibility, catalog, binding, semantic role
processing and portable receipt validation. They are not merely untested features.

Client preservation was checked against the existing installation review: Codex 0.2.7
(9 package files), Claude prepare 0.1.15 (85 package files), shared runtime (85 files),
launcher and D2 hashes match. One Golem installation per client remains enabled.
The installed runtime stays at its reviewed f2563f5 source identity. No new Work Pack
code is installed in either client; no TopSolar policy/approval/Work/evidence operation
was issued. Local logs and preservation details live outside the source checkout in
`../workpack-m1-validation-20261102/` and are not public package contents.


## M2 implementation record (before M3)

`pack validate`, `pack inspect`, `pack compatibility` are implemented as thin native C
CLI handlers. The existing M1 validator and numeric version parser are reused; the
new public read API reuses `golem_evidence_path_open`. Source-contract metadata now
lists these three local CLI routes and all four native APIs. MCP and language bindings
remain empty/NOT_IMPLEMENTED, with no installed producer/policy changes.

New tests cover full manifests and exact raw digest, deterministic JSON, explicit and
compiled Core version, inclusive/numeric interval endpoints, invalid versions, malformed
input, 64KiB boundary, symlink parents/leaf, traversal, hardlinks, FIFO, directory,
missing input, lock contention and no automatic output-store writes. Native injected
read fixtures deterministically modify and replace the file mid-read; both fail stale
without changing caller outputs. Inspect buffer sizing and failure output invariance
are checked. The fuzz target additionally exercises inspect and compatibility.

M2 retains the existing 0/1/2 exit taxonomy. Incompatibility is a completed false
comparison, not parser failure or runtime availability. Optional pre-existing command
recording is preserved; Work state is never touched by these handlers. No client
installation, policy pin, role binding, owner action, provider or service is changed.
M3–M7 remain NOT_IMPLEMENTED, not merely NOT_RUN. No new policy choice is required
for this explicit local read-only CLI; future binding still requires M4 review.

### M2 verification (2026-11-02)

| Check | Result |
| --- | --- |
| Debug build, warnings as errors | PASS |
| Full native/CLI regression (`ctest --test-dir build/workpack-m1 -j4 --output-on-failure`) | 417/417 PASS |
| Work Pack targeted fixtures | 13/13 PASS |
| ASan/UBSan Work Pack fixtures and mutation smoke | 13/13 PASS |
| Installed public API consumer | 1/1 PASS |
| Capability regression | Initial 370/371; missing `pack` documentation entry corrected, affected 16/16 PASS |
| Strict repository capability inventory | 450 source surfaces, 348 public declarations, zero blockers |
| Diff whitespace, source-contract and documentation links | PASS |

No checker, approval rule or regression timeout was weakened. The capability test's
initial failure exposed an outdated root CLI documentation list, which now includes
`pack`; the test itself is unchanged.

NOT_RUN: real client/Work E2E, provider/Truthound calls, coverage-guided libFuzzer
campaign, Linux/Windows builds, Conan distribution and client installation updates.
Compatibility checks only the declared numeric interval, not installed MCP delivery
or runtime availability. M3–M7 remain NOT_IMPLEMENTED.

The existing Codex 0.2.7 package (9 files), Claude prepare 0.1.15 package (85 files),
shared runtime (85 files), policy and launcher pins are checked against the installation
review. The installed runtime remains f2563f5; this native CLI change is not installed
in either client. No TopSolar/Work action or approval issuance was performed. Detailed
local logs, including initial failures, are retained outside the checkout in
`../workpack-m2-validation-20261102/`.

## M3 implementation record (before M4) (2026-11-02)

Native `golem_workpack_catalog` and CLI `pack list --catalog INDEX` /
`pack search QUERY --catalog INDEX` implement explicit local discovery. They reuse M1
manifest/version validation and the M2 snapshot reader; the reader's bounded internal
helper now accepts the index's 1 MiB ceiling while the public manifest reader retains
its 64 KiB contract. No Python runtime/reducer or client configuration is introduced.

Fixtures cover Korean/English positive/negative queries, deduplicated tokens, ties,
no-match, numeric version sorting, order independence, metadata/digest drift, duplicate
index entries, unknown keys, query/entry/byte bounds, invalid UTF-8, locking, symlinks,
traversal and no output-store publication. Native tests cover output sizing/invariance
and injected index mutation. Results are observations only; M4–M7 remain NOT_IMPLEMENTED.

### M3 verification results

| Check | Result |
| --- | --- |
| Debug build with warnings as errors | PASS |
| Work Pack native/CLI fixtures and mutation smoke | 14/14 PASS |
| ASan/UBSan same subset (including 1 MiB/256-entry boundaries) | 14/14 PASS |
| Installed public API consumer | 1/1 PASS |
| Full native/CLI regression | Initially 416/418 PASS; both interrupted tests passed isolated recheck |
| Capability regression | Initially 370/371 PASS; corrected native registry module 5/5 PASS |
| Strict static inventory | 451 source surfaces, 349 public declarations, zero blockers |
| Current source pins, documentation links and whitespace | PASS |

The initial full regression hit `candidate_diff_integration`'s unchanged 180-second
limit while several checks ran concurrently. Isolated recheck passed in 97.79 seconds.
`orchestration_benchmark` correctly rejected an input binary changed by the diagnostic
message rebuild during measurement; after freezing source/binaries it passed in
58.01 seconds. No timeout, input-change guard or test assertion was relaxed.
The first capability run detected incorrectly edited existing native registry hashes;
those original pins were restored, the affected five tests passed, and the final
repository-wide static reconciliation has no blockers. An earlier artifact refresh
also rejected concurrent inventory edits; final artifacts use stable verified bytes.
Initial failure logs are retained, not replaced with only successful runs.

Representative verification commands:

```sh
cmake --build build/workpack-m1 -j6
ctest --test-dir build/workpack-m1 -R 'workpack|fuzz_seeds' --output-on-failure
ctest --test-dir build/workpack-m1 -j4 --output-on-failure
ctest --test-dir build/workpack-m1 -j1 -R '^(candidate_diff_integration|orchestration_benchmark)$' --output-on-failure
cmake --build build/workpack-m1-asan -j6
ctest --test-dir build/workpack-m1-asan -R 'workpack|fuzz_seeds' --output-on-failure
python3 -m unittest discover -s tools -p 'test_capability_*.py'
python3 -m unittest discover -s tools -p 'test_capability_native.py'
python3 tools/capability_refresh.py --root "$PWD"
```

NOT_RUN: real Codex/Claude/Work E2E, provider/Truthound calls, coverage-guided libFuzzer,
Linux/Windows builds, Conan distribution and client package updates. M4–M7 and Work Pack
MCP/language delivery remain NOT_IMPLEMENTED, not merely untested. Existing Codex 0.2.7
(9 package files), Claude prepare 0.1.15 (85 files), shared runtime (85 files), launchers
and TopSolar D2 pins match the installed f2563f5 review; each client retains its one
active Golem installation. No actual Work action, approval issuance, evidence update
or COMMIT_UNKNOWN retry occurred. Private detailed logs and the installation check
are in `../workpack-m3-validation-20261102/`, outside the source repository.

## M4 current implementation — native-documents-v1

Owner selected the separate exact binding design on 2026-11-02 (proposal SHA-256
81be10a3fb1f468c51a52a278cf9de2a4488733341c94da30a21854133e2e665).
See [selected design](m4-binding-design.md) and [implemented limits](binding.md).
Resolve/bind/explain reuse native Work locks, generation, role enrollment, CAS, event
chain/replay, deadline checks and optional API recording. No production binding, client
policy update or native approval issuance occurs. Unsupported mappings remain BLOCKED.


M4 remains a deliberately limited native implementation. General external-tool,
development/QA, session-owner/fence, independent identity and semantic release mappings
are NOT_IMPLEMENTED; Work Pack MCP/language delivery is still a later stage. These
are explicit blockers, not skipped tests promoted to support. The reference Truthound
Pack cannot be bound by `native-documents-v1`.

Verification uses fresh disposable Works, including synthetic local exact approvals.
Existing TopSolar Works and production approval bytes are never used as mutation
fixtures. Installed Codex 0.2.7 and Claude prepare 0.1.15 remain at their reviewed
f2563f5 runtime; this source commit is not an installation update. The inventory check
matches all 9 Codex, 85 Claude and 85 shared runtime files, policy/launcher hashes and
Claude settings, with one enabled Golem installation per client and no direct duplicate.

NOT_RUN: actual Codex/Claude/Work E2E, client package updates, external provider or
Truthound calls, Linux/Windows builds, Conan distribution, coverage-guided libFuzzer.
No production binding, approval issuance, policy application, existing QA/completion
rerun or COMMIT_UNKNOWN recovery is performed. Detailed initial and final logs are
retained in `../workpack-m4-validation-20261102/`, outside the source repository.


### M4 verification results

| Check | Result |
| --- | --- |
| Final Debug build with warnings as errors | PASS |
| Final Work Pack, mutation smoke and automatic recording checks | 17/17 PASS |
| ASan/UBSan Work Pack subset | Initial 15/15 PASS; final version-drift addition 14/15, corrected fixture expectation recheck 1/1 PASS |
| ASan/UBSan added recording boundary | 2/2 PASS |
| Installed public API consumer | 1/1 PASS |
| Full native/CLI regression | 418/419 initially; missing new recording API inventory entry corrected, affected inventory/recording recheck 2/2 PASS |
| Capability regression | 371/371 PASS |
| Strict static inventory | 453 source surfaces, 352 public declarations, zero blockers |
| Exact inspected source pins | 573/573 match |
| Old pre-M4 reader | Reads legacy Work; rejects opt-in binding with CORRUPT_JOURNAL |
| Documentation links and whitespace | PASS |

The full run kept the measured Debug binary fixed throughout. After it completed,
the historical Core-version replay refinement was rebuilt and tested in the final
17-test subset; no existing native path or test limit was relaxed. A future-incompatible
reader fixture preserves the historical receipt but reports current mapping BLOCKED.
The initial sanitizer fixture used an enum identifier where the existing public API
returns a descriptive status string; the assertion now compares the native string
contract. The full regression's inventory tripwire correctly detected the new
`golem_workpack_bind` recording wrapper. Both the explicit inventory and the actual
C recording helper were extended; rejection, private-input omission, nested/thread
recording and failure behavior are tested through the existing recording suite.
The first sandbox-only session fixture failed on denied boot-ID access; the host
fixture passed with the native boot-ID checks unchanged. All initial logs remain.

Representative final commands:

```sh
cmake --build build/workpack-m1 -j3
ctest --test-dir build/workpack-m1 -j3 --output-on-failure
ctest --test-dir build/workpack-m1 -R 'workpack|fuzz_seeds|native_api_(inventory|recording)' --output-on-failure
cmake --build build/workpack-m1-asan -j3
ctest --test-dir build/workpack-m1-asan -R 'workpack|fuzz_seeds' --output-on-failure
ctest --test-dir build/workpack-m1-asan -R '^workpack_binding$' --output-on-failure
ctest --test-dir build/workpack-m1-asan -R 'native_api_(inventory|recording)' --output-on-failure
python3 -m unittest discover -s tools -p 'test_capability_*.py'
python3 tools/capability_refresh.py --root "$PWD"
```


## M5 current implementation — untrusted proposals and native role observation

See [proposal contract](proposals.md). Two additive public native APIs and two thin CLI
routes reuse the native strict parser, M2 snapshot reader, M4 binding, Work lock,
workflow closure/CAS checks and existing role `evaluate`. There is no new approval
mechanism, persisted schema, role enrollment, identity authority or client update.
Self-declared principal/model/provider tokens cannot become owner identity. M4's
unsupported general/external/development/session mappings remain unsupported; M5 does
not label them merely untested or claim a full semantic verification system.


### M5 verification results (2026-11-02)

| Check | Result |
| --- | --- |
| Debug build, warnings as errors | PASS |
| Work Pack native/CLI/fixture and mutation smoke | 17/17 PASS |
| ASan/UBSan same Work Pack subset | 17/17 PASS |
| Existing golden workflow, completion, role contract, automatic API recording/inventory, installed-header regression | 6/6 PASS |
| Installed public C API consumer | 1/1 PASS |
| Capability regression | 371/371 PASS |
| Final strict static inventory | 454 source surfaces, 354 public declarations, zero blockers |
| Current inspected source pins | 577/577 match |
| Source-contract 10 API/10 CLI entries, document links and whitespace | PASS |

The first static inventory mistakenly selected the inert proposal JSON sample as an
executable source; adding a test-reference was not sufficient because that source
scanner does not treat JSON examples as test entrypoints. It is now classified like
the existing Pack JSON sample: tracked inert fixture, exercised by the C consumer,
CLI and mutation seed. The code/test files remain source-reviewed and the exact sample
bytes are preserved in Git and the private verification record. The resulting registry
change also required refreshing its development hash. Initial blocker logs remain;
no scanner rule, test assertion, authority gate or timeout was weakened.

Representative verification commands:

```sh
cmake --build build/workpack-m1 -j3
ctest --test-dir build/workpack-m1 -R 'workpack|fuzz_seeds' --output-on-failure
cmake --build build/workpack-m1-asan -j3
ctest --test-dir build/workpack-m1-asan -R 'workpack|fuzz_seeds' --output-on-failure
ctest --test-dir build/workpack-m1 -j2 -R '^(role_contract_cli|native_api_recording|native_api_inventory|completion_cli|golden_workflow|header_workpack)$' --output-on-failure
python3 -m unittest discover -s tools -p 'test_capability_*.py'
python3 tools/capability_refresh.py --root "$PWD"
```

NOT_RUN in M5: full 421-case native suite (the affected Work Pack and existing native
contracts above were run), real Codex/Claude/Work E2E, client package updates, external
provider/Truthound calls, Linux/Windows builds, Conan distribution, coverage-guided
libFuzzer and remote CI confirmation. Earlier M4 full-suite results are historical,
not presented as a new M5 run. General external/development/session/independent
identity mappings and Work Pack MCP delivery remain NOT_IMPLEMENTED.

Installed Codex 0.2.7 and Claude prepare 0.1.15, their existing launchers and TopSolar
policies remain the reviewed f2563f5 snapshot. Each client retains one enabled Golem
installation; no new direct connection or Owner UI is created. Production approval,
Work/evidence and COMMIT_UNKNOWN are not modified or retried. No new operational
permission was needed for this source-only non-authoritative addition. Private logs,
source/fixture identities and start/end installation comparisons are retained in
`../workpack-m5-validation-20261102/` outside the source repository.

## M6 current implementation — bounded private evidence packages

See [receipts](receipts.md) and [owner-selected design](m6-export-design.md).
Three additive public APIs and CLI commands reuse native strict parsing, M4 binding,
M5 document closure, native role/document/Pack validation, Work lock, verified CAS
reads and immutable no-replace/fsync publication. No Work event, reducer change,
new native approval receipt or client permission is introduced. Export is a separate
exact disclosure decision; inspect/verify cannot grant it. This selected design
only covers implementation and isolated fixtures, not an existing project's export.

Original proposal SHA-256: `24cfd1e66949a7daa937af843ec7bf468e83ad5e3748793057b18aa9691c817f`.
A private retained copy preserves those original bytes. Full model-agent/external
QA receipt aggregation, source authentication, replay/import and Work Pack MCP
routing remain NOT_IMPLEMENTED, not merely untested.

### M6 verification results (2026-11-02)

| Check | Result |
| --- | --- |
| Debug and ASan/UBSan builds, warnings as errors | PASS |
| Work Pack/CLI/fuzz smoke/native API recording and inventory subset | 20/20 PASS in each build |
| Final M6 eight-scenario fixture, including strict error exits/sanitizer checks | PASS in debug and ASan/UBSan |
| Existing evidence, publication faults, role/completion API regression | 14/14 PASS |
| Existing golden workflow, completion/role CLI, installed header and M6 fixture | 5/5 PASS |
| Installed public C SDK consumer | 1/1 PASS |
| Capability regression | 371/371 PASS |
| Strict static inventory | 459 source surfaces, 357 public declarations; zero blockers |
| Source pins and source-contract metadata | 586 exact source hashes; 13 native APIs/13 CLI routes; no MCP claim |
| Work Pack document links and whitespace | PASS |
| Existing installed clients/runtime/policy/launcher preservation | PASS; exact start/end inventory comparison |

The first M6 fixture used `work` as a mutation-copy directory, colliding with its
existing synthetic Work; it was corrected to a distinct fixture-only path. Initial
static passes identified the new receipt dispatch/file/selector/graph-root and design
document references missing from the model. These were registered against actual
source and exact hashes, and the existing CLI inventory document was updated. No
checker condition, native approval/lock/CAS rule, test timeout or permission was
weakened. Negative CLI cases additionally require native error exit 1, never a
process crash or sanitizer failure. Initial failure logs are retained privately.

Representative commands:

```sh
cmake --build build/workpack-m1 -j3
ctest --test-dir build/workpack-m1 -R 'workpack|fuzz_seeds|native_api_(inventory|recording)' --output-on-failure
cmake --build build/workpack-m1-asan -j3
ctest --test-dir build/workpack-m1-asan -R 'workpack|fuzz_seeds|native_api_(inventory|recording)' --output-on-failure
python3 -m unittest discover -s tools -p 'test_capability_*.py'
python3 tools/capability_refresh.py --root "$PWD"
```

NOT_RUN: full 422-case native suite, real client/production export, client updates,
network/provider/Truthound calls, Linux/Windows/Conan builds, coverage-guided fuzzing,
and remote CI confirmation. Tests use disposable native Works only. The selected
inventory limits are enforced; this is not a claim of exhaustive memory-fault or
hostile concurrent-writer coverage. Offline verification is unsigned structural
integrity, not authenticated origin, semantic evidence truth, replay of all events,
current QA PASS or current Work completion.

Codex 0.2.7 and Claude prepare 0.1.15 remain the reviewed f2563f5 installation
snapshot, one enabled Golem per client. Installed Codex 9 files, Claude 85 files and
shared runtime 85 files match the original inventory; both TopSolar policy bytes,
producer references, launchers and Claude settings match. This native source update
is not installed-client Work Pack delivery. No production Work/action, approval,
QA/completion, COMMIT_UNKNOWN or Owner UI is invoked, retried or modified.
Private original approval proposal, installation comparisons, source identities and
logs are retained in `../workpack-m6-validation-20261102/` outside the repository.

## M7 current implementation — reference observation bridge

See [reference adapter](reference-adapter.md). One native pure API and one thin CLI
route validate pinned Truthound Local 3.3.1 captures. Existing native document
contracts, M4 exact binding, M5 role observation and M6 export/verify implement the
local scenario; no Python reducer, new approval authority or Work event is added.
The external release Pack remains unsupported by native binding. A distinct
native-observation-review Pack is used; structural satisfaction never grants release.

Actual external execution was separately approved under exact private plan SHA-256
`b9233dd30f20371fc097c42cf1e2603da9b5779b74caa67ce894bbff870c0216`.
The plan pins installed server/permission/MCP source and interpreter bytes plus two
synthetic files. Its isolated consent file does not replace global Truthound consent.

### M7 verification results (2026-11-02)

| Layer / check | Result |
| --- | --- |
| Mock adapter fixtures | PASS: declared successful/failed checks, tool failure, truncation, unknowns, contradictions, schema/pin/size failures, inert injected strings |
| Native local scenario | PASS: external release binding rejected; distinct document Pack bound; planning observation submitted; M5 native role SATISFIED only; M6 export/verify integrity only |
| Actual Truthound Local 3.3.1 | 6/6 calls completed, one isolated installed stdio session; zero retries |
| Actual clean CSV | check: 3 rows, 2 columns, null/duplicate satisfied; profile returned; sampled scan 0 findings (not proof of PII absence) |
| Actual issues CSV | check transport succeeded but quality false, 2 issues; profile returned; sampled email finding count 3, one finding (estimated, not unique-person count) |
| Saved actual responses through final native adapter/document scenario | PASS; no repeated Truthound calls |
| Debug and ASan/UBSan relevant Work Pack/fuzz/native recording subset | 22/22 PASS each |
| Installed public C SDK consumer | 1/1 PASS |
| Capability regression | 371/371 PASS |
| Final strict inventory | 460 surfaces, 358 public declarations, 589 source hashes; zero blockers |
| Source contract/document links/whitespace | 14 API/14 CLI routes, no MCP claims; PASS |
| Golem installations, policies and launchers | Start/end exact bytes match; one enabled Golem per client |

The native scenario initially proposed a new completion literal not accepted by the
existing v0 Pack validator. The fixture was corrected to the original schema rather
than changing that validator: its READY_FOR_RELEASE literal remains unevaluated;
its distinct document Pack ID and restricted mapping are explicit. Review then added
known row/column consistency and untruncated cardinality checks. Existing response
captures were revalidated without another external call. Initial static reference
selection and structure-model mismatches were corrected against final bytes; the
actual Python/native scenario is the selected capability test reference, while fuzz
and SDK consumer remain separate existing verification boundaries. The final strict
scan and full capability regression pass without weakening checks or timeouts.

Actual clean CSV SHA-256: `4c0610aa92b75ca794ceec30068934fc6bc3d2fbff87969a15977f8fcf96f13f`.
Actual issues CSV SHA-256: `0223321919a3ead69f38b58cd8f0c85845411ec4299876b110bbaec28192f8d0`.
All approved input/program pins still match after the six calls. Raw MCP envelopes,
tool catalog, exact plan, isolated consent, assembled captures and logs are private
under `../workpack-m7-validation-20261102/`. Calls use the installed Python/runtime
directly, without dependency downloads, global consent replacement or client restart.
The original global Truthound permissions file was absent and remains absent.

Representative local validation:

```sh
cmake --build build/workpack-m1 -j3
ctest --test-dir build/workpack-m1 -R 'workpack|fuzz_seeds|native_api_(inventory|recording)' --output-on-failure
cmake --build build/workpack-m1-asan -j3
ctest --test-dir build/workpack-m1-asan -R 'workpack|fuzz_seeds|native_api_(inventory|recording)' --output-on-failure
python3 -m unittest discover -s tools -p 'test_capability_*.py'
python3 tools/capability_refresh.py --root "$PWD"
```

NOT_RUN: full 424-case native suite, Codex/Claude Desktop model/UI E2E, production
dataset/Work/export, client package updates, remote services, Linux/Windows/Conan,
coverage-guided fuzzing and remote CI confirmation. Earlier M6 full workflow/role/
completion regressions are historical, not new M7 runs. Mock and retained-response
processing are not counted as additional actual Truthound executions. No claim of
full Core/Truthound/MCP parity or independent source authentication is made.

NOT_IMPLEMENTED: general external/custom role binding, independent principal proof,
authoritative READY_FOR_RELEASE predicate, external typed M6 object acceptance,
new Work Pack MCP routes and automatic release. M7's implemented bridge stays within
existing native document and export contracts; these omissions are not mere skips.

Codex 0.2.7 and Claude prepare 0.1.15 still use the reviewed f2563f5 snapshot, with
unchanged installed inventory, runtime/producer, TopSolar policies and launchers.
Production approvals, Work/evidence and COMMIT_UNKNOWN were not invoked, retried or
modified. New local fixtures and the approved isolated Truthound consent are separate.

## Common MCP delivery after M7

The existing 14 Work Pack CLI operations now have five shared MCP tools; see
[MCP scope, exact-action fields and verification](mcp.md). Earlier milestone
statements that MCP was NOT_IMPLEMENTED describe those milestones. Native
semantics were reused without a new Core parser/reducer or implicit authority.
The installed Codex/Claude packages and TopSolar policy pins are unchanged;
implementation/fixture qualification must not be presented as installed E2E.
