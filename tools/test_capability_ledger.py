import copy
import unittest
from unittest.mock import patch

import capability_ledger as ledger


def sample():
    capability = dict.fromkeys(ledger.CAPABILITY_FIELDS)
    capability.update(id='same-id', observation_ids=['same-id'])
    return {'schema': ledger.SCHEMA,
        'sources': [{'path': 'src/feature.c', 'sha256': 'a' * 64}],
        'observations': [{'id': 'same-id', 'kind': None, 'source_path': 'src/feature.c',
                          'entrypoint': 'feature_call', 'selector': 'status'}],
        'capabilities': [capability]}


class BaseFields(unittest.TestCase):
    def assert_rejected_without_mutation(self, value):
        before = copy.deepcopy(value)
        with self.assertRaises(ledger.BaseFieldError):
            ledger.validate_base_fields(value)
        self.assertEqual(before, value)

    def test_base_success_is_not_coverage_or_full_validation(self):
        value = sample()
        before = copy.deepcopy(value)
        self.assertIsNone(ledger.validate_base_fields(value))
        self.assertEqual(before, value)
        # Deliberately unresolved types are not silently declared approved.
        self.assertIsNone(value['observations'][0]['kind'])
        self.assertIsNone(value['capabilities'][0]['implementation'])

    def test_empty_arrays_and_null_selector(self):
        self.assertIsNone(ledger.validate_base_fields(dict(schema=ledger.SCHEMA,
            sources=[], observations=[], capabilities=[])))
        value = sample()
        value['observations'][0]['selector'] = None
        value['capabilities'][0]['observation_ids'] = []
        self.assertIsNone(ledger.validate_base_fields(value))

    def test_all_four_object_levels_are_closed_and_required(self):
        locations = [(), ('sources', 0), ('observations', 0), ('capabilities', 0)]
        for location in locations:
            for unknown in (True, False):
                value = sample()
                target = value
                for key in location:
                    target = target[key]
                if unknown:
                    target['unexpected'] = True
                else:
                    target.pop(next(iter(target)))
                with self.subTest(location=location, unknown=unknown):
                    self.assert_rejected_without_mutation(value)

    def test_rejects_wrong_root_schema_and_array_types(self):
        for field, invalid in [('schema', 'other.v1'), ('schema', None),
                               ('sources', ()), ('observations', {}), ('capabilities', None)]:
            value = sample()
            value[field] = invalid
            with self.subTest(field=field, invalid=invalid):
                self.assert_rejected_without_mutation(value)

    def test_rejects_unsafe_or_noncanonical_paths_without_normalizing(self):
        for path in ('', '/src/a.c', '../a.c', 'src/../a.c', 'src/./a.c',
                     'src//a.c', 'src/a.c/', 'src\\a.c', 'C:/a.c', 'C:a.c', 'a\0.c'):
            value = sample()
            value['sources'][0]['path'] = path
            with self.subTest(path=path):
                self.assert_rejected_without_mutation(value)

    def test_digest_type_case_length_and_source_reference(self):
        for digest in ('A' * 64, 'g' * 64, 'a' * 63, 'a' * 65, 123, None):
            value = sample()
            value['sources'][0]['sha256'] = digest
            self.assert_rejected_without_mutation(value)
        value = sample()
        value['observations'][0]['source_path'] = 'src/other.c'
        self.assert_rejected_without_mutation(value)

    def test_duplicate_sources_and_ids(self):
        for group in ('sources', 'observations', 'capabilities'):
            value = sample()
            value[group].append(copy.deepcopy(value[group][0]))
            with self.subTest(group=group):
                self.assert_rejected_without_mutation(value)

    def test_required_text_and_selector_type(self):
        for group, field in [('observations', 'id'), ('observations', 'entrypoint'),
                             ('observations', 'selector'), ('capabilities', 'id')]:
            for invalid in ('', False, [], {}):
                value = sample()
                value[group][0][field] = invalid
                self.assert_rejected_without_mutation(value)

    def test_dangling_duplicate_or_wrong_type_observation_refs(self):
        for refs in (['missing'], ['same-id', 'same-id'], [None], [''], 'same-id'):
            value = sample()
            value['capabilities'][0]['observation_ids'] = refs
            self.assert_rejected_without_mutation(value)

    def test_order_and_separate_id_namespaces_are_preserved(self):
        value = sample()
        value['sources'].append({'path': 'a.c', 'sha256': 'b' * 64})
        other = copy.deepcopy(value['observations'][0])
        other.update(id='earlier', source_path='a.c')
        value['observations'].append(other)
        value['capabilities'][0]['observation_ids'].append('earlier')
        before = copy.deepcopy(value)
        ledger.validate_base_fields(value)
        self.assertEqual(before, value)


