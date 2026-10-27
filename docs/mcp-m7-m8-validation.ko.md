# M7/M8 실제 설치·검증 기록 — 2026-10-26~27

**최신 r9 결과: Claude task 0.1.8 업데이트 후 별도 Work에서 QA 1회·읽기 전용 저장 결과 재조회·QA 결과/완료 문서 제출·native finalize·보고서 물질화가 실제 Claude client에서 성공했다. Codex와 새 Claude Work 모두 현재 DONE / acceptance_verified=true / generation 9 / completion_sequence 1이다. 과거 Claude COMMIT_UNKNOWN은 재실행·repair·reconcile 없이 미해결로 보존한다. 판정 범위는 선언된 macOS synthetic C Work와 현재 M8 정합성 검사이며 제품 전체 출시 완료가 아니다.**

Codex·Claude의 개선본 실제 설치, 읽기·입력 의존 응답·미허용 Work 차단·M2 준비/확인·native claim·동일 ID 저장 결과 재조회를 관측했다. 추가 C QA는 별도 사례로 기록한다. **두 client의 선언된 synthetic C Work 완료와 모든 profile·OS·제품 전체 배포 완료를 구분한다.** r8의 Claude 보류는 후속 사용자 지시로 해제했고, 아래 r9 기록이 최신 상태다. 최신 기계 판독 결과는 [검증 행렬](mcp-m7-m8-validation.json)에 있다.

## 범위와 판정 기준

실제 대상은 macOS의 Codex Desktop 26.1021.31345(build 21828), bundled CLI 0.164.0-alpha.11.1과 Claude Desktop 3.6556.2(Sonnet 5.5 medium)다. CLI/SDK fixture를 desktop 성공으로 대신하지 않는다. 테스트 대화에서 호출한 server/tool, native immutable 결과, 현재 status/next/완료 predicate를 각각 대조했다.

사용자는 별도 synthetic project/Work/registry/정책, 두 client의 설치·재로딩, 기존 D1/D2/D4 owner 절차와 최소 정상 계정 모델 호출을 허용했다. r8에서는 Claude를 보류하고 Codex/M8을 계속했으며, r9에서 사용자가 Claude 업데이트와 별도 Work의 남은 검증을 명시 승인했다. 생산 권한, credential, 외부 service 변경, 실제 target merge, 개발/원본 저장소 commit/push·PR·공개 배포는 수행하지 않았다.

`AVAILABLE`은 전달 상태다. 실행 결과와 agent 진술, hash와 내용의 진실성, 역사적 QA와 현재 QA, QA PASS와 Work 완료를 구분한다. owner 선언의 `LOCAL_COOPERATIVE`와 issuer label은 독립된 인간 신원·서명의 인증이 아니다. 원래 native parser/reducer/lock/fence/승인/완료 predicate를 재사용했다.

## 소스·패키지 변경

| 실제 발견 | 근거 | 수정과 유지한 조건 |
| --- | --- | --- |
| feature MCPB config description 누락 | 실제 Claude 설치 미리보기의 Required 오류 6개 | 모든 config 항목에 description 제공. consent 기본 false 유지 |
| 선택하지 않은 optional 계약의 template 문자열 | 실제 Claude가 `${user_config...}`를 전달 | 정해진 optional template 6개만 없음으로 해석. concrete 값·consent triple 검사는 유지 |
| union inputSchema object root 누락 | 실제 MCP/mcp-types 2.3.0 tools/list 검증 오류 14개 | oneOf root에 `type: object` 추가. branch의 required/closed/권한/한도 유지 |
| 동일 버전 설치가 과거 cache를 재사용 | 실제 UI·설치 bytes | feature MCPB 0.1.5, Codex 0.2.2와 전체 payload identity 대조. 버전만으로 일치 판정하지 않음 |
| Setup의 private launcher-only 분기 누락 | 실제 plugin에는 adapter script가 없음 | resolved command를 먼저 구분. 검토된 direct launcher/pin 보존, default adapter로 재바인딩하지 않음 |
| 구 D2 SDK fixture의 무조건 전체 도구 노출 가정 | resource/owner/host 계약 없는 fixture의 조건부 9개 숨김 | 실제 D1/D2-only 집합과 대조. 정책·guard 확대 없음 |

`tools/test_integration_m6.py`는 config 설명, object schema root, optional consent/template의 거부 경계를 검증한다. `tests/c/integration_d2_mcp.py`는 조건부 노출의 정확한 집합을 검사한다. native core는 이 작업에서 변경하지 않았다.

테스트 launcher는 isolated Python에 module/SDK 경로를 명시했다. macOS shebang/socket 길이 문제는 전용 짧은 가상환경/임시 경로로 해소했다. 검사 한도와 거부 조건은 완화하지 않았다. Codex QA의 초기 direct bootstrap은 setup-only로 차단됐으며 실패 시점의 세부 code는 확보하지 못했다. 원 configure를 호출하고 오류 code만 private에 기록하는 검토된 launcher로 재생성·재설치하고 새 대화에서 관측했다. cache 파일만 임시 수정한 것이 아니다. 최종 판정은 검증 행렬을 따른다.

## 설치 identity와 런타임

최종 feature MCPB 5개는 0.1.8이며 전체 SHA와 파일 수는 JSON의 `artifact_index`에 있다. task SHA-256은 `f377f2d3a1b9d30bcb6210c269234af2c68ea5bb51cfe0ca84a4bb7fb2af4fb4`이다. 각 최종 archive는 payload 81개와 생성 schema 5개를 포함하며 현재 source에서 byte 동일하게 재생성된다. 실제 policy/registry/Work/evidence/credential/private log는 배포물에 포함하지 않는다. Claude의 r6 task 0.1.5 설치 SHA `bd60ba9c0f7ac705a4c2adfafb051b18f903ede8fd53a27939f343fb401627b7`과 r7의 0.1.6 산출물은 이전 버전 근거로 보존한다.

