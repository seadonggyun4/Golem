# M4 승인된 실행·QA·검증 증거 연결

고정 M4 backlog 83개를 기존 core·D2·D4·M2·M3와 별도 opt-in owner helper 효과 계약에 연결한다. 실제 client/Work E2E·외부 서비스 호출·승인 적용·commit/push는 NOT_RUN이다. 비용 inbox 경로는 첫 단계의 disposable accounting 재구성이며 실제 run의 복원·완료·정산이나 provider 인증을 뜻하지 않는다.

## 제공 경로와 권위

D2에 읽기 도구 4개를 추가하고, D4에 정확한 owner action 도구 7개를 추가했다. M2의 불변 준비·재조회·owner bytes 대조와 M3의 기존 경로를 재사용한다. 기존 scope에 새 이름을 자동 추가하지 않는다. 개발 producer 변경으로 기존 승인 자료를 자동 재인증하거나 활성 설치를 전환하지 않는다.

| 도구 | 연결한 동작 | 결과·권한 경계 |
| --- | --- | --- |
| execution_read | approval describe, receipt verify, authorized verify, CAS read/verify/receipt verify | 현재 core 검사를 요청하지만 read 성공이 QA 실행·새 승인·완료는 아님 |
| proof_read | render, verify, integrity, verify-dir | 정확한 native stdout 보존. hash/manifest 일치는 내용 진실성·수용 증명이 아님 |
| research_read | status/inspect/report/metrics/compare/validate/redaction validate/observability/bundle verify | 기존 core 선택 기능. report Markdown 유지, OTLP/PROV 출력은 로컬 자료이며 자동 업로드하지 않음 |
| cost_read | 선언된 첫 단계 accounting 재구성 | 같은 이름의 live run에 연결하거나 결과를 쓰지 않음. 기존 bundle_read cost도 유지 |
| evidence_import | bounded bytes를 scoped CAS로 import하고 receipt 발행 | put/import/receipt store의 기존 core 검증. 임의 외부 파일 경로를 모델에서 받지 않음 |
| execution_verify | exact owner action으로 read-only receipt verify | 실행·승인 consume·QA command를 호출하지 않음 |
| proof_publish | 검토된 pack을 private audit root에 게시 | 모델이 export 목적지를 선택하지 않음. artifact integrity와 사실 인증 분리 |
| research_request | case-create, attempt-plan, attempt-record, outcome-enroll, adjudicate, cohort-create, cohort-observe | 7개 operation을 닫힌 enum으로 명시. core record parser/reducer를 재사용 |
| research_export | case와 redaction policy로 원래 bundle export | private mutation spool에 생성, native 원본·manifest·privacy 경계 유지 |
| cost_inbox_reconcile | 동일한 bounded accounting 재구성을 exact owner action으로 요청 | 현재 native WorkRun을 갱신하는 API가 아니며 정산/단계 PASS를 만들지 않음 |
| helper_execute | 별도로 검토한 8개 helper군의 정확한 인자·효과 | D4 action과 추가 owner helper policy의 교집합. 기본 비활성 |

D2는 project_id/work_id와 닫힌 operation·자료만 받고, 실제 Work 경로는 기존 registry에서 가져온다. artifact의 파일 이름은 새 private snapshot 내부 이름으로만 사용하고 절대경로·parent 탈출을 거부한다. 읽기 전후 Work record 및 producer/pins·quota·전달 예산을 확인하고 원문을 잘라 성공 처리하지 않는다. 실패 spool과 raw output은 보존한다.

`execution_read`가 허용한 CAS 조회는 새 이름을 명시 승인한 Work의 CAS 범위다. 기존 evidence_read의 committed-reference 제한을 변경하지 않는다. 기존 read grant만으로 새 조회 scope가 생기지 않는다.

연결된 CLI alias는 같은 native operation 표현을 사용할 수 있다. research의 convenience wrapper별 문자열 문법을 모델에 다시 노출하지 않고, 같은 원래 core request의 7개 operation을 각각 명시 검증한다. generic call 하나의 존재를 모든 operation 제공 근거로 세지 않는다.

## 기존 QA 승인·실행 계약

