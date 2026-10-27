# MCP 전 기능 연결: 소스 진입점 목록

상태: **설계용 정적 목록**, 기능 제공 완료·행동 검증 결과가 아니다. 작성일: 2026-10-26.
기준 소스: `2e690091a55f366d5f99580ee375fca7610f2f77`. [통합 설계와 구현 계획](mcp-full-coverage-plan.ko.md)의 M0 입력이다.

2026-10-26 재추출에서도 48 header/344 선언을 확인했다. 직접 정의 연결도 대조했으나
이후 전수 확장에서 344개 공개 API를 모두 원장에 연결하고 파일별 operation 검토를 마쳤다.
선택/저장소 정적 gate의 차단 항목은 0이며, 실제 MCP 제공·행동 검증과 구분한다.
[최신 scope 보고서](mcp-m0-repository-scope.md)와
[재검토 기록](mcp-m0-review-2026-10-26.ko.md)을 함께 본다. 아래 설계 입력 목록은
검토된 기능 coverage나 실제 MCP 제공 완료 표가 아니다.

주석을 제외한 public header의 `golem_*(` 이름을 수집하고 callback 반환 타입
`golem_status`를 제외했다. allocator/free/handle/codec와 host callback은 모델 도구로
일대일 노출하지 않는다. 하나의 `call` 함수 안 operation discriminator와 CLI 하위 명령,
private host API의 권한 의미는 이 어휘 목록만으로 전수 검사되지 않는다.
M0에서 각각 operation 단위로 분해·분류해야 하며 이 문서만으로 100% coverage를 주장하지 않는다.

## Public C header 진입점

48개 header, header별 합계 344개 이름. 같은 이름의 복수 header 선언은 별도 항목이다.

