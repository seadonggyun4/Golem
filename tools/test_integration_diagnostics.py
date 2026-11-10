"""Pure error/shape fixtures. No registry, Work, native command or MCP process."""
import copy
import unittest

import integration_contract as c
import integration_mutations as mutations
import integration_preparations as preparations
import integration_service as reads


class ValidationDiagnostics(unittest.TestCase):
    def rejected(self, value, rule, **kwargs):
        with self.assertRaises(c.IntegrationError) as caught:
            c._validate(value, rule, **kwargs)
        self.assertEqual(caught.exception.code, 'SCHEMA')
        self.assertEqual(str(caught.exception), 'SCHEMA')
        return caught.exception

    def preparation(self):
        return {'project_id': 'fixture-project', 'work_id': 'fixture-work',
                'preparation_request_id': 'fixture-request', 'tool': 'session_claim',
                'session_id': '', 'native_binding_id': '', 'fields_json': '{}',
                'body': '', 'context_json': '', 'count_json': ''}

    def test_empty_session_id_reports_public_format_before_service_access(self):
        service = reads.Service.__new__(reads.Service)
        with self.assertRaises(c.IntegrationError) as caught:
            service.call('action_prepare', self.preparation())
        diagnostic = c.validation_diagnostic(caught.exception)
        self.assertEqual(diagnostic['path'], '$.session_id')
        self.assertEqual(diagnostic['scope'], 'INPUT_SCHEMA')
        self.assertEqual(diagnostic['reason'], 'FORMAT')
        self.assertEqual(diagnostic['expected'], {'type': 'string', 'maxLength': 64, 'format': 'identifier'})
        # No registry, lock or preparation instance was supplied or accessed.
        self.assertEqual(service.__dict__, {})

    def test_nested_array_path_and_integer_boolean_boundary(self):
        rule = c.obj({'rows': c.array(c.obj({'sequence': c.INTEGER}))})
        error = self.rejected({'rows': [{'sequence': True}]}, rule)
        diagnostic = c.validation_diagnostic(error)
        self.assertEqual(diagnostic['path'], '$.rows[0].sequence')
        self.assertEqual(diagnostic['reason'], 'TYPE')
        self.assertEqual(diagnostic['scope'], 'CONTRACT_SHAPE')
        c._validate({'rows': [{'sequence': 0}]}, rule)

    def test_missing_required_field_is_named_without_unrelated_values(self):
        args = self.preparation(); args.pop('body'); args['fields_json'] = '{"private":"sentinel-value"}'
        error = self.rejected(args, preparations.SCHEMAS['action_prepare'], scope='INPUT_SCHEMA')
        diagnostic = c.validation_diagnostic(error)
        self.assertEqual((diagnostic['path'], diagnostic['reason']), ('$.body', 'MISSING_REQUIRED_FIELD'))
        self.assertNotIn('sentinel-value', c.encoded(reads.blocked(error)).decode())

    def test_unknown_input_key_and_value_are_never_echoed(self):
        args = self.preparation(); args['session_id'] = 'fixture-owner'
        args['secret-unknown-field'] = 'sentinel-value'
        error = self.rejected(args, preparations.SCHEMAS['action_prepare'])
        diagnostic = c.validation_diagnostic(error)
        self.assertEqual((diagnostic['path'], diagnostic['reason']), ('$', 'UNEXPECTED_FIELDS'))
        for response in (reads.blocked(error), mutations.blocked(error)):
            encoded = c.encoded(response).decode()
            self.assertNotIn('secret-unknown-field', encoded)
            self.assertNotIn('sentinel-value', encoded)

    def test_private_const_enum_and_pattern_are_not_returned(self):
        cases = [('wrong', {'const': 'sentinel-approval-key'}, 'CONST'),
                 ('wrong', c.enum('sentinel-owner-label'), 'ENUM'),
                 ('wrong', {'type': 'string', 'pattern': '^sentinel-token$'}, 'FORMAT')]
        for value, rule, reason in cases:
            with self.subTest(reason=reason):
                error = self.rejected(value, rule)
                self.assertEqual(c.validation_diagnostic(error)['reason'], reason)
                self.assertNotIn('sentinel', c.encoded(reads.blocked(error)).decode())

    def test_schema_key_without_safe_identifier_is_unnamed(self):
        error = self.rejected({}, c.obj({'/private/sentinel': c.ID}))
        self.assertEqual(c.validation_diagnostic(error)['path'], '$.<field>')
        self.assertNotIn('sentinel', c.encoded(reads.blocked(error)).decode())

    def test_oneof_zero_and_multiple_matches_still_reject(self):
        one = {'oneOf': [c.obj({'kind': {'const': 'one'}}), c.obj({'kind': {'const': 'two'}})]}
        c._validate({'kind': 'one'}, one)
        for rule, value in ((one, {'kind': 'three'}), ({'oneOf': [c.ID, c.ID]}, 'both')):
            error = self.rejected(value, rule)
            self.assertEqual(c.validation_diagnostic(error)['reason'], 'ONE_OF')

    def test_size_range_and_duplicate_rejection_unchanged(self):
        cases = [('xx', {'type': 'string', 'maxLength': 1}, 'LENGTH'),
                 (2, {'type': 'integer', 'minimum': 0, 'maximum': 1}, 'RANGE'),
                 ([], c.array(c.ID), 'ARRAY_LENGTH'),
                 (['same', 'same'], c.array(c.ID), 'DUPLICATE_ITEMS')]
        for value, rule, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(c.validation_diagnostic(self.rejected(value, rule))['reason'], reason)

    def test_direct_mutation_args_are_input_scope_and_never_dispatch(self):
        service = mutations.Service.__new__(mutations.Service)
        with self.assertRaises(c.IntegrationError) as caught:
            service.call('session_claim', {'project_id': 'fixture-project', 'work_id': 'fixture-work',
                'action_id': '', 'request_id': 'fixture-request'})
        diagnostic = c.validation_diagnostic(caught.exception)
        self.assertEqual((diagnostic['path'], diagnostic['scope']), ('$.action_id', 'INPUT_SCHEMA'))
        self.assertEqual(service.__dict__, {})

    def test_semantic_diagnostic_preserves_code_and_both_error_envelopes(self):
        with self.assertRaises(c.IntegrationError) as caught:
            c.require(False, 'ACTION_CONTEXT_SCOPE', diagnostic=c.field_diagnostic(
                '$.context_json', 'EMPTY_REQUIRED', {'type': 'string', 'maxLength': 0}, scope='INPUT_CONTRACT'))
        error = caught.exception
        self.assertEqual(str(error), 'ACTION_CONTEXT_SCOPE')
        for mapper in (reads.blocked, mutations.blocked):
            detailed = mapper(error); generic = mapper(c.IntegrationError(error.code))
            diagnostic = detailed.pop('validation_diagnostic')
            self.assertEqual(detailed, generic)
            self.assertEqual(diagnostic['expected'], {'type': 'string', 'maxLength': 0})

    def test_uncertain_outcome_stays_unknown_and_not_retryable(self):
        error = self.rejected('', c.ID)
        detailed = mutations.blocked(error, uncertain=True, evidence_id='fixture-evidence')
        generic = mutations.blocked(c.IntegrationError('SCHEMA'), uncertain=True, evidence_id='fixture-evidence')
        detailed.pop('validation_diagnostic')
        self.assertEqual(detailed, generic)
        self.assertEqual(detailed['state'], 'COMMIT_UNKNOWN')
        self.assertEqual(detailed['native_state_changed'], 'UNKNOWN')
        self.assertFalse(detailed['automatic_retry_allowed'])
        self.assertFalse(detailed['execution_authorized'])

    def test_arbitrary_or_malformed_diagnostic_is_not_forwarded(self):
        safe = c.field_diagnostic('$.body', 'TYPE', {'type': 'string'})
        altered = []
        for field, bad in (('path', '/private/sentinel'), ('scope', ['INPUT_SCHEMA']),
                           ('reason', 'sentinel-token'), ('expected', {'actual': 'sentinel'})):
            value = copy.deepcopy(safe); value[field] = bad; altered.append(value)
        for value in ({'message': 'sentinel'}, *altered):
            error = c.IntegrationError('SCHEMA'); error.diagnostic = value
            for mapper in (reads.blocked, mutations.blocked):
                response = mapper(error)
                self.assertNotIn('validation_diagnostic', response)
                self.assertNotIn('sentinel', c.encoded(response).decode())


if __name__ == '__main__':
    unittest.main()
