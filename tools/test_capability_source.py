import unittest
from pathlib import Path

from capability_source import (ExtractionError, c_comparison_values,
                               observation_difference, python_literal_names)


class SourceObservations(unittest.TestCase):
    def test_c_literals_comments_reversal_and_nested_subject(self):
        source = '''
          // strcmp(op, "fake_line")
          /* strcmp(op, "fake_block") */
          const char *s = "strcmp(op, fake_string)";
          if (!strcmp(op, "claim")) {}
          if (strcmp("sta" "tus", op) == 0) {}
          if (!strcmp(dw_text(r, "operation"), "finalize")) {}
          if (strcmp(other, "not_this_subject")) {}
        '''
        self.assertEqual(c_comparison_values(source, 'op'), ('claim', 'status'))
        self.assertEqual(c_comparison_values(source, 'dw_text(r,"operation")'), ('finalize',))

    def test_c_whitespace_and_escaped_quotes_do_not_create_calls(self):
        source = 'char *s="escaped \\" strcmp(op, fake)"; strcmp(argv [ 2 ], "start");'
        self.assertEqual(c_comparison_values(source, 'argv[2]'), ('start',))

    def test_duplicate_branch_is_one_lexical_name(self):
        self.assertEqual(c_comparison_values('strcmp(op,"status"); strcmp(op,"status");', 'op'), ('status',))

    def test_preprocessor_branches_are_not_runtime_profile(self):
        self.assertEqual(c_comparison_values('#if 0\nstrcmp(op,"disabled");\n#endif', 'op'), ('disabled',))

    def test_c_unsupported_shapes_block_without_partial_result(self):
        for tail in ('strcmp(op, NAME);', 'strncmp(op,"next",4);', 'strcmp(op, u8"next");',
                     'strcmp(op,"\\x6eext");', 'strcmp(op,"bad name");', 'strcmp(op,"next";',
                     '/* missing end', '"missing end'):
            with self.subTest(tail=tail), self.assertRaises(ExtractionError):
                c_comparison_values('strcmp(op,"status");'+tail, 'op')

    def test_python_does_not_import_or_evaluate_values(self):
        source = 'raise RuntimeError("must not execute")\nSCHEMAS={"status": arbitrary(), "next": missing.value}'
        self.assertEqual(python_literal_names(source, 'SCHEMAS', mapping=True), ('next', 'status'))

    def test_python_tuple_and_annotation(self):
        self.assertEqual(python_literal_names('NAMES: tuple = ("resume", "begin")', 'NAMES', mapping=False), ('begin', 'resume'))

    def test_python_ambiguous_or_computed_declarations_block(self):
        for source in ('NAMES=("next", "next")', 'NAMES=other', 'NAMES=(name,)',
                       'NAMES=("bad-name",)', 'NAMES=("next",)\nNAMES=("status",)', 'NAMES=(',
                       'OTHER=("next",)'):
            with self.subTest(source=source), self.assertRaises(ExtractionError):
                python_literal_names(source, 'NAMES', mapping=False)
        for source in ('SCHEMAS={**other}', 'SCHEMAS={name: value}',
                       'SCHEMAS={"status": 1, "status": 2}'):
            with self.subTest(source=source), self.assertRaises(ExtractionError):
                python_literal_names(source, 'SCHEMAS', mapping=True)

    def test_missing_detection_against_independently_stated_expectation(self):
        expected = ('begin', 'claim', 'status')
        source = 'strcmp(op,"status"); strcmp(op,"claim"); strcmp(op,"begin");'
        self.assertEqual(observation_difference(expected, c_comparison_values(source, 'op')), ((), ()))
        self.assertEqual(observation_difference(expected, c_comparison_values(source+'strcmp(op,"new_op");', 'op')), (('new_op',), ()))
        self.assertEqual(observation_difference(expected, c_comparison_values(source.replace('"claim"', '"changed"'), 'op')), (('changed',), ('claim',)))
        self.assertEqual(observation_difference(expected, c_comparison_values(source.replace('strcmp(op,"begin");', ''), 'op')), ((), ('begin',)))

    def test_duplicate_and_invalid_observations_are_not_collapsed(self):
        for expected, observed in ((('status',), ('status', 'status')), (['status', 'status'], []),
                                   ([], [None]), ([], ['']), ('status', [])):
            with self.subTest(expected=expected, observed=observed), self.assertRaises(ExtractionError):
                observation_difference(expected, observed)