| Header | 이름 수 | 이름 / 처리 대상 |
| --- | ---: | --- |
| [adapter_descriptor.h](../include/golem/adapter_descriptor.h) | 12 | `golem_adapter_descriptor_current`, `golem_adapter_descriptor_decode`, `golem_adapter_descriptor_digest`, `golem_adapter_descriptor_encode`, `golem_adapter_descriptor_from_v1`, `golem_adapter_descriptor_to_v1`, `golem_adapter_descriptor_validate`, `golem_adapter_dispatch_checked`, `golem_harness_compatible`, `golem_harness_observation_encode`, `golem_harness_probe`, `golem_harness_probe_encode` |
| [adapter_protocol.h](../include/golem/adapter_protocol.h) | 12 | `golem_adapter_create`, `golem_adapter_dispatch`, `golem_adapter_envelope_decode`, `golem_adapter_envelope_encode`, `golem_adapter_free`, `golem_adapter_msgpack_decode`, `golem_adapter_msgpack_encode`, `golem_adapter_noop_create`, `golem_adapter_noop_run_stage`, `golem_adapter_probe`, `golem_adapter_request_init`, `golem_adapter_result_validate` |
| [admission.h](../include/golem/admission.h) | 14 | `golem_admission_begin`, `golem_admission_cancel`, `golem_admission_close`, `golem_admission_dispatch`, `golem_admission_enqueue`, `golem_admission_grant`, `golem_admission_identity`, `golem_admission_lookup`, `golem_admission_open`, `golem_admission_open_diagnostic`, `golem_admission_publish_work`, `golem_admission_release`, `golem_admission_resize`, `golem_admission_settle` |
| [agent_session.h](../include/golem/agent_session.h) | 4 | `golem_agent_reply_free`, `golem_agent_request_validate`, `golem_agent_session_call`, `golem_agent_session_resume_context` |
| [allocator.h](../include/golem/allocator.h) | 5 | `golem_allocator_alloc`, `golem_allocator_alloc_zero`, `golem_allocator_default`, `golem_allocator_free`, `golem_allocator_validate` |
| [approval.h](../include/golem/approval.h) | 4 | `golem_approval_call`, `golem_approval_describe`, `golem_approval_request_validate`, `golem_execution_call_receipted` |
| [arena.h](../include/golem/arena.h) | 4 | `golem_arena_alloc`, `golem_arena_init`, `golem_arena_reset`, `golem_arena_used_get` |
| [binding.h](../include/golem/binding.h) | 4 | `golem_binding_abi_version`, `golem_binding_call`, `golem_binding_free`, `golem_binding_status_message` |
| [candidate.h](../include/golem/candidate.h) | 4 | `golem_candidate_call`, `golem_candidate_current_host`, `golem_candidate_gate_digest`, `golem_candidate_validate` |
| [cli.h](../include/golem/cli.h) | 0 | 타입·상수·전이 include; 개별 도구 대상 아님 |
| [completion.h](../include/golem/completion.h) | 3 | `golem_completion_call`, `golem_completion_report`, `golem_completion_validate` |
| [context.h](../include/golem/context.h) | 4 | `golem_context_publish`, `golem_context_read`, `golem_context_render`, `golem_context_request_validate` |
| [core.h](../include/golem/core.h) | 26 | `golem_stage_graph_create`, `golem_stage_graph_create_with_allocator`, `golem_stage_graph_default_spec`, `golem_stage_graph_free`, `golem_stage_graph_next`, `golem_stage_graph_reentry`, `golem_stage_graph_spec_get`, `golem_stage_graph_validate_transition`, `golem_stage_name`, `golem_stage_run_snapshot_get`, `golem_stage_transition_validate`, `golem_work_capsule_create`, `golem_work_capsule_create_with_allocator`, `golem_work_capsule_free`, `golem_work_capsule_spec_borrow`, `golem_work_run_attempts_get`, `golem_work_run_begin`, `golem_work_run_cancel`, `golem_work_run_create`, `golem_work_run_create_with_allocator`, `golem_work_run_finish`, `golem_work_run_free`, `golem_work_run_id_borrow`, `golem_work_run_reenter`, `golem_work_run_snapshot_get`, `golem_work_run_stage_borrow` |
| [cost.h](../include/golem/cost.h) | 18 | `golem_budget_check`, `golem_cost_calculate`, `golem_cost_ledger_entry_get`, `golem_cost_ledger_options_get`, `golem_cost_ledger_report_get`, `golem_cost_ledger_stage_totals_get`, `golem_cost_ledger_totals_get`, `golem_cost_report_decode`, `golem_token_usage_add`, `golem_work_run_cost_borrow`, `golem_work_run_cost_enable`, `golem_work_run_cost_inbox_enable`, `golem_work_run_cost_inbox_status`, `golem_work_run_cost_inbox_sync`, `golem_work_run_cost_plan`, `golem_work_run_cost_report`, `golem_work_run_cost_report_json`, `golem_work_run_cost_settle` |
| [daemon.h](../include/golem/daemon.h) | 7 | `golem_daemon_close`, `golem_daemon_init`, `golem_daemon_inspect`, `golem_daemon_open`, `golem_daemon_recover`, `golem_daemon_submit`, `golem_daemon_tick` |
| [discovery.h](../include/golem/discovery.h) | 3 | `golem_discovery_report`, `golem_discovery_snapshot`, `golem_discovery_validate` |
| [document.h](../include/golem/document.h) | 11 | `golem_document_body`, `golem_document_generation`, `golem_document_inspect`, `golem_document_metadata`, `golem_document_project`, `golem_document_store_close`, `golem_document_store_create`, `golem_document_store_open`, `golem_document_submit`, `golem_document_validate`, `golem_work_spec_validate` |
| [error.h](../include/golem/error.h) | 3 | `golem_diagnostic_clear`, `golem_diagnostic_set`, `golem_status_string` |
| [event_reader.h](../include/golem/event_reader.h) | 5 | `golem_event_reader_close`, `golem_event_reader_open`, `golem_event_reader_read`, `golem_event_reader_refresh`, `golem_runtime_event_sse` |
| [evidence.h](../include/golem/evidence.h) | 14 | `golem_digest_bytes`, `golem_digest_file`, `golem_digest_format`, `golem_digest_parse`, `golem_evidence_close`, `golem_evidence_import`, `golem_evidence_open`, `golem_evidence_put`, `golem_evidence_read`, `golem_evidence_receipt_store`, `golem_evidence_receipt_verify`, `golem_evidence_verify`, `golem_receipt_decode`, `golem_receipt_encode` |
| [execution.h](../include/golem/execution.h) | 7 | `golem_execution_bundle_inspect`, `golem_execution_bundle_verify`, `golem_execution_call`, `golem_execution_call_authorized`, `golem_execution_contract_validate`, `golem_execution_render`, `golem_execution_reply_free` |
| [gateway.h](../include/golem/gateway.h) | 2 | `golem_gateway_envelope_decode`, `golem_gateway_envelope_prepare` |
| [inventory.h](../include/golem/inventory.h) | 4 | `golem_inventory_capture`, `golem_inventory_compare`, `golem_inventory_policy_validate`, `golem_inventory_reply_free` |
| [journal.h](../include/golem/journal.h) | 14 | `golem_journal_append`, `golem_journal_checkpoint_get`, `golem_journal_close`, `golem_journal_crc32`, `golem_journal_created_encode`, `golem_journal_event_decode`, `golem_journal_event_encode`, `golem_journal_inspect`, `golem_journal_open`, `golem_journal_reader_init`, `golem_journal_reader_next`, `golem_journal_record_decode`, `golem_journal_record_encode`, `golem_journal_replay` |
| [lease.h](../include/golem/lease.h) | 7 | `golem_lease_acquire`, `golem_lease_create`, `golem_lease_free`, `golem_lease_heartbeat`, `golem_lease_release`, `golem_lease_resource_borrow`, `golem_lease_validate` |
| [lineage.h](../include/golem/lineage.h) | 16 | `golem_lineage_add`, `golem_lineage_begin`, `golem_lineage_create`, `golem_lineage_decode`, `golem_lineage_encode`, `golem_lineage_free`, `golem_lineage_load`, `golem_lineage_node_get`, `golem_lineage_parents`, `golem_lineage_predecessors`, `golem_lineage_run_id_borrow`, `golem_lineage_seal`, `golem_lineage_stage_get`, `golem_lineage_stats_get`, `golem_lineage_store`, `golem_lineage_verify` |
| [optimization.h](../include/golem/optimization.h) | 7 | `golem_cache_break_even`, `golem_fallback_check`, `golem_optimization_policy_init`, `golem_work_run_begin_optimized`, `golem_work_run_optimization_enable`, `golem_work_run_optimization_evaluate`, `golem_work_run_optimization_policy_get` |
| [policy.h](../include/golem/policy.h) | 13 | `golem_autonomy_evaluate`, `golem_policy_artifact_decode`, `golem_policy_artifact_encode`, `golem_policy_create`, `golem_policy_evaluate`, `golem_policy_free`, `golem_policy_reason_name`, `golem_policy_spec_get`, `golem_policy_spec_init`, `golem_policy_spec_validate`, `golem_policy_verdict_name`, `golem_work_run_begin_authorized`, `golem_work_run_permission_request` |
| [prepared_runtime.h](../include/golem/prepared_runtime.h) | 6 | `golem_prepared_cache_acquire`, `golem_prepared_cache_close`, `golem_prepared_cache_create`, `golem_prepared_cache_invalidate`, `golem_prepared_cache_release`, `golem_prepared_runtime_view` |
| [proof.h](../include/golem/proof.h) | 5 | `golem_proof_integrity`, `golem_proof_publish`, `golem_proof_render`, `golem_proof_verify`, `golem_proof_verify_directory` |
| [record.h](../include/golem/record.h) | 5 | `golem_record_begin`, `golem_record_call`, `golem_record_finish`, `golem_record_last_api_outcome`, `golem_record_write` |
| [reentry.h](../include/golem/reentry.h) | 3 | `golem_reentry_call`, `golem_reentry_report`, `golem_reentry_validate` |
| [replay.h](../include/golem/replay.h) | 7 | `golem_journal_recover`, `golem_replay_create`, `golem_replay_expect_checkpoint`, `golem_replay_feed`, `golem_replay_finish`, `golem_replay_free`, `golem_replay_progress_get` |
| [research.h](../include/golem/research.h) | 12 | `golem_research_bundle`, `golem_research_bundle_verify`, `golem_research_call`, `golem_research_compare`, `golem_research_inspect`, `golem_research_metrics`, `golem_research_metrics_report`, `golem_research_observability`, `golem_research_redaction_validate`, `golem_research_report`, `golem_research_status`, `golem_research_validate` |
| [resource.h](../include/golem/resource.h) | 1 | `golem_resource_run` |
| [role_contract.h](../include/golem/role_contract.h) | 4 | `golem_role_call`, `golem_role_request_validate`, `golem_role_template`, `golem_role_validate` |
| [runtime.h](../include/golem/runtime.h) | 11 | `golem_runtime_cancel`, `golem_runtime_checkpoint`, `golem_runtime_create`, `golem_runtime_drive`, `golem_runtime_free`, `golem_runtime_heartbeat`, `golem_runtime_lease_bind`, `golem_runtime_recover`, `golem_runtime_report_get`, `golem_runtime_run_borrow`, `golem_runtime_step` |
| [runtime_event.h](../include/golem/runtime_event.h) | 7 | `golem_admission_events`, `golem_runtime_cursor_format`, `golem_runtime_cursor_parse`, `golem_runtime_event_name`, `golem_runtime_events_export`, `golem_runtime_events_snapshot`, `golem_worker_events` |
| [runtime_profile.h](../include/golem/runtime_profile.h) | 11 | `golem_runtime_link_run`, `golem_runtime_profile_cache_acquire`, `golem_runtime_profile_cache_close`, `golem_runtime_profile_cache_create`, `golem_runtime_profile_cache_release`, `golem_runtime_profile_current`, `golem_runtime_profile_digest`, `golem_runtime_profile_encode`, `golem_runtime_profile_free`, `golem_runtime_profile_parse`, `golem_runtime_profile_register` |
| [session_binding.h](../include/golem/session_binding.h) | 5 | `golem_session_binding_call`, `golem_session_binding_request_validate`, `golem_session_fence_check`, `golem_work_history`, `golem_work_record` |
| [supervisor.h](../include/golem/supervisor.h) | 5 | `golem_supervisor_run`, `golem_supervisor_run_at`, `golem_supervisor_run_bulk`, `golem_supervisor_run_observed`, `golem_supervisor_run_streamed` |
| [system_error.h](../include/golem/system_error.h) | 5 | `golem_system_error_action`, `golem_system_error_begin`, `golem_system_error_end`, `golem_system_error_name`, `golem_system_error_note` |
| [types.h](../include/golem/types.h) | 8 | `golem_bytes_init`, `golem_bytes_slice`, `golem_bytes_write`, `golem_string_clone`, `golem_string_view_from_cstr`, `golem_string_view_init`, `golem_string_view_slice`, `golem_string_view_write` |
| [version.h](../include/golem/version.h) | 1 | `golem_version_string` |
| [worker.h](../include/golem/worker.h) | 11 | `golem_worker_acknowledge`, `golem_worker_cancel`, `golem_worker_close`, `golem_worker_diagnostics`, `golem_worker_heartbeat`, `golem_worker_inspect`, `golem_worker_open`, `golem_worker_options_default`, `golem_worker_recording_status`, `golem_worker_start`, `golem_worker_submit` |
| [workflow.h](../include/golem/workflow.h) | 5 | `golem_document_graph_evaluate`, `golem_workflow_inputs`, `golem_workflow_next`, `golem_workflow_select`, `golem_workflow_trace` |
| [workflow_template.h](../include/golem/workflow_template.h) | 4 | `golem_workflow_template_builtin`, `golem_workflow_template_expand`, `golem_workflow_template_instantiate`, `golem_workflow_template_validate` |
| [workspace.h](../include/golem/workspace.h) | 1 | `golem_workspace_call` |

