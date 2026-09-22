"""Hard-crash and byte-prefix recovery, including repeated recovery with no dispatch."""
import fcntl
import json
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib

CLI, RUNNER, ROOT = (str(Path(p).resolve()) for p in sys.argv[1:4])
CASE = sys.argv[4]
REPAIR_RUNNER = str(Path(sys.argv[5]).resolve())
sys.argv = [sys.argv[0]]


class CrashRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="recovery-", dir=ROOT)
        self.root = Path(self.temp.name)
        self.queue = self.root / "queue"
        self.calls = self.root / "calls"
        self.call("init", self.root / "project")
        self.call("daemon", "init", self.queue)
        self.call("daemon", "submit", self.queue, self.root / "project/capsule.json")
        self.job = self.queue / "jobs/00000000000000000001"

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args, code=0):
        p = subprocess.run([CLI, *map(str, args)], capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, code, (p.stdout, p.stderr))
        return json.loads(p.stdout) if code == 0 else None

    def run_helper(self, point="none"):
        p = subprocess.run([RUNNER, str(self.queue), point, str(self.calls)], capture_output=True, timeout=30)
        self.assertEqual(p.returncode, 0 if point == "none" else -signal.SIGKILL, p.stderr)

    def history(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def snapshot(self):
        return {p.relative_to(self.queue): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.queue.rglob("*") if p.is_file()}

    def recover(self):
        return self.call("daemon", "recover", self.queue)

    def test_boundaries(self):
        self.run_helper(CASE)
        before_calls = self.history()
        result = self.recover()
        self.assertEqual(before_calls, self.history())
        before = self.snapshot()
        self.assertEqual(self.recover()["recovery"]["repaired"], "0")
        self.assertEqual(before, self.snapshot())
        recoverable = CASE in ("before-start", "finish-intent", "finished")
        self.assertEqual(result["jobs"][0]["state"], "ready" if recoverable else "attention")
        self.run_helper()
        expected = [str(i) for i in range(1, 7)] if recoverable else before_calls
        self.assertEqual(self.history(), expected)
        self.run_helper()
        self.assertEqual(self.history(), expected)

    def test_prefixes(self):
        self.run_helper()
        journal = self.job / "journal.bin"
        original = journal.read_bytes()
        frames = sorted(self.job.glob("intent-*"))
        prefix = len(original) - len(frames[-1].read_bytes())
        for length in [0, 1, 31, len(frames[0].read_bytes()), prefix, prefix + 1, len(original) - 1]:
            journal.write_bytes(original[:length])  # Fault injection in a disposable queue.
            self.assertEqual(self.recover()["recovery"]["repaired"], "1")
            self.assertEqual(journal.read_bytes(), original)
            self.assertEqual(self.recover()["recovery"]["repaired"], "0")
            self.run_helper()
            self.assertEqual(self.history(), [str(i) for i in range(1, 7)])

    def test_corrupt(self):
        self.run_helper()
        journal = self.job / "journal.bin"
        original = journal.read_bytes()
        if CASE == "conflict":
            journal.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        elif CASE == "missing-intent":
            (self.job / "intent-00000000000000000002").unlink()
        elif CASE == "corrupt-intent":
            (self.job / "intent-00000000000000000002").write_bytes(b"corrupt")
        elif CASE == "missing-tail-intent":
            sorted(self.job.glob("intent-*"))[-1].unlink()
        elif CASE == "metadata":
            options = self.job / "options.bin"
            options.write_bytes(options.read_bytes()[:-1] + b"x")
            journal.write_bytes(original[:-1])
        elif CASE == "legacy":
            (self.job / "recovery.meta").unlink()
        elif CASE == "symlink":
            frame = self.job / "intent-00000000000000000002"
            backup = self.root / "frame"
            frame.rename(backup)
            frame.symlink_to(backup)
        elif CASE == "missing-journal":
            journal.unlink()
        elif CASE == "invalid-transition":
            # Valid framing/CRC, but FINISHED without STARTED is not recoverable.
            frame = bytearray((self.job / "intent-00000000000000000003").read_bytes())
            struct.pack_into("<Q", frame, 16, 2)
            struct.pack_into("<I", frame, 24, 0)
            struct.pack_into("<I", frame, 24, zlib.crc32(frame))
            (self.job / "intent-00000000000000000002").write_bytes(frame)
            journal.write_bytes((self.job / "intent-00000000000000000001").read_bytes())
        before = self.snapshot()
        result = self.recover()
        self.assertEqual(result["recovery"]["attention"], "1")
        self.assertEqual(result["recovery"]["repaired"], "0")
        self.assertEqual(before, self.snapshot())
        self.run_helper()
        self.assertEqual(self.history(), [str(i) for i in range(1, 7)])

    def test_locks(self):
        for path, root_lock in [(self.queue / ".daemon.lock", True), (self.job / "journal.bin", False)]:
            with path.open("rb") as locked:
                fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if root_lock:
                    self.call("daemon", "recover", self.queue, code=1)
                else:
                    self.assertEqual(self.recover()["recovery"]["busy"], "1")
        self.assertEqual(self.recover()["recovery"]["ready"], "1")
        self.assertEqual(self.history(), [])

    def test_claim(self):
        self.run_helper("execute")
        # Simulate loss of both journal and intent suffix, but retain dispatch claim.
        journal = self.job / "journal.bin"
        journal.write_bytes((self.job / "intent-00000000000000000001").read_bytes())
        (self.job / "intent-00000000000000000002").unlink()
        self.run_helper()
        self.assertEqual(self.history(), ["1"])
        self.assertEqual(self.recover()["jobs"][0]["state"], "attention")

    def test_recrash(self):
        self.run_helper()
        journal = self.job / "journal.bin"
        original = journal.read_bytes()
        journal.write_bytes(original[:-64])
        for n in range(3):
            p = subprocess.run([REPAIR_RUNNER, str(self.queue)], capture_output=True, timeout=15)
            self.assertEqual(p.returncode, -signal.SIGKILL, p.stderr)
            self.assertEqual(journal.read_bytes(), original[:len(original) - 63 + n])
        self.assertEqual(self.recover()["recovery"]["repaired"], "1")
        self.assertEqual(journal.read_bytes(), original)
        self.run_helper()
        self.assertEqual(self.history(), [str(i) for i in range(1, 7)])

    def test_publication(self):
        with (self.queue / ".queue.lock").open("rb") as locked:
            fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
            p = subprocess.Popen([RUNNER, str(self.queue), "none", str(self.calls)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                time.sleep(0.1)
                self.assertIsNone(p.poll())
                fcntl.flock(locked, fcntl.LOCK_UN)
                _, error = p.communicate(timeout=15)
                self.assertEqual(p.returncode, 0, error)
            finally:
                if p.poll() is None:
                    p.kill()
                p.communicate(timeout=5)
        self.assertEqual(self.history(), [str(i) for i in range(1, 7)])

    def test_unpublished(self):
        names = [".intent-00000000000000000002.pending", ".intent-00000000000000000002.pending-orphan"]
        for name in names:
            (self.job / name).write_bytes(b"partial unpublished frame")
        self.run_helper()
        self.assertEqual(self.history(), [str(i) for i in range(1, 7)])
        for name in names:
            self.assertEqual((self.job / name).read_bytes(), b"partial unpublished frame")
        self.assertEqual(self.recover()["recovery"]["complete"], "1")


if CASE in ("before-start", "start-intent", "started", "claim", "execute", "finish-intent", "finished"):
    method = "test_boundaries"
elif CASE == "prefixes":
    method = "test_prefixes"
elif CASE == "locks":
    method = "test_locks"
elif CASE == "claim-retained":
    method = "test_claim"
elif CASE == "recrash":
    method = "test_recrash"
elif CASE == "publication":
    method = "test_publication"
elif CASE == "unpublished":
    method = "test_unpublished"
else:
    method = "test_corrupt"
result = unittest.TextTestRunner().run(unittest.TestSuite([CrashRecovery(method)]))
sys.exit(not result.wasSuccessful())
