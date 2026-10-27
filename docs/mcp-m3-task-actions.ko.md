# M3 일상 action 연결

M3의 고정 backlog 60개를 기존 core·D2·D4·M2 경로에 연결한다. 실제 client/사용자 Work E2E, 승인·설치·등록 적용, commit/push는 실행하지 않는다. 아래 기록은 정적·fixture 개발 검증 범위다.

## 도구와 기존 권위

새 action 20개와 기존 D4 7개를 같은 owner policy의 닫힌 tool enum·정확한 action 파일 pin으로 선택한다. MCP 호출 인자는 기존 project_id/work_id/action_id/request_id 네 개뿐이다. 모델이 native JSON·path·argv·approve boolean을 실행 호출에 넣을 수 없다. 기존 policy/transfer 파일과 활성 연결을 자동 재작성하지 않는다. 개발 중 바뀐 producer를 기존 승인으로 재인증하지도 않는다.

| 기능 | 새 action | 기존 core/CLI 경로 |
| --- | --- | --- |
| 세션 시작·갱신·반려 | session_start, session_heartbeat, session_reject_output | session call, agent reducer·lease·token·input/source·반려 승인 digest |
| native 연결 | binding_attach | agent binding attach, descriptor와 현재 token·sequence |
| workflow 역할 | role_enroll, role_assess | role call enroll/assess, 원래 template·역할·보호·계약 승인 검사 |
| 완료 | completion_finalize, completion_report | completion call finalize / report, 원래 completion predicate·historical renderer |
| 재진입 | reentry_decide, reentry_report | reentry call decide / report, failure/evidence·정책·별도 reentry counter |
| 문서 projection | document_project | document project, 등록된 ID/revision; 새 문서 내용 제출은 기존 document_submit |
| Work 생성 | work_create | work start / golem_document_store_create, 새 디렉터리·원래 Work specification |
| 맥락 게시 | context_publish | context publish, 원래 tokenizer count proof·source·입력 검사 |
| source snapshot | discovery_snapshot | discovery snapshot, 명시된 project 내 파일과 제한된 native Git capture |
| profile·run 연결 | profile_register, run_link | profile register/link, 원래 descriptive profile·binding·journal checkpoint 계약 |
| simulation | work_noop_run, adapter_noop_run | run --noop / adapter noop run-file, local.noop만 사용 |
| lineage | lineage_store | lineage store, sealed binary graph decode·모든 CAS target digest/size 검증 후 저장 |
| 승인 요청 | approval_request | approval call request, prepare/finish/run 범위의 pending 요청만 생성 |

고정 60개 ID의 분류는 `capability_m3_backlog_registry.py`에 유지한다. 기존 claim/begin/resume/reconcile/submit·document_submit 경로도 각 operation에 명시 대조한다. 읽기 면은 기존 M1/D2 경로를 재사용하고, 하나의 CLI call을 모든 operation 제공으로 세지 않는다. 저수준 journal append는 고정 noop transcript writer를 통해, lineage store는 제한된 sealed graph 도구를 통해 연결한다. 임의 journal frame 삽입·CAS 덮어쓰기·provider 호출·일반 shell dispatcher는 제공하지 않는다.

Work 생성은 이미 승인된 Work를 anchor로 한 별도 exact action이다. owner가 검토한 specification과 project 바로 아래의 새 단일 디렉터리 이름만 사용하며, 기존 디렉터리·symlink·기등록 Work ID를 생성 대상으로 채택하지 않는다. 생성 이후 D1 등록·읽기 grant·D2 전달 scope는 owner의 기존 registry 절차로 따로 처리한다. MCP가 새 Work를 자동 승인하거나 기존 등록을 교체하지 않는다.

## M2 준비·core 검증

기존 action_prepare·approved_action_prepare·plan_read·action_confirm을 재사용한다. M2에 새 실행 권한은 없다. 세션 sequence와 document generation을 서로 대체하지 않고, active token/input/source 및 등록 reference를 현재 관측에서 복사·대조한다. 의미 입력·승인 digest·evidence·가설은 작성하지 않는다. 불완전 초안은 질문으로 남기고 core validator를 실행하지 않는다. 30분·같은 instance·동일 Work/binding/producer/basis, 불변 원문 및 원래 native key/D4 request ID 계약을 유지한다.