## Native CLI 최상위 dispatch

`src/cli/main.c`의 `argv[1]` 비교에서 수집했다. usage에 빠진 하위 명령도 M0에서는
각 dispatcher와 native schema에서 대조한다. `--help`/`--version`은 진단 기능이고
`init`·`work start`·CAS import·salvage·daemon 운영은 읽기 권한으로 승격할 수 없다.

- `--help`
- `--version`
- `adapter`
- `agent`
- `approval`
- `candidate`
- `capsule`
- `completion`
- `context`
- `cost`
- `daemon`
- `discovery`
- `doctor`
- `document`
- `events`
- `evidence`
- `execution`
- `init`
- `journal`
- `lineage`
- `output`
- `profile`
- `proof`
- `reentry`
- `replay`
- `research`
- `role`
- `run`
- `session`
- `work`
- `workflow`

- `inventory`

## Python 모듈 범위

`tools/*.py` 중 `test_` 접두사를 제외한 파일 목록이다. 개별 모듈의 모든 함수가
제품 기능은 아니다. 구현 라이브러리·검증기·벤치마크·배포 도구를 M0에서 구분한다.
이 목록에 있다는 이유로 해당 프로그램 실행 권한 또는 MCP 노출을 부여하지 않는다.

- [agent_entrypoint.py](../tools/agent_entrypoint.py)
- [agent_io.py](../tools/agent_io.py)
- [agent_lifecycle.py](../tools/agent_lifecycle.py)
- [benchmark_intent_journal.py](../tools/benchmark_intent_journal.py)
- [benchmark_orchestration.py](../tools/benchmark_orchestration.py)
- [benchmark_runtime.py](../tools/benchmark_runtime.py)
- [billing_evidence.py](../tools/billing_evidence.py)
- [check_guard_mutations.py](../tools/check_guard_mutations.py)
- [classify_failures.py](../tools/classify_failures.py)
- [codex_hosted.py](../tools/codex_hosted.py)
- [context_resume.py](../tools/context_resume.py)
- [doctor_environment.py](../tools/doctor_environment.py)
- [evidence_adapters.py](../tools/evidence_adapters.py)
- [evidence_contract.py](../tools/evidence_contract.py)
- [evidence_export.py](../tools/evidence_export.py)
- [execution_record.py](../tools/execution_record.py)
- [github_checks.py](../tools/github_checks.py)
- [github_context.py](../tools/github_context.py)
- [github_policy.py](../tools/github_policy.py)
- [hosted_usage.py](../tools/hosted_usage.py)
- [install_conan_cli.py](../tools/install_conan_cli.py)
- [instruction_bundle.py](../tools/instruction_bundle.py)
- [integration_backend.py](../tools/integration_backend.py)
- [integration_codex_plugin.py](../tools/integration_codex_plugin.py)
- [integration_config.py](../tools/integration_config.py)
- [integration_contract.py](../tools/integration_contract.py)
- [integration_gateway.py](../tools/integration_gateway.py)
- [integration_gateway_auth.py](../tools/integration_gateway_auth.py)
- [integration_gateway_contract.py](../tools/integration_gateway_contract.py)
- [integration_hook_contract.py](../tools/integration_hook_contract.py)
- [integration_hooks.py](../tools/integration_hooks.py)
- [integration_install.py](../tools/integration_install.py)
- [integration_launch.py](../tools/integration_launch.py)
- [integration_lifecycle.py](../tools/integration_lifecycle.py)
- [integration_mcp.py](../tools/integration_mcp.py)
- [integration_mcpb.py](../tools/integration_mcpb.py)
- [integration_mcpb_entry.py](../tools/integration_mcpb_entry.py)
- [integration_mutation_contract.py](../tools/integration_mutation_contract.py)
- [integration_mutation_mcp.py](../tools/integration_mutation_mcp.py)
- [integration_mutations.py](../tools/integration_mutations.py)
- [integration_recovery.py](../tools/integration_recovery.py)
- [integration_registry.py](../tools/integration_registry.py)
- [integration_reload_probe.py](../tools/integration_reload_probe.py)
- [integration_service.py](../tools/integration_service.py)
- [integration_transfer.py](../tools/integration_transfer.py)
- [integration_update.py](../tools/integration_update.py)
- [intent_authority.py](../tools/intent_authority.py)
- [intent_authority_lifecycle.py](../tools/intent_authority_lifecycle.py)
- [isolation_canary.py](../tools/isolation_canary.py)
- [judgment_record.py](../tools/judgment_record.py)
- [native_record.py](../tools/native_record.py)
- [provider_costs.py](../tools/provider_costs.py)
- [provider_usage.py](../tools/provider_usage.py)
- [remote_status.py](../tools/remote_status.py)
- [retire_legacy_cli.py](../tools/retire_legacy_cli.py)
- [revision_status.py](../tools/revision_status.py)
- [status_collector.py](../tools/status_collector.py)
- [syscall_record.py](../tools/syscall_record.py)
- [usage_pipeline.py](../tools/usage_pipeline.py)
- [verify_agent.py](../tools/verify_agent.py)
- [verify_alpha.py](../tools/verify_alpha.py)
- [verify_environment.py](../tools/verify_environment.py)
- [verify_gateway_schema.py](../tools/verify_gateway_schema.py)
- [verify_hook_schema.py](../tools/verify_hook_schema.py)
- [verify_install_schema.py](../tools/verify_install_schema.py)
- [verify_integration_schema.py](../tools/verify_integration_schema.py)
- [verify_isolation.py](../tools/verify_isolation.py)
- [verify_mutation_schema.py](../tools/verify_mutation_schema.py)
- [verify_orchestration.py](../tools/verify_orchestration.py)
- [verify_preflight.py](../tools/verify_preflight.py)
- [verify_resource.py](../tools/verify_resource.py)
- [verify_runtime.py](../tools/verify_runtime.py)
- [verify_runtime_legacy.py](../tools/verify_runtime_legacy.py)
- [verify_update_schema.py](../tools/verify_update_schema.py)

