# M5 병렬 작업·후보 결과·병합 절차 연결

상태: 고정 native facade 47개 연결과 명시 범위 코드·정적·fixture 검증 완료. 고정 M5 원장 47개는 기존 native 기반에 한정한 제공 경로를 대조한다. P4/P5 신규 scheduler·merge broker 구현 완료를 뜻하지 않는다. 실제 client/Work E2E, host 시작/연결, 외부 서비스, 승인 적용, 실제 merge, commit/push는 NOT_RUN이다.

## 구현 및 권한 경계

- D2 `candidate_read`: validate, host_validate, request_digest, gates, status, diff, context_candidate. compare/review_check/target_check는 별도 owner host 계약의 정확한 query ID·파일 bytes·native digest만 사용한다. request_digest는 json-c 해시이며 schema 검증·실행 성공이 아니다. context candidate는 tokenizer 측정이나 모델 입력 수신을 보증하지 않는다.
- D2 `workspace_read`: 현재 owner 계약과 원래 D4 action/request ID로 저장된 결과만 재조회한다. 새 intent나 native 호출을 만들지 않으며 현재 workspace 검증으로 승격하지 않는다. 직접 workspace 현재 검사는 D4 `workspace_request`의 정확한 승인 action에 남긴다. 불확실 CREATE/REMOVE를 재시도하거나 repair하지 않는다. 기존 active/recovery claim은 보존·차단한다.
- D2 `inventory_read`: 업로드한 정책의 native 검증과 두 snapshot의 순수 비교. 제공된 snapshot의 provenance·진실성은 인증하지 않는다.
- D4 `inventory_capture`: 정확한 owner action의 정책과 등록된 project root만 native capture에 전달한다. 파일/Git 읽기 및 private audit 기록이며 실행·merge 권한이 아니다.
- D4 `candidate_request`: create/enroll/reserve/start/cancel/settle/diff-seal/review/select/cohort-record. 원래 finish는 직접 허용하지 않고 별도 종료 attestation을 요구하는 기존 typed settle 경로에 연결한다. candidate start는 기존 current-agent connector이며 새 agent를 만드는 scheduler가 아니다. admission grant는 기존 owner CLI로만 관리한다.
- D4 `workspace_request`: create/resume/activate/seal/retain/remove를 기존 `golem_workspace_call`에 전달한다. CREATE는 고정 full base OID, RETAIN은 기존 CAS evidence를 요구한다. SEAL/RETAIN/REMOVE는 별도 operator attestation과 native active/recovery claim 부재가 필요하다. 기존 dirty/untracked/ignored 변경은 native non-force 제거 검사로 보존된다.
- 기존 M3 `context_publish`와 M2 준비·owner action 확인을 재사용한다. 일반 Work 변경은 candidate host가 parent lock을 보유하는 동안 `PARALLEL_HOST_OWNS_PARENT_WORK`로 dispatch 전에 차단한다. owner가 host를 중지하고 정책을 명시적으로 변경한 뒤 원래 경로를 사용할 수 있다. 자동 stop/restart/reload는 없다.

## 선택적 owner host 계약

`tools/integration_parallel_hosts.py`의 `schema`와 `plan --input`은 schema/producer 자료만 출력한다. 실제 연결·승인·host 시작을 수행하지 않는다. D4 launcher의 `--parallel-host-policy`, `--reviewed-parallel-host-policy-sha256`, `--approve-parallel-host` 세 인자가 모두 있어야 활성화된다. M4 helper 계약과 별개이며 기본 비활성이다.

계약은 mutation/transfer policy SHA, host ID, config 파일 bytes SHA 및 native config digest, private Unix socket device/inode, parent/child/target 등록 Work, repository/worktree/admission root identity, 허용 operation, 정확한 D4 action SHA와 native request digest를 고정한다. owner 자료·socket은 project 밖 private 위치다. 모든 영향 Work에 기존 D1 record/status/next 및 D2 work_inspect scope가 필요하며 자동 등록·grant는 없다. v1은 project별 하나의 명시 host만 허용하여 별도 parent/namespace를 병렬 arbiter로 추가하지 않는다. 각 host는 하나의 등록 project, 그 `.golem` 아래 child tree/build/temp와 worktree/admission root, project root의 target tree만 지원한다. 외부 root나 교차 project는 지원하지 않는다.