class RepositorySamples(unittest.TestCase):
    """Six explicitly reviewed samples, not an exhaustive repository ledger."""
    root = Path(__file__).resolve().parents[1]

    def test_native_session_operation_sample(self):
        source = (self.root / 'src/agent_session/coordinator.c').read_text()
        self.assertEqual(c_comparison_values(source, 'op'),
            ('begin', 'claim', 'context', 'heartbeat', 'next', 'reconcile',
             'reject_output', 'resume', 'start', 'status', 'submit'))

    def test_native_completion_operation_sample(self):
        source = (self.root / 'src/completion/model.c').read_text()
        self.assertEqual(c_comparison_values(source, 'dw_text(r,"operation")'), ('finalize', 'resume'))

    def test_cli_subcommand_sample_includes_template_dispatch(self):
        source = (self.root / 'src/cli/workflow.c').read_text()
        self.assertEqual(c_comparison_values(source, 'argv[2]'), ('inputs', 'next', 'select', 'template', 'trace'))

    def test_cli_top_level_matches_existing_source_inventory(self):
        source = (self.root / 'src/cli/main.c').read_text()
        inventory = (self.root / 'docs/mcp-capability-inventory.ko.md').read_text()
        section = inventory.split('## Native CLI 최상위 dispatch\n', 1)[1].split('\n## ', 1)[0]
        expected = tuple(line[3:-1] for line in section.splitlines() if line.startswith('- `') and line.endswith('`'))
        self.assertTrue(expected)
        self.assertEqual(observation_difference(expected, c_comparison_values(source, 'argv[1]')), ((), ()))

    def test_d2_tool_declarations_without_importing_runtime_modules(self):
        source = (self.root / 'tools/integration_service.py').read_text()
        self.assertEqual(python_literal_names(source, 'SCHEMAS', mapping=True),
            tuple(sorted(('completion_check', 'context_get', 'evidence_read', 'handoff_prepare',
             'history_read', 'projects_list', 'work_inspect', 'workflow_read', 'template_read', 'role_read', 'session_read', 'binding_read', 'document_read', 'context_read', 'discovery_read', 'events_read', 'journal_read', 'profile_read', 'diagnostic_read', 'native_validate', 'report_read', 'approval_read', 'reentry_read', 'artifact_read', 'usage_read', 'revision_read', 'configuration_read', 'bundle_read', 'inputs_prepare', 'action_prepare', 'contract_prepare', 'approved_action_prepare', 'plan_read', 'action_confirm','proof_read','research_read','cost_read','execution_read','candidate_read','inventory_read','workspace_read','parallel_prepare','merge_prepare'))))

    def test_d4_tool_declarations_without_granting_mutations(self):
        source = (self.root / 'tools/integration_mutation_contract.py').read_text()
        self.assertEqual(python_literal_names(source, 'NAMES', mapping=False),
            tuple(sorted(('document_submit','execution_request','session_begin','session_claim','session_reconcile','session_resume','session_submit','session_start','session_heartbeat','session_reject_output','binding_attach','role_enroll','role_assess','completion_finalize','completion_report','reentry_decide','reentry_report','document_project','work_create','context_publish','discovery_snapshot','profile_register','run_link','work_noop_run','adapter_noop_run','lineage_store','approval_request','evidence_import','proof_publish','research_request','research_export','cost_inbox_reconcile','helper_execute','execution_verify','inventory_capture','candidate_request','workspace_request'))))


if __name__ == '__main__':
    unittest.main()
