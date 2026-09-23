"""Process-boundary recovery tests; all queues and workers are test-local."""
import json
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

CLI = str(Path(sys.argv[1]).resolve())
ROOT = str(Path(sys.argv[2]).resolve())
sys.argv = [sys.argv[0]]


class DaemonIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="daemon-cli-", dir=ROOT)
        self.root = Path(self.tmp.name)
        self.queue = self.root / "queue"
        self.call("init", self.root / "project")
        self.capsule = self.root / "project/capsule.json"
        self.call("daemon", "init", self.queue)
        self.children = []
        self.groups = []

    def tearDown(self):
        for p in self.children:
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=5)
        for pid in self.groups:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.tmp.cleanup()

    def call(self, *args, code=0):
        p = subprocess.run([CLI, *map(str, args)], capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, code, (args, p.stdout, p.stderr))
        if code:
            self.assertEqual(p.stdout, "")
            return None
        return json.loads(p.stdout)

    def submit(self):
        result = self.call("daemon", "submit", self.queue, self.capsule)
        return self.queue / "jobs" / f'{int(result["ticket"]):020d}'

    def run_queue(self, mode="--drain", worker=CLI):
        return self.call("daemon", "run", self.queue, "--worker", worker, mode)

    def status(self):
        return self.call("daemon", "status", self.queue)["jobs"]

    def spawn(self, worker=CLI):
        p = subprocess.Popen([CLI, "daemon", "run", str(self.queue), "--worker", str(worker)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.children.append(p)
        return p

    def wait_for(self, condition):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = condition()
            if value:
                return value
            time.sleep(0.02)
        self.fail(f"Timed out: jobs={self.status()}, processes={[p.poll() for p in self.children]}")

    def worker(self, mode):
        path = self.root / "worker.py"
        path.write_text(f"""#!{sys.executable}
import os, sys, time
from pathlib import Path
if sys.argv[3] == 'probe':
    os.execv({CLI!r}, [{CLI!r}, *sys.argv[1:]])
sys.stdin.buffer.read()
Path(sys.argv[4], 'worker.pid').write_text(str(os.getpid()))
if {mode!r} == 'descendant':
    if os.fork() == 0:
        time.sleep(2)
        Path(sys.argv[4], 'descendant-survived').write_text('unexpected')
        os._exit(0)
    print('{{invalid')
    sys.exit(0)
if {mode!r} == 'malformed':
    print('{{invalid')
    sys.exit(0)
while True:
    time.sleep(0.1)
""")
        path.chmod(0o700)
        return path

    def test_restart_and_fairness(self):
        first, second = self.submit(), self.submit()
        self.run_queue("--once")
        result = first / "result-00000000000000000001"
        self.assertTrue(result.exists())
        self.assertFalse((second / result.name).exists())
        original = result.read_bytes()
        journal_prefix = (first / "journal.bin").read_bytes()
        self.run_queue()
        self.assertEqual([j["state"] for j in self.status()], ["complete", "complete"])
        self.assertEqual(result.read_bytes(), original)
        self.assertTrue((first / "journal.bin").read_bytes().startswith(journal_prefix))
        for job in [first, second]:
            results = sorted(job.glob("result-*"))
            self.assertEqual(len(results), 6)
            for file in results:
                envelope = json.loads(file.read_text())
                self.assertEqual(envelope["simulation"], "1")
            replay = self.call("replay", job / "journal.bin", "--require-terminal")
            self.assertEqual(replay["state"], "SUCCEEDED")
        before = {p: p.read_bytes() for p in self.queue.rglob("*") if p.is_file()}
        self.run_queue()
        self.assertEqual(before, {p: p.read_bytes() for p in self.queue.rglob("*") if p.is_file()})

    def test_foreground_lock_and_live_submission(self):
        p = self.spawn()
        self.wait_for(lambda: p.poll() is not None or self.queue.exists())
        # A submitted job completing proves the foreground owner has acquired its lock.
        self.submit()
        self.wait_for(lambda: self.status()[0]["state"] == "complete")
        self.call("daemon", "run", self.queue, "--worker", CLI, "--once", code=1)
        self.submit()
        self.wait_for(lambda: self.status()[1]["state"] == "complete")
        p.send_signal(signal.SIGTERM)
        stdout, stderr = p.communicate(timeout=5)
        self.assertEqual(p.returncode, 0, stderr)
        self.assertEqual(len(json.loads(stdout)["jobs"]), 2)
        self.run_queue()

    def test_submission_waits_for_reader_and_does_not_duplicate(self):
        with (self.queue / ".queue.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            p = subprocess.Popen([CLI, "daemon", "submit", str(self.queue), str(self.capsule)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.children.append(p)
            time.sleep(0.3)
            self.assertIsNone(p.poll(), "submission did not tolerate a temporary reader")
            self.assertEqual(list((self.queue / "jobs").iterdir()), [])
            fcntl.flock(lock, fcntl.LOCK_UN)
            stdout, stderr = p.communicate(timeout=5)
            self.assertEqual(p.returncode, 0, stderr)
            self.assertEqual(int(json.loads(stdout)["ticket"]), 1)
        self.assertEqual(len(self.status()), 1)

    def test_submission_busy_is_bounded_and_does_not_publish(self):
        with (self.queue / ".queue.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            self.call("daemon", "submit", self.queue, self.capsule, code=1)
            self.assertEqual(list((self.queue / "jobs").iterdir()), [])

    def test_uncertain_crash_and_signal(self):
        for sig in [signal.SIGTERM, signal.SIGKILL]:
            job = self.submit()
            p = self.spawn(self.worker("hang"))
            pid_file = job / "evidence/worker.pid"
            self.wait_for(lambda: pid_file.exists() and pid_file.read_text())
            pid = int(pid_file.read_text())
            self.groups.append(pid)
            self.assertIn("busy", [j["state"] for j in self.status()])
            p.send_signal(sig)
            p.communicate(timeout=5)
            if sig == signal.SIGTERM:
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
            else:
                # SIGKILL cannot run supervisor cleanup. Reconcile, never redispatch.
                os.killpg(pid, signal.SIGKILL)
            before = (job / "journal.bin").read_bytes()
            self.run_queue()
            self.assertEqual(self.status()[-1]["state"], "attention")
            self.assertEqual(before, (job / "journal.bin").read_bytes())
            self.assertFalse(list(job.glob("result-*")))

    def test_corrupt_missing_and_orphan_marker(self):
        broken, healthy = self.submit(), self.submit()
        journal = broken / "journal.bin"
        data = journal.read_bytes()
        journal.write_bytes(b"bad!" + data[4:])
        self.run_queue()
        self.assertEqual([j["state"] for j in self.status()], ["attention", "complete"])
        orphan = self.submit()
        (orphan / "dispatch-00000000000000000001").write_bytes(b"orphan")
        self.run_queue()
        self.assertEqual(self.status()[-1]["state"], "attention")
        self.assertFalse(list(orphan.glob("worker.stdout-*")))
        missing = self.submit()
        (missing / "options.bin").unlink()
        self.assertEqual(self.status()[-1]["state"], "attention")
        hidden = self.queue / "jobs/.pending-unpublished"
        hidden.mkdir()
        self.assertEqual(len(self.status()), 4)
        self.assertTrue(healthy.exists())

    def test_policy_and_malformed_worker(self):
        capsule = json.loads(self.capsule.read_text())
        capsule["permissions"]["planning"] = "ASK_ALWAYS"
        self.capsule.write_text(json.dumps(capsule))
        denied = self.submit()
        self.run_queue()
        self.assertEqual(self.status()[0]["state"], "attention")
        self.assertFalse(list(denied.glob("dispatch-*")))
        capsule["permissions"]["planning"] = "AUTO_LOCAL"
        self.capsule.write_text(json.dumps(capsule))
        invalid = self.submit()
        self.run_queue(worker=self.worker("malformed"))
        self.assertEqual(self.status()[1]["state"], "attention")
        self.assertTrue(list(invalid.glob("worker.stdout-*")))
        self.assertFalse(list(invalid.glob("result-*")))
        self.run_queue()
        self.assertEqual(self.status()[1]["state"], "attention")

    def test_usage_and_paths(self):
        self.call("daemon", "run", self.queue, code=2)
        self.call("daemon", "run", self.queue, "--worker", "relative", code=1)
        self.call("daemon", "init", self.queue, code=1)
        linked = self.root / "linked"
        linked.symlink_to(self.queue, target_is_directory=True)
        self.call("daemon", "status", linked, code=1)

    def test_prior_evidence_corruption(self):
        job = self.submit()
        self.run_queue("--once")
        result = json.loads((job / "result-00000000000000000001").read_text())
        digest = result["evidence_digest"]
        artifact = job / "evidence/objects/sha256" / digest[:2] / digest[2:]
        artifact.chmod(0o600)
        artifact.write_bytes(b"corrupted")
        self.run_queue()
        self.assertEqual(self.status()[0]["state"], "attention")
        self.assertFalse((job / "worker.stdout-00000000000000000002").exists())

    def test_descendant_termination(self):
        job = self.submit()
        self.run_queue(worker=self.worker("descendant"))
        self.assertEqual(self.status()[0]["state"], "attention")
        time.sleep(2.2)
        self.assertFalse((job / "evidence/descendant-survived").exists())


if __name__ == "__main__":
    unittest.main()
