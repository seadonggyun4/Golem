# M2 입력·준비 구현과 검증

## 범위와 계약

M2는 현재 승인된 Work에서 입력·native action 초안·구조 검증·재조회 가능한 불변 준비안을 제공한다. 기존 D2 전달 범위와 D1 record/status/next 권한이 필요하며, owner action 조회·확인은 기존 D4 policy가 있는 서비스에서만 제공한다. 기존 도구 scope에 새 이름을 자동 추가하지 않는다. runtime/연결·승인·policy·등록 Work를 변경하거나 native mutation을 호출하지 않는다.

검토된 backlog에는 M2 단독 native 실행 항목 대신 M3 60/M4 45/M5 29, 총 134개 action의 M2 준비 의존성이 있었다. 고정 ID/대조표는 `capability_m2_backlog_registry.py`와 재생성 JSON의 `m2_preparation_dependencies`에 유지한다. 26개는 기존 D4 typed 초안/owner byte 검토, 22개는 core 입력 artifact 구조 검증, 86개는 현재 Work 입력/basis와 후속 typed native route 경계다. 공통 준비가 있다고 후속 operation의 schema·실행 경로·권한까지 제공됐다고 주장하지 않는다. M3~M5 delivery backlog 190개를 지우거나 이 준비 기능의 완료율에 합산하지 않는다.

COV-D03의 이번 구현 선택은 기존 private audit spool에 불변·비권한 자료를 보존하는 것이다. 계획의 수명은 동일 Service instance, 30분, 동일 Work/binding/producer/관측 basis로 제한한다. 이 선택은 새 owner 승인 형식이나 실행 grant가 아니다. 실제 owner action 등록은 기존 owner 계약을 사용한다. 모델 boolean이나 준비안 hash를 승인으로 사용하지 않는다.

## 제공 도구

| 도구 | 동작 | 권한·결과 경계 |
| --- | --- | --- |
| inputs_prepare | 기존 workflow.inputs와 Work record/status/next에서 완전 입력과 현재 basis 확보 | 원래 stdout bytes/base64/SHA 보존. 모델 소비·실행 허가 아님 |
| action_prepare | D4의 7개 tool에 대한 공통 fence·native key·revision/parent 자동 구성 | caller 의미 입력 누락은 질문. approval=null 초안, owner 등록 없음 |
| contract_prepare | session/document/execution/completion/reentry/role/template/discovery/profile/capsule의 기존 validator | 제공된 JSON/body 원문 유지. artifact 구조만 검증, operation/state/실행 승인 아님 |
| approved_action_prepare | 이미 owner policy에 pin된 action을 새 현재 준비안으로 검토 | 기존 bytes/key 그대로 보존. owner pin 경로 비공개, policy가 없으면 숨김 |
| plan_read | opaque plan ID와 SHA로 원래 준비안 재조회·basis 재검사 | 동일 instance/cache 참조·SHA·scope·TTL 필요. 복구·수정·재실행 없음 |
| action_confirm | 현재 준비안과 기존 owner action의 exact bytes/pin 대조 | 원래 D4 invocation 식별자만 반환. D4 admission·native precondition·dispatch는 NOT_RUN |

D2 SCHEMAS/transfer NAMES에 위 6개를 명시 연결하고 D4의 읽기 위임을 재사용한다. action tool 집합 7개와 승인 경로는 유지한다. local 추가 이름을 기존 remote gateway allowlist에 넣지 않는다. public bundle도 명시 producer 파일 목록을 재사용한다. 실제 SDK/client 노출은 검증하지 않았다.

## 자동 구성과 원문

session의 expected_sequence는 native status, expected_generation은 native next의 document_generation에서 각각 복사한다. 두 counter를 비교하거나 timestamps로 해석하지 않는다. active token/input_digest/source_snapshot은 현재 native active 자료에서만 취한다. active token이 필요한 요청에서 다른 session label·변경된 token·manifest를 거부하고 selection source·출력 reference를 대조한다. claim/resume의 실제 live-owner admission은 원래 core가 수행한다. session ID는 협력적 label이며 인증된 사람/대화 신원으로 승격하지 않는다.

document의 revision/supersedes는 최신 등록 manifest, parent_ids는 최신 등록 reference로 구성한다. 같은 문서의 과거 parent reference나 다른 Work 출력으로 대체하지 않는다. body/context/count 문자열을 요약·수정하지 않는다. core document parser/Markdown 검사와 기존 D4의 schema/version·body/context·owner 검사는 유지한다. 최신 등록 reference가 dependency-fresh/내용 승인이라는 주장은 하지 않는다.

