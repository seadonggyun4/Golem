import concurrent.futures
import importlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib

LIBRARY, ROOT = Path(sys.argv.pop(1)).resolve(), Path(sys.argv.pop(1)).resolve()
if len(sys.argv) > 1 and sys.argv[1] == "--installed":
    sys.argv.pop(1)
else:
    sys.path.insert(0, str(ROOT / "bindings/python/src"))
binding = importlib.import_module("golem_runtime")


class BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = binding.Engine(LIBRARY)
        cls.capsule = (ROOT / "samples/work-capsules/basic.json").read_bytes()
        cls.journal = bytes.fromhex((ROOT / "tests/c/fixtures/journal/v1_default.hex").read_text())

    def test_validate(self):
        a = self.engine.validate(self.capsule)
        self.assertTrue(a["valid"])
        self.assertEqual(a["stages"], ["planning", "ux", "publishing", "development", "qa", "audit"])
        self.assertEqual(a, self.engine.validate(json.loads(self.capsule)))
        self.assertEqual(a, self.engine.validate(self.capsule.decode()))
        a["stages"].clear()
        self.assertEqual(len(self.engine.validate(self.capsule)["stages"]), 6)

    def test_invalid_capsule(self):
        for data in (b'{}', b'{"id":"a","id":"b"}', b'\xff', self.capsule + b'\0', b'a' * 131073):
            with self.assertRaises(binding.GolemError) as error:
                self.engine.validate(data)
            self.assertIsInstance(error.exception.status, int)
        invalid = json.loads(self.capsule); invalid["stages"] = ["planning", "planning"]
        with self.assertRaises(binding.GolemError): self.engine.validate(invalid)
        with self.assertRaises(TypeError): self.engine.validate(42)

    def test_replay(self):
        result = self.engine.replay(self.journal)
        self.assertEqual(result["state"], "SUCCEEDED")
        self.assertEqual(result["journal_records"], "13")
        self.assertEqual(int(result["journal_bytes"]), len(self.journal))
        self.assertFalse(result["acceptance_verified"])
        self.assertFalse(result["bundle_verified"])
        self.assertEqual(result, self.engine.replay(memoryview(self.journal)))
        self.assertEqual(result, self.engine.replay(bytearray(self.journal)))

    def test_unfinished(self):
        created_size = 32 + struct.unpack_from('<I', self.journal, 12)[0]
        ready = self.engine.replay(self.journal[:created_size])
        self.assertEqual(ready["state"], "READY")
        running = self.engine.replay(self.journal[:created_size + 64])
        self.assertEqual(running["state"], "RUNNING")
        self.assertEqual(running["recovery_action"], "RECONCILE_ATTEMPT")

    def test_invalid_replay(self):
        invalid = bytes.fromhex((ROOT / "tests/c/fixtures/journal/v1_invalid_transition.hex").read_text())
        for data in (b'', self.journal[:-1], b'X' + self.journal[1:], invalid):
            with self.assertRaises(binding.GolemError): self.engine.replay(data)
        with self.assertRaises(TypeError): self.engine.replay("journal.bin")

    def test_other_states_and_utf8(self):
        for name, expected in (("reentry", "SUCCEEDED"), ("cancelled", "CANCELLED")):
            data = bytes.fromhex((ROOT / f"tests/c/fixtures/journal/v1_{name}.hex").read_text())
            self.assertEqual(self.engine.replay(data)["state"], expected)
        first_size = 32 + struct.unpack_from('<I', self.journal, 12)[0]
        first = bytearray(self.journal[:first_size])
        stages = struct.unpack_from('<I', first, 36)[0]
        run_id = 32 + 8 + 4 * stages + 4 * 12 + 4 * 6 + 4
        first[run_id] = 255
        first[24:28] = b'\0' * 4
        struct.pack_into('<I', first, 24, zlib.crc32(first))
        with self.assertRaises(binding.GolemError) as error:
            self.engine.replay(first)
        self.assertEqual(error.exception.status, 3)

    def test_parallel_and_repeated(self):
        def run(_):
            self.engine.validate(self.capsule)
            return self.engine.replay(self.journal)["state"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(run, range(100))), ["SUCCEEDED"] * 100)

    def test_loading(self):
        with self.assertRaises(ValueError): binding.Engine("relative.so")
        with self.assertRaises(FileNotFoundError): binding.Engine(LIBRARY.parent / "missing-library.so")


if __name__ == "__main__":
    unittest.main()
