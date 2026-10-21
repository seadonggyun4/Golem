"""D1 installer isolation, lossless edits and explicit interrupted-apply repair."""
import copy
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

import integration_config as config
import integration_contract as c
import integration_install as installer
import integration_launch as launch
import integration_registry as r
from integration_hook_contract import executable_pin
import test_integration_d2 as fixtures


class Install(unittest.TestCase):
    for name in ("approve", "query", "expect", "inventory", "save_policy"):
        locals()[name] = getattr(fixtures.D2, name)

    def setUp(self):
        fixtures.D2.setUp(self)
        self.state = self.root / "installer"
        r.Registry.create(self.state, approve_local_owner=True)
        self.manager = installer.Installer(self.state)
        sdk = self.root / "sdk-fixture"
        sdk.mkdir(mode=0o700)
        (sdk / "fixture.py").write_bytes(b"# pinned fixture, not an actual MCP SDK\n")
        runtime = {"python": executable_pin(Path(sys.executable).resolve()), "sdk_root": str(sdk),
                   "sdk_identity": r.identity(sdk), "files": {"fixture.py": c.sha((sdk / "fixture.py").read_bytes())}}
        self.request = {"installation_id": "first", "clients_stopped": "STOPPED_OWNER_ATTESTED", "targets": []}
        for kind in config.CLIENTS:
            home = self.root / kind
            home.mkdir(mode=0o700)
            path = home / config.FILENAMES[kind]
            content = b'# owner comment\nmodel = "unchanged"\n' if kind == "codex-config" else b'{\n "hooks": {"existing": [1, 2]}, "unknown" : true\n}\n'
            path.write_bytes(content)
            path.chmod(0o600)
            self.request["targets"].append({"client": kind, "config": str(path), "server_name": "golem",
                "runtime": runtime,
                "transfer_policy": {"path": str(self.policy_path), "sha256": self.digest}})

    def apply(self, plan, **kwargs):
        return self.manager.apply(plan, c.sha(c.encoded(plan)), approve_installation=True, **kwargs)

    def install(self):
        plan = self.manager.plan("install", self.request)
        self.apply(plan)
        return plan

    def removal(self):
        return self.manager.plan("remove", {"installation_id": "first", "clients_stopped": "STOPPED_OWNER_ATTESTED"})

    def test_plan_no_configuration_native_or_registry_writes(self):
        before = self.inventory()
        files = {t["config"]: Path(t["config"]).read_bytes() for t in self.request["targets"]}
        self.manager.plan("install", self.request)
        self.assertEqual(before, self.inventory())
        self.assertEqual(files, {p: Path(p).read_bytes() for p in files})
        self.assertEqual(list(self.state.iterdir()), [])

    def test_closed_schema_owner_intent_and_plan_digest(self):
        for key in self.request:
            value = copy.deepcopy(self.request)
            del value[key]
            self.expect("SCHEMA", lambda: self.manager.plan("install", value))
        self.expect("SCHEMA", lambda: self.manager.plan("install", {**self.request, "approve": True}))
        plan = self.manager.plan("install", self.request)
        self.expect("OWNER_INSTALL_APPROVAL_REQUIRED", lambda: self.manager.apply(plan, c.sha(c.encoded(plan))))
        self.expect("PLAN_DIGEST", lambda: self.manager.apply(plan, "0" * 64, approve_installation=True))

    def test_lossless_roundtrip_all_clients_and_native_inventory(self):
        files = {t["config"]: Path(t["config"]).read_bytes() for t in self.request["targets"]}
        before = self.inventory()
        self.install()
        self.assertEqual(self.manager.inspect("first")["state"], "RELOAD_REQUIRED")
        self.apply(self.removal())
        self.assertEqual(files, {p: Path(p).read_bytes() for p in files})
        self.assertEqual(before, self.inventory())
        self.assertEqual(self.manager.inspect("first")["state"], "REMOVED")

    def test_comments_multiline_toml_and_unknown_json_formatting_retained(self):
        entry = {"command": "/bin/example", "args": ["--policy", "quoted path"]}
        text = b'# before\n[other]\nvalue = """[not.a.table]\n# comment inside\n"""\n'
        after, _ = config.edit("codex-config", text, "golem", entry)
        self.assertTrue(after.startswith(text))
        self.assertEqual(config.edit("codex-config", after, "golem", entry, remove=True)[0], text)
        for text in (b'{"mcpServers" : { "other": {"odd" : [1,2]} }, "x": 2}', b'{"x": 1}'):
            after, created = config.edit("claude-desktop", text, "golem", entry)
            self.assertIn(b'"x": ', after)
            result, _ = config.edit("claude-desktop", after, "golem", entry, remove=True, created_container=created)
            self.assertEqual(c.decode(result), c.decode(text))

    def test_unmanaged_edits_survive_removal(self):
        self.install()
        for item in self.request["targets"]:
            path = Path(item["config"])
            raw = path.read_bytes()
            if item["client"] == "codex-config":
                raw += b'\n[new_user_section]\nflag = 7\n'
            else:
                raw = raw.replace(b'"unknown" : true', b'"unknown" : true, "later" : [3, 4]')
            path.write_bytes(raw)
        self.apply(self.removal())
        for item in self.request["targets"]:
            raw = Path(item["config"]).read_bytes()
            self.assertIn(b'flag = 7' if item["client"] == "codex-config" else b'"later" : [3, 4]', raw)

    def test_edited_managed_entry_blocks_remove_without_overwrite(self):
        self.install()
        path = Path(self.request["targets"][0]["config"])
        path.write_bytes(path.read_bytes().replace(b'command = ', b'disabled = true\ncommand = '))
        original = path.read_bytes()
        self.expect("MANAGED_CONFIG_DRIFT", self.removal)
        self.assertEqual(path.read_bytes(), original)

    def test_stale_plan_config_metadata_parent_and_pins_block(self):
        plan = self.manager.plan("install", self.request)
        path = Path(self.request["targets"][0]["config"])
        path.write_bytes(path.read_bytes() + b'\n# owner edit\n')
        self.expect("INSTALL_PLAN_STALE", lambda: self.apply(plan))
        self.assertFalse(self.manager.directory("first").exists())
        self.policy_path.write_bytes(self.policy_path.read_bytes() + b" ")
        self.expect("TRANSFER_POLICY_CHANGED", lambda: self.manager.plan("install", self.request))

    def test_conflict_and_unsupported_formats_do_not_normalize(self):
        entry = {"command": "/example", "args": []}
        self.expect("SERVER_NAME_CONFLICT", lambda: config.edit("codex-config", b'[mcp_servers.golem]\ncommand="old"\n', "golem", entry))
        for data in (b'{"x":1,"x":2}', b'{/* comment */}', b'[]', b'{"mcpServers":[]}'):
            with self.assertRaises(ValueError):
                config.edit("claude-desktop", data, "golem", entry)
        with self.assertRaises(ValueError):
            config.edit("codex-config", b'mcp_servers = {}\n', "golem", entry)

    def test_multiple_target_partial_apply_requires_explicit_repair(self):
        plan = self.manager.plan("install", self.request)
        real = installer.publish_config
        calls = 0
        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected config write")
            return real(*args)
        with patch.object(installer, "publish_config", side_effect=fail_second):
            with self.assertRaises(OSError):
                self.apply(plan)
        self.assertEqual(self.manager.inspect("first")["state"], "PARTIAL")
        self.expect("INSTALL_ID_USED", lambda: self.apply(plan))
        self.apply(plan, repair=True)
        self.assertEqual(self.manager.inspect("first")["state"], "RELOAD_REQUIRED")

    def test_crash_after_replace_before_receipt_repairs_without_second_write(self):
        self.request["targets"] = self.request["targets"][:1]
        plan = self.manager.plan("install", self.request)
        real = installer.retain
        def fail(path, data):
            if path.name == "applied-0.json":
                raise OSError("crash after replace")
            return real(path, data)
        with patch.object(installer, "retain", side_effect=fail):
            with self.assertRaises(OSError):
                self.apply(plan)
        with patch.object(installer, "publish_config", side_effect=AssertionError("must not republish")):
            self.apply(plan, repair=True)

    def test_partial_repair_never_overwrites_intervening_user_edits(self):
        plan = self.manager.plan("install", self.request)
        with patch.object(installer, "publish_config", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.apply(plan)
        path = Path(self.request["targets"][0]["config"])
        path.write_bytes(path.read_bytes() + b'\n# concurrent edit\n')
        self.expect("CONFIG_DRIFT", lambda: self.apply(plan, repair=True))

    def test_removal_partial_blocks_launcher_and_repairs_explicitly(self):
        self.install()
        plan = self.removal()
        with patch.object(installer, "publish_config", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.apply(plan)
        path = self.manager.directory("first") / "launch-0.json"
        self.expect("INSTALL_REMOVED_OR_PARTIAL", lambda: launch.check(path, c.sha(path.read_bytes())))
        self.apply(plan, repair=True)

    def test_launcher_requires_commit_current_grant_and_interpreter(self):
        self.install()
        path = self.manager.directory("first") / "launch-0.json"
        self.assertEqual(launch.check(path, c.sha(path.read_bytes())), self.request["targets"][0])
        self.approve("revoke")
        self.expect("PROJECT_APPROVAL_REQUIRED", lambda: launch.check(path, c.sha(path.read_bytes())))

    def test_backup_corruption_and_changed_producer_block_repair(self):
        plan = self.manager.plan("install", self.request)
        with patch.object(installer, "publish_config", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.apply(plan)
        backup = self.manager.directory("first") / "before-0.bin"
        backup.write_bytes(b"tampered")
        self.expect("INSTALL_BACKUP_CORRUPT", lambda: self.apply(plan, repair=True))
        with patch.object(installer, "producer", return_value={}):
            self.expect("INSTALL_PLAN_STALE", lambda: self.apply(plan, repair=True))

    def test_symlink_hardlink_unreviewed_parent_and_native_config_paths(self):
        path = Path(self.request["targets"][0]["config"])
        copy_path = path.parent / "copy"
        os.link(path, copy_path)
        self.expect("UNSAFE_FILE", lambda: self.manager.plan("install", self.request))
        copy_path.unlink()
        path.parent.chmod(0o777)
        self.expect("CONFIG_PARENT_UNSAFE", lambda: self.manager.plan("install", self.request))

    def test_directory_lock_serializes_different_installer_states(self):
        path = Path(self.request["targets"][0]["config"])
        with installer.directory_lock(path.parent):
            self.expect("CONFIG_BUSY", lambda: self.install())

    def test_new_configuration_files_private_and_removal_keeps_empty_scaffold(self):
        for item in self.request["targets"]:
            Path(item["config"]).unlink()
        self.install()
        self.apply(self.removal())
        for item in self.request["targets"]:
            path = Path(item["config"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(config.parsed(item["client"], path.read_bytes())[1], {})

    def bootstrap_request(self):
        root = self.root / "new-project"
        root.mkdir(mode=0o700)
        (root / "user.txt").write_bytes(b"preserve\n")
        return {"bootstrap_id": "new", "project_id": "new-project", "root": str(root)}

    def test_bootstrap_explicit_empty_scaffold_without_work_grants_or_client_settings(self):
        request = self.bootstrap_request()
        root = Path(request["root"])
        plan = self.manager.plan("bootstrap", request)
        self.assertFalse((root / ".golem").exists())
        result = self.apply(plan)
        self.assertEqual(result["state"], "BOOTSTRAPPED")
        self.assertEqual((root / "user.txt").read_bytes(), b"preserve\n")
        self.assertEqual([str(p.relative_to(root)) for p in sorted(root.rglob("*"))],
                         [".golem", ".golem/integration", ".golem/integration/manifest.json", "user.txt"])
        self.assertFalse(result["work_created"])
        self.assertFalse(result["grants_created"])
        self.expect("BOOTSTRAP_EXISTS_USE_D1_ENROLLMENT", lambda: self.manager.plan("bootstrap", request))

    def test_bootstrap_crash_retains_scaffold_and_only_exact_repair_completes(self):
        request = self.bootstrap_request()
        plan = self.manager.plan("bootstrap", request)
        real = installer.retain
        def fail(path, data):
            if path.name == "manifest.json":
                raise OSError("disk full")
            return real(path, data)
        with patch.object(installer, "retain", side_effect=fail):
            with self.assertRaises(OSError):
                self.apply(plan)
        self.apply(plan, repair=True)
        self.assertTrue((Path(request["root"]) / ".golem/integration/manifest.json").exists())

    def test_bootstrap_existing_root_and_partial_unknown_content_never_modified(self):
        request = self.bootstrap_request()
        plan = self.manager.plan("bootstrap", request)
        runtime = Path(request["root"]) / ".golem"
        runtime.mkdir()
        (runtime / "evidence").write_bytes(b"untouched")
        self.expect("BOOTSTRAP_EXISTS_USE_D1_ENROLLMENT", lambda: self.apply(plan))
        self.assertEqual((runtime / "evidence").read_bytes(), b"untouched")

    def test_backup_files_owner_private(self):
        self.install()
        directory = self.manager.directory("first")
        for path in directory.iterdir():
            self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_same_bytes_changed_metadata_or_parent_invalidates_plan(self):
        plan = self.manager.plan("install", self.request)
        path = Path(self.request["targets"][0]["config"])
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000))
        self.expect("INSTALL_PLAN_STALE", lambda: self.apply(plan))
        plan = self.manager.plan("install", self.request)
        previous = path.parent.with_name("previous-parent")
        path.parent.rename(previous)
        path.parent.mkdir(mode=0o700)
        path.write_bytes((previous / path.name).read_bytes())
        path.chmod(0o600)
        self.expect("INSTALL_PLAN_STALE", lambda: self.apply(plan))

    def test_other_mcp_servers_added_after_install_survive_remove(self):
        self.install()
        item = self.request["targets"][1]
        path = Path(item["config"])
        raw = path.read_bytes()
        rows = config.members(raw.decode())[0]
        _, closing = config.members(raw.decode(), rows["mcpServers"][1])
        text = raw.decode()
        path.write_text(text[:closing] + ',"user_added":{"command":"/unchanged"}' + text[closing:])
        self.apply(self.removal())
        self.assertEqual(c.decode(path.read_bytes())["mcpServers"], {"user_added": {"command": "/unchanged"}})

    def test_revoked_grant_or_changed_sdk_blocks_install_before_config_write(self):
        plan = self.manager.plan("install", self.request)
        self.approve("revoke")
        self.expect("PROJECT_APPROVAL_REQUIRED", lambda: self.apply(plan))
        self.assertFalse(self.manager.directory("first").exists())

    def test_bootstrap_partial_unknown_content_keeps_original_bytes(self):
        request = self.bootstrap_request()
        plan = self.manager.plan("bootstrap", request)
        real = installer.retain
        def fail(path, data):
            if path.name == "manifest.json":
                raise OSError("disk full")
            return real(path, data)
        with patch.object(installer, "retain", side_effect=fail):
            with self.assertRaises(OSError):
                self.apply(plan)
        unexpected = Path(request["root"]) / ".golem/original-evidence"
        unexpected.write_bytes(b"preserve")
        self.expect("BOOTSTRAP_CONTENT_DRIFT", lambda: self.apply(plan, repair=True))
        self.assertEqual(unexpected.read_bytes(), b"preserve")

    def test_new_file_publication_never_replaces_racing_file(self):
        path = self.root / "new-config.json"
        real = installer.os.link
        def create_competitor(source, target, **kwargs):
            Path(target).write_bytes(b"concurrent user file")
            return real(source, target, **kwargs)
        with patch.object(installer.os, "link", side_effect=create_competitor):
            with self.assertRaises(FileExistsError):
                installer.publish_config(path, None, b"{}")
        self.assertEqual(path.read_bytes(), b"concurrent user file")

    def test_duplicate_paths_and_client_mismatch_are_not_installed(self):
        request = copy.deepcopy(self.request)
        request["targets"][1]["config"] = request["targets"][0]["config"]
        self.expect("DUPLICATE_CONFIG_TARGET", lambda: self.manager.plan("install", request))
        request = copy.deepcopy(self.request)
        request["targets"][0]["config"] = str(Path(request["targets"][0]["config"]).with_name("unrelated.toml"))
        self.expect("CLIENT_CONFIG_PATH", lambda: self.manager.plan("install", request))

    def test_remove_rejects_corrupt_original_backup_and_copied_state(self):
        self.install()
        copied = self.root / "copied-state"
        shutil.copytree(self.state, copied)
        other = installer.Installer(copied)
        self.expect("INSTALL_RECORD_CONFLICT", lambda: other.plan("remove", {
            "installation_id": "first", "clients_stopped": "STOPPED_OWNER_ATTESTED"}))
        (self.manager.directory("first") / "before-0.bin").write_bytes(b"corrupt")
        self.expect("INSTALL_BACKUP_CORRUPT", self.removal)

    def test_client_environment_expansion_cannot_change_reviewed_arguments(self):
        root = self.root / "state-${HOME}"
        r.Registry.create(root, approve_local_owner=True)
        other = installer.Installer(root)
        self.expect("CLIENT_ENV_EXPANSION_FORBIDDEN", lambda: other.plan("install", self.request))

    def test_full_history_capacity_still_allows_removal_not_new_install(self):
        self.install()
        for index in range(127):
            (self.state / f"installation-retained-{index}").mkdir(mode=0o700)
        self.apply(self.removal())
        request = {**self.request, "installation_id": "new"}
        plan = self.manager.plan("install", request)
        self.expect("INSTALL_QUOTA", lambda: self.apply(plan))


if __name__ == "__main__":
    unittest.main()