user가 제공하는 source snapshot은 기존 native 문서의 attribution 계약이다. M2는 Git/worktree/provider를 자동 탐색하지 않는다. basis_scope는 등록 Work/binding/producer/native read 관측으로 명시하며 live_source_scan은 NOT_RUN이다. 파일·보호 oracle·lease·정책·source·input의 실제 dispatch 검사는 원래 core/D4가 lock 아래 다시 수행해야 한다.

## Core·D4 분리

`integration_mutation_contract.action_shape`는 기존 D4의 닫힌 JSON/body/context/owner 형태 검사다. 실행 초안에서만 누락 approval을 자료로 표현할 수 있으며 기본값은 허용하지 않는다. 실제 `native_action`은 기본 검사 뒤에 decision 파일 SHA/schema·host pin·실행 가능성을 계속 검사한다. D4 Policy.action은 기존처럼 native_action을 호출한다. M2에는 dispatch·apply·복구·Policy 생성 경로가 없다.

session validate는 고정 `golem_agent_request_validate`를 호출하는 CLI 읽기 branch로 추가했다. store를 열거나 session call/resume을 호출하지 않는다. profile validate도 기존 parse/digest CLI 경로를 재사용한다. metadata/contract validator가 exit 0이어도 native 상태 충족·QA PASS·실행 가능성을 판정하지 않는다. native validator 실패·timeout·손상 응답은 원문과 실패 spool을 보존하며 준비안을 정상으로 봉인하지 않는다.

## 불변 저장·수명·재조회

생성 요청의 preparation_request_id는 scope별 조회 상관 label이다. native key나 D4 request_id가 아니며 권한도 아니다. 같은 상관 ID와 정확히 같은 입력으로 재요청하면 원래 준비안만 재검사·반환한다. 입력을 바꾸면 conflict, basis/TTL이 바뀌면 stale/expired로 차단한다. 원래 key·bytes·D4 request ID를 갱신하거나 새 실행으로 전환하지 않는다.

native key와 D4 request ID는 최초 준비 시 생성해 불변 plan에 보존한다. owner가 별도 검토·등록한 action을 읽는 경우 기존 native key/bytes를 다시 만들지 않는다. plan_id→SHA는 Service 내부 cache에 보관하므로 모델이 임의 hash와 파일을 제시해서 현재 준비안으로 인증할 수 없다. plan.json은 private no-follow/single-link/byte/stamp 검사를 거쳐 읽는다. 반환 plan은 owner 경로를 가린 projection이며 plan_sha256은 저장된 원본의 SHA다.

재시작 후 cache가 없는 준비안은 MCP에서 재인증하지 않는다. 원본 audit 파일은 보존하며 owner가 확인한다. 새 서비스에서는 현재 승인 action을 approved_action_prepare로 새로 검토할 수 있지만 기존 action 자체를 변경하거나 이전 COMMIT_UNKNOWN을 해결하지 않는다. 실제 D4의 기존 미확정 효과·quarantine·중복 key/결과·owner/lease·보호 검사는 그대로 남는다. action_confirm은 그 admission을 실행했다고 주장하지 않는다.

Work record 전후 bytes와 record/status/next의 session sequence를 대조한다. 준비 완료 후 다시 같은 basis를 검사한다. 조회/확인은 TTL을 관측 전후에 모두 검사한다. 원자 snapshot이나 읽은 뒤 상태 고정을 보장하지 않는다. 사후 plan/action bytes 변경·다른 binding/Work·producer/정책·head·sequence·token/lease/boot 관측 변화는 차단하며 자동 repair/rebase가 없다.

기존 shared audit quota를 먼저 검사한다(생성 최대 10 read slot, 조회/확인 4). native stdout/stderr와 metadata headroom, plan 1 MiB·instance cache 64개·관측된 spool 개수 한도를 둔다. quota는 예약/물리 디스크 보장이 아니며 동시 프로세스의 공유 audit admission 보장은 기존 계약과 같다. 자동 삭제·회전·새 registry 우회는 없다. prepare 결과 예산이 부족하면 자르지 않는다.

## 수작업 입력 측정

session claim fixture에서 caller는 ttl_ms/source_snapshot/byte_budget 3개 native 필드를 제공하고 adapter가 공통 native 필드를 구성한다. native_request_fields, derived_fields, caller_fields 및 별도 transport selector 수를 기록한다. 이것은 native field 입력 수 비교이며 agent 성공·사용성 실험·token 절감·실제 처리 시간 측정이 아니다. 문서 의미·evidence·승인은 자동 작성하지 않는다.