def classified_sample():
    value = sample()
    value['observations'][0]['kind'] = 'NATIVE_OPERATION'
    value['capabilities'][0].update(implementation='IMPLEMENTED', review_status='REVIEWED',
        current_routes=['OWNER_ONLY'], target_routes=['MCP_REVIEWED_ACTION'])
    return value


class ClassificationFields(unittest.TestCase):
    def test_accepted_enums_do_not_rewrite_or_grant_authority(self):
        value = classified_sample()
        before = copy.deepcopy(value)
        self.assertIsNone(ledger.validate_classification_fields(value))
        self.assertEqual(ledger.classification_blockers(value), ())
        self.assertIsNone(value['capabilities'][0]['authorities'])
        self.assertEqual(before, value)

    def test_each_adopted_kind_and_implementation(self):
        for kind in ledger.OBSERVATION_KINDS:
            for implementation in ledger.IMPLEMENTATIONS:
                value = classified_sample()
                value['observations'][0]['kind'] = kind
                value['capabilities'][0]['implementation'] = implementation
                self.assertIsNone(ledger.validate_classification_fields(value))

    def test_wrong_enum_names_types_and_case_fail_without_mutation(self):
        for group, field in [('observations', 'kind'), ('capabilities', 'implementation'),
                             ('capabilities', 'review_status')]:
            for invalid in ('UNKNOWN', 'reviewed', '', True, None, [], {}):
                value = classified_sample()
                value[group][0][field] = invalid
                before = copy.deepcopy(value)
                with self.subTest(group=group, field=field, invalid=invalid), self.assertRaises(ledger.BaseFieldError):
                    ledger.validate_classification_fields(value)
                self.assertEqual(before, value)

    def test_route_duplicates_types_and_unknown_values_fail(self):
        for field in ('current_routes', 'target_routes'):
            for invalid in (['MCP_READ', 'MCP_READ'], ['MCP_ANYTHING'], ['PROPOSED_NOT_IMPLEMENTED'],
                            [True], [None], 'MCP_READ', None, {}):
                value = classified_sample()
                value['capabilities'][0][field] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ledger.BaseFieldError):
                    ledger.validate_classification_fields(value)

    def test_route_order_and_current_target_distinction_preserved(self):
        value = classified_sample()
        value['capabilities'][0]['current_routes'] = ['OWNER_ONLY', 'HOST_INTERNAL']
        value['capabilities'][0]['target_routes'] = ['MCP_REVIEWED_ACTION', 'MCP_READ']
        before = copy.deepcopy(value)
        ledger.validate_classification_fields(value)
        self.assertEqual(before, value)

    def test_all_uncertainty_is_reported_even_for_unreferenced_observation(self):
        value = classified_sample()
        value['observations'][0]['kind'] = 'UNRESOLVED'
        value['capabilities'][0].update(implementation='UNVERIFIED', review_status='UNREVIEWED',
                                       observation_ids=[])
        before = copy.deepcopy(value)
        self.assertEqual(ledger.classification_blockers(value),
            (('UNRESOLVED', 'same-id'), ('UNVERIFIED', 'same-id'), ('UNREVIEWED', 'same-id')))
        self.assertEqual(before, value)

    def test_empty_or_proposed_routes_do_not_produce_completion_result(self):
        for implementation in ('PARTIAL', 'PROPOSED', 'UNSUPPORTED'):
            value = classified_sample()
            value['capabilities'][0].update(implementation=implementation, current_routes=[])
            self.assertIsNone(ledger.validate_classification_fields(value))
            # No classification uncertainty is not a complete provision verdict.
            self.assertEqual(ledger.classification_blockers(value), ())
        empty = dict(schema=ledger.SCHEMA, sources=[], observations=[], capabilities=[])
        self.assertIsNone(ledger.validate_classification_fields(empty))
        self.assertEqual(ledger.classification_blockers(empty), ())


def metadata_sample():
    value = classified_sample()
    value['capabilities'][0].update(authorities=['Owner-reviewed D1/D2 contract'],
        effects=['NATIVE_READ', 'AUDIT_WRITE'],
        constraints={'platforms': ['Not independently verified'],
                     'limits': ['Sufficiency not checked'], 'notes': 'Description only'},
        test_refs=[{'path': 'tests/not-present.py', 'selector': 'test_not_executed'}],
        doc_refs=[{'path': 'docs/not-present.md', 'anchor': None}],
        rationale='A declaration, not permission or proof')
    return value