prepare/finish/run은 기존 execution_request와 owner-pinned approval host·decision/request receipt·contract/shell contract pin을 계속 사용한다. `golem_execution_call_receipted`의 scope 재계산·host recheck·one-use consume intent·native lock/fence·protected source·owner/token/input·결과 유실 처리를 바꾸지 않는다. 준비안이나 helper policy가 native QA 승인을 대체하지 않는다.

receipted execution API 자체는 writable store와 승인 consume을 요구하는 mutation 전용이다. 이 API의 결과 읽기 경로는 기존 approval_read status이며, API를 read-only로 호출한다고 주장하지 않는다. 별도 verify/verify-authorized CLI branch는 operation이 정확히 verify인지 확인하고 read-only store에서 원래 golem_execution_call/golem_execution_call_authorized 검사를 호출한다. 원래 승인 실행 host는 그대로 유지한다.

M2 초안의 approval=null, native_state_preconditions_checked=false 및 action_confirm의 d4_admission=NOT_RUN을 유지한다. helper 초안에는 추가 owner 효과 계약이 필요하다는 blocker를 둔다. owner action을 검토하는 경우 별도 helper policy도 현재 범위와 대조한다. seal/cache/SHA/Work/binding/producer/TTL·동일 상관 ID·원래 native key/request ID·재시작 거부 계약을 유지한다.

## 별도 owner helper 효과 계약

사용자가 채택한 별도 선택적 계약은 `golem.integration-helper-effects.v1`이다. helper policy는 정확한 mutation_policy_sha256에 결합되며, helper_id별 project/Work·D4 action 파일의 원래 SHA·Python executable pin·고정 helper·정확한 argv JSON·cwd·immutable input pins·자식 executable pins·출력 root·효과·credential 파일 pin·최대 540초를 선언한다. argv는 JSON 배열을 보존하는 문자열이다. 중복 인자는 원문 그대로 처리하고, 반복된 scope/output flag도 모두 검사한다.

| helper군 | 닫힌 실행 mode |
| --- | --- |
| agent_io | run, observe, observe-history, procedure, judgment-write |
| agent_lifecycle | run |
| billing_evidence | reconcile, native-export |
| evidence_export | create, prepare-raw |
| hosted_usage | ingest, listen |
| provider_costs | fetch, ingest |
| status_collector | collect, --follow 금지 |
| usage_pipeline | init, pump, listen, run-claude, deliver, close, sync |

Python/module 선택은 고정 allowlist와 producer에서 오며 MCP caller가 argv·path·환경·실행 파일·credential을 전달하지 않는다. CLI의 --helper-policy/--reviewed-helper-policy-sha256/--approve-helper-effects 세 owner 인자가 모두 있어야 한다. 기존 읽기/QA 승인만 있으면 helper_execute를 숨기고 admission도 거부한다. 새로운 helper policy를 설치하거나 실제 승인 자료를 작성하지 않았다.

HOST_EXECUTION/FILESYSTEM_WRITE는 별도 필수 효과다. collector fetch에는 NETWORK/CREDENTIALS, listen/client 실행에는 NETWORK/CREDENTIALS/SERVICE, export 계열에는 EXPORT가 추가로 필요하다. credential 값은 명시된 private pin 파일에서만 받아 자식 환경에 넣고 helper policy·원문 응답으로 반환하지 않는다. 기본 HOME·ambient credential을 상속하지 않으며 Python/loader/Git 환경 주입을 거부한다. --cli/--work/--work-id/--project-id/--cwd의 알려진 매핑을 현재 승인과 대조한다. owner가 선택한 gh credential 사용과 openssl billing 검증·사용량 client 실행 파일도 별도 executable pin을 요구한다.

agent command/lifecycle plan은 원래 helper validator가 검사한다. facade는 알려진 plan·입력·자식 실행 파일의 pin 교집합만 추가로 대조하고 원래 reducer/expect predicate를 재구현하지 않는다. plan의 cwd/알려진 입력을 현재 승인과 대조한다. 새로운 OS sandbox, arbitrary command 의미 검사, descendant/network의 완전 관측을 보장하지 않는다. 이것은 원래 LOCAL_COOPERATIVE host 경계이며 owner가 정확한 명령과 효과를 검토해야 한다.