## 별도로 확인할 private host와 패키지

- `src/intent/*.h`, `src/intent/*.c`: 승인된 D01·D08/P1a schema·quota·journal·object store·reader.
  public C API로 승격하거나 미구현 adoption/ACTIVE를 있다고 표시하지 않는다.
- `tools/intent_authority.py`, `tools/intent_authority_lifecycle.py`: 등록·변경·읽기·proposal
  쓰기와 단계별 owner 복구. public D1 integration registry와 동일 authority라고 추정하지 않는다.
- `plugins/golem/scripts/launcher.py`, `plugins/golem/skills/golem-setup/SKILL.md`:
  설치·연결 adapter와 setup 스킬. 일반 Work 진행 스킬과 구분한다.
- `tools/integration_mcpb.py`, `tools/integration_codex_plugin.py`: 배포 생성기.
  설치된 실제 package의 capability는 승인 정책 교집합으로 별도 확인한다.
- `tests/c`, `tools/test_*.py`, `.github/workflows`: 구현·fixture·실제 client 검증 근거.
  test 파일 이름이나 CI PASS를 개별 기능의 모든 환경 지원으로 승격하지 않는다.

## 목록 갱신과 누락 판정

M0는 이 목록에 source digest·operation·schema/version·효과·native guard·권한 주체·
MCP tool/owner 경로·시험·문서·package profile을 연결한 capability ledger를 작성한다.
각 항목은 `MCP_READ`, `MCP_REVIEWED_ACTION`, `OWNER_ONLY`, `HOST_INTERNAL`,
`PROPOSED_NOT_IMPLEMENTED`, `UNCLASSIFIED` 중 하나를 명시한다.
`UNCLASSIFIED` 또는 근거 없는 제외가 남으면 전 기능 연결 완료를 선언하지 않는다.
새 public API/CLI/Python 제품 기능이 생기면 ledger와 시험을 함께 갱신한다.