class MetadataFields(unittest.TestCase):
    def reject(self, value):
        before = copy.deepcopy(value)
        with self.assertRaises(ledger.BaseFieldError):
            ledger.validate_metadata_fields(value)
        self.assertEqual(before, value)

    def test_structure_does_not_read_or_certify_evidence(self):
        value = metadata_sample()
        before = copy.deepcopy(value)
        with patch('builtins.open', side_effect=AssertionError('must not read files')):
            self.assertIsNone(ledger.validate_metadata_fields(value))
            self.assertEqual(ledger.metadata_blockers(value), ())
        self.assertEqual(before, value)

    def test_empty_arrays_are_not_coverage_or_permission(self):
        value = metadata_sample()
        capability = value['capabilities'][0]
        for field in ('authorities', 'effects', 'test_refs', 'doc_refs', 'current_routes', 'target_routes'):
            capability[field] = []
        capability['constraints'].update(platforms=[], limits=[])
        self.assertIsNone(ledger.validate_metadata_fields(value))
        self.assertEqual(ledger.metadata_blockers(value), ())

    def test_text_arrays_reject_wrong_types_empty_values_and_duplicates(self):
        for group, field in [('capability', 'authorities'), ('constraints', 'platforms'), ('constraints', 'limits')]:
            for invalid in ('label', None, {}, [''], [False], ['same', 'same']):
                value = metadata_sample()
                target = value['capabilities'][0]
                if group == 'constraints':
                    target = target['constraints']
                target[field] = invalid
                self.reject(value)

    def test_constraints_are_closed_and_notes_rationale_are_nonempty(self):
        for field, invalid in [('constraints', None), ('constraints', {}),
                               ('constraints', {'platforms': [], 'limits': [], 'notes': 'ok', 'allow': True}),
                               ('rationale', ''), ('rationale', True)]:
            value = metadata_sample()
            value['capabilities'][0][field] = invalid
            self.reject(value)
        for invalid in ('', False, [], None):
            value = metadata_sample()
            value['capabilities'][0]['constraints']['notes'] = invalid
            self.reject(value)

    def test_effects_are_closed_enum_arrays_and_duplicates_rejected(self):
        for effect in ledger.EFFECTS:
            value = metadata_sample()
            value['capabilities'][0]['effects'] = [effect]
            self.assertIsNone(ledger.validate_metadata_fields(value))
        for invalid in ('NETWORK', None, ['network'], ['ALLOW'], [False], ['GIT', 'GIT']):
            value = metadata_sample()
            value['capabilities'][0]['effects'] = invalid
            self.reject(value)

    def test_unknown_effect_and_classification_blockers_are_combined(self):
        value = metadata_sample()
        value['observations'][0]['kind'] = 'UNRESOLVED'
        value['capabilities'][0].update(implementation='UNVERIFIED', review_status='UNREVIEWED',
                                       effects=['UNVERIFIED'])
        self.assertEqual(ledger.metadata_blockers(value),
            (('UNRESOLVED', 'same-id'), ('UNVERIFIED', 'same-id'),
             ('UNREVIEWED', 'same-id'), ('EFFECTS_UNVERIFIED', 'same-id')))

    def test_reference_shapes_paths_and_pair_duplicates_rejected(self):
        for field, selector in [('test_refs', 'selector'), ('doc_refs', 'anchor')]:
            for invalid in (None, 'path', [{}], [{'path': '../outside', selector: None}],
                            [{'path': 'a', selector: ''}], [{'path': 'a', selector: False}],
                            [{'path': 'a', selector: None, 'approved': True}],
                            [{'path': 'a', selector: None}, {'path': 'a', selector: None}]):
                value = metadata_sample()
                value['capabilities'][0][field] = invalid
                self.reject(value)

    def test_reference_order_and_distinct_selectors_preserved_without_execution(self):
        value = metadata_sample()
        value['capabilities'][0]['test_refs'] = [
            {'path': 'tests/a.py', 'selector': None},
            {'path': 'tests/a.py', 'selector': 'do_not_execute()'}]
        value['capabilities'][0]['doc_refs'] = [
            {'path': 'docs/a.md', 'anchor': 'second'},
            {'path': 'docs/a.md', 'anchor': 'first'}]
        before = copy.deepcopy(value)
        self.assertIsNone(ledger.validate_metadata_fields(value))
        self.assertEqual(before, value)


if __name__ == '__main__':
    unittest.main()
