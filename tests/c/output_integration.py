"""Native default presentation and immutable payload retrieval, no provider calls."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import os
import errno
import pty
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI, HELPER, SOURCE = (str(Path(sys.argv.pop(1)).resolve()) for _ in range(3))
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--evidence-root", type=Path)
options, rest = parser.parse_known_args()
sys.argv = [sys.argv[0], *rest]
EVIDENCE = options.evidence_root
if EVIDENCE:
    EVIDENCE.mkdir(mode=0o700)


class Output(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="golem-cli-output-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.store = self.root / "private"
        self.file = self.root / "payload.json"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GOLEM_CLI_OUTPUT")}
        self.env["HOME"] = str(self.root)
        self.value = {"schema_version": 1, "state": "OPEN", "generation": 2,
                      "acceptance_verified": False, "committed": True,
                      "metadata": {"notes": "fixture " * 2000}, "nullable": None}
        self.payload(self.value)

    def payload(self, value):
        self.file.write_text(json.dumps(value, separators=(",", ":")))

    def run_cli(self, *args, code=0, env=None):
        p = subprocess.run([CLI, *map(str, args)], capture_output=True, env=env or self.env, timeout=30)
        self.assertEqual(p.returncode, code, (p.stdout, p.stderr))
        return p

    def emit(self, *options, env=None, code=0):
        p = subprocess.run([HELPER, *map(str, options), "emit", str(self.file)],
                           capture_output=True, env=env or self.env, timeout=30)
        self.assertEqual(p.returncode, code, p.stderr)
        return p

    def test_default_pipe_compact_and_raw_exact(self):
        p = self.emit()
        view = json.loads(p.stdout)
        self.assertEqual(view["schema"], "golem.cli-output.v1")
        self.assertTrue(view["partial"])
        self.assertTrue(view["read_before_action"])
        self.assertFalse(view["execution_authority"])
        self.assertFalse(view["fields"]["acceptance_verified"])
        self.assertIsNone(view["fields"]["nullable"])
        self.assertEqual(view["omitted"], ["metadata"])
        self.assertLessEqual(len(p.stdout), 2049)
        raw = self.run_cli(*view["next_read_argv"][1:])
        self.assertEqual(raw.stdout, self.file.read_bytes() + b"\n")
        self.assertEqual(hashlib.sha256(raw.stdout[:-1]).hexdigest(), view["evidence"]["sha256"])
        self.assertEqual(int(view["evidence"]["bytes"]), len(raw.stdout) - 1)
        self.assertEqual((self.root / ".golem-cli-output").stat().st_mode & 0o777, 0o700)

    def test_full_exact_no_store(self):
        p = self.emit("--output-mode", "full")
        self.assertEqual(p.stdout, self.file.read_bytes() + b"\n")
        self.assertFalse((self.root / ".golem-cli-output").exists())

    def test_default_tty_also_compact(self):
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([HELPER, "emit", str(self.file)], stdout=slave,
                                       stderr=subprocess.PIPE, env=self.env)
            os.close(slave)
            slave = -1
            data = b""
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    break
                if not chunk:
                    break
                data += chunk
            _, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(json.loads(data)["view"], "compact")
        finally:
            os.close(master)
            if slave >= 0:
                os.close(slave)

    def test_protected_semantics_never_truncated_to_fit(self):
        self.value["permissions"] = {"action" + str(i): "REQUIRES_REVIEW" for i in range(100)}
        self.payload(self.value)
        self.assertEqual(self.emit().stdout, self.file.read_bytes() + b"\n")

    def test_small_and_unknown_json_shapes_remain_full(self):
        for value in ({"state": "OPEN"}, ["large " * 1000], {"schema_version": 987, "extra": "short"}):
            self.payload(value)
            self.assertEqual(self.emit().stdout, self.file.read_bytes() + b"\n")
        self.assertFalse((self.root / ".golem-cli-output").exists())

    def test_malformed_json_never_projected(self):
        for payload in (b"not json" * 1000, b'{"a":1,"a":2,"long":"' + b"x" * 4000 + b'"}'):
            self.file.write_bytes(payload)
            self.assertEqual(self.emit().stdout, payload + b"\n")

    def test_negative_nested_states_preserved_at_exit_zero(self):
        for state in ("BLOCKED", "FAIL", "ERROR", "STALE", "DENIED", "NOT_DONE", "SKIPPED",
                      "RECOVERY_REQUIRED", "NOT_EXECUTED", "UNKNOWN", "PARTIALLY_VERIFIED"):
            with self.subTest(state=state):
                self.value["metadata"]["deep"] = [{"status": state}]
                self.payload(self.value)
                self.assertEqual(self.emit().stdout, self.file.read_bytes() + b"\n")
        self.assertFalse((self.root / ".golem-cli-output").exists())

    def test_diagnostics_and_approvals_not_hidden(self):
        for key, value in (("errors", ["precise error"]), ("reason", "long reason " * 500),
                           ("allowed", False), ("authorized", False), ("lease_valid", False),
                           ("human_approval", {"required": True}), ("requirements", ["gate"])):
            self.value["metadata"]["nested"] = {key: value}
            self.payload(self.value)
            self.assertEqual(self.emit().stdout, self.file.read_bytes() + b"\n")

    def test_no_expansion_and_summary_budget_fallback(self):
        self.payload({"item" + str(i): "a" * 128 for i in range(32)})
        self.assertEqual(self.emit().stdout, self.file.read_bytes() + b"\n")
        self.assertFalse((self.root / ".golem-cli-output").exists())

    def test_invalid_options_before_effects(self):
        for options in (("--output-mode", "bad"), ("--output-store", "relative"),
                        ("--output-mode", "full", "--output-mode", "compact"), ("--output-mode",)):
            p = self.run_cli(*options, "init", self.root / "never", code=2)
            self.assertFalse(p.stdout)
            self.assertFalse((self.root / "never").exists())

    def test_environment_and_flag_precedence(self):
        env = dict(self.env, GOLEM_CLI_OUTPUT="full")
        self.assertEqual(self.emit(env=env).stdout, self.file.read_bytes() + b"\n")
        self.assertEqual(json.loads(self.emit("--output-mode", "compact", env=env).stdout)["view"], "compact")
        self.run_cli("--version", code=2, env=dict(self.env, GOLEM_CLI_OUTPUT="invalid"))

    def test_private_store_unavailable_preserves_outcome_and_payload(self):
        self.store.mkdir(mode=0o755)
        self.store.chmod(0o755)
        p = self.emit("--output-store", self.store)
        self.assertEqual(p.stdout, self.file.read_bytes() + b"\n")
        diagnostic = json.loads(p.stderr)
        self.assertEqual(diagnostic["fallback"], "full")
        self.assertFalse(diagnostic["retry_effect"])
        self.assertFalse((self.store / "objects").exists())

    def test_symlink_and_traversal_store_rejected_without_chmod(self):
        target = self.root / "target"
        target.mkdir(mode=0o700)
        self.store.symlink_to(target, target_is_directory=True)
        for path in (self.store, str(target) + "/../other"):
            p = self.emit("--output-store", path)
            self.assertEqual(p.stdout, self.file.read_bytes() + b"\n")
            self.assertIn(b"OUTPUT_STORE_UNAVAILABLE", p.stderr)
        self.assertFalse(list(target.iterdir()))

    def test_cache_corruption_is_detected_not_repaired(self):
        view = json.loads(self.emit("--output-store", self.store).stdout)
        key = view["evidence"]["sha256"]
        path = self.store / "objects/sha256" / key[:2] / key[2:]
        path.chmod(0o600)
        path.write_bytes(b"tampered")
        p = self.run_cli("--output-store", self.store, "output", "read", key, code=1)
        self.assertFalse(p.stdout)
        self.assertIn(b"do not rerun effects", p.stderr)
        p = self.emit("--output-store", self.store)
        self.assertEqual(p.stdout, self.file.read_bytes() + b"\n")
        self.assertEqual(path.read_bytes(), b"tampered")

    def test_read_missing_and_invalid_digest_never_creates_store(self):
        for key in ("0" * 64, "../escape", "BAD"):
            p = self.run_cli("--output-store", self.store, "output", "read", key, code=1)
            self.assertFalse(p.stdout)
            self.assertFalse(self.store.exists())

    def test_concurrent_identical_payload_publication(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.emit("--output-store", self.store), range(12)))
        for p in results:
            self.assertFalse(p.stderr)
            self.assertEqual(p.stdout, results[0].stdout)
        self.assertEqual(len(list((self.store / "objects/sha256").glob("*/*"))), 1)

    def test_cli_error_exit_and_diagnostics_unchanged(self):
        a = self.run_cli("session", "call", self.root / "missing", self.file, code=1)
        b = self.run_cli("--output-mode", "full", "session", "call", self.root / "missing", self.file, code=1)
        self.assertEqual((a.stdout, a.stderr), (b.stdout, b.stderr))

    def test_templates_and_requested_artifacts_unchanged(self):
        for command in (("role", "template", "implementer"), ("workflow", "template", "show", "feature")):
            self.assertEqual(self.run_cli(*command).stdout, self.run_cli("--output-mode", "full", *command).stdout)
        self.assertFalse((self.root / ".golem-cli-output").exists())

    def test_real_mutation_receipt_retrieved_without_reexecuting(self):
        samples = Path(SOURCE) / "samples/documents"
        spec = json.loads((samples / "work.json").read_text())
        meta = json.loads((samples / "planning.json").read_text())
        ids = [f"REQ-{i:03d}" for i in range(160)]
        spec["acceptance"] = [{"id": key, "criterion": "Fixture requirement"} for key in ids]
        meta["requirement_ids"] = ids
        body = (samples / "planning.md").read_text().replace(
            "REQ-1 requires byte-identical retrieval of the committed revision.",
            " ".join(ids) + " require byte-identical retrieval of the committed revision.")
        spec_path, meta_path, body_path = (self.root / name for name in ("spec.json", "meta.json", "body.md"))
        spec_path.write_text(json.dumps(spec))
        meta_path.write_text(json.dumps(meta))
        body_path.write_text(body)
        work = self.root / "work"
        self.run_cli("work", "start", work, spec_path)
        p = self.run_cli("document", "submit", work, meta_path, body_path, "submission")
        view = json.loads(p.stdout)
        self.assertEqual(view["schema"], "golem.cli-output.v1")
        self.assertTrue(view["fields"]["committed"])
        events = {path.name: path.read_bytes() for path in (work / "events").iterdir()}
        meta_path.unlink()
        body_path.unlink()
        raw = self.run_cli(*view["next_read_argv"][1:])
        observed = self.run_cli("--output-mode", "full", "document", "inspect", work, "planning", "1")
        self.assertEqual(json.loads(raw.stdout), json.loads(observed.stdout))
        self.assertEqual(len(json.loads(raw.stdout)["metadata"]["requirement_ids"]), 160)
        self.assertEqual(events, {path.name: path.read_bytes() for path in (work / "events").iterdir()})
        self.assertLess(len(p.stdout), len(raw.stdout))
        if EVIDENCE:
            (EVIDENCE / "compact.json").write_bytes(p.stdout)
            (EVIDENCE / "full.json").write_bytes(raw.stdout)
            measurement = {
                "schema": "golem.cli-output-measurement.v1", "fixture": "synthetic document submission",
                "cli_sha256": hashlib.sha256(Path(CLI).read_bytes()).hexdigest(),
                "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "full_bytes": len(raw.stdout), "compact_bytes": len(p.stdout),
                "full_sha256": hashlib.sha256(raw.stdout).hexdigest(),
                "compact_sha256": hashlib.sha256(p.stdout).hexdigest(),
                "readback_equal": True, "work_events_unchanged_by_readback": True,
                "provider_tokens": None, "end_to_end_savings": None,
                "limitations": "Includes output framing, excludes input prompts and subsequent raw retrieval."
            }
            (EVIDENCE / "measurement.json").write_text(json.dumps(measurement, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