## 전수 M0 원장 연결 — 최신

위 초기 진입점 목록은 현재 [닫힌 원장](mcp-m0-observations.json)으로 확장했다.
public API 344개·callback 선언 30개, 생산/계약 파일 424개 전체 표면과 473개 제외 경계,
중첩 CLI/Python/FFI operation을 검토했다. 513개 입력·2,107개 관측·1,078개 capability의
source/operation/분류/검토/미해석 blocker는 0이다. [전수 근거](mcp-m0-reconciliation.json)와
[출구 검토](mcp-m0-review-2026-10-26.ko.md)를 따른다. 숫자는 기능 수나 독립 MCP tool 수가 아니다.
MCP 미제공 312개·owner 관리 83개·명시적 역사적 지원 제외 17개를 구분하며 실행 권한은 없다.


## M1 구현 이후 최신 상태 — 2026-10-26

M1의 local typed 읽기 21개를 기존 D2 7개와 연결했다. 원래 M1 backlog 120개 ID를 유지하고 기능별 core/argv·resource·fixture 근거를 대조했다. 전체 표와 권한 경계는 [M1 읽기 검토](mcp-m1-read-coverage.ko.md), 실제 재계산은 [원장 대조](mcp-m0-reconciliation.json)의 `m1_read_coverage`를 따른다. 읽기 84·공통 core 7·내부 의존 20·owner 5·혼합 3·source 준비 1을 각각 구분한다. source capture M3, billing 독립 reconciliation M4, owner policy/config 계획·검사 M6 경계를 숨기지 않는다.