## 검증·보존

정적 profile은 source/함수 구조, schema→literal handler, M1 고정 validation argv, owner-policy 전달, cache/SHA/binding/TTL/current basis, 순수 shape와 실제 D4 승인 검사를 따로 대조한다. frozen 134개 ID와 남은 milestone/권한을 검사한다. 해석되지 않은 실행이나 일반 동적 call graph를 인증하지 않는다.

제품 fixture는 임시 registry/Work와 가짜 native validator만 사용한다. 실제 client/사용자 Work E2E는 NOT_RUN이다. C API fixture는 임시 unit 데이터만 사용하며 CLI/client 종단 시험을 실행하지 않는다. 최종 회귀 수치와 재생성 결과는 아래 완료 기록에 갱신한다.

원본 Golem·활성 Codex/Claude 연결·설정·launcher·승인·pin·기존 Work/evidence/CAS/journal·보호 계약을 변경하지 않는다. 기존 미커밋/미추적 M0/M1 변경을 보존하며 commit/push·실제 정책 적용·배포·자동 재개·provider 전달을 하지 않는다.

## 재현 명령과 최종 기록

```sh
GOLEM_M2_COMPONENT_CLI="$PWD/build/m1-read/golem" PYTHONPATH=tools python3 -m unittest test_integration_m2
GOLEM_M2_COMPONENT_CLI="$PWD/build/m1-read/golem" PYTHONPATH=tools python3 -m unittest discover -s tools -p 'test_integration*.py'
PYTHONPATH=tools python3 -m unittest discover -s tools -p 'test_capability_*.py'
python3 tools/capability_check.py --root "$PWD"
python3 tools/capability_refresh.py --root "$PWD"
cmake --build build/m1-read --target golem_cli golem_test_agent_session golem_test_document golem_test_execution golem_test_workflow
ctest --test-dir build/m1-read -R '^(agent_session_api|document_api|execution_api|workflow_api)$' --output-on-failure
```

macOS의 M2 제품 fixture 35개(명시 opt-in된 순수 session-validate CLI component 1개 포함), M2 정적 변형 fixture 8개, C API unit fixture 4개를 실행했다. CLI component는 임시 JSON만 입력받고 Work 경로나 client/server를 시작하지 않는다. 실제 core parser로 정상·unknown operation·추가 approval 필드·중복 JSON key를 확인한다. 전체 integration 대상은 253개, capability 대상은 325개다. 선택 SDK/gateway 부재로 기존 18개는 skip이다. SDK 설치·실제 stdio/client/native Work 종단 실행으로 바꾸지 않는다.

검토 원장은 명시 source/근거 525개·관측 2,171개·capability 1,115개와 product source 429개다. 기존 tracked index 897개와 boundary 검토를 유지하고 새 두 runtime 모듈을 개발 분석 파일로 제외하지 않는다. 검토 모델은 author의 명시 source/함수/효과 재검토로 갱신했으며 checker/renderer가 자동 갱신하지 않는다. frozen M1 120개·M2 준비 의존 134개와 미제공 native delivery 190개를 각각 유지한다.

최종 성공 판정은 단순 해시/exit 0가 아니라 closed schema·필드/호출·불변 참조·현재 관측·owner 경계와 음성 변형 fixture의 결과를 함께 대조한다. 여전히 실제 binding/receiver 신원·계약의 의미 품질·현재 source/정책·실행 성공·제품 수용을 정적/fixture 통과로 인증하지 않는다. actual client E2E·Linux/Windows·CI·commit/push는 NOT_RUN이다.


## M3 완료 후 현재 상태 (2026-10-26)

[M3 구현 기록](mcp-m3-task-actions.ko.md): 고정 backlog 60개를 새 typed action 20개·기존 D4 7개 및 M2 준비 계약에 연결했다. source/근거 529개·관측 2,215개·capability 1,139개·product source 430개, 선택/저장소 blocker 0이다. tracked baseline 897개와 기존 callback/TRY/publication guard·boundary 계약은 유지한다. M4 83/M5 47, delivery 130개와 owner 83/unsupported 17은 남긴다. M1의 120개·M2의 134개 표는 당시 의존성 근거이며 M3 완료는 별도의 고정 60개 표로 대조한다.

검증: M3 제품 fixture 19개, M3 정적 fixture 9개, 전체 integration 272개(254 통과/18 skip), capability 334개, C API unit 25개 통과. 실제 client/Work E2E·Linux/Windows·CI·commit/push는 NOT_RUN이다. 기존 연결·승인·원본·Work·staging을 변경하지 않는다.
