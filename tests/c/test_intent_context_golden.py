"""Offline collector regressions, authored under HOLD; do not run yet."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from intent_context_golden import collect

ROOT = Path(__file__).resolve().parents[2]


class ContextGoldenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='qc-context-collector-')
        self.logs = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def marker(self, checkpoint='accept'):
        golden = json.loads((ROOT / 'tests/fixtures/intent/context-golden.json').read_text())
        files = {'request.json': b'{"op":"accept"}',
                 'stdout': b'{"body":{"intent_qa_status":"ACCEPTED","execution_status":"PASS"}}',
                 'stderr': b'', 'meta.json': b'{"returncode":0,"fault":""}'}
        for suffix, raw in files.items():
            (self.logs / ('native-0001.' + suffix)).write_bytes(raw)
        marker = dict(checkpoint=checkpoint, stem='native-0001',
                      sha256={k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
                      source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                     for p in golden['sources']})
        (self.logs / 'context-accept.json').write_text(json.dumps(marker))

    def test_absent_is_not_pass(self):
        result = collect(ROOT, self.logs)
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertEqual(len(result['missing_checkpoints']), 4)
        self.assertFalse(result['authority_verified'])

    def test_one_checkpoint_does_not_cover_other_contexts(self):
        self.marker()
        result = collect(ROOT, self.logs)
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertEqual(len(result['checkpoints']), 1)
        self.assertEqual(len(result['unobserved_definitions']), 30)

    def test_changed_result_is_rejected(self):
        self.marker()
        (self.logs / 'native-0001.stdout').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            collect(ROOT, self.logs)

    def test_unknown_checkpoint_is_rejected(self):
        self.marker('self-approved')
        with self.assertRaisesRegex(ValueError, 'unknown/duplicate'):
            collect(ROOT, self.logs)

    def test_duplicate_checkpoint_is_rejected(self):
        self.marker()
        (self.logs / 'context-second.json').write_bytes((self.logs / 'context-accept.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'unknown/duplicate'):
            collect(ROOT, self.logs)

    def test_symlink_transcript_is_rejected(self):
        self.marker()
        target = self.logs / 'native-0001.stdout'
        raw = target.read_bytes()
        target.unlink()
        (self.logs / 'other').write_bytes(raw)
        target.symlink_to('other')
        with self.assertRaisesRegex(ValueError, 'non-regular'):
            collect(ROOT, self.logs)


if __name__ == '__main__':
    unittest.main()