전체 source horizon은 기존 424에 새 runtime 읽기 모듈 3개를 추가한 427이다. 명시 source/근거 520개, 관측 2,156개, capability 1,106개로 확장했다. tracked index 기준 897개와 기존 boundary 검토는 유지한다. 새 runtime을 개발 분석 파일로 제외하지 않는다. 분석기/검토 모델/원장은 검사기가 자동 갱신하지 않는다. source·operation·효과·connection·전수 gate의 검토 모델을 명시적으로 갱신했다.

| 단계 | 이번 개발 상태 | 남은 검증·기능 |
| --- | --- | --- |
| M0 | 확장된 horizon의 목록·정적 gate 유지 | 실제 실행/권한 충족을 인증하지 않음 |
| M1 | 읽기 코드·정적 연결·임시 fixture 구현, 선택적 owner resource 계약 | 실제 설치·노출/client E2E NOT_RUN; owner/source/billing 경계는 표의 후속 단계 |
| M2 | 신규 준비 기능 확장 미착수 | 기존 typed action의 준비 의존 유지 |
| M3 | 본격 수명주기 확장 미착수 | context publish·fresh discovery source capture 포함 |
| M4 | 실행/QA 확장 미착수 | billing 검증/정확 join과 evidence 실행 권위 유지 |
| M5 | 병렬/병합 확장 미착수 | 기존 backlog 유지 |
| M6 | skill/패키징 확장 미착수 | 실제 owner 정책·설치·승인·설정 작업 유지 |
| M7 | 실제 client harness 확장 미착수 | Codex/Claude E2E NOT_RUN |
| M8 | 최종 전체 제공/CI 미완료 | Linux/Windows·CI NOT_RUN, commit/push 없음 |