helper 출력 root는 기존 registry private audit 아래 `helper-output-<work_id>-...`의 명시 root로 제한한다. 알려진 output/state/directory/store 및 export positional 목적지를 그 범위와 대조한다. 기존 Work/project와 겹치거나 새 registry로 quota를 우회할 수 없다. 공유 bytes/entries/read quota를 dispatch 전후에 검사한다. 이는 디스크 예약이나 동일 UID의 비협력적 프로세스까지 차단하는 장치가 아니다. 무삭제·수동 capacity 검토 계약을 유지한다.

helper는 기존 D4 durable intent/writer/fence/current action pin/불확실 효과 격리를 사용한다. 같은 request ID는 원래 결과만 조회하고, 한 번 dispatch intent가 생긴 helper action은 새 request ID로도 재실행하지 않는다. 기존 D5 clearance로 동일 helper를 자동 재가동하지 않는다. 변경된 효과는 별도 owner 계약과 action 검토가 필요하다. 성공한 helper process의 stdout도 opaque base64 자료로 보존하고 QA PASS·provider 인증·Work 완료로 승격하지 않는다. timeout/nonzero/기록 실패·사후 helper policy 변경은 COMMIT_UNKNOWN이며 자동 재시도가 없다.

owner용 schema/producer plan 명령은 자료만 출력하며 policy를 적용하지 않는다:

```sh
PYTHONPATH=tools python3 tools/integration_helper_contract.py schema
PYTHONPATH=tools python3 tools/integration_helper_contract.py plan --input OWNER_PRIVATE_INPUT.json
```

## 비용·증거 해석 한계

native cost inbox는 caller가 소유한 pristine READY WorkRun에 한 번만 붙일 수 있는 in-memory API다. 이미 진행 중인 run에 attach하거나 원래 ledger를 공개 경로에서 복원한다고 가정하지 않는다. 이번 고정 bridge는 명시 capsule/run ID와 sealed sequence 1 snapshot 하나로 disposable 첫 entry만 구성하고, 원래 enable/sync/status/report/entry/totals/stage/options API를 호출한다. USD bounded profile이며 provider 호출·실제 Work store·journal·stage finish/PASS·settlement를 만들지 않는다. 다른 sequence/통화·missing/unsealed·충돌은 core/shape에서 거부한다. 후속 live host의 전체 단계 연결·취소 후 late accounting 운영을 이 경로의 완료로 주장하지 않는다.

금액이 cost_known=false이면 JSON null, 명시적 known-zero이면 "0"로 구분한다. 원래 report와 input snapshot은 audit 원문으로 보존한다. usage/cost totals·hosted scope·billing 서명/신뢰·aggregate API scope 비교는 기존 helper 규칙을 재사용한다. unknown/partial/unpriced 자료를 실제 무료 비용으로 만들지 않고, hash/서명·한 호출의 사용량을 독립적인 provider bill 인증·scope 전체 완전성·실제 수행 진실성으로 바꾸지 않는다.

proof와 research export는 로컬 artifact다. integrity_verified·source_projection_verified·native receipt·historical report의 의미를 유지하고 current QA PASS/수용/완료로 바꾸지 않는다. 실제 외부 전송·credential 사용·서버 수신·provider 호출 검증은 NOT_RUN이다.

## 검증과 재현

정적 M4 profile은 고정 4 read/7 action·schema/handler·owner helper scope/pins/effects·원래 QA host·원문/현재 관측·read-only verify·bounded accounting·83개 고정 행을 대조한다. 필수 guard 제거·인자 교환·권한/진실성 승격·native 경로 제거·backlog 변경의 음성 fixture를 둔다. 기존 M0 callback/TRY/publication guard·D2/D4/M1/M2/M3 검사를 계속 요구하며 checker가 검토 모델을 자동 갱신하지 않는다.

제품 fixture는 임시 registry/정책과 fake capture로 admission·불확실성·새 ID 재실행 차단·정확한 raw bytes·helper credential/output scope·quota·변경을 확인한다. opt-in component는 임시 JSON·inbox만 사용하는 native parser와 disposable accounting이다. 실제 client/Work E2E가 아니다. helper 회귀의 HTTP 서버는 localhost 합성 fixture이고 실제 외부 API를 호출하지 않는다.

검토 원장의 기존 coarse effect enum은 그대로 두었다. credential 사용은 NATIVE_READ/DISCLOSURE, service는 PROCESS/NETWORK, export는 DISCLOSURE/AUDIT_WRITE 등의 잠재 효과와 상세 notes로 기록하며, runtime helper policy에서는 CREDENTIALS/SERVICE/EXPORT를 별도로 명시 승인한다. 효과 이름을 삭제해 검사를 통과시키는 방식이 아니다.

