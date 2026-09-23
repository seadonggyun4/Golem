"""Real Work ledger + admission bridge; synthetic execution, not a live agent."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import unittest

HELPER = Path(sys.argv.pop(1)).resolve()
import session_integration as fixture


class Admission(fixture.Session):
    # Do not repeat inherited session test cases in this suite.
    def setup_work(self, *args, **kwargs):
        super().setup_work(*args, **kwargs)
        self.cli("profile", "register", self.work,
                 fixture.fixture.SOURCE / "samples/runtime-profile.json", "profile-1")

    def invoke(self, mode="success", work="example-work", session="agent-a"):
        ledger = self.root / "admission"
        ledger.mkdir(exist_ok=True)
        return subprocess.run([str(HELPER), str(ledger), str(self.work),
                               self.active["runtime_binding"], work, session, mode],
                              capture_output=True, timeout=30, env=fixture.fixture.ENV)

    def prepared(self):
        self.setup_session(actual=True)
        self.claim()
        self.begin()

    def test_work_binding_and_replay(self):
        self.prepared()
        before = len(list((self.work / "events").glob("*.evt")))
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["state"], 8)
        self.assertEqual(data["executions"], 1)
        self.assertEqual(len(list((self.work / "events").glob("*.evt"))), before + 1)
        receipt = self.work / "objects/sha256" / data["receipt"][:2] / data["receipt"][2:]
        event = json.loads(receipt.read_bytes())
        self.assertEqual(event["type"], "admission-link")
        self.assertEqual(event["runtime_binding"], self.active["runtime_binding"])
        self.assertEqual(event["session_id"], "agent-a")
        self.request("status")  # Replay understands the new Work event.
        replay = self.invoke("inspect")
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(json.loads(replay.stdout)["executions"], 0)
        receipt.unlink()
        self.request("status", ok=False)

    def test_wrong_work_blocks_execution(self):
        self.prepared()
        result = self.invoke(work="other-work")
        self.assertNotEqual(result.returncode, 0)
        replay = self.invoke("inspect")
        self.assertEqual(json.loads(replay.stdout)["state"], 9)

    def test_wrong_session_blocks_execution(self):
        self.prepared()
        self.assertNotEqual(self.invoke(session="other-session").returncode, 0)

    def test_claim_not_begun_blocks_execution(self):
        self.setup_session(actual=True)
        self.claim()
        self.assertNotEqual(self.invoke().returncode, 0)

    def test_kill_after_work_publication(self):
        self.prepared()
        self.assertEqual(self.invoke("kill-publish").returncode, -signal.SIGKILL)
        result = self.invoke("inspect")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], 9)
        self.assertEqual(json.loads(result.stdout)["executions"], 0)
        self.request("status")

    def test_kill_after_execution_evidence(self):
        self.prepared()
        self.assertEqual(self.invoke("kill-execute").returncode, -signal.SIGKILL)
        for _ in range(2):
            result = self.invoke("inspect")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["state"], 6)
            self.assertEqual(json.loads(result.stdout)["executions"], 0)
        self.request("status")


if __name__ == "__main__":
    suite = unittest.TestSuite(Admission(name) for name in Admission.__dict__ if name.startswith("test_"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