과거의 M0 미완료/M1 미착수 절은 이전 checkpoint다. M1 코드 검증을 계획의 장기 출구 조건인 실제 client 노출 검증으로 바꾸지 않는다. 원본·활성 연결·기존 승인/pin/Work/evidence는 변경하지 않았다.


## M2 입력·준비 이후 최신 상태 — 2026-10-26

M2의 입력/초안/구조 검증/불변 plan/owner action 검토/확인 도구 6개를 기존 D2·D4에 연결했다. [구현·수명·검증 기록](mcp-m2-preparation.ko.md)과 원장 대조 JSON의 `m2_preparation_dependencies`를 따른다. 기존 준비 의존 134개 ID를 보존한다: D4 typed 초안/owner byte 검토 26, core artifact 구조 검증 22, 현재 입력 basis와 후속 native route 경계 86이다. 뒤의 86개를 operation-specific typed schema/실행 제공 완료로 계산하지 않는다. M3 60/M4 45/M5 29의 준비 의존이며 해당 단계의 native 권한·효과·실행 경로는 여전히 별개다.

COV-D03의 구현은 기존 private audit에 저장하는 동일 instance·30분·현재 등록 Work basis의 비권한 plan이다. 사용자 상관 ID는 재조회용이고 native key/D4 request ID를 대체하지 않는다. 같은 요청의 결과 유실 후 재조회는 원래 plan/key/bytes를 반환하며 stale/conflict/재시작 시 자동 복구하지 않는다. owner action 파일·승인·정책을 새로 작성/적용하거나 기존 승인 bytes를 고치지 않는다. 실제 dispatch는 기존 D4/core 검사를 유지한다.

전수 source/근거 525개·관측 2,171개·capability 1,115개, product source 429개로 horizon을 확장했다. source·operation·효과·기존 D2/D4/M1 및 새 M2 profile을 함께 검사한다. 기존 미제공 delivery 190개(M3 60/M4 83/M5 47), owner 관리 83개·역사적 지원 제외 17개는 보존한다. 새로운 준비안이 그 native 실행을 제공하거나 승인했다는 뜻이 아니다.

| 단계 | 현재 코드·검증 상태 | 남은 범위 |
| --- | --- | --- |
| M0 | M2 source/operation을 포함한 전수 정적 대조 | 실행/권한/실제 receiver 인증 아님 |
| M1 | 기존 읽기 구현·회귀 유지 | 실제 client 노출/E2E NOT_RUN |
| M2 | 공통 입력/불변 준비/owner byte 확인 구현·정적/fixture 검증 | 실제 client 사용성/노출 검증 NOT_RUN; operation별 새 native route는 M3~M5 |
| M3 | 신규 수명주기 확장 미착수 | creation/누락 operation별 권한·typed action·finalize |
| M4 | 신규 QA/실행 확장 미착수 | 원래 protected source/approval/evidence/native 실행 계약 |
| M5 | 신규 병렬/병합 확장 미착수 | host/runtime handle·source 범위·native 효과별 계약 |
| M6 | 신규 배포/owner 관리 확장 미착수 | 기존 launcher/정책/승인/pin 유지, 자동 적용 없음 |
| M7 | 실제 client harness 확장 미착수 | Codex/Claude/remote E2E NOT_RUN |
| M8 | 최종 전체 제공/CI 미완료 | Linux/Windows·CI NOT_RUN, commit/push 없음 |

