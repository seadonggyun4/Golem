# M1 읽기 기능 구현과 경계

## 구현 범위

M0의 고정 M1 backlog 120개를 유지한 채 D2 읽기 facade와 core 계약에 대조한다. 목록 원본은 `tools/capability_m1_coverage_registry.py`의 BASELINE_IDS/M1_COVERAGE이며, 검사기는 원본을 갱신하지 않는다. 정적 연결은 `capability_m1.py`, backlog 대조는 `capability_m1_coverage.py`, 최종 목록/누락 검사는 기존 `capability_check.py`가 담당한다. 도구 존재·SHA·선언·fixture 성공은 실제 client 전달이나 제품 수용 PASS가 아니다.

기존 D2 7개에 새 typed 읽기 21개를 연결했다. workflow, template, role, session context, binding inspect, committed document metadata, context, discovery artifact, journal, runtime profile, 진단, native validation, completion/reentry report와 execution render/bundle inspect·verify, approval/reentry status가 Work 범위의 읽기다. artifact, usage, revision, configuration, bundle, events는 별도의 owner resource 선택이 필요하다. D4는 같은 D2 Service로 읽기를 전달한다. remote gateway의 기존 읽기 7개 허용 집합은 고정되어 새 local 도구가 자동 위임되지 않는다.

## Core와 D2 계약

- 모델은 project/work ID와 닫힌 operation·원본 JSON bytes를 제공한다. CLI·Work·spool 경로와 argv는 고정 builder가 구성한다. 임의 명령·파일 경로·수신자는 받지 않는다.
- 기존 transfer scope의 도구명 교집합과 D1 `record` 권한을 재검사한다. 새 이름을 기존 scope에 자동 추가하지 않는다. 새 코드의 producer pin은 owner의 향후 검토 대상으로만 바뀐다. 현재 배포·승인·연결은 갱신하지 않았다.
- native 읽기는 전후 Work record가 같아야 전달한다. quota, private spool, 정해진 환경, full output, 크기 한도를 유지한다. native 실패·timeout·malformed/duplicate JSON·drift·예산 초과는 결과를 전달하지 않고 spool에 실패와 원본을 보존한다. 자동 재시도·복구·삭제는 없다.
- native stdout은 원래 bytes의 base64·길이·SHA와 함께 전달한다. JSON/text projection은 별도다. artifact raw/window와 output bytes에도 원문 경로가 있다. 크기 초과를 잘라 성공으로 반환하지 않는다.
- context의 선택적 token-count proof는 제공된 JSON bytes만 private spool에 기록한다. core의 digest/tokenizer/budget 검사는 그대로 남는다. 후보의 0-token 계수를 render 성공으로 바꾸지 않는다.
- completion/reentry의 새 `inspect`는 store를 read-only로 열고 report의 project 인자를 false로 전달한다. 기존 `report`의 명시적 projection 동작은 유지한다. reentry status도 read-only로 연다. validate 성공은 구조적 유효성과 acceptance=false를 JSON으로 반환한다.

## 선택적 resource 계약

사용자가 채택한 `golem.integration-read-resources.v1`은 기존 D1/D2 권한과 분리된 선택적 계약이다. owner가 project/work/resource ID 및 각 파일의 ID·논리 이름·절대 경로·SHA-256·허용 도구를 명시한다. 계약 SHA, transfer SHA, producer 일치, private policy, literal owner opt-in 세 인자가 모두 필요하다. `integration_read_resources.py schema|plan`은 schema/코드 pin을 채운 검토안을 반환할 뿐 파일을 선택·읽거나 승인·설치를 만들지 않는다.

각 파일은 no-follow descriptor traversal로 한정해서 읽는다. symlink, hardlink, directory, drift, 잘못된 digest를 거부한다. 파일당 1 MiB, aggregate 8 MiB, resource/file 각각 64개, 논리 이름 깊이 8의 한도를 둔다. private copy의 유한 파일만 core helper에 전달하며, 원본 기록의 cwd·path·manifest provenance를 따라 외부 자료를 탐색하지 않는다. 처리 후 같은 파일 집합을 재검사한다. 모델 catalog는 ID·논리 이름·SHA·허용 도구만 제시한다.