검증 루트는 `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026`다.

| 대상 | 설치·실행 identity |
| --- | --- |
| Codex 기본 E2E | `golem@golem-m7-skills` 0.2.2, server `golem-m7-skills`; `~/.codex/plugins/cache/golem-m7-skills/golem/0.2.2`에서 실제 읽기·재조회 관측 |
| Codex C QA | `golem@golem-m7-qa-reviewed` 0.2.2, server `golem-m7-qa-reviewed`; private source `qa-stage-v5/codex-marketplace`, 설치 cache `~/.codex/plugins/cache/golem-m7-qa-reviewed/golem/0.2.2` |
| Codex interpreter/SDK | canonical Homebrew Python 3.14.7, 전용 `runtime/lib/python3.14/site-packages`, MCP/mcp-types 2.3.0; `-I -B -c`의 명시 경로 launcher |
| Claude 최종 설치 | `~/Library/Application Support/Claude/Claude Extensions/local.mcpb.golem-contributors.golem-task`; 승인한 r6 task payload 81개 bytes 일치 |
| Claude launcher/SDK | 실제 `uv run --directory … tools/integration_distribution_entry.py`; 전용 Python 3.11.14, MCP/mcp-types 2.3.0 |
| native | `r5/native-golem`, SHA `ca47c364541650c9fe0dcc59b523b943d73064a16c53d10542a1275a7dd2d893`; SDK pin `r5/native-sdk.json`; QA host는 기존 `integration_approval_host.c` public API 경로 |

Codex plugin은 9개 파일이고 marketplace catalog를 포함한 생성물은 10개다. task QA 노출은 별도 검토된 D4 실행 action과 D2 scope를 포함하여 15개가 됐다. profile 선택만으로 실행 권한이 생긴 것이 아니다. M4 helper와 M5 owner host는 비활성이다.

Codex의 Setup/Work 두 스킬은 실제 세션 inventory에서 관측했다. direct launcher 분기를 실제로 적용하여 default adapter 상태를 변경하지 않았다. Claude는 manifest/config 설명과 MCP tool schema 안내를 실제로 사용했다. archive에 포함된 Codex SKILL.md가 Claude의 native Skills로 자동 로드됐다는 주장은 하지 않는다.

native는 arm64 Mach-O이며 직접 의존하는 libcrypto.3, libjson-c.5, libmd4c.0, libSystem을 관측했다. self-contained=false, signature=NOT_IMPLEMENTED, trust_root=NOT_SELECTED다. 이것은 전체 동적 closure·code signing·OS/host qualification이 아니다.

## 기본 실제 E2E 결과

| test | 관측 | 결과와 한계 |
| --- | --- | --- |
| C1 Codex final install | 0.2.2 설치 bytes, 새 desktop server ready | 실제 연결·호출 관측. 원래 공개 main/기존 설치본으로 대체하지 않음 |
| C2 source 전달·응답 | status/next/record, scope body의 evidence_read | Batch `a6cb41b9e881`; 29×62+46=1844. 정답을 prompt에 주지 않음 |
| C3 실제 미허용 Work | 실제 존재하는 `denied-work` status 1회 | `TRANSFER_SCOPE / NOT_DISPATCHED`; NOT_FOUND 대체 아님 |
| C4 준비·승인 action | approved_action_prepare→plan_read→action_confirm | exact action 일치. M2 준비를 owner 승인/실행으로 승격하지 않음 |
| C5 native claim | request `8be3791fd4bf456da3b5a02725c1acc7` | committed=true, sequence 1→2; receipt `abbf6d2453af8154ff91cd2e010b5762f813cda533be92a1d6aa21626cb39a40` |
| C6 원 ID 재조회 | 사용자가 명시 승인한 동일 ID 1회 | 같은 immutable 결과/receipt/sequence. 현재 native state는 기록된 claim state와 일치하고 attempts=1. 저장 결과의 `native_state_changed=POSSIBLE`은 그대로 보존 |
| C7 완료 | native completion_check | WAIT, completion_sequence=0, acceptance=false. claim은 begin/QA/완료가 아님 |
| A1 Claude 최초 설치 | task 0.1.4 handshake·setup_status | SETUP_VALIDATION_FAILED 보존. 정상 E2E로 집계하지 않음 |
| A2 Claude 수정본 | task 0.1.5 최종 r6 설치·설정·13개 노출 | 실제 payload bytes와 정책 path/SHA 일치 |
| A3 source 전달·차단 | scope evidence 원문, 미허용 Work | Batch `68d9cd3e0d5e`; 49×24+33=1209. `TRANSFER_SCOPE / NOT_DISPATCHED` |
| A4 claim·재조회 | request `8d26a427cead4b109c14ec8f20418fa1` 실행 1회·재조회 1회 | 같은 receipt `d58001416dd3bae5b81e963c33d48062c3c6ecb4b2c32e435ff10e24b0fc529f`; sequence=2, attempts=1 |
| A5 완료 | 실제 completion_check와 후속 native 읽기 | WAIT, completion_sequence=0, acceptance=false |

Codex claim은 0.2.1 대화 `01a17849-9f30-7301-9220-b9b6be253551`에서 관측했다. 0.2.2 대화 `01a17867-5d3c-7bc1-9858-b14cc8e51899`에서 새 읽기·원 ID 재조회를 관측했다. 두 버전 사이 runtime module bytes는 동일하며 Setup/metadata 차이를 별도로 기록했다.

Claude 기본 flow 대화는 `c4bd3586-89bb-4ce0-9dc0-a8b0aec8ebf7`다. UI 응답의 denied-work를 추측했다는 진술은 fixture 실재 검증과 구분했다. 실제 enrollment와 `.golem/works/denied`가 존재하고, client grant에는 없다. 일회 UI 승인만 사용했고 persistent always-allow를 적용하지 않았다.

