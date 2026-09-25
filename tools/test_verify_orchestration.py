import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from benchmark_orchestration import collect
from verify_orchestration import GROUPS
from verify_runtime import adjudicate


class OrchestrationReport(unittest.TestCase):
    def test_required_inventory_unique_and_missing_fail_closed(self):
        names = sum(GROUPS.values(), ())
        self.assertEqual(len(names), len(set(names)))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "result.xml"
            p.write_text('<testsuite><testcase name="unknown" status="run"/></testsuite>')
            self.assertFalse(adjudicate(p, names))

    def test_samples_require_stable_projection_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            binary = root / "binary"
            binary.write_bytes(b"fixture")
            commands = {k: [binary] for k in ("history", "events", "diff", "template")}
            def fixed(_argv, _kind):
                return dict(elapsed_ns=10, bytes=2, sha256="a" * 64)
            with patch("benchmark_orchestration.sample", side_effect=fixed):
                report = collect(commands, root / "success", repeats=5)
                self.assertFalse(report["actual_agent_verified"])
                self.assertEqual(report["performance_gate"], "NOT_EVALUATED")
                with self.assertRaises(FileExistsError):
                    collect(commands, root / "success", repeats=5)
            samples = [fixed(None, None) for _ in range(4)] + [dict(elapsed_ns=10, bytes=2, sha256="b" * 64)] * 4
            with patch("benchmark_orchestration.sample", side_effect=samples):
                with self.assertRaisesRegex(ValueError, "projection changed"):
                    collect(commands, root / "changed", repeats=5)
            self.assertFalse((root / "changed/report.json").exists())
            with self.assertRaises(ValueError):
                collect({}, root / "missing", repeats=5)

    def test_unchanged_output_cannot_hide_changed_request(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            binary, request = root / "binary", root / "request.json"
            binary.write_bytes(b"fixture")
            request.write_bytes(b"before")
            commands = {k: [binary, request] for k in ("history", "events", "diff", "template")}
            def changed(_argv, _kind):
                request.write_bytes(b"after")
                return dict(elapsed_ns=10, bytes=2, sha256="a" * 64)
            with patch("benchmark_orchestration.sample", side_effect=changed):
                with self.assertRaisesRegex(ValueError, "inputs changed"):
                    collect(commands, root / "result", repeats=5)
            self.assertFalse((root / "result/report.json").exists())


if __name__ == "__main__":
    unittest.main()
