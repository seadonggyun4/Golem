add_executable(golem_context_api_helper context_api_helper.c)
add_executable(golem_inventory_helper inventory_helper.c)
target_link_libraries(golem_inventory_helper PRIVATE Golem::golem PkgConfig::JSONC)
golem_configure_target(golem_inventory_helper)
add_executable(golem_test_inventory test_inventory.c)
target_link_libraries(golem_test_inventory PRIVATE Golem::golem PkgConfig::JSONC)
golem_configure_target(golem_test_inventory)
add_test(NAME change_inventory_unit COMMAND golem_test_inventory)
add_executable(golem_workspace_helper workspace_helper.c)
target_link_libraries(golem_workspace_helper PRIVATE Golem::golem)
golem_configure_target(golem_workspace_helper)
add_executable(golem_test_runtime_events test_runtime_events.c)
target_link_libraries(golem_test_runtime_events PRIVATE Golem::golem)
golem_configure_target(golem_test_runtime_events)
foreach(case ring codec durable worker)
    add_test(NAME runtime_events_${case} COMMAND golem_test_runtime_events ${case})
    set_tests_properties(runtime_events_${case} PROPERTIES TIMEOUT 60)
endforeach()
target_link_libraries(golem_context_api_helper PRIVATE Golem::golem)
golem_configure_target(golem_context_api_helper)
add_executable(golem_test_research test_research.c)
target_link_libraries(golem_test_research PRIVATE Golem::golem)
golem_configure_target(golem_test_research)
add_test(NAME research_api COMMAND golem_test_research ${CMAKE_CURRENT_BINARY_DIR})
set_tests_properties(research_api PROPERTIES TIMEOUT 30)

add_executable(golem_test_completion test_completion.c)
add_executable(golem_test_role_contract test_role_contract.c)
target_link_libraries(golem_test_role_contract PRIVATE Golem::golem PkgConfig::JSONC)
golem_configure_target(golem_test_role_contract)
add_test(NAME role_contract_api COMMAND golem_test_role_contract)
add_executable(golem_test_completion_version test_completion_version.c)
target_link_libraries(golem_test_completion_version PRIVATE Golem::golem PkgConfig::JSONC)
golem_configure_target(golem_test_completion_version)
add_test(NAME completion_version_allocator COMMAND golem_test_completion_version)
target_link_libraries(golem_test_completion PRIVATE Golem::golem)
golem_configure_target(golem_test_completion)
add_test(NAME completion_api COMMAND golem_test_completion)
set_tests_properties(completion_api PROPERTIES TIMEOUT 30)
add_executable(golem_test_reentry test_reentry.c)
target_link_libraries(golem_test_reentry PRIVATE Golem::golem)
golem_configure_target(golem_test_reentry)
add_test(NAME reentry_api COMMAND golem_test_reentry)
set_tests_properties(reentry_api PROPERTIES TIMEOUT 30)

add_executable(golem_test_execution test_execution.c)
target_link_libraries(golem_test_execution PRIVATE Golem::golem)
golem_configure_target(golem_test_execution)
add_test(NAME execution_api COMMAND golem_test_execution)
add_executable(golem_test_execution_logs test_execution_logs.c)
target_link_libraries(golem_test_execution_logs PRIVATE Golem::golem PkgConfig::JSONC)
golem_configure_target(golem_test_execution_logs)
add_test(NAME execution_logs COMMAND golem_test_execution_logs)
add_executable(golem_test_proof_publication test_proof_publication.c)
target_link_libraries(golem_test_proof_publication PRIVATE Golem::golem PkgConfig::JSONC OpenSSL::Crypto)
golem_configure_target(golem_test_proof_publication)
add_test(NAME proof_publication_faults COMMAND golem_test_proof_publication)
add_executable(golem_test_supervisor_stream test_supervisor_stream.c)
target_link_libraries(golem_test_supervisor_stream PRIVATE Golem::golem)
golem_configure_target(golem_test_supervisor_stream)
add_test(NAME supervisor_stream COMMAND golem_test_supervisor_stream)
set_tests_properties(execution_api PROPERTIES TIMEOUT 30)