최초 Claude projects_list 시간 초과는 승인 UI가 처리되지 않아 tools/call로 전달되지 않은 사례였다. 읽기 1회만 명시 재시도하여 전달을 확인했다. mutation timeout을 안전한 재실행으로 취급하지 않았다.

## C QA, 실패 근거와 보존

부모 에이전트는 별도 synthetic C fixture에서 실제 컴파일·테스트 실패를 먼저 관측하고 `logic.c`의 뺄셈을 덧셈으로 수정했다. native execution prepare/finish와 development-result/qa-plan을 원 parser/renderer 경로로 준비했다. 실제 client가 이 준비·파일 수정까지 수행했다고 주장하지 않는다.

첫 QA fixture(v4)의 author가 native describe에 사용한 JSON과 D4 `native_json`의 key 순서를 다르게 만들었다. 기존 `src/execution/model.c:ex_hash`는 json-c의 직렬화를 사용한다. 읽기 전용 native approval describe로 비교한 두 scope는 **request_digest만 달랐다**. semantic JSON 내용과 source snapshot의 일치는 원래 exact 승인 계약의 일치를 뜻하지 않는다. 제품의 guard를 고치거나 request/승인/pin을 자동 재작성하지 않았다.

| QA case | 실제 층위·판정 |
| --- | --- |
| Q-A v4 | Claude 실제 execution_request `7c77e5b7c0e24734bfe84da0b7eac61e` 1회 전달. native error 11 `stale stage result`; D4는 `COMMIT_UNKNOWN / NATIVE_FAILURE / native_state_changed=UNKNOWN`을 불변 결과로 보존 |
| Q-C v4 | Codex request `f6a1d74409774955b1282b7ef0d50e11`은 자동 승인 검토에서 native dispatch 전에 거부. 재시도/우회 없음. exact action 준비·확인은 별도 관측 |
| Q-F forensic | native 읽기로 요청 key 순서와 request_digest 차이 입증. 기록된 development snapshot과 현재 native snapshot도 일치. 이것을 QA 성공·무효과 증명·unknown 해소로 승격하지 않음 |
| Q-C v5 | 사용자 후속 지시에 따라 별도 Codex project `m7-qa-codex-v5` 준비. describe/dispatch 전체 bytes와 native action digest 일치 검사. 실제 QA 두 case PASS, verify/verify_authorized 성공. receipt `ad46e9aff4b2313a1b9a9a506fcb07d3eda58a8e2ceded9f7dc07f06c0006510`, request `d08d14ff9137497c8d32e803c70a4321`. r6 당시 완료는 RECONCILE_EXECUTION/SUBMIT_RESULT, acceptance=false였으며 r8의 현재 DONE은 아래에서 구분한다. 기존 execution_request를 이용한 재조회는 BLOCKED 이력을 보존한다. r7에서 별도 읽기 전용 stored_result 경로를 구현·설치하고 Codex 실제 조회에 성공했다. receipt 기반 verify 성공을 이 조회의 대체 근거로 쓰지 않았다 |

Codex v5의 첫 저장 결과 재조회는 자동 승인 검토에서 차단됐다. 사용자가 정확한 동일 ID 호출 1회를 명시 승인한 뒤 실제 호출했으나 기존 대화에서 `Transport closed`로 응답을 받지 못했다. native Work 파일 55개와 immutable 결과 hash가 모두 그대로임을 확인했다. 새 대화 `01a178d2-08a0-76a0-98fb-705cb1180e02`에서 같은 서버의 projects_list 읽기가 정상 응답하여 연결을 복구했다. 승인 횟수를 자동 확대하지 않았다. 사용자가 복구된 연결에서 동일 인자 재조회 1회를 추가로 명시 승인했으나 자동 승인 검토가 실행 가능 tool과 cached-result-only/추가 실행 금지 조건의 충돌을 이유로 다시 거부했다. 약속대로 추가 호출 없이 중단했다. 두 승인 후 시도는 각각 transport 오류와 승인 검토 거부이며, 당시 성공한 desktop 동일 ID QA 재조회는 없었다. 이후 사용자가 안전한 읽기 전용 코드 수정을 요청하여 아래 r7에서 해소했다. native 파일 55개와 원 immutable 결과 hash는 최종 거부 후에도 모두 동일하다. transport 오류를 QA 결과 변경이나 native 결과 재조회 성공으로 기록하지 않는다.

v4의 원래 Work·request·owner decision·approval·intent·dispatch-intent·result-ref와 예약을 보존했다. Claude의 native execution-attempts 디렉터리는 읽기 관측 시 없었지만 이를 전체 부작용 부재나 종료 증명으로 해석하지 않는다. 같은 ID 또는 새 ID로 그 Work를 다시 실행·repair·reconcile하지 않았다. v5는 별도 Work/승인/정책이며 v4 승인 bytes를 교체하지 않았다.

Claude는 추가 QA 요청 뒤 Free 사용량 제한 UI에 도달했다. UI 표시 재개 시각은 2026-10-27 02:30 Asia/Seoul이었다. 유료 전환·계정 변경·예정 자동 재시도를 하지 않았다. 이후 사용자가 Claude 검증 종료를 명시했으므로 더 진행하지 않는다. 기본 read/claim/replay 성공을 QA 성공으로 바꾸지 않는다.

QA owner 계약의 raw job log 정책은 `DISCARD`, max_bytes=0, require_complete=false다. wrapper stdout/stderr·receipt·case 관측을 보존하되 raw job log 전체를 확보했다고 표시하지 않는다. 원래 owner/native 계약과 별도 helper/network/credential 권한은 구분했다.

## r7: 안전한 저장 결과 조회 해소 — 2026-10-27

