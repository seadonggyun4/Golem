# MCP capability inventory

Selected inventory: COMPLETE

This compares only the explicitly selected scope; it is not repository-wide coverage, execution, authorization or product PASS.

| Capability | Implementation | Current routes | Target routes | Review |
| --- | --- | --- | --- | --- |
| d2.completion_check | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| d2.context_get | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| d2.evidence_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| d2.handoff_prepare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| d2.history_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| d2.projects_list | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| d2.work_inspect | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| d4.document_submit | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| d4.execution_request | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| d4.session_begin | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| d4.session_claim | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| d4.session_reconcile | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| d4.session_resume | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| d4.session_submit | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| completion.finalize | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| completion.resume | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| session.begin | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| session.claim | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| session.context | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| session.heartbeat | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| session.next | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| session.reject_output | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| session.resume | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| session.start | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| session.status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| session.submit | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| workflow.inputs | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| workflow.next | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| workflow.select | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| workflow.trace | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.template | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.help | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| cli.route.version | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| cli.route.adapter | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.agent | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.approval | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.candidate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.capsule | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.completion | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.context | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.cost | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.daemon | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.discovery | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.doctor | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.document | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.events | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.evidence | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.execution | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.init | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.journal | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.lineage | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.output | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.profile | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.proof | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.reentry | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.route.replay | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.route.research | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.role | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.run | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.session | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.work | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.route.workflow | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.adapter.convert | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.adapter.describe | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.adapter.noop | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.adapter.probe | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.agent_session.call | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.agent_session.resume | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.approval.call | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.approval.describe | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.candidate.call | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.candidate.diff | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.candidate.gates | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.candidate.host-validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.candidate.request-digest | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.candidate.serve | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.candidate.status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.candidate.validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.completion.call | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.completion.check | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.completion.report | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.completion.validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.context.candidate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.context.markdown | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.context.publish | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.context.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.context.render | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.daemon.init | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.daemon.recover | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.daemon.run | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.daemon.status | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.daemon.submit | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.discovery.report | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.discovery.snapshot | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.discovery.validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.doctor.admission | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.doctor.clock | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.doctor.work | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.document.inspect | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.document.project | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.document.start | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.document.submit | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.document.validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.events.jsonl | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.events.otlp | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.events.prov | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.execution.bundle | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.execution.call | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.execution.render | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.execution.validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.journal.inspect | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.journal.salvage | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.journal.verify-salvage | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.lineage.trace | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.lineage.verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.output.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.runtime_profile.current | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.runtime_profile.link | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.runtime_profile.register | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.runtime_profile.validate | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.proof.integrity | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.proof.publish | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.proof.render | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.proof.verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.proof.verify-dir | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.reentry.call | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.reentry.report | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.reentry.validate | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.research.attempt | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.research.bundle-verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.research.call | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.research.case | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.research.cohort | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.research.compare | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.research.export | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.research.inspect | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.research.metrics | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.research.observability | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.research.outcome | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.research.report | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.research.status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.research.validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.role.call | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.role.template | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.role.validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.work.capsule | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.work.cost | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.work.init | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| cli.dispatch.work.replay | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.work.run | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.workflow_template.instantiate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.workflow_template.list | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.workflow_template.show | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.workflow_template.validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_runtime_cursor_parse | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_events_snapshot | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_events_export | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_status_string | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| owner.transfer.schema | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| owner.transfer.plan | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| native.golem_adapter_descriptor_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_descriptor_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_descriptor_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_descriptor_digest | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_descriptor_from_v1 | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_descriptor_to_v1 | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_descriptor_current | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_harness_compatible | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_harness_observation_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_dispatch_checked | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_harness_probe | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_harness_probe_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_probe | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_request_init | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_result_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_dispatch | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_envelope_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_envelope_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_msgpack_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_msgpack_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_noop_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_adapter_noop_run_stage | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_admission_open | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_open_diagnostic | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_close | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_identity | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_enqueue | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_lookup | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_grant | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_resize | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_cancel | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_dispatch | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_begin | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_publish_work | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_settle | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_admission_release | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_agent_request_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_agent_session_call | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_agent_session_resume_context | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_agent_reply_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_allocator_default | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_allocator_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_allocator_alloc | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_allocator_alloc_zero | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_allocator_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_approval_request_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_approval_describe | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_approval_call | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_execution_call_receipted | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_arena_init | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_arena_alloc | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_arena_reset | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_arena_used_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_binding_abi_version | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_binding_call | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_binding_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_binding_status_message | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_candidate_current_host | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_candidate_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_candidate_gate_digest | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_candidate_call | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION, OWNER_ONLY | MCP_READ, MCP_REVIEWED_ACTION, OWNER_ONLY | REVIEWED |
| native.golem_completion_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_completion_call | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_completion_report | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_context_request_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_context_render | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_context_publish | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_context_read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_stage_name | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_graph_default_spec | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_graph_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_graph_create_with_allocator | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_graph_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_graph_spec_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_graph_next | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_graph_validate_transition | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_graph_reentry | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_transition_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_capsule_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_capsule_create_with_allocator | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_capsule_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_capsule_spec_borrow | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_create_with_allocator | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_id_borrow | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_snapshot_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_attempts_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_stage_borrow | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_stage_run_snapshot_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_begin | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_finish | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_reenter | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_cancel | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_token_usage_add | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_cost_calculate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_budget_check | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_cost_enable | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_cost_borrow | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_work_run_cost_plan | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_cost_report | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_cost_report_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_cost_report_json | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_cost_inbox_enable | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_work_run_cost_inbox_sync | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_work_run_cost_inbox_status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_work_run_cost_settle | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_cost_ledger_entry_get | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_cost_ledger_report_get | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_cost_ledger_totals_get | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_cost_ledger_stage_totals_get | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_cost_ledger_options_get | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_daemon_recover | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_daemon_init | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_daemon_submit | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_daemon_inspect | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_daemon_open | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_daemon_tick | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_daemon_close | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_discovery_validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_discovery_report | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_discovery_snapshot | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_work_spec_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_document_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_document_store_create | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_document_store_open | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_document_store_close | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_document_generation | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_document_submit | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_document_inspect | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_document_body | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_document_metadata | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_document_project | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_diagnostic_clear | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_diagnostic_set | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_event_reader_open | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_event_reader_refresh | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_event_reader_read | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_event_reader_close | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_event_sse | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_digest_bytes | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_digest_file | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_digest_parse | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_digest_format | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_evidence_open | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_evidence_close | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_evidence_put | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_evidence_import | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_evidence_verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_evidence_read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_receipt_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_receipt_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_evidence_receipt_store | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_evidence_receipt_verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_execution_contract_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_execution_call | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_execution_call_authorized | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_execution_render | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_execution_reply_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_execution_bundle_inspect | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_execution_bundle_verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_gateway_envelope_prepare | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_gateway_envelope_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_inventory_policy_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_inventory_capture | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_inventory_compare | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_inventory_reply_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_checkpoint_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_inspect | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_journal_crc32 | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_record_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_record_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_reader_init | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_reader_next | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_created_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_event_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_event_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_open | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_append | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_journal_close | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_replay | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_lease_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lease_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lease_acquire | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lease_heartbeat | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lease_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lease_release | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lease_resource_borrow | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_run_id_borrow | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_stats_get | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_lineage_stage_get | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_lineage_node_get | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_lineage_begin | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_add | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_seal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_parents | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_predecessors | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_lineage_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_lineage_verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_lineage_store | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_lineage_load | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_optimization_policy_init | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_cache_break_even | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_fallback_check | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_optimization_enable | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_optimization_policy_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_optimization_evaluate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_begin_optimized | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_artifact_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_artifact_decode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_spec_init | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_spec_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_spec_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_autonomy_evaluate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_evaluate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_verdict_name | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_policy_reason_name | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_permission_request | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_work_run_begin_authorized | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_prepared_cache_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_prepared_cache_acquire | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_prepared_runtime_view | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_prepared_cache_invalidate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_prepared_cache_release | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_prepared_cache_close | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_proof_render | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_proof_verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_proof_integrity | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_proof_publish | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_proof_verify_directory | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_record_begin | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_record_write | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_record_finish | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_record_call | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_record_last_api_outcome | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_reentry_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_reentry_call | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_reentry_report | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_replay_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_replay_expect_checkpoint | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_replay_feed | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_replay_finish | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_replay_progress_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_replay_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_journal_recover | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_research_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_research_call | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_research_inspect | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_research_report | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_research_status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_research_metrics | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_research_metrics_report | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_research_compare | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_research_redaction_validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_research_bundle | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_research_bundle_verify | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_research_observability | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_resource_run | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_role_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_role_request_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_role_template | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_role_call | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_runtime_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_recover | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_step | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_drive | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_cancel | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_report_get | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_run_borrow | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_lease_bind | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_checkpoint | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_heartbeat | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_worker_events | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_admission_events | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_cursor_format | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_event_name | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_parse | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_free | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_digest | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_encode | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_cache_create | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_cache_acquire | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_cache_release | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_cache_close | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_runtime_profile_register | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_runtime_profile_current | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_runtime_link_run | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_session_binding_request_validate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_session_binding_call | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| native.golem_work_history | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_work_record | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_session_fence_check | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_supervisor_run | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_supervisor_run_at | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_supervisor_run_streamed | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_supervisor_run_bulk | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_supervisor_run_observed | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_system_error_begin | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_system_error_end | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_system_error_note | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_system_error_name | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_system_error_action | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_bytes_init | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_bytes_slice | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_string_view_init | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_string_view_from_cstr | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_string_view_slice | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_bytes_write | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_string_view_write | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_string_clone | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_version_string | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| native.golem_worker_options_default | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_open | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_submit | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_start | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_inspect | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_diagnostics | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_recording_status | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_cancel | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_heartbeat | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_acknowledge | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_worker_close | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| native.golem_document_graph_evaluate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workflow_select | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workflow_inputs | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workflow_trace | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workflow_next | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workflow_template_validate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workflow_template_builtin | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workflow_template_expand | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workflow_template_instantiate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| native.golem_workspace_call | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION, OWNER_ONLY | MCP_READ, MCP_REVIEWED_ACTION, OWNER_ONLY | REVIEWED |
| callback.golem_harness_guard.observe | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_harness_guard.now | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_adapter_ops.probe | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_adapter_ops.run_stage | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_admission_dispatch_ops.publish | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_admission_dispatch_ops.execute | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_agent_clock.read | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_allocator.allocate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_allocator.deallocate | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_approval_host.decide | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_approval_host.recheck | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_candidate_host.check | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_candidate_host.resolve | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_candidate_host.start | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_candidate_host.cancel | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_candidate_current_options.authorize | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_candidate_current_options.request_cancel | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_context_tokenizer.count | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_daemon_ops.execute | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_lease_ops.record | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_prepared_options.observe | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_prepared_options.prepare | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_prepared_options.clock_ns | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_runtime_ops.record | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_runtime_ops.execute | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_runtime_ops.now | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_session_binding_host.observe | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_supervisor_stream.write | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_workspace_host.check | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| callback.golem_workspace_host.pulse | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| operation.agent_session.request_schema.begin | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.request_schema.claim | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.request_schema.context | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.agent_session.request_schema.heartbeat | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.request_schema.next | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.agent_session.request_schema.reconcile | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.request_schema.reject_output | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.request_schema.resume | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.request_schema.start | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.request_schema.status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.agent_session.request_schema.submit | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.golem_agent_session_resume_context.resume | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.policy.ap_request.approve | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| operation.policy.ap_request.deny | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| operation.policy.ap_request.expire | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| operation.policy.ap_request.recover | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| operation.policy.ap_request.request | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.policy.ap_request.revoke | IMPLEMENTED | HOST_INTERNAL | OWNER_ONLY | REVIEWED |
| operation.policy.ap_request.status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.completion.co_validate.finalize | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.execution.call.finish | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.execution.call.prepare | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.execution.call.run | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.execution.call.verify | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.policy.ap_scope.finish | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.policy.ap_scope.prepare | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.policy.ap_scope.run | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.workflow.rc_request.assess | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.workflow.rc_request.enroll | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.workflow.rc_request.evaluate | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.workflow.rc_request.status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.reentry.re_validate.decide | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.reentry.re_validate.status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.agent_session.shape.attach | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.agent_session.shape.inspect | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.research.rs_validate.attempt-plan | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.research.rs_validate.attempt-record | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.research.rs_validate.case-create | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.research.rs_validate.outcome-enroll | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.research.rs_is_cohort.cohort-create | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.research.rs_is_cohort.cohort-observe | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.research.rs_is_outcome.adjudicate | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.research.rs_is_outcome.outcome-enroll | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.cancel | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.cohort-record | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.compare | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.candidate.golem_candidate_call.create | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.diff | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.candidate.golem_candidate_call.diff-seal | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.enroll | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.finish | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.reserve | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.review | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.review-check | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.candidate.golem_candidate_call.select | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.start | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.golem_candidate_call.status | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.candidate.golem_candidate_call.target-check | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.candidate.dispatch.cancel | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.cohort-record | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.compare | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.candidate.dispatch.diff | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.candidate.dispatch.diff-seal | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.enroll | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.finish | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.reserve | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.review | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.review-check | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.candidate.dispatch.select | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.start | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.candidate.dispatch.target-check | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_CREATE | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_RESUME | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_ACTIVATE | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_SEAL | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_RETAIN | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.golem.golem_workspace_operation.GOLEM_WORKSPACE_REMOVE | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| operation.golem.golem_binding_call.GOLEM_BINDING_VALIDATE | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.golem.golem_binding_call.GOLEM_BINDING_REPLAY | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| operation.golem.golem_binding_call.GOLEM_BINDING_DESCRIBE_ADAPTER | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.CMakeLists.txt.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.CMakePresets.json.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.bindings.native.bridge.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.bindings.python.src.golem_runtime.__init__.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.bindings.typescript.index.d.ts.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.bindings.typescript.index.mjs.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.bindings.typescript.native.addon.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.conanfile.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.adapter_descriptor.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.adapter_protocol.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.admission.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.agent_session.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.allocator.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.approval.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.arena.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.binding.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.candidate.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.cli.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.completion.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.context.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.core.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.cost.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.daemon.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.discovery.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.document.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.error.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.event_reader.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.evidence.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.execution.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.gateway.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.inventory.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.journal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.lease.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.lineage.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.optimization.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.policy.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.prepared_runtime.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.proof.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.record.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.reentry.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.replay.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.research.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.resource.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.role_contract.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.runtime.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.runtime_event.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.runtime_profile.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.session_binding.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.supervisor.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.system_error.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.types.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.version.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.worker.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.workflow.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.workflow_template.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.include.golem.workspace.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.plugins.golem..codex-plugin.plugin.json.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.plugins.golem..mcp.json.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.plugins.golem.scripts.launcher.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.plugins.golem.skills.golem-setup.SKILL.md.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.pyproject.toml.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.source_policy.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.adapter.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.descriptor_codec.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.descriptor_guard.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.descriptor_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.descriptor_model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.descriptor_probe.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.envelope_json.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.envelope_msgpack.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.gateway.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.noop.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.schema.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.adapter_protocol.schema.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.binding.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.binding_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.clock.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.coordinator.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.history.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.history_incremental.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.record.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.rejection.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.agent_session.storage.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.cohort.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.comparison.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.controller.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.current.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.diff.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.diff_content.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.evidence.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.isolation.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.patch.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.candidate.store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.adapter.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.adapter_descriptor.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.agent_session.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.approval.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.candidate.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.candidate_host.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.candidate_host_cli.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.candidate_host_config.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.candidate_host_runtime.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.candidate_host_transport.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.capsule.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.completion.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.context.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.context_tokenizer.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.context_tokenizer.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.daemon.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.daemon_worker.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.daemon_worker.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.discovery.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.doctor.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.document.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.error.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.error.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.events.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.execution.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.io.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.journal.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.json.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.lineage.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.main.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.output.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.output.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.projection.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.proof.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.reentry.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.research.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.research_bundle.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.role.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.runtime.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.runtime_profile.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.work.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.work.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.workflow.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cli.workflow_template.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.allocator.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.arena.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.diagnostic.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.error.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.json.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.json.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.record.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.record_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.span.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.system_error.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.types.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.common.version.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.deliverable.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.evaluator.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.predicate_roles.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.predicate_v1.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.recovery.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.renderer_v1.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.report.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.completion.store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.core.authorization.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.core.capsule.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.core.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.core.loop_controller.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.core.memory.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.core.stage_graph.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.core.stage_run.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.core.work_run.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cost.budget.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cost.cache.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cost.import.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cost.inbox.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cost.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cost.ledger.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.cost.usage.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.admission.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.admission_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.admission_model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.admission_storage.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.admission_work.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.cgroup_exec.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.cgroup_exec_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.cgroup_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.event_reader.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.event_sse.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.events.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.events_admission.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.events_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.queue.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.recovery.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.resource.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.resource_io.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.scheduler.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.storage.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.supervisor.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.daemon.worker.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.discovery.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.discovery.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.discovery.report.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.discovery.snapshot.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.document.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.document.markdown.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.document.record.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.document.record_read.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.document.registry.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.document.schema.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.document.storage.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.evidence.cas.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.evidence.digest.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.evidence.fs.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.evidence.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.evidence.read.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.evidence.receipt.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.bundle.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.change.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.command.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.inventory_ref.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.logs.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.proof_format.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.proof_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.proof_pack.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.proof_store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.report.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.runner.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.execution.store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.__init__.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.adapters.__init__.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.adapters.base.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.adapters.local.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.cli.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.core.__init__.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.core.models.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.core.optimization.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.core.serialization.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.evidence.__init__.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.evidence.store.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.policies.__init__.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.policies.autonomy.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.runtime.__init__.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.runtime.lease.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.golem.runtime.loop.py.historical | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.fragment.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.fragment.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.inventory.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.inventory.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.journal.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.journal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.object.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.object.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.object_graph.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.object_graph.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.object_inventory.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.object_inventory.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.quota.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.quota.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.schema.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.intent.schema.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.inventory.capture.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.inventory.compare.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.inventory.git_record.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.inventory.git_record.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.inventory.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.inventory.matcher.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.inventory.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.journal.capsule_codec.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.journal.codec.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.journal.event.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.journal.file.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.journal.inspect.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.journal.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.journal.replay.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.lineage.codec.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.lineage.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.lineage.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.lineage.query.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.lineage.store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.optimization.execution.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.optimization.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.optimization.selection.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.policy.approval_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.policy.approval_model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.policy.approval_scope.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.policy.approval_store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.policy.artifact.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.policy.autonomy.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.policy.fallback.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.reentry.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.reentry.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.reentry.store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.reentry.workflow.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.replay.apply.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.replay.engine.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.replay.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.bundle.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.bundle_format.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.bundle_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.cohort.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.compare.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.metrics.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.metrics_report.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.observability.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.outcome.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.report.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.runtime_observability.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.research.store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.lease.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.loop.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.prepared_cache.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.profile_binding.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.profile_cache.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.profile_codec.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.profile_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.profile_link.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.profile_model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.runtime.profile_store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.context_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.context_model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.context_projection.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.context_selection.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.graph.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.query.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.role_contract.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.role_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.role_store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.template.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.template_builtin.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.template_guard.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workflow.template_internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workspace.git.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workspace.internal.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workspace.lifecycle.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workspace.model.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.src.workspace.store.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.agent_entrypoint.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.agent_io.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.agent_lifecycle.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.benchmark_intent_journal.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.benchmark_orchestration.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.benchmark_runtime.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.billing_evidence.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.check_guard_mutations.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.classify_failures.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.codex_hosted.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.context_resume.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.doctor_environment.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.event_bridge.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.event_bridge_limits.h.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.evidence_adapters.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.evidence_contract.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.evidence_export.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.execution_record.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.github_checks.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.github_context.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.github_policy.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.hosted_usage.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.install_conan_cli.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.instruction_bundle.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_approval_host.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_backend.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_codex_plugin.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_config.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_contract.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_gateway.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_gateway_auth.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_gateway_contract.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_hook_contract.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_hooks.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_install.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_launch.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_lifecycle.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_mcp.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_mcpb.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_mcpb_entry.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_mutation_contract.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_mutation_mcp.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_mutations.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_recovery.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_registry.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_reload_probe.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_service.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_transfer.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_update.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.intent_authority.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.intent_authority_host.c.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.intent_authority_lifecycle.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.isolation_canary.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.judgment_record.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.native_record.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.provider_costs.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.provider_usage.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.remote_status.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.retire_legacy_cli.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.revision_status.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.status_collector.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.syscall_record.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.usage_pipeline.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_agent.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_alpha.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_environment.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_gateway_schema.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_hook_schema.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_install_schema.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_integration_schema.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_isolation.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_mutation_schema.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_orchestration.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_preflight.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_resource.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_runtime.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_runtime_legacy.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.verify_update_schema.py.internal | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.bindings.native.bridge.c.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.bindings.typescript.index.d.ts.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.bindings.typescript.index.mjs.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.bindings.typescript.native.addon.c.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.plugins.golem.scripts.launcher.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.src.cli.adapter.c.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.src.cli.adapter.c.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.src.cli.agent_session.c.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.src.cli.agent_session.c.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.src.cli.execution.c.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.src.cli.research.c.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.src.cli.work.c.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.src.cli.work.c.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.src.golem.cli.py.commands.excluded | UNSUPPORTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.agent_entrypoint.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.agent_entrypoint.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ, OWNER_ONLY | MCP_READ, OWNER_ONLY | REVIEWED |
| surface.tools.agent_io.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.tools.agent_io.py.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.agent_lifecycle.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.tools.agent_lifecycle.py.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.billing_evidence.py.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.billing_evidence.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.evidence_adapters.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.tools.evidence_export.py.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.evidence_export.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.tools.hosted_usage.py.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.instruction_bundle.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.instruction_bundle.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ, OWNER_ONLY | MCP_READ, OWNER_ONLY | REVIEWED |
| surface.tools.integration_gateway_contract.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ, OWNER_ONLY | MCP_READ, OWNER_ONLY | REVIEWED |
| surface.tools.integration_hook_contract.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ, OWNER_ONLY | MCP_READ, OWNER_ONLY | REVIEWED |
| surface.tools.integration_install.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.integration_mutation_contract.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ, OWNER_ONLY | MCP_READ, OWNER_ONLY | REVIEWED |
| surface.tools.integration_recovery.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.integration_registry.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.integration_transfer.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.integration_update.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.provider_costs.py.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.provider_costs.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.tools.status_collector.py.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.status_collector.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| surface.tools.usage_pipeline.py.commands.action | IMPLEMENTED | HOST_INTERNAL, MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| surface.tools.verify_agent.py.commands.owner | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.verify_agent.py.commands.read | IMPLEMENTED | HOST_INTERNAL, MCP_READ | MCP_READ | REVIEWED |
| internal.publication_guard.fixed_values | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| m1.tool.approval_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.artifact_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.binding_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.bundle_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.configuration_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.context_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.diagnostic_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.discovery_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.document_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.events_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.journal_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.native_validate | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.profile_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.reentry_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.report_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.revision_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.role_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.session_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.template_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.usage_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m1.tool.workflow_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.completion.inspect | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.reentry.inspect | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| surface.tools.integration_reads.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_read_resources.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_read_views.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_read_resources.owner-commands.schema | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.integration_read_resources.owner-commands.plan | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| m2.tool.action_confirm | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m2.tool.action_prepare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m2.tool.approved_action_prepare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m2.tool.contract_prepare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m2.tool.inputs_prepare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m2.tool.plan_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.agent_session.validate | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| surface.tools.integration_preparations.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_prepare_builders.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| m3.tool.adapter_noop_run | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.approval_request | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.binding_attach | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.completion_finalize | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.completion_report | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.context_publish | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.discovery_snapshot | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.document_project | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.lineage_store | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.profile_register | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.reentry_decide | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.reentry_report | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.role_assess | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.role_enroll | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.run_link | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.session_heartbeat | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.session_reject_output | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.session_start | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.work_create | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m3.tool.work_noop_run | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.approval.validate | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.lineage.store | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.role.request-validate | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| surface.tools.integration_task_actions.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| m4.tool.cost_inbox_reconcile | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m4.tool.evidence_import | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m4.tool.execution_verify | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m4.tool.helper_execute | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m4.tool.proof_publish | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m4.tool.research_export | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m4.tool.research_request | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m4.tool.cost_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m4.tool.execution_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m4.tool.proof_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m4.tool.research_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.execution.verify | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.execution.verify-authorized | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.research.redaction-validate | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| surface.tools.integration_quality_actions.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_quality_reads.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_helper_contract.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| owner.integration_helper_contract.schema | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| owner.integration_helper_contract.plan | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| cli.dispatch.work.--noop | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.work.inbox | IMPLEMENTED | MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.work.report | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.dispatch.work.validate | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m5.tool.candidate_request | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m5.tool.inventory_capture | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m5.tool.workspace_request | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| m5.tool.candidate_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m5.tool.inventory_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m5.tool.workspace_read | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m5.tool.merge_prepare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| m5.tool.parallel_prepare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| cli.route.inventory | IMPLEMENTED | MCP_READ, MCP_REVIEWED_ACTION | MCP_READ, MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.work.inventory | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.work.capture | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| cli.dispatch.work.compare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| surface.tools.integration_parallel_actions.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_parallel_reads.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_parallel_hosts.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_parallel_preparations.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| owner.integration_parallel_hosts.schema | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| owner.integration_parallel_hosts.plan | IMPLEMENTED | OWNER_ONLY | OWNER_ONLY | REVIEWED |
| surface.tools.integration_feature_profiles.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_distribution.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_distribution_entry.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.tools.integration_owner_maintenance.py.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.plugins.golem.skills.golem-work.SKILL.md.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.plugins.golem.skills.golem-work.agents.openai.yaml.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| surface.plugins.golem.skills.golem-work.references.profiles.md.file-surface | IMPLEMENTED | HOST_INTERNAL | HOST_INTERNAL | REVIEWED |
| mcp.management.tool.management_catalog | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| mcp.management.tool.management_prepare | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| mcp.management.tool.management_request | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.tool.management_result | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| mcp.management.route.daemon_status | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.daemon_init | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.daemon_submit | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.daemon_run_once | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.daemon_drain | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.daemon_recover | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.journal_inspect | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.journal_verify_salvage | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.journal_salvage | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.adapter_describe | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.adapter_noop_probe | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.admission_probe | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.approval_decide | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.approval_describe | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.tool.management_host_status | IMPLEMENTED | MCP_READ | MCP_READ | REVIEWED |
| mcp.management.route.adapter_convert | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.adapter_probe | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.candidate_serve | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |
| mcp.management.route.candidate_stop | IMPLEMENTED | MCP_REVIEWED_ACTION | MCP_REVIEWED_ACTION | REVIEWED |

