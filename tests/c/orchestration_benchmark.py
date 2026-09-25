"""Bounded real-fixture benchmark, never interpreted as a performance gate."""
import sys
import subprocess
import unittest
import uuid
from pathlib import Path
from candidate_diff_integration import CandidateDiff
from discovery_integration import CLI, SOURCE

EVENTS = Path(sys.argv.pop(1)).resolve()
OUTPUT = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(SOURCE / "tools"))
from benchmark_orchestration import collect, commands


class Benchmark(CandidateDiff):
    def test_readonly_samples(self):
        self.ready_diff()
        self.command("diff-seal", "a", redaction="metadata")
        self.stop_host()
        admission = self.root / "benchmark-events"
        admission.mkdir()
        subprocess.run([str(EVENTS), "fixture", str(admission)], check=True, capture_output=True)
        request = self.write("history-benchmark.json", dict(schema_version=1, work_id="example-work",
                             after=0, limit=64, document_head="", agent_head=""))
        output = OUTPUT / ("orchestration-benchmark-" + uuid.uuid4().hex)
        report = collect(commands(CLI, self.work, request, admission, self.parent, "group", "a"),
                         output, repeats=30)
        self.assertEqual(set(report["metrics"]), {"history", "events", "diff", "template"})
        self.assertEqual(report["performance_gate"], "NOT_EVALUATED")
        print("Private benchmark evidence:", output)


def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite([Benchmark("test_readonly_samples")])


if __name__ == "__main__":
    unittest.main()
