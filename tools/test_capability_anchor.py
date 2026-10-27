import hashlib
import unittest
from unittest.mock import patch
from capability_anchor import markdown_anchor
from capability_evidence import inspect_references
from capability_files import SourceFile
from test_capability_ledger import metadata_sample


class Anchors(unittest.TestCase):
    def test_id_name_unicode_and_exact_position(self):
        for field in ('id', 'name'):
            raw = ('# intro\n\n<a '+field+'="근거"></a>\n').encode()
            self.assertEqual(markdown_anchor(raw, '근거'), (3, None))

    def test_duplicate_and_missing_never_resolved(self):
        self.assertIsNone(markdown_anchor(b'<a id="x"></a>\n<a name="x"></a>', 'x')[0])
        self.assertIsNone(markdown_anchor(b'# x', 'x')[0])

    def test_fences_comments_excluded(self):
        raw = b'```html\n<a id="x"></a>\n```\n<!--\n<a id="x"></a>\n-->\n<a id="x"></a>'
        self.assertEqual(markdown_anchor(raw, 'x'), (7, None))

    def test_fence_lengths_and_comment_text_in_code(self):
        raw = b'~~~~\n<!--\n~~~\n<a id="x"></a>\n~~~~\n<a id="x"></a>'
        self.assertEqual(markdown_anchor(raw, 'x'), (6, None))

    def test_inline_code_example_excluded(self):
        self.assertEqual(markdown_anchor(b'Example `<a id="x"></a>`\n<a id="x"></a>', 'x'), (2, None))

    def test_ambiguous_contexts_fail_closed(self):
        for text in ('<!--', '```', '<pre>', '> <a id="x"></a>', '- example',
                     '`multiline', '    <a id="x"></a>', '<a id="x" class="other"></a>', '\\<a id="x"></a>'):
            with self.subTest(text=text):
                self.assertIsNone(markdown_anchor((text+'\n<a id="x"></a>').encode(), 'x')[0])

    def test_no_slug_normalization_or_entity_decoding(self):
        for raw, anchor in [(b'# Heading', 'heading'), (b'<a id="x"></a>', '#x'),
                            (b'<a id="X"></a>', 'x'), (b'<a id="a&amp;b"></a>', 'a&b')]:
            self.assertIsNone(markdown_anchor(raw, anchor)[0])

    def test_null_invalid_utf8(self):
        self.assertEqual(markdown_anchor(b'', None), (None, 'ANCHOR_UNSPECIFIED'))
        self.assertEqual(markdown_anchor(b'\xff', 'x'), (None, 'MARKDOWN_NOT_UTF8'))

    def test_reader_integration_keeps_execution_sufficiency_unverified(self):
        ledger = metadata_sample()
        ledger['capabilities'][0]['doc_refs'][0]['anchor'] = 'x'
        raw = b'<a id="x"></a>'
        file = SourceFile('docs/not-present.md', hashlib.sha256(raw).hexdigest(), raw)
        with patch('capability_evidence.read_sources', return_value=(file,)):
            result = inspect_references(ledger, '/root', [file.path])[1]
        self.assertFalse(result.locator_unverified)
        self.assertEqual(result.declaration_line, 1)
        self.assertTrue(result.execution_unverified)
        self.assertTrue(result.sufficiency_unverified)


if __name__ == '__main__':
    unittest.main()