completion은 원래 predicate version 1/2를 모두 허용한다. M2의 completion_schema_version 선택(생략 시 기존 v1)을 native schema_version으로 옮긴다. 역할 계약을 사용하는 v2를 v1로 자동 fallback하지 않는다. role enrollment는 core role validate에서 얻어 owner가 검토한 contract_digest를 action의 count_json attachment에 보존하고 --approve-contract로 그대로 전달한다. Python이 json-c serialization/digest를 복제하거나 대화 동의를 승인 digest로 만들지 않는다.

재진입은 M1 reentry_read status에서 확인한 별도 reentry_sequence를 caller가 명시한다. M2는 이를 session sequence에서 추정하지 않는다. 이 값의 native 현재성·실패/정책 충족은 실제 reducer가 다시 검사하며 준비 결과의 native_state_preconditions_checked는 false다. report sequence는 역사적 결과 선택이며 현재 완료 상태를 뜻하지 않는다.

기존 session/document/execution validator 외에 binding_request·role_request·approval_request·work_specification의 순수 CLI parser branch를 추가했다. store를 열기 전에 공개 core validator를 호출한다. profile/capsule도 기존 validator를 재사용한다. context count proof, run journal, adapter envelope, lineage binary 및 상태 의존 조건의 최종 검사는 각 원래 native 경로가 수행한다. shape 검사를 전체 native 문법/의미 검증으로 승격하지 않는다.

## D4 intent·효과·재조회

Service.call의 닫힌 schema, owner policy/action pins, D5 maintenance fence, Work lineage와 request ID, private immutable intent, writer lock, 기존 미확정 효과 격리와 no automatic retry를 공유한다. M3용 고정 argv builder를 호출하기 전후에도 기존 authorization과 action bytes 대조를 유지한다. native owner/lease/boot/clock/token/input/source/binding/보호 검사는 원래 core가 원래 store lock 아래 수행한다. 사전 조회나 action_confirm을 상태 예약/실행 승인으로 설명하지 않는다.

생성·discovery의 추가 파일 scope는 고정 owner action에서만 가져온다. discovery는 승인 project root와 명시된 내부 파일만 허용하고, parent 탈출·관리 Git 경로·symlink를 채택하지 않는다. Work 생성/공유 원본 파일을 삭제하거나 자동 repair하지 않는다. lineage/adapter의 저수준 CAS 쓰기는 원래 API에 lifecycle/policy 인증 기능이 없으므로 exact owner D4 scope 및 immutable CAS 계약으로 제한한다. 이를 workflow 등록·보호 oracle·실행 수용으로 인증하지 않는다.

모든 action stdout의 정확한 base64와 SHA를 보존한다. completion/reentry report는 원래 Markdown을 변형 없이 UTF-8 text와 base64로 반환하며 역사적 projection으로 표시한다. transport exit 0·원래 receipt·projection 생성 성공을 현재 QA PASS/완료/새 lease로 승격하지 않는다. timeout·비정상 종료·손상/기록 실패 뒤에는 기존 COMMIT_UNKNOWN과 Work 격리가 적용되고 자동 재실행하지 않는다. 같은 request ID는 원래 결과만 조회한다. 기존 D5 clearance 이후 M3 action의 재사용 방지는 tool+전체 native request digest로 판별한다.

공유 audit quota, 32개 owner action policy 한도, action/JSON c.LIMIT 및 native output/전달 예산을 유지한다. binary journal/graph도 bounded base64 입력만 허용한다. noop bundle은 private mutation spool에 생성하며 실제 에이전트 작업이 아니다. 무삭제 계약을 유지하고 새 registry로 용량 포화를 우회하지 않는다.

## 정적·fixture·회귀 검증

정적 profile은 20개 선언·D4/M2 handoff·owner/Work/token·creation/discovery 경계·순수 parser·고정 native 경로와 고정 backlog 60개를 대조한다. 검토된 source/AST/효과와 독립적인 필수 guard 검사를 함께 사용한다. 누락·잘못된 인자·상태/권한 승격·core parser 제거·임의 route 변경의 변형 fixture는 실패해야 한다. 원장/renderer가 모델을 자동 재검토하거나 변경된 hash만으로 계약을 인증하지 않는다.

제품 fixture는 임시 registry와 가짜 native reply/capture만 사용한다. 준비→owner exact bytes 등록 fixture→confirm→D4 intent/고정 dispatch double→동일 결과 조회의 합성 cycle을 검사한다. 이는 실제 Work/client E2E가 아니다. 별도 opt-in pure CLI component는 임시 JSON만으로 새 parser 4개와 completion v2의 정상·추가 필드 거부를 확인하며 Work를 열거나 lifecycle을 진행하지 않는다. C API unit은 기존 native guard/부정·복구·버전 경계를 확인한다.