이전의 M2 미착수 절은 과거 checkpoint다. 현재 code/정적/fixture 검증과 실제 client 검증·전체 native 기능 제공 완료를 구분한다.


## M3 완료 후 현재 상태 (2026-10-26)

[M3 구현 기록](mcp-m3-task-actions.ko.md): 고정 backlog 60개를 새 typed action 20개·기존 D4 7개 및 M2 준비 계약에 연결했다. source/근거 529개·관측 2,215개·capability 1,139개·product source 430개, 선택/저장소 blocker 0이다. tracked baseline 897개와 기존 callback/TRY/publication guard·boundary 계약은 유지한다. M4 83/M5 47, delivery 130개와 owner 83/unsupported 17은 남긴다. M1의 120개·M2의 134개 표는 당시 의존성 근거이며 M3 완료는 별도의 고정 60개 표로 대조한다.

검증: M3 제품 fixture 19개, M3 정적 fixture 9개, 전체 integration 272개(254 통과/18 skip), capability 334개, C API unit 25개 통과. 실제 client/Work E2E·Linux/Windows·CI·commit/push는 NOT_RUN이다. 기존 연결·승인·원본·Work·staging을 변경하지 않는다.


## M4 후 현재 기록 (2026-10-26)

[M4 계약·83개 처리표](mcp-m4-quality-evidence.ko.md): D2 read 4개·D4 action 7개를 추가하고 기존 core·M2·M3·QA host 및 별도 owner helper effects 계약에 연결했다. M4의 cost inbox는 첫 단계 disposable accounting이며 live run attach/정산이 아니다. 실제 외부 서비스·client/Work E2E는 NOT_RUN이다.

정적 source/근거 535개·관측 2,249개·capability 1,162개·product source 433개, 선택/저장소 blocker 0. 고정 M1 120/M2 준비 의존 134/M3 60/M4 83의 근거를 각각 유지하며, 남은 native delivery는 M5 47개다. owner 83개와 unsupported 17개를 유지한다. 기존 callback/TRY/publication guard·boundary·tracked baseline 897개를 약화하지 않는다.

M4 fixture 34개·정적 fixture 11개·helper 회귀 192개·C API unit 37개 통과. 전체 integration 306개(288 통과/18 skip), capability 345개 통과. 기존 연결·승인·원본 변경·Work·staging을 보존하고 install·승인 적용·실제 외부 서비스·E2E·CI·commit/push는 수행하지 않았다.


## M5 현재 source inventory (2026-10-26)

[M5 상세·47개 표](mcp-m5-parallel-candidates.ko.md). source/근거542·관측2275·capability1180·whole product437; D2 source schema43개+D4 action37개. inventory CLI는 기존 native policy_validate/capture/compare를 재사용한다. candidate/workspace는 default-off 별도 owner host 계약에 묶고 workspace 읽기는 기존 action의 역사 결과만 제공한다. 고정 delivery47개 연결과 P4/P5 신규 scheduler/merge 등의 7개 NOT_IMPLEMENTED 의무를 분리한다. 실제 client/Work/host/서비스/merge E2E는 NOT_RUN이며 기존 owner 관리83개·unsupported17개를 재분류하지 않는다.


## M6 명시 범위 기록 (2026-10-26)

M6 현재: source552·관측2282·capability1187·whole-file surface444. source 도구는 기존 D2 43+D4 37이며 5개 feature profile은 현재 owner scope와의 교집합이다. 스킬/metadata/소스 패키지 포함은 실행 권한이 아니다. owner83개와 M5 미구현7개·unsupported17개는 유지한다. 상세 계약·처리표·검증은 [M6 기록](mcp-m6-distribution.ko.md)을 따른다.