parent Work는 native host가 배타 잠금으로 보유한다. 새 host-info 및 work-record/work-status/work-next는 그 handle에서 원래 native record/parser/reducer를 호출한다. candidate compare/review-check/target-check의 child handle은 읽기 전용으로 열어 CAS 생성 효과를 허용하지 않는다. native RESUME는 기존 잠긴 read-only store에서 identity·receipt를 검증하며 publish·repair하지 않는다. 후보 내부 검증만 이 경로를 사용하고 직접 workspace-resume·activate는 active/recovery claim을 계속 거부한다. CREATE는 새 부재 tree만 준비하며, SEAL/RETAIN/REMOVE의 종료·claim 검사는 유지한다. Python은 state·lock·fence·자원/lease·QA predicate를 재구현하지 않는다. 선택한 host에서 실패하면 direct CLI로 fallback하지 않는다. socket/config/Work/root/producer의 현재 pin을 재확인하고 host-info config digest를 사전·사후 대조한다. same UID와 config digest는 협력적 로컬 identity 관측이며 암호학적 host나 인간 identity 인증이 아니다.

종료 자료 `golem.integration-operator-termination.v1`은 host/config/action/request digest와 `all_workers_stopped:true`, `OPERATOR_ATTESTED_NOT_PROCESS_REAPING_OBSERVATION`을 정확히 고정한 private file pin이다. 모델 boolean·lease 만료·cancel 요청은 이를 대체하지 못한다. native는 active/recovery claim을 다시 거부한다. 실제 OS process reap이나 강한 containment 증명을 제공하지 않으므로 그러한 정책의 fallback으로 사용할 수 없다.

D4 immutable intent와 request ID를 그대로 사용한다. 같은 원래 request ID는 저장된 결과만 재조회한다. host action의 dispatch-intent가 있으면 새 request ID로 같은 action을 반복할 수 없다. 결과 유실·timeout·사후 pin 변경은 COMMIT_UNKNOWN이며 자동 재실행·repair·승인 발급이 없다. pending QA는 기존 D4 차단을 유지한다. native stdout bytes/base64/SHA는 역사 관측이며 현재 QA PASS·target 채택 가능성·완료가 아니다.

## P4/P5에서 구현되지 않은 기능

기존 `docs/intent-assurance-parallel.ko.md`는 구현 제안이다. 기존 best-of-N candidate와 기능 분할 DAG를 동일시하지 않는다.

D2 `parallel_prepare`, `merge_prepare`는 기존 M2의 private spool·UUID·SHA·동일 service instance·30분 TTL·현재 basis 검사를 재사용한다. 별도 authority database나 실행 queue를 만들지 않는다. task/Work/selection/spec/source/owner/resource/후보 참조, typed edge의 정확한 predecessor·선택 attempt·evidence policy·baseline을 보존하고 중복·누락·cycle·spec/baseline mismatch·edge consumption mode를 검사한다. 각 참조 Work의 D1/D2 scope와 native record/status/next 및 정확한 selection revision/digest를 다시 관측한다. 제공된 spec/source/evidence/owner/resource 값은 진실·충족을 인증한 값이 아니다.

merge 준비는 source와 target Work 격리 및 고정 40/64자리 target OID·generation·policy·결과·QA·review/input/tree 참조를 보존한다. 이 참조가 실제 native issued receipt라는 인증, 현재 source scan, target applicability, target ref CAS를 수행하지 않는다. 기존 native target-check는 owner의 고정 query로 별도 재조회한다. 기존 target-check도 최신 target integration broker나 merge 구현을 대신하지 않는다.

다음 기능은 **NOT_IMPLEMENTED / IMPLEMENTATION_REQUIRED**이며 단순 NOT_RUN이 아니다: task DAG scheduler, typed edge evidence acceptance, resource receiver broker, merge queue, integration workspace와 fresh QA, target ref CAS broker, merge publication receipt. 준비 결과의 readiness/edge acceptance는 NOT_EVALUATED, resources_reserved와 merge_authorized는 false다. action_confirm은 OWNER_ACTION만 허용하므로 이 준비안을 실행 권한으로 바꾸지 못한다.

## 한도와 보존