add_executable(golem_test_runtime_profile test_runtime_profile.c)
add_executable(golem_test_json_contract test_json_contract.c)
target_link_libraries(golem_test_json_contract PRIVATE Golem::golem PkgConfig::JSONC)
golem_configure_target(golem_test_json_contract)
add_test(NAME json_contract COMMAND golem_test_json_contract)
set_tests_properties(json_contract PROPERTIES TIMEOUT 30 LABELS "hardening")
add_executable(golem_test_admission test_admission.c)
add_executable(golem_test_admission_open test_admission_open.c)
target_link_libraries(golem_test_admission_open PRIVATE Golem::golem OpenSSL::Crypto PkgConfig::JSONC)
golem_configure_target(golem_test_admission_open)
add_test(NAME admission_open_diagnostics COMMAND golem_test_admission_open)
set_tests_properties(admission_open_diagnostics PROPERTIES LABELS "restricted-diagnostic" TIMEOUT 30)
add_executable(golem_test_admission_contract test_admission_contract.c)
target_link_libraries(golem_test_admission_contract PRIVATE Golem::golem)
golem_configure_target(golem_test_admission_contract)
add_test(NAME admission_contract COMMAND golem_test_admission_contract)
set_tests_properties(admission_contract PROPERTIES TIMEOUT 30 LABELS "hardening;admission")
add_executable(golem_test_admission_faults test_admission_faults.c)
target_link_libraries(golem_test_admission_faults PRIVATE Golem::golem OpenSSL::Crypto)
golem_configure_target(golem_test_admission_faults)
add_test(NAME admission_faults COMMAND golem_test_admission_faults)
set_tests_properties(admission_faults PROPERTIES TIMEOUT 30)
add_executable(golem_admission_work_helper admission_work_helper.c)
add_executable(golem_test_resource test_resource.c)
target_link_libraries(golem_test_resource PRIVATE Golem::golem)
golem_configure_target(golem_test_resource)
add_test(NAME resource_api COMMAND golem_test_resource)
target_link_libraries(golem_admission_work_helper PRIVATE Golem::golem)
golem_configure_target(golem_admission_work_helper)
target_link_libraries(golem_test_admission PRIVATE Golem::golem)
golem_configure_target(golem_test_admission)
foreach(case basic fairness nested capacity explore recovery identity corruption ownership guards)
    add_test(NAME admission_${case} COMMAND golem_test_admission ${case})
    set_tests_properties(admission_${case} PROPERTIES TIMEOUT 60)
endforeach()
add_executable(golem_test_descriptor test_descriptor.c)
target_link_libraries(golem_test_descriptor PRIVATE Golem::golem)
golem_configure_target(golem_test_descriptor)
foreach(case codec invalid compatibility current)
    add_test(NAME adapter_descriptor_${case} COMMAND golem_test_descriptor ${case})
    set_tests_properties(adapter_descriptor_${case} PROPERTIES TIMEOUT 30)
endforeach()
add_executable(golem_descriptor_probe_helper descriptor_probe_helper.c)
target_link_libraries(golem_descriptor_probe_helper PRIVATE Golem::golem)
golem_configure_target(golem_descriptor_probe_helper)
target_link_libraries(golem_test_runtime_profile PRIVATE Golem::golem PkgConfig::JSONC)
golem_configure_target(golem_test_runtime_profile)
foreach(case codec invalid cache ownership prepared)
    add_test(NAME runtime_profile_${case} COMMAND golem_test_runtime_profile ${case})
    set_tests_properties(runtime_profile_${case} PROPERTIES TIMEOUT 30)
endforeach()

add_executable(golem_test_agent_session test_agent_session.c)
target_link_libraries(golem_test_agent_session PRIVATE Golem::golem)
golem_configure_target(golem_test_agent_session)
add_test(NAME agent_session_api COMMAND golem_test_agent_session)
add_executable(golem_test_session_binding test_session_binding.c)
target_link_libraries(golem_test_session_binding PRIVATE Golem::golem)
golem_configure_target(golem_test_session_binding)
add_test(NAME session_binding_api COMMAND golem_test_session_binding)
add_executable(golem_test_approval test_approval.c)
target_link_libraries(golem_test_approval PRIVATE Golem::golem)
golem_configure_target(golem_test_approval)
add_test(NAME approval_api COMMAND golem_test_approval)
add_executable(golem_test_event_reader test_event_reader.c)
target_link_libraries(golem_test_event_reader PRIVATE Golem::golem)
golem_configure_target(golem_test_event_reader)
add_test(NAME event_reader_api COMMAND golem_test_event_reader)
set_tests_properties(event_reader_api PROPERTIES TIMEOUT 30 LABELS "observation")
add_executable(golem_test_event_backpressure test_event_backpressure.c)
target_link_libraries(golem_test_event_backpressure PRIVATE Golem::golem)
golem_configure_target(golem_test_event_backpressure)
add_test(NAME event_bridge_backpressure COMMAND golem_test_event_backpressure)
set_tests_properties(event_bridge_backpressure PROPERTIES TIMEOUT 30 LABELS "observation")
if(GOLEM_BUILD_EVENT_BRIDGE)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME event_bridge_http COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/event_bridge_integration.py
        $<TARGET_FILE:golem_event_bridge> $<TARGET_FILE:golem_test_runtime_events>)
    set_tests_properties(event_bridge_http PROPERTIES TIMEOUT 120 LABELS "observation;http")