```sh
cmake -S . -B build/m1-read -DGOLEM_BUILD_INTEGRATION_HOST=ON
cmake --build build/m1-read --target golem_cli golem_integration_host golem_test_proof_publication golem_test_research golem_test_cost
GOLEM_M2_COMPONENT_CLI="$PWD/build/m1-read/golem" GOLEM_M3_COMPONENT_CLI="$PWD/build/m1-read/golem" GOLEM_M4_COMPONENT_CLI="$PWD/build/m1-read/golem" PYTHONPATH=tools python3 -m unittest discover -s tools -p 'test_integration*.py'
PYTHONPATH=tools python3 -m unittest discover -s tools -p 'test_capability_*.py'
PYTHONPATH=tools python3 -m unittest test_agent_io test_agent_lifecycle test_usage_integrations test_provider_costs test_evidence_export test_status_collector test_usage_pipeline test_usage_pipeline_host test_provider_usage
python3 tools/capability_check.py --root "$PWD"
python3 tools/capability_refresh.py --root "$PWD"
```

빌드 옵션은 개발 build 디렉터리에만 적용하며 install·launcher·연결·실제 policy를 전환하지 않는다. 실제 E2E·외부 서비스·Linux/Windows·CI·commit/push는 NOT_RUN이다. 내장 디스크 부족을 피하는 fixture TMPDIR는 source reader의 build/비공개 제외 경로 밖 SSD 임시 폴더로 지정할 수 있다. 기존 연결·승인·registry·Work/evidence/CAS/journal·원본 저장소·staging은 보존한다.

## 고정 83개 처리표

아래 행은 실제 연결한 제한된 경로를 뜻하며 client 또는 native 실행 성공을 인증하지 않는다. `OWNER_EXACT_HELPER_EFFECTS`는 별도 owner helper 계약, `EXISTING_D4_QA_HOST`는 기존 native 승인 host, `FIRST_STAGE_DISPOSABLE_ACCOUNTING`은 앞서 설명한 제한적 accounting이다.

