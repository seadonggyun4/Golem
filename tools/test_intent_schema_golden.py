"""Public QC shape parity; never dispatch an Intent host or authorize a Work."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

import integration_contract as contract
import integration_intent as intent


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'tests/fixtures/intent/schema-golden'
SPEC = importlib.util.spec_from_file_location(
    'golem_test_intent_schema_golden_runner', ROOT / 'tests/c/intent_schema_golden.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class IntentSchemaGolden(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / 'docs/schemas/intent-qc-contracts.v1.schema.json').read_bytes())
        Draft202012Validator.check_schema(self.schema)
        self.validator = Draft202012Validator({**self.schema,
            'oneOf': [{'$ref': '#/$defs/integration-intent-host'}]})
        self.original = json.loads((FOLDER / 'integration-intent-host--valid.json').read_bytes())

    def assert_shape(self, value, expected):
        self.assertEqual(self.validator.is_valid(value), expected, 'public schema')
        try:
            contract._validate(value, intent.POLICY)
            accepted = True
        except contract.IntegrationError:
            accepted = False
        self.assertEqual(accepted, expected, 'runtime shape')

    def test_every_declared_operation_agrees_without_widening_product_packets(self):
        public = self.schema['$defs']['integration-intent-host']['properties']['bindings']['items']
        operations = intent.BINDING['properties']['operation']['enum']
        self.assertEqual(public['properties']['operation']['enum'], operations)
        for operation in operations:
            with self.subTest(operation=operation):
                value = copy.deepcopy(self.original)
                value['bindings'][0].update(operation=operation, action_id='', action_sha256='0' * 64)
                self.assert_shape(value, True)
        for operation in ('enroll', 'review', 'approve', 'enrollment-inspect-extra', ''):
            with self.subTest(unregistered_operation=operation):
                value = copy.deepcopy(self.original)
                value['bindings'][0]['operation'] = operation
                self.assert_shape(value, False)
        product = self.schema['$defs']['product-host-packet']['properties']['operation']['enum']
        self.assertEqual(set(product), {'assess', 'current', 'resume', 'accept', 'finalize'})
        self.assertNotIn('enrollment-inspect', product)
        self.assertEqual(len(self.schema['$defs']), 30)

    def test_binding_members_and_limits_remain_closed(self):
        for field in intent.BINDING['required']:
            with self.subTest(missing=field):
                value = copy.deepcopy(self.original)
                del value['bindings'][0][field]
                self.assert_shape(value, False)
        value = copy.deepcopy(self.original)
        value['bindings'][0]['approve'] = True
        self.assert_shape(value, False)
        for count, expected in ((0, False), (1, True), (32, True), (33, False)):
            with self.subTest(count=count):
                value = copy.deepcopy(self.original)
                value['bindings'] = [dict(value['bindings'][0], binding_id='binding-' + str(i))
                                     for i in range(count)]
                self.assert_shape(value, expected)
        value = copy.deepcopy(self.original)
        value['bindings'] *= 2
        self.assert_shape(value, False)

    def test_digest_boundaries_agree_for_all_policy_pins(self):
        paths = [('transfer_policy_sha256',), ('mutation_policy_sha256',),
                 ('registration_sha256',), ('git', 'sha256'), ('bridge', 'sha256'),
                 ('bindings', 0, 'action_sha256'), ('bindings', 0, 'packet', 'sha256'),
                 ('producer', 'integration_intent.py')]
        for path in paths:
            for digest, expected in (('a' * 64, True), ('A' * 64, False), ('a' * 63, False),
                                     ('a' * 65, False), ('a' * 64 + '\n', False)):
                with self.subTest(path=path, length=len(digest), expected=expected):
                    value = copy.deepcopy(self.original)
                    target = value
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = digest
                    self.assert_shape(value, expected)

    def test_variable_identifiers_and_paths_reject_trailing_controls(self):
        paths = [('repository',), ('git', 'path'), ('bridge', 'path'),
                 ('bindings', 0, 'packet', 'path'), ('bindings', 0, 'review_root', 'path')]
        identifiers = [('bindings', 0, name) for name in ('binding_id', 'project_id', 'work_id')]
        for path in paths + identifiers:
            for suffix in ('\n', '\r', '\r\n', '\t', '\0', '\x7f'):
                with self.subTest(path=path, suffix=repr(suffix)):
                    value = copy.deepcopy(self.original)
                    target = value
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] += suffix
                    self.assert_shape(value, False)
        for path in paths + identifiers:
            for suffix in ('\u2028', '\u2029'):
                with self.subTest(path=path, unicode_line_separator=repr(suffix)):
                    value = copy.deepcopy(self.original)
                    target = value
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] += suffix
                    self.assert_shape(value, path in paths)
        for path, size in [(path, 4096) for path in paths] + [(path, 64) for path in identifiers]:
            for length, expected in ((size, True), (size + 1, False)):
                with self.subTest(path=path, length=length):
                    value = copy.deepcopy(self.original)
                    target = value
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = 'a' * length
                    self.assert_shape(value, expected)
        # Runtime PATH permits Unicode; this check adds no filesystem policy.
        value = copy.deepcopy(self.original)
        value['repository'] = '/합성/경로'
        self.assert_shape(value, True)

    def test_pinned_golden_shapes_match_runtime_without_claiming_native_acceptance(self):
        manifest = json.loads((FOLDER / 'manifest.json').read_bytes())
        cases = [case for case in manifest['cases']
                 if case.get('definition') == 'integration-intent-host']
        self.assertGreaterEqual(len(cases), 18)
        required = {'integration-intent-host--' + suffix for suffix in (
            'enrollment-inspect', 'unsupported-enroll', 'duplicate-binding',
            'digest-newline', 'id-newline', 'path-newline')}
        self.assertTrue(required <= {case['id'] for case in cases})
        for case in cases:
            with self.subTest(case=case['id']):
                raw = (FOLDER / case['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), case['sha256'])
                try:
                    public = self.validator.is_valid(RUNNER.decode(raw))
                except (ValueError, UnicodeError):
                    public = False
                try:
                    contract._validate(contract.decode(raw), intent.POLICY)
                    runtime = True
                except contract.IntegrationError:
                    runtime = False
                self.assertEqual((public, runtime), (case['shape_accept'],) * 2)
                self.assertIsNone(case['native_probe'])
                self.assertIsNone(case['native_accept'])
                self.assertEqual(case['native_status'], 'NOT_RUN')
                self.assertTrue(case['context_required'])
        for name in ('tools/integration_contract.py', 'tools/integration_intent.py'):
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(),
                             manifest['source_sha256'][name])


if __name__ == '__main__':
    unittest.main()