endif()
set_tests_properties(approval_api PROPERTIES TIMEOUT 30 LABELS "approval")
set_tests_properties(agent_session_api PROPERTIES TIMEOUT 30)

add_executable(golem_test_workflow test_workflow.c)
target_link_libraries(golem_test_workflow PRIVATE Golem::golem)
golem_configure_target(golem_test_workflow)
add_test(NAME workflow_api COMMAND golem_test_workflow)
set_tests_properties(workflow_api PROPERTIES TIMEOUT 30)

add_executable(golem_test_discovery test_discovery.c)
target_link_libraries(golem_test_discovery PRIVATE Golem::golem)
target_compile_definitions(golem_test_discovery PRIVATE
    GOLEM_DISCOVERY_SAMPLE="${PROJECT_SOURCE_DIR}/samples/discovery/assessment.json")
golem_configure_target(golem_test_discovery)
add_test(NAME discovery_api COMMAND golem_test_discovery)
set_tests_properties(discovery_api PROPERTIES TIMEOUT 15)

add_executable(golem_test_document test_document.c)
target_link_libraries(golem_test_document PRIVATE Golem::golem)
target_compile_definitions(golem_test_document PRIVATE
    GOLEM_DOCUMENT_SAMPLES="${PROJECT_SOURCE_DIR}/samples/documents")
golem_configure_target(golem_test_document)
add_test(NAME document_api COMMAND golem_test_document ${CMAKE_CURRENT_BINARY_DIR})
set_tests_properties(document_api PROPERTIES TIMEOUT 60)

add_executable(golem_test_policy_artifact test_policy_artifact.c)
target_link_libraries(golem_test_policy_artifact PRIVATE Golem::golem)
golem_configure_target(golem_test_policy_artifact)
add_test(NAME policy_artifact COMMAND golem_test_policy_artifact)
set_tests_properties(policy_artifact PROPERTIES TIMEOUT 15 LABELS hardening)