| Capability ID | 연결 경로 | Scope |
| --- | --- | --- |
| cli.route.cost | cost_read, bundle_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.route.evidence | evidence_import, evidence_read, execution_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.route.execution | execution_request, execution_verify | EXISTING_D4_QA_HOST |
| cli.route.proof | proof_publish, proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.route.research | research_request, research_export, research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.execution.call | execution_request | EXISTING_D4_QA_HOST |
| cli.dispatch.proof.integrity | proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.proof.publish | proof_publish | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.proof.render | proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.proof.verify | proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.proof.verify-dir | proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.attempt | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.bundle-verify | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.call | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.case | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.cohort | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.compare | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.export | research_export | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.inspect | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.metrics | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.observability | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.outcome | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.report | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.status | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.research.validate | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| cli.dispatch.work.cost | cost_read, bundle_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_approval_describe | execution_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_execution_call_receipted | execution_request, approval_read | EXISTING_D4_QA_HOST |
| native.golem_work_run_cost_borrow | cost_read, bundle_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_work_run_cost_inbox_enable | cost_inbox_reconcile | FIRST_STAGE_DISPOSABLE_ACCOUNTING |
| native.golem_work_run_cost_inbox_sync | cost_inbox_reconcile | FIRST_STAGE_DISPOSABLE_ACCOUNTING |
| native.golem_work_run_cost_inbox_status | cost_read | FIRST_STAGE_DISPOSABLE_ACCOUNTING |
| native.golem_cost_ledger_entry_get | cost_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_cost_ledger_report_get | cost_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_cost_ledger_totals_get | cost_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_cost_ledger_stage_totals_get | cost_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_cost_ledger_options_get | cost_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_evidence_put | evidence_import | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_evidence_import | evidence_import | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_evidence_verify | execution_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_evidence_read | evidence_read, execution_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_evidence_receipt_store | evidence_import | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_evidence_receipt_verify | execution_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_execution_call | execution_request, execution_read | EXISTING_D4_QA_HOST |
| native.golem_execution_call_authorized | execution_request, execution_read | EXISTING_D4_QA_HOST |
| native.golem_proof_render | proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_proof_verify | proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_proof_integrity | proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_proof_publish | proof_publish | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_proof_verify_directory | proof_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_call | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_inspect | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_report | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_status | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_metrics | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_metrics_report | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_compare | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_redaction_validate | research_read, research_export | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_bundle | research_export | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_bundle_verify | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| native.golem_research_observability | research_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.execution.call.finish | execution_request | EXISTING_D4_QA_HOST |
| operation.execution.call.prepare | execution_request | EXISTING_D4_QA_HOST |
| operation.execution.call.run | execution_request | EXISTING_D4_QA_HOST |
| operation.execution.call.verify | execution_verify, execution_read | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.research.rs_validate.attempt-plan | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.research.rs_validate.attempt-record | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.research.rs_validate.case-create | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.research.rs_validate.outcome-enroll | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.research.rs_is_cohort.cohort-create | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.research.rs_is_cohort.cohort-observe | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.research.rs_is_outcome.adjudicate | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| operation.research.rs_is_outcome.outcome-enroll | research_request | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| surface.src.cli.research.c.commands.action | research_request, research_export | FIXED_NATIVE_OR_SCOPED_ARTIFACT |
| surface.tools.agent_io.py.commands.action | helper_execute | OWNER_EXACT_HELPER_EFFECTS |
| surface.tools.agent_lifecycle.py.commands.action | helper_execute | OWNER_EXACT_HELPER_EFFECTS |
| surface.tools.billing_evidence.py.commands.action | helper_execute | OWNER_EXACT_HELPER_EFFECTS |
| surface.tools.billing_evidence.py.commands.read | helper_execute, usage_read | OWNER_EXACT_HELPER_EFFECTS |
| surface.tools.evidence_export.py.commands.action | helper_execute | OWNER_EXACT_HELPER_EFFECTS |
| surface.tools.hosted_usage.py.commands.action | helper_execute | OWNER_EXACT_HELPER_EFFECTS |
| surface.tools.provider_costs.py.commands.action | helper_execute | OWNER_EXACT_HELPER_EFFECTS |
| surface.tools.status_collector.py.commands.action | helper_execute | OWNER_EXACT_HELPER_EFFECTS |
| surface.tools.usage_pipeline.py.commands.action | helper_execute | OWNER_EXACT_HELPER_EFFECTS |


## 완료 기록

macOS warnings-as-errors CLI·기존 integration approval host·관련 unit build를 통과했다. M4 제품 fixture 34개(임시 core parser/accounting component 2개 포함), 정적 변형 fixture 11개, 기존 helper 회귀 192개와 native C API unit 37개가 통과했다. 전체 integration은 306개 중 288개 통과·기존 선택 항목 18개 skip, 전체 capability는 345개 통과다. 선택 gateway 16개·SDK icon 1개·실제 stdio MCPB 1개 skip을 제품 성공으로 계산하지 않는다.

helper 회귀의 localhost 합성 HTTP fixture는 sandbox socket 제한을 해제한 검증 환경에서 다시 확인했다. 실제 외부 API·credential·서비스 연결·실제 client/Work E2E는 실행하지 않았다. helper 출력의 기존 ancestor symlink와 반복 scope/output 인자도 거부 fixture로 확인했다. native unknown-money는 null, 명시 known-zero는 "0"로 구분했다.

최종 전수 원장은 source/근거 535개·관측 2,249개·capability 1,162개·product source 433개에서 선택/저장소 blocker 0이다. 새 cost inbox의 argv[2] operation을 별도 원장으로 추가해 기존 file 검토에 숨기지 않았다. M4 고정 83개를 연결했으며 M5 delivery 47개·owner 관리 83개·명시 unsupported 17개는 남겼다. 8개 generated artifact는 순수 재계산과 바이트 단위로 대조한다.

실제 외부 서비스·client/Work E2E·Linux/Windows·CI·commit/push는 NOT_RUN이다. 기존 연결·설정·launcher·승인·registry·실제 Work/evidence/CAS/journal·원본 저장소와 staging은 보존한다. 코드 연결은 명시한 bounded 계약 범위의 완료이며 provider 진실성·실행 수용·live accounting 운영이나 전체 제품 완료 인증이 아니다.