- `execution_read(operation="stored_result")`는 project/Work/action/request 네 ID만 받는다. D2 공개 범위와 현재 D4 정확한 action/owner/asset pin을 모두 검사하며, 기존 `_admit(existing_only=True)`와 `_result`를 재사용한다. native command·subprocess·승인 적용·intent 생성·repair·fallback이 없다. 결과 누락/손상/철회/다른 ID는 차단하고, 기록된 COMMIT_UNKNOWN은 그대로 보존한다.
- 원본 JSON bytes를 bounded base64·SHA-256과 함께 반환한다. outer AVAILABLE/native_state_changed=false는 이번 읽기의 전달/효과이며 inner native_state_changed=POSSIBLE은 원 실행의 과거 기록이다. 현재 QA·acceptance·완료는 false로 구분한다. execution_request 자체의 실행 annotations/승인 검사는 변경하지 않았다.
- 원 QA 정책·승인 bytes는 수정하지 않았다. 새 producer hashes와 transfer pin만 반영한 별도 정책을 만들고 actions·grants가 원본과 정확히 같음을 확인했다. 읽기 ceiling을 적용한 launcher에서 모든 D4 action tool이 접근 불가하다. 새 권한을 추가하지 않았다.
- Codex `golem@golem-m7-history` **0.2.3**, 설치 cache `~/.codex/plugins/cache/golem-m7-history/golem/0.2.3`, runtime `r7/installed-runtime`. 파일 9개가 생성 원본과 byte 동일하며 inventory SHA `0dd10720aa3aea0c8f2bb487982a1d330324731d827dded9d74f231e5fa8b0d5`이다. 전체 inventory는 archive hash와 구분한다.
- 기존 대화는 새 서버를 노출하지 않아 호출 없이 NOT_RUN으로 남겼다. 새 실제 대화 **M7 Golem 0.2.3 읽기 전용 저장 결과 검증**, ID `01a17aac-b2b5-74a0-8678-f8e66e8a155d`에서 `golem-m7-history.golem_execution_read`를 정확히 **1회** 호출했다. turn `01a17aac-b3cd-7623-8989-aadb563fcbe8`, tool call `exec-137524be-0253-45c5-97df-a2a1b1484f82`.
- 원 project `m7-qa-codex-v5` / Work `example-work` / action `reviewed-qa-run-v5` / request `d08d14ff9137497c8d32e803c70a4321`의 **11,643 bytes**, SHA **`c09a431f9178777d2c0750cc007a673bec6a1468bd70bf0de01aa3c8202892cf`** 일치. 역사적 QA PASS, 이번 읽기 native_dispatch_performed=false. 실제 trace의 bytes를 원 immutable 파일과 대조했고, agent 진술만으로 판정하지 않았다.
- 원 QA Work **55개 파일**, mutation evidence **328개 파일**, 원본 저장소 baseline **897개 파일**의 hash가 유지됐다. Claude 주 설정/테스트 설정과 원 QA 정책도 그대로다. 기존 M7 Work의 실행 재호출·승인 적용·repair·commit/push는 하지 않았다. 허용된 회귀 suite의 별도 disposable Work 실행/승인과 구분한다.
- modern/legacy SDK에서도 성공·미존재 ID 차단·원본 hash 일치와 annotations/실행 도구 미노출을 확인했다. 단위 fixture는 파일 생성 및 native capture가 호출되면 실패하도록 검사한다. 정적 공격 fixture는 existing_only 해제·실행 분기 주입·미존재 차단 삭제를 검출한다.
- 중간 검증 로그의 sandbox AF_UNIX/shebang 문제, 테스트 대상/quote 불일치, 갱신 전 fixture hash 불일치를 보존했다. 원 검사를 완화하지 않고 짧은 격리 runtime·host 검증·정확한 snapshot과 fixture로 해소했다. 최종 결과는 성공 로그만을 근거로 집계한다.

## r8: Codex QA 결과 제출과 native 현재 완료 — 2026-10-27

현재 패키지는 Codex **0.2.5**, feature MCPB **0.1.8**이다. 5개 최종 archive는 `r8/final/artifacts`와 행렬의 `artifact_index`에 있으며 각 payload 81개다. task SHA-256은 `f377f2d3a1b9d30bcb6210c269234af2c68ea5bb51cfe0ca84a4bb7fb2af4fb4`이다. Claude 설치본은 기존 0.1.5를 유지했다.

| 단계 | 실제 client 근거 | native 결과 |
| --- | --- | --- |
| 기존 QA 결과 제출 | `golem-m7-finish-qa` / 대화 `01a17ab7-4355-74d1-a910-7348da1b1b6d`, request `d2c27ac77507433287d8cdc90ebdc220` | native renderer의 schema-5 qa-result r1, gen8, manifest `16aa89f980c4157167ce296df2acec1c29c1c02a703d2830dcc5a86d84769692`; 원 QA receipt 재사용 |
| completion 문서 | `golem-m7-finish-complete` / 대화 `01a17ac9-4e84-7b72-9a98-aac2c32210bd`, request `bd56f3b5f26e4c6196eeea72d6ed8db8` | completion r1, gen9, manifest `04755756a2ae31603ccf14c06332439c868f3f20bc8bdad9ac8616076cda2e37`; 후속 VERIFY_COMPLETION |
| native finalize | 같은 0.2.5 대화, request `b348e135e0e64dbf80139dae5593ca9f` | golem.completion.development.v1 / RECORDED, completion receipt `dc83b75b24e2b20abd1e3a65fde2f3f01572954d442777cb52f47e6577b9751c`; 후속 RECOVER_REPORT |
| 보고서 물질화 | 같은 대화, request `aa0175328de841cebad3f359629fc922` | sequence1 report `6ca30d5dc49fe4a00da9a2ce664b8a550dcaa0a5918eed50fc751d6d7562e5a4`; client stdout·Work 파일·CAS bytes 일치 |
| 현재 완료 조회 | 실제 client 마지막 completion_check 및 부모의 독립 read-only completion_check | inner DONE, acceptance_verified=true, generation9, completion_sequence1, QA CURRENT/PASS. outer AVAILABLE는 여전히 전달 상태 |

