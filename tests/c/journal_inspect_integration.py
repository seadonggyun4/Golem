"""Independent chain oracle and non-destructive salvage contract."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = str(Path(sys.argv.pop(1)).resolve())
FIXTURES = Path(__file__).parent / "fixtures/journal"


class JournalInspection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source.bin"
        self.good = bytes.fromhex((FIXTURES / "v1_default.hex").read_text())
        self.source.write_bytes(self.good)

    def call(self, *args, ok=True):
        result = subprocess.run([CLI, "journal", *map(str, args)], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        return json.loads(result.stdout) if result.stdout else None

    def salvage(self, data, destination="recovered", ok=True, digest=None):
        self.source.write_bytes(data)
        result = self.call("salvage", self.source, self.root / destination, "--expect-source",
                           digest or hashlib.sha256(data).hexdigest(), "--accept-truncated-tail", ok=ok)
        self.assertEqual(self.source.read_bytes(), data)
        return result

    def test_chain_independent_oracle_and_anchor(self):
        # v1 frame payload length is little-endian u32 at byte 12.
        position, head, records = 0, bytes(32), 0
        while position < len(self.good):
            size = 32 + int.from_bytes(self.good[position + 12:position + 16], "little")
            frame = self.good[position:position + size]
            head = hashlib.sha256(b"golem.journal.chain.v1" + head + hashlib.sha256(frame).digest()).digest()
            position += size
            records += 1
        report = self.call("inspect", self.source, "--expect-chain", head.hex())
        self.assertEqual(report["chain_head"], head.hex())
        self.assertEqual(report["source_digest"], hashlib.sha256(self.good).hexdigest())
        self.assertEqual(int(report["records"]), records)
        self.assertFalse(report["authenticated"])
        self.call("inspect", self.source, "--expect-chain", "f" * 64, ok=False)

    def test_torn_tail_export_is_exact_prefix(self):
        data = self.good[:-1]
        report = self.salvage(data)
        recovered = self.root / "recovered"
        self.assertGreater(int(report["discarded_bytes"]), 0)
        self.assertEqual((recovered / "journal.bin").read_bytes(), data[:int(report["valid_bytes"])])
        self.assertEqual(json.loads((recovered / "salvage.json").read_text()), report)
        self.call("inspect", recovered / "journal.bin")
        result = subprocess.run([CLI, "replay", str(recovered / "journal.bin")], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.salvage(data, ok=False)  # existing destination must not be replaced

    def test_every_partial_last_frame_boundary(self):
        # Inspect all byte cuts, not just the last byte. Full prefix boundaries
        # are structurally valid and cannot establish completeness without an anchor.
        for cut in range(len(self.good) - 32, len(self.good)):
            self.source.write_bytes(self.good[:cut])
            report = self.call("inspect", self.source, ok=False)
            self.assertLessEqual(int(report["valid_bytes"]), cut)

    def test_corruption_and_bad_transition_are_not_salvaged(self):
        corrupt = bytearray(self.good)
        corrupt[35] ^= 1
        self.salvage(bytes(corrupt), ok=False)
        bad = bytes.fromhex((FIXTURES / "v1_invalid_transition.hex").read_text())
        self.salvage(bad + b"torn", destination="semantic", ok=False)
        self.assertFalse((self.root / "semantic").exists())

    def test_complete_empty_and_stale_source_rejected(self):
        self.salvage(self.good, ok=False)
        self.salvage(b"", ok=False)
        self.salvage(self.good[:-1], digest="0" * 64, ok=False)
        self.assertFalse((self.root / "recovered").exists())

    def test_symlink_and_locked_source_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.source)
        self.call("inspect", link, ok=False)
        with self.source.open("rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.call("inspect", self.source, ok=False)


if __name__ == "__main__":
    unittest.main()