## Observed entrypoints

| Kind | Source | Entrypoint | Selector |
| --- | --- | --- | --- |
| NATIVE_OPERATION | src/agent_session/coordinator.c | golem_agent_session_call | context |
| NATIVE_OPERATION | src/agent_session/coordinator.c | golem_agent_session_call | next |
| NATIVE_OPERATION | src/agent_session/coordinator.c | golem_agent_session_call | reject_output |
| NATIVE_OPERATION | src/agent_session/coordinator.c | golem_agent_session_call | resume |
| NATIVE_OPERATION | src/agent_session/coordinator.c | golem_agent_session_call | status |
| NATIVE_OPERATION | src/agent_session/coordinator.c | prepare | begin |
| NATIVE_OPERATION | src/agent_session/coordinator.c | prepare | claim |
| NATIVE_OPERATION | src/agent_session/coordinator.c | prepare | heartbeat |
| NATIVE_OPERATION | src/agent_session/coordinator.c | prepare | reject_output |
| NATIVE_OPERATION | src/agent_session/coordinator.c | prepare | resume |
| NATIVE_OPERATION | src/agent_session/coordinator.c | prepare | start |
| NATIVE_OPERATION | src/agent_session/coordinator.c | prepare | submit |
| NATIVE_OPERATION | src/agent_session/coordinator.c | query | next |
| NATIVE_OPERATION | src/agent_session/coordinator.c | query | status |
| NATIVE_OPERATION | src/completion/model.c | co_validate_v1 | finalize |
| NATIVE_OPERATION | src/completion/model.c | co_validate_v1 | resume |
| CLI_ROUTE | src/cli/workflow.c | golem_cli_workflow | inputs |
| CLI_ROUTE | src/cli/workflow.c | golem_cli_workflow | next |
| CLI_ROUTE | src/cli/workflow.c | golem_cli_workflow | select |
| CLI_ROUTE | src/cli/workflow.c | golem_cli_workflow | template |
| CLI_ROUTE | src/cli/workflow.c | golem_cli_workflow | trace |
| CLI_ROUTE | src/cli/main.c | dispatch | --help |
| CLI_ROUTE | src/cli/main.c | dispatch | --version |
| CLI_ROUTE | src/cli/main.c | dispatch | adapter |
| CLI_ROUTE | src/cli/main.c | dispatch | agent |
| CLI_ROUTE | src/cli/main.c | dispatch | approval |
| CLI_ROUTE | src/cli/main.c | dispatch | candidate |
| CLI_ROUTE | src/cli/main.c | dispatch | capsule |
| CLI_ROUTE | src/cli/main.c | dispatch | completion |
| CLI_ROUTE | src/cli/main.c | dispatch | context |
| CLI_ROUTE | src/cli/main.c | dispatch | cost |
| CLI_ROUTE | src/cli/main.c | dispatch | daemon |
| CLI_ROUTE | src/cli/main.c | dispatch | discovery |
| CLI_ROUTE | src/cli/main.c | dispatch | doctor |
| CLI_ROUTE | src/cli/main.c | dispatch | document |
| CLI_ROUTE | src/cli/main.c | dispatch | events |
| CLI_ROUTE | src/cli/main.c | dispatch | evidence |
| CLI_ROUTE | src/cli/main.c | dispatch | execution |
| CLI_ROUTE | src/cli/main.c | dispatch | init |
| CLI_ROUTE | src/cli/main.c | dispatch | journal |
| CLI_ROUTE | src/cli/main.c | dispatch | lineage |
| CLI_ROUTE | src/cli/main.c | dispatch | output |
| CLI_ROUTE | src/cli/main.c | dispatch | profile |
| CLI_ROUTE | src/cli/main.c | dispatch | proof |
| CLI_ROUTE | src/cli/main.c | dispatch | reentry |
| CLI_ROUTE | src/cli/main.c | dispatch | replay |
| CLI_ROUTE | src/cli/main.c | dispatch | research |
| CLI_ROUTE | src/cli/main.c | dispatch | role |
| CLI_ROUTE | src/cli/main.c | dispatch | run |
| CLI_ROUTE | src/cli/main.c | dispatch | session |
| CLI_ROUTE | src/cli/main.c | dispatch | work |
| CLI_ROUTE | src/cli/main.c | dispatch | workflow |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | completion_check |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | context_get |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | evidence_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | handoff_prepare |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | history_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | projects_list |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | work_inspect |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | document_submit |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | execution_request |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | session_begin |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | session_claim |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | session_reconcile |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | session_resume |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | session_submit |
| CLI_ROUTE | src/cli/adapter.c | golem_cli_adapter | convert |
| CLI_ROUTE | src/cli/adapter.c | golem_cli_adapter | describe |
| CLI_ROUTE | src/cli/adapter.c | golem_cli_adapter | noop |
| CLI_ROUTE | src/cli/adapter.c | golem_cli_adapter | probe |
| CLI_ROUTE | src/cli/agent_session.c | golem_cli_agent_session | call |
| CLI_ROUTE | src/cli/agent_session.c | golem_cli_agent_session | resume |
| CLI_ROUTE | src/cli/approval.c | golem_cli_approval | call |
| CLI_ROUTE | src/cli/approval.c | golem_cli_approval | describe |
| CLI_ROUTE | src/cli/candidate.c | golem_cli_candidate | call |
| CLI_ROUTE | src/cli/candidate.c | golem_cli_candidate | diff |
| CLI_ROUTE | src/cli/candidate.c | golem_cli_candidate | gates |
| CLI_ROUTE | src/cli/candidate.c | golem_cli_candidate | host-validate |
| CLI_ROUTE | src/cli/candidate.c | golem_cli_candidate | request-digest |
| CLI_ROUTE | src/cli/candidate.c | golem_cli_candidate | serve |
| CLI_ROUTE | src/cli/candidate.c | golem_cli_candidate | status |
| CLI_ROUTE | src/cli/candidate.c | golem_cli_candidate | validate |
| CLI_ROUTE | src/cli/completion.c | golem_cli_completion | call |
| CLI_ROUTE | src/cli/completion.c | golem_cli_completion | check |
| CLI_ROUTE | src/cli/completion.c | golem_cli_completion | report |
| CLI_ROUTE | src/cli/completion.c | golem_cli_completion | validate |
| CLI_ROUTE | src/cli/context.c | golem_cli_context | candidate |
| CLI_ROUTE | src/cli/context.c | golem_cli_context | markdown |
| CLI_ROUTE | src/cli/context.c | golem_cli_context | publish |
| CLI_ROUTE | src/cli/context.c | golem_cli_context | read |
| CLI_ROUTE | src/cli/context.c | golem_cli_context | render |
| CLI_ROUTE | src/cli/daemon.c | golem_cli_daemon | init |
| CLI_ROUTE | src/cli/daemon.c | golem_cli_daemon | recover |
| CLI_ROUTE | src/cli/daemon.c | golem_cli_daemon | run |
| CLI_ROUTE | src/cli/daemon.c | golem_cli_daemon | status |
| CLI_ROUTE | src/cli/daemon.c | golem_cli_daemon | submit |
| CLI_ROUTE | src/cli/discovery.c | golem_cli_discovery | report |
| CLI_ROUTE | src/cli/discovery.c | golem_cli_discovery | snapshot |
| CLI_ROUTE | src/cli/discovery.c | golem_cli_discovery | validate |
| CLI_ROUTE | src/cli/doctor.c | golem_cli_doctor | admission |
| CLI_ROUTE | src/cli/doctor.c | golem_cli_doctor | clock |
| CLI_ROUTE | src/cli/doctor.c | golem_cli_doctor | work |
| CLI_ROUTE | src/cli/document.c | golem_cli_document | inspect |
| CLI_ROUTE | src/cli/document.c | golem_cli_document | project |
| CLI_ROUTE | src/cli/document.c | golem_cli_document | start |
| CLI_ROUTE | src/cli/document.c | golem_cli_document | submit |
| CLI_ROUTE | src/cli/document.c | golem_cli_document | validate |
| CLI_ROUTE | src/cli/events.c | golem_cli_events | --jsonl |
| CLI_ROUTE | src/cli/events.c | golem_cli_events | --otlp |
| CLI_ROUTE | src/cli/events.c | golem_cli_events | --prov |
| CLI_ROUTE | src/cli/execution.c | golem_cli_execution | bundle |
| CLI_ROUTE | src/cli/execution.c | golem_cli_execution | call |
| CLI_ROUTE | src/cli/execution.c | golem_cli_execution | render |
| CLI_ROUTE | src/cli/execution.c | golem_cli_execution | validate |
| CLI_ROUTE | src/cli/journal.c | golem_cli_journal | inspect |
| CLI_ROUTE | src/cli/journal.c | golem_cli_journal | salvage |
| CLI_ROUTE | src/cli/journal.c | golem_cli_journal | verify-salvage |
| CLI_ROUTE | src/cli/lineage.c | golem_cli_lineage | trace |
| CLI_ROUTE | src/cli/lineage.c | golem_cli_lineage | verify |
| CLI_ROUTE | src/cli/output.c | golem_cli_output | read |
| CLI_ROUTE | src/cli/runtime_profile.c | golem_cli_runtime_profile | current |
| CLI_ROUTE | src/cli/runtime_profile.c | golem_cli_runtime_profile | link |
| CLI_ROUTE | src/cli/runtime_profile.c | golem_cli_runtime_profile | register |
| CLI_ROUTE | src/cli/runtime_profile.c | golem_cli_runtime_profile | validate |
| CLI_ROUTE | src/cli/proof.c | golem_cli_proof | integrity |
| CLI_ROUTE | src/cli/proof.c | golem_cli_proof | publish |
| CLI_ROUTE | src/cli/proof.c | golem_cli_proof | render |
| CLI_ROUTE | src/cli/proof.c | golem_cli_proof | verify |
| CLI_ROUTE | src/cli/proof.c | golem_cli_proof | verify-dir |
| CLI_ROUTE | src/cli/reentry.c | golem_cli_reentry | call |
| CLI_ROUTE | src/cli/reentry.c | golem_cli_reentry | report |
| CLI_ROUTE | src/cli/reentry.c | golem_cli_reentry | validate |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | attempt |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | bundle-verify |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | call |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | case |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | cohort |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | compare |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | export |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | inspect |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | metrics |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | observability |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | outcome |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | report |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | status |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | validate |
| CLI_ROUTE | src/cli/role.c | golem_cli_role | call |
| CLI_ROUTE | src/cli/role.c | golem_cli_role | template |
| CLI_ROUTE | src/cli/role.c | golem_cli_role | validate |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | capsule |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | cost |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | init |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | replay |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | run |
| CLI_ROUTE | src/cli/workflow_template.c | golem_cli_workflow_template | instantiate |
| CLI_ROUTE | src/cli/workflow_template.c | golem_cli_workflow_template | list |
| CLI_ROUTE | src/cli/workflow_template.c | golem_cli_workflow_template | show |
| CLI_ROUTE | src/cli/workflow_template.c | golem_cli_workflow_template | validate |
| C_PUBLIC_DECLARATION | include/golem/runtime_event.h | golem_runtime_cursor_parse | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_event.h | golem_runtime_events_snapshot | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_event.h | golem_runtime_events_export | None |
| C_PUBLIC_DECLARATION | include/golem/error.h | golem_status_string | None |
| CLI_ROUTE | tools/integration_transfer.py | main | schema |
| CLI_ROUTE | tools/integration_transfer.py | main | plan |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_adapter_descriptor_validate | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_adapter_descriptor_decode | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_adapter_descriptor_encode | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_adapter_descriptor_digest | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_adapter_descriptor_from_v1 | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_adapter_descriptor_to_v1 | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_adapter_descriptor_current | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_harness_compatible | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_harness_observation_encode | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_adapter_dispatch_checked | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_harness_probe | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_harness_probe_encode | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_create | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_free | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_probe | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_request_init | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_result_validate | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_dispatch | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_envelope_encode | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_envelope_decode | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_msgpack_encode | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_msgpack_decode | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_noop_create | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_noop_run_stage | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_open | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_open_diagnostic | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_close | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_identity | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_enqueue | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_lookup | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_grant | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_resize | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_cancel | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_dispatch | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_begin | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_publish_work | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_settle | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_release | None |
| C_PUBLIC_DECLARATION | include/golem/agent_session.h | golem_agent_request_validate | None |
| C_PUBLIC_DECLARATION | include/golem/agent_session.h | golem_agent_session_call | None |
| C_PUBLIC_DECLARATION | include/golem/agent_session.h | golem_agent_session_resume_context | None |
| C_PUBLIC_DECLARATION | include/golem/agent_session.h | golem_agent_reply_free | None |
| C_PUBLIC_DECLARATION | include/golem/allocator.h | golem_allocator_default | None |
| C_PUBLIC_DECLARATION | include/golem/allocator.h | golem_allocator_validate | None |
| C_PUBLIC_DECLARATION | include/golem/allocator.h | golem_allocator_alloc | None |
| C_PUBLIC_DECLARATION | include/golem/allocator.h | golem_allocator_alloc_zero | None |
| C_PUBLIC_DECLARATION | include/golem/allocator.h | golem_allocator_free | None |
| C_PUBLIC_DECLARATION | include/golem/approval.h | golem_approval_request_validate | None |
| C_PUBLIC_DECLARATION | include/golem/approval.h | golem_approval_describe | None |
| C_PUBLIC_DECLARATION | include/golem/approval.h | golem_approval_call | None |
| C_PUBLIC_DECLARATION | include/golem/approval.h | golem_execution_call_receipted | None |
| C_PUBLIC_DECLARATION | include/golem/arena.h | golem_arena_init | None |
| C_PUBLIC_DECLARATION | include/golem/arena.h | golem_arena_alloc | None |
| C_PUBLIC_DECLARATION | include/golem/arena.h | golem_arena_reset | None |
| C_PUBLIC_DECLARATION | include/golem/arena.h | golem_arena_used_get | None |
| C_PUBLIC_DECLARATION | include/golem/binding.h | golem_binding_abi_version | None |
| C_PUBLIC_DECLARATION | include/golem/binding.h | golem_binding_call | None |
| C_PUBLIC_DECLARATION | include/golem/binding.h | golem_binding_free | None |
| C_PUBLIC_DECLARATION | include/golem/binding.h | golem_binding_status_message | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_current_host | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_validate | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_gate_digest | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_call | None |
| C_PUBLIC_DECLARATION | include/golem/completion.h | golem_completion_validate | None |
| C_PUBLIC_DECLARATION | include/golem/completion.h | golem_completion_call | None |
| C_PUBLIC_DECLARATION | include/golem/completion.h | golem_completion_report | None |
| C_PUBLIC_DECLARATION | include/golem/context.h | golem_context_request_validate | None |
| C_PUBLIC_DECLARATION | include/golem/context.h | golem_context_render | None |
| C_PUBLIC_DECLARATION | include/golem/context.h | golem_context_publish | None |
| C_PUBLIC_DECLARATION | include/golem/context.h | golem_context_read | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_name | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_graph_default_spec | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_graph_create | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_graph_create_with_allocator | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_graph_free | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_graph_spec_get | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_graph_next | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_graph_validate_transition | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_graph_reentry | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_transition_validate | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_capsule_create | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_capsule_create_with_allocator | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_capsule_free | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_capsule_spec_borrow | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_create | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_create_with_allocator | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_free | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_id_borrow | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_snapshot_get | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_attempts_get | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_stage_borrow | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_stage_run_snapshot_get | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_begin | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_finish | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_reenter | None |
| C_PUBLIC_DECLARATION | include/golem/core.h | golem_work_run_cancel | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_token_usage_add | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_cost_calculate | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_budget_check | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_enable | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_borrow | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_plan | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_report | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_cost_report_decode | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_report_json | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_inbox_enable | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_inbox_sync | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_inbox_status | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_work_run_cost_settle | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_cost_ledger_entry_get | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_cost_ledger_report_get | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_cost_ledger_totals_get | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_cost_ledger_stage_totals_get | None |
| C_PUBLIC_DECLARATION | include/golem/cost.h | golem_cost_ledger_options_get | None |
| C_PUBLIC_DECLARATION | include/golem/daemon.h | golem_daemon_recover | None |
| C_PUBLIC_DECLARATION | include/golem/daemon.h | golem_daemon_init | None |
| C_PUBLIC_DECLARATION | include/golem/daemon.h | golem_daemon_submit | None |
| C_PUBLIC_DECLARATION | include/golem/daemon.h | golem_daemon_inspect | None |
| C_PUBLIC_DECLARATION | include/golem/daemon.h | golem_daemon_open | None |
| C_PUBLIC_DECLARATION | include/golem/daemon.h | golem_daemon_tick | None |
| C_PUBLIC_DECLARATION | include/golem/daemon.h | golem_daemon_close | None |
| C_PUBLIC_DECLARATION | include/golem/discovery.h | golem_discovery_validate | None |
| C_PUBLIC_DECLARATION | include/golem/discovery.h | golem_discovery_report | None |
| C_PUBLIC_DECLARATION | include/golem/discovery.h | golem_discovery_snapshot | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_work_spec_validate | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_validate | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_store_create | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_store_open | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_store_close | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_generation | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_submit | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_inspect | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_body | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_metadata | None |
| C_PUBLIC_DECLARATION | include/golem/document.h | golem_document_project | None |
| C_PUBLIC_DECLARATION | include/golem/error.h | golem_diagnostic_clear | None |
| C_PUBLIC_DECLARATION | include/golem/error.h | golem_diagnostic_set | None |
| C_PUBLIC_DECLARATION | include/golem/event_reader.h | golem_event_reader_open | None |
| C_PUBLIC_DECLARATION | include/golem/event_reader.h | golem_event_reader_refresh | None |
| C_PUBLIC_DECLARATION | include/golem/event_reader.h | golem_event_reader_read | None |
| C_PUBLIC_DECLARATION | include/golem/event_reader.h | golem_event_reader_close | None |
| C_PUBLIC_DECLARATION | include/golem/event_reader.h | golem_runtime_event_sse | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_digest_bytes | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_digest_file | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_digest_parse | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_digest_format | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_evidence_open | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_evidence_close | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_evidence_put | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_evidence_import | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_evidence_verify | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_evidence_read | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_receipt_encode | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_receipt_decode | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_evidence_receipt_store | None |
| C_PUBLIC_DECLARATION | include/golem/evidence.h | golem_evidence_receipt_verify | None |
| C_PUBLIC_DECLARATION | include/golem/execution.h | golem_execution_contract_validate | None |
| C_PUBLIC_DECLARATION | include/golem/execution.h | golem_execution_call | None |
| C_PUBLIC_DECLARATION | include/golem/execution.h | golem_execution_call_authorized | None |
| C_PUBLIC_DECLARATION | include/golem/execution.h | golem_execution_render | None |
| C_PUBLIC_DECLARATION | include/golem/execution.h | golem_execution_reply_free | None |
| C_PUBLIC_DECLARATION | include/golem/execution.h | golem_execution_bundle_inspect | None |
| C_PUBLIC_DECLARATION | include/golem/execution.h | golem_execution_bundle_verify | None |
| C_PUBLIC_DECLARATION | include/golem/gateway.h | golem_gateway_envelope_prepare | None |
| C_PUBLIC_DECLARATION | include/golem/gateway.h | golem_gateway_envelope_decode | None |
| C_PUBLIC_DECLARATION | include/golem/inventory.h | golem_inventory_policy_validate | None |
| C_PUBLIC_DECLARATION | include/golem/inventory.h | golem_inventory_capture | None |
| C_PUBLIC_DECLARATION | include/golem/inventory.h | golem_inventory_compare | None |
| C_PUBLIC_DECLARATION | include/golem/inventory.h | golem_inventory_reply_free | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_checkpoint_get | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_inspect | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_crc32 | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_record_encode | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_record_decode | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_reader_init | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_reader_next | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_created_encode | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_event_encode | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_event_decode | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_open | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_append | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_close | None |
| C_PUBLIC_DECLARATION | include/golem/journal.h | golem_journal_replay | None |
| C_PUBLIC_DECLARATION | include/golem/lease.h | golem_lease_create | None |
| C_PUBLIC_DECLARATION | include/golem/lease.h | golem_lease_free | None |
| C_PUBLIC_DECLARATION | include/golem/lease.h | golem_lease_acquire | None |
| C_PUBLIC_DECLARATION | include/golem/lease.h | golem_lease_heartbeat | None |
| C_PUBLIC_DECLARATION | include/golem/lease.h | golem_lease_validate | None |
| C_PUBLIC_DECLARATION | include/golem/lease.h | golem_lease_release | None |
| C_PUBLIC_DECLARATION | include/golem/lease.h | golem_lease_resource_borrow | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_create | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_free | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_run_id_borrow | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_stats_get | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_stage_get | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_node_get | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_begin | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_add | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_seal | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_parents | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_predecessors | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_encode | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_decode | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_verify | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_store | None |
| C_PUBLIC_DECLARATION | include/golem/lineage.h | golem_lineage_load | None |
| C_PUBLIC_DECLARATION | include/golem/optimization.h | golem_optimization_policy_init | None |
| C_PUBLIC_DECLARATION | include/golem/optimization.h | golem_cache_break_even | None |
| C_PUBLIC_DECLARATION | include/golem/optimization.h | golem_fallback_check | None |
| C_PUBLIC_DECLARATION | include/golem/optimization.h | golem_work_run_optimization_enable | None |
| C_PUBLIC_DECLARATION | include/golem/optimization.h | golem_work_run_optimization_policy_get | None |
| C_PUBLIC_DECLARATION | include/golem/optimization.h | golem_work_run_optimization_evaluate | None |
| C_PUBLIC_DECLARATION | include/golem/optimization.h | golem_work_run_begin_optimized | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_artifact_encode | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_artifact_decode | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_spec_init | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_spec_validate | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_create | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_free | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_spec_get | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_autonomy_evaluate | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_evaluate | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_verdict_name | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_policy_reason_name | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_work_run_permission_request | None |
| C_PUBLIC_DECLARATION | include/golem/policy.h | golem_work_run_begin_authorized | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_cache_create | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_cache_acquire | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_runtime_view | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_cache_invalidate | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_cache_release | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_cache_close | None |
| C_PUBLIC_DECLARATION | include/golem/proof.h | golem_proof_render | None |
| C_PUBLIC_DECLARATION | include/golem/proof.h | golem_proof_verify | None |
| C_PUBLIC_DECLARATION | include/golem/proof.h | golem_proof_integrity | None |
| C_PUBLIC_DECLARATION | include/golem/proof.h | golem_proof_publish | None |
| C_PUBLIC_DECLARATION | include/golem/proof.h | golem_proof_verify_directory | None |
| C_PUBLIC_DECLARATION | include/golem/record.h | golem_record_begin | None |
| C_PUBLIC_DECLARATION | include/golem/record.h | golem_record_write | None |
| C_PUBLIC_DECLARATION | include/golem/record.h | golem_record_finish | None |
| C_PUBLIC_DECLARATION | include/golem/record.h | golem_record_call | None |
| C_PUBLIC_DECLARATION | include/golem/record.h | golem_record_last_api_outcome | None |
| C_PUBLIC_DECLARATION | include/golem/reentry.h | golem_reentry_validate | None |
| C_PUBLIC_DECLARATION | include/golem/reentry.h | golem_reentry_call | None |
| C_PUBLIC_DECLARATION | include/golem/reentry.h | golem_reentry_report | None |
| C_PUBLIC_DECLARATION | include/golem/replay.h | golem_replay_create | None |
| C_PUBLIC_DECLARATION | include/golem/replay.h | golem_replay_expect_checkpoint | None |
| C_PUBLIC_DECLARATION | include/golem/replay.h | golem_replay_feed | None |
| C_PUBLIC_DECLARATION | include/golem/replay.h | golem_replay_finish | None |
| C_PUBLIC_DECLARATION | include/golem/replay.h | golem_replay_progress_get | None |
| C_PUBLIC_DECLARATION | include/golem/replay.h | golem_replay_free | None |
| C_PUBLIC_DECLARATION | include/golem/replay.h | golem_journal_recover | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_validate | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_call | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_inspect | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_report | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_status | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_metrics | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_metrics_report | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_compare | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_redaction_validate | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_bundle | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_bundle_verify | None |
| C_PUBLIC_DECLARATION | include/golem/research.h | golem_research_observability | None |
| C_PUBLIC_DECLARATION | include/golem/resource.h | golem_resource_run | None |
| C_PUBLIC_DECLARATION | include/golem/role_contract.h | golem_role_validate | None |
| C_PUBLIC_DECLARATION | include/golem/role_contract.h | golem_role_request_validate | None |
| C_PUBLIC_DECLARATION | include/golem/role_contract.h | golem_role_template | None |
| C_PUBLIC_DECLARATION | include/golem/role_contract.h | golem_role_call | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_create | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_free | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_recover | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_step | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_drive | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_cancel | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_report_get | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_run_borrow | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_lease_bind | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_checkpoint | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_heartbeat | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_event.h | golem_worker_events | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_event.h | golem_admission_events | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_event.h | golem_runtime_cursor_format | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_event.h | golem_runtime_event_name | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_parse | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_free | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_digest | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_encode | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_cache_create | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_cache_acquire | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_cache_release | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_cache_close | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_register | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_profile_current | None |
| C_PUBLIC_DECLARATION | include/golem/runtime_profile.h | golem_runtime_link_run | None |
| C_PUBLIC_DECLARATION | include/golem/session_binding.h | golem_session_binding_request_validate | None |
| C_PUBLIC_DECLARATION | include/golem/session_binding.h | golem_session_binding_call | None |
| C_PUBLIC_DECLARATION | include/golem/session_binding.h | golem_work_history | None |
| C_PUBLIC_DECLARATION | include/golem/session_binding.h | golem_work_record | None |
| C_PUBLIC_DECLARATION | include/golem/session_binding.h | golem_session_fence_check | None |
| C_PUBLIC_DECLARATION | include/golem/supervisor.h | golem_supervisor_run | None |
| C_PUBLIC_DECLARATION | include/golem/supervisor.h | golem_supervisor_run_at | None |
| C_PUBLIC_DECLARATION | include/golem/supervisor.h | golem_supervisor_run_streamed | None |
| C_PUBLIC_DECLARATION | include/golem/supervisor.h | golem_supervisor_run_bulk | None |
| C_PUBLIC_DECLARATION | include/golem/supervisor.h | golem_supervisor_run_observed | None |
| C_PUBLIC_DECLARATION | include/golem/system_error.h | golem_system_error_begin | None |
| C_PUBLIC_DECLARATION | include/golem/system_error.h | golem_system_error_end | None |
| C_PUBLIC_DECLARATION | include/golem/system_error.h | golem_system_error_note | None |
| C_PUBLIC_DECLARATION | include/golem/system_error.h | golem_system_error_name | None |
| C_PUBLIC_DECLARATION | include/golem/system_error.h | golem_system_error_action | None |
| C_PUBLIC_DECLARATION | include/golem/types.h | golem_bytes_init | None |
| C_PUBLIC_DECLARATION | include/golem/types.h | golem_bytes_slice | None |
| C_PUBLIC_DECLARATION | include/golem/types.h | golem_string_view_init | None |
| C_PUBLIC_DECLARATION | include/golem/types.h | golem_string_view_from_cstr | None |
| C_PUBLIC_DECLARATION | include/golem/types.h | golem_string_view_slice | None |
| C_PUBLIC_DECLARATION | include/golem/types.h | golem_bytes_write | None |
| C_PUBLIC_DECLARATION | include/golem/types.h | golem_string_view_write | None |
| C_PUBLIC_DECLARATION | include/golem/types.h | golem_string_clone | None |
| C_PUBLIC_DECLARATION | include/golem/version.h | golem_version_string | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_options_default | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_open | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_submit | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_start | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_inspect | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_diagnostics | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_recording_status | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_cancel | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_heartbeat | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_acknowledge | None |
| C_PUBLIC_DECLARATION | include/golem/worker.h | golem_worker_close | None |
| C_PUBLIC_DECLARATION | include/golem/workflow.h | golem_document_graph_evaluate | None |
| C_PUBLIC_DECLARATION | include/golem/workflow.h | golem_workflow_select | None |
| C_PUBLIC_DECLARATION | include/golem/workflow.h | golem_workflow_inputs | None |
| C_PUBLIC_DECLARATION | include/golem/workflow.h | golem_workflow_trace | None |
| C_PUBLIC_DECLARATION | include/golem/workflow.h | golem_workflow_next | None |
| C_PUBLIC_DECLARATION | include/golem/workflow_template.h | golem_workflow_template_validate | None |
| C_PUBLIC_DECLARATION | include/golem/workflow_template.h | golem_workflow_template_builtin | None |
| C_PUBLIC_DECLARATION | include/golem/workflow_template.h | golem_workflow_template_expand | None |
| C_PUBLIC_DECLARATION | include/golem/workflow_template.h | golem_workflow_template_instantiate | None |
| C_PUBLIC_DECLARATION | include/golem/workspace.h | golem_workspace_call | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_harness_guard.observe | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_descriptor.h | golem_harness_guard.now | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_ops.probe | None |
| C_PUBLIC_DECLARATION | include/golem/adapter_protocol.h | golem_adapter_ops.run_stage | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_dispatch_ops.publish | None |
| C_PUBLIC_DECLARATION | include/golem/admission.h | golem_admission_dispatch_ops.execute | None |
| C_PUBLIC_DECLARATION | include/golem/agent_session.h | golem_agent_clock.read | None |
| C_PUBLIC_DECLARATION | include/golem/allocator.h | golem_allocator.allocate | None |
| C_PUBLIC_DECLARATION | include/golem/allocator.h | golem_allocator.deallocate | None |
| C_PUBLIC_DECLARATION | include/golem/approval.h | golem_approval_host.decide | None |
| C_PUBLIC_DECLARATION | include/golem/approval.h | golem_approval_host.recheck | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_host.check | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_host.resolve | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_host.start | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_host.cancel | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_current_options.authorize | None |
| C_PUBLIC_DECLARATION | include/golem/candidate.h | golem_candidate_current_options.request_cancel | None |
| C_PUBLIC_DECLARATION | include/golem/context.h | golem_context_tokenizer.count | None |
| C_PUBLIC_DECLARATION | include/golem/daemon.h | golem_daemon_ops.execute | None |
| C_PUBLIC_DECLARATION | include/golem/lease.h | golem_lease_ops.record | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_options.observe | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_options.prepare | None |
| C_PUBLIC_DECLARATION | include/golem/prepared_runtime.h | golem_prepared_options.clock_ns | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_ops.record | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_ops.execute | None |
| C_PUBLIC_DECLARATION | include/golem/runtime.h | golem_runtime_ops.now | None |
| C_PUBLIC_DECLARATION | include/golem/session_binding.h | golem_session_binding_host.observe | None |
| C_PUBLIC_DECLARATION | include/golem/supervisor.h | golem_supervisor_stream.write | None |
| C_PUBLIC_DECLARATION | include/golem/workspace.h | golem_workspace_host.check | None |
| C_PUBLIC_DECLARATION | include/golem/workspace.h | golem_workspace_host.pulse | None |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | begin |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | claim |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | context |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | heartbeat |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | next |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | reconcile |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | reject_output |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | resume |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | start |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | status |
| NATIVE_OPERATION | src/agent_session/coordinator.c | request_schema | submit |
| NATIVE_OPERATION | src/agent_session/coordinator.c | golem_agent_session_resume_context | resume |
| NATIVE_OPERATION | src/policy/approval_model.c | ap_request | approve |
| NATIVE_OPERATION | src/policy/approval_model.c | ap_request | deny |
| NATIVE_OPERATION | src/policy/approval_model.c | ap_request | expire |
| NATIVE_OPERATION | src/policy/approval_model.c | ap_request | recover |
| NATIVE_OPERATION | src/policy/approval_model.c | ap_request | request |
| NATIVE_OPERATION | src/policy/approval_model.c | ap_request | revoke |
| NATIVE_OPERATION | src/policy/approval_model.c | ap_request | status |
| NATIVE_OPERATION | src/completion/evaluator.c | co_validate | finalize |
| NATIVE_OPERATION | src/execution/store.c | call | finish |
| NATIVE_OPERATION | src/execution/store.c | call | prepare |
| NATIVE_OPERATION | src/execution/store.c | call | run |
| NATIVE_OPERATION | src/execution/store.c | call | verify |
| NATIVE_OPERATION | src/policy/approval_scope.c | ap_scope | finish |
| NATIVE_OPERATION | src/policy/approval_scope.c | ap_scope | prepare |
| NATIVE_OPERATION | src/policy/approval_scope.c | ap_scope | run |
| NATIVE_OPERATION | src/workflow/role_contract.c | rc_request | assess |
| NATIVE_OPERATION | src/workflow/role_contract.c | rc_request | enroll |
| NATIVE_OPERATION | src/workflow/role_contract.c | rc_request | evaluate |
| NATIVE_OPERATION | src/workflow/role_contract.c | rc_request | status |
| NATIVE_OPERATION | src/reentry/model.c | re_validate | decide |
| NATIVE_OPERATION | src/reentry/model.c | re_validate | status |
| NATIVE_OPERATION | src/agent_session/binding.c | shape | attach |
| NATIVE_OPERATION | src/agent_session/binding.c | shape | inspect |
| NATIVE_OPERATION | src/research/model.c | rs_validate | attempt-plan |
| NATIVE_OPERATION | src/research/model.c | rs_validate | attempt-record |
| NATIVE_OPERATION | src/research/model.c | rs_validate | case-create |
| NATIVE_OPERATION | src/research/model.c | rs_validate | outcome-enroll |
| NATIVE_OPERATION | src/research/cohort.c | rs_is_cohort | cohort-create |
| NATIVE_OPERATION | src/research/cohort.c | rs_is_cohort | cohort-observe |
| NATIVE_OPERATION | src/research/outcome.c | rs_is_outcome | adjudicate |
| NATIVE_OPERATION | src/research/outcome.c | rs_is_outcome | outcome-enroll |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | cancel |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | cohort-record |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | compare |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | create |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | diff |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | diff-seal |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | enroll |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | finish |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | reserve |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | review |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | review-check |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | select |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | start |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | status |
| NATIVE_OPERATION | src/candidate/controller.c | golem_candidate_call | target-check |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | cancel |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | cohort-record |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | compare |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | diff |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | diff-seal |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | enroll |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | finish |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | reserve |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | review |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | review-check |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | select |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | start |
| NATIVE_OPERATION | src/candidate/controller.c | dispatch | target-check |
| NATIVE_OPERATION | include/golem/workspace.h | golem_workspace_operation | GOLEM_WORKSPACE_CREATE |
| NATIVE_OPERATION | include/golem/workspace.h | golem_workspace_operation | GOLEM_WORKSPACE_RESUME |
| NATIVE_OPERATION | include/golem/workspace.h | golem_workspace_operation | GOLEM_WORKSPACE_ACTIVATE |
| NATIVE_OPERATION | include/golem/workspace.h | golem_workspace_operation | GOLEM_WORKSPACE_SEAL |
| NATIVE_OPERATION | include/golem/workspace.h | golem_workspace_operation | GOLEM_WORKSPACE_RETAIN |
| NATIVE_OPERATION | include/golem/workspace.h | golem_workspace_operation | GOLEM_WORKSPACE_REMOVE |
| NATIVE_OPERATION | include/golem/binding.h | golem_binding_call | GOLEM_BINDING_VALIDATE |
| NATIVE_OPERATION | include/golem/binding.h | golem_binding_call | GOLEM_BINDING_REPLAY |
| NATIVE_OPERATION | include/golem/binding.h | golem_binding_call | GOLEM_BINDING_DESCRIBE_ADAPTER |
| NATIVE_OPERATION | CMakeLists.txt | file-surface | None |
| NATIVE_OPERATION | CMakePresets.json | file-surface | None |
| NATIVE_OPERATION | bindings/native/bridge.c | file-surface | None |
| PYTHON_DECLARATION | bindings/python/src/golem_runtime/__init__.py | file-surface | None |
| NATIVE_OPERATION | bindings/typescript/index.d.ts | file-surface | None |
| NATIVE_OPERATION | bindings/typescript/index.mjs | file-surface | None |
| NATIVE_OPERATION | bindings/typescript/native/addon.c | file-surface | None |
| PYTHON_DECLARATION | conanfile.py | file-surface | None |
| NATIVE_OPERATION | include/golem/adapter_descriptor.h | file-surface | None |
| NATIVE_OPERATION | include/golem/adapter_protocol.h | file-surface | None |
| NATIVE_OPERATION | include/golem/admission.h | file-surface | None |
| NATIVE_OPERATION | include/golem/agent_session.h | file-surface | None |
| NATIVE_OPERATION | include/golem/allocator.h | file-surface | None |
| NATIVE_OPERATION | include/golem/approval.h | file-surface | None |
| NATIVE_OPERATION | include/golem/arena.h | file-surface | None |
| NATIVE_OPERATION | include/golem/binding.h | file-surface | None |
| NATIVE_OPERATION | include/golem/candidate.h | file-surface | None |
| NATIVE_OPERATION | include/golem/cli.h | file-surface | None |
| NATIVE_OPERATION | include/golem/completion.h | file-surface | None |
| NATIVE_OPERATION | include/golem/context.h | file-surface | None |
| NATIVE_OPERATION | include/golem/core.h | file-surface | None |
| NATIVE_OPERATION | include/golem/cost.h | file-surface | None |
| NATIVE_OPERATION | include/golem/daemon.h | file-surface | None |
| NATIVE_OPERATION | include/golem/discovery.h | file-surface | None |
| NATIVE_OPERATION | include/golem/document.h | file-surface | None |
| NATIVE_OPERATION | include/golem/error.h | file-surface | None |
| NATIVE_OPERATION | include/golem/event_reader.h | file-surface | None |
| NATIVE_OPERATION | include/golem/evidence.h | file-surface | None |
| NATIVE_OPERATION | include/golem/execution.h | file-surface | None |
| NATIVE_OPERATION | include/golem/gateway.h | file-surface | None |
| NATIVE_OPERATION | include/golem/inventory.h | file-surface | None |
| NATIVE_OPERATION | include/golem/journal.h | file-surface | None |
| NATIVE_OPERATION | include/golem/lease.h | file-surface | None |
| NATIVE_OPERATION | include/golem/lineage.h | file-surface | None |
| NATIVE_OPERATION | include/golem/optimization.h | file-surface | None |
| NATIVE_OPERATION | include/golem/policy.h | file-surface | None |
| NATIVE_OPERATION | include/golem/prepared_runtime.h | file-surface | None |
| NATIVE_OPERATION | include/golem/proof.h | file-surface | None |
| NATIVE_OPERATION | include/golem/record.h | file-surface | None |
| NATIVE_OPERATION | include/golem/reentry.h | file-surface | None |
| NATIVE_OPERATION | include/golem/replay.h | file-surface | None |
| NATIVE_OPERATION | include/golem/research.h | file-surface | None |
| NATIVE_OPERATION | include/golem/resource.h | file-surface | None |
| NATIVE_OPERATION | include/golem/role_contract.h | file-surface | None |
| NATIVE_OPERATION | include/golem/runtime.h | file-surface | None |
| NATIVE_OPERATION | include/golem/runtime_event.h | file-surface | None |
| NATIVE_OPERATION | include/golem/runtime_profile.h | file-surface | None |
| NATIVE_OPERATION | include/golem/session_binding.h | file-surface | None |
| NATIVE_OPERATION | include/golem/supervisor.h | file-surface | None |
| NATIVE_OPERATION | include/golem/system_error.h | file-surface | None |
| NATIVE_OPERATION | include/golem/types.h | file-surface | None |
| NATIVE_OPERATION | include/golem/version.h | file-surface | None |
| NATIVE_OPERATION | include/golem/worker.h | file-surface | None |
| NATIVE_OPERATION | include/golem/workflow.h | file-surface | None |
| NATIVE_OPERATION | include/golem/workflow_template.h | file-surface | None |
| NATIVE_OPERATION | include/golem/workspace.h | file-surface | None |
| NATIVE_OPERATION | plugins/golem/.codex-plugin/plugin.json | file-surface | None |
| NATIVE_OPERATION | plugins/golem/.mcp.json | file-surface | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | file-surface | None |
| NATIVE_OPERATION | plugins/golem/skills/golem-setup/SKILL.md | file-surface | None |
| NATIVE_OPERATION | pyproject.toml | file-surface | None |
| PYTHON_DECLARATION | source_policy.py | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/adapter.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/descriptor_codec.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/descriptor_guard.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/descriptor_internal.h | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/descriptor_model.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/descriptor_probe.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/envelope_json.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/envelope_msgpack.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/gateway.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/internal.h | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/model.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/noop.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/schema.c | file-surface | None |
| NATIVE_OPERATION | src/adapter_protocol/schema.h | file-surface | None |
| NATIVE_OPERATION | src/agent_session/binding.c | file-surface | None |
| NATIVE_OPERATION | src/agent_session/binding_internal.h | file-surface | None |
| NATIVE_OPERATION | src/agent_session/clock.c | file-surface | None |
| NATIVE_OPERATION | src/agent_session/coordinator.c | file-surface | None |
| NATIVE_OPERATION | src/agent_session/history.c | file-surface | None |
| NATIVE_OPERATION | src/agent_session/history_incremental.c | file-surface | None |
| NATIVE_OPERATION | src/agent_session/internal.h | file-surface | None |
| NATIVE_OPERATION | src/agent_session/model.c | file-surface | None |
| NATIVE_OPERATION | src/agent_session/record.c | file-surface | None |
| NATIVE_OPERATION | src/agent_session/rejection.c | file-surface | None |
| NATIVE_OPERATION | src/agent_session/storage.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/cohort.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/comparison.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/controller.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/current.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/diff.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/diff_content.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/evidence.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/internal.h | file-surface | None |
| NATIVE_OPERATION | src/candidate/isolation.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/model.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/patch.c | file-surface | None |
| NATIVE_OPERATION | src/candidate/store.c | file-surface | None |
| NATIVE_OPERATION | src/cli/adapter.c | file-surface | None |
| NATIVE_OPERATION | src/cli/adapter_descriptor.c | file-surface | None |
| NATIVE_OPERATION | src/cli/agent_session.c | file-surface | None |
| NATIVE_OPERATION | src/cli/approval.c | file-surface | None |
| NATIVE_OPERATION | src/cli/candidate.c | file-surface | None |
| NATIVE_OPERATION | src/cli/candidate_host.h | file-surface | None |
| NATIVE_OPERATION | src/cli/candidate_host_cli.c | file-surface | None |
| NATIVE_OPERATION | src/cli/candidate_host_config.c | file-surface | None |
| NATIVE_OPERATION | src/cli/candidate_host_runtime.c | file-surface | None |
| NATIVE_OPERATION | src/cli/candidate_host_transport.c | file-surface | None |
| NATIVE_OPERATION | src/cli/capsule.c | file-surface | None |
| NATIVE_OPERATION | src/cli/completion.c | file-surface | None |
| NATIVE_OPERATION | src/cli/context.c | file-surface | None |
| NATIVE_OPERATION | src/cli/context_tokenizer.c | file-surface | None |
| NATIVE_OPERATION | src/cli/context_tokenizer.h | file-surface | None |
| NATIVE_OPERATION | src/cli/daemon.c | file-surface | None |
| NATIVE_OPERATION | src/cli/daemon_worker.c | file-surface | None |
| NATIVE_OPERATION | src/cli/daemon_worker.h | file-surface | None |
| NATIVE_OPERATION | src/cli/discovery.c | file-surface | None |
| NATIVE_OPERATION | src/cli/doctor.c | file-surface | None |
| NATIVE_OPERATION | src/cli/document.c | file-surface | None |
| NATIVE_OPERATION | src/cli/error.c | file-surface | None |
| NATIVE_OPERATION | src/cli/error.h | file-surface | None |
| NATIVE_OPERATION | src/cli/events.c | file-surface | None |
| NATIVE_OPERATION | src/cli/execution.c | file-surface | None |
| NATIVE_OPERATION | src/cli/internal.h | file-surface | None |
| NATIVE_OPERATION | src/cli/io.c | file-surface | None |
| NATIVE_OPERATION | src/cli/journal.c | file-surface | None |
| NATIVE_OPERATION | src/cli/json.c | file-surface | None |
| NATIVE_OPERATION | src/cli/lineage.c | file-surface | None |
| NATIVE_OPERATION | src/cli/main.c | file-surface | None |
| NATIVE_OPERATION | src/cli/output.c | file-surface | None |
| NATIVE_OPERATION | src/cli/output.h | file-surface | None |
| NATIVE_OPERATION | src/cli/projection.c | file-surface | None |
| NATIVE_OPERATION | src/cli/proof.c | file-surface | None |
| NATIVE_OPERATION | src/cli/reentry.c | file-surface | None |
| NATIVE_OPERATION | src/cli/research.c | file-surface | None |
| NATIVE_OPERATION | src/cli/research_bundle.c | file-surface | None |
| NATIVE_OPERATION | src/cli/role.c | file-surface | None |
| NATIVE_OPERATION | src/cli/runtime.c | file-surface | None |
| NATIVE_OPERATION | src/cli/runtime_profile.c | file-surface | None |
| NATIVE_OPERATION | src/cli/work.c | file-surface | None |
| NATIVE_OPERATION | src/cli/work.h | file-surface | None |
| NATIVE_OPERATION | src/cli/workflow.c | file-surface | None |
| NATIVE_OPERATION | src/cli/workflow_template.c | file-surface | None |
| NATIVE_OPERATION | src/common/allocator.c | file-surface | None |
| NATIVE_OPERATION | src/common/arena.c | file-surface | None |
| NATIVE_OPERATION | src/common/diagnostic.c | file-surface | None |
| NATIVE_OPERATION | src/common/error.c | file-surface | None |
| NATIVE_OPERATION | src/common/json.c | file-surface | None |
| NATIVE_OPERATION | src/common/json.h | file-surface | None |
| NATIVE_OPERATION | src/common/record.c | file-surface | None |
| NATIVE_OPERATION | src/common/record_internal.h | file-surface | None |
| NATIVE_OPERATION | src/common/span.c | file-surface | None |
| NATIVE_OPERATION | src/common/system_error.c | file-surface | None |
| NATIVE_OPERATION | src/common/types.c | file-surface | None |
| NATIVE_OPERATION | src/common/version.c | file-surface | None |
| NATIVE_OPERATION | src/completion/deliverable.c | file-surface | None |
| NATIVE_OPERATION | src/completion/evaluator.c | file-surface | None |
| NATIVE_OPERATION | src/completion/internal.h | file-surface | None |
| NATIVE_OPERATION | src/completion/model.c | file-surface | None |
| NATIVE_OPERATION | src/completion/predicate_roles.c | file-surface | None |
| NATIVE_OPERATION | src/completion/predicate_v1.c | file-surface | None |
| NATIVE_OPERATION | src/completion/recovery.c | file-surface | None |
| NATIVE_OPERATION | src/completion/renderer_v1.c | file-surface | None |
| NATIVE_OPERATION | src/completion/report.c | file-surface | None |
| NATIVE_OPERATION | src/completion/store.c | file-surface | None |
| NATIVE_OPERATION | src/core/authorization.c | file-surface | None |
| NATIVE_OPERATION | src/core/capsule.c | file-surface | None |
| NATIVE_OPERATION | src/core/internal.h | file-surface | None |
| NATIVE_OPERATION | src/core/loop_controller.c | file-surface | None |
| NATIVE_OPERATION | src/core/memory.c | file-surface | None |
| NATIVE_OPERATION | src/core/stage_graph.c | file-surface | None |
| NATIVE_OPERATION | src/core/stage_run.c | file-surface | None |
| NATIVE_OPERATION | src/core/work_run.c | file-surface | None |
| NATIVE_OPERATION | src/cost/budget.c | file-surface | None |
| NATIVE_OPERATION | src/cost/cache.c | file-surface | None |
| NATIVE_OPERATION | src/cost/import.c | file-surface | None |
| NATIVE_OPERATION | src/cost/inbox.c | file-surface | None |
| NATIVE_OPERATION | src/cost/internal.h | file-surface | None |
| NATIVE_OPERATION | src/cost/ledger.c | file-surface | None |
| NATIVE_OPERATION | src/cost/usage.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/admission.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/admission_internal.h | file-surface | None |
| NATIVE_OPERATION | src/daemon/admission_model.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/admission_storage.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/admission_work.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/cgroup_exec.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/cgroup_exec_internal.h | file-surface | None |
| NATIVE_OPERATION | src/daemon/cgroup_internal.h | file-surface | None |
| NATIVE_OPERATION | src/daemon/event_reader.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/event_sse.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/events.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/events_admission.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/events_internal.h | file-surface | None |
| NATIVE_OPERATION | src/daemon/internal.h | file-surface | None |
| NATIVE_OPERATION | src/daemon/queue.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/recovery.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/resource.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/resource_io.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/scheduler.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/storage.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/supervisor.c | file-surface | None |
| NATIVE_OPERATION | src/daemon/worker.c | file-surface | None |
| NATIVE_OPERATION | src/discovery/internal.h | file-surface | None |
| NATIVE_OPERATION | src/discovery/model.c | file-surface | None |
| NATIVE_OPERATION | src/discovery/report.c | file-surface | None |
| NATIVE_OPERATION | src/discovery/snapshot.c | file-surface | None |
| NATIVE_OPERATION | src/document/internal.h | file-surface | None |
| NATIVE_OPERATION | src/document/markdown.c | file-surface | None |
| NATIVE_OPERATION | src/document/record.c | file-surface | None |
| NATIVE_OPERATION | src/document/record_read.c | file-surface | None |
| NATIVE_OPERATION | src/document/registry.c | file-surface | None |
| NATIVE_OPERATION | src/document/schema.c | file-surface | None |
| NATIVE_OPERATION | src/document/storage.c | file-surface | None |
| NATIVE_OPERATION | src/evidence/cas.c | file-surface | None |
| NATIVE_OPERATION | src/evidence/digest.c | file-surface | None |
| NATIVE_OPERATION | src/evidence/fs.c | file-surface | None |
| NATIVE_OPERATION | src/evidence/internal.h | file-surface | None |
| NATIVE_OPERATION | src/evidence/read.c | file-surface | None |
| NATIVE_OPERATION | src/evidence/receipt.c | file-surface | None |
| NATIVE_OPERATION | src/execution/bundle.c | file-surface | None |
| NATIVE_OPERATION | src/execution/change.c | file-surface | None |
| NATIVE_OPERATION | src/execution/command.c | file-surface | None |
| NATIVE_OPERATION | src/execution/internal.h | file-surface | None |
| NATIVE_OPERATION | src/execution/inventory_ref.c | file-surface | None |
| NATIVE_OPERATION | src/execution/logs.c | file-surface | None |
| NATIVE_OPERATION | src/execution/model.c | file-surface | None |
| NATIVE_OPERATION | src/execution/proof_format.c | file-surface | None |
| NATIVE_OPERATION | src/execution/proof_internal.h | file-surface | None |
| NATIVE_OPERATION | src/execution/proof_pack.c | file-surface | None |
| NATIVE_OPERATION | src/execution/proof_store.c | file-surface | None |
| NATIVE_OPERATION | src/execution/report.c | file-surface | None |
| NATIVE_OPERATION | src/execution/runner.c | file-surface | None |
| NATIVE_OPERATION | src/execution/store.c | file-surface | None |
| PYTHON_DECLARATION | src/golem/__init__.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/adapters/__init__.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/adapters/base.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/adapters/local.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/cli.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/core/__init__.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/core/models.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/core/optimization.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/core/serialization.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/evidence/__init__.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/evidence/store.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/policies/__init__.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/policies/autonomy.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/runtime/__init__.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/runtime/lease.py | file-surface | None |
| PYTHON_DECLARATION | src/golem/runtime/loop.py | file-surface | None |
| NATIVE_OPERATION | src/intent/fragment.c | file-surface | None |
| NATIVE_OPERATION | src/intent/fragment.h | file-surface | None |
| NATIVE_OPERATION | src/intent/inventory.c | file-surface | None |
| NATIVE_OPERATION | src/intent/inventory.h | file-surface | None |
| NATIVE_OPERATION | src/intent/journal.c | file-surface | None |
| NATIVE_OPERATION | src/intent/journal.h | file-surface | None |
| NATIVE_OPERATION | src/intent/object.c | file-surface | None |
| NATIVE_OPERATION | src/intent/object.h | file-surface | None |
| NATIVE_OPERATION | src/intent/object_graph.c | file-surface | None |
| NATIVE_OPERATION | src/intent/object_graph.h | file-surface | None |
| NATIVE_OPERATION | src/intent/object_inventory.c | file-surface | None |
| NATIVE_OPERATION | src/intent/object_inventory.h | file-surface | None |
| NATIVE_OPERATION | src/intent/quota.c | file-surface | None |
| NATIVE_OPERATION | src/intent/quota.h | file-surface | None |
| NATIVE_OPERATION | src/intent/schema.c | file-surface | None |
| NATIVE_OPERATION | src/intent/schema.h | file-surface | None |
| NATIVE_OPERATION | src/inventory/capture.c | file-surface | None |
| NATIVE_OPERATION | src/inventory/compare.c | file-surface | None |
| NATIVE_OPERATION | src/inventory/git_record.c | file-surface | None |
| NATIVE_OPERATION | src/inventory/git_record.h | file-surface | None |
| NATIVE_OPERATION | src/inventory/internal.h | file-surface | None |
| NATIVE_OPERATION | src/inventory/matcher.c | file-surface | None |
| NATIVE_OPERATION | src/inventory/model.c | file-surface | None |
| NATIVE_OPERATION | src/journal/capsule_codec.c | file-surface | None |
| NATIVE_OPERATION | src/journal/codec.c | file-surface | None |
| NATIVE_OPERATION | src/journal/event.c | file-surface | None |
| NATIVE_OPERATION | src/journal/file.c | file-surface | None |
| NATIVE_OPERATION | src/journal/inspect.c | file-surface | None |
| NATIVE_OPERATION | src/journal/internal.h | file-surface | None |
| NATIVE_OPERATION | src/journal/replay.c | file-surface | None |
| NATIVE_OPERATION | src/lineage/codec.c | file-surface | None |
| NATIVE_OPERATION | src/lineage/internal.h | file-surface | None |
| NATIVE_OPERATION | src/lineage/model.c | file-surface | None |
| NATIVE_OPERATION | src/lineage/query.c | file-surface | None |
| NATIVE_OPERATION | src/lineage/store.c | file-surface | None |
| NATIVE_OPERATION | src/optimization/execution.c | file-surface | None |
| NATIVE_OPERATION | src/optimization/internal.h | file-surface | None |
| NATIVE_OPERATION | src/optimization/selection.c | file-surface | None |
| NATIVE_OPERATION | src/policy/approval_internal.h | file-surface | None |
| NATIVE_OPERATION | src/policy/approval_model.c | file-surface | None |
| NATIVE_OPERATION | src/policy/approval_scope.c | file-surface | None |
| NATIVE_OPERATION | src/policy/approval_store.c | file-surface | None |
| NATIVE_OPERATION | src/policy/artifact.c | file-surface | None |
| NATIVE_OPERATION | src/policy/autonomy.c | file-surface | None |
| NATIVE_OPERATION | src/policy/fallback.c | file-surface | None |
| NATIVE_OPERATION | src/reentry/internal.h | file-surface | None |
| NATIVE_OPERATION | src/reentry/model.c | file-surface | None |
| NATIVE_OPERATION | src/reentry/store.c | file-surface | None |
| NATIVE_OPERATION | src/reentry/workflow.c | file-surface | None |
| NATIVE_OPERATION | src/replay/apply.c | file-surface | None |
| NATIVE_OPERATION | src/replay/engine.c | file-surface | None |
| NATIVE_OPERATION | src/replay/internal.h | file-surface | None |
| NATIVE_OPERATION | src/research/bundle.c | file-surface | None |
| NATIVE_OPERATION | src/research/bundle_format.c | file-surface | None |
| NATIVE_OPERATION | src/research/bundle_internal.h | file-surface | None |
| NATIVE_OPERATION | src/research/cohort.c | file-surface | None |
| NATIVE_OPERATION | src/research/compare.c | file-surface | None |
| NATIVE_OPERATION | src/research/internal.h | file-surface | None |
| NATIVE_OPERATION | src/research/metrics.c | file-surface | None |
| NATIVE_OPERATION | src/research/metrics_report.c | file-surface | None |
| NATIVE_OPERATION | src/research/model.c | file-surface | None |
| NATIVE_OPERATION | src/research/observability.c | file-surface | None |
| NATIVE_OPERATION | src/research/outcome.c | file-surface | None |
| NATIVE_OPERATION | src/research/report.c | file-surface | None |
| NATIVE_OPERATION | src/research/runtime_observability.c | file-surface | None |
| NATIVE_OPERATION | src/research/store.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/lease.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/loop.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/prepared_cache.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/profile_binding.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/profile_cache.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/profile_codec.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/profile_internal.h | file-surface | None |
| NATIVE_OPERATION | src/runtime/profile_link.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/profile_model.c | file-surface | None |
| NATIVE_OPERATION | src/runtime/profile_store.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/context_internal.h | file-surface | None |
| NATIVE_OPERATION | src/workflow/context_model.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/context_projection.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/context_selection.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/graph.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/internal.h | file-surface | None |
| NATIVE_OPERATION | src/workflow/model.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/query.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/role_contract.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/role_internal.h | file-surface | None |
| NATIVE_OPERATION | src/workflow/role_store.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/template.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/template_builtin.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/template_guard.c | file-surface | None |
| NATIVE_OPERATION | src/workflow/template_internal.h | file-surface | None |
| NATIVE_OPERATION | src/workspace/git.c | file-surface | None |
| NATIVE_OPERATION | src/workspace/internal.h | file-surface | None |
| NATIVE_OPERATION | src/workspace/lifecycle.c | file-surface | None |
| NATIVE_OPERATION | src/workspace/model.c | file-surface | None |
| NATIVE_OPERATION | src/workspace/store.c | file-surface | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | file-surface | None |
| PYTHON_DECLARATION | tools/agent_io.py | file-surface | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | file-surface | None |
| PYTHON_DECLARATION | tools/benchmark_intent_journal.py | file-surface | None |
| PYTHON_DECLARATION | tools/benchmark_orchestration.py | file-surface | None |
| PYTHON_DECLARATION | tools/benchmark_runtime.py | file-surface | None |
| PYTHON_DECLARATION | tools/billing_evidence.py | file-surface | None |
| PYTHON_DECLARATION | tools/check_guard_mutations.py | file-surface | None |
| PYTHON_DECLARATION | tools/classify_failures.py | file-surface | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | file-surface | None |
| PYTHON_DECLARATION | tools/context_resume.py | file-surface | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | file-surface | None |
| NATIVE_OPERATION | tools/event_bridge.c | file-surface | None |
| NATIVE_OPERATION | tools/event_bridge_limits.h | file-surface | None |
| PYTHON_DECLARATION | tools/evidence_adapters.py | file-surface | None |
| PYTHON_DECLARATION | tools/evidence_contract.py | file-surface | None |
| PYTHON_DECLARATION | tools/evidence_export.py | file-surface | None |
| PYTHON_DECLARATION | tools/execution_record.py | file-surface | None |
| PYTHON_DECLARATION | tools/github_checks.py | file-surface | None |
| PYTHON_DECLARATION | tools/github_context.py | file-surface | None |
| PYTHON_DECLARATION | tools/github_policy.py | file-surface | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | file-surface | None |
| PYTHON_DECLARATION | tools/install_conan_cli.py | file-surface | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | file-surface | None |
| NATIVE_OPERATION | tools/integration_approval_host.c | file-surface | None |
| PYTHON_DECLARATION | tools/integration_backend.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_codex_plugin.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_config.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_contract.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_gateway_auth.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_gateway_contract.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_hooks.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_install.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_launch.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_mcp.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_mcpb.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_mcpb_entry.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_mutation_mcp.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_mutations.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_recovery.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_registry.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_service.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_transfer.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_update.py | file-surface | None |
| PYTHON_DECLARATION | tools/intent_authority.py | file-surface | None |
| NATIVE_OPERATION | tools/intent_authority_host.c | file-surface | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | file-surface | None |
| PYTHON_DECLARATION | tools/isolation_canary.py | file-surface | None |
| PYTHON_DECLARATION | tools/judgment_record.py | file-surface | None |
| PYTHON_DECLARATION | tools/native_record.py | file-surface | None |
| PYTHON_DECLARATION | tools/provider_costs.py | file-surface | None |
| PYTHON_DECLARATION | tools/provider_usage.py | file-surface | None |
| PYTHON_DECLARATION | tools/remote_status.py | file-surface | None |
| PYTHON_DECLARATION | tools/retire_legacy_cli.py | file-surface | None |
| PYTHON_DECLARATION | tools/revision_status.py | file-surface | None |
| PYTHON_DECLARATION | tools/status_collector.py | file-surface | None |
| PYTHON_DECLARATION | tools/syscall_record.py | file-surface | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_agent.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_alpha.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_environment.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_gateway_schema.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_hook_schema.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_install_schema.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_integration_schema.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_isolation.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_mutation_schema.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_orchestration.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_preflight.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_resource.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_runtime.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_runtime_legacy.py | file-surface | None |
| PYTHON_DECLARATION | tools/verify_update_schema.py | file-surface | None |
| NATIVE_OPERATION | bindings/native/bridge.c | command-path | GOLEM_BINDING_DESCRIBE_ADAPTER |
| NATIVE_OPERATION | bindings/native/bridge.c | command-path | GOLEM_BINDING_REPLAY |
| NATIVE_OPERATION | bindings/native/bridge.c | command-path | GOLEM_BINDING_VALIDATE |
| PYTHON_DECLARATION | bindings/python/src/golem_runtime/__init__.py | Engine | None |
| PYTHON_DECLARATION | bindings/python/src/golem_runtime/__init__.py | Engine.describe_adapter | None |
| PYTHON_DECLARATION | bindings/python/src/golem_runtime/__init__.py | Engine.replay | None |
| PYTHON_DECLARATION | bindings/python/src/golem_runtime/__init__.py | Engine.validate | None |
| PYTHON_DECLARATION | bindings/python/src/golem_runtime/__init__.py | GolemError | None |
| PYTHON_DECLARATION | bindings/python/src/golem_runtime/__init__.py | ReplayResult | None |
| PYTHON_DECLARATION | bindings/python/src/golem_runtime/__init__.py | ValidationResult | None |
| NATIVE_OPERATION | bindings/typescript/index.d.ts | command-path | Engine.describeAdapter |
| NATIVE_OPERATION | bindings/typescript/index.d.ts | command-path | Engine.replay |
| NATIVE_OPERATION | bindings/typescript/index.d.ts | command-path | Engine.validate |
| NATIVE_OPERATION | bindings/typescript/index.mjs | command-path | Engine.describeAdapter |
| NATIVE_OPERATION | bindings/typescript/index.mjs | command-path | Engine.replay |
| NATIVE_OPERATION | bindings/typescript/index.mjs | command-path | Engine.validate |
| NATIVE_OPERATION | bindings/typescript/native/addon.c | command-path | call.1.validate |
| NATIVE_OPERATION | bindings/typescript/native/addon.c | command-path | call.2.replay |
| NATIVE_OPERATION | bindings/typescript/native/addon.c | command-path | call.3.describe_adapter |
| PYTHON_DECLARATION | conanfile.py | GolemConan | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.build | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.configure | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.export | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.export_sources | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.generate | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.layout | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.package | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.package_info | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.requirements | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.set_version | None |
| PYTHON_DECLARATION | conanfile.py | GolemConan.validate | None |
| CLI_ROUTE | plugins/golem/scripts/launcher.py | argparse:operation | configure |
| CLI_ROUTE | plugins/golem/scripts/launcher.py | argparse:operation | serve |
| CLI_ROUTE | plugins/golem/scripts/launcher.py | argparse:operation | status |
| NATIVE_OPERATION | plugins/golem/scripts/launcher.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | configure |
| NATIVE_OPERATION | plugins/golem/scripts/launcher.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | status |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | SetupError | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | canonical | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | configure | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | decode | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | digest | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | directory | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | load | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | locked | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | main | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | pairs | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | read_private | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | require | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | serve | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | status | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | sync_directory | None |
| PYTHON_DECLARATION | plugins/golem/scripts/launcher.py | validate_launcher | None |
| PYTHON_DECLARATION | source_policy.py | export_sources | None |
| PYTHON_DECLARATION | source_policy.py | selected | None |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ 2 ] | convert |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ 2 ] | describe |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ 2 ] | noop |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ 2 ] | probe |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ 3 ] | msgpack |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ 3 ] | probe |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ 3 ] | run |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ 4 ] | msgpack |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ argc - 1 ] | msgpack |
| CLI_ROUTE | src/cli/adapter.c | argv:argv [ argc - 2 ] | --format |
| CLI_ROUTE | src/cli/adapter.c | command-path | adapter noop probe |
| CLI_ROUTE | src/cli/adapter.c | command-path | adapter noop run |
| CLI_ROUTE | src/cli/adapter_descriptor.c | argv:argv [ 2 ] | probe |
| CLI_ROUTE | src/cli/adapter_descriptor.c | argv:argv [ 3 ] | --current |
| CLI_ROUTE | src/cli/adapter_descriptor.c | argv:argv [ 3 ] | noop |
| CLI_ROUTE | src/cli/adapter_descriptor.c | argv:argv [ 7 ] | --allow-process |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 1 ] | agent |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 1 ] | work |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 2 ] | binding |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 2 ] | call |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 2 ] | history |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 2 ] | record |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 2 ] | resume |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 3 ] | attach |
| CLI_ROUTE | src/cli/agent_session.c | argv:argv [ 3 ] | inspect |
| CLI_ROUTE | src/cli/agent_session.c | command-path | agent binding attach |
| CLI_ROUTE | src/cli/agent_session.c | command-path | agent binding inspect |
| CLI_ROUTE | src/cli/agent_session.c | command-path | work history |
| CLI_ROUTE | src/cli/agent_session.c | command-path | work record |
| CLI_ROUTE | src/cli/approval.c | argv:argv [ 2 ] | call |
| CLI_ROUTE | src/cli/approval.c | argv:argv [ 2 ] | describe |
| CLI_ROUTE | src/cli/candidate.c | argv:argv [ 2 ] | call |
| CLI_ROUTE | src/cli/candidate.c | argv:argv [ 2 ] | diff |
| CLI_ROUTE | src/cli/candidate.c | argv:argv [ 2 ] | gates |
| CLI_ROUTE | src/cli/candidate.c | argv:argv [ 2 ] | host-validate |
| CLI_ROUTE | src/cli/candidate.c | argv:argv [ 2 ] | request-digest |
| CLI_ROUTE | src/cli/candidate.c | argv:argv [ 2 ] | serve |
| CLI_ROUTE | src/cli/candidate.c | argv:argv [ 2 ] | status |
| CLI_ROUTE | src/cli/candidate.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/candidate_host_cli.c | argv:argv [ 5 ] | --approve-config |
| CLI_ROUTE | src/cli/candidate_host_cli.c | argv:argv [ i ] | --approve-request |
| CLI_ROUTE | src/cli/candidate_host_cli.c | argv:argv [ i ] | --attest-termination |
| CLI_ROUTE | src/cli/completion.c | argv:argv [ 2 ] | call |
| CLI_ROUTE | src/cli/completion.c | argv:argv [ 2 ] | check |
| CLI_ROUTE | src/cli/completion.c | argv:argv [ 2 ] | report |
| CLI_ROUTE | src/cli/completion.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/context.c | argv:argv [ 2 ] | candidate |
| CLI_ROUTE | src/cli/context.c | argv:argv [ 2 ] | markdown |
| CLI_ROUTE | src/cli/context.c | argv:argv [ 2 ] | publish |
| CLI_ROUTE | src/cli/context.c | argv:argv [ 2 ] | read |
| CLI_ROUTE | src/cli/context.c | argv:argv [ 2 ] | render |
| CLI_ROUTE | src/cli/context.c | argv:argv [ argc - 2 ] | --token-count |
| CLI_ROUTE | src/cli/daemon.c | argv:argv [ 2 ] | init |
| CLI_ROUTE | src/cli/daemon.c | argv:argv [ 2 ] | recover |
| CLI_ROUTE | src/cli/daemon.c | argv:argv [ 2 ] | run |
| CLI_ROUTE | src/cli/daemon.c | argv:argv [ 2 ] | status |
| CLI_ROUTE | src/cli/daemon.c | argv:argv [ 2 ] | submit |
| CLI_ROUTE | src/cli/daemon.c | argv:argv [ 4 ] | --worker |
| CLI_ROUTE | src/cli/daemon.c | argv:argv [ 6 ] | --drain |
| CLI_ROUTE | src/cli/daemon.c | argv:argv [ 6 ] | --once |
| CLI_ROUTE | src/cli/discovery.c | argv:argv [ 2 ] | report |
| CLI_ROUTE | src/cli/discovery.c | argv:argv [ 2 ] | snapshot |
| CLI_ROUTE | src/cli/discovery.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/doctor.c | argv:argv [ 2 ] | admission |
| CLI_ROUTE | src/cli/doctor.c | argv:argv [ 2 ] | clock |
| CLI_ROUTE | src/cli/doctor.c | argv:argv [ 2 ] | work |
| CLI_ROUTE | src/cli/document.c | argv:argv [ 1 ] | document |
| CLI_ROUTE | src/cli/document.c | argv:argv [ 1 ] | work |
| CLI_ROUTE | src/cli/document.c | argv:argv [ 2 ] | inspect |
| CLI_ROUTE | src/cli/document.c | argv:argv [ 2 ] | project |
| CLI_ROUTE | src/cli/document.c | argv:argv [ 2 ] | start |
| CLI_ROUTE | src/cli/document.c | argv:argv [ 2 ] | submit |
| CLI_ROUTE | src/cli/document.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/events.c | argv:argv [ 3 ] | --jsonl |
| CLI_ROUTE | src/cli/events.c | argv:argv [ 3 ] | --otlp |
| CLI_ROUTE | src/cli/events.c | argv:argv [ 3 ] | --prov |
| CLI_ROUTE | src/cli/events.c | argv:argv [ 4 ] | --after |
| CLI_ROUTE | src/cli/execution.c | argv:argv [ 2 ] | bundle |
| CLI_ROUTE | src/cli/execution.c | argv:argv [ 2 ] | call |
| CLI_ROUTE | src/cli/execution.c | argv:argv [ 2 ] | render |
| CLI_ROUTE | src/cli/execution.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/execution.c | argv:argv [ 3 ] | inspect |
| CLI_ROUTE | src/cli/execution.c | argv:argv [ 3 ] | verify |
| CLI_ROUTE | src/cli/execution.c | argv:argv [ i ] | --approve-contract |
| CLI_ROUTE | src/cli/execution.c | argv:argv [ i ] | --approve-shell-contract |
| CLI_ROUTE | src/cli/execution.c | command-path | execution bundle inspect |
| CLI_ROUTE | src/cli/execution.c | command-path | execution bundle verify |
| CLI_ROUTE | src/cli/journal.c | argv:argv [ 2 ] | inspect |
| CLI_ROUTE | src/cli/journal.c | argv:argv [ 2 ] | salvage |
| CLI_ROUTE | src/cli/journal.c | argv:argv [ 2 ] | verify-salvage |
| CLI_ROUTE | src/cli/journal.c | argv:argv [ 4 ] | --expect-chain |
| CLI_ROUTE | src/cli/journal.c | argv:argv [ 4 ] | --expect-receipt |
| CLI_ROUTE | src/cli/journal.c | argv:argv [ 5 ] | --expect-source |
| CLI_ROUTE | src/cli/journal.c | argv:argv [ 7 ] | --accept-truncated-tail |
| CLI_ROUTE | src/cli/lineage.c | argv:argv [ 2 ] | trace |
| CLI_ROUTE | src/cli/lineage.c | argv:argv [ 2 ] | verify |
| CLI_ROUTE | src/cli/lineage.c | argv:argv [ 6 ] | --direct |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | --help |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | --version |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | adapter |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | agent |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | approval |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | candidate |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | capsule |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | completion |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | context |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | cost |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | daemon |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | discovery |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | doctor |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | document |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | events |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | evidence |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | execution |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | init |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | journal |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | lineage |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | output |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | profile |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | proof |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | reentry |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | replay |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | research |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | role |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | run |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | session |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | work |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 1 ] | workflow |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 2 ] | hash |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 2 ] | history |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 2 ] | put |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 2 ] | read |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 2 ] | record |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 2 ] | verify |
| CLI_ROUTE | src/cli/main.c | argv:argv [ 2 ] | verify-receipt |
| CLI_ROUTE | src/cli/output.c | argv:argv [ 1 ] | context |
| CLI_ROUTE | src/cli/output.c | argv:argv [ 2 ] | observability |
| CLI_ROUTE | src/cli/output.c | argv:argv [ 2 ] | read |
| CLI_ROUTE | src/cli/output.c | argv:argv [ 2 ] | report |
| CLI_ROUTE | src/cli/output.c | argv:argv [ count ] | --output-mode |
| CLI_ROUTE | src/cli/output.c | argv:argv [ count ] | --output-store |
| CLI_ROUTE | src/cli/proof.c | argv:argv [ 2 ] | integrity |
| CLI_ROUTE | src/cli/proof.c | argv:argv [ 2 ] | publish |
| CLI_ROUTE | src/cli/proof.c | argv:argv [ 2 ] | render |
| CLI_ROUTE | src/cli/proof.c | argv:argv [ 2 ] | verify |
| CLI_ROUTE | src/cli/proof.c | argv:argv [ 2 ] | verify-dir |
| CLI_ROUTE | src/cli/reentry.c | argv:argv [ 2 ] | call |
| CLI_ROUTE | src/cli/reentry.c | argv:argv [ 2 ] | report |
| CLI_ROUTE | src/cli/reentry.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | attempt |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | bundle-verify |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | call |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | case |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | cohort |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | compare |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | export |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | inspect |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | metrics |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | observability |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | outcome |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | report |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | status |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 3 ] | adjudicate |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 3 ] | create |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 3 ] | enroll |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 3 ] | observe |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 3 ] | plan |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 3 ] | record |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 4 ] | --case |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 6 ] | --format |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 7 ] | otlp |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 7 ] | prov |
| CLI_ROUTE | src/cli/research.c | argv:argv [ 8 ] | --redact |
| CLI_ROUTE | src/cli/research.c | argv:argv [ i + 1 ] | json |
| CLI_ROUTE | src/cli/research.c | argv:argv [ i + 1 ] | markdown |
| CLI_ROUTE | src/cli/research.c | argv:argv [ i ] | --case |
| CLI_ROUTE | src/cli/research.c | argv:argv [ i ] | --format |
| CLI_ROUTE | src/cli/research.c | command-path | research attempt plan |
| CLI_ROUTE | src/cli/research.c | command-path | research attempt record |
| CLI_ROUTE | src/cli/research.c | command-path | research case create |
| CLI_ROUTE | src/cli/research.c | command-path | research cohort create |
| CLI_ROUTE | src/cli/research.c | command-path | research cohort observe |
| CLI_ROUTE | src/cli/research.c | command-path | research outcome adjudicate |
| CLI_ROUTE | src/cli/research.c | command-path | research outcome enroll |
| CLI_ROUTE | src/cli/research_bundle.c | argv:argv [ 2 ] | bundle-verify |
| CLI_ROUTE | src/cli/research_bundle.c | argv:argv [ 2 ] | export |
| CLI_ROUTE | src/cli/research_bundle.c | argv:argv [ 4 ] | --case |
| CLI_ROUTE | src/cli/research_bundle.c | argv:argv [ 4 ] | --expect-manifest |
| CLI_ROUTE | src/cli/research_bundle.c | argv:argv [ 6 ] | --output |
| CLI_ROUTE | src/cli/research_bundle.c | argv:argv [ 8 ] | --redact |
| CLI_ROUTE | src/cli/role.c | argv:argv [ 2 ] | call |
| CLI_ROUTE | src/cli/role.c | argv:argv [ 2 ] | template |
| CLI_ROUTE | src/cli/role.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/role.c | argv:argv [ 5 ] | --approve-contract |
| CLI_ROUTE | src/cli/runtime_profile.c | argv:argv [ 2 ] | current |
| CLI_ROUTE | src/cli/runtime_profile.c | argv:argv [ 2 ] | link |
| CLI_ROUTE | src/cli/runtime_profile.c | argv:argv [ 2 ] | register |
| CLI_ROUTE | src/cli/runtime_profile.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 1 ] | capsule |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 1 ] | cost |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 1 ] | init |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 1 ] | replay |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 1 ] | run |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 2 ] | --noop |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 2 ] | report |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 2 ] | validate |
| CLI_ROUTE | src/cli/work.c | argv:argv [ 4 ] | --output |
| CLI_ROUTE | src/cli/work.c | argv:argv [ i ] | --expect-chain |
| CLI_ROUTE | src/cli/work.c | argv:argv [ i ] | --require-terminal |
| CLI_ROUTE | src/cli/work.c | command-path | capsule validate |
| CLI_ROUTE | src/cli/work.c | command-path | cost report |
| CLI_ROUTE | src/cli/work.c | command-path | run --noop |
| CLI_ROUTE | src/cli/workflow.c | argv:argv [ 2 ] | inputs |
| CLI_ROUTE | src/cli/workflow.c | argv:argv [ 2 ] | next |
| CLI_ROUTE | src/cli/workflow.c | argv:argv [ 2 ] | select |
| CLI_ROUTE | src/cli/workflow.c | argv:argv [ 2 ] | template |
| CLI_ROUTE | src/cli/workflow.c | argv:argv [ 2 ] | trace |
| CLI_ROUTE | src/cli/workflow_template.c | argv:argv [ 3 ] | instantiate |
| CLI_ROUTE | src/cli/workflow_template.c | argv:argv [ 3 ] | list |
| CLI_ROUTE | src/cli/workflow_template.c | argv:argv [ 3 ] | show |
| CLI_ROUTE | src/cli/workflow_template.c | argv:argv [ 3 ] | validate |
| PYTHON_DECLARATION | src/golem/adapters/base.py | AgentAdapter | None |
| PYTHON_DECLARATION | src/golem/adapters/base.py | AgentAdapter.run_stage | None |
| PYTHON_DECLARATION | src/golem/adapters/base.py | StageResult | None |
| PYTHON_DECLARATION | src/golem/adapters/local.py | LocalNoopAdapter | None |
| PYTHON_DECLARATION | src/golem/adapters/local.py | LocalNoopAdapter.run_stage | None |
| CLI_ROUTE | src/golem/cli.py | argparse:command | smoke-run |
| NATIVE_OPERATION | src/golem/cli.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | smoke-run |
| PYTHON_DECLARATION | src/golem/cli.py | default_capsule | None |
| PYTHON_DECLARATION | src/golem/cli.py | main | None |
| PYTHON_DECLARATION | src/golem/core/models.py | AcceptanceCriterion | None |
| PYTHON_DECLARATION | src/golem/core/models.py | AutonomyMode | None |
| PYTHON_DECLARATION | src/golem/core/models.py | ContextPackage | None |
| PYTHON_DECLARATION | src/golem/core/models.py | Decision | None |
| PYTHON_DECLARATION | src/golem/core/models.py | EvidenceRef | None |
| PYTHON_DECLARATION | src/golem/core/models.py | FailureType | None |
| PYTHON_DECLARATION | src/golem/core/models.py | StageGraph | None |
| PYTHON_DECLARATION | src/golem/core/models.py | StageGraph.next_after | None |
| PYTHON_DECLARATION | src/golem/core/models.py | StageGraph.reentry_for | None |
| PYTHON_DECLARATION | src/golem/core/models.py | StageName | None |
| PYTHON_DECLARATION | src/golem/core/models.py | StageRun | None |
| PYTHON_DECLARATION | src/golem/core/models.py | StageStatus | None |
| PYTHON_DECLARATION | src/golem/core/models.py | WorkCapsule | None |
| PYTHON_DECLARATION | src/golem/core/models.py | WorkCapsule.validate | None |
| PYTHON_DECLARATION | src/golem/core/models.py | WorkRun | None |
| PYTHON_DECLARATION | src/golem/core/models.py | WorkRun.latest_stage_run | None |
| PYTHON_DECLARATION | src/golem/core/optimization.py | BudgetPolicy | None |
| PYTHON_DECLARATION | src/golem/core/optimization.py | CostLedgerEntry | None |
| PYTHON_DECLARATION | src/golem/core/optimization.py | OptimizationAction | None |
| PYTHON_DECLARATION | src/golem/core/optimization.py | OptimizationAdvisor | None |
| PYTHON_DECLARATION | src/golem/core/optimization.py | OptimizationAdvisor.propose | None |
| PYTHON_DECLARATION | src/golem/core/optimization.py | OptimizationProposal | None |
| PYTHON_DECLARATION | src/golem/core/optimization.py | ProviderUsage | None |
| PYTHON_DECLARATION | src/golem/core/serialization.py | stable_json | None |
| PYTHON_DECLARATION | src/golem/evidence/store.py | EvidenceStore | None |
| PYTHON_DECLARATION | src/golem/evidence/store.py | EvidenceStore.put | None |
| PYTHON_DECLARATION | src/golem/evidence/store.py | EvidenceStore.verify | None |
| PYTHON_DECLARATION | src/golem/evidence/store.py | redact | None |
| PYTHON_DECLARATION | src/golem/evidence/store.py | sha256_text | None |
| PYTHON_DECLARATION | src/golem/evidence/store.py | validate_safe_payload | None |
| PYTHON_DECLARATION | src/golem/policies/autonomy.py | ActionRequest | None |
| PYTHON_DECLARATION | src/golem/policies/autonomy.py | evaluate_action | None |
| PYTHON_DECLARATION | src/golem/runtime/lease.py | Lease | None |
| PYTHON_DECLARATION | src/golem/runtime/lease.py | Lease.heartbeat | None |
| PYTHON_DECLARATION | src/golem/runtime/lease.py | Lease.is_stale | None |
| PYTHON_DECLARATION | src/golem/runtime/loop.py | LoopController | None |
| PYTHON_DECLARATION | src/golem/runtime/loop.py | LoopController.next_stage_index | None |
| PYTHON_DECLARATION | src/golem/runtime/loop.py | LoopController.run_once | None |
| CLI_ROUTE | tools/agent_entrypoint.py | argparse:command | apply |
| CLI_ROUTE | tools/agent_entrypoint.py | argparse:command | check |
| CLI_ROUTE | tools/agent_entrypoint.py | argparse:command | plan |
| NATIVE_OPERATION | tools/agent_entrypoint.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | apply |
| NATIVE_OPERATION | tools/agent_entrypoint.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | check |
| NATIVE_OPERATION | tools/agent_entrypoint.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | plan |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | EntryError | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | apply | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | atomic_write | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | check | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | encoded | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | git | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | locked | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | main | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | no_symlinks | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | plan | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | plan_identity | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | read_setup | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | regular_bytes | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | sha | None |
| PYTHON_DECLARATION | tools/agent_entrypoint.py | split_block | None |
| CLI_ROUTE | tools/agent_io.py | argparse:command | guide |
| CLI_ROUTE | tools/agent_io.py | argparse:command | judgment-facts |
| CLI_ROUTE | tools/agent_io.py | argparse:command | judgment-view |
| CLI_ROUTE | tools/agent_io.py | argparse:command | judgment-write |
| CLI_ROUTE | tools/agent_io.py | argparse:command | measure |
| CLI_ROUTE | tools/agent_io.py | argparse:command | observe |
| CLI_ROUTE | tools/agent_io.py | argparse:command | observe-history |
| CLI_ROUTE | tools/agent_io.py | argparse:command | procedure |
| CLI_ROUTE | tools/agent_io.py | argparse:command | procedure-view |
| CLI_ROUTE | tools/agent_io.py | argparse:command | raw |
| CLI_ROUTE | tools/agent_io.py | argparse:command | record-view |
| CLI_ROUTE | tools/agent_io.py | argparse:command | report |
| CLI_ROUTE | tools/agent_io.py | argparse:command | run |
| CLI_ROUTE | tools/agent_io.py | argparse:command | usage-total |
| CLI_ROUTE | tools/agent_io.py | argparse:command | view |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | guide |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | judgment-facts |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | judgment-view |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | measure |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | observe |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | observe-history |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | procedure |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | procedure-view |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | raw |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | record-view |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | run |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | usage-total |
| NATIVE_OPERATION | tools/agent_io.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | view |
| NATIVE_OPERATION | tools/agent_io.py | branch:Name(id=&#x27;mode&#x27;, ctx=Load()) | DELTA |
| NATIVE_OPERATION | tools/agent_io.py | branch:Subscript(value=Subscript(value=Name(id=&#x27;command&#x27;, ctx=Load()), slice=Constant(value=&#x27;usage&#x27;), ctx=Load()), slice=Constant(value=&#x27;provider&#x27;), ctx=Load()) | claude.code.v1 |
| NATIVE_OPERATION | tools/agent_io.py | branch:Subscript(value=Subscript(value=Name(id=&#x27;command&#x27;, ctx=Load()), slice=Constant(value=&#x27;usage&#x27;), ctx=Load()), slice=Constant(value=&#x27;provider&#x27;), ctx=Load()) | codex.exec.v1 |
| PYTHON_DECLARATION | tools/agent_io.py | ObservationError | None |
| PYTHON_DECLARATION | tools/agent_io.py | comparable | None |
| PYTHON_DECLARATION | tools/agent_io.py | consolidated_value | None |
| PYTHON_DECLARATION | tools/agent_io.py | encoded | None |
| PYTHON_DECLARATION | tools/agent_io.py | file_inventory | None |
| PYTHON_DECLARATION | tools/agent_io.py | fingerprint | None |
| PYTHON_DECLARATION | tools/agent_io.py | history_plan | None |
| PYTHON_DECLARATION | tools/agent_io.py | identity | None |
| PYTHON_DECLARATION | tools/agent_io.py | load_bundle | None |
| PYTHON_DECLARATION | tools/agent_io.py | main | None |
| PYTHON_DECLARATION | tools/agent_io.py | measure | None |
| PYTHON_DECLARATION | tools/agent_io.py | observe_plan | None |
| PYTHON_DECLARATION | tools/agent_io.py | observed_fields | None |
| PYTHON_DECLARATION | tools/agent_io.py | procedure_plan | None |
| PYTHON_DECLARATION | tools/agent_io.py | procedure_view | None |
| PYTHON_DECLARATION | tools/agent_io.py | producer | None |
| PYTHON_DECLARATION | tools/agent_io.py | read_json | None |
| PYTHON_DECLARATION | tools/agent_io.py | read_raw | None |
| PYTHON_DECLARATION | tools/agent_io.py | report | None |
| PYTHON_DECLARATION | tools/agent_io.py | run | None |
| PYTHON_DECLARATION | tools/agent_io.py | select_procedure | None |
| PYTHON_DECLARATION | tools/agent_io.py | validate_plan | None |
| PYTHON_DECLARATION | tools/agent_io.py | validate_work_record | None |
| PYTHON_DECLARATION | tools/agent_io.py | view | None |
| PYTHON_DECLARATION | tools/agent_io.py | work_record | None |
| CLI_ROUTE | tools/agent_lifecycle.py | argparse:command | inspect |
| CLI_ROUTE | tools/agent_lifecycle.py | argparse:command | run |
| CLI_ROUTE | tools/agent_lifecycle.py | argparse:command | validate |
| NATIVE_OPERATION | tools/agent_lifecycle.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | run |
| NATIVE_OPERATION | tools/agent_lifecycle.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | validate |
| NATIVE_OPERATION | tools/agent_lifecycle.py | branch:Call(func=Name(id=&#x27;set&#x27;, ctx=Load()), args=[Name(id=&#x27;command&#x27;, ctx=Load())]) | argv |
| NATIVE_OPERATION | tools/agent_lifecycle.py | branch:Call(func=Name(id=&#x27;set&#x27;, ctx=Load()), args=[Name(id=&#x27;command&#x27;, ctx=Load())]) | executable_sha256 |
| NATIVE_OPERATION | tools/agent_lifecycle.py | branch:Call(func=Name(id=&#x27;set&#x27;, ctx=Load()), args=[Name(id=&#x27;command&#x27;, ctx=Load())]) | expect |
| NATIVE_OPERATION | tools/agent_lifecycle.py | branch:Call(func=Name(id=&#x27;set&#x27;, ctx=Load()), args=[Name(id=&#x27;command&#x27;, ctx=Load())]) | id |
| NATIVE_OPERATION | tools/agent_lifecycle.py | branch:Call(func=Name(id=&#x27;set&#x27;, ctx=Load()), args=[Name(id=&#x27;command&#x27;, ctx=Load())]) | timeout |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | check_pins | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | check_result | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | compact | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | inspect | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | main | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | publish | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | run | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | sync_directory | None |
| PYTHON_DECLARATION | tools/agent_lifecycle.py | validate | None |
| PYTHON_DECLARATION | tools/benchmark_intent_journal.py | main | None |
| PYTHON_DECLARATION | tools/benchmark_intent_journal.py | measure | None |
| PYTHON_DECLARATION | tools/benchmark_intent_journal.py | payload | None |
| PYTHON_DECLARATION | tools/benchmark_intent_journal.py | publish | None |
| PYTHON_DECLARATION | tools/benchmark_intent_journal.py | replay | None |
| PYTHON_DECLARATION | tools/benchmark_orchestration.py | collect | None |
| PYTHON_DECLARATION | tools/benchmark_orchestration.py | commands | None |
| PYTHON_DECLARATION | tools/benchmark_orchestration.py | main | None |
| PYTHON_DECLARATION | tools/benchmark_orchestration.py | sample | None |
| PYTHON_DECLARATION | tools/benchmark_runtime.py | collect | None |
| PYTHON_DECLARATION | tools/benchmark_runtime.py | main | None |
| PYTHON_DECLARATION | tools/benchmark_runtime.py | sample | None |
| PYTHON_DECLARATION | tools/benchmark_runtime.py | summarize | None |
| CLI_ROUTE | tools/billing_evidence.py | argparse:mode | native-export |
| CLI_ROUTE | tools/billing_evidence.py | argparse:mode | reconcile |
| NATIVE_OPERATION | tools/billing_evidence.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | native-export |
| NATIVE_OPERATION | tools/billing_evidence.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | reconcile |
| PYTHON_DECLARATION | tools/billing_evidence.py | digest | None |
| PYTHON_DECLARATION | tools/billing_evidence.py | load_records | None |
| PYTHON_DECLARATION | tools/billing_evidence.py | main | None |
| PYTHON_DECLARATION | tools/billing_evidence.py | native_report | None |
| PYTHON_DECLARATION | tools/billing_evidence.py | reconcile | None |
| PYTHON_DECLARATION | tools/billing_evidence.py | validate | None |
| PYTHON_DECLARATION | tools/billing_evidence.py | verify | None |
| PYTHON_DECLARATION | tools/check_guard_mutations.py | detected | None |
| PYTHON_DECLARATION | tools/check_guard_mutations.py | main | None |
| PYTHON_DECLARATION | tools/check_guard_mutations.py | replacement | None |
| PYTHON_DECLARATION | tools/classify_failures.py | classify | None |
| PYTHON_DECLARATION | tools/classify_failures.py | main | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | Transport | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | Transport.close | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | Transport.receive | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | Transport.remaining | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | Transport.response | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | Transport.send | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | main | None |
| PYTHON_DECLARATION | tools/codex_hosted.py | run | None |
| PYTHON_DECLARATION | tools/context_resume.py | NoRedirect | None |
| PYTHON_DECLARATION | tools/context_resume.py | NoRedirect.redirect_request | None |
| PYTHON_DECLARATION | tools/context_resume.py | config | None |
| PYTHON_DECLARATION | tools/context_resume.py | count_input | None |
| PYTHON_DECLARATION | tools/context_resume.py | error_detail | None |
| PYTHON_DECLARATION | tools/context_resume.py | main | None |
| PYTHON_DECLARATION | tools/context_resume.py | provider_input | None |
| PYTHON_DECLARATION | tools/context_resume.py | resume | None |
| PYTHON_DECLARATION | tools/context_resume.py | tokenizer_id | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | attempt | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | collect | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | engine | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | filesystem | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | lock | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | main | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | root_probe | None |
| PYTHON_DECLARATION | tools/doctor_environment.py | unix_socket | None |
| CLI_ROUTE | tools/evidence_adapters.py | argparse:command | declaration |
| CLI_ROUTE | tools/evidence_adapters.py | argparse:command | observation |
| CLI_ROUTE | tools/evidence_adapters.py | argparse:command | research-outcome |
| CLI_ROUTE | tools/evidence_adapters.py | argparse:command | review |
| NATIVE_OPERATION | tools/evidence_adapters.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | declaration |
| NATIVE_OPERATION | tools/evidence_adapters.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | observation |
| NATIVE_OPERATION | tools/evidence_adapters.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | review |
| PYTHON_DECLARATION | tools/evidence_adapters.py | declaration | None |
| PYTHON_DECLARATION | tools/evidence_adapters.py | main | None |
| PYTHON_DECLARATION | tools/evidence_adapters.py | observation | None |
| PYTHON_DECLARATION | tools/evidence_adapters.py | process_assessment | None |
| PYTHON_DECLARATION | tools/evidence_adapters.py | read_bytes | None |
| PYTHON_DECLARATION | tools/evidence_adapters.py | research_outcome | None |
| PYTHON_DECLARATION | tools/evidence_adapters.py | review | None |
| PYTHON_DECLARATION | tools/evidence_contract.py | assessment | None |
| PYTHON_DECLARATION | tools/evidence_contract.py | check | None |
| PYTHON_DECLARATION | tools/evidence_contract.py | require | None |
| PYTHON_DECLARATION | tools/evidence_contract.py | set_check | None |
| PYTHON_DECLARATION | tools/evidence_contract.py | sha256 | None |
| PYTHON_DECLARATION | tools/evidence_contract.py | text | None |
| PYTHON_DECLARATION | tools/evidence_contract.py | validate | None |
| CLI_ROUTE | tools/evidence_export.py | argparse:command | catalog-observation |
| CLI_ROUTE | tools/evidence_export.py | argparse:command | export |
| CLI_ROUTE | tools/evidence_export.py | argparse:command | verify |
| NATIVE_OPERATION | tools/evidence_export.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | catalog-observation |
| NATIVE_OPERATION | tools/evidence_export.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | export |
| PYTHON_DECLARATION | tools/evidence_export.py | catalog_validate | None |
| PYTHON_DECLARATION | tools/evidence_export.py | directory_entries | None |
| PYTHON_DECLARATION | tools/evidence_export.py | export | None |
| PYTHON_DECLARATION | tools/evidence_export.py | is_digest | None |
| PYTHON_DECLARATION | tools/evidence_export.py | main | None |
| PYTHON_DECLARATION | tools/evidence_export.py | node | None |
| PYTHON_DECLARATION | tools/evidence_export.py | observation_catalog | None |
| PYTHON_DECLARATION | tools/evidence_export.py | reference | None |
| PYTHON_DECLARATION | tools/evidence_export.py | references | None |
| PYTHON_DECLARATION | tools/evidence_export.py | relative_path | None |
| PYTHON_DECLARATION | tools/evidence_export.py | require | None |
| PYTHON_DECLARATION | tools/evidence_export.py | safe_read | None |
| PYTHON_DECLARATION | tools/evidence_export.py | strict_json | None |
| PYTHON_DECLARATION | tools/evidence_export.py | summary | None |
| PYTHON_DECLARATION | tools/evidence_export.py | verify | None |
| PYTHON_DECLARATION | tools/evidence_export.py | walk | None |
| PYTHON_DECLARATION | tools/execution_record.py | capture | None |
| PYTHON_DECLARATION | tools/execution_record.py | check | None |
| PYTHON_DECLARATION | tools/execution_record.py | digest | None |
| PYTHON_DECLARATION | tools/execution_record.py | encoded | None |
| PYTHON_DECLARATION | tools/execution_record.py | executable_identity | None |
| PYTHON_DECLARATION | tools/execution_record.py | git | None |
| PYTHON_DECLARATION | tools/execution_record.py | metadata | None |
| PYTHON_DECLARATION | tools/execution_record.py | native_inventory | None |
| PYTHON_DECLARATION | tools/execution_record.py | private_directory | None |
| PYTHON_DECLARATION | tools/execution_record.py | run | None |
| PYTHON_DECLARATION | tools/execution_record.py | run_private | None |
| PYTHON_DECLARATION | tools/execution_record.py | save | None |
| PYTHON_DECLARATION | tools/execution_record.py | source_identity | None |
| PYTHON_DECLARATION | tools/execution_record.py | source_observation | None |
| PYTHON_DECLARATION | tools/github_checks.py | APIError | None |
| PYTHON_DECLARATION | tools/github_checks.py | Client | None |
| PYTHON_DECLARATION | tools/github_checks.py | Client.endpoint | None |
| PYTHON_DECLARATION | tools/github_checks.py | Client.get | None |
| PYTHON_DECLARATION | tools/github_checks.py | Client.one | None |
| PYTHON_DECLARATION | tools/github_checks.py | Client.pages | None |
| PYTHON_DECLARATION | tools/github_checks.py | check_state | None |
| PYTHON_DECLARATION | tools/github_checks.py | deployments | None |
| PYTHON_DECLARATION | tools/github_checks.py | discover | None |
| PYTHON_DECLARATION | tools/github_checks.py | evaluate | None |
| PYTHON_DECLARATION | tools/github_checks.py | snapshot | None |
| PYTHON_DECLARATION | tools/github_checks.py | text | None |
| NATIVE_OPERATION | tools/github_context.py | branch:Name(id=&#x27;mode&#x27;, ctx=Load()) | head |
| NATIVE_OPERATION | tools/github_context.py | branch:Name(id=&#x27;mode&#x27;, ctx=Load()) | merge |
| PYTHON_DECLARATION | tools/github_context.py | check | None |
| PYTHON_DECLARATION | tools/github_context.py | ref | None |
| PYTHON_DECLARATION | tools/github_context.py | resolve | None |
| PYTHON_DECLARATION | tools/github_context.py | sha | None |
| PYTHON_DECLARATION | tools/github_context.py | validate | None |
| PYTHON_DECLARATION | tools/github_policy.py | collect | None |
| PYTHON_DECLARATION | tools/github_policy.py | deployment_rule | None |
| PYTHON_DECLARATION | tools/github_policy.py | latest | None |
| PYTHON_DECLARATION | tools/github_policy.py | name | None |
| PYTHON_DECLARATION | tools/github_policy.py | outcome | None |
| PYTHON_DECLARATION | tools/github_policy.py | positive | None |
| PYTHON_DECLARATION | tools/github_policy.py | scanning_rule | None |
| PYTHON_DECLARATION | tools/github_policy.py | scanning_tool | None |
| PYTHON_DECLARATION | tools/github_policy.py | timestamp | None |
| PYTHON_DECLARATION | tools/github_policy.py | unique | None |
| PYTHON_DECLARATION | tools/github_policy.py | workflow_rule | None |
| CLI_ROUTE | tools/hosted_usage.py | argparse:mode | ingest |
| CLI_ROUTE | tools/hosted_usage.py | argparse:mode | listen |
| NATIVE_OPERATION | tools/hosted_usage.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | ingest |
| PYTHON_DECLARATION | tools/hosted_usage.py | Collector | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | Collector.accept | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | Collector.claude | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | Collector.codex | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | Collector.record | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | binding | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | breakdown | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | http_body | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | main | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | otlp_attributes | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | persist | None |
| PYTHON_DECLARATION | tools/hosted_usage.py | server | None |
| PYTHON_DECLARATION | tools/install_conan_cli.py | install | None |
| CLI_ROUTE | tools/instruction_bundle.py | argparse:command | apply |
| CLI_ROUTE | tools/instruction_bundle.py | argparse:command | check |
| CLI_ROUTE | tools/instruction_bundle.py | argparse:command | plan |
| NATIVE_OPERATION | tools/instruction_bundle.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | check |
| NATIVE_OPERATION | tools/instruction_bundle.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | plan |
| PYTHON_DECLARATION | tools/instruction_bundle.py | apply | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | boundary | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | check | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | dependencies | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | fail | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | identity | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | main | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | observed | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | plan | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | relative | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | valid_hash | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | validate_manifest | None |
| PYTHON_DECLARATION | tools/instruction_bundle.py | writable | None |
| NATIVE_OPERATION | tools/integration_backend.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | next |
| NATIVE_OPERATION | tools/integration_backend.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | status |
| PYTHON_DECLARATION | tools/integration_backend.py | audit_capacity | None |
| PYTHON_DECLARATION | tools/integration_backend.py | read | None |
| NATIVE_OPERATION | tools/integration_codex_plugin.py | branch:Call(func=Name(id=&#x27;set&#x27;, ctx=Load()), args=[Name(id=&#x27;command&#x27;, ctx=Load())]) | args |
| NATIVE_OPERATION | tools/integration_codex_plugin.py | branch:Call(func=Name(id=&#x27;set&#x27;, ctx=Load()), args=[Name(id=&#x27;command&#x27;, ctx=Load())]) | command |
| PYTHON_DECLARATION | tools/integration_codex_plugin.py | build | None |
| PYTHON_DECLARATION | tools/integration_codex_plugin.py | main | None |
| PYTHON_DECLARATION | tools/integration_codex_plugin.py | pairs | None |
| PYTHON_DECLARATION | tools/integration_config.py | block | None |
| PYTHON_DECLARATION | tools/integration_config.py | drop | None |
| PYTHON_DECLARATION | tools/integration_config.py | edit | None |
| PYTHON_DECLARATION | tools/integration_config.py | managed | None |
| PYTHON_DECLARATION | tools/integration_config.py | members | None |
| PYTHON_DECLARATION | tools/integration_config.py | parsed | None |
| PYTHON_DECLARATION | tools/integration_contract.py | IntegrationError | None |
| PYTHON_DECLARATION | tools/integration_contract.py | array | None |
| PYTHON_DECLARATION | tools/integration_contract.py | bounded | None |
| PYTHON_DECLARATION | tools/integration_contract.py | decode | None |
| PYTHON_DECLARATION | tools/integration_contract.py | encoded | None |
| PYTHON_DECLARATION | tools/integration_contract.py | enum | None |
| PYTHON_DECLARATION | tools/integration_contract.py | obj | None |
| PYTHON_DECLARATION | tools/integration_contract.py | require | None |
| PYTHON_DECLARATION | tools/integration_contract.py | schema | None |
| PYTHON_DECLARATION | tools/integration_contract.py | sha | None |
| PYTHON_DECLARATION | tools/integration_contract.py | validate | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | Gateway | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | Gateway.app | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | Gateway.authorize | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | Gateway.call | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | Gateway.server | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | Gateway.tools | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | Guard | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | main | None |
| PYTHON_DECLARATION | tools/integration_gateway.py | tls | None |
| PYTHON_DECLARATION | tools/integration_gateway_auth.py | Verifier | None |
| PYTHON_DECLARATION | tools/integration_gateway_auth.py | Verifier.authenticate | None |
| PYTHON_DECLARATION | tools/integration_gateway_auth.py | Verifier.load_keys | None |
| PYTHON_DECLARATION | tools/integration_gateway_auth.py | Verifier.revocations | None |
| PYTHON_DECLARATION | tools/integration_gateway_auth.py | Verifier.verify_token | None |
| CLI_ROUTE | tools/integration_gateway_contract.py | argparse:operation | plan |
| CLI_ROUTE | tools/integration_gateway_contract.py | argparse:operation | schema |
| NATIVE_OPERATION | tools/integration_gateway_contract.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | schema |
| PYTHON_DECLARATION | tools/integration_gateway_contract.py | Policy | None |
| PYTHON_DECLARATION | tools/integration_gateway_contract.py | Policy.current | None |
| PYTHON_DECLARATION | tools/integration_gateway_contract.py | https | None |
| PYTHON_DECLARATION | tools/integration_gateway_contract.py | main | None |
| PYTHON_DECLARATION | tools/integration_gateway_contract.py | producer | None |
| PYTHON_DECLARATION | tools/integration_gateway_contract.py | validate | None |
| PYTHON_DECLARATION | tools/integration_gateway_contract.py | validate_revocations | None |
| CLI_ROUTE | tools/integration_hook_contract.py | argparse:operation | check |
| CLI_ROUTE | tools/integration_hook_contract.py | argparse:operation | fragment |
| CLI_ROUTE | tools/integration_hook_contract.py | argparse:operation | pin |
| CLI_ROUTE | tools/integration_hook_contract.py | argparse:operation | plan |
| CLI_ROUTE | tools/integration_hook_contract.py | argparse:operation | schema |
| NATIVE_OPERATION | tools/integration_hook_contract.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | fragment |
| NATIVE_OPERATION | tools/integration_hook_contract.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | pin |
| NATIVE_OPERATION | tools/integration_hook_contract.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | plan |
| NATIVE_OPERATION | tools/integration_hook_contract.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | schema |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | Profile | None |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | Profile.current | None |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | executable_pin | None |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | fragment | None |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | main | None |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | plan | None |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | producer | None |
| PYTHON_DECLARATION | tools/integration_hook_contract.py | validate | None |
| PYTHON_DECLARATION | tools/integration_hooks.py | envelope | None |
| PYTHON_DECLARATION | tools/integration_hooks.py | event | None |
| PYTHON_DECLARATION | tools/integration_hooks.py | failure | None |
| PYTHON_DECLARATION | tools/integration_hooks.py | main | None |
| PYTHON_DECLARATION | tools/integration_hooks.py | observe | None |
| PYTHON_DECLARATION | tools/integration_hooks.py | preflight | None |
| CLI_ROUTE | tools/integration_install.py | argparse:--operation | bootstrap |
| CLI_ROUTE | tools/integration_install.py | argparse:--operation | install |
| CLI_ROUTE | tools/integration_install.py | argparse:--operation | remove |
| CLI_ROUTE | tools/integration_install.py | argparse:command | apply |
| CLI_ROUTE | tools/integration_install.py | argparse:command | init |
| CLI_ROUTE | tools/integration_install.py | argparse:command | inspect |
| CLI_ROUTE | tools/integration_install.py | argparse:command | plan |
| CLI_ROUTE | tools/integration_install.py | argparse:command | repair |
| CLI_ROUTE | tools/integration_install.py | argparse:command | runtime |
| CLI_ROUTE | tools/integration_install.py | argparse:command | schema |
| NATIVE_OPERATION | tools/integration_install.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | init |
| NATIVE_OPERATION | tools/integration_install.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | inspect |
| NATIVE_OPERATION | tools/integration_install.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | plan |
| NATIVE_OPERATION | tools/integration_install.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | repair |
| NATIVE_OPERATION | tools/integration_install.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | runtime |
| NATIVE_OPERATION | tools/integration_install.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | schema |
| NATIVE_OPERATION | tools/integration_install.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | bootstrap |
| NATIVE_OPERATION | tools/integration_install.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | install |
| NATIVE_OPERATION | tools/integration_install.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | remove |
| PYTHON_DECLARATION | tools/integration_install.py | Installer | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.apply | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.bootstrap | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.directory | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.facts | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.inspect | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.launch | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.original | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.plan | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.stored | None |
| PYTHON_DECLARATION | tools/integration_install.py | Installer.target | None |
| PYTHON_DECLARATION | tools/integration_install.py | directory_lock | None |
| PYTHON_DECLARATION | tools/integration_install.py | main | None |
| PYTHON_DECLARATION | tools/integration_install.py | mkdir | None |
| PYTHON_DECLARATION | tools/integration_install.py | parent | None |
| PYTHON_DECLARATION | tools/integration_install.py | producer | None |
| PYTHON_DECLARATION | tools/integration_install.py | publish_config | None |
| PYTHON_DECLARATION | tools/integration_install.py | retain | None |
| PYTHON_DECLARATION | tools/integration_install.py | snapshot | None |
| PYTHON_DECLARATION | tools/integration_launch.py | check | None |
| PYTHON_DECLARATION | tools/integration_launch.py | main | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | clearance | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | current | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | fence | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | lock | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | participation | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | pointer | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | publish | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | quiet | None |
| PYTHON_DECLARATION | tools/integration_lifecycle.py | retired_identity | None |
| PYTHON_DECLARATION | tools/integration_mcp.py | BoundedInput | None |
| PYTHON_DECLARATION | tools/integration_mcp.py | icon_bytes | None |
| PYTHON_DECLARATION | tools/integration_mcp.py | main | None |
| PYTHON_DECLARATION | tools/integration_mcp.py | run | None |
| PYTHON_DECLARATION | tools/integration_mcp.py | server | None |
| PYTHON_DECLARATION | tools/integration_mcp.py | server_icons | None |
| PYTHON_DECLARATION | tools/integration_mcpb.py | build | None |
| PYTHON_DECLARATION | tools/integration_mcpb.py | main | None |
| PYTHON_DECLARATION | tools/integration_mcpb.py | manifest | None |
| PYTHON_DECLARATION | tools/integration_mcpb_entry.py | configured_service | None |
| PYTHON_DECLARATION | tools/integration_mcpb_entry.py | main | None |
| PYTHON_DECLARATION | tools/integration_mcpb_entry.py | run_setup | None |
| PYTHON_DECLARATION | tools/integration_mcpb_entry.py | setup_notice | None |
| PYTHON_DECLARATION | tools/integration_mcpb_entry.py | setup_server | None |
| CLI_ROUTE | tools/integration_mutation_contract.py | argparse:operation | check |
| CLI_ROUTE | tools/integration_mutation_contract.py | argparse:operation | plan |
| CLI_ROUTE | tools/integration_mutation_contract.py | argparse:operation | schema |
| NATIVE_OPERATION | tools/integration_mutation_contract.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | plan |
| NATIVE_OPERATION | tools/integration_mutation_contract.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | schema |
| NATIVE_OPERATION | tools/integration_mutation_contract.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | claim |
| NATIVE_OPERATION | tools/integration_mutation_contract.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | reconcile |
| NATIVE_OPERATION | tools/integration_mutation_contract.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | resume |
| NATIVE_OPERATION | tools/integration_mutation_contract.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | submit |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | Policy | None |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | Policy.action | None |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | Policy.authorize | None |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | Policy.current | None |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | main | None |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | native_action | None |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | producer | None |
| PYTHON_DECLARATION | tools/integration_mutation_contract.py | validate | None |
| PYTHON_DECLARATION | tools/integration_mutation_mcp.py | main | None |
| PYTHON_DECLARATION | tools/integration_mutation_mcp.py | run | None |
| PYTHON_DECLARATION | tools/integration_mutation_mcp.py | server | None |
| PYTHON_DECLARATION | tools/integration_mutations.py | Service | None |
| PYTHON_DECLARATION | tools/integration_mutations.py | Service.call | None |
| PYTHON_DECLARATION | tools/integration_mutations.py | Service.tools | None |
| PYTHON_DECLARATION | tools/integration_mutations.py | blocked | None |
| CLI_ROUTE | tools/integration_recovery.py | argparse:command | apply |
| CLI_ROUTE | tools/integration_recovery.py | argparse:command | plan |
| CLI_ROUTE | tools/integration_recovery.py | argparse:command | schema |
| NATIVE_OPERATION | tools/integration_recovery.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | plan |
| NATIVE_OPERATION | tools/integration_recovery.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | schema |
| PYTHON_DECLARATION | tools/integration_recovery.py | apply | None |
| PYTHON_DECLARATION | tools/integration_recovery.py | audit_inventory | None |
| PYTHON_DECLARATION | tools/integration_recovery.py | facts | None |
| PYTHON_DECLARATION | tools/integration_recovery.py | main | None |
| PYTHON_DECLARATION | tools/integration_recovery.py | plan | None |
| CLI_ROUTE | tools/integration_registry.py | argparse:operation | apply |
| CLI_ROUTE | tools/integration_registry.py | argparse:operation | describe |
| CLI_ROUTE | tools/integration_registry.py | argparse:operation | init |
| CLI_ROUTE | tools/integration_registry.py | argparse:operation | plan |
| CLI_ROUTE | tools/integration_registry.py | argparse:operation | read |
| CLI_ROUTE | tools/integration_registry.py | argparse:operation | revoke |
| CLI_ROUTE | tools/integration_registry.py | argparse:operation | revoke-plan |
| CLI_ROUTE | tools/integration_registry.py | argparse:operation | schema |
| NATIVE_OPERATION | tools/integration_registry.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | describe |
| NATIVE_OPERATION | tools/integration_registry.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | init |
| NATIVE_OPERATION | tools/integration_registry.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | plan |
| NATIVE_OPERATION | tools/integration_registry.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | read |
| NATIVE_OPERATION | tools/integration_registry.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | revoke |
| NATIVE_OPERATION | tools/integration_registry.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | revoke-plan |
| NATIVE_OPERATION | tools/integration_registry.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | schema |
| PYTHON_DECLARATION | tools/integration_registry.py | Registry | None |
| PYTHON_DECLARATION | tools/integration_registry.py | Registry.apply | None |
| PYTHON_DECLARATION | tools/integration_registry.py | Registry.authorize | None |
| PYTHON_DECLARATION | tools/integration_registry.py | Registry.create | None |
| PYTHON_DECLARATION | tools/integration_registry.py | Registry.locked | None |
| PYTHON_DECLARATION | tools/integration_registry.py | Registry.plan | None |
| PYTHON_DECLARATION | tools/integration_registry.py | check_project | None |
| PYTHON_DECLARATION | tools/integration_registry.py | describe | None |
| PYTHON_DECLARATION | tools/integration_registry.py | file_pin | None |
| PYTHON_DECLARATION | tools/integration_registry.py | identity | None |
| PYTHON_DECLARATION | tools/integration_registry.py | main | None |
| PYTHON_DECLARATION | tools/integration_registry.py | producer | None |
| PYTHON_DECLARATION | tools/integration_registry.py | real_path | None |
| PYTHON_DECLARATION | tools/integration_registry.py | regular | None |
| NATIVE_OPERATION | tools/integration_reload_probe.py | branch:Name(id=&#x27;mode&#x27;, ctx=Load()) | auto |
| NATIVE_OPERATION | tools/integration_reload_probe.py | branch:Name(id=&#x27;mode&#x27;, ctx=Load()) | legacy |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | append_log | None |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | command | None |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | main | None |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | probe | None |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | runtime | None |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | validate_runtime | None |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | worker | None |
| PYTHON_DECLARATION | tools/integration_reload_probe.py | worker_args | None |
| PYTHON_DECLARATION | tools/integration_service.py | Service | None |
| PYTHON_DECLARATION | tools/integration_service.py | Service.available | None |
| PYTHON_DECLARATION | tools/integration_service.py | Service.call | None |
| PYTHON_DECLARATION | tools/integration_service.py | Service.tools | None |
| PYTHON_DECLARATION | tools/integration_service.py | blocked | None |
| PYTHON_DECLARATION | tools/integration_service.py | context_failure | None |
| PYTHON_DECLARATION | tools/integration_service.py | counter_semantics | None |
| CLI_ROUTE | tools/integration_transfer.py | argparse:operation | plan |
| CLI_ROUTE | tools/integration_transfer.py | argparse:operation | schema |
| NATIVE_OPERATION | tools/integration_transfer.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;operation&#x27;, ctx=Load()) | schema |
| PYTHON_DECLARATION | tools/integration_transfer.py | Transfer | None |
| PYTHON_DECLARATION | tools/integration_transfer.py | Transfer.current | None |
| PYTHON_DECLARATION | tools/integration_transfer.py | Transfer.scope | None |
| PYTHON_DECLARATION | tools/integration_transfer.py | main | None |
| PYTHON_DECLARATION | tools/integration_transfer.py | producer | None |
| PYTHON_DECLARATION | tools/integration_transfer.py | validate | None |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | freeze |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | ready |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | repair-switch |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | restore |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | stage |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | stage-repair |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | switch |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | thaw |
| CLI_ROUTE | tools/integration_update.py | argparse:--operation | verify |
| CLI_ROUTE | tools/integration_update.py | argparse:command | apply |
| CLI_ROUTE | tools/integration_update.py | argparse:command | inspect |
| CLI_ROUTE | tools/integration_update.py | argparse:command | plan |
| CLI_ROUTE | tools/integration_update.py | argparse:command | schema |
| NATIVE_OPERATION | tools/integration_update.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | inspect |
| NATIVE_OPERATION | tools/integration_update.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | plan |
| NATIVE_OPERATION | tools/integration_update.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;command&#x27;, ctx=Load()) | schema |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | freeze |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | ready |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | repair-switch |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | restore |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | stage |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | stage-repair |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | switch |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | thaw |
| NATIVE_OPERATION | tools/integration_update.py | branch:Name(id=&#x27;operation&#x27;, ctx=Load()) | verify |
| PYTHON_DECLARATION | tools/integration_update.py | Manager | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.apply | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.bundle | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.enrollment | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.facts | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.frozen | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.observe | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.plan | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.quiet | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.stage_facts | None |
| PYTHON_DECLARATION | tools/integration_update.py | Manager.unresolved | None |
| PYTHON_DECLARATION | tools/integration_update.py | acknowledge | None |
| PYTHON_DECLARATION | tools/integration_update.py | inventory | None |
| PYTHON_DECLARATION | tools/integration_update.py | main | None |
| PYTHON_DECLARATION | tools/integration_update.py | pinned | None |
| PYTHON_DECLARATION | tools/integration_update.py | producer | None |
| PYTHON_DECLARATION | tools/intent_authority.py | authority_identity | None |
| PYTHON_DECLARATION | tools/intent_authority.py | authorized_root | None |
| PYTHON_DECLARATION | tools/intent_authority.py | native_inspect | None |
| PYTHON_DECLARATION | tools/intent_authority.py | object_store_plan | None |
| PYTHON_DECLARATION | tools/intent_authority.py | read_baseline | None |
| PYTHON_DECLARATION | tools/intent_authority.py | register | None |
| PYTHON_DECLARATION | tools/intent_authority.py | registration_plan | None |
| PYTHON_DECLARATION | tools/intent_authority.py | repository_identity | None |
| PYTHON_DECLARATION | tools/intent_authority.py | revocation_plan | None |
| PYTHON_DECLARATION | tools/intent_authority.py | revoke | None |
| PYTHON_DECLARATION | tools/intent_authority.py | store_objects | None |
| PYTHON_DECLARATION | tools/intent_authority.py | validate_locator | None |
| PYTHON_DECLARATION | tools/intent_authority.py | verify_observation | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | alias_recovery_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | change | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | change_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | damage_recovery_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | envelope_recovery_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | finish_envelope | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | finish_host_final | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | finish_host_publication | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | finish_host_terminal | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | fragment_recovery_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | host_alias_recovery_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | host_final_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | host_publication_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | host_terminal_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | native_recovery_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | partial_recovery_plan | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | recover | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | recover_alias | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | recover_damage | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | recover_fragment | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | recover_host_alias | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | recover_native | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | recover_partial | None |
| PYTHON_DECLARATION | tools/intent_authority_lifecycle.py | recovery_plan | None |
| PYTHON_DECLARATION | tools/isolation_canary.py | main | None |
| PYTHON_DECLARATION | tools/judgment_record.py | ContractError | None |
| PYTHON_DECLARATION | tools/judgment_record.py | binding | None |
| PYTHON_DECLARATION | tools/judgment_record.py | fact_ids | None |
| PYTHON_DECLARATION | tools/judgment_record.py | facts | None |
| PYTHON_DECLARATION | tools/judgment_record.py | identifier | None |
| PYTHON_DECLARATION | tools/judgment_record.py | load | None |
| PYTHON_DECLARATION | tools/judgment_record.py | replay | None |
| PYTHON_DECLARATION | tools/judgment_record.py | require | None |
| PYTHON_DECLARATION | tools/judgment_record.py | validate_binding | None |
| PYTHON_DECLARATION | tools/judgment_record.py | validate_delta | None |
| PYTHON_DECLARATION | tools/judgment_record.py | view | None |
| PYTHON_DECLARATION | tools/judgment_record.py | write | None |
| PYTHON_DECLARATION | tools/native_record.py | check | None |
| CLI_ROUTE | tools/provider_costs.py | argparse:mode | fetch |
| CLI_ROUTE | tools/provider_costs.py | argparse:mode | ingest |
| CLI_ROUTE | tools/provider_costs.py | argparse:mode | view |
| NATIVE_OPERATION | tools/provider_costs.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | fetch |
| NATIVE_OPERATION | tools/provider_costs.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | ingest |
| NATIVE_OPERATION | tools/provider_costs.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | view |
| PYTHON_DECLARATION | tools/provider_costs.py | CostError | None |
| PYTHON_DECLARATION | tools/provider_costs.py | NoRedirect | None |
| PYTHON_DECLARATION | tools/provider_costs.py | NoRedirect.redirect_request | None |
| PYTHON_DECLARATION | tools/provider_costs.py | collect | None |
| PYTHON_DECLARATION | tools/provider_costs.py | compare | None |
| PYTHON_DECLARATION | tools/provider_costs.py | decimal_amount | None |
| PYTHON_DECLARATION | tools/provider_costs.py | iso | None |
| PYTHON_DECLARATION | tools/provider_costs.py | load | None |
| PYTHON_DECLARATION | tools/provider_costs.py | main | None |
| PYTHON_DECLARATION | tools/provider_costs.py | normalize_report | None |
| PYTHON_DECLARATION | tools/provider_costs.py | params | None |
| PYTHON_DECLARATION | tools/provider_costs.py | parse_page | None |
| PYTHON_DECLARATION | tools/provider_costs.py | query | None |
| PYTHON_DECLARATION | tools/provider_costs.py | request | None |
| PYTHON_DECLARATION | tools/provider_costs.py | timestamp | None |
| PYTHON_DECLARATION | tools/provider_usage.py | add | None |
| PYTHON_DECLARATION | tools/provider_usage.py | anthropic | None |
| PYTHON_DECLARATION | tools/provider_usage.py | binding | None |
| PYTHON_DECLARATION | tools/provider_usage.py | codex | None |
| PYTHON_DECLARATION | tools/provider_usage.py | collect | None |
| PYTHON_DECLARATION | tools/provider_usage.py | collect_cli | None |
| PYTHON_DECLARATION | tools/provider_usage.py | count | None |
| PYTHON_DECLARATION | tools/provider_usage.py | emit | None |
| PYTHON_DECLARATION | tools/provider_usage.py | event | None |
| PYTHON_DECLARATION | tools/provider_usage.py | merge | None |
| PYTHON_DECLARATION | tools/provider_usage.py | model_name | None |
| PYTHON_DECLARATION | tools/provider_usage.py | openai | None |
| PYTHON_DECLARATION | tools/provider_usage.py | private_bytes | None |
| PYTHON_DECLARATION | tools/provider_usage.py | text | None |
| PYTHON_DECLARATION | tools/provider_usage.py | totals | None |
| PYTHON_DECLARATION | tools/remote_status.py | NoRedirect | None |
| PYTHON_DECLARATION | tools/remote_status.py | NoRedirect.redirect_request | None |
| PYTHON_DECLARATION | tools/remote_status.py | QueryError | None |
| PYTHON_DECLARATION | tools/remote_status.py | check | None |
| PYTHON_DECLARATION | tools/remote_status.py | decode | None |
| PYTHON_DECLARATION | tools/remote_status.py | get | None |
| PYTHON_DECLARATION | tools/remote_status.py | main | None |
| PYTHON_DECLARATION | tools/remote_status.py | refresh | None |
| PYTHON_DECLARATION | tools/remote_status.py | timestamp | None |
| PYTHON_DECLARATION | tools/remote_status.py | validate_queries | None |
| PYTHON_DECLARATION | tools/retire_legacy_cli.py | recognized | None |
| PYTHON_DECLARATION | tools/retire_legacy_cli.py | retire | None |
| PYTHON_DECLARATION | tools/revision_status.py | evidence | None |
| PYTHON_DECLARATION | tools/revision_status.py | github_deployment | None |
| PYTHON_DECLARATION | tools/revision_status.py | github_run | None |
| PYTHON_DECLARATION | tools/revision_status.py | junit | None |
| PYTHON_DECLARATION | tools/revision_status.py | main | None |
| PYTHON_DECLARATION | tools/revision_status.py | native_completion | None |
| PYTHON_DECLARATION | tools/revision_status.py | observe | None |
| PYTHON_DECLARATION | tools/revision_status.py | projection | None |
| PYTHON_DECLARATION | tools/revision_status.py | remote_relation | None |
| PYTHON_DECLARATION | tools/revision_status.py | source_relation | None |
| PYTHON_DECLARATION | tools/revision_status.py | target_source | None |
| PYTHON_DECLARATION | tools/revision_status.py | validate | None |
| CLI_ROUTE | tools/status_collector.py | argparse:mode | collect |
| CLI_ROUTE | tools/status_collector.py | argparse:mode | status |
| NATIVE_OPERATION | tools/status_collector.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | status |
| PYTHON_DECLARATION | tools/status_collector.py | atomic | None |
| PYTHON_DECLARATION | tools/status_collector.py | collect | None |
| PYTHON_DECLARATION | tools/status_collector.py | config | None |
| PYTHON_DECLARATION | tools/status_collector.py | credential | None |
| PYTHON_DECLARATION | tools/status_collector.py | directory | None |
| PYTHON_DECLARATION | tools/status_collector.py | lock | None |
| PYTHON_DECLARATION | tools/status_collector.py | main | None |
| PYTHON_DECLARATION | tools/status_collector.py | private_json | None |
| PYTHON_DECLARATION | tools/status_collector.py | read | None |
| PYTHON_DECLARATION | tools/status_collector.py | run | None |
| PYTHON_DECLARATION | tools/syscall_record.py | capture | None |
| PYTHON_DECLARATION | tools/syscall_record.py | command | None |
| PYTHON_DECLARATION | tools/syscall_record.py | main | None |
| CLI_ROUTE | tools/usage_pipeline.py | argparse:mode | close |
| CLI_ROUTE | tools/usage_pipeline.py | argparse:mode | deliver |
| CLI_ROUTE | tools/usage_pipeline.py | argparse:mode | init |
| CLI_ROUTE | tools/usage_pipeline.py | argparse:mode | listen |
| CLI_ROUTE | tools/usage_pipeline.py | argparse:mode | pump |
| CLI_ROUTE | tools/usage_pipeline.py | argparse:mode | run-claude |
| CLI_ROUTE | tools/usage_pipeline.py | argparse:mode | sync |
| NATIVE_OPERATION | tools/usage_pipeline.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | close |
| NATIVE_OPERATION | tools/usage_pipeline.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | deliver |
| NATIVE_OPERATION | tools/usage_pipeline.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | init |
| NATIVE_OPERATION | tools/usage_pipeline.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | listen |
| NATIVE_OPERATION | tools/usage_pipeline.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | pump |
| NATIVE_OPERATION | tools/usage_pipeline.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | run-claude |
| NATIVE_OPERATION | tools/usage_pipeline.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | sync |
| PYTHON_DECLARATION | tools/usage_pipeline.py | Pipeline | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | Pipeline.accept | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | Pipeline.close | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | Pipeline.create | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | Pipeline.load | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | Pipeline.locked | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | Pipeline.sync | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | atomic | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | claude_environment | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | deliver | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | main | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | private_dir | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | route | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | run_claude | None |
| PYTHON_DECLARATION | tools/usage_pipeline.py | sanitized | None |
| CLI_ROUTE | tools/verify_agent.py | argparse:mode | fixture |
| CLI_ROUTE | tools/verify_agent.py | argparse:mode | observe |
| CLI_ROUTE | tools/verify_agent.py | argparse:mode | report |
| NATIVE_OPERATION | tools/verify_agent.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | fixture |
| NATIVE_OPERATION | tools/verify_agent.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | observe |
| NATIVE_OPERATION | tools/verify_agent.py | branch:Attribute(value=Name(id=&#x27;args&#x27;, ctx=Load()), attr=&#x27;mode&#x27;, ctx=Load()) | report |
| PYTHON_DECLARATION | tools/verify_agent.py | base | None |
| PYTHON_DECLARATION | tools/verify_agent.py | capture | None |
| PYTHON_DECLARATION | tools/verify_agent.py | fixture | None |
| PYTHON_DECLARATION | tools/verify_agent.py | main | None |
| PYTHON_DECLARATION | tools/verify_agent.py | observe | None |
| PYTHON_DECLARATION | tools/verify_agent.py | render_report | None |
| PYTHON_DECLARATION | tools/verify_agent.py | save | None |
| PYTHON_DECLARATION | tools/verify_agent.py | strict_json | None |
| PYTHON_DECLARATION | tools/verify_agent.py | suite_digest | None |
| PYTHON_DECLARATION | tools/verify_agent.py | write_report | None |
| PYTHON_DECLARATION | tools/verify_alpha.py | audit_install | None |
| PYTHON_DECLARATION | tools/verify_alpha.py | main | None |
| PYTHON_DECLARATION | tools/verify_alpha.py | run | None |
| PYTHON_DECLARATION | tools/verify_alpha.py | snapshot | None |
| PYTHON_DECLARATION | tools/verify_environment.py | check_bundle | None |
| PYTHON_DECLARATION | tools/verify_environment.py | encoded | None |
| PYTHON_DECLARATION | tools/verify_environment.py | execute | None |
| PYTHON_DECLARATION | tools/verify_environment.py | main | None |
| PYTHON_DECLARATION | tools/verify_environment.py | read_doctor | None |
| PYTHON_DECLARATION | tools/verify_environment.py | run | None |
| PYTHON_DECLARATION | tools/verify_environment.py | select_tests | None |
| PYTHON_DECLARATION | tools/verify_environment.py | successful | None |
| PYTHON_DECLARATION | tools/verify_environment.py | verdict | None |
| PYTHON_DECLARATION | tools/verify_gateway_schema.py | main | None |
| PYTHON_DECLARATION | tools/verify_hook_schema.py | main | None |
| PYTHON_DECLARATION | tools/verify_install_schema.py | main | None |
| PYTHON_DECLARATION | tools/verify_integration_schema.py | main | None |
| PYTHON_DECLARATION | tools/verify_isolation.py | main | None |
| PYTHON_DECLARATION | tools/verify_isolation.py | qualify | None |
| PYTHON_DECLARATION | tools/verify_mutation_schema.py | main | None |
| PYTHON_DECLARATION | tools/verify_orchestration.py | main | None |
| PYTHON_DECLARATION | tools/verify_preflight.py | audit_groups | None |
| PYTHON_DECLARATION | tools/verify_preflight.py | main | None |
| PYTHON_DECLARATION | tools/verify_resource.py | counters | None |
| PYTHON_DECLARATION | tools/verify_resource.py | main | None |
| PYTHON_DECLARATION | tools/verify_resource.py | verify | None |
| NATIVE_OPERATION | tools/verify_runtime.py | branch:Subscript(value=Name(id=&#x27;command&#x27;, ctx=Load()), slice=BinOp(left=Name(id=&#x27;index&#x27;, ctx=Load()), op=Sub(), right=Constant(value=1)), ctx=Load()) | --start-directory |
| NATIVE_OPERATION | tools/verify_runtime.py | branch:Subscript(value=Name(id=&#x27;command&#x27;, ctx=Load()), slice=BinOp(left=Name(id=&#x27;index&#x27;, ctx=Load()), op=Sub(), right=Constant(value=1)), ctx=Load()) | -s |
| PYTHON_DECLARATION | tools/verify_runtime.py | adjudicate | None |
| PYTHON_DECLARATION | tools/verify_runtime.py | main | None |
| PYTHON_DECLARATION | tools/verify_runtime.py | required_tests | None |
| PYTHON_DECLARATION | tools/verify_runtime.py | run | None |
| PYTHON_DECLARATION | tools/verify_runtime.py | test_inputs | None |
| PYTHON_DECLARATION | tools/verify_runtime_legacy.py | main | None |
| PYTHON_DECLARATION | tools/verify_runtime_legacy.py | schema_rejection | None |
| PYTHON_DECLARATION | tools/verify_runtime_legacy.py | verify | None |
| PYTHON_DECLARATION | tools/verify_update_schema.py | main | None |
| NATIVE_OPERATION | src/agent_session/storage.c | as_publication_guard | None |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | approval_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | artifact_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | binding_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | bundle_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | configuration_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | context_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | diagnostic_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | discovery_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | document_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | events_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | journal_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | native_validate |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | profile_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | reentry_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | report_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | revision_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | role_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | session_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | template_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | usage_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | workflow_read |
| CLI_ROUTE | src/cli/completion.c | golem_cli_completion | inspect |
| CLI_ROUTE | src/cli/reentry.c | golem_cli_reentry | inspect |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | approval_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | binding_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | context_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | diagnostic_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | discovery_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | document_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | journal_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | native_validate |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | profile_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | reentry_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | report_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | role_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | session_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | template_read |
| MCP_TOOL_DECLARATION | tools/integration_reads.py | SCHEMAS | workflow_read |
| MCP_TOOL_DECLARATION | tools/integration_read_resources.py | SCHEMAS | artifact_read |
| MCP_TOOL_DECLARATION | tools/integration_read_resources.py | SCHEMAS | bundle_read |
| MCP_TOOL_DECLARATION | tools/integration_read_resources.py | SCHEMAS | configuration_read |
| MCP_TOOL_DECLARATION | tools/integration_read_resources.py | SCHEMAS | events_read |
| MCP_TOOL_DECLARATION | tools/integration_read_resources.py | SCHEMAS | revision_read |
| MCP_TOOL_DECLARATION | tools/integration_read_resources.py | SCHEMAS | usage_read |
| PYTHON_DECLARATION | tools/integration_reads.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_read_resources.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_read_views.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_read_resources.py | owner-commands | schema |
| PYTHON_DECLARATION | tools/integration_read_resources.py | owner-commands | plan |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | action_confirm |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | action_prepare |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | approved_action_prepare |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | contract_prepare |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | inputs_prepare |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | plan_read |
| CLI_ROUTE | src/cli/agent_session.c | golem_cli_agent_session | validate |
| MCP_TOOL_DECLARATION | tools/integration_preparations.py | SCHEMAS | action_confirm |
| MCP_TOOL_DECLARATION | tools/integration_preparations.py | SCHEMAS | action_prepare |
| MCP_TOOL_DECLARATION | tools/integration_preparations.py | SCHEMAS | approved_action_prepare |
| MCP_TOOL_DECLARATION | tools/integration_preparations.py | SCHEMAS | contract_prepare |
| MCP_TOOL_DECLARATION | tools/integration_preparations.py | SCHEMAS | inputs_prepare |
| MCP_TOOL_DECLARATION | tools/integration_preparations.py | SCHEMAS | plan_read |
| PYTHON_DECLARATION | tools/integration_preparations.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_prepare_builders.py | file-surface | None |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | adapter_noop_run |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | approval_request |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | binding_attach |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | completion_finalize |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | completion_report |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | context_publish |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | discovery_snapshot |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | document_project |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | lineage_store |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | profile_register |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | reentry_decide |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | reentry_report |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | role_assess |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | role_enroll |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | run_link |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | session_heartbeat |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | session_reject_output |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | session_start |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | work_create |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | work_noop_run |
| CLI_ROUTE | src/cli/approval.c | golem_cli_approval | validate |
| CLI_ROUTE | src/cli/lineage.c | golem_cli_lineage | store |
| CLI_ROUTE | src/cli/role.c | golem_cli_role | request-validate |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | adapter_noop_run |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | approval_request |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | binding_attach |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | completion_finalize |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | completion_report |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | context_publish |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | discovery_snapshot |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | document_project |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | lineage_store |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | profile_register |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | reentry_decide |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | reentry_report |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | role_assess |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | role_enroll |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | run_link |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | session_heartbeat |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | session_reject_output |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | session_start |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | work_create |
| MCP_TOOL_DECLARATION | tools/integration_task_actions.py | NAMES | work_noop_run |
| PYTHON_DECLARATION | tools/integration_task_actions.py | file-surface | None |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | cost_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | execution_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | proof_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | research_read |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | cost_inbox_reconcile |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | evidence_import |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | execution_verify |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | helper_execute |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | proof_publish |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | research_export |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | research_request |
| CLI_ROUTE | src/cli/execution.c | golem_cli_execution | verify |
| CLI_ROUTE | src/cli/execution.c | golem_cli_execution | verify-authorized |
| CLI_ROUTE | src/cli/research.c | golem_cli_research | redaction-validate |
| MCP_TOOL_DECLARATION | tools/integration_quality_actions.py | NAMES | cost_inbox_reconcile |
| MCP_TOOL_DECLARATION | tools/integration_quality_actions.py | NAMES | evidence_import |
| MCP_TOOL_DECLARATION | tools/integration_quality_actions.py | NAMES | execution_verify |
| MCP_TOOL_DECLARATION | tools/integration_quality_actions.py | NAMES | helper_execute |
| MCP_TOOL_DECLARATION | tools/integration_quality_actions.py | NAMES | proof_publish |
| MCP_TOOL_DECLARATION | tools/integration_quality_actions.py | NAMES | research_export |
| MCP_TOOL_DECLARATION | tools/integration_quality_actions.py | NAMES | research_request |
| MCP_TOOL_DECLARATION | tools/integration_quality_reads.py | SCHEMAS | cost_read |
| MCP_TOOL_DECLARATION | tools/integration_quality_reads.py | SCHEMAS | execution_read |
| MCP_TOOL_DECLARATION | tools/integration_quality_reads.py | SCHEMAS | proof_read |
| MCP_TOOL_DECLARATION | tools/integration_quality_reads.py | SCHEMAS | research_read |
| PYTHON_DECLARATION | tools/integration_quality_actions.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_quality_reads.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_helper_contract.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_helper_contract.py | owner_cli | schema |
| PYTHON_DECLARATION | tools/integration_helper_contract.py | owner_cli | plan |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | --noop |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | inbox |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | report |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | validate |
| CLI_ROUTE | src/cli/main.c | dispatch | inventory |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | candidate_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | inventory_read |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | merge_prepare |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | parallel_prepare |
| MCP_TOOL_DECLARATION | tools/integration_service.py | SCHEMAS | workspace_read |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | candidate_request |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | inventory_capture |
| MCP_TOOL_DECLARATION | tools/integration_mutation_contract.py | NAMES | workspace_request |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | inventory |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | capture |
| CLI_ROUTE | src/cli/work.c | golem_cli_work | compare |
| MCP_TOOL_DECLARATION | tools/integration_parallel_actions.py | NAMES | candidate_request |
| MCP_TOOL_DECLARATION | tools/integration_parallel_actions.py | NAMES | inventory_capture |
| MCP_TOOL_DECLARATION | tools/integration_parallel_actions.py | NAMES | workspace_request |
| MCP_TOOL_DECLARATION | tools/integration_parallel_reads.py | SCHEMAS | candidate_read |
| MCP_TOOL_DECLARATION | tools/integration_parallel_reads.py | SCHEMAS | inventory_read |
| MCP_TOOL_DECLARATION | tools/integration_parallel_reads.py | SCHEMAS | workspace_read |
| MCP_TOOL_DECLARATION | tools/integration_parallel_preparations.py | SCHEMAS | merge_prepare |
| MCP_TOOL_DECLARATION | tools/integration_parallel_preparations.py | SCHEMAS | parallel_prepare |
| PYTHON_DECLARATION | tools/integration_parallel_actions.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_parallel_reads.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_parallel_hosts.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_parallel_preparations.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_parallel_hosts.py | owner_cli | schema |
| PYTHON_DECLARATION | tools/integration_parallel_hosts.py | owner_cli | plan |
| PYTHON_DECLARATION | tools/integration_feature_profiles.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_distribution.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_distribution_entry.py | file-surface | None |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | file-surface | None |
| NATIVE_OPERATION | plugins/golem/skills/golem-work/SKILL.md | file-surface | None |
| NATIVE_OPERATION | plugins/golem/skills/golem-work/agents/openai.yaml | file-surface | None |
| NATIVE_OPERATION | plugins/golem/skills/golem-work/references/profiles.md | file-surface | None |
| MCP_TOOL_DECLARATION | tools/integration_owner_maintenance.py | MANAGEMENT_SCHEMAS | management_catalog |
| MCP_TOOL_DECLARATION | tools/integration_owner_maintenance.py | MANAGEMENT_SCHEMAS | management_prepare |
| MCP_TOOL_DECLARATION | tools/integration_owner_maintenance.py | MANAGEMENT_SCHEMAS | management_request |
| MCP_TOOL_DECLARATION | tools/integration_owner_maintenance.py | MANAGEMENT_SCHEMAS | management_result |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | daemon_status |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | daemon_init |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | daemon_submit |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | daemon_run_once |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | daemon_drain |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | daemon_recover |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | journal_inspect |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | journal_verify_salvage |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | journal_salvage |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | adapter_describe |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | adapter_noop_probe |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | admission_probe |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | approval_decide |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | approval_describe |
| MCP_TOOL_DECLARATION | tools/integration_owner_maintenance.py | MANAGEMENT_SCHEMAS | management_host_status |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | management_argv | adapter_convert |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | ManagementService._delivery | adapter_probe |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | ManagementService._delivery | candidate_serve |
| PYTHON_DECLARATION | tools/integration_owner_maintenance.py | ManagementService._delivery | candidate_stop |

## Blockers


## Delivery backlog


## Static connection checks

| Profile | Bounded checks | Scope |
| --- | --- | --- |
| d2_fallback | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| d4_delegation | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| d4_mutation_graph | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| m1_reads | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| m1_backlog | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| m2_preparation | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| m3_task_actions | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| m4_quality_evidence | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| m5_parallel_candidates | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| m6_feature_distribution | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| d1_backend | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| d4_transport | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_adapter | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_agent_session | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_approval | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_candidate | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_completion | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_context | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_daemon | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_discovery | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_doctor | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_document | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_events | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_execution | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_journal | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_lineage | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_output | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_proof | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_reentry | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_research | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_role | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_runtime_profile | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_session_binding | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_work | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.dispatch.golem_cli_workflow | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_edge.golem_cli_workflow.golem_cli_workflow_template | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_closure.events | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| source_role.src/common/record_internal.h | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| source_role.src/cli/internal.h | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| source_role.src/cli/output.h | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| source_role.tools/integration_contract.py | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| source_role.tools/integration_transfer.py | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| source_role.tools/integration_backend.py | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| source_role.tools/integration_mutations.py | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| source_role.tools/integration_mutation_mcp.py | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_agent_session_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_agent_request_validate | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_agent_session_resume_context | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_approval_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_approval_request_validate | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_completion_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_completion_validate | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_execution_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_execution_call_authorized | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_execution_call_receipted | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_approval_describe | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_role_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_role_request_validate | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_reentry_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_reentry_validate | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_session_binding_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_session_binding_request_validate | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_research_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_research_validate | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_candidate_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_workspace_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| domain.golem_binding_call | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| c_graph | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| native_operation_surfaces | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| whole_file_surfaces | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| reviewed_effects | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| boundary_contracts | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
| private_publication_guard | CONFIRMED | Static structure only; no policy satisfaction or execution proof |