bundle의 lineage/CAS/output/replay/cost와 events는 명시 선택된 snapshot에서만 읽는다. 특히 events의 native API는 admission directory를 요구하므로 Work 경로를 admission 경로로 추정하지 않는다. live worker ring/SSE reader의 ownership을 만들거나 이전하지 않는다. cursor stale 오류를 숨기거나 cursor 없이 재시도하지 않는다.

usage의 미확인 비용은 null로 유지한다. billing receipt의 자기 선언이나 파일 SHA를 delegated billing authority로 인정하지 않는다. billing_view는 보고된 totals와 선언된 export/receipt만 보여 주며 독립 검증·reconcile·Work 비용 배정은 false다. revision의 저장된 PASS/current/latest 주장도 historical capture 안에 두고 live native acceptance/remote latest를 false로 표시한다. 모든 콘텐츠는 UNTRUSTED_DATA다.

## 120개 backlog의 해석

원래 ID를 삭제하지 않는다. 동일 core의 C/TS/Python wrapper와 borrowed handle·encoder는 각각 새 MCP 도구로 만들지 않는다. caller-owned runtime/reader/FILE/graph handle은 HOST_DEPENDENCY로 명시하고 native 선언/구현 목록은 유지한다. 외부에서 호출 가능한 읽기 의미는 명시된 facade로 연결한다. 이는 해당 low-level API를 실제 호출했다고 주장하는 것이 아니다.

혼합 CLI root의 읽기와 변경 기능을 구분했다. context publish는 M3, discovery의 새 source/Git capture는 기존 native snapshot과 같은 M3 준비/변경 경계다. billing 독립 reconciliation과 QA 실행은 M4다. execution의 기존 bundle inspect/verify와 render는 report_read에 연결하고 committed document metadata의 execution_receipt만 허용한다. owner entrypoint/instruction/승인·gateway·hook policy의 실제 check/plan/apply는 COV-D01의 owner 경로와 M6에 남는다. M1은 그 자료의 선택된 manifest/managed block/schema/stored plan을 읽는다. 이 잔여 기능을 M1 지원으로 승격하지 않는다. 기존 M3~M6 backlog는 계속 검사한다.

M1의 읽기 코드·정적·fixture 경계와 실제 client 검증 완료는 다르다. 실제 Codex/Claude/native Work E2E는 NOT_RUN이며, M7/M8에서 실행해야 할 조건으로 유지한다. 새 resource 계약을 실제 승인·자료·활성 연결에 적용하지 않았다.

## 검증과 보존

검증은 macOS의 정적 profile, 가짜 receiver와 임시 D2/resource fixture, 기존 integration 회귀, warnings-as-errors C 빌드 및 completion/reentry/workflow의 C unit fixture를 사용한다. 실제 사용자 Work·client E2E·network/provider 전달·commit·push는 수행하지 않는다. 테스트 참조는 선언 확인과 실행 결과를 구분한다. 최종 수치와 skip 사유는 아래 검증 완료 기록에 구분한다.

원본 저장소, 활성 Codex/Claude 설정·launcher·approval·registry·policy·producer pin·evidence·CAS·journal·receipt·Work와 보호 계약은 변경하지 않는다. 개발 worktree의 기존 미커밋·미추적 M0 구현은 보존한다.

## 재현 명령

```sh
PYTHONPATH=tools python3 -m unittest test_integration_m1 test_integration_m1_resources
PYTHONPATH=tools python3 -m unittest discover -s tools -p 'test_integration*.py'
PYTHONPATH=tools python3 -m unittest discover -s tools -p 'test_capability_*.py'
python3 tools/capability_check.py --root "$PWD"
python3 tools/capability_refresh.py --root "$PWD"
cmake --build build/m1-read --target golem_cli golem_test_completion golem_test_reentry golem_test_workflow
ctest --test-dir build/m1-read -R '^(completion_api|reentry_api|workflow_api)$' --output-on-failure
```

source reader가 sandbox Git 경고를 거부한 실행은 성공으로 세지 않는다. 검사를 약화하지 않고 동일 개발 worktree의 host에서 정적·capability 회귀를 재실행했다. callback fixture의 SDK double은 실제 SDK/client 결과가 아니다. 선택 SDK/gateway 의존성이 없는 회귀는 skip이며 NOT_RUN으로 남는다.

