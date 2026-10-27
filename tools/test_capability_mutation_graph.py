import unittest
import test_capability_connections as fixtures
from capability_mutation_graph import inspect_mutation_graph
import capability_delegation as delegation

class Graph(unittest.TestCase):
    inputs = fixtures.Connections.inputs
    changed = fixtures.Connections.changed
    def test_actual_graph_is_not_execution(self):
        r=inspect_mutation_graph(self.inputs(delegation))
        self.assertFalse(r.blockers); self.assertEqual(len(r.edges),10)
        self.assertEqual(len(r.prefix_mapping),5)
        self.assertEqual(dict(r.argv_routes)['execution_request'],('host','execute'))
        self.assertFalse(r.policy_satisfied);self.assertFalse(r.native_execution_verified)
    def test_prefix_mutations(self):
        for old,new in ((b'name.removeprefix("session_")',b'name.removeprefix("other_")'),
                        (b'name.startswith("session_")',b'name.startswith(prefix)')):
            files,pins=self.changed(delegation,'tools/integration_mutation_contract.py',old,new)
            self.assertTrue(inspect_mutation_graph(files,pins).blockers)
    def test_capture_arguments_and_scope(self):
        for old,new in ((b'records.capture(argv, output, 540',b'records.capture(other, output, 540'),
                        (b'with admission:',b'if False:')):
            files,pins=self.changed(delegation,'tools/integration_mutations.py',old,new)
            self.assertTrue(inspect_mutation_graph(files,pins).blockers)
    def test_policy_edge_removed(self):
        files,pins=self.changed(delegation,'tools/integration_mutations.py',b'project, scope = self.policy.authorize(entry)',b'project, scope = other.authorize(entry)')
        self.assertTrue(inspect_mutation_graph(files,pins).blockers)
    def test_argv_precedence_predicate(self):
        files,pins=self.changed(delegation,'tools/integration_mutations.py',b'if tool == "session_resume":',b'if tool.startswith("session_"):')
        self.assertTrue(inspect_mutation_graph(files,pins).blockers)
    def test_lock_expression_changed(self):
        files,pins=self.changed(delegation,'tools/integration_mutations.py',b'with self.registry.locked(exclusive=True):',b'with self.registry.locked(exclusive=False):')
        self.assertTrue(inspect_mutation_graph(files,pins).blockers)