M5 host는 최대 16개, 영향 Work 최대 16개/host, 정확한 action/query 각 32개, 3개 고정 root를 사용한다. DAG task 최대16/edge64, artifact ref32/edge, 전체 MCP 입력262144bytes, native process capture32MiB, 기존 candidate host wire512KiB(초과 시 차단), 기존 shared audit quota 및 15초 제한을 적용한다. native inventory는 1024path/1MiB JSON/64MiB content per pass, 4096visits/64levels/60초 자체 한도를 적용하며 integration의 더 짧은 15초가 우선한다. timeout은 완료나 재실행 허가가 아니다.

unknown usage·cost는 native known flag와 원래 값을 보존하고 unknown을 0으로 판정하지 않는다. select는 merge/push false를 유지한다. 실제 연결/설정/launcher/승인/registry/Work/evidence/CAS/journal/기존 candidate·worktree 및 원본 저장소 변경을 보존한다. fixture가 만든 임시 자료만 정리한다.

## 검증 및 47개 항목

고정 47개 모두 현재 native 기반에 한정한 실제 제공 경로에 연결했다. 읽기/순수 검증, 정확한 native action, 원래 owner 전용 관리 경계를 유지한다. `native.golem_workspace_call`의 MCP_READ는 저장된 action 결과이며 현재 RESUME 검사는 정확한 D4 action이다. 47은 새 scheduler/merge 기능 수가 아니며 위의 7개 미구현 의무는 남는다.

- M5 fixture **28개** 통과: 모든 candidate/workspace operation의 고정 argv/bytes·unknown accounting flag, 별도 host 기본 비활성, cross-Work/owner/socket/config scope, 별도 종료 attestation, 현재 host digest 불일치, 결과 유실/원래 결과 재조회/새 ID 재실행 차단, historical workspace read의 무 intent·무 native 호출, DAG cycle·missing/duplicate/spec/selection drift, merge proposal의 두 Work basis drift.
- 전체 integration **334개 중 316 통과/18 skip**. skip은 선택적 gateway 16개, SDK icon 1개, 실제 stdio MCPB 1개다. 순수 M2/M3/M4/M5 CLI component는 opt-in으로 실행했으며 live Work/client E2E가 아니다.
- capability 전체 회귀 및 M5 adversarial 정적 검사를 실행했다. 구체적인 최종 개수와 gate 결과는 아래 최종 기록을 따른다. 모델 pin 재작성만으로 owner·termination·read-only·unimplemented·재실행 경계를 완화하지 못하도록 독립 검사를 유지한다.
- Debug `-Wall -Wextra -Wpedantic -Werror` CLI build 통과. 기존 native API/codec/ownership/accounting 단위 37개와 candidate model·inventory 단위 2개, **39개 모두 통과**. workspace/candidate host integration 테스트는 실제 host·QA·Work 흐름을 실행하므로 NOT_RUN이다.
- 실제 host 시작/접속·client/Work E2E·외부 서비스·owner 승인 적용·실제 merge·설치/reload·CI·Linux/Windows·commit/push는 **NOT_RUN**. 7개 P4/P5 새 기능은 **NOT_IMPLEMENTED**다.

| 고정 capability ID | 실제 native 근거 | 제공 도구 | 한정 권한/효과·결과 |
| --- | --- | --- | --- |