네 개 action은 각각 M2 approved_action_prepare → plan_read → action_confirm → 반환된 원 invocation의 **1회** 호출을 관측했다. 새 세션·claim·QA attempt·native 승인 적용은 없었다. 첫 QA 제출 대화는 스킬 파일 읽기에 read-only shell 1회를 사용해 자체 테스트 prompt의 더 엄격한 shell 제한과 불일치했다. Work/정책 쓰기는 없었으며 이후 prompt는 필요한 스킬 읽기를 명확히 허용했다. 이를 native 결과나 승인의 추가 근거로 사용하지 않는다.

이 DONE은 `m7-qa-codex-v5 / example-work / selection`의 선언된 합성 C gate와 전체 필수 문서 closure에 한정된다. parent가 수행했던 prepare/fix/finish와 client가 수행한 QA·등록·완료를 구분한다. 전체 Golem 제품/모든 API·다른 OS·독립 검토·Claude 완료를 뜻하지 않는다. issues=[]는 agent 선언이며 native predicate는 원 source/QA/gate/attempt/session/permission 조건을 그대로 적용했다.

### 시작 충돌 수정과 승인 경계

completion 전용 연결의 시작 실패는 실제 진단의 **REGISTRY_BUSY**였다. 단일 시작 지연만으로 해소되지 않았고, 후속 로그는 MCP 초기 연결 후 tools/list에서도 같은 read-lock 충돌을 보였다. 이를 native action 실패/재실행으로 처리하지 않았다. 중간 document/final/serial/ready 대화는 action 미호출 NOT_RUN 이력을 보존했다.

`integration_distribution_entry`는 configure 및 기존 lifecycle.participation 진입에서만 REGISTRY_BUSY를 기다린다. `integration_mcp.listed_tools`는 service.tools 메타데이터 조회만 기다리며 D2/D4 callback이 같은 helper를 사용한다. 각 단계는 monotonic deadline **5초**, 50ms 간격이며 반복 사이에서 deadline을 검사한다. 이미 진행 중인 파일 I/O를 강제 선점하는 전체 응답 시간 보장은 아니다. 다른 오류·pending·quota·stale·COMMIT_UNKNOWN은 기다리거나 재시도하지 않는다. 요청 handler와 native action은 이 loop 밖에 있다.

추가된 runtime 회귀 8건은 동일 owner pins 재검사, timeout, 비대상 오류, participation 해제, server 시작 이후 오류의 무재진입, metadata receiver/오류/한도를 검사한다. 정적 공격 회귀는 이 helper를 service.call로 바꾸거나 error whitelist·시간 한도·exception 범위를 확대하면 pin 갱신 후에도 차단한다. D4 `_admit`/`_mutate`, native parser/approval, core lock 구현은 r7과 byte 동일하다.

새 producer pin은 새 private 정책 파일에만 기록했다. 기존 native action/승인 bytes와 D2 grant는 그대로다. 최종 연결은 정확한 completion 문서/finalize/report 세 action만 허용하고 execution_request·helper·session획득은 노출하지 않는다. 이번 턴에 새로 만든 중간 연결 5개만 설치 identity와 설정 백업 후 지원 CLI로 철회했다. 기존 Golem, r5 QA 및 r7 history 연결은 유지했다. 참여 기록/증거를 삭제하거나 128개 한도를 올리지 않았다.

원 Work의 기존 **55개 파일**, 원 QA evidence **328개 파일**, 원본 저장소 baseline **897개 파일**의 SHA가 모두 유지됐다. Work에는 문서·완료 receipt/보고서용 **14개 파일**이 추가됐고 runner 표식은 여전히 `x`다. QA receipt/result bytes·host/decision pin·소스 19개 root 파일·Claude 설정도 유지됐다.

## M8 정적·fixture·회귀 정합성

| 검사 | 결과 |
| --- | --- |
| 최종 integration 전체 | **376 PASS / skip0**. r7 368건에 startup/metadata 대기 회귀8건 추가 |
| 최종 capability 전체 | **366 PASS / skip0**. startup 및 metadata helper 공격 회귀2건 추가 |
| native 계약 단위 | 이전 39 PASS 유지. native source/binary 동일 확인, r7에서 재실행하지 않음 |
| 현재 native D2 modern/legacy SDK | 9 PASS. 수정된 schema 포함 |
| 현재 native D4·QA·불확실성 SDK | 15 PASS. 기존 임시 QA 결과에서 읽기 경로의 subprocess 금지·Work hash 유지 추가 확인 |
| package/version 부분 | 26 PASS. 전체 integration과 중복이므로 합산하지 않음 |
| package entrypoint | 1 PASS |
| Setup/Work 공식 skill validator | 각각 PASS. 이전 PyYAML SKIP 해소 |
| repository/source-role 보고서 검사 | 16 PASS; 최종 문서 후 재검증 로그 별도 보존 |
| 현재 5 profile SDK stdio | 최종 runtime의 별도 disposable discovery fixture에서 profile/owner 교집합·공개 목록·미허용 Work 차단·helper/host 비활성 PASS. 기존 registry/Work/참여 기록에는 영향 없음. native Work E2E나 desktop으로 집계하지 않음. r7의 실제 Work 읽기 profile 관측은 별도 이전 근거로 유지 |
| 5 archive·설치 inventory | allowlist·asset·스킬·schema·import closure, 추가/private 파일 거부, 현재 source와 byte 재현 |
| 원장 고정 산출물 | 8개 byte 재현 일치 |
| 원장 대조 | source 552 / observation 2,282 / capability 1,187 / product surface 444, selected/repository blocker 0 |
| 도구 선언 | D2 43 / D4 37 / union 80. 노출은 profile와 현재 owner 정책의 교집합 |

