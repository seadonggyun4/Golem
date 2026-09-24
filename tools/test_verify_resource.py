from collections import defaultdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify_resource as gate


class KernelQualification(unittest.TestCase):
    def test_kernel_deltas_required_not_just_child_exit(self):
        for enforced in (False, True):
            with self.subTest(enforced=enforced), tempfile.TemporaryDirectory() as tmp:
                seen = defaultdict(int)
                def observe(scope, name):
                    seen[name] += 1
                    if name == "cgroup.events":
                        return {"populated": 0}
                    key = {"cpu.stat": "nr_throttled", "memory.events": "oom_kill",
                           "pids.events": "max"}[name]
                    return {key: int(enforced and seen[name] > 1)}
                with patch.object(gate, "counters", side_effect=observe), \
                        patch.object(gate.subprocess, "run") as run:
                    if not enforced:
                        with self.assertRaises(ValueError):
                            gate.verify(Path(tmp), Path(tmp))
                    else:
                        report = gate.verify(Path(tmp), Path(tmp))
                        self.assertEqual(report["status"], "PASS")
                        self.assertFalse(report["sandbox_verified"])
                        self.assertFalse(report["candidate_integration_verified"])
                    self.assertEqual([call.args[0][-1] for call in run.call_args_list],
                                     ["normal", "memory", "cpu", "tasks"])

    def test_populated_scope_never_launches(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(gate, "counters", return_value={"populated": 1}), \
                patch.object(gate.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                gate.verify(Path(tmp), Path(tmp))
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