## 고정 M1 backlog 대조

읽기 facade 84, 공통 core facade 7, 내부 의존 20, owner 경계 5, 혼합 읽기/변경 3, source 준비 경계 1이다. 각 행의 ID·operation·근거와 잔여 단계는 원장 JSON의 `m1_read_coverage`에도 담는다. 아래 경계 행을 지원 완료 숫자에 합산하지 않는다.

| 원래 capability ID | 판정 | 읽기 경로 | 후속 단계 |
| --- | --- | --- | --- |
| session.context | READ_FACADE | session_read / context | — |
| workflow.inputs | READ_FACADE | workflow_read / inputs | — |
| workflow.next | READ_FACADE | workflow_read / next | — |
| workflow.select | READ_FACADE | workflow_read / select | — |
| workflow.trace | READ_FACADE | workflow_read / trace | — |
| cli.route.template | READ_FACADE | template_read / list, show, validate, instantiate | — |
| cli.route.capsule | READ_FACADE | native_validate / capsule | — |
| cli.route.context | MIXED_READ_ACTION | context_read / render, markdown, read | M3 |
| cli.route.discovery | MIXED_READ_ACTION | discovery_read / validate, report | M3 |
| cli.route.events | READ_FACADE | events_read / export | — |
| cli.route.lineage | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| cli.route.output | READ_FACADE | bundle_read / output | — |
| cli.route.replay | READ_FACADE | bundle_read / replay | — |
| cli.route.workflow | READ_FACADE | workflow_read / inputs, next, select, trace | — |
| cli.dispatch.completion.check | READ_FACADE | completion_check | — |
| cli.dispatch.completion.validate | READ_FACADE | native_validate / completion | — |
| cli.dispatch.context.markdown | READ_FACADE | context_read / render, markdown, read | — |
| cli.dispatch.context.read | READ_FACADE | context_read / render, markdown, read | — |
| cli.dispatch.context.render | READ_FACADE | context_read / render, markdown, read | — |
| cli.dispatch.discovery.report | READ_FACADE | discovery_read / validate, report | — |
| cli.dispatch.discovery.snapshot | PREPARATION_BOUNDARY | caller-owned internal contract | M3 |
| cli.dispatch.discovery.validate | READ_FACADE | discovery_read / validate, report | — |
| cli.dispatch.doctor.clock | READ_FACADE | diagnostic_read / clock, work | — |
| cli.dispatch.doctor.work | READ_FACADE | diagnostic_read / clock, work | — |
| cli.dispatch.document.inspect | READ_FACADE | document_read / inspect | — |
| cli.dispatch.document.validate | READ_FACADE | native_validate / document | — |
| cli.dispatch.events.jsonl | READ_FACADE | events_read / export | — |
| cli.dispatch.events.otlp | READ_FACADE | events_read / export | — |
| cli.dispatch.events.prov | READ_FACADE | events_read / export | — |
| cli.dispatch.lineage.trace | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| cli.dispatch.lineage.verify | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| cli.dispatch.output.read | READ_FACADE | bundle_read / output | — |
| cli.dispatch.role.template | READ_FACADE | role_read / template, validate | — |
| cli.dispatch.role.validate | READ_FACADE | role_read / template, validate | — |
| cli.dispatch.work.capsule | READ_FACADE | native_validate / capsule | — |
| cli.dispatch.work.replay | READ_FACADE | bundle_read / replay | — |
| cli.dispatch.workflow_template.instantiate | READ_FACADE | template_read / list, show, validate, instantiate | — |
| cli.dispatch.workflow_template.list | READ_FACADE | template_read / list, show, validate, instantiate | — |
| cli.dispatch.workflow_template.show | READ_FACADE | template_read / list, show, validate, instantiate | — |
| cli.dispatch.workflow_template.validate | READ_FACADE | template_read / list, show, validate, instantiate | — |
| native.golem_adapter_descriptor_current | READ_FACADE | diagnostic_read / adapter_current | — |
| native.golem_harness_compatible | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_harness_observation_encode | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_harness_probe_encode | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_context_render | READ_FACADE | context_read / render, markdown, read | — |
| native.golem_context_read | READ_FACADE | context_read / render, markdown, read | — |
| native.golem_discovery_validate | READ_FACADE | discovery_read / validate, report | — |
| native.golem_discovery_report | READ_FACADE | discovery_read / validate, report | — |
| native.golem_document_generation | READ_FACADE | document_read / inspect | — |
| native.golem_document_inspect | READ_FACADE | document_read / inspect | — |
| native.golem_document_body | READ_FACADE | evidence_read | — |
| native.golem_document_metadata | READ_FACADE | document_read / inspect | — |
| native.golem_event_reader_open | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_event_reader_refresh | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_event_reader_read | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_event_reader_close | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_runtime_event_sse | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_digest_file | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_journal_checkpoint_get | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_journal_inspect | READ_FACADE | journal_read / inspect, replay | — |
| native.golem_journal_replay | READ_FACADE | journal_read / inspect, replay | — |
| native.golem_lineage_run_id_borrow | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_lineage_stats_get | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| native.golem_lineage_stage_get | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| native.golem_lineage_node_get | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| native.golem_lineage_parents | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_lineage_predecessors | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| native.golem_lineage_verify | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| native.golem_lineage_load | READ_FACADE | bundle_read / lineage_trace, lineage_verify | — |
| native.golem_runtime_report_get | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_runtime_run_borrow | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_worker_events | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_admission_events | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_runtime_cursor_format | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_runtime_event_name | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_runtime_profile_current | READ_FACADE | profile_read / current | — |
| native.golem_work_history | READ_FACADE | history_read | — |
| native.golem_work_record | READ_FACADE | work_inspect | — |
| native.golem_session_fence_check | HOST_DEPENDENCY | caller-owned internal contract | — |
| native.golem_document_graph_evaluate | HOST_DEPENDENCY | workflow_read / select, trace | — |
| native.golem_workflow_select | READ_FACADE | workflow_read / select | — |
| native.golem_workflow_inputs | READ_FACADE | workflow_read / inputs | — |
| native.golem_workflow_trace | READ_FACADE | workflow_read / trace | — |
| native.golem_workflow_next | READ_FACADE | workflow_read / next | — |
| native.golem_workflow_template_validate | READ_FACADE | template_read / list, show, validate, instantiate | — |
| native.golem_workflow_template_builtin | READ_FACADE | template_read / list, show, validate, instantiate | — |
| native.golem_workflow_template_expand | READ_FACADE | template_read / list, show, validate, instantiate | — |
| native.golem_workflow_template_instantiate | READ_FACADE | template_read / list, show, validate, instantiate | — |
| operation.agent_session.request_schema.context | READ_FACADE | session_read / context | — |
| operation.agent_session.request_schema.next | READ_FACADE | work_inspect | — |
| operation.agent_session.request_schema.status | READ_FACADE | work_inspect | — |
| operation.policy.ap_request.status | READ_FACADE | approval_read / status | — |
| operation.workflow.rc_request.evaluate | READ_FACADE | role_read / evaluate, status | — |
| operation.workflow.rc_request.status | READ_FACADE | role_read / evaluate, status | — |
| operation.reentry.re_validate.status | READ_FACADE | reentry_read / status | — |
| operation.agent_session.shape.inspect | READ_FACADE | binding_read / inspect | — |
| operation.golem.golem_binding_call.GOLEM_BINDING_VALIDATE | SHARED_CORE_FACADE | native_validate / capsule, adapter | — |
| operation.golem.golem_binding_call.GOLEM_BINDING_REPLAY | SHARED_CORE_FACADE | native_validate / capsule, adapter | — |
| operation.golem.golem_binding_call.GOLEM_BINDING_DESCRIBE_ADAPTER | SHARED_CORE_FACADE | native_validate / capsule, adapter | — |
| surface.bindings.native.bridge.c.commands.read | SHARED_CORE_FACADE | native_validate / capsule, adapter | — |
| surface.bindings.typescript.index.d.ts.commands.read | SHARED_CORE_FACADE | native_validate / capsule, adapter | — |
| surface.bindings.typescript.index.mjs.commands.read | SHARED_CORE_FACADE | native_validate / capsule, adapter | — |
| surface.bindings.typescript.native.addon.c.commands.read | SHARED_CORE_FACADE | native_validate / capsule, adapter | — |
| surface.src.cli.adapter.c.commands.read | READ_FACADE | diagnostic_read / noop_adapter, adapter_current | — |
| surface.src.cli.agent_session.c.commands.read | READ_FACADE | work_inspect | — |
| surface.src.cli.execution.c.commands.read | READ_FACADE | report_read / execution_render, execution_bundle_inspect, execution_bundle_verify | — |
| surface.src.cli.work.c.commands.read | READ_FACADE | bundle_read / cost, replay | — |
| surface.tools.agent_entrypoint.py.commands.read | OWNER_BOUNDARY | configuration_read / entrypoint, saved_plan | M6 |
| surface.tools.agent_io.py.commands.read | READ_FACADE | artifact_read / view, report, raw, record, procedure, measure, facts | — |
| surface.tools.agent_lifecycle.py.commands.read | READ_FACADE | artifact_read / lifecycle | — |
| surface.tools.billing_evidence.py.commands.read | MIXED_READ_ACTION | usage_read / totals, billing_view | M4 |
| surface.tools.evidence_adapters.py.commands.read | READ_FACADE | artifact_read / declaration, review, research_outcome | — |
| surface.tools.evidence_export.py.commands.read | READ_FACADE | artifact_read / export | — |
| surface.tools.instruction_bundle.py.commands.read | OWNER_BOUNDARY | configuration_read / instruction_manifest, saved_plan | M6 |
| surface.tools.integration_gateway_contract.py.commands.read | OWNER_BOUNDARY | configuration_read / schemas, saved_plan | M6 |
| surface.tools.integration_hook_contract.py.commands.read | OWNER_BOUNDARY | configuration_read / schemas, saved_plan | M6 |
| surface.tools.integration_mutation_contract.py.commands.read | OWNER_BOUNDARY | configuration_read / schemas, saved_plan | M6 |
| surface.tools.provider_costs.py.commands.read | READ_FACADE | usage_read / provider_cost | — |
| surface.tools.status_collector.py.commands.read | READ_FACADE | revision_read / relations, saved_status | — |
| surface.tools.verify_agent.py.commands.read | READ_FACADE | artifact_read / conformance | — |