add_executable(golem_test_daemon test_daemon.c)
target_link_libraries(golem_test_daemon PRIVATE Golem::golem)
golem_configure_target(golem_test_daemon)
foreach(case lifecycle retry limits uncertain policy corruption recovery invalid)
    add_test(NAME daemon_${case} COMMAND golem_test_daemon ${case} ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(daemon_${case} PROPERTIES TIMEOUT 60)
endforeach()
add_executable(golem_test_supervisor test_supervisor.c)
add_executable(golem_test_worker test_worker.c)
add_executable(golem_test_worker_faults test_worker_faults.c)
target_link_libraries(golem_test_worker_faults PRIVATE Golem::golem Threads::Threads)
golem_configure_target(golem_test_worker_faults)
foreach(case thread reap)
    add_test(NAME worker_fault_${case} COMMAND golem_test_worker_faults ${case})
    set_tests_properties(worker_fault_${case} PROPERTIES TIMEOUT 30)
endforeach()
target_link_libraries(golem_test_worker PRIVATE Golem::golem)
golem_configure_target(golem_test_worker)
foreach(case limits overlap reserve echo exit signal overflow lease timeout missing cancel recovery)
    add_test(NAME worker_${case} COMMAND golem_test_worker ${case})
    set_tests_properties(worker_${case} PROPERTIES TIMEOUT 30)
endforeach()
add_executable(golem_test_supervisor_input_close test_supervisor_input_close.c)
target_link_libraries(golem_test_supervisor_input_close PRIVATE Golem::golem)
golem_configure_target(golem_test_supervisor_input_close)
foreach(error pipe reset io)
    foreach(outcome exit signal success hang)
        add_test(NAME supervisor_input_${error}_${outcome}
            COMMAND golem_test_supervisor_input_close ${error} ${outcome})
        set_tests_properties(supervisor_input_${error}_${outcome} PROPERTIES TIMEOUT 15)
    endforeach()
endforeach()

add_executable(golem_test_supervisor_exit_race test_supervisor_exit_race.c)
target_link_libraries(golem_test_supervisor_exit_race PRIVATE Golem::golem)
golem_configure_target(golem_test_supervisor_exit_race)
foreach(case late-eof late-reap-eof held-pipe denied)
    add_test(NAME supervisor_exit_${case} COMMAND golem_test_supervisor_exit_race ${case})
    set_tests_properties(supervisor_exit_${case} PROPERTIES TIMEOUT 15)
endforeach()
target_link_libraries(golem_test_supervisor PRIVATE Golem::golem)
golem_configure_target(golem_test_supervisor)
foreach(case echo exit signal hang overflow stderr cancel)
    add_test(NAME supervisor_${case} COMMAND golem_test_supervisor ${case})
    set_tests_properties(supervisor_${case} PROPERTIES TIMEOUT 15)
endforeach()

add_executable(golem_test_lease test_lease.c)
target_link_libraries(golem_test_lease PRIVATE Golem::golem)
golem_configure_target(golem_test_lease)
foreach(case lifecycle identity invalid runtime ownership)
    add_test(NAME lease_${case} COMMAND golem_test_lease ${case})
    set_tests_properties(lease_${case} PROPERTIES TIMEOUT 30)
endforeach()

add_executable(golem_test_runtime_adapter test_runtime_adapter.c)
target_link_libraries(golem_test_runtime_adapter PRIVATE Golem::golem)
golem_configure_target(golem_test_runtime_adapter)
add_test(NAME runtime_adapter COMMAND golem_test_runtime_adapter)
set_tests_properties(runtime_adapter PROPERTIES TIMEOUT 60)

add_executable(golem_test_runtime test_runtime.c)
target_link_libraries(golem_test_runtime PRIVATE Golem::golem)
golem_configure_target(golem_test_runtime)
foreach(case matrix limits policy timeout failures overrides cancel ownership)
    add_test(NAME runtime_${case} COMMAND golem_test_runtime ${case})
    set_tests_properties(runtime_${case} PROPERTIES TIMEOUT 30)
endforeach()

add_executable(golem_test_common test_common.c)
target_link_libraries(golem_test_common PRIVATE Golem::golem)
golem_configure_target(golem_test_common)
add_test(NAME common COMMAND golem_test_common)
set_tests_properties(common PROPERTIES TIMEOUT 15)

add_executable(golem_test_core test_core.c)
target_link_libraries(golem_test_core PRIVATE Golem::golem)
golem_configure_target(golem_test_core)
foreach(case graph transitions capsule lifecycle reentry policy_cancel overrides nulls)
    add_test(NAME core_${case} COMMAND golem_test_core ${case})
    set_tests_properties(core_${case} PROPERTIES TIMEOUT 30)
endforeach()

add_executable(golem_test_memory test_memory.c)
target_link_libraries(golem_test_memory PRIVATE Golem::golem)
golem_configure_target(golem_test_memory)
foreach(case allocator arena spans diagnostics core_oom)
    add_test(NAME memory_${case} COMMAND golem_test_memory ${case})
    set_tests_properties(memory_${case} PROPERTIES TIMEOUT 30)
endforeach()

add_executable(golem_test_journal test_journal.c)
add_executable(golem_test_checkpoint test_journal_checkpoint.c)
target_link_libraries(golem_test_checkpoint PRIVATE Golem::golem)
target_compile_definitions(golem_test_checkpoint PRIVATE
    GOLEM_JOURNAL_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures/journal")
golem_configure_target(golem_test_checkpoint)
add_test(NAME journal_checkpoint COMMAND golem_test_checkpoint)
add_executable(golem_test_journal_faults test_journal_faults.c)
target_link_libraries(golem_test_journal_faults PRIVATE Golem::golem)
golem_configure_target(golem_test_journal_faults)
add_test(NAME journal_syscall_faults COMMAND golem_test_journal_faults)
add_executable(golem_test_recovery_publication test_recovery_publication.c
    ${PROJECT_SOURCE_DIR}/src/cli/json.c)
target_link_libraries(golem_test_recovery_publication PRIVATE Golem::golem PkgConfig::JSONC OpenSSL::Crypto)
golem_configure_target(golem_test_recovery_publication)
add_test(NAME recovery_publication_faults COMMAND golem_test_recovery_publication)
target_link_libraries(golem_test_journal PRIVATE Golem::golem)
target_compile_definitions(golem_test_journal PRIVATE
    GOLEM_JOURNAL_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures/journal")
golem_configure_target(golem_test_journal)
foreach(case codec replay corruption semantics lifecycle file oom)
    add_test(NAME journal_${case} COMMAND golem_test_journal ${case})
    set_tests_properties(journal_${case} PROPERTIES TIMEOUT 60)
endforeach()

add_executable(golem_test_replay test_replay.c)
target_link_libraries(golem_test_replay PRIVATE Golem::golem)
target_compile_definitions(golem_test_replay PRIVATE
    GOLEM_JOURNAL_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures/journal")
golem_configure_target(golem_test_replay)
foreach(case chunks missing failure_state reports oom crash recover_failure bounded)
    add_test(NAME replay_${case} COMMAND golem_test_replay ${case})
    set_tests_properties(replay_${case} PROPERTIES TIMEOUT 60)
endforeach()

add_executable(golem_test_evidence test_evidence.c)
target_link_libraries(golem_test_evidence PRIVATE Golem::golem)
golem_configure_target(golem_test_evidence)
foreach(case digest receipt roundtrip file corruption paths ownership concurrent io_failure)
    add_test(NAME evidence_${case} COMMAND golem_test_evidence ${case})
    set_tests_properties(evidence_${case} PROPERTIES TIMEOUT 60)
endforeach()
if(GOLEM_BUILD_CLI)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME doctor_environment COMMAND ${Python3_EXECUTABLE}
        ${PROJECT_SOURCE_DIR}/tools/doctor_environment.py --binary $<TARGET_FILE:golem_cli>
        --root ${CMAKE_CURRENT_BINARY_DIR} --profile full-ci)
    add_test(NAME doctor_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/doctor_integration.py $<TARGET_FILE:golem_cli>)
    add_test(NAME restricted_diagnostics COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/restricted_diagnostics.py $<TARGET_FILE:golem_cli>)
    add_test(NAME diagnostic_tools COMMAND ${Python3_EXECUTABLE} -m unittest
        test_doctor_environment test_classify_failures test_verify_environment)
    set_tests_properties(diagnostic_tools PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}/tools")
    set_tests_properties(restricted_diagnostics diagnostic_tools
        PROPERTIES LABELS "restricted-diagnostic" TIMEOUT 120)
    add_test(NAME golden_workflow COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/golden_workflow.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    # Six real compiler/session workflows; retain per-command deadlines as well.
    set_tests_properties(golden_workflow PROPERTIES TIMEOUT 900)
    add_test(NAME change_inventory_integration COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/inventory_integration.py $<TARGET_FILE:golem_inventory_helper>)
    set_tests_properties(change_inventory_integration PROPERTIES TIMEOUT 240)
    add_test(NAME execution_change_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/execution_change_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(execution_change_cli PROPERTIES TIMEOUT 240)
    add_test(NAME execution_change_large_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/execution_change_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER}
        Changes.test_large_v5_qa_markdown_completion_and_staleness)
    set_tests_properties(execution_change_large_cli PROPERTIES TIMEOUT 240)
    add_test(NAME candidate_cli_host COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/candidate_cli_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(candidate_cli_host PROPERTIES TIMEOUT 240)
    add_test(NAME workspace_lifecycle COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/workspace_integration.py $<TARGET_FILE:golem_cli>
        $<TARGET_FILE:golem_workspace_helper> ${PROJECT_SOURCE_DIR})
    set_tests_properties(workspace_lifecycle PROPERTIES TIMEOUT 240)
    add_test(NAME runtime_validation_report COMMAND ${Python3_EXECUTABLE} -m unittest
        discover -s ${PROJECT_SOURCE_DIR}/tools -p test_verify_runtime.py)
    set_tests_properties(runtime_validation_report PROPERTIES TIMEOUT 30 LABELS runtime-contract)
    add_test(NAME orchestration_validation_report COMMAND ${Python3_EXECUTABLE} -m unittest
        discover -s ${PROJECT_SOURCE_DIR}/tools -p test_verify_orchestration.py)
    set_tests_properties(orchestration_validation_report PROPERTIES TIMEOUT 30 LABELS orchestration)
    add_test(NAME isolation_validation_report COMMAND ${Python3_EXECUTABLE} -m unittest
        discover -s ${PROJECT_SOURCE_DIR}/tools -p test_verify_isolation.py)
    set_tests_properties(isolation_validation_report PROPERTIES TIMEOUT 30 LABELS "runtime-contract;isolation")
    add_test(NAME runtime_canary COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/runtime_canary.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(runtime_canary PROPERTIES TIMEOUT 300 LABELS "runtime-contract;fixture")
    add_test(NAME adapter_descriptor_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/descriptor_integration.py $<TARGET_FILE:golem_cli>
        $<TARGET_FILE:golem_descriptor_probe_helper>)
    set_tests_properties(adapter_descriptor_cli PROPERTIES TIMEOUT 120)
    add_test(NAME admission_work_integration COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/admission_integration.py $<TARGET_FILE:golem_admission_work_helper>
        $<TARGET_FILE:golem_cli> ${PROJECT_SOURCE_DIR} $<TARGET_FILE:golem_agent_client>)
    set_tests_properties(admission_work_integration PROPERTIES TIMEOUT 120)
    add_test(NAME journal_inspect_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/journal_inspect_integration.py $<TARGET_FILE:golem_cli>)
    set_tests_properties(journal_inspect_cli PROPERTIES TIMEOUT 60)
    add_executable(golem_agent_client agent_client.c)
    target_link_libraries(golem_agent_client PRIVATE Golem::golem)
    golem_configure_target(golem_agent_client)
    add_test(NAME agent_session_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/session_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} $<TARGET_FILE:golem_agent_client>)
    set_tests_properties(agent_session_cli PROPERTIES TIMEOUT 240)
    add_executable(golem_binding_client binding_client.c)
    target_link_libraries(golem_binding_client PRIVATE Golem::golem)
    golem_configure_target(golem_binding_client)
    add_test(NAME session_binding_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/binding_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} $<TARGET_FILE:golem_agent_client> $<TARGET_FILE:golem_binding_client>)
    set_tests_properties(session_binding_cli PROPERTIES TIMEOUT 360 LABELS "binding;session")
    add_executable(golem_approval_client approval_client.c)
    target_link_libraries(golem_approval_client PRIVATE Golem::golem)
    golem_configure_target(golem_approval_client)
    add_test(NAME approval_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/approval_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} $<TARGET_FILE:golem_approval_client>)
    set_tests_properties(approval_cli PROPERTIES TIMEOUT 360 LABELS "approval;execution")
    add_test(NAME runtime_profile_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/profile_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} $<TARGET_FILE:golem_agent_client>)
    set_tests_properties(runtime_profile_cli PROPERTIES TIMEOUT 240)
    add_test(NAME execution_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/execution_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(execution_cli PROPERTIES TIMEOUT 240)
    add_test(NAME execution_bundle_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/execution_bundle_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(execution_bundle_cli PROPERTIES TIMEOUT 240)
    add_test(NAME proof_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/proof_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(proof_cli PROPERTIES TIMEOUT 240)
    add_test(NAME execution_boundary_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/execution_boundary_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(execution_boundary_cli PROPERTIES TIMEOUT 240)
    add_test(NAME execution_inventory COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/execution_inventory.py ${PROJECT_SOURCE_DIR})
    add_test(NAME research_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/research_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(research_cli PROPERTIES TIMEOUT 180)
    add_test(NAME outcome_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/outcome_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} -v)
    set_tests_properties(outcome_cli PROPERTIES TIMEOUT 300)
    add_test(NAME research_metrics_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/metrics_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(research_metrics_cli PROPERTIES TIMEOUT 180)
    add_test(NAME research_cohort_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/cohort_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(research_cohort_cli PROPERTIES TIMEOUT 180)
    add_test(NAME research_bundle_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/bundle_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(research_bundle_cli PROPERTIES TIMEOUT 180)
    add_test(NAME research_observability_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/observability_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(research_observability_cli PROPERTIES TIMEOUT 180)
    add_test(NAME outcome_bundle_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/outcome_bundle_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} -v)
    set_tests_properties(outcome_bundle_cli PROPERTIES TIMEOUT 180)
    add_test(NAME outcome_metrics_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/outcome_metrics_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} -v)
    set_tests_properties(outcome_metrics_cli PROPERTIES TIMEOUT 300)
    add_test(NAME reentry_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/reentry_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(reentry_cli PROPERTIES TIMEOUT 360)
    add_test(NAME completion_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/completion_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} -v)
    set_tests_properties(completion_cli PROPERTIES TIMEOUT 900)
    add_test(NAME role_contract_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/role_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} -v)
    set_tests_properties(role_contract_cli PROPERTIES TIMEOUT 600 LABELS "roles;completion")
    add_test(NAME completion_historical_store COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/completion_history.py $<TARGET_FILE:golem_cli>
        $<TARGET_FILE:golem_test_completion_version>)
    set_tests_properties(completion_historical_store PROPERTIES TIMEOUT 90)
    add_test(NAME agent_conformance_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/conformance_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(agent_conformance_cli PROPERTIES TIMEOUT 900 LABELS "conformance;fixture")
    add_test(NAME document_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/document_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR}/samples/documents ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(document_cli PROPERTIES TIMEOUT 180)
    add_test(NAME discovery_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/discovery_integration.py $<TARGET_FILE:golem_cli> ${PROJECT_SOURCE_DIR})
    set_tests_properties(discovery_cli PROPERTIES TIMEOUT 180)
    add_test(NAME context_projection_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/context_integration.py $<TARGET_FILE:golem_cli> ${PROJECT_SOURCE_DIR})
    set_tests_properties(context_projection_cli PROPERTIES TIMEOUT 180)
    add_test(NAME runtime_events_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/events_integration.py $<TARGET_FILE:golem_cli> $<TARGET_FILE:golem_test_runtime_events>)
    set_tests_properties(runtime_events_cli PROPERTIES TIMEOUT 60)
    add_test(NAME workflow_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/workflow_integration.py $<TARGET_FILE:golem_cli> ${PROJECT_SOURCE_DIR})
    set_tests_properties(workflow_cli PROPERTIES TIMEOUT 180)
    add_test(NAME workflow_template_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/workflow_template_integration.py $<TARGET_FILE:golem_cli> ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER})
    set_tests_properties(workflow_template_cli PROPERTIES TIMEOUT 180)
    add_test(NAME orchestration_integration COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/orchestration_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} -v)
    set_tests_properties(orchestration_integration PROPERTIES TIMEOUT 240 LABELS "orchestration;fixture")
    add_executable(golem_crash_runner crash_runner.c)
    target_link_libraries(golem_crash_runner PRIVATE Golem::golem OpenSSL::Crypto)
    golem_configure_target(golem_crash_runner)
    add_executable(golem_recovery_runner recovery_runner.c)
    target_link_libraries(golem_recovery_runner PRIVATE Golem::golem OpenSSL::Crypto)
    golem_configure_target(golem_recovery_runner)
    foreach(case before-start start-intent started claim execute finish-intent finished prefixes
            conflict missing-intent corrupt-intent missing-tail-intent metadata legacy symlink locks claim-retained recrash
            missing-journal invalid-transition publication unpublished)
        add_test(NAME crash_${case} COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/crash_integration.py $<TARGET_FILE:golem_cli>
            $<TARGET_FILE:golem_crash_runner> ${CMAKE_CURRENT_BINARY_DIR} ${case} $<TARGET_FILE:golem_recovery_runner>)
        set_tests_properties(crash_${case} PROPERTIES TIMEOUT 90)
    endforeach()
    add_test(NAME daemon_cli COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/daemon_integration.py $<TARGET_FILE:golem_cli> ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(daemon_cli PROPERTIES TIMEOUT 120)
    add_test(NAME cli_integration COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/cli_integration.py $<TARGET_FILE:golem_cli> ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(cli_integration PROPERTIES TIMEOUT 120)
    add_test(NAME evidence_cli COMMAND ${CMAKE_COMMAND}
        -DCLI=$<TARGET_FILE:golem_cli> -DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}
        -P ${CMAKE_CURRENT_SOURCE_DIR}/evidence_cli.cmake)
    set_tests_properties(evidence_cli PROPERTIES TIMEOUT 60)
endif()

add_executable(golem_test_lineage test_lineage.c)
target_link_libraries(golem_test_lineage PRIVATE Golem::golem)
golem_configure_target(golem_test_lineage)
foreach(case lifecycle reentry invalid codec ownership capacity storage bounded identity nulls)
    add_test(NAME lineage_${case} COMMAND golem_test_lineage ${case})
    set_tests_properties(lineage_${case} PROPERTIES TIMEOUT 60)
endforeach()
if(GOLEM_BUILD_CLI)
    add_test(NAME lineage_cli COMMAND ${CMAKE_COMMAND}
        -DCLI=$<TARGET_FILE:golem_cli> -DFIXTURE=$<TARGET_FILE:golem_test_lineage>
        -DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR} -P ${CMAKE_CURRENT_SOURCE_DIR}/lineage_cli.cmake)
    set_tests_properties(lineage_cli PROPERTIES TIMEOUT 90)
endif()

add_executable(golem_test_policy test_policy.c)
target_link_libraries(golem_test_policy PRIVATE Golem::golem)
golem_configure_target(golem_test_policy)
foreach(case matrix gates immutable scope replay ownership invalid)
    add_test(NAME policy_${case} COMMAND golem_test_policy ${case})
    set_tests_properties(policy_${case} PROPERTIES TIMEOUT 60)
endforeach()

add_executable(golem_test_cost test_cost.c)
target_link_libraries(golem_test_cost PRIVATE Golem::golem)
golem_configure_target(golem_test_cost)
foreach(case arithmetic lifecycle retry budget reports capacity aggregate ownership invalid)
    add_test(NAME cost_${case} COMMAND golem_test_cost ${case})
    set_tests_properties(cost_${case} PROPERTIES TIMEOUT 60)
endforeach()

add_executable(golem_test_optimization test_optimization.c)
target_link_libraries(golem_test_optimization PRIVATE Golem::golem)
golem_configure_target(golem_test_optimization)
foreach(case cache selection noop gates scope fallback atomic ownership invalid failure_barrier)
    add_test(NAME optimization_${case} COMMAND golem_test_optimization ${case})
    set_tests_properties(optimization_${case} PROPERTIES TIMEOUT 60)
endforeach()

add_executable(golem_test_adapter test_adapter.c)
target_link_libraries(golem_test_adapter PRIVATE Golem::golem)
golem_configure_target(golem_test_adapter)
foreach(case lifecycle codec gates failures replay invalid optimized mutations guarded)
    add_test(NAME adapter_${case} COMMAND golem_test_adapter ${case})
    set_tests_properties(adapter_${case} PROPERTIES TIMEOUT 60)
endforeach()
if(GOLEM_BUILD_CLI)
    add_test(NAME adapter_cli COMMAND ${CMAKE_COMMAND}
        -DCLI=$<TARGET_FILE:golem_cli> -DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}
        -P ${CMAKE_CURRENT_SOURCE_DIR}/adapter_cli.cmake)
    set_tests_properties(adapter_cli PROPERTIES TIMEOUT 60)
endif()

add_executable(golem_test_wire test_wire.c)
target_link_libraries(golem_test_wire PRIVATE Golem::golem)
golem_configure_target(golem_test_wire)
foreach(case roundtrip limits buffers malformed wide gateway mutations)
    add_test(NAME wire_${case} COMMAND golem_test_wire ${case})
    set_tests_properties(wire_${case} PROPERTIES TIMEOUT 60)
endforeach()

add_executable(golem_test_candidate test_candidate.c)
target_link_libraries(golem_test_candidate PRIVATE Golem::golem PkgConfig::JSONC)
golem_configure_target(golem_test_candidate)
add_test(NAME candidate_model COMMAND golem_test_candidate ${PROJECT_SOURCE_DIR}/samples/candidates/group.json)
if(GOLEM_BUILD_CLI)
    add_executable(golem_candidate_host_helper candidate_host_helper.c)
    target_link_libraries(golem_candidate_host_helper PRIVATE Golem::golem PkgConfig::JSONC)
    golem_configure_target(golem_candidate_host_helper)
    add_test(NAME candidate_integration COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/candidate_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} $<TARGET_FILE:golem_candidate_host_helper>)
    set_tests_properties(candidate_integration PROPERTIES TIMEOUT 240)
    add_test(NAME candidate_diff_integration COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/candidate_diff_integration.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} $<TARGET_FILE:golem_candidate_host_helper>)
    set_tests_properties(candidate_diff_integration PROPERTIES TIMEOUT 180)
    add_test(NAME orchestration_benchmark COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/orchestration_benchmark.py $<TARGET_FILE:golem_cli>
        ${PROJECT_SOURCE_DIR} ${CMAKE_C_COMPILER} $<TARGET_FILE:golem_candidate_host_helper>
        $<TARGET_FILE:golem_test_runtime_events> ${CMAKE_CURRENT_BINARY_DIR})
    set_tests_properties(orchestration_benchmark PROPERTIES TIMEOUT 240 LABELS "orchestration;benchmark;fixture")
endif()

# Compile every installed header alone and twice: self-containment and guards.
file(GLOB public_headers CONFIGURE_DEPENDS "${PROJECT_SOURCE_DIR}/include/golem/*.h")
foreach(header IN LISTS public_headers)
    get_filename_component(stem "${header}" NAME_WE)
    file(GENERATE OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/header_${stem}.c"
        CONTENT "#include \"golem/${stem}.h\"\n#include \"golem/${stem}.h\"\nint main(void) { return 0; }\n")
    add_executable(golem_header_${stem} "${CMAKE_CURRENT_BINARY_DIR}/header_${stem}.c")
    target_link_libraries(golem_header_${stem} PRIVATE Golem::golem)
    golem_configure_target(golem_header_${stem})
    add_test(NAME header_${stem} COMMAND golem_header_${stem})
    set_tests_properties(header_${stem} PROPERTIES TIMEOUT 15)
endforeach()
