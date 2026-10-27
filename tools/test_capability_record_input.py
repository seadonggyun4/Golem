import unittest
from unittest.mock import patch
import capability_record_input as c


class Inputs(unittest.TestCase):
    def decode(self, raw):
        return c.decode_record_inputs({'a.json': raw}, ['a.json'])['a.json']

    def test_numbers_and_unchanged_raw(self):
        raw = b'{"exit":0,"elapsed":0.25,"n":null}'
        self.assertEqual(self.decode(raw), {'exit': 0, 'elapsed': .25, 'n': None})
        self.assertEqual(raw, b'{"exit":0,"elapsed":0.25,"n":null}')
        self.assertTrue(self.decode(b'1'+b'0'*5000).is_finite())

    def test_invalid_json(self):
        for raw in (b'\xff', b'\xef\xbb\xbf{}', b'{"a":1,"a":2}', b'"\\ud800"',
                    b'NaN', b'Infinity', b'1e999', b'{} trailing', b'{'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.decode(raw)

    def test_exact_depth(self):
        self.decode(b'['*32+b'0'+b']'*32)
        with self.assertRaisesRegex(c.RecordInputError, 'DEPTH'):
            self.decode(b'['*33+b'0'+b']'*33)
        self.assertEqual(self.decode(b'"[[[["'), '[[[[')

    def test_exact_string_bytes_and_keys(self):
        self.decode(b'"'+b'x'*c.STRING_MAX+b'"')
        for raw in (b'"'+b'x'*(c.STRING_MAX+1)+b'"', b'{"'+b'x'*(c.STRING_MAX+1)+b'":0}'):
            with self.assertRaisesRegex(c.RecordInputError, 'STRING'):
                self.decode(raw)

    def test_count_and_source_path(self):
        c.decode_record_inputs({str(i): b'' for i in range(4096)}, [])
        with self.assertRaises(ValueError):
            c.decode_record_inputs({str(i): b'' for i in range(4097)}, [])
        for name in ('../x', '/x', 'a//b'):
            with self.assertRaises(ValueError):
                c.decode_record_inputs({name: b''}, [])

    def test_exact_file_and_total_sizes(self):
        raw = b'x'*c.FILE_MAX
        c.decode_record_inputs({str(i): raw for i in range(4)}, [])
        with self.assertRaisesRegex(c.RecordInputError, 'TOTAL'):
            c.decode_record_inputs({**{str(i): raw for i in range(4)}, 'extra': b'x'}, [])
        with self.assertRaisesRegex(c.RecordInputError, 'FILE_BYTES_LIMIT'):
            c.decode_record_inputs({'x': raw+b'x'}, [])

    def test_node_budget_across_files(self):
        with patch.object(c, 'NODES_MAX', 4):
            c.decode_record_inputs({'a': b'[0]', 'b': b'[1]'}, ['a', 'b'])
            with self.assertRaisesRegex(c.RecordInputError, 'NODE'):
                c.decode_record_inputs({'a': b'[0]', 'b': b'[1,2]'}, ['a', 'b'])

    def test_explicit_selection_no_reference_following(self):
        self.assertEqual(self.decode(b'{"path":"/private/never-read"}'), {'path': '/private/never-read'})
        for names in (['missing'], ['a', 'a']):
            with self.assertRaises(ValueError):
                c.decode_record_inputs({'a': b'{}'}, names)
        self.assertEqual(c.decode_record_inputs({'binary': b'\xff'}, []), {})


if __name__ == '__main__':
    unittest.main()
