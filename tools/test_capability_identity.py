import copy
import hashlib
import json
import unittest

import capability_ledger as ledger
from test_capability_ledger import metadata_sample


def fields():
    return {'kind': 'NATIVE_OPERATION', 'source_path': 'src/agent_session/coordinator.c',
            'entrypoint': 'golem_agent_session_call', 'selector': 'status'}


def identified_sample():
    value = metadata_sample()
    observation = value['observations'][0]
    identity = ledger.observation_identity(**{key: observation[key] for key in
        ('kind', 'source_path', 'entrypoint', 'selector')})
    observation['id'] = identity
    value['capabilities'][0]['observation_ids'] = [identity]
    return value


class ObservationIdentity(unittest.TestCase):
    def test_independent_literal_json_known_vector(self):
        self.assertEqual(ledger.observation_identity(**fields()),
            'obs-9048f400a48ad3cdcd59f6080b8bc97ac5d8257f2ddab5093d8422dc9d956459')
        # Independent explicit wire bytes, not the implementation's encoder.
        payload = (b'{"entrypoint":"golem_agent_session_call","kind":"NATIVE_OPERATION",'
                   b'"selector":"status","source_path":"src/agent_session/coordinator.c"}')
        self.assertNotEqual(ledger.observation_identity(**fields()),
                            'obs-' + hashlib.sha256(payload).hexdigest())
        self.assertNotEqual(ledger.observation_identity(**fields()),
            'obs-' + hashlib.sha256(b'golem.mcp-observation-id.v1' + payload).hexdigest())

    def test_each_identity_member_changes_id(self):
        original = fields()
        expected = ledger.observation_identity(**original)
        for key, other in [('kind', 'CLI_ROUTE'), ('source_path', 'src/other.c'),
                           ('entrypoint', 'other_call'), ('selector', 'next')]:
            self.assertNotEqual(expected, ledger.observation_identity(**{**original, key: other}))

    def test_null_selector_is_not_a_string(self):
        original = fields()
        self.assertNotEqual(ledger.observation_identity(**{**original, 'selector': None}),
                            ledger.observation_identity(**{**original, 'selector': 'null'}))

    def test_unicode_and_no_normalization(self):
        original = fields()
        left = {**original, 'source_path': 'src/é.c'}
        right = {**original, 'source_path': 'src/e\u0301.c'}
        payload = ('{"entrypoint":"golem_agent_session_call","kind":"NATIVE_OPERATION",'
                   '"selector":"status","source_path":"src/é.c"}').encode('utf-8')
        self.assertEqual(ledger.observation_identity(**left),
            'obs-' + hashlib.sha256(b'golem.mcp-observation-id.v1\0' + payload).hexdigest())
        self.assertNotEqual(ledger.observation_identity(**left), ledger.observation_identity(**right))

    def test_input_field_order_and_original_objects_preserved(self):
        original = fields()
        before = copy.deepcopy(original)
        reversed_fields = dict(reversed(list(original.items())))
        self.assertEqual(ledger.observation_identity(**original), ledger.observation_identity(**reversed_fields))
        self.assertEqual(original, before)

    def test_source_hash_and_array_order_are_not_identity_or_reapproval(self):
        value = identified_sample()
        identifier = value['observations'][0]['id']
        value['sources'][0]['sha256'] = 'b' * 64
        value['sources'].insert(0, {'path': 'src/extra.c', 'sha256': 'c' * 64})
        self.assertIsNone(ledger.validate_observation_ids(value))
        self.assertEqual(value['observations'][0]['id'], identifier)
        # No actual source bytes or earlier review are verified by this function.

    def test_mismatch_is_rejected_without_rewriting_ids_or_refs(self):
        value = identified_sample()
        value['observations'][0]['id'] = 'obs-' + '0' * 64
        value['capabilities'][0]['observation_ids'] = [value['observations'][0]['id']]
        before = copy.deepcopy(value)
        with self.assertRaisesRegex(ledger.BaseFieldError, '^OBSERVATION_ID_MISMATCH$'):
            ledger.validate_observation_ids(value)
        self.assertEqual(value, before)

    def test_bounded_decode_and_capability_ids_stay_separate(self):
        value = identified_sample()
        value['capabilities'][0]['id'] = 'owner-chosen-stable-capability'
        raw = json.dumps(value).encode()
        self.assertEqual(ledger.decode_identified_ledger(raw), value)
        bad = metadata_sample()
        with self.assertRaisesRegex(ledger.BaseFieldError, '^OBSERVATION_ID_MISMATCH$'):
            ledger.decode_identified_ledger(json.dumps(bad).encode())
        # The lower layer intentionally promises structural decoding only.
        self.assertEqual(ledger.decode_ledger(json.dumps(bad).encode()), bad)

    def test_invalid_identity_inputs_are_not_normalized_or_truncated(self):
        original = fields()
        for key, invalid in [('kind', 'UNKNOWN'), ('source_path', '../outside.c'),
                             ('source_path', '/src/a.c'), ('entrypoint', ''),
                             ('entrypoint', 'é' * 2049), ('entrypoint', '\ud800'),
                             ('selector', True), ('selector', ''), ('selector', 'a' * 4097)]:
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ledger.BaseFieldError):
                ledger.observation_identity(**{**original, key: invalid})


if __name__ == '__main__':
    unittest.main()