r7 검사 source를 고정했다. execution_read 저장 결과 경로·D4 서비스의 existing_only 연결·읽기 annotations·Work skill을 수정하여 전체 integration/capability와 native D2/D4·5 profile·설치 bytes를 재검증했다. r6와 r7 runtime bytes가 동일하다고 주장하지 않는다. native 코드를 변경하거나 기존 M0~M6 검사·ID·거부 조건을 약화하지 않았다.

정적 생성기의 `client_e2e=NOT_RUN`, `native_execution_verified=false`는 그 명령 자체가 실행을 인증하지 않는다는 계약이다. 실제 M7 관측은 행렬의 해당 capability/case에만 연결하고 원장 전체를 실행 인증으로 바꾸지 않았다. 원격 CI·다른 OS·공개 release의 근거로 로컬 검사를 사용하지 않는다.

부모의 최종 native 읽기는 workspace sandbox에서 macOS `sysctlbyname` EPERM(`session.boot_identity_clock`)으로 한 번 실패했다. 원 진단을 보존하고 명시적인 host 권한으로 읽기 전용 state/next/완료 관측을 완료했다. Git의 DARWIN_USER_TEMP_DIR confstr 경고도 원래 stderr 거부 guard가 차단했으며, 정적 대조 역시 명시 host 환경에서 검사했다. 이를 Work 손상이나 native mutation으로 해석하거나 guard를 우회하지 않았다.

## 남은 의무·usage·보존

- facade delivery backlog 0, owner-management 83, unsupported 17을 유지한다. 대표 E2E 성공으로 owner83개 전체를 완료 처리하지 않는다.
- M5 task DAG scheduler, typed edge evidence acceptance, resource receiver broker, merge queue, integration workspace/fresh QA, target ref CAS broker, merge publication receipt는 NOT_IMPLEMENTED다.
- P7 self-contained runtime·전체 동적 closure·서명/trust root·정식 OS/host qualification·업데이트/유통은 미구현/미결이다.
- Linux/Windows·remote CI·Hosted/remote·실제 target merge·공개 배포는 NOT_RUN이다. task 외 profile의 desktop 검증과 이번 기록 밖의 다른 native CTest integration suite도 NOT_RUN이며, 39개는 선택한 native 단위 검사다. client가 직접 prepare/finish한 전체 흐름도 검증 범위 밖이다. 실행을 시도한 QA 실패를 NOT_RUN으로 숨기지 않는다.
- Codex usage는 명시적으로 만든 테스트 대화의 cumulative token_count만 기록한다. parent/Claude와 청구액 전체를 포함하지 않는다. cached input과 reasoning output은 다른 counter와 중복될 수 있어 합산하지 않는다. Claude usage와 양쪽 billing cost는 null/UNKNOWN이다.
- 개발 HEAD `2e690091a55f366d5f99580ee375fca7610f2f77`, 원본 HEAD `e583b17469c50edd1e18df90880df07940c77b69`를 유지한다. 원본 baseline 897개 파일의 SHA가 모두 일치하고 기존 `assets/Golem-codex-plugin.png` 수정도 보존했다. staging은 비어 있다.
- Claude 주 설정 파일은 원 백업과 byte 동일하다. 테스트 확장만 승인한 파일로 업데이트하고 정책 path/SHA를 UI로 선택했다. Codex의 의미상 config 변경은 이번 `golem-m7-*` 테스트 항목으로 한정한다. 생산 Work 전체를 읽어 전후 hash 조사한 것은 아니다.
- 테스트 Git fixture는 기존 개발 HEAD를 fetch/checkout하여 재사용했다. 이 durable C QA 준비에서 새 Git commit은 만들지 않았다. 기존 회귀 suite의 disposable fixture baseline commit과 개발/원본 commit을 구분한다. 개발/원본 commit/push·PR·공개 배포는 하지 않았다.
- 중간 테스트 plugin/cache와 launcher는 private 백업 후 지원 CLI로 철회·교체한다. process 정리는 명령 identity·PID·귀속을 확인하여 이번 작업의 transport만 대상으로 한다. 기존 사용자 process·native claim/lease·unknown 예약은 변경하지 않는다. 이번 후속 정리에서 명령 identity를 확인한 중간 transport 16개와 이전 launcher 2개의 실제 종료를 확인했다. 최종 plugin의 구성 상태와 process 수를 혼동하지 않으며, 이 정리로 현재 feature process 수를 추론하지 않는다. process 종료·lease 만료를 Work 완료나 unknown 해소로 표시하지 않는다.

초기 private-log mode 정리에서 신규 테스트 Work의 불변 파일 257개 mode에 영향을 준 실행 실수가 있었다. native dw_publish/CAS 생성 규칙으로 0400을 복원하고 모든 bytes/hash와 현재 status/next를 다시 대조했다. 생산/기존 사용자 Work에는 적용되지 않았다. private `test-file-mode-correction.json`에 보존했다.

최종 Codex 설치의 9-file inventory SHA는 `1510d2624385cd6dab35450ec23295843379ad0a04e3c3c3bb55782b90155d25`다. 이는 archive SHA와 구분되는 파일 inventory identity이며 실제 설치 bytes와 source를 대조했다. r6 당시 추가 테스트 plugin은 `golem@golem-m7-qa-reviewed` 한 개였다. r7에서는 이를 보존한 채 `golem@golem-m7-history` 0.2.3 읽기 전용 연결을 추가했다. 기본 검증용 skills 및 중간 release/QA/diagnostic plugin은 백업 후 철회했고 원래 Golem은 보존했다.

M7의 기본 두 client 흐름 및 Codex의 실제 QA·읽기 전용 동일 ID 조회·QA 결과 제출·현재 native DONE이 해당 범위에서 통과했다. Claude QA와 client/OS 전체 의무가 남으므로 전체 M7 완료로 선언하지 않는다. M8은 현재 macOS source/artifact·정적·fixture·회귀·관측 결과의 정합성 범위로 한정한다.