### 재현 명령

```sh
cmake --build build/m1-read --target golem_cli golem_test_agent_session golem_test_document golem_test_execution golem_test_workflow golem_test_role_contract golem_test_completion golem_test_reentry golem_test_session_binding golem_test_approval golem_test_discovery golem_test_runtime_profile golem_test_lineage
GOLEM_M2_COMPONENT_CLI="$PWD/build/m1-read/golem" GOLEM_M3_COMPONENT_CLI="$PWD/build/m1-read/golem" PYTHONPATH=tools python3 -m unittest test_integration_m3
GOLEM_M2_COMPONENT_CLI="$PWD/build/m1-read/golem" GOLEM_M3_COMPONENT_CLI="$PWD/build/m1-read/golem" PYTHONPATH=tools python3 -m unittest discover -s tools -p 'test_integration*.py'
PYTHONPATH=tools python3 -m unittest discover -s tools -p 'test_capability_*.py'
ctest --test-dir build/m1-read -R '^(agent_session_api|session_binding_api|approval_api|document_api|workflow_api|role_contract_api|completion_api|reentry_api|execution_api|discovery_api|runtime_profile_(codec|invalid|cache|ownership|prepared)|lineage_(lifecycle|reentry|invalid|codec|ownership|capacity|storage|bounded|identity|nulls))$' --output-on-failure
python3 tools/capability_check.py --root "$PWD"
python3 tools/capability_refresh.py --root "$PWD"
```

최종 회귀·재생성 수치는 아래 완료 기록으로 갱신한다. 실제 Codex/Claude SDK 노출·실제 Work 종단·Linux/Windows·CI·commit/push는 NOT_RUN이다. 기존 활성 연결/승인/launcher·registry·실제 Work·evidence/CAS/journal와 원본 저장소의 기존 변경은 보존한다. 생산자 pin 갱신은 정적 개발 모델에만 반영하며 활성 승인 자료에는 적용하지 않는다.


### 완료 기록

macOS warnings-as-errors build가 통과했다. M3 제품 fixture 19개(실제 순수 CLI parser component 1개 포함), M3 정적 변형 fixture 9개와 기존 C API unit 25개를 실행해 통과했다. 전체 integration 272개 중 254개 통과·기존 선택 항목 18개 skip, 전체 capability 334개 통과다. skip은 선택 gateway 16개·SDK icon 1개·실제 stdio MCPB 1개다. SDK 설치나 실제 E2E로 바꾸지 않았다.

내장 디스크 공간이 부족한 검증 환경에서는 여유 공간이 있는 SSD의 별도 임시 폴더를 TMPDIR로 지정해 회귀를 재실행했다. source reader의 build/상태/비공개 제외 규칙은 그대로 유지한다. fixture 자체의 종료 정리 외에 사용자 자료를 삭제하지 않았다.

전수 정적 검사는 source/근거 529개·관측 2,215개·capability 1,139개·product source 430개에서 선택/저장소 blocker 0이다. M3 고정 60개는 모두 연결됐으며 후속 M4 83개/M5 47개, 총 130개와 owner 83개/unsupported 17개는 유지한다. generated artifact 8개는 재계산과 바이트 단위로 대조한다. 실제 실행/권한 충족/수용·client 검증 flag는 계속 false/NOT_RUN이다.


## M4 후 현재 기록 (2026-10-26)

[M4 계약·83개 처리표](mcp-m4-quality-evidence.ko.md): D2 read 4개·D4 action 7개를 추가하고 기존 core·M2·M3·QA host 및 별도 owner helper effects 계약에 연결했다. M4의 cost inbox는 첫 단계 disposable accounting이며 live run attach/정산이 아니다. 실제 외부 서비스·client/Work E2E는 NOT_RUN이다.

정적 source/근거 535개·관측 2,249개·capability 1,162개·product source 433개, 선택/저장소 blocker 0. 고정 M1 120/M2 준비 의존 134/M3 60/M4 83의 근거를 각각 유지하며, 남은 native delivery는 M5 47개다. owner 83개와 unsupported 17개를 유지한다. 기존 callback/TRY/publication guard·boundary·tracked baseline 897개를 약화하지 않는다.

M4 fixture 34개·정적 fixture 11개·helper 회귀 192개·C API unit 37개 통과. 전체 integration 306개(288 통과/18 skip), capability 345개 통과. 기존 연결·승인·원본 변경·Work·staging을 보존하고 install·승인 적용·실제 외부 서비스·E2E·CI·commit/push는 수행하지 않았다.
