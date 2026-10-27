import copy
import json
import unittest
from unittest.mock import patch

import capability_ledger as ledger
from test_capability_ledger import metadata_sample


def encoded(value, *, ascii_only=False):
    return json.dumps(value, ensure_ascii=ascii_only, separators=(',', ':')).encode('utf-8')


class BoundedDecoder(unittest.TestCase):
    def rejected(self, raw, code):
        before = raw
        with self.assertRaises(ledger.BaseFieldError) as caught:
            ledger.decode_ledger(raw)
        self.assertEqual(str(caught.exception), code)
        self.assertEqual(before, raw)

    def test_decode_is_structural_not_file_execution_or_coverage(self):
        value = metadata_sample()
        raw = encoded(value)
        with patch('builtins.open', side_effect=AssertionError('no file reads')):
            actual = ledger.decode_ledger(raw)
        self.assertEqual(actual, value)
        self.assertIsNot(actual, value)
        self.assertEqual(encoded(actual), raw)
        empty = dict(schema=ledger.SCHEMA, sources=[], observations=[], capabilities=[])
        self.assertEqual(ledger.decode_ledger(encoded(empty)), empty)

    def test_raw_bytes_boundary_and_reject_before_parser(self):
        value = dict(schema=ledger.SCHEMA, sources=[], observations=[], capabilities=[])
        raw = encoded(value)
        exact = raw + b' ' * (ledger.JSON_BYTES_MAX - len(raw))
        self.assertEqual(ledger.decode_ledger(exact), value)
        with patch.object(ledger.json, 'loads', side_effect=AssertionError('must reject first')):
            self.rejected(exact + b' ', 'JSON_BYTES_LIMIT')

    def test_container_depth_boundary_before_json_parser(self):
        # Depth 16 reaches structural rejection; depth 17 never reaches parser.
        self.rejected(b'[' * 16 + b'null' + b']' * 16, 'CLOSED_FIELDS')
        with patch.object(ledger.json, 'loads', side_effect=AssertionError('must reject first')):
            self.rejected(b'[' * 17 + b'null' + b']' * 17, 'JSON_DEPTH_LIMIT')

    def test_escaped_quotes_and_brackets_do_not_count_as_containers(self):
        value = metadata_sample()
        value['capabilities'][0]['rationale'] = ('[{' * 20) + '"\\quoted\\"' + ('}]' * 20)
        self.assertEqual(ledger.decode_ledger(encoded(value)), value)

    def test_encoding_bom_and_input_type(self):
        raw = encoded(metadata_sample())
        self.rejected(b'\xef\xbb\xbf' + raw, 'JSON_BOM')
        self.rejected(b'\xff' + raw, 'JSON_UTF8')
        for invalid in (raw.decode(), bytearray(raw), None):
            self.rejected(invalid, 'LEDGER_BYTES')

    def test_duplicate_members_at_root_nested_and_escaped_key(self):
        for raw in (b'{"schema":"x","schema":"y"}',
                    b'{"schema":"x","\\u0073chema":"y"}',
                    b'{"a":{"notes":"x","notes":"y"}}'):
            self.rejected(raw, 'JSON_DUPLICATE_KEY')

    def test_lone_surrogates_are_rejected_in_values_and_keys(self):
        value = metadata_sample()
        for invalid in ('\ud800', '\udfff'):
            value['capabilities'][0]['rationale'] = invalid
            self.rejected(encoded(value, ascii_only=True), 'JSON_SURROGATE')
        self.rejected(b'{"\\ud800":"x"}', 'JSON_SURROGATE')

    def test_nonfinite_and_numeric_values_do_not_reach_field_validation(self):
        for raw in (b'NaN', b'Infinity', b'-Infinity'):
            self.rejected(raw, 'JSON_NONFINITE')
        for raw in (b'0', b'1.0', b'1e999999', b'9' * 5000):
            self.rejected(raw, 'JSON_NUMBER_NOT_IN_SCHEMA')

    def test_sources_count_exact_boundary_and_over(self):
        value = metadata_sample()
        value['sources'].extend({'path': f'src/source-{i}.c', 'sha256': 'b' * 64}
                               for i in range(4095))
        self.assertEqual(len(ledger.decode_ledger(encoded(value))['sources']), 4096)
        value['sources'].append({'path': 'src/one-extra.c', 'sha256': 'b' * 64})
        self.rejected(encoded(value), 'ARRAY_LIMIT')

    def test_observations_count_exact_boundary_and_over(self):
        value = metadata_sample()
        observation = value['observations'][0]
        value['observations'].extend({**observation, 'id': f'obs-{i}'} for i in range(16383))
        self.assertEqual(len(ledger.decode_ledger(encoded(value))['observations']), 16384)
        value['observations'].append({**observation, 'id': 'obs-extra'})
        self.rejected(encoded(value), 'ARRAY_LIMIT')

    def test_capabilities_count_exact_boundary_and_over(self):
        value = metadata_sample()
        capability = value['capabilities'][0]
        value['capabilities'].extend({**capability, 'id': f'cap-{i}'} for i in range(4095))
        self.assertEqual(len(ledger.decode_ledger(encoded(value))['capabilities']), 4096)
        value['capabilities'].append({**capability, 'id': 'cap-extra'})
        self.rejected(encoded(value), 'ARRAY_LIMIT')

    def test_item_array_boundaries(self):
        for field in ('authorities', 'platforms', 'limits', 'test_refs', 'doc_refs', 'observation_ids'):
            value = metadata_sample()
            cap = value['capabilities'][0]
            target = cap['constraints'] if field in ('platforms', 'limits') else cap
            if field in ('test_refs', 'doc_refs'):
                selector = 'selector' if field == 'test_refs' else 'anchor'
                target[field] = [{'path': f'tests/item-{i}', selector: None} for i in range(256)]
                extra = {'path': 'tests/extra', selector: None}
            elif field == 'observation_ids':
                source = value['observations'][0]
                value['observations'] = [{**source, 'id': f'obs-{i}'} for i in range(257)]
                target[field] = [f'obs-{i}' for i in range(256)]
                extra = 'obs-256'
            else:
                target[field] = [f'item-{i}' for i in range(256)]
                extra = 'extra'
            with self.subTest(field=field):
                self.assertEqual(ledger.decode_ledger(encoded(value)), value)
                target[field].append(extra)
                self.rejected(encoded(value), 'ARRAY_LIMIT')
        # Enum uniqueness is stricter than 256; oversized arrays still fail first.
        for field in ('effects', 'current_routes', 'target_routes'):
            value = metadata_sample()
            value['capabilities'][0][field] = ['UNVERIFIED'] * 257
            self.rejected(encoded(value), 'ARRAY_LIMIT')

    def test_id_byte_boundary_is_utf8_not_character_count(self):
        value = metadata_sample()
        identifier = 'é' * 128  # 256 bytes
        value['observations'][0]['id'] = identifier
        value['capabilities'][0].update(id=identifier, observation_ids=[identifier])
        self.assertEqual(ledger.decode_ledger(encoded(value)), value)
        value['capabilities'][0]['id'] += 'a'
        self.rejected(encoded(value), 'STRING_BYTES_LIMIT')

    def test_long_text_byte_boundaries(self):
        for field in ('rationale', 'notes'):
            value = metadata_sample()
            cap = value['capabilities'][0]
            target = cap if field == 'rationale' else cap['constraints']
            target[field] = 'é' * 8192
            self.assertEqual(ledger.decode_ledger(encoded(value)), value)
            target[field] += 'a'
            self.rejected(encoded(value), 'STRING_BYTES_LIMIT')

    def test_default_string_and_path_byte_boundaries(self):
        value = metadata_sample()
        value['observations'][0]['entrypoint'] = 'é' * 2048
        self.assertEqual(ledger.decode_ledger(encoded(value)), value)
        value['observations'][0]['entrypoint'] += 'a'
        self.rejected(encoded(value), 'STRING_BYTES_LIMIT')
        value = metadata_sample()
        path = 'src/' + 'a' * 4092
        value['sources'][0]['path'] = value['observations'][0]['source_path'] = path
        self.assertEqual(ledger.decode_ledger(encoded(value)), value)
        value['sources'][0]['path'] += 'a'
        self.rejected(encoded(value), 'STRING_BYTES_LIMIT')

    def test_unicode_pairs_and_normalization_are_preserved(self):
        value = metadata_sample()
        value['capabilities'][0]['rationale'] = '😀 e\u0301 é'
        raw = encoded(value, ascii_only=True)
        self.assertEqual(ledger.decode_ledger(raw), value)
        before = copy.deepcopy(value)
        ledger.decode_ledger(encoded(value))
        self.assertEqual(value, before)

    def test_malformed_trailing_and_truncated_json(self):
        for raw in (b'', b'{', b'{"a":"unterminated', b'{"a":[}',
                    encoded(metadata_sample()) + b' {}', b'/* comment */ {}'):
            self.rejected(raw, 'JSON_SYNTAX')


if __name__ == '__main__':
    unittest.main()