## 상세 증거 경로

- source 보고서: `/Volumes/Extreme SSD/golem-project/mcp-counter-semantics-src/docs/mcp-m7-m8-validation.{ko.md,json}`
- 현재 artifact/index: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/r8/final/artifacts/` (Claude 설치본은 r6 유지)
- 현재 private 행렬·trace·native 결과·보존: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/r8/private/`, 실제 최종 client 근거 `r8/final/current/`; 이전 r6/r7 실패와 조회 해소 이력 유지
- 원 로그·보존·회귀: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/private/`
- 불변 claim·v4 unknown: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/r5/private/{codex,claude}-v4/registry/`
- 수정 Codex QA·owner review·재생성 launcher: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/qa-stage-v5/`

원시 자료는 owner-private이며 공개 배포 대상이 아니다. synthetic identity와 무결성 hash만 공개 보고에 연결한다.


## r9 — Claude 보류 해제·0.1.8 업데이트·별도 Work 완료

이 절과 JSON의 `qa_fresh_v9`가 최신 Claude 판정이다. 앞의 보류/NOT_RUN/COMMIT_UNKNOWN 기록은 당시의 역사적 결과로 보존한다. 기존 UNKNOWN의 성공 전환이나 재실행으로 해석하지 않는다.

- 실제 client: Claude Desktop 3.6556.2, Free, Sonnet 5.5 medium. 대화 [Claude Desktop M7 QA 격리 실행](https://claude.ai/chat/3138e426-e0df-41a2-87e2-cc1e0e33e85a).
- task 0.1.8 SHA-256 `f377f2d3a1b9d30bcb6210c269234af2c68ea5bb51cfe0ca84a4bb7fb2af4fb4`. 사용자의 해당 파일 업데이트 확인을 받고 실제 Update/Install을 적용했다. 설치 archive 82개 엔트리(81개 payload와 package inventory)가 승인 파일과 전부 일치했다.
- 새 project `m7-qa-claude-v9`, Work `example-work`, selection `selection`. 새 registry와 새 Work를 생성했고 이전 Work를 복제하지 않았다. parent가 pre-fix C 실패 재현·native prepare·수정·finish를 수행했다. 실제 Claude는 QA 실행과 후속 문서/완료 절차를 수행했다.
- 처음 준비 스크립트가 native approval action의 키 순서를 재정렬해 승인 host가 `policy denied`로 거부했다. 해당 요청/거부 capture는 미승인 PENDING으로 보존했다. native describe의 순서를 그대로 담은 별도 요청을 기존 host로 승인했다. native parser/승인 조건을 바꾸지 않았다. 실제 dispatch의 native bytes와 action pin은 M2 준비 및 승인한 bytes와 동일했다.
- 각 action마다 Claude의 approved_action_prepare → plan_read → action_confirm을 새로 거쳤다. 준비/확인은 `execution_authorized=false`, `approval_created=false`다. M2가 제안한 wrapper request ID와 owner가 선택한 실제 ID는 별도로 기록했고 native action/body/승인 pin은 같음을 파일 SHA로 대조했다.
- 모든 Claude 도구 허용은 1회였다. 항상 허용·승인 검사 완화·helper/host/resource 권한 추가는 없었다. QA 이후 연결을 결과 제출 전용, 최종 완료 전용 정책으로 재로딩해 execution_request 노출을 제거했다.

| 단계 | 실제 결과 |
| --- | --- |
| 새 QA 실행 | 정확한 action/request 1회, NATIVE_RESULT_RECORDED, 두 declared case PASS, exit 0, runner marker `x` |
| 저장 결과 재조회 | execution_read/stored_result 동일 ID 1회 성공. execution_request 재호출 없음 |
| receipt 검증 | verify·verify_authorized 각각 읽기 1회. hash/무결성과 진실성·provider 인증은 구분 |
| QA 결과 문서 | native renderer/schema 5와 native parser 사용, document_submit 1회, generation 7→8. 현재 QA CURRENT/PASS |
| completion 문서 | 검증한 고정 문서 action 1회, generation 8→9. 다음 native action VERIFY_COMPLETION |
| finalize | 정확한 selection/key/generation/issues 고정 action 1회. native 완료 receipt 기록 |
| report | sequence 1 보고서 물질화 1회. Work/CAS/immutable native reply/readonly inspect bytes 일치 |
| 최종 현재 조회 | DONE, acceptance_verified=true, generation 9, completion_sequence 1. session sequence와 다른 카운터를 섞지 않음 |

새 QA receipt는 `0003d3446cbd14dea7dcc8163ab99aef10a52f3368e88a936c96ce0ffde55851`, completion receipt는 `c1e2324980fd71f0fa97a98c1719554734f4a363bb7612b35b47bfc3c51a22f4`, report digest는 `e788c4a2ce553a752c9e3aee694ac42e0e617799187a45529968f4f7a3754838`다. native predicate는 `golem.completion.development.v1`, independent_review=false이며 declared synthetic gates 범위다.

최신 설치본에서 실제 존재하는 Codex synthetic DONE Work(m7-qa-codex-v5/example-work)의 status 조회를 Claude task로 1회 시도했다. 펼친 실제 tool Error 원문은 TRANSFER_SCOPE / NOT_DISPATCHED / native_state_changed=false였고 NOT_FOUND가 아니었다. 해당 Work의 원파일 69개 hash는 그대로다. 다른 Golem 서버로 우회하거나 재시도하지 않았다. 도구로 이미 전달된 gate 값 duration_ms=2405, stdout_size=95, stderr_size=0, cases=2로 계산한 `(duration_ms mod 1000)+stdout_size-stderr_size+cases`의 agent 응답은 502이며 immutable native 값의 독립 계산과 일치했다. 프롬프트에 수치나 정답을 제공하지 않았다. 도구 입력 의존의 한 사례만 관측한 것이며 내부 이해/진실성을 인증하지 않는다.

task transport의 실제 tools/call metadata는 총 30회다(projects_list 1, M2 준비/읽기/확인 15, 정확한 D4 action 5, execution_read 3, completion_check 5, scope 거부 work_inspect 1). 실제 설치된 .venv Python process와 uv parent를 식별했고 canonical interpreter는 uv의 CPython 3.11.14, 해당 .venv의 MCP distribution은 2.3.0이다. native QA gate는 별도 pinned Homebrew Python 3.14.7과 C compiler를 사용했다. 승인된 task MCP server는 의도적으로 활성 상태로 남겼고 gate는 reaped=true다. 추가 candidate/helper host를 시작하지 않았다. Codex의 qa-reviewed 0.2.2/history 0.2.3/finish-complete 0.2.5와 원래 두 client Golem 연결을 보존했다.

실제 UI의 정확한 도구 인자와 성공 trace, task transport의 method/id/result metadata, immutable native 결과, 서버의 receipt/완료 read delivery, 독립 native current 조회를 대조했다. Claude 기본 logger는 전체 tool payload를 저장하지 않아 raw client 응답 bytes 전체의 별도 복사/해시 일치는 주장하지 않는다. 저장 결과 재조회 성공은 실제 UI에서 관측했고 원 immutable 결과 hash를 대조했다. Claude native Skills 자동 로드는 관측하지 않았고 manifest/tool 안내를 사용했다. usage·비용은 확보되지 않아 null/UNKNOWN이다.

M8은 같은 source inventory에서 원장 8개·패키지 5개 재생성 일치를 재확인했다. 552 sources / 2,282 observations / 1,187 capabilities / 444 surfaces / D2 43 / D4 37이다. selected/repository/delivery blocker는 0이고 owner backlog 83·unsupported 17은 유지했다. 현재 승인·불확실성·읽기 재조회·M2·패키지/재로딩 회귀는 96개 고유 검사 PASS다. 최초 96개 중 CLI 미지정으로 skip한 1개는 명시 CLI의 순수 validator 검사로 보완해 미해소 skip은 0이다. 기존 r8 전체 integration 376 / capability 366 / native SDK D2 9·D4 15 / repository/source-role 16 결과는 같은 source hash의 기록으로 보존했으며 r9에서 전체를 재실행했다고 표시하지 않는다.

기존 UNKNOWN evidence 100개·Work 44개·policy/action/decision 각 1개, Codex DONE Work 69개와 원본 저장소 897개 원파일의 SHA가 그대로다. Claude main config와 원본 Golem 연결을 보존했고 테스트 extension policy/digest만 새 scope로 전환했다. native src/include, 양쪽 HEAD·staging, Codex QA marker `x`, 새 Claude QA marker `x`를 대조했다. 기존 UNKNOWN은 계속 미해결이며 새 Work 성공으로 해소되지 않는다. 전체 생산 Work를 전수 inventoried했다고 주장하지 않는다.

Linux/Windows/remote CI/Hosted, 실제 target merge, public distribution, 실제 desktop가 수행하는 prepare/finish, task 이외 profile의 desktop 종단 검증, 서명/trust root 및 기존 M5/P4/P5 미구현 범위는 계속 NOT_RUN 또는 NOT_IMPLEMENTED다. commit/push는 수행하지 않았다. 세부 실행 ID·hash·검사·보존 원장은 JSON의 `evidence_paths_r9`와 `r9-claude/private/validation-matrix.json`에 있다.

문서 갱신 후 현재 repository/source-role 검사 16개도 PASS(skip 0)였다. Claude UI의 공유 5시간 한도 90% 이상 사용 배너를 관측했으며, 이 비율을 해당 테스트의 token·비용으로 환산하지 않았다. 정상 모델 호출은 마지막 입력 의존/권한 차단 확인 뒤 추가하지 않았다.


## 검증 후 설치 정리와 개발 규칙

2026-10-27 사용자가 각 client에 검증된 최신 Golem만 남기도록 별도 요청했다. Codex는 `golem@golem-m7-finish-complete` 0.2.5만 남기고 구 plugin 3개·오래된 marketplace 17개·비활성 direct MCP `golem`을 지원되는 관리 기능으로 제거했다. Claude Desktop은 구 Golem 0.1.3을 UI에서 제거하고 Golem task 0.1.8만 남겼다. 남긴 설치 bytes와 최신 Claude 설정은 그대로다. 이전 절/JSON의 설치 보존 내용은 M7/M8 검증 당시의 역사적 관측이다. 현재 목록은 workspace의 `.golem-plugin-installations.json`을 따른다.

제거 전 프로그램/설정 복구 자료를 owner-private `m7m8-validation-20261026/cleanup-latest-20261027/private`에 보존했다. 기존 COMMIT_UNKNOWN evidence 100개·Work 44개·승인 policy/action/decision, Codex DONE Work 69개·새 Claude DONE Work 71개의 원파일 hash가 모두 동일하다. 권한·정책 범위는 이전하지 않았고 Work 실행/모델 호출/commit/push도 하지 않았다. 공식 Codex CLI가 무관한 `node_repl.args=[]`를 기본 빈 인자 목록의 생략 형태로 직렬화한 한 건을 별도 기록했으며 다른 유효 설정은 동일하다.

후속 사용자 지시에 따라 workspace 공통 `AGENTS.md`와 `CLAUDE.md`에 개발 시작·설치 변경·종료 시 최신 검증본 한 개 유지, 중복 정리, 실제 bytes/권한/보존 검사와 원장 갱신을 필수 규칙으로 추가했다. 설정·원본·승인·evidence 삭제로 검증/정리를 성공 처리하거나 미검증 버전을 최신본으로 승격하지 않는다. 자세한 정리 결과는 `m7m8-validation-20261026/cleanup-latest-20261027/summary.json`에 있다.