| `cli.route.candidate` | `src/cli/main.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `cli.dispatch.candidate.diff` | `src/cli/candidate.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `cli.dispatch.candidate.gates` | `src/cli/candidate.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `cli.dispatch.candidate.host-validate` | `src/cli/candidate.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `cli.dispatch.candidate.request-digest` | `src/cli/candidate.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `cli.dispatch.candidate.status` | `src/cli/candidate.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `cli.dispatch.candidate.validate` | `src/cli/candidate.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `cli.dispatch.context.candidate` | `src/cli/context.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `native.golem_candidate_gate_digest` | `include/golem/candidate.h` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `native.golem_candidate_call` | `include/golem/candidate.h` | `candidate_request`, `candidate_read` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `native.golem_context_publish` | `include/golem/context.h` | `context_publish` | CONNECTED / 기존 M3 D4+native tokenizer; quiescent Work; live E2E NOT_RUN |
| `native.golem_inventory_capture` | `include/golem/inventory.h` | `inventory_capture`, `inventory_read` | CONNECTED / 정확 D4 project read/Git; snapshot≠truth; live E2E NOT_RUN |
| `native.golem_workspace_call` | `include/golem/workspace.h` | `workspace_request`, `workspace_read` | CONNECTED / D4+별도 host; terminal attestation; read는 역사 결과; merge 없음; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.cancel` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.cohort-record` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.compare` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.create` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.diff` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.diff-seal` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.enroll` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.finish` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.reserve` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.review` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.review-check` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.select` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.start` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.status` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.candidate.golem_candidate_call.target-check` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.candidate.dispatch.cancel` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.cohort-record` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.compare` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.candidate.dispatch.diff` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.candidate.dispatch.diff-seal` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.enroll` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.finish` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.reserve` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.review` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.review-check` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.candidate.dispatch.select` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.start` | `src/candidate/controller.c` | `candidate_request` | CONNECTED / D4+별도 host; finish→typed settle; 채택≠merge; live E2E NOT_RUN |
| `operation.candidate.dispatch.target-check` | `src/candidate/controller.c` | `candidate_read` | CONNECTED / D1/D2 read 또는 별도 owner query; 수락 아님; live E2E NOT_RUN |
| `operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_CREATE` | `include/golem/workspace.h` | `workspace_request`, `workspace_read` | CONNECTED / D4+별도 host; terminal attestation; read는 역사 결과; merge 없음; live E2E NOT_RUN |
| `operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_RESUME` | `include/golem/workspace.h` | `workspace_request`, `workspace_read` | CONNECTED / D4+별도 host; terminal attestation; read는 역사 결과; merge 없음; live E2E NOT_RUN |
| `operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_ACTIVATE` | `include/golem/workspace.h` | `workspace_request`, `workspace_read` | CONNECTED / D4+별도 host; terminal attestation; read는 역사 결과; merge 없음; live E2E NOT_RUN |
| `operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_SEAL` | `include/golem/workspace.h` | `workspace_request`, `workspace_read` | CONNECTED / D4+별도 host; terminal attestation; read는 역사 결과; merge 없음; live E2E NOT_RUN |
| `operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_RETAIN` | `include/golem/workspace.h` | `workspace_request`, `workspace_read` | CONNECTED / D4+별도 host; terminal attestation; read는 역사 결과; merge 없음; live E2E NOT_RUN |
| `operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_REMOVE` | `include/golem/workspace.h` | `workspace_request`, `workspace_read` | CONNECTED / D4+별도 host; terminal attestation; read는 역사 결과; merge 없음; live E2E NOT_RUN |


## 최종 검증·보존 기록

M0~M5 selected/repository gate 모두 blocker **0**, 고정 M5 47/47 연결, source/근거542·관측2275·capability1180·whole product437이다. M5 mandatory static profile은 read3/action3/preparation2 및 source function52개와 고정47개를 대조한다. capability 회귀 **355개 통과**(M5 adversarial10개 포함), integration **334개 중316 통과/18 skip**(M5 fixture28개 포함), native unit **39개 통과**, Werror CLI build 및 `git diff --check` 통과. 8개 고정 원장 산출물은 재계산 bytes와 대조한다.

원본 저장소 HEAD `e583b17469c50edd1e18df90880df07940c77b69` 및 기존 `assets/Golem-codex-plugin.png` 변경 목록을 유지했다. 개발 checkout HEAD `2e690091a55f366d5f99580ee375fca7610f2f77`, staged path 0. 기존 선택535개 source 중 명시된 M5 runtime14개와 문서·정적 모델/fixture 밖 예상하지 않은 변경은 없다. 기존 관측2249개·capability1162개 ID를 모두 유지했다. 실제 private Work 전체 bytes를 읽어 인증했다는 의미는 아니며 실제 연결·launcher 설정·승인/registry/Work/CAS/journal/기존 후보 디렉터리에 작업을 적용하지 않았다. 개발 build와 임시 fixture만 사용하고 임시 fixture는 정리했다.

남는 항목은 P4/P5 새 구현7개(NOT_IMPLEMENTED), 기존 owner 관리83개, 명시적 unsupported17개, 실제 host/client/Work/외부 서비스/merge 검증 및 CI·플랫폼 검증(NOT_RUN)이다. 기본 비활성 owner host 계약과 기존 설치 정책을 실제 연결에 적용하지 않았다. commit/push는 수행하지 않았다.
