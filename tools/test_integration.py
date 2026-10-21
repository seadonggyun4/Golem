"""D1 isolated local approval, registry and read-backend contracts."""
import copy
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import integration_backend as backend
import integration_contract as c
import integration_registry as r


class Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="golem-integration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project with spaces"
        self.work = self.project / ".golem/works/a"
        (self.work / "events").mkdir(parents=True)
        (self.work / "events/00000001.evt").write_bytes(b"synthetic genesis; native tests use real frames")
        self.sdk = self.root / "sdk.md"
        self.sdk.write_text("Synthetic SDK\n")
        self.cli = self.root / "golem-fixture"
        self.cli.write_text("#!" + sys.executable + "\n" +
            "import json, os, sys\n"
            "args=sys.argv[1:]\n"
            "q=json.load(open(args[-1]))\n"
            "assert args[:2] == ['--output-mode', 'full']\n"
            "assert not any(k in os.environ for k in ['GIT_PAGER','SECRET','HOME'])\n"
            "if args[2:4] == ['work','record']:\n"
            " print(json.dumps({'schema':'golem.work-record.v1','work_id':'a',"
            "'work_specification':{'work_id':'a'},'execution_authorized':False}))\n"
            "else: print(json.dumps({'observed':q,'authorization':'NONE'}))\n")
        self.cli.chmod(0o700)
        self.registry = r.Registry.create(self.root / "private-registry", approve_local_owner=True)
        self.enrollment = {"schema": "golem.integration-enrollment.v1",
            "project": r.describe("p", self.project, self.cli, [self.sdk], [("a", self.work)]),
            "grants": [{"schema": "golem.integration-grant.v1", "principal_id": "owner",
                "client_id": "client-a", "operations": ["status", "next", "record", "history"],
                "work_ids": ["a"], "destination": "LOCAL_HOST", "assurance": "LOCAL_COOPERATIVE"}]}

    def approve(self, action="approve"):
        plan = self.registry.plan(self.enrollment, action)
        return self.registry.apply(self.enrollment, plan["plan_sha256"], action=action, approve_local_owner=True)

    def query(self, operation="status"):
        return {"schema": "golem.integration-read.v1", "binding": {
            "schema": "golem.integration-client-binding.v1", "project_id": "p", "generation": 1,
            "principal_id": "owner", "client_id": "client-a", "assurance": "LOCAL_COOPERATIVE"},
            "work_id": "a", "operation": operation, "limit": 64, "cursor": None}

    def expect(self, code, call):
        with self.assertRaises(c.IntegrationError) as error:
            call()
        self.assertEqual(error.exception.code, code)

    def inventory(self):
        return {str(p.relative_to(self.project)): (p.stat().st_mode, c.sha(p.read_bytes()))
                for p in self.project.rglob("*") if p.is_file()}

    def test_plan_and_schema_generation_do_not_execute_or_change_project(self):
        before = self.inventory()
        with patch.object(subprocess, "Popen", side_effect=AssertionError("no launch")):
            plan = self.registry.plan(self.enrollment)
            self.assertEqual(plan["plan_sha256"], c.sha(c.encoded(plan["plan"])))
            for kind in c.CONTRACTS:
                self.assertEqual(c.schema(kind)["additionalProperties"], False)
        self.assertEqual(before, self.inventory())
        self.assertEqual(list(self.registry.root.iterdir()), [])

    def test_committed_schemas_match_single_source(self):
        for kind in c.CONTRACTS:
            path = Path(c.__file__).resolve().parents[1] / "samples/integration" / (kind + ".schema.json")
            self.assertEqual(json.loads(path.read_bytes()), c.schema(kind))

    def test_every_contract_field_is_required_and_closed(self):
        values = {"project": self.enrollment["project"], "grant": self.enrollment["grants"][0],
                  "binding": self.query()["binding"], "enrollment": self.enrollment, "read": self.query()}
        for kind, value in values.items():
            c.validate(kind, value)
            for key in value:
                broken = copy.deepcopy(value)
                del broken[key]
                self.expect("SCHEMA", lambda: c.validate(kind, broken))
            broken = {**value, "extra": True}
            self.expect("SCHEMA", lambda: c.validate(kind, broken))

    def test_approval_requires_owner_intent_and_exact_current_plan(self):
        plan = self.registry.plan(self.enrollment)
        self.expect("OWNER_APPROVAL_REQUIRED", lambda: self.registry.apply(self.enrollment, plan["plan_sha256"]))
        self.expect("PLAN_STALE", lambda: self.registry.apply(self.enrollment, "0" * 64, approve_local_owner=True))
        self.approve()
        self.expect("PLAN_STALE", lambda: self.registry.apply(self.enrollment, plan["plan_sha256"], approve_local_owner=True))

    def test_plan_wrapper_limit_blocks_before_publication(self):
        with patch.object(c, "LIMIT", len(c.encoded(self.enrollment)) + 100):
            self.expect("PLAN_LIMIT", lambda: self.registry.plan(self.enrollment))
        self.assertEqual(list(self.registry.root.iterdir()), [])

    def test_record_wrapper_limit_never_activates_unreadable_snapshot(self):
        plan = self.registry.plan(self.enrollment)
        with patch.object(c, "LIMIT", len(c.encoded(plan["plan"]))):
            self.expect("REGISTRY_RECORD_LIMIT", lambda: self.registry.apply(
                self.enrollment, plan["plan_sha256"], approve_local_owner=True))
        self.assertEqual(list(self.registry.root.iterdir()), [])

    def test_unicode_result_wrapper_is_bounded_not_silently_truncated(self):
        self.approve()
        native = {"schema": "golem.work-record.v1", "work_id": "a", "work_specification": {"work_id": "a"},
                  "execution_authorized": False, "note": "\uac00" * 120}
        self.assertLess(len(json.dumps(native, ensure_ascii=False).encode()), 1024)
        with patch.object(c, "MAX_NATIVE", 1024), patch.object(backend, "_native", return_value=(native, {})):
            self.expect("NATIVE_OUTPUT_LIMIT", lambda: backend.read(self.registry, self.query("record")))
        spool = next(self.registry.root.glob("read-*"))
        self.assertFalse((spool / "result.json").exists())
        self.assertNotIn("result", c.decode((spool / "failure.json").read_bytes()))

    def test_stale_pins_sdk_and_lineage_block(self):
        self.approve()
        for path in (self.sdk, self.cli, self.work / "events/00000001.evt"):
            old = path.read_bytes()
            path.write_bytes(old + b"changed")
            with self.assertRaises(c.IntegrationError):
                backend.read(self.registry, self.query())
            path.write_bytes(old)

    def test_foreign_principal_client_work_generation_and_unsupported_operation(self):
        self.approve()
        for field, value, code in (("principal_id", "foreign", "PRINCIPAL_SCOPE"),
                                  ("client_id", "foreign", "PRINCIPAL_SCOPE"),
                                  ("generation", 0, "GRANT_STALE"),
                                  ("project_id", "other", "PROJECT_APPROVAL_REQUIRED")):
            query = self.query()
            query["binding"][field] = value
            self.expect(code, lambda: backend.read(self.registry, query))
        query = self.query()
        query["work_id"] = "other"
        self.expect("GRANT_SCOPE", lambda: backend.read(self.registry, query))
        query = self.query()
        query["operation"] = "resume"
        self.expect("SCHEMA", lambda: backend.read(self.registry, query))

    def test_revocation_survives_missing_project_or_changed_pins(self):
        self.approve()
        self.sdk.unlink()
        record = self.approve("revoke")
        self.assertEqual(record["state"], "REVOKED")
        self.expect("PROJECT_APPROVAL_REQUIRED", lambda: backend.read(self.registry, self.query()))

    def test_native_reads_preserve_project_and_strip_inherited_environment(self):
        self.approve()
        before = self.inventory()
        with patch.dict(os.environ, {"GIT_PAGER": "do-not-run", "SECRET": "private", "GOLEM_RECORD_ROOT": "bad"}):
            for operation in ("status", "next", "record", "history"):
                result = backend.read(self.registry, self.query(operation))
                self.assertEqual(result["state"], "OBSERVED")
                self.assertFalse(result["execution_authorized"])
                output = Path(result["evidence_path"])
                self.assertTrue((output / "result.json").is_file())
                capture = c.decode((output / "record/execution/source-before.json").read_bytes())
                self.assertEqual(capture["status"], "NOT_OBSERVED")
        self.assertEqual(before, self.inventory())

    def test_missing_approval_does_not_launch_or_write_spool(self):
        with patch.object(backend.records, "capture", side_effect=AssertionError("no launch")):
            self.expect("PROJECT_APPROVAL_REQUIRED", lambda: backend.read(self.registry, self.query()))
        self.assertEqual(list(self.registry.root.iterdir()), [])

    def test_multiple_clients_keep_distinct_scopes_and_revoked_generation(self):
        second = copy.deepcopy(self.enrollment["grants"][0])
        second.update(client_id="client-b", operations=["status"])
        self.enrollment["grants"].append(second)
        self.approve()
        query = self.query()
        query["binding"]["client_id"] = "client-b"
        self.assertEqual(backend.read(self.registry, query)["state"], "OBSERVED")
        query["operation"] = "record"
        self.expect("GRANT_SCOPE", lambda: backend.read(self.registry, query))
        self.assertEqual(backend.read(self.registry, self.query())["state"], "OBSERVED")
        self.enrollment["grants"].pop()
        self.approve()
        self.expect("GRANT_STALE", lambda: backend.read(self.registry, self.query()))
        query["binding"]["generation"] = 2
        self.expect("PRINCIPAL_SCOPE", lambda: backend.read(self.registry, query))

    def test_native_error_keeps_raw_streams_and_failure_record(self):
        self.cli.write_text("#!/bin/sh\nprintf '{broken'; printf diagnostic >&2; exit 3\n")
        self.enrollment["project"]["cli"] = r.file_pin(self.cli)
        self.approve()
        self.expect("NATIVE_FAILURE", lambda: backend.read(self.registry, self.query()))
        spool = next(self.registry.root.glob("read-*"))
        self.assertEqual((spool / "record/stdout.log").read_bytes(), b"{broken")
        self.assertEqual((spool / "record/stderr.log").read_bytes(), b"diagnostic")
        self.assertTrue((spool / "failure.json").exists())

    def test_zero_exit_malformed_or_wrong_work_is_not_success(self):
        for reply, code in (("{broken", "JSON_INVALID"), ("{}", "WORK_IDENTITY"), ("[]", "NATIVE_CONTRACT")):
            self.cli.write_text("#!/bin/sh\nprintf '%s' '" + reply + "'\n")
            self.enrollment["project"]["cli"] = r.file_pin(self.cli)
            self.approve()
            query = self.query()
            with self.registry.locked():
                current, _ = self.registry._load("p")
            query["binding"]["generation"] = current["generation"]
            self.expect(code, lambda: backend.read(self.registry, query))

    def test_registry_modes_corrupt_pointer_and_snapshot(self):
        self.registry.root.chmod(0o755)
        self.expect("PRIVATE_MODE", lambda: r.Registry(self.registry.root))
        self.registry.root.chmod(0o700)
        self.approve()
        pointer = self.registry.root / "p.current"
        value = c.decode(pointer.read_bytes())
        snapshot = self.registry.root / f"p.1.{value['sha256']}.json"
        snapshot.write_bytes(snapshot.read_bytes() + b" ")
        self.expect("REGISTRY_CORRUPT", lambda: backend.read(self.registry, self.query()))

    def test_copied_registry_and_producer_drift_require_review(self):
        self.approve()
        with patch.object(r, "producer", return_value={**r.producer(), "execution_record.py": "0" * 64}):
            self.expect("PRODUCER_CHANGED", lambda: backend.read(self.registry, self.query()))
        moved = self.root / "registry-copy"
        shutil.copytree(self.registry.root, moved)
        other = r.Registry(moved)
        self.expect("REGISTRY_CHANGED", lambda: backend.read(other, self.query()))

    def test_partial_publish_does_not_activate_and_preserves_orphan(self):
        original = self.registry._publish
        def publish(path, data, replace=False):
            if replace:
                raise OSError("interruption before pointer")
            original(path, data, replace)
        with patch.object(self.registry, "_publish", side_effect=publish):
            with self.assertRaises(OSError):
                self.approve()
        self.assertEqual(len(list(self.registry.root.glob("p.1.*.json"))), 1)
        self.expect("PROJECT_APPROVAL_REQUIRED", lambda: backend.read(self.registry, self.query()))
        self.approve()

    def test_shared_read_lock_prevents_revocation_race(self):
        self.approve()
        fd = os.open(self.registry.root, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            self.expect("REGISTRY_BUSY", lambda: self.approve("revoke"))
        finally:
            os.close(fd)

    def test_read_holds_admission_against_revoke_and_allows_two_clients(self):
        self.approve()
        entered, release = threading.Event(), threading.Event()
        native = backend._native
        def slow(*args):
            entered.set()
            self.assertTrue(release.wait(10))
            return native(*args)
        with ThreadPoolExecutor(max_workers=2) as pool:
            with patch.object(backend, "_native", side_effect=slow):
                read = pool.submit(backend.read, self.registry, self.query())
                try:
                    self.assertTrue(entered.wait(10))
                    self.expect("REGISTRY_BUSY", lambda: self.approve("revoke"))
                finally:
                    release.set()
                self.assertEqual(read.result(timeout=20)["state"], "OBSERVED")
            futures = [pool.submit(backend.read, self.registry, self.query()) for unused in range(2)]
            self.assertTrue(all(f.result(timeout=20)["state"] == "OBSERVED" for f in futures))

    def test_timeout_and_quota_fail_without_retry(self):
        self.cli.write_text("#!" + sys.executable + "\nimport time;time.sleep(30)\n")
        self.enrollment["project"]["cli"] = r.file_pin(self.cli)
        self.approve()
        with patch.object(backend, "TIMEOUT_SECONDS", .1):
            self.expect("NATIVE_FAILURE", lambda: backend.read(self.registry, self.query()))
        self.assertEqual(len(list(self.registry.root.glob("read-*"))), 1)
        for index in range(256):
            (self.registry.root / f"read-quota-{index}").mkdir()
        self.expect("AUDIT_QUOTA", lambda: backend.read(self.registry, self.query()))

    def test_path_replacement_symlinks_hardlinks_and_private_scope(self):
        alias = self.root / "alias"
        alias.symlink_to(self.project, target_is_directory=True)
        self.expect("SYMLINK", lambda: r.identity(alias))
        linked = self.root / "linked"
        os.link(self.sdk, linked)
        self.expect("UNSAFE_FILE", lambda: r.regular(linked))
        linked.unlink()
        self.approve()
        moved = self.work.with_name("old")
        self.work.rename(moved)
        (self.work / "events").mkdir(parents=True)
        shutil.copyfile(moved / "events/00000001.evt", self.work / "events/00000001.evt")
        self.expect("WORK_CHANGED", lambda: backend.read(self.registry, self.query()))
        shutil.rmtree(self.work)
        moved.rename(self.work)
        nested = r.Registry.create(self.project / "private", approve_local_owner=True)
        self.expect("REGISTRY_SCOPE", lambda: nested.plan(self.enrollment))

    def test_queries_reject_smuggled_native_keys_and_authenticated_claims(self):
        for key, value in (("argv", ["resume"]), ("operation", "begin"), ("limit", True), ("limit", 0)):
            query = self.query()
            query[key] = value
            self.expect("SCHEMA", lambda: c.validate("read", query))
        query = self.query()
        query["binding"]["assurance"] = "AUTHENTICATED"
        self.expect("SCHEMA", lambda: c.validate("read", query))

    def test_schema_unknown_missing_duplicate_nonfinite_unicode_and_depth(self):
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b'"\xff"', b'"\\ud800"',
                     b'{"\\ud800":null}', b'"\\u0000"', b'[' * 30 + b']' * 30):
            with self.assertRaises(c.IntegrationError):
                c.decode(data)
        for value in (True, 1.2, "1", -1):
            query = self.query()
            query["binding"]["generation"] = value
            self.expect("SCHEMA", lambda: c.validate("read", query))
        value = copy.deepcopy(self.enrollment)
        value["project"]["works"].append(copy.deepcopy(value["project"]["works"][0]))
        self.expect("SCHEMA", lambda: c.validate("enrollment", value))

    def test_cli_admin_roundtrip_and_no_secret_error_echo(self):
        input_file = self.root / "enrollment.json"
        input_file.write_bytes(c.encoded(self.enrollment))
        input_file.chmod(0o600)
        script = Path(r.__file__)
        def run(*args):
            return subprocess.run([sys.executable, str(script), *args], capture_output=True, timeout=30)
        description = self.root / "description.json"
        description.write_bytes(c.encoded({"schema": "golem.integration-description.v1",
            "project_id": "p", "root": str(self.project), "cli": str(self.cli),
            "sdk_files": [str(self.sdk)], "works": [{"work_id": "a", "path": str(self.work)}]}))
        description.chmod(0o600)
        result = run("describe", "--input", str(description))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.enrollment["project"])
        result = run("plan", "--registry", str(self.registry.root), "--input", str(input_file))
        self.assertEqual(result.returncode, 0, result.stderr)
        digest = json.loads(result.stdout)["plan_sha256"]
        result = run("apply", "--registry", str(self.registry.root), "--input", str(input_file),
                     "--reviewed-plan", digest, "--approve-local-owner")
        self.assertEqual(result.returncode, 0, result.stderr)
        input_file.write_bytes(b'{"secret":"never-echo-this"}')
        result = run("read", "--registry", str(self.registry.root), "--input", str(input_file))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(b"never-echo-this", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
