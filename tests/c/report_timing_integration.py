"""Real failure records survive deferred presentation and historical replay."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

HELPER = Path(sys.argv.pop(4)).resolve()
from reentry_integration import Reentry


class Timing(Reentry):
    def helper(self, mode, value):
        return subprocess.run([str(HELPER), mode, str(self.work), str(value)],
                              capture_output=True, check=True, timeout=30).stdout.decode()

    def inventory(self):
        return {p.relative_to(self.work).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.work.rglob('*') if p.is_file()}

    def test_deferred_projection_and_failure_recovery(self):
        self.setup_failure()
        decision = json.loads(self.helper('deferred', self.write('decision.json', self.request())))
        self.assertEqual(decision['record']['schema_version'], 2)
        self.assertEqual(decision['record']['renderer_version'], 1)
        self.assertNotIn('report_digest', decision['record'])
        self.assertFalse((self.work / 'failures').exists())
        manifest = self.inputs('development-plan')
        key = decision['decision_digest']
        recorded = self.work / 'objects/sha256' / key[:2] / key[2:]
        self.assertEqual(manifest['total_bytes'],
                         sum(doc['bytes'] for doc in manifest['documents']) + recorded.stat().st_size)
        self.inputs('development-plan', budget=manifest['total_bytes'] - 1, ok=False)
        for p in (self.work / 'objects/sha256').glob('*/*'):
            self.assertFalse(p.read_bytes().startswith(b'# Failure and Reentry'))
        before = self.inventory()
        self.helper('failed-render', 1)
        self.assertEqual(before, self.inventory())
        self.assertEqual(self.decide(), decision)
        text = self.helper('read', 1)
        self.assertEqual(before, self.inventory())
        self.assertIn('Overall QA: **FAIL**', text)
        target = self.work / 'failures/r0001.md'
        target.parent.mkdir()
        target.write_text('conflicting user content')
        self.raw('reentry', 'report', self.work, 1, ok=False)
        self.assertEqual(target.read_text(), 'conflicting user content')
        self.assertEqual(self.decide(), decision)
        target.unlink()
        self.assertEqual(self.raw('reentry', 'report', self.work, 1), text)
        self.assertEqual(self.raw('reentry', 'report', self.work, 1), text)
        after = self.inventory()
        self.assertEqual({k: v for k, v in after.items() if k != 'failures/r0001.md'}, before)
        target.unlink()
        self.assertEqual(self.next()['target_kind'], 'development-plan')
        self.assertEqual(self.raw('reentry', 'report', self.work, 1), text)

    def test_legacy_and_mixed_replay(self):
        self.setup_failure()
        request = self.request('UNKNOWN')
        self.helper('legacy', self.write('legacy.json', request))
        first = self.decide(request)
        self.assertEqual(first['record']['schema_version'], 1)
        digest = first['record']['report_digest']
        obj = self.work / 'objects/sha256' / digest[:2] / digest[2:]
        historical = obj.read_bytes()
        self.assertEqual(self.raw('reentry', 'report', self.work, 1).encode(), historical)
        evidence = self.cli('evidence', 'put', self.work, self.write('review.txt', 'Inspect subtraction.'))
        request = self.request(key='decision-2', expected_sequence=1, previous_decision=first['decision_digest'])
        request['evidence_refs'].append(evidence['digest'])
        second = self.decide(request)
        self.assertEqual(second['record']['schema_version'], 2)
        self.assertEqual(self.decide(request), second)
        self.assertEqual(self.inputs('development-plan')['schema_version'], 3)
        self.assertEqual(self.raw('reentry', 'report', self.work, 1).encode(), historical)
        obj.unlink()
        self.cli('reentry', 'call', self.work, self.write('status.json', {'schema_version': 1, 'operation': 'status'}), ok=False)

    def test_unknown_renderer_and_tampered_decision_fail_closed(self):
        for mode in ('future', 'tampered'):
            with self.subTest(mode=mode):
                self.tearDown()
                self.setUp()
                self.setup_failure()
                self.helper(mode, self.write('decision.json', self.request()))
                self.cli('reentry', 'call', self.work, self.write('status.json', {'schema_version': 1, 'operation': 'status'}), ok=False)

    def test_legacy_session_context_keeps_historical_markdown(self):
        self.setup_failure(sessions=True)
        self.helper('legacy', self.write('legacy.json', self.request()))
        self.begin_claim()
        request = {'schema_version': 1, 'operation': 'context', 'work_id': 'example-work',
                   'token': self.token, 'max_bytes': 1048576}
        reply = self.cli('session', 'call', self.work, self.write('context.json', request))
        self.assertEqual(reply['manifest']['schema_version'], 2)
        self.assertIn(self.failure['receipt_digest'], reply['failure_markdown'])
        self.assertNotIn('failure_record', reply)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Timing(name) for name in Timing.__dict__ if name.startswith('test_'))


if __name__ == '__main__':
    unittest.main()