## 검증 완료 기록

macOS host의 최종 검증 대상은 capability 정적/변형 fixture 317개, integration 회귀 218개, 그중 M1 native/resource/callback/package-import fixture 47개다. integration의 18개는 선택 SDK/gateway 의존성 부재로 skip됐다(16 gateway, 1 SDK icon, 1 실제 stdio bundle fixture). 실제 SDK/client 호출 결과로 세지 않는다. 재사용한 usage/cost/evidence/judgment/revision/conformance helper 회귀 156개와 completion/reentry/workflow C unit fixture 3개도 통과했다. C CLI는 Debug, `GOLEM_WARNINGS_AS_ERRORS=ON`으로 컴파일했다. 실제 Codex/Claude/native Work E2E·외부 provider·CI·Linux/Windows는 NOT_RUN이다.

추가로 SDK 없이 public bundle을 임시 폴더에 풀고 Python module import만 하는 격리 fixture를 실행했다. 누락된 public helper 의존 파일을 재현하고 기존 명시 producer allowlist에 필요한 코드만 포함하도록 고쳤다. 이 검사는 server/client/launcher를 시작하거나 설치·정책·승인을 적용하지 않는다. resource quota는 두 capture stream과 metadata 공간을 계산하고 전달 직전 aggregate 용량을 다시 검사한다. 관측된 headroom은 예약/물리 여유 공간 보장이 아니다. 초과·실패 원문은 보존한다.

전수 원장 출구는 명시 source/근거 520개·관측 2,156개·capability 1,106개와 product source 427개를 대조한다. 고정 M1 120개에서 아직 실행하지 않은 owner/준비/변경 부분은 ID를 유지한 채 M3/M4/M6 경계에 남겼다. 그 외 실제 미제공 delivery 190개(M3 60/M4 83/M5 47), 기존 owner 관리 83개와 역사적 지원 제외 17개를 구분한다. M1 코드 검증을 실제 client 노출/전체 M1 장기 출구나 M2~M8 완료로 승격하지 않는다.
