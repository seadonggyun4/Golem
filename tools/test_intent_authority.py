import os
from pathlib import Path
import subprocess
import tempfile
import shutil
import sys
import struct
import inspect
import unittest
from unittest.mock import patch

from integration_contract import IntegrationError
import fcntl
import intent_authority as host
import intent_authority_lifecycle as lifecycle
from intent_authority import authority_identity, repository_identity, verify_observation


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="golem-d01-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / "repository"
        self.repo.mkdir()
        if sys.platform == "darwin":
            self.git_binary = Path(subprocess.check_output(
                ["/usr/bin/xcrun", "--find", "git"], timeout=10,
                env={"PATH": "/usr/bin:/bin"}, text=True).strip()).resolve()
        else:
            self.git_binary = Path(shutil.which("git")).resolve()
        self.git("init", "-q")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "fixture")
        self.authority = self.base / "authority"
        self.authority.mkdir(mode=0o700)
        self.pin = self.base / "host"
        self.pin.write_bytes(b"fixture host")

    def git(self, *args):
        subprocess.run(["/usr/bin/git", "-C", str(self.repo), *args], check=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(self.base),
                            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
                       capture_output=True)

    def observations(self):
        repo = repository_identity(self.repo, git=self.git_binary)
        return repo, authority_identity(self.authority, repo, [self.pin])

    def test_linked_worktree_common_identity(self):
        linked = self.base / "linked"
        self.git("worktree", "add", "--detach", str(linked), "HEAD")
        first = repository_identity(self.repo, git=self.git_binary)
        second = repository_identity(linked, git=self.git_binary)
        self.assertEqual(first["common_dir"], second["common_dir"])
        self.assertEqual(first["common_identity"], second["common_identity"])
        self.assertNotEqual(first["root_identity"], second["root_identity"])
        nested = self.repo / "not-external"
        nested.mkdir(mode=0o700)
        with self.assertRaises(IntegrationError):
            authority_identity(nested, second, [self.pin])

    def test_read_only_and_clean_environment(self):
        def snapshot():
            return {str(p.relative_to(self.repo)): p.read_bytes()
                    for p in self.repo.rglob("*") if p.is_file()}
        before = snapshot()
        with patch.dict(os.environ, {"GIT_DIR": "/nonexistent", "GIT_WORK_TREE": "/nonexistent",
                                     "GIT_PAGER": "false", "GIT_CONFIG_COUNT": "invalid"}):
            repo, authority = self.observations()
            verify_observation(repo, authority)
        self.assertEqual(snapshot(), before)

    def test_pin_change(self):
        repo, authority = self.observations()
        self.pin.write_bytes(b"changed")
        with self.assertRaises(IntegrationError):
            verify_observation(repo, authority)

    def test_authority_replacement(self):
        repo, authority = self.observations()
        self.authority.rename(self.base / "old")
        self.authority.mkdir(mode=0o700)
        with self.assertRaises(IntegrationError):
            verify_observation(repo, authority)

    def test_common_dir_replacement(self):
        repo, authority = self.observations()
        (self.repo / ".git").rename(self.repo / "old-git")
        self.git("init", "-q")
        with self.assertRaises(IntegrationError):
            verify_observation(repo, authority)

    def test_scope_symlink_and_public_mode(self):
        repo = repository_identity(self.repo, git=self.git_binary)
        inside = self.repo / "authority"
        inside.mkdir(mode=0o700)
        with self.assertRaises(IntegrationError):
            authority_identity(inside, repo, [self.pin])
        link = self.base / "alias"
        link.symlink_to(self.authority, target_is_directory=True)
        with self.assertRaises(IntegrationError):
            authority_identity(link, repo, [self.pin])
        self.authority.chmod(0o755)
        with self.assertRaises(IntegrationError):
            authority_identity(self.authority, repo, [self.pin])

    def enroll(self, pins=None):
        if not os.environ.get("GOLEM_INTENT_HOST"):
            self.skipTest("native bridge path required")
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        pins = pins or [self.pin, bridge]
        plan = host.registration_plan(self.repo, self.authority, pins, git=self.git_binary)
        return host.register(self.repo, self.authority, pins, plan["plan_sha256"],
                             git=self.git_binary, bridge=bridge, approve_local_owner=True)

    def test_explicit_registration_and_conflict(self):
        plan = host.registration_plan(self.repo, self.authority, [self.pin], git=self.git_binary)
        self.assertFalse((self.repo / ".git" / host.LOCATOR).exists())
        with self.assertRaises(IntegrationError):
            host.register(self.repo, self.authority, [self.pin], plan["plan_sha256"], git=self.git_binary, bridge=self.pin)
        value = self.enroll()
        with host.authorized_root(self.repo, value["registration_sha256"], git=self.git_binary) as (fd, _):
            self.assertEqual(os.fstat(fd).st_ino, self.authority.stat().st_ino)
        competing = self.base / "other-authority"
        competing.mkdir(mode=0o700)
        with self.assertRaisesRegex(IntegrationError, "AUTHORITY_CONFLICT"):
            host.registration_plan(self.repo, competing, [self.pin], git=self.git_binary)
        self.assertEqual(len(list(self.authority.iterdir())), 3)

    def test_stale_plan_and_missing_locator(self):
        plan = host.registration_plan(self.repo, self.authority, [self.pin], git=self.git_binary)
        self.pin.write_bytes(b"changed")
        with self.assertRaisesRegex(IntegrationError, "PLAN_STALE"):
            host.register(self.repo, self.authority, [self.pin], plan["plan_sha256"],
                          git=self.git_binary, bridge=self.pin, approve_local_owner=True)
        with self.assertRaisesRegex(IntegrationError, "AUTHORITY_REGISTRATION_REQUIRED"):
            with host.authorized_root(self.repo, "0" * 64, git=self.git_binary):
                self.fail("unregistered authority opened")

    def test_linked_worktree_resolves_same_registration(self):
        linked = self.base / "linked"
        self.git("worktree", "add", "--detach", str(linked), "HEAD")
        value = self.enroll()
        with host.authorized_root(linked, value["registration_sha256"], git=self.git_binary) as (fd, _):
            self.assertEqual(os.fstat(fd).st_ino, self.authority.stat().st_ino)

    def test_locator_pin_tamper_and_pending_block(self):
        value = self.enroll()
        with self.assertRaisesRegex(IntegrationError, "REGISTRATION_PIN_MISMATCH"):
            with host.authorized_root(self.repo, "0" * 64, git=self.git_binary):
                self.fail("wrong registration accepted")
        pending = self.repo / ".git" / (host.PENDING + "fixture")
        pending.write_bytes(b"partial")
        with self.assertRaisesRegex(IntegrationError, "LOCATOR_COMMIT_UNKNOWN"):
            with host.authorized_root(self.repo, value["registration_sha256"], git=self.git_binary):
                self.fail("pending registration accepted")
        self.assertEqual(pending.read_bytes(), b"partial")

    def test_common_lock_conflict_and_pin_change_during_use(self):
        value = self.enroll()
        fd = os.open(self.repo / ".git", os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(IntegrationError, "AUTHORITY_REGISTRATION_BUSY"):
                with host.authorized_root(self.repo, value["registration_sha256"], git=self.git_binary):
                    self.fail("conflicting lock accepted")
        finally:
            os.close(fd)
        with self.assertRaises(IntegrationError):
            with host.authorized_root(self.repo, value["registration_sha256"], git=self.git_binary):
                self.pin.write_bytes(b"changed during use")

    def test_other_repository_cannot_share_authority(self):
        self.enroll()
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        self.repo = self.base / "second-repository"
        self.repo.mkdir()
        self.git("init", "-q")
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        pins = [self.pin, bridge]
        plan = host.registration_plan(self.repo, self.authority, pins, git=self.git_binary)
        with self.assertRaisesRegex(IntegrationError, "NATIVE_REGISTRATION_BLOCKED"):
            host.register(self.repo, self.authority, pins, plan["plan_sha256"],
                          git=self.git_binary, bridge=bridge, approve_local_owner=True)
        self.assertFalse((self.repo / ".git" / host.LOCATOR).exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})

    def test_failed_locator_publish_preserves_pending(self):
        if not os.environ.get("GOLEM_INTENT_HOST"):
            self.skipTest("native bridge path required")
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        pins = [self.pin, bridge]
        plan = host.registration_plan(self.repo, self.authority, pins, git=self.git_binary)
        with patch.object(host.os, "link", side_effect=OSError("injected link failure")):
            with self.assertRaises(OSError):
                host.register(self.repo, self.authority, pins, plan["plan_sha256"],
                              git=self.git_binary, bridge=bridge, approve_local_owner=True)
        self.assertTrue(any(p.name.startswith(host.PENDING) for p in (self.repo / ".git").iterdir()))
        with self.assertRaisesRegex(IntegrationError, "LOCATOR_COMMIT_UNKNOWN"):
            host.registration_plan(self.repo, self.authority, pins, git=self.git_binary)

    @unittest.skipUnless(os.environ.get("GOLEM_INTENT_HOST"), "native bridge path required")
    def test_registration_replay_and_missing_native_binding(self):
        value = self.enroll()
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        self.assertEqual(self.enroll(), value)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})
        # Simulate lost registration in this disposable fixture only.
        for path in self.authority.iterdir():
            path.unlink()
        with self.assertRaisesRegex(IntegrationError, "NATIVE_REGISTRATION_BLOCKED"):
            self.enroll()
        self.assertEqual(list(self.authority.iterdir()), [])

    def test_common_lock_detects_path_replacement(self):
        repository = repository_identity(self.repo, git=self.git_binary)
        with self.assertRaisesRegex(IntegrationError, "COMMON_DIR_CHANGED"):
            with host._common_lock(repository):
                (self.repo / ".git").rename(self.repo / "old-git")
                (self.repo / ".git").mkdir()

    def revoke_fixture(self, value, **kwargs):
        digest = value["registration_sha256"]
        plan = host.revocation_plan(self.repo, digest, git=self.git_binary)
        return host.revoke(self.repo, digest, plan["plan_sha256"],
                           git=self.git_binary, approve_local_owner=True, **kwargs)

    def test_revocation_preserves_evidence_and_blocks_access(self):
        value = self.enroll()
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        locator = self.repo / ".git" / host.LOCATOR
        original = locator.read_bytes()
        self.revoke_fixture(value)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})
        self.assertEqual(original, locator.read_bytes())
        for call in (lambda: self.enroll(), lambda: host.native_inspect(
                self.repo, value["registration_sha256"], git=self.git_binary,
                bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve()),
                lambda: self.revoke_fixture(value)):
            with self.assertRaisesRegex(IntegrationError, "AUTHORITY_REVOKED"):
                call()

    def test_revocation_requires_approval_and_exact_plan(self):
        value = self.enroll()
        digest = value["registration_sha256"]
        before = {p.name: p.read_bytes() for p in (self.repo / ".git").iterdir() if p.is_file()}
        plan = host.revocation_plan(self.repo, digest, git=self.git_binary)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.repo / ".git").iterdir() if p.is_file()})
        with self.assertRaisesRegex(IntegrationError, "OWNER_APPROVAL_REQUIRED"):
            host.revoke(self.repo, digest, plan["plan_sha256"], git=self.git_binary)
        with self.assertRaisesRegex(IntegrationError, "PLAN_STALE"):
            host.revoke(self.repo, digest, "0" * 64, git=self.git_binary, approve_local_owner=True)
        self.assertFalse((self.repo / ".git" / host.TOMBSTONE).exists())

    def test_revocation_owner_and_shared_reader_conflicts(self):
        value = self.enroll()
        for directory, lock, error in ((self.authority, fcntl.LOCK_EX, "AUTHORITY_OWNER_BUSY"),
                                      (self.repo / ".git", fcntl.LOCK_SH, "AUTHORITY_REGISTRATION_BUSY")):
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                fcntl.flock(fd, lock | fcntl.LOCK_NB)
                with self.assertRaisesRegex(IntegrationError, error):
                    self.revoke_fixture(value)
            finally:
                os.close(fd)
        self.assertFalse((self.repo / ".git" / host.TOMBSTONE).exists())

    def test_revocation_partial_publication_blocks_without_cleanup(self):
        value = self.enroll()
        with patch.object(host.os, "link", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.revoke_fixture(value)
        self.assertTrue(any(p.name.startswith(host.PENDING) for p in (self.repo / ".git").iterdir()))
        with self.assertRaisesRegex(IntegrationError, "LOCATOR_COMMIT_UNKNOWN"):
            self.enroll()

    def test_malformed_tombstone_fails_closed(self):
        self.enroll()
        marker = self.repo / ".git" / host.TOMBSTONE
        marker.symlink_to(self.base / "missing")
        with self.assertRaisesRegex(IntegrationError, "AUTHORITY_REVOKED"):
            self.enroll()

    def change_fixture(self, value):
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        pins = [self.pin, bridge]
        plan = lifecycle.change_plan(self.repo, value["registration_sha256"], pins, git=self.git_binary)
        return lifecycle.change(self.repo, value["registration_sha256"], pins, plan["plan_sha256"],
                                git=self.git_binary, bridge=bridge, approve_local_owner=True)

    def recover_fixture(self, digest):
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        plan = lifecycle.recovery_plan(self.repo, digest, git=self.git_binary, bridge=bridge)
        return lifecycle.recover(self.repo, digest, plan["plan_sha256"], git=self.git_binary,
                                 bridge=bridge, approve_local_owner=True)

    def test_change_chain_preserves_history_and_intake_lane(self):
        original = self.enroll()
        initial = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        value = original
        for version in (b"second pin", b"third pin"):
            self.pin.write_bytes(version)
            value = self.change_fixture(value)
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        observed = host.native_inspect(self.repo, value["registration_sha256"], git=self.git_binary, bridge=bridge)
        self.assertEqual(observed["committed"], 3)
        self.assertEqual(observed["usage"][0][0], 3)
        self.assertEqual(observed["usage"][1:], [[0] * 4] * 2)
        for name, data in initial.items():
            self.assertEqual((self.authority / name).read_bytes(), data)
        saved = self.repo / ".git" / (host.HISTORY + original["registration_sha256"] + ".json")
        self.assertEqual(saved.read_bytes(), host.encoded(original))
        # Roll back locator bytes in this fixture: native latest binding still rejects it.
        locator = self.repo / ".git" / host.LOCATOR
        locator.chmod(0o600)
        locator.write_bytes(host.encoded(original))
        self.pin.write_bytes(b"fixture host")
        with self.assertRaisesRegex(IntegrationError, "NATIVE_INSPECTION_BLOCKED"):
            host.native_inspect(self.repo, original["registration_sha256"], git=self.git_binary, bridge=bridge)

    def test_change_cannot_resurrect_an_old_registration_digest(self):
        value = self.enroll()
        self.pin.write_bytes(b"second")
        new = self.change_fixture(value)
        self.pin.write_bytes(b"fixture host")
        with self.assertRaisesRegex(IntegrationError, "NATIVE_BINDING_UNCONFIRMED"):
            self.change_fixture(new)
        self.assertFalse((self.repo / ".git" / host.CHANGE).exists())

    def test_change_rejects_missing_approval_and_moved_authority(self):
        value = self.enroll()
        self.pin.write_bytes(b"second")
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        plan = lifecycle.change_plan(self.repo, value["registration_sha256"], [self.pin, bridge], git=self.git_binary)
        with self.assertRaisesRegex(IntegrationError, "OWNER_APPROVAL_REQUIRED"):
            lifecycle.change(self.repo, value["registration_sha256"], [self.pin, bridge], plan["plan_sha256"],
                             git=self.git_binary, bridge=bridge)
        self.authority.rename(self.base / "saved-authority")
        self.authority.mkdir(mode=0o700)
        with self.assertRaisesRegex(IntegrationError, "REGISTRATION_MOVE_DENIED"):
            lifecycle.change_plan(self.repo, value["registration_sha256"], [self.pin, bridge], git=self.git_binary)

    def test_legacy_producer_requires_explicit_reapproval(self):
        legacy = {key: value for key, value in host._producer().items() if key != "intent_authority_lifecycle.py"}
        with patch.object(host, "_producer", return_value=legacy), patch.object(host, "REGISTRATION", host.LEGACY_REGISTRATION):
            value = self.enroll()
        with self.assertRaisesRegex(IntegrationError, "PRODUCER_CHANGED"):
            with host.authorized_root(self.repo, value["registration_sha256"], git=self.git_binary):
                self.fail("legacy producer silently accepted")
        new = self.change_fixture(value)
        self.assertIn("intent_authority_lifecycle.py", new["record"]["producer"])

    def test_recovery_requires_exact_native_transition(self):
        value = self.enroll()
        self.pin.write_bytes(b"second")
        with patch.object(lifecycle, "_finish", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.change_fixture(value)
        path = self.repo / ".git" / host.CHANGE
        intent = host.decode(path.read_bytes())
        fake = intent["plan"]["before"]["record"]
        fake["producer"]["intent_authority.py"] = "0" * 64
        intent["plan"]["before"] = lifecycle._locator(fake)
        intent["plan_sha256"] = host.sha(host.encoded(intent["plan"]))
        path.chmod(0o600)
        path.write_bytes(host.encoded(intent))
        locator = self.repo / ".git" / host.LOCATOR
        locator.chmod(0o600)
        locator.write_bytes(host.encoded(intent["plan"]["before"]))
        with self.assertRaisesRegex(IntegrationError, "NATIVE_BINDING_UNCONFIRMED"):
            self.recover_fixture(intent["plan"]["after"]["registration_sha256"])

    def test_recovery_plan_does_not_authorize_or_ignore_changed_snapshot(self):
        value = self.enroll()
        common = self.repo / ".git"
        pending = common / (host.PENDING + "complete")
        pending.write_bytes(host.encoded(value))
        pending.chmod(0o600)
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        plan = lifecycle.recovery_plan(self.repo, value["registration_sha256"], git=self.git_binary, bridge=bridge)
        with self.assertRaisesRegex(IntegrationError, "OWNER_APPROVAL_REQUIRED"):
            lifecycle.recover(self.repo, value["registration_sha256"], plan["plan_sha256"], git=self.git_binary, bridge=bridge)
        duplicate = common / (host.PENDING + "another")
        duplicate.write_bytes(pending.read_bytes())
        duplicate.chmod(0o600)
        with self.assertRaisesRegex(IntegrationError, "PLAN_STALE"):
            lifecycle.recover(self.repo, value["registration_sha256"], plan["plan_sha256"],
                              git=self.git_binary, bridge=bridge, approve_local_owner=True)

    def test_change_committed_recovery_does_not_append(self):
        value = self.enroll()
        self.pin.write_bytes(b"second")
        with patch.object(lifecycle.os, "replace", side_effect=OSError("injected replace")):
            with self.assertRaises(OSError):
                self.change_fixture(value)
        common = self.repo / ".git"
        intent = host.decode((common / host.CHANGE).read_bytes())
        new = intent["plan"]["after"]
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        self.assertEqual(self.recover_fixture(new["registration_sha256"]), new)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})
        self.assertFalse((common / host.CHANGE).exists())
        self.assertTrue((common / (host.HISTORY + "change-" + host.sha(host.encoded(intent)) + ".json")).exists())

    def change_publish_fault(self, step, after_link=False):
        value = self.enroll()
        self.pin.write_bytes(b"second")
        original = host.os.unlink if after_link else host.os.link
        calls = 0
        def fault(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == step:
                raise OSError("injected publication boundary")
            return original(*args, **kwargs)
        with patch.object(host.os, "unlink" if after_link else "link", side_effect=fault):
            with self.assertRaises(OSError):
                self.change_fixture(value)
        common = self.repo / ".git"
        intent = host.decode((common / host.CHANGE).read_bytes())
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        new = intent["plan"]["after"]
        self.assertEqual(self.recover_fixture(new["registration_sha256"]), new)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})
        self.assertFalse(any(p.name.startswith(host.PENDING) for p in common.iterdir()))

    def test_recovery_after_old_history_publish_failure(self):
        self.change_publish_fault(2)

    def test_recovery_after_candidate_publish_failure(self):
        self.change_publish_fault(3)

    def test_recovery_after_change_history_publish_failure(self):
        self.change_publish_fault(4)

    def test_recovery_after_candidate_hardlink_publication(self):
        self.change_publish_fault(3, after_link=True)

    def test_change_uncommitted_recovery_is_blocked(self):
        value = self.enroll()
        self.pin.write_bytes(b"second")
        native = lifecycle._native
        def fail_append(*args, **kwargs):
            if kwargs.get("check"):
                return native(*args, **kwargs)
            raise IntegrationError("injected")
        with patch.object(lifecycle, "_native", side_effect=fail_append):
            with self.assertRaises(IntegrationError):
                self.change_fixture(value)
        intent = host.decode((self.repo / ".git" / host.CHANGE).read_bytes())
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        with self.assertRaisesRegex(IntegrationError, "NATIVE_BINDING_UNCONFIRMED"):
            self.recover_fixture(intent["plan"]["after"]["registration_sha256"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})

    def test_initial_recovery_preserves_pending_and_native_bytes(self):
        if not os.environ.get("GOLEM_INTENT_HOST"):
            self.skipTest("native bridge required")
        with patch.object(host.os, "link", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.enroll()
        common = self.repo / ".git"
        pending = next(p for p in common.iterdir() if p.name.startswith(host.PENDING))
        data = pending.read_bytes()
        value = host.decode(data)
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        self.assertEqual(self.recover_fixture(value["registration_sha256"]), value)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})
        archive = common / (host.HISTORY + "pending-" + host.sha(data) + ".json")
        self.assertEqual(archive.read_bytes(), data)
        self.assertFalse(pending.exists())

    def test_initial_recovery_handles_published_pending_hardlink(self):
        value = self.enroll()
        common = self.repo / ".git"
        os.link(common / host.LOCATOR, common / (host.PENDING + "crash"))
        self.assertEqual(self.recover_fixture(value["registration_sha256"]), value)
        self.assertEqual((common / host.LOCATOR).stat().st_nlink, 1)

    def test_recovery_rejects_tombstone_and_partial_bytes(self):
        value = self.enroll()
        common = self.repo / ".git"
        (common / (host.PENDING + "partial")).write_bytes(b"{")
        with self.assertRaises(ValueError):
            self.recover_fixture(value["registration_sha256"])
        (common / host.TOMBSTONE).write_bytes(b"revoked")
        with self.assertRaisesRegex(IntegrationError, "AUTHORITY_REVOKED"):
            self.recover_fixture(value["registration_sha256"])

    def test_recovery_rejects_fifo_without_waiting_for_writer(self):
        value = self.enroll()
        os.mkfifo(self.repo / ".git" / (host.PENDING + "fifo"), 0o600)
        with self.assertRaisesRegex(IntegrationError, "RECOVERY_FILE_INVALID"):
            self.recover_fixture(value["registration_sha256"])

    def prepared_fixture(self, change=False):
        value = self.enroll()
        if change:
            self.pin.write_bytes(b"second")
            with patch.object(lifecycle, "_finish", side_effect=OSError("fixture interrupt")):
                with self.assertRaises(OSError):
                    self.change_fixture(value)
            value = host.decode((self.repo / ".git" / host.CHANGE).read_bytes())["plan"]["after"]
        else:
            (self.repo / ".git" / host.LOCATOR).unlink()
        # Disposable fixture: exact post-payload/pre-event crash image.
        (self.authority / ("00000002.event" if change else "00000001.event")).unlink()
        return value

    def finish_native_fixture(self, value):
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        plan = lifecycle.native_recovery_plan(self.repo, value["record"], git=self.git_binary, bridge=bridge)
        return lifecycle.recover_native(self.repo, value["record"], plan["plan_sha256"],
                                        git=self.git_binary, bridge=bridge, approve_local_owner=True)

    def test_native_initial_pending_completion(self):
        value = self.prepared_fixture()
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        self.assertEqual(self.finish_native_fixture(value), value)
        for name, data in before.items():
            self.assertEqual((self.authority / name).read_bytes(), data)
        self.assertEqual(len(list(self.authority.iterdir())), 3)
        self.assertFalse((self.repo / ".git" / host.NATIVE_RECOVERY).exists())
        self.assertTrue(any(p.name.startswith(host.HISTORY + "native-recovery-") for p in (self.repo / ".git").iterdir()))

    def test_native_change_pending_completion(self):
        value = self.prepared_fixture(change=True)
        self.assertEqual(self.finish_native_fixture(value), value)
        observed = host.native_inspect(self.repo, value["registration_sha256"], git=self.git_binary,
                                       bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve())
        self.assertEqual(observed["committed"], 2)
        self.assertEqual(observed["usage"][0][0], 2)
        self.assertEqual(observed["usage"][1:], [[0] * 4] * 2)

    def test_native_pending_intent_failure_prevents_event(self):
        value = self.prepared_fixture()
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        with patch.object(host.os, "link", side_effect=OSError("intent publication failed")):
            with self.assertRaises(OSError):
                self.finish_native_fixture(value)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})

    def test_native_pending_explicit_reentry_after_event_commit(self):
        value = self.prepared_fixture(change=True)
        with patch.object(lifecycle, "_finish", side_effect=OSError("host interrupted")):
            with self.assertRaises(OSError):
                self.finish_native_fixture(value)
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        self.assertEqual(self.finish_native_fixture(value), value)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})

    def test_native_pending_denies_staging_and_revocation(self):
        value = self.prepared_fixture()
        (self.authority / "00000001.event.pending").write_bytes(b"partial")
        with self.assertRaisesRegex(IntegrationError, "NATIVE_PENDING_NOT_RECOVERABLE"):
            self.finish_native_fixture(value)
        (self.repo / ".git" / host.TOMBSTONE).write_bytes(b"revoked")
        with self.assertRaisesRegex(IntegrationError, "AUTHORITY_REVOKED"):
            self.finish_native_fixture(value)

    def test_native_pending_requires_fresh_owner_approval(self):
        value = self.prepared_fixture()
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        plan = lifecycle.native_recovery_plan(self.repo, value["record"], git=self.git_binary, bridge=bridge)
        with self.assertRaisesRegex(IntegrationError, "OWNER_APPROVAL_REQUIRED"):
            lifecycle.recover_native(self.repo, value["record"], plan["plan_sha256"], git=self.git_binary, bridge=bridge)
        with self.assertRaisesRegex(IntegrationError, "PLAN_STALE"):
            lifecycle.recover_native(self.repo, value["record"], "0" * 64,
                                     git=self.git_binary, bridge=bridge, approve_local_owner=True)
        self.assertFalse((self.authority / "00000001.event").exists())

    def test_native_pending_rejects_other_operation(self):
        value = self.prepared_fixture()
        path = self.authority / "00000001.prep"
        prep = host.decode(path.read_bytes())
        prep["operation_id"] = host.sha(b"not a D01 operation")
        path.chmod(0o600)
        path.write_bytes(host.encoded(prep))
        with self.assertRaisesRegex(IntegrationError, "NATIVE_PENDING_NOT_RECOVERABLE"):
            self.finish_native_fixture(value)

    def test_native_pending_respects_other_owner(self):
        value = self.prepared_fixture()
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(IntegrationError, "NATIVE_PENDING_NOT_RECOVERABLE"):
                self.finish_native_fixture(value)
        finally:
            os.close(fd)
        self.assertFalse((self.authority / "00000001.event").exists())

    def test_native_recovery_reentry_after_locator_finished(self):
        value = self.prepared_fixture(change=True)
        archive = lifecycle._archive
        def fail_native_history(fd, common, name, data):
            if name.startswith(host.HISTORY + "native-recovery-"):
                raise OSError("history boundary")
            return archive(fd, common, name, data)
        with patch.object(lifecycle, "_archive", side_effect=fail_native_history):
            with self.assertRaises(OSError):
                self.finish_native_fixture(value)
        self.assertFalse((self.repo / ".git" / host.CHANGE).exists())
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        self.assertEqual(self.finish_native_fixture(value), value)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})

    def alias_fixture(self, kind=2, prepared=False):
        value = self.prepared_fixture() if prepared else self.enroll()
        final = self.authority / ("00000001." + ("prep", "payload", "event")[kind])
        pending = Path(str(final) + ".pending")
        os.link(final, pending)
        return value, final, pending

    def finish_alias_fixture(self, value, kind=2, previous=None):
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        plan = lifecycle.alias_recovery_plan(self.repo, value["record"], kind, git=self.git_binary,
                                             bridge=bridge, previous=previous)
        return lifecycle.recover_alias(self.repo, value["record"], kind, plan["plan_sha256"],
                                       git=self.git_binary, bridge=bridge, previous=previous, approve_local_owner=True)

    def partial_fixture(self, kind=1, change=False):
        value = self.prepared_fixture(change=change)
        seq = 2 if change else 1
        stem = f"{seq:08d}"
        full = (self.authority / (stem + ".payload")).read_bytes()
        if kind == 1:
            (self.authority / (stem + ".payload")).unlink()
            raw = full[:23]
        elif kind == 0:
            raw = (self.authority / (stem + ".prep")).read_bytes()[:23]
        else:
            raw = b"GIQEV"
        pending = self.authority / (stem + "." + ("prep", "payload", "event")[kind] + ".pending")
        pending.write_bytes(raw)
        pending.chmod(0o600)
        return value, pending, raw, full

    def partial_plan(self, value, kind=1, action="quarantine", previous=None):
        return lifecycle.partial_recovery_plan(self.repo, value["record"], kind, action=action,
            git=self.git_binary, bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve(), previous=previous)

    def finish_partial(self, value, kind=1, action="quarantine", previous=None):
        plan = self.partial_plan(value, kind, action, previous)
        return lifecycle.recover_partial(self.repo, value["record"], kind, plan["plan_sha256"], action=action,
            git=self.git_binary, bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve(), previous=previous,
            approve_local_owner=True)

    def test_partial_payload_quarantine_then_separate_replacement(self):
        value, pending, raw, full = self.partial_fixture()
        prep = (self.authority / "00000001.prep").read_bytes()
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        plan = self.partial_plan(value)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})
        result = self.finish_partial(value)
        self.assertFalse(pending.exists())
        envelope = (self.authority / "quarantine/00000001.payload").read_bytes()
        self.assertEqual(envelope[320:], raw)
        self.assertEqual(envelope[224:248].rstrip(b"\0"), b"00000001.payload.pending")
        self.assertEqual(envelope[192:224].hex(), plan["plan_sha256"])
        usage = result["after"]["usage"]
        self.assertEqual(usage[0][2], plan["plan"]["before"]["usage"][0][2] + 320)
        self.assertEqual(usage[0][3], plan["plan"]["before"]["usage"][0][3] + 1)
        self.assertFalse((self.authority / "00000001.payload").exists())
        replaced = self.finish_partial(value, action="replace")
        self.assertEqual((self.authority / "00000001.payload").read_bytes(), full)
        self.assertEqual((self.authority / "00000001.prep").read_bytes(), prep)
        self.assertEqual((self.authority / "quarantine/00000001.payload").read_bytes(), envelope)
        self.assertEqual(replaced["after"]["usage"][0][2], usage[0][2] + len(full))
        self.assertEqual(replaced["after"]["usage"][0][3], usage[0][3] + 1)
        self.assertEqual(replaced["after"]["usage"][0][:2], usage[0][:2])
        self.assertEqual(replaced["after"]["usage"][1:], usage[1:])
        self.assertEqual(replaced["after"]["committed"], 0)
        self.assertFalse((self.authority / "00000001.event").exists())
        self.assertFalse((self.repo / ".git" / host.LOCATOR).exists())
        with self.assertRaises(IntegrationError):
            self.partial_plan(value, action="replace")

    def test_partial_other_staging_kinds_preserve_final_bytes(self):
        for kind in (0, 2):
            with self.subTest(kind=kind):
                # Use one authority per subcase to avoid changing an existing fixture.
                case = IdentityTests("test_partial_payload_quarantine_then_separate_replacement")
                case.setUp()
                try:
                    value, pending, raw, _ = case.partial_fixture(kind=kind)
                    before = {p.name: p.read_bytes() for p in case.authority.iterdir() if p != pending}
                    case.finish_partial(value, kind=kind)
                    for name, data in before.items():
                        self.assertEqual((case.authority / name).read_bytes(), data)
                    name = ("prep", "payload", "event")[kind]
                    self.assertEqual((case.authority / "quarantine" / ("00000001." + name)).read_bytes()[320:], raw)
                    self.assertFalse((case.authority / "00000001.event").exists())
                finally:
                    case.doCleanups()

    def test_partial_rejects_stale_plan_and_missing_owner(self):
        value, pending, raw, _ = self.partial_fixture()
        plan = self.partial_plan(value)
        options = dict(action="quarantine", git=self.git_binary, bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve())
        with self.assertRaises(IntegrationError):
            lifecycle.recover_partial(self.repo, value["record"], 1, plan["plan_sha256"], **options)
        pending.write_bytes(raw + b"x")
        with self.assertRaises(IntegrationError):
            lifecycle.recover_partial(self.repo, value["record"], 1, plan["plan_sha256"],
                                      approve_local_owner=True, **options)
        self.assertFalse((self.authority / "quarantine").exists())

    def test_partial_approval_failure_keeps_source(self):
        value, pending, raw, _ = self.partial_fixture()
        with patch.object(host, "_publish", side_effect=OSError("fixture approval failure")):
            with self.assertRaises(OSError):
                self.finish_partial(value)
        self.assertEqual(pending.read_bytes(), raw)
        self.assertFalse((self.authority / "quarantine").exists())

    def test_partial_receipt_failure_requires_explicit_finalize(self):
        value, _, _, _ = self.partial_fixture()
        original = lifecycle._archive
        def fail(fd, common, name, data):
            if name.startswith(host.HISTORY + "partial-recovery-"):
                raise OSError("fixture receipt failure")
            return original(fd, common, name, data)
        with patch.object(lifecycle, "_archive", side_effect=fail):
            with self.assertRaises(OSError):
                self.finish_partial(value)
        with self.assertRaises(IntegrationError):
            self.partial_plan(value, action="replace")
        with self.assertRaises(IntegrationError):
            lifecycle.native_recovery_plan(self.repo, value["record"], git=self.git_binary,
                                           bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve())
        with self.assertRaises(IntegrationError):
            host._load(host.repository_identity(self.repo, git=self.git_binary))
        envelope = (self.authority / "quarantine/00000001.payload").read_bytes()
        self.finish_partial(value)
        self.assertEqual((self.authority / "quarantine/00000001.payload").read_bytes(), envelope)
        with patch.object(lifecycle, "_archive", side_effect=fail):
            with self.assertRaises(OSError):
                self.finish_partial(value, action="replace")
        payload = (self.authority / "00000001.payload").stat()
        self.finish_partial(value, action="replace")
        self.assertEqual((self.authority / "00000001.payload").stat().st_ino, payload.st_ino)
        self.assertFalse((self.authority / "00000001.event").exists())

    def test_partial_owner_conflict_and_external_link(self):
        value, pending, _, _ = self.partial_fixture()
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(IntegrationError):
                self.partial_plan(value)
        finally:
            os.close(fd)
        os.link(pending, self.base / "external")
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        self.assertFalse((self.authority / "quarantine").exists())

    def test_partial_unattributed_and_corrupt_preparation_block(self):
        value, pending, raw, _ = self.partial_fixture()
        unknown = self.authority / "unknown"
        unknown.write_bytes(b"unknown")
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        unknown.unlink()
        prep = self.authority / "00000001.prep"
        prep.chmod(0o600)
        prep.write_bytes(b"{")
        prep.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        self.assertEqual(pending.read_bytes(), raw)

    def test_partial_wrong_source_and_replacement_without_quarantine(self):
        value, _, _, _ = self.partial_fixture()
        with self.assertRaises(IntegrationError):
            self.partial_plan(value, action="replace")
        altered = host.decode(host.encoded(value))
        altered["record"]["authority"]["pins"] = altered["record"]["authority"]["pins"][:1]
        with self.assertRaises(IntegrationError):
            self.partial_plan(altered)

    def test_partial_quarantine_tamper_and_unfinished_file_block(self):
        value, _, _, _ = self.partial_fixture()
        self.finish_partial(value)
        envelope = self.authority / "quarantine/00000001.payload"
        raw = envelope.read_bytes()
        extra = self.authority / "quarantine/00000001.payload.pending"
        extra.write_bytes(b"unfinished")
        extra.chmod(0o600)
        with self.assertRaises(IntegrationError):
            self.partial_plan(value, action="replace")
        extra.unlink()
        envelope.chmod(0o600)
        envelope.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        envelope.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.partial_plan(value, action="replace")

    def test_partial_quarantine_directory_symlink_and_permissions(self):
        value, pending, raw, _ = self.partial_fixture()
        destination = self.base / "outside"
        destination.mkdir(mode=0o700)
        q = self.authority / "quarantine"
        q.symlink_to(destination, target_is_directory=True)
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        q.unlink()
        q.mkdir(mode=0o755)
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        self.assertEqual(pending.read_bytes(), raw)
        self.assertEqual(list(destination.iterdir()), [])

    def test_partial_quarantine_header_tamper_blocks(self):
        value, _, _, _ = self.partial_fixture()
        self.finish_partial(value)
        envelope = self.authority / "quarantine/00000001.payload"
        raw = bytearray(envelope.read_bytes())
        raw[40] ^= 1
        envelope.chmod(0o600)
        envelope.write_bytes(raw)
        envelope.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.partial_plan(value, action="replace")

    def test_partial_replacement_preserves_existing_payload(self):
        value, _, _, full = self.partial_fixture()
        self.finish_partial(value)
        final = self.authority / "00000001.payload"
        final.write_bytes(full)
        final.chmod(0o400)
        inode = final.stat().st_ino
        with self.assertRaises(IntegrationError):
            self.partial_plan(value, action="replace")
        self.assertEqual(final.read_bytes(), full)
        self.assertEqual(final.stat().st_ino, inode)

    def test_partial_revoked_and_host_pending_block(self):
        value, pending, raw, _ = self.partial_fixture()
        common = self.repo / ".git"
        marker = common / (host.PENDING + "incomplete")
        marker.write_bytes(b"{")
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        marker.unlink()
        (common / host.TOMBSTONE).write_bytes(b"{}")
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        self.assertEqual(pending.read_bytes(), raw)

    def test_partial_change_keeps_locator_and_change_intent(self):
        value, _, _, full = self.partial_fixture(change=True)
        common = self.repo / ".git"
        locator = (common / host.LOCATOR).read_bytes()
        change = (common / host.CHANGE).read_bytes()
        previous = host.decode(locator)["registration_sha256"]
        self.finish_partial(value, previous=previous)
        self.finish_partial(value, action="replace", previous=previous)
        self.assertEqual((common / host.LOCATOR).read_bytes(), locator)
        self.assertEqual((common / host.CHANGE).read_bytes(), change)
        self.assertEqual((self.authority / "00000002.payload").read_bytes(), full)
        self.assertFalse((self.authority / "00000002.event").exists())

    def envelope_fixture(self, both=False, kind=1, change=False):
        value, source, raw, _ = self.partial_fixture(kind=kind, change=change)
        previous = None
        if change:
            previous = host.decode((self.repo / ".git" / host.LOCATOR).read_bytes())["registration_sha256"]
        plan = self.partial_plan(value, kind=kind, previous=previous)
        origin = {"schema": "golem.intent-partial-intent.v1", "plan": plan["plan"], "plan_sha256": plan["plan_sha256"]}
        intent_path = self.repo / ".git" / host.PARTIAL_RECOVERY
        intent_path.write_bytes(host.encoded(origin))
        intent_path.chmod(0o400)
        before = plan["plan"]["before"]
        # Exact disposable crash image: complete envelope before/after final link.
        wire = bytearray(320)
        wire[:8] = b"GIQUA001"
        struct.pack_into("<QQQQQQ", wire, 8, before["sequence"], 0, kind, before["device"], before["inode"], len(raw))
        for offset, digest in ((64, before["preparation"]), (96, before["operation"]), (128, before["request"]),
                               (160, before["final_digest"]), (192, plan["plan_sha256"])):
            wire[offset:offset + 32] = bytes.fromhex(digest)
        wire[224:224 + len(source.name)] = source.name.encode("ascii")
        wire.extend(raw)
        wire[288:320] = bytes.fromhex(host.sha(bytes(wire)))
        q = self.authority / "quarantine"
        q.mkdir(mode=0o700)
        final = q / f'{before["sequence"]:08d}.{("prep", "payload", "event")[kind]}'
        pending = final.with_name(final.name + ".pending")
        pending.write_bytes(wire)
        pending.chmod(0o400)
        if both:
            os.link(pending, final)
        return value, source, final, pending, previous

    def envelope_plan(self, value, kind=1, previous=None):
        return lifecycle.envelope_recovery_plan(self.repo, value["record"], kind, git=self.git_binary,
            bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve(), previous=previous)

    def finish_envelope_fixture(self, value, kind=1, previous=None):
        plan = self.envelope_plan(value, kind, previous)
        return lifecycle.finish_envelope(self.repo, value["record"], kind, plan["plan_sha256"], git=self.git_binary,
            bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve(), previous=previous, approve_local_owner=True)

    def host_alias_fixture(self, receipt=False):
        value, _, _, _, _ = self.envelope_fixture()
        common = self.repo / ".git"
        if receipt:
            self.finish_envelope_fixture(value)
            final = next(common.glob(host.HISTORY + "envelope-recovery-*.json"))
        else:
            final = common / host.PARTIAL_RECOVERY
        pending = common / (host.PENDING + "a" * 32)
        os.link(final, pending)
        return value, final, pending

    def host_alias_plan(self, value, final):
        return lifecycle.host_alias_recovery_plan(self.repo, value["record"], final.name, git=self.git_binary)

    def finish_host_alias(self, value, final):
        plan = self.host_alias_plan(value, final)
        return lifecycle.recover_host_alias(self.repo, value["record"], final.name, plan["plan_sha256"],
            git=self.git_binary, approve_local_owner=True)

    def test_host_alias_preserves_native_and_final(self):
        value, final, pending = self.host_alias_fixture()
        original, inode = final.read_bytes(), final.stat().st_ino
        files = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        native = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        self.host_alias_plan(value, final)
        self.assertEqual(files, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        with patch.object(lifecycle, "_alias_native", side_effect=AssertionError("native forbidden")):
            self.finish_host_alias(value, final)
        self.assertFalse(pending.exists())
        self.assertEqual((final.read_bytes(), final.stat().st_ino), (original, inode))
        self.assertEqual(native, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})
        self.assertFalse((self.repo / ".git" / host.LOCATOR).exists())

    def test_host_alias_receipt(self):
        value, final, pending = self.host_alias_fixture(receipt=True)
        original = final.read_bytes()
        self.finish_host_alias(value, final)
        self.assertFalse(pending.exists())
        self.assertEqual(final.read_bytes(), original)

    def test_host_alias_approval_and_lock(self):
        value, final, pending = self.host_alias_fixture()
        plan = self.host_alias_plan(value, final)
        with self.assertRaisesRegex(IntegrationError, "OWNER_APPROVAL_REQUIRED"):
            lifecycle.recover_host_alias(self.repo, value["record"], final.name, plan["plan_sha256"], git=self.git_binary)
        with self.assertRaisesRegex(IntegrationError, "PLAN_STALE"):
            lifecycle.recover_host_alias(self.repo, value["record"], final.name, "0" * 64,
                git=self.git_binary, approve_local_owner=True)
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(IntegrationError, "AUTHORITY_OWNER_BUSY"):
                self.host_alias_plan(value, final)
        finally:
            os.close(fd)
        self.assertTrue(pending.exists())

    def test_host_alias_independent_copy_extra_link_and_missing_final(self):
        value, final, pending = self.host_alias_fixture()
        extra = final.with_name("extra")
        os.link(final, extra)
        with self.assertRaises(IntegrationError):
            self.host_alias_plan(value, final)
        extra.unlink()
        raw = pending.read_bytes()
        pending.unlink()
        pending.write_bytes(raw)
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.host_alias_plan(value, final)
        final.unlink()
        with self.assertRaises(OSError):
            self.host_alias_plan(value, final)
        self.assertEqual(pending.read_bytes(), raw)

    def test_host_alias_approval_failure_preserves_alias(self):
        value, final, pending = self.host_alias_fixture()
        with patch.object(host, "_publish", side_effect=OSError("approval failed")):
            with self.assertRaises(OSError):
                self.finish_host_alias(value, final)
        self.assertEqual(final.stat().st_ino, pending.stat().st_ino)

    def test_host_alias_receipt_failure_requires_fresh_approval(self):
        value, final, pending = self.host_alias_fixture()
        with patch.object(lifecycle, "_archive", side_effect=OSError("receipt failed")):
            with self.assertRaises(OSError):
                self.finish_host_alias(value, final)
        self.assertFalse(pending.exists())
        self.assertTrue((self.repo / ".git" / host.HOST_ALIAS_RECOVERY).exists())
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)
        self.finish_host_alias(value, final)
        self.assertFalse((self.repo / ".git" / host.HOST_ALIAS_RECOVERY).exists())

    def test_host_alias_corrupt_record_denied(self):
        value, final, pending = self.host_alias_fixture()
        final.chmod(0o600)
        final.write_bytes(b'{"schema":')
        final.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.host_alias_plan(value, final)
        self.assertTrue(pending.exists())

    def test_host_alias_native_intent(self):
        value = self.prepared_fixture(change=True)
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        plan = lifecycle.native_recovery_plan(self.repo, value["record"], git=self.git_binary, bridge=bridge)
        common = self.repo / ".git"
        final = common / host.NATIVE_RECOVERY
        final.write_bytes(host.encoded({"schema": "golem.intent-native-recovery-intent.v1", **plan}))
        final.chmod(0o400)
        pending = common / (host.PENDING + "b" * 32)
        os.link(final, pending)
        self.finish_host_alias(value, final)
        self.assertTrue(final.exists())
        self.assertFalse(pending.exists())
        self.assertFalse((self.authority / "00000002.event").exists())

    def test_host_alias_native_history(self):
        value = self.prepared_fixture()
        self.finish_native_fixture(value)
        common = self.repo / ".git"
        final = next(common.glob(host.HISTORY + "native-recovery-*.json"))
        pending = common / (host.PENDING + "b" * 32)
        os.link(final, pending)
        self.finish_host_alias(value, final)
        self.assertFalse(pending.exists())

    def test_host_alias_alias_receipt(self):
        value, _, _ = self.alias_fixture()
        self.finish_alias_fixture(value)
        common = self.repo / ".git"
        final = next(common.glob(host.HISTORY + "alias-recovery-*.json"))
        pending = common / (host.PENDING + "b" * 32)
        os.link(final, pending)
        self.finish_host_alias(value, final)
        self.assertFalse(pending.exists())

    def test_host_alias_partial_receipt(self):
        value, _, _, _ = self.partial_fixture()
        self.finish_partial(value)
        common = self.repo / ".git"
        final = next(common.glob(host.HISTORY + "partial-recovery-*.json"))
        pending = common / (host.PENDING + "b" * 32)
        os.link(final, pending)
        self.finish_host_alias(value, final)
        self.assertFalse(pending.exists())

    def test_host_alias_envelope_intent(self):
        value, _, _, _, _ = self.envelope_fixture()
        plan = self.envelope_plan(value)
        common = self.repo / ".git"
        final = common / host.ENVELOPE_RECOVERY
        final.write_bytes(host.encoded({"schema": "golem.intent-envelope-intent.v1", **plan}))
        final.chmod(0o400)
        pending = common / (host.PENDING + "b" * 32)
        os.link(final, pending)
        self.finish_host_alias(value, final)
        self.assertTrue(final.exists())
        self.assertFalse(pending.exists())

    def test_envelope_pending_only_finish_preserves_source_and_separate_steps(self):
        value, source, final, pending, previous = self.envelope_fixture()
        raw, inode, envelope = source.read_bytes(), source.stat().st_ino, pending.read_bytes()
        common = self.repo / ".git"
        original = (common / host.PARTIAL_RECOVERY).read_bytes()
        files = {str(p.relative_to(self.base)): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        plan = self.envelope_plan(value)
        self.assertEqual(files, {str(p.relative_to(self.base)): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        result = self.finish_envelope_fixture(value)
        self.assertFalse(pending.exists())
        self.assertEqual(final.read_bytes(), envelope)
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(source.stat().st_ino, inode)
        self.assertEqual(result["after"]["usage"], plan["plan"]["current"]["usage"])
        self.assertEqual((common / host.PARTIAL_RECOVERY).read_bytes(), original)
        self.assertFalse((self.authority / "00000001.payload").exists())
        self.assertFalse((self.authority / "00000001.event").exists())
        self.assertFalse((common / host.LOCATOR).exists())
        self.finish_partial(value)
        self.assertFalse(source.exists())
        self.assertFalse((self.authority / "00000001.payload").exists())

    def publication_fixture(self, receipt=False):
        value, final, pending = self.host_alias_fixture(receipt=receipt)
        final.unlink()
        return value, final, pending

    def fragment_fixture(self, kind=1, change=False):
        value, source, final, pending, previous = self.envelope_fixture(kind=kind, change=change)
        cut = pending.read_bytes()[:-1]
        pending.chmod(0o600)
        pending.write_bytes(cut)
        pending.chmod(0o400)
        return value, source, final, pending, previous

    def fragment_plan(self, value, action="preserve", kind=1, previous=None):
        return lifecycle.fragment_recovery_plan(self.repo, value["record"], kind, action,
            git=self.git_binary, bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve(), previous=previous)

    def finish_fragment(self, value, action="preserve", kind=1, previous=None):
        plan = self.fragment_plan(value, action, kind, previous)
        return lifecycle.recover_fragment(self.repo, value["record"], kind, action, plan["plan_sha256"],
            git=self.git_binary, bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve(),
            previous=previous, approve_local_owner=True)

    def test_fragment_preserve_and_separate_detach(self):
        value, source, final, pending, _ = self.fragment_fixture()
        raw, cut = source.read_bytes(), pending.read_bytes()
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        self.fragment_plan(value)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        self.finish_fragment(value)
        preserved = final.with_name(final.name + ".fragment")
        self.assertEqual(preserved.read_bytes()[320:], cut)
        self.assertEqual(pending.read_bytes(), cut)
        self.assertFalse(final.exists())
        self.finish_fragment(value, "detach")
        self.assertFalse(pending.exists())
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(preserved.read_bytes()[320:], cut)
        self.assertFalse((self.authority / "00000001.event").exists())
        self.assertFalse((self.repo / ".git" / host.LOCATOR).exists())

    def damage_fixture(self, kind=1, change=False):
        value, source, final, envelope, previous = self.fragment_fixture(kind, change)
        with patch.object(lifecycle, "_archive", side_effect=OSError("receipt")):
            with self.assertRaises(OSError):
                self.finish_fragment(value, kind=kind, previous=previous)
        preserved = final.with_name(final.name + ".fragment")
        cut = preserved.with_name(preserved.name + ".pending")
        preserved.rename(cut)
        raw = cut.read_bytes()[:-1]
        cut.chmod(0o600)
        cut.write_bytes(raw)
        cut.chmod(0o400)
        return value, source, envelope, cut, previous

    def damage_plan(self, value, action="preserve", kind=1, previous=None):
        return lifecycle.damage_recovery_plan(self.repo, value["record"], kind, action,
            git=self.git_binary, bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve(), previous=previous)

    def finish_damage(self, value, action="preserve", kind=1, previous=None):
        plan = self.damage_plan(value, action, kind, previous)
        return lifecycle.recover_damage(self.repo, value["record"], kind, action, plan["plan_sha256"],
            git=self.git_binary, bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve(),
            previous=previous, approve_local_owner=True)

    def test_damage_preserve_separate_detach_read_only(self):
        value, source, envelope, cut, _ = self.damage_fixture()
        raw, env, fragment = source.read_bytes(), envelope.read_bytes(), cut.read_bytes()
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        self.damage_plan(value)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        receipt = self.finish_damage(value)
        final = cut.with_name(cut.name.removesuffix(".pending") + ".damage")
        self.assertEqual(final.read_bytes()[384:], fragment)
        self.assertEqual(cut.read_bytes(), fragment)
        self.assertEqual(receipt["after"]["object_bytes"], len(fragment) + 384)
        self.finish_damage(value, "detach")
        self.assertFalse(cut.exists())
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(envelope.read_bytes(), env)
        self.assertTrue((self.repo / ".git" / host.FRAGMENT_RECOVERY).exists())
        self.assertFalse((self.repo / ".git" / host.DAMAGE_RECOVERY).exists())
        self.assertFalse((self.repo / ".git" / host.LOCATOR).exists())
        self.assertFalse((self.authority / "00000001.event").exists())

    def test_damage_finish_pending_and_pair(self):
        value, _, _, cut, _ = self.damage_fixture()
        self.finish_damage(value)
        final = cut.with_name(cut.name.removesuffix(".pending") + ".damage")
        pending = final.with_name(final.name + ".pending")
        original = final.read_bytes()
        final.rename(pending)
        self.finish_damage(value, "finish")
        self.assertEqual(final.read_bytes(), original)
        self.assertFalse(pending.exists())
        os.link(final, pending)
        self.finish_damage(value, "finish")
        self.assertFalse(pending.exists())
        self.assertTrue(cut.exists())

    def test_damage_receipt_reentry(self):
        value, _, _, _, _ = self.damage_fixture()
        for action in ("preserve", "detach"):
            with patch.object(lifecycle, "_archive", side_effect=OSError("receipt")):
                with self.assertRaises(OSError):
                    self.finish_damage(value, action)
            self.finish_damage(value, action)

    def test_damage_corrupt_terminal_object_stays_blocked(self):
        value, _, _, cut, _ = self.damage_fixture()
        self.finish_damage(value)
        final = cut.with_name(cut.name.removesuffix(".pending") + ".damage")
        original = final.read_bytes()
        final.chmod(0o600)
        final.write_bytes(original[:-1])
        final.chmod(0o400)
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        with self.assertRaises(IntegrationError):
            self.damage_plan(value, "detach")
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def test_damage_short_header_and_extra_link_denied(self):
        value, _, _, cut, _ = self.damage_fixture()
        raw = cut.read_bytes()
        cut.chmod(0o600)
        cut.write_bytes(raw[:319])
        cut.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.damage_plan(value)
        cut.chmod(0o600)
        cut.write_bytes(raw)
        cut.chmod(0o400)
        os.link(cut, cut.with_name("unexpected"))
        with self.assertRaises(IntegrationError):
            self.damage_plan(value)

    def test_damage_approval_failure_no_native_write(self):
        value, _, _, cut, _ = self.damage_fixture()
        before = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        with patch.object(host, "_publish", side_effect=OSError("intent")):
            with self.assertRaises(OSError):
                self.finish_damage(value)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})

    def test_damage_changed_parent_approval_denied(self):
        value, _, _, _, _ = self.damage_fixture()
        path = self.repo / ".git" / host.FRAGMENT_RECOVERY
        raw = host.decode(path.read_bytes())
        raw["plan"]["current"]["truncated_inode"] += 1
        raw["plan_sha256"] = host.sha(host.encoded(raw["plan"]))
        path.chmod(0o600)
        path.write_bytes(host.encoded(raw))
        path.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.damage_plan(value)

    def test_damage_change_registration(self):
        value, _, _, _, previous = self.damage_fixture(kind=2, change=True)
        locator = (self.repo / ".git" / host.LOCATOR).read_bytes()
        self.finish_damage(value, kind=2, previous=previous)
        self.finish_damage(value, "detach", kind=2, previous=previous)
        self.assertEqual((self.repo / ".git" / host.LOCATOR).read_bytes(), locator)

    def test_damage_owner_stale_and_pending_denied(self):
        value, _, _, cut, _ = self.damage_fixture()
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        plan = self.damage_plan(value)
        with self.assertRaises(IntegrationError):
            lifecycle.recover_damage(self.repo, value["record"], 1, "preserve", plan["plan_sha256"],
                git=self.git_binary, bridge=bridge)
        with self.assertRaises(IntegrationError):
            lifecycle.recover_damage(self.repo, value["record"], 1, "preserve", "0" * 64,
                git=self.git_binary, bridge=bridge, approve_local_owner=True)
        unrelated = self.repo / ".git" / (host.PENDING + "a" * 32)
        unrelated.write_bytes(b"pending")
        with self.assertRaises(IntegrationError):
            self.damage_plan(value)
        self.assertTrue(cut.exists())

    def test_damage_independent_copy_denied(self):
        value, _, _, cut, _ = self.damage_fixture()
        self.finish_damage(value)
        final = cut.with_name(cut.name.removesuffix(".pending") + ".damage")
        pending = final.with_name(final.name + ".pending")
        pending.write_bytes(final.read_bytes())
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.damage_plan(value, "finish")
        self.assertTrue(final.exists() and pending.exists() and cut.exists())

    def test_damage_reentry_changed_cut_denied(self):
        value, _, _, cut, _ = self.damage_fixture()
        with patch.object(lifecycle, "_alias_native", wraps=lifecycle._alias_native) as native:
            original = native._mock_wraps
            def fail_write(*args, **kwargs):
                if len(args) > 4:
                    raise OSError("before native publication")
                return original(*args, **kwargs)
            native.side_effect = fail_write
            with self.assertRaises(OSError):
                self.finish_damage(value)
        raw = cut.read_bytes()
        cut.chmod(0o600)
        cut.write_bytes(raw[:-1])
        cut.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.damage_plan(value)

    def test_fragment_complete_pending_finish(self):
        value, _, final, pending, _ = self.fragment_fixture()
        self.finish_fragment(value)
        preserved = final.with_name(final.name + ".fragment")
        staged = preserved.with_name(preserved.name + ".pending")
        preserved.rename(staged)
        self.finish_fragment(value, "finish")
        self.assertTrue(pending.exists())
        self.assertTrue(preserved.exists())
        self.assertFalse(staged.exists())

    def test_fragment_pair_finish(self):
        value, _, final, pending, _ = self.fragment_fixture()
        self.finish_fragment(value)
        preserved = final.with_name(final.name + ".fragment")
        staged = preserved.with_name(preserved.name + ".pending")
        os.link(preserved, staged)
        self.finish_fragment(value, "finish")
        self.assertTrue(pending.exists())
        self.assertFalse(staged.exists())

    def test_fragment_receipt_failure_reentry(self):
        value, _, _, _, _ = self.fragment_fixture()
        with patch.object(lifecycle, "_archive", side_effect=OSError("receipt")):
            with self.assertRaises(OSError):
                self.finish_fragment(value)
        self.finish_fragment(value)
        with patch.object(lifecycle, "_archive", side_effect=OSError("receipt")):
            with self.assertRaises(OSError):
                self.finish_fragment(value, "detach")
        self.finish_fragment(value, "detach")

    def test_fragment_rejects_damaged_header_and_preserved_object(self):
        value, _, final, pending, _ = self.fragment_fixture()
        cut = pending.read_bytes()
        pending.chmod(0o600)
        pending.write_bytes(cut[:319])
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.fragment_plan(value)
        pending.chmod(0o600)
        pending.write_bytes(cut)
        pending.chmod(0o400)
        self.finish_fragment(value)
        preserved = final.with_name(final.name + ".fragment")
        preserved.chmod(0o600)
        preserved.write_bytes(preserved.read_bytes()[:-1])
        preserved.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.fragment_plan(value, "detach")
        self.assertEqual(pending.read_bytes(), cut)

    def test_fragment_approval_failure_and_owner(self):
        value, _, final, pending, _ = self.fragment_fixture()
        with patch.object(host, "_publish", side_effect=OSError("approval")):
            with self.assertRaises(OSError):
                self.finish_fragment(value)
        self.assertFalse(final.with_name(final.name + ".fragment").exists())
        self.assertTrue(pending.exists())
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(IntegrationError):
                self.fragment_plan(value)
        finally:
            os.close(fd)

    def test_fragment_change_registration_keeps_locator(self):
        value, _, _, _, previous = self.fragment_fixture(kind=2, change=True)
        locator = (self.repo / ".git" / host.LOCATOR).read_bytes()
        self.finish_fragment(value, kind=2, previous=previous)
        self.finish_fragment(value, "detach", kind=2, previous=previous)
        self.assertEqual((self.repo / ".git" / host.LOCATOR).read_bytes(), locator)

    def test_fragment_original_approval_and_extra_link_denied(self):
        value, _, _, pending, _ = self.fragment_fixture()
        intent = self.repo / ".git" / host.PARTIAL_RECOVERY
        original = intent.read_bytes()
        intent.unlink()
        with self.assertRaises(OSError):
            self.fragment_plan(value)
        intent.write_bytes(original)
        intent.chmod(0o400)
        os.link(pending, self.base / "extra-fragment")
        with self.assertRaises(IntegrationError):
            self.fragment_plan(value)

    def test_fragment_stale_approval_and_unrelated_pending(self):
        value, _, _, pending, _ = self.fragment_fixture()
        plan = self.fragment_plan(value)
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        with self.assertRaisesRegex(IntegrationError, "OWNER_APPROVAL_REQUIRED"):
            lifecycle.recover_fragment(self.repo, value["record"], 1, "preserve", plan["plan_sha256"],
                git=self.git_binary, bridge=bridge)
        with self.assertRaisesRegex(IntegrationError, "PLAN_STALE"):
            lifecycle.recover_fragment(self.repo, value["record"], 1, "preserve", "0" * 64,
                git=self.git_binary, bridge=bridge, approve_local_owner=True)
        (self.repo / ".git" / (host.PENDING + "e" * 32)).write_bytes(b"unknown")
        with self.assertRaises(IntegrationError):
            self.fragment_plan(value)
        self.assertTrue(pending.exists())

    def test_fragment_reentry_changed_cut_denied(self):
        value, _, final, pending, _ = self.fragment_fixture()
        original = lifecycle._alias_native
        def fail_write(*args, **kwargs):
            if len(args) > 4 and args[4] is not None:
                raise OSError("interrupted before native")
            return original(*args, **kwargs)
        with patch.object(lifecycle, "_alias_native", side_effect=fail_write):
            with self.assertRaises(OSError):
                self.finish_fragment(value)
        pending.chmod(0o600)
        pending.write_bytes(pending.read_bytes()[:-1])
        pending.chmod(0o400)
        with self.assertRaisesRegex(IntegrationError, "FRAGMENT_STATE_CHANGED"):
            self.fragment_plan(value)
        self.assertFalse(final.with_name(final.name + ".fragment").exists())

    def test_fragment_independent_copy_finish_denied(self):
        value, _, final, pending, _ = self.fragment_fixture()
        self.finish_fragment(value)
        preserved = final.with_name(final.name + ".fragment")
        staged = preserved.with_name(preserved.name + ".pending")
        staged.write_bytes(preserved.read_bytes())
        staged.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.fragment_plan(value, "finish")
        self.assertTrue(pending.exists())

    def test_fragment_conflicting_change_intent_denied(self):
        value, _, _, pending, previous = self.fragment_fixture(change=True)
        path = self.repo / ".git" / host.CHANGE
        change = host.decode(path.read_bytes())
        change["plan"]["after"] = change["plan"]["before"]
        change["plan_sha256"] = host.sha(host.encoded(change["plan"]))
        path.chmod(0o600)
        path.write_bytes(host.encoded(change))
        path.chmod(0o400)
        with self.assertRaisesRegex(IntegrationError, "CHANGE_INTENT_INVALID"):
            self.fragment_plan(value, previous=previous)
        self.assertTrue(pending.exists())

    def publication_plan(self, value, final, pending):
        return lifecycle.host_publication_plan(self.repo, value["record"], pending.name, final.name, git=self.git_binary)

    def terminal_fixture(self, family, kind):
        value, target, original_pending = self.publication_fixture()
        if family == "host-alias":
            os.link(original_pending, target)
        def finish():
            if family == "host-publication":
                return self.finish_publication(value, target, original_pending)
            plan = lifecycle.host_alias_recovery_plan(self.repo, value["record"], target.name, git=self.git_binary)
            return lifecycle.recover_host_alias(self.repo, value["record"], target.name, plan["plan_sha256"],
                git=self.git_binary, approve_local_owner=True)
        marker = host.HOST_PUBLICATION if family == "host-publication" else host.HOST_ALIAS_RECOVERY
        if kind == "intent":
            unlink, link = os.unlink, os.link
            def stop_link(src, dst, *args, **kwargs):
                if dst == target.name:
                    raise OSError("original target link")
                return link(src, dst, *args, **kwargs)
            def stop_unlink(name, *args, **kwargs):
                if name == original_pending.name:
                    raise OSError("original alias unlink")
                return unlink(name, *args, **kwargs)
            with patch.object(os, "link", side_effect=stop_link), patch.object(os, "unlink", side_effect=stop_unlink):
                with self.assertRaises(OSError):
                    finish()
            final = self.repo / ".git" / marker
        elif kind == "receipt":
            finish()
            final = next((self.repo / ".git").glob(host.HISTORY + family + "-recovery-*.json"))
        else:
            with patch.object(lifecycle, "_archive", side_effect=OSError("receipt")):
                with self.assertRaises(OSError):
                    finish()
            archive = lifecycle._archive
            def stop_receipt(fd, common, name, raw):
                if name.startswith(host.HISTORY + family + "-recovery-"):
                    raise OSError("receipt again")
                return archive(fd, common, name, raw)
            with patch.object(lifecycle, "_archive", side_effect=stop_receipt):
                with self.assertRaises(OSError):
                    finish()
            final = next((self.repo / ".git").glob(host.HISTORY + family + "-approval-*.json"))
        pending = final.with_name(host.PENDING + "e" * 32)
        final.rename(pending)
        return value, final, pending, target, original_pending

    def terminal_plan(self, value, final, pending):
        return lifecycle.host_terminal_plan(self.repo, value["record"], pending.name, final.name, git=self.git_binary)

    def finish_terminal(self, value, final, pending):
        plan = self.terminal_plan(value, final, pending)
        return lifecycle.finish_host_terminal(self.repo, value["record"], pending.name, final.name,
            plan["plan_sha256"], git=self.git_binary, approve_local_owner=True)

    def check_terminal(self, family, kind):
        value, final, pending, target, original_pending = self.terminal_fixture(family, kind)
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        native = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        original_state = (target.exists(), original_pending.exists())
        raw = pending.read_bytes()
        self.terminal_plan(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        with patch.object(lifecycle, "_alias_native", side_effect=AssertionError("native invoked")):
            self.finish_terminal(value, final, pending)
            os.link(final, pending)
            self.finish_terminal(value, final, pending)
        self.assertEqual(final.read_bytes(), raw)
        self.assertFalse(pending.exists())
        self.assertEqual(original_state, (target.exists(), original_pending.exists()))
        self.assertEqual(native, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})

    def test_terminal_publication_intent(self):
        self.check_terminal("host-publication", "intent")

    def final_fixture(self, kind):
        value, target, original_pending, _, _ = self.terminal_fixture("host-publication", "intent")
        if kind == "intent":
            link = os.link
            def stop(src, dst, *args, **kwargs):
                if dst == target.name:
                    raise OSError("terminal target link")
                return link(src, dst, *args, **kwargs)
            with patch.object(os, "link", side_effect=stop):
                with self.assertRaises(OSError):
                    self.finish_terminal(value, target, original_pending)
            final = self.repo / ".git" / host.HOST_TERMINAL
        elif kind == "receipt":
            self.finish_terminal(value, target, original_pending)
            final = next((self.repo / ".git").glob(host.HISTORY + "host-terminal-recovery-*.json"))
        else:
            archive = lifecycle._archive
            def stop_receipt(fd, common, name, raw):
                if name.startswith(host.HISTORY + "host-terminal-recovery-"):
                    raise OSError("terminal receipt")
                return archive(fd, common, name, raw)
            with patch.object(lifecycle, "_archive", side_effect=stop_receipt):
                for _ in range(2):
                    with self.assertRaises(OSError):
                        self.finish_terminal(value, target, original_pending)
            final = next((self.repo / ".git").glob(host.HISTORY + "host-terminal-approval-*.json"))
        pending = final.with_name(host.PENDING + "d" * 32)
        final.rename(pending)
        return value, final, pending

    def final_plan(self, value, final, pending):
        return lifecycle.host_final_plan(self.repo, value["record"], pending.name, final.name, git=self.git_binary)

    def finish_final(self, value, final, pending):
        plan = self.final_plan(value, final, pending)
        return lifecycle.finish_host_final(self.repo, value["record"], pending.name, final.name,
            plan["plan_sha256"], git=self.git_binary, approve_local_owner=True)

    def check_final(self, kind):
        value, final, pending = self.final_fixture(kind)
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        native = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        raw = pending.read_bytes()
        self.final_plan(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        with patch.object(lifecycle, "_alias_native", side_effect=AssertionError("native invoked")):
            self.finish_final(value, final, pending)
            os.link(final, pending)
            self.finish_final(value, final, pending)
        self.assertEqual(raw, final.read_bytes())
        self.assertFalse(pending.exists())
        self.assertEqual(native, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})

    def test_final_terminal_intent(self):
        self.check_final("intent")

    def test_final_terminal_receipt(self):
        self.check_final("receipt")

    def test_final_terminal_reapproval(self):
        self.check_final("approval")

    def test_final_pair_receipt_reentry(self):
        value, final, pending = self.final_fixture("intent")
        unlink = os.unlink
        def stop(name, *args, **kwargs):
            if name == pending.name:
                raise OSError("final pair")
            return unlink(name, *args, **kwargs)
        with patch.object(os, "unlink", side_effect=stop):
            with self.assertRaises(OSError):
                self.finish_final(value, final, pending)
        self.assertEqual(final.stat().st_ino, pending.stat().st_ino)
        archive = lifecycle._archive
        def stop_receipt(fd, common, name, raw):
            if name.startswith(host.HISTORY + "host-final-recovery-"):
                raise OSError("final receipt")
            return archive(fd, common, name, raw)
        with patch.object(lifecycle, "_archive", side_effect=stop_receipt):
            with self.assertRaises(OSError):
                self.finish_final(value, final, pending)
        self.assertFalse(pending.exists())
        self.finish_final(value, final, pending)

    def test_final_denies_partial_self_and_unknown_pending(self):
        value, final, pending = self.final_fixture("intent")
        raw = pending.read_bytes()
        pending.chmod(0o600)
        pending.write_bytes(raw[:-1])
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.final_plan(value, final, pending)
        pending.chmod(0o600)
        pending.write_bytes(raw)
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.final_plan(value, final.with_name(host.HOST_FINAL), pending)
        (pending.parent / (host.PENDING + "f" * 32)).write_bytes(b"unknown")
        with self.assertRaises(IntegrationError):
            self.final_plan(value, final, pending)

    def test_final_requires_owner_and_fresh_plan(self):
        value, final, pending = self.final_fixture("intent")
        plan = self.final_plan(value, final, pending)
        with self.assertRaises(IntegrationError):
            lifecycle.finish_host_final(self.repo, value["record"], pending.name, final.name,
                plan["plan_sha256"], git=self.git_binary)
        with self.assertRaises(IntegrationError):
            lifecycle.finish_host_final(self.repo, value["record"], pending.name, final.name,
                "0" * 64, git=self.git_binary, approve_local_owner=True)

    def test_final_partial_approval_blocks_all_reentry(self):
        value, final, pending = self.final_fixture("intent")
        marker = self.repo / ".git" / host.HOST_FINAL
        marker.write_bytes(b'{"schema":')
        marker.chmod(0o400)
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        for plan in (self.final_plan, self.terminal_plan, self.publication_plan):
            with self.assertRaises(IntegrationError):
                plan(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def test_final_approval_failure_preserves_source(self):
        value, final, pending = self.final_fixture("intent")
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        with patch.object(host, "_publish", side_effect=OSError("final approval")):
            with self.assertRaises(OSError):
                self.finish_final(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def test_final_independent_copy_denied(self):
        value, final, pending = self.final_fixture("intent")
        final.write_bytes(pending.read_bytes())
        final.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.final_plan(value, final, pending)

    def test_final_marker_blocks_all_public_d01_entrypoints(self):
        value = self.enroll()
        marker = self.repo / ".git" / host.HOST_FINAL
        marker.write_bytes(b'{"schema":')
        marker.chmod(0o400)
        arguments = {"root": self.repo, "authority": self.authority, "pins": [self.pin],
            "registration_sha256": value["registration_sha256"],
            "expected_registration_sha256": value["registration_sha256"],
            "record": value["record"], "target_record": value["record"], "kind": 0,
            "action": "preserve", "git": self.git_binary, "bridge": self.pin,
            "reviewed_plan_sha256": "0" * 64, "approve_local_owner": True,
            "pending_name": host.PENDING + "b" * 32, "final_name": host.NATIVE_RECOVERY}
        entries = [host.registration_plan, host.register, host.revocation_plan, host.revoke,
            lifecycle.change_plan, lifecycle.change, lifecycle.recovery_plan, lifecycle.recover,
            lifecycle.native_recovery_plan, lifecycle.recover_native,
            lifecycle.alias_recovery_plan, lifecycle.recover_alias,
            lifecycle.partial_recovery_plan, lifecycle.recover_partial,
            lifecycle.envelope_recovery_plan, lifecycle.finish_envelope,
            lifecycle.fragment_recovery_plan, lifecycle.recover_fragment,
            lifecycle.damage_recovery_plan, lifecycle.recover_damage,
            lifecycle.host_alias_recovery_plan, lifecycle.recover_host_alias,
            lifecycle.host_publication_plan, lifecycle.finish_host_publication,
            lifecycle.host_terminal_plan, lifecycle.finish_host_terminal]
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        for entry in entries:
            with self.subTest(entry=entry.__name__):
                kwargs = {name: arguments[name] for name in inspect.signature(entry).parameters if name in arguments}
                with self.assertRaisesRegex(IntegrationError, "HOST_FINAL_REQUIRED"):
                    entry(**kwargs)
        with self.assertRaisesRegex(IntegrationError, "HOST_FINAL_REQUIRED"):
            with host.authorized_root(self.repo, value["registration_sha256"], git=self.git_binary):
                self.fail("authority opened")
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def check_final_partial_publication(self, stage):
        value, final, pending = self.final_fixture("intent")
        if stage == "approval":
            unlink = os.unlink
            def stop_pair(name, *args, **kwargs):
                if name == pending.name:
                    raise OSError("pair")
                return unlink(name, *args, **kwargs)
            with patch.object(os, "unlink", side_effect=stop_pair):
                with self.assertRaises(OSError):
                    self.finish_final(value, final, pending)
        publish = host._publish
        interrupted = pending.with_name(host.PENDING + "c" * 32)
        def stop_publish(fd, name, data):
            selected = name == host.HOST_FINAL if stage == "intent" else name.startswith(
                host.HISTORY + "host-final-" + ("approval-" if stage == "approval" else "recovery-"))
            if selected:
                interrupted.write_bytes(data[:len(data) // 2])
                interrupted.chmod(0o400)
                raise OSError("partial final " + stage)
            return publish(fd, name, data)
        with patch.object(host, "_publish", side_effect=stop_publish):
            with self.assertRaises(OSError):
                self.finish_final(value, final, pending)
        self.assertTrue(interrupted.exists())
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        for entry in (self.final_plan, self.finish_final, self.terminal_plan, self.publication_plan):
            with self.subTest(stage=stage, entry=entry.__name__):
                with self.assertRaises(IntegrationError):
                    entry(value, final, pending)
        for name in (host.HOST_FINAL, host.HISTORY + "host-final-approval-" + "0" * 64 + ".json",
                     host.HISTORY + "host-final-recovery-" + "0" * 64 + ".json"):
            for predicate in (lifecycle._host_record_target, lifecycle._terminal_target, lifecycle._final_target):
                self.assertFalse(predicate(name))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def test_final_partial_intent_publication_is_terminal(self):
        self.check_final_partial_publication("intent")

    def test_final_partial_reapproval_publication_is_terminal(self):
        self.check_final_partial_publication("approval")

    def test_final_partial_receipt_publication_is_terminal(self):
        self.check_final_partial_publication("receipt")

    def test_terminal_publication_receipt(self):
        self.check_terminal("host-publication", "receipt")

    def test_terminal_publication_reapproval(self):
        self.check_terminal("host-publication", "approval")

    def test_terminal_alias_intent(self):
        self.check_terminal("host-alias", "intent")

    def test_terminal_alias_receipt(self):
        self.check_terminal("host-alias", "receipt")

    def test_terminal_alias_reapproval(self):
        self.check_terminal("host-alias", "approval")

    def test_terminal_pair_and_receipt_reentry(self):
        value, final, pending, _, _ = self.terminal_fixture("host-publication", "intent")
        unlink = os.unlink
        def stop(name, *args, **kwargs):
            if name == pending.name:
                raise OSError("terminal pair")
            return unlink(name, *args, **kwargs)
        with patch.object(os, "unlink", side_effect=stop):
            with self.assertRaises(OSError):
                self.finish_terminal(value, final, pending)
        self.assertEqual(final.stat().st_ino, pending.stat().st_ino)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        archive = lifecycle._archive
        def stop_receipt(fd, common, name, raw):
            if name.startswith(host.HISTORY + "host-terminal-recovery-"):
                raise OSError("terminal receipt")
            return archive(fd, common, name, raw)
        with patch.object(lifecycle, "_archive", side_effect=stop_receipt):
            with self.assertRaises(OSError):
                self.finish_terminal(value, final, pending)
        self.assertFalse(pending.exists())
        self.finish_terminal(value, final, pending)

    def test_terminal_partial_self_and_extra_pending_denied(self):
        value, final, pending, _, _ = self.terminal_fixture("host-alias", "receipt")
        raw = pending.read_bytes()
        pending.chmod(0o600)
        pending.write_bytes(raw[:-1])
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.terminal_plan(value, final, pending)
        pending.chmod(0o600)
        pending.write_bytes(raw)
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.terminal_plan(value, final.with_name(host.HOST_TERMINAL), pending)
        (pending.parent / (host.PENDING + "f" * 32)).write_bytes(b"unknown")
        with self.assertRaises(IntegrationError):
            self.terminal_plan(value, final, pending)

    def test_terminal_approval_failure_no_changes(self):
        value, final, pending, _, _ = self.terminal_fixture("host-publication", "intent")
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        with patch.object(host, "_publish", side_effect=OSError("terminal approval")):
            with self.assertRaises(OSError):
                self.finish_terminal(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def test_terminal_stale_owner_and_owner_lock(self):
        value, final, pending, _, _ = self.terminal_fixture("host-publication", "intent")
        plan = self.terminal_plan(value, final, pending)
        with self.assertRaises(IntegrationError):
            lifecycle.finish_host_terminal(self.repo, value["record"], pending.name, final.name,
                plan["plan_sha256"], git=self.git_binary)
        with self.assertRaises(IntegrationError):
            lifecycle.finish_host_terminal(self.repo, value["record"], pending.name, final.name,
                "0" * 64, git=self.git_binary, approve_local_owner=True)
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(IntegrationError):
                self.terminal_plan(value, final, pending)
        finally:
            os.close(fd)

    def test_terminal_independent_copy_denied(self):
        value, final, pending, _, _ = self.terminal_fixture("host-alias", "receipt")
        final.write_bytes(pending.read_bytes())
        final.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.terminal_plan(value, final, pending)

    def test_terminal_original_state_regression_denied(self):
        value, final, pending, target, original_pending = self.terminal_fixture("host-publication", "approval")
        target.rename(original_pending)
        with self.assertRaises(IntegrationError):
            self.terminal_plan(value, final, pending)

    def test_terminal_own_partial_approval_stays_blocked(self):
        value, final, pending, _, _ = self.terminal_fixture("host-publication", "intent")
        marker = self.repo / ".git" / host.HOST_TERMINAL
        marker.write_bytes(b'{"schema":')
        marker.chmod(0o400)
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        with self.assertRaises(IntegrationError):
            self.terminal_plan(value, final, pending)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def preservation_publication_fixture(self, family, record_kind):
        if family == "damage":
            value, _, _, _, _ = self.damage_fixture()
            finish = self.finish_damage
            marker = host.DAMAGE_RECOVERY
        else:
            value, _, _, _, _ = self.fragment_fixture()
            finish = self.finish_fragment
            marker = host.FRAGMENT_RECOVERY
        if record_kind == "intent":
            original = lifecycle._alias_native
            def fail_native(*args, **kwargs):
                if len(args) > 4:
                    raise OSError("native not started")
                return original(*args, **kwargs)
            with patch.object(lifecycle, "_alias_native", side_effect=fail_native):
                with self.assertRaises(OSError):
                    finish(value)
            final = self.repo / ".git" / marker
        elif record_kind == "receipt":
            finish(value)
            final = next((self.repo / ".git").glob(host.HISTORY + family + "-recovery-*.json"))
        else:
            with patch.object(lifecycle, "_archive", side_effect=OSError("receipt")):
                with self.assertRaises(OSError):
                    finish(value)
            archive = lifecycle._archive
            def fail_receipt(fd, common, name, data):
                if name.startswith(host.HISTORY + family + "-recovery-"):
                    raise OSError("receipt again")
                return archive(fd, common, name, data)
            with patch.object(lifecycle, "_archive", side_effect=fail_receipt):
                with self.assertRaises(OSError):
                    finish(value)
            final = next((self.repo / ".git").glob(host.HISTORY + family + "-approval-*.json"))
        pending = final.with_name(host.PENDING + "d" * 32)
        final.rename(pending)
        return value, final, pending

    def check_preservation_publication(self, family, kind):
        value, final, pending = self.preservation_publication_fixture(family, kind)
        native = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        raw = pending.read_bytes()
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        self.publication_plan(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        with patch.object(lifecycle, "_alias_native", side_effect=AssertionError("native invocation")):
            self.finish_publication(value, final, pending)
            self.assertEqual(final.read_bytes(), raw)
            os.link(final, pending)
            self.finish_publication(value, final, pending)
        self.assertFalse(pending.exists())
        self.assertEqual(native, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})

    def test_fragment_intent_publication(self):
        self.check_preservation_publication("fragment", "intent")

    def test_fragment_receipt_publication(self):
        self.check_preservation_publication("fragment", "receipt")

    def test_fragment_reapproval_publication(self):
        self.check_preservation_publication("fragment", "approval")

    def test_damage_intent_publication(self):
        self.check_preservation_publication("damage", "intent")

    def test_damage_receipt_publication(self):
        self.check_preservation_publication("damage", "receipt")

    def test_damage_reapproval_publication(self):
        self.check_preservation_publication("damage", "approval")

    def test_preservation_publication_receipt_reentry(self):
        value, final, pending = self.preservation_publication_fixture("damage", "receipt")
        before = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        with patch.object(lifecycle, "_archive", side_effect=OSError("host receipt")):
            with self.assertRaises(OSError):
                self.finish_publication(value, final, pending)
        self.assertTrue(final.exists())
        self.assertFalse(pending.exists())
        self.finish_publication(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})

    def test_preservation_publication_partial_and_forged_receipt_denied(self):
        value, final, pending = self.preservation_publication_fixture("fragment", "receipt")
        raw = pending.read_bytes()
        pending.chmod(0o600)
        pending.write_bytes(raw[:-1])
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        changed = host.decode(raw)
        changed["after"]["usage"][0][2] += 1
        pending.chmod(0o600)
        pending.write_bytes(host.encoded(changed))
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        self.assertFalse(final.exists())

    def test_preservation_publication_dependency_change_denied(self):
        value, final, pending = self.preservation_publication_fixture("damage", "intent")
        link = os.link
        def interrupt(source, destination, *args, **kwargs):
            if destination == final.name:
                raise OSError("before target link")
            return link(source, destination, *args, **kwargs)
        with patch.object(os, "link", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.finish_publication(value, final, pending)
        self.assertTrue((self.repo / ".git" / host.HOST_PUBLICATION).exists())
        self.assertFalse(final.exists())
        parent = self.repo / ".git" / host.FRAGMENT_RECOVERY
        raw = host.decode(parent.read_bytes())
        raw["plan"]["current"]["truncated_inode"] += 1
        raw["plan_sha256"] = host.sha(host.encoded(raw["plan"]))
        parent.chmod(0o600)
        parent.write_bytes(host.encoded(raw))
        parent.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)

    def test_preservation_publication_self_recovery_denied(self):
        value, final, pending = self.preservation_publication_fixture("fragment", "intent")
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final.with_name(host.HOST_PUBLICATION), pending)

    def test_preservation_alias_api(self):
        value, final, pending = self.preservation_publication_fixture("damage", "intent")
        os.link(pending, final)
        native = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        plan = lifecycle.host_alias_recovery_plan(self.repo, value["record"], final.name, git=self.git_binary)
        lifecycle.recover_host_alias(self.repo, value["record"], final.name, plan["plan_sha256"],
            git=self.git_binary, approve_local_owner=True)
        self.assertTrue(final.exists())
        self.assertFalse(pending.exists())
        self.assertEqual(native, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})

    def test_preservation_publication_pair_interrupt_reentry(self):
        value, final, pending = self.preservation_publication_fixture("fragment", "intent")
        native = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        unlink = os.unlink
        def interrupt(name, *args, **kwargs):
            if name == pending.name:
                raise OSError("after final link")
            return unlink(name, *args, **kwargs)
        with patch.object(os, "unlink", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.finish_publication(value, final, pending)
        self.assertEqual(final.stat().st_ino, pending.stat().st_ino)
        self.finish_publication(value, final, pending)
        self.assertFalse(pending.exists())
        self.assertEqual(native, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})

    def test_preservation_reapproval_changed_identity_denied(self):
        value, final, pending = self.preservation_publication_fixture("damage", "approval")
        value_bytes = host.decode(pending.read_bytes())
        value_bytes["plan"]["current"]["truncated_inode"] += 1
        value_bytes["plan_sha256"] = host.sha(host.encoded(value_bytes["plan"]))
        final = final.with_name(host.HISTORY + "damage-approval-" + value_bytes["plan_sha256"] + ".json")
        pending.chmod(0o600)
        pending.write_bytes(host.encoded(value_bytes))
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)

    def test_preservation_publication_independent_copy_denied(self):
        value, final, pending = self.preservation_publication_fixture("damage", "receipt")
        final.write_bytes(pending.read_bytes())
        final.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        self.assertTrue(final.exists() and pending.exists())

    def test_preservation_publication_approval_failure_no_changes(self):
        value, final, pending = self.preservation_publication_fixture("fragment", "intent")
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        with patch.object(host, "_publish", side_effect=OSError("host approval")):
            with self.assertRaises(OSError):
                self.finish_publication(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def finish_publication(self, value, final, pending):
        plan = self.publication_plan(value, final, pending)
        return lifecycle.finish_host_publication(self.repo, value["record"], pending.name, final.name,
            plan["plan_sha256"], git=self.git_binary, approve_local_owner=True)

    def test_host_publication_preserves_bytes_and_native(self):
        value, final, pending = self.publication_fixture()
        raw, inode = pending.read_bytes(), pending.stat().st_ino
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        native = {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()}
        self.publication_plan(value, final, pending)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})
        with patch.object(lifecycle, "_alias_native", side_effect=AssertionError("no native")):
            self.finish_publication(value, final, pending)
        self.assertFalse(pending.exists())
        self.assertEqual((final.read_bytes(), final.stat().st_ino), (raw, inode))
        self.assertEqual(native, {str(p): p.read_bytes() for p in self.authority.rglob("*") if p.is_file()})
        self.assertFalse((self.repo / ".git" / host.LOCATOR).exists())
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)

    def test_host_publication_receipt(self):
        value, final, pending = self.publication_fixture(receipt=True)
        raw = pending.read_bytes()
        self.finish_publication(value, final, pending)
        self.assertEqual(final.read_bytes(), raw)

    def test_host_publication_pair_reentry(self):
        value, final, pending = self.publication_fixture()
        original = os.unlink
        def interrupted(name, *args, **kwargs):
            if name == pending.name:
                raise OSError("fixture before unlink")
            return original(name, *args, **kwargs)
        with patch.object(os, "unlink", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.finish_publication(value, final, pending)
        self.assertEqual(final.stat().st_ino, pending.stat().st_ino)
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)
        self.finish_publication(value, final, pending)
        self.assertFalse(pending.exists())

    def test_host_publication_final_reentry(self):
        value, final, pending = self.publication_fixture()
        with patch.object(lifecycle, "_archive", side_effect=OSError("receipt interrupted")):
            with self.assertRaises(OSError):
                self.finish_publication(value, final, pending)
        self.assertFalse(pending.exists())
        self.assertTrue(final.exists())
        self.finish_publication(value, final, pending)
        self.assertFalse((self.repo / ".git" / host.HOST_PUBLICATION).exists())

    def test_host_publication_approval_failure(self):
        value, final, pending = self.publication_fixture()
        with patch.object(host, "_publish", side_effect=OSError("approval interrupted")):
            with self.assertRaises(OSError):
                self.finish_publication(value, final, pending)
        self.assertFalse(final.exists())
        self.assertTrue(pending.exists())

    def test_host_publication_binding_and_ambiguity(self):
        value, final, pending = self.publication_fixture()
        extra = pending.with_name(host.PENDING + "c" * 32)
        extra.write_bytes(b"unrelated")
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        extra.unlink()
        final.write_bytes(pending.read_bytes())
        final.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        final.unlink()
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final.with_name(host.HOST_PUBLICATION), pending)
        pending.chmod(0o600)
        pending.write_bytes(b'{"schema":')
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)

    def test_host_publication_approval_stale_and_owner(self):
        value, final, pending = self.publication_fixture()
        plan = self.publication_plan(value, final, pending)
        with self.assertRaisesRegex(IntegrationError, "OWNER_APPROVAL_REQUIRED"):
            lifecycle.finish_host_publication(self.repo, value["record"], pending.name, final.name,
                plan["plan_sha256"], git=self.git_binary)
        with self.assertRaisesRegex(IntegrationError, "PLAN_STALE"):
            lifecycle.finish_host_publication(self.repo, value["record"], pending.name, final.name,
                "0" * 64, git=self.git_binary, approve_local_owner=True)
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(IntegrationError, "AUTHORITY_OWNER_BUSY"):
                self.publication_plan(value, final, pending)
        finally:
            os.close(fd)

    def test_host_publication_pending_reentry(self):
        value, final, pending = self.publication_fixture()
        original = os.link
        def interrupted(source, destination, *args, **kwargs):
            if destination == final.name:
                raise OSError("fixture before final link")
            return original(source, destination, *args, **kwargs)
        with patch.object(os, "link", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.finish_publication(value, final, pending)
        self.assertFalse(final.exists())
        self.assertTrue(pending.exists())
        self.finish_publication(value, final, pending)
        self.assertTrue(final.exists())
        self.assertFalse(pending.exists())

    def test_host_publication_partial_approval_blocks_without_mutation(self):
        value, final, pending = self.publication_fixture()
        marker = self.repo / ".git" / host.HOST_PUBLICATION
        marker.write_bytes(b'{"schema":')
        marker.chmod(0o400)
        before = pending.read_bytes()
        with self.assertRaises(IntegrationError):
            self.finish_publication(value, final, pending)
        self.assertEqual(pending.read_bytes(), before)
        self.assertFalse(final.exists())
        self.assertEqual(marker.read_bytes(), b'{"schema":')

    def test_host_publication_symlink_and_extra_link(self):
        value, final, pending = self.publication_fixture()
        extra = self.base / "extra-link"
        os.link(pending, extra)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        pending.unlink()
        pending.symlink_to(extra)
        with self.assertRaises(IntegrationError):
            self.publication_plan(value, final, pending)
        self.assertTrue(extra.exists())

    def test_envelope_existing_pair_releases_only_pending_name(self):
        value, source, final, pending, _ = self.envelope_fixture(both=True)
        plan = self.envelope_plan(value)
        inode = final.stat().st_ino
        result = self.finish_envelope_fixture(value)
        before, after = plan["plan"]["current"], result["after"]
        self.assertEqual(final.stat().st_ino, inode)
        self.assertFalse(pending.exists())
        self.assertTrue(source.exists())
        self.assertEqual(after["usage"][0][2], before["usage"][0][2] - before["envelope_bytes"])
        self.assertEqual(after["usage"][0][3], before["usage"][0][3] - 1)
        self.assertEqual(after["usage"][0][:2], before["usage"][0][:2])
        self.assertEqual(after["usage"][1:], before["usage"][1:])

    def test_envelope_rejects_partial_duplicate_and_extra_link(self):
        value, _, final, pending, _ = self.envelope_fixture()
        complete = pending.read_bytes()
        pending.chmod(0o600)
        pending.write_bytes(complete[:-1])
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)
        pending.chmod(0o600)
        pending.write_bytes(complete)
        pending.chmod(0o400)
        final.write_bytes(complete)
        final.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)
        final.unlink()
        os.link(pending, self.base / "external-envelope")
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)

    def test_envelope_original_intent_and_source_required(self):
        value, source, _, _, _ = self.envelope_fixture()
        path = self.repo / ".git" / host.PARTIAL_RECOVERY
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)
        path.write_bytes(original)
        path.chmod(0o400)
        source.unlink()
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)

    def test_envelope_owner_stale_and_approval_publication_failure(self):
        value, _, final, pending, _ = self.envelope_fixture()
        plan = self.envelope_plan(value)
        options = dict(git=self.git_binary, bridge=Path(os.environ["GOLEM_INTENT_HOST"]).resolve())
        with self.assertRaises(IntegrationError):
            lifecycle.finish_envelope(self.repo, value["record"], 1, plan["plan_sha256"], **options)
        with self.assertRaises(IntegrationError):
            lifecycle.finish_envelope(self.repo, value["record"], 1, "0" * 64, approve_local_owner=True, **options)
        with patch.object(host, "_publish", side_effect=OSError("fixture approval failure")):
            with self.assertRaises(OSError):
                self.finish_envelope_fixture(value)
        self.assertFalse(final.exists())
        self.assertTrue(pending.exists())

    def test_envelope_receipt_failure_only_finalizes_history(self):
        value, source, final, pending, _ = self.envelope_fixture()
        original = lifecycle._archive
        def fail(fd, common, name, data):
            if name.startswith(host.HISTORY + "envelope-recovery-"):
                raise OSError("fixture receipt failure")
            return original(fd, common, name, data)
        with patch.object(lifecycle, "_archive", side_effect=fail):
            with self.assertRaises(OSError):
                self.finish_envelope_fixture(value)
        self.assertFalse(pending.exists())
        self.assertTrue(source.exists())
        inode = final.stat().st_ino
        with self.assertRaises(IntegrationError):
            self.partial_plan(value)
        self.finish_envelope_fixture(value)
        self.assertEqual(final.stat().st_ino, inode)
        self.assertTrue((self.repo / ".git" / host.PARTIAL_RECOVERY).exists())
        self.assertFalse((self.repo / ".git" / host.ENVELOPE_RECOVERY).exists())

    def test_envelope_change_chain_preserves_locator(self):
        value, source, final, _, previous = self.envelope_fixture(kind=2, change=True)
        common = self.repo / ".git"
        before = {name: (common / name).read_bytes() for name in (host.LOCATOR, host.CHANGE, host.PARTIAL_RECOVERY)}
        self.finish_envelope_fixture(value, kind=2, previous=previous)
        self.assertTrue(final.exists() and source.exists())
        self.assertFalse((self.authority / "00000002.event").exists())
        self.assertEqual(before, {name: (common / name).read_bytes() for name in before})

    def test_envelope_prep_owner_lock_and_host_pending(self):
        value, source, final, _, _ = self.envelope_fixture(kind=0)
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(IntegrationError):
                self.envelope_plan(value, kind=0)
        finally:
            os.close(fd)
        pending = self.repo / ".git" / (host.PENDING + "unknown")
        pending.write_bytes(b"{")
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value, kind=0)
        pending.unlink()
        self.finish_envelope_fixture(value, kind=0)
        self.assertTrue(source.exists() and final.exists())

    def test_envelope_unapproved_digest_and_changed_source_rejected(self):
        value, source, _, pending, _ = self.envelope_fixture()
        original = pending.read_bytes()
        changed = bytearray(original)
        changed[192:224] = bytes(32)
        changed[288:320] = bytes(32)
        changed[288:320] = bytes.fromhex(host.sha(bytes(changed)))
        pending.chmod(0o600)
        pending.write_bytes(changed)
        pending.chmod(0o400)
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)
        pending.chmod(0o600)
        pending.write_bytes(original)
        pending.chmod(0o400)
        source.write_bytes(b"changed")
        with self.assertRaises(IntegrationError):
            self.envelope_plan(value)

    def test_alias_event_preserves_final_and_releases_only_alias_usage(self):
        value, final, pending = self.alias_fixture()
        original = {p.name: p.read_bytes() for p in self.authority.iterdir() if p != pending}
        result = self.finish_alias_fixture(value)
        before, after = result["intent"]["plan"]["before"], result["after"]
        self.assertFalse(pending.exists())
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.authority.iterdir()})
        self.assertEqual(after["usage"][0][:2], before["usage"][0][:2])
        self.assertEqual(after["usage"][0][2], before["usage"][0][2] - final.stat().st_size)
        self.assertEqual(after["usage"][0][3], before["usage"][0][3] - 1)
        self.assertEqual(after["usage"][1:], before["usage"][1:])
        self.assertEqual(after["head"], before["head"])

    def test_alias_prepared_payload_does_not_publish_event(self):
        value, _, pending = self.alias_fixture(kind=1, prepared=True)
        self.finish_alias_fixture(value, kind=1)
        self.assertFalse(pending.exists())
        self.assertFalse((self.authority / "00000001.event").exists())

    def test_alias_independent_copy_is_rejected(self):
        value, final, pending = self.alias_fixture()
        pending.unlink()
        pending.write_bytes(final.read_bytes())
        pending.chmod(0o600)
        with self.assertRaisesRegex(IntegrationError, "NATIVE_ALIAS_NOT_RECOVERABLE"):
            self.finish_alias_fixture(value)

    def test_alias_external_third_link_is_rejected(self):
        value, final, _ = self.alias_fixture()
        os.link(final, self.base / "external")
        with self.assertRaisesRegex(IntegrationError, "NATIVE_ALIAS_NOT_RECOVERABLE"):
            self.finish_alias_fixture(value)

    def test_alias_approval_publication_failure_preserves_alias(self):
        value, _, pending = self.alias_fixture()
        with patch.object(host.os, "link", side_effect=OSError("approval publication")):
            with self.assertRaises(OSError):
                self.finish_alias_fixture(value)
        self.assertTrue(pending.exists())

    def test_alias_history_failure_can_be_explicitly_finalized(self):
        value, final, pending = self.alias_fixture()
        archive = lifecycle._archive
        def fail_receipt(fd, common, name, data):
            if name.startswith(host.HISTORY + "alias-recovery-"):
                raise OSError("receipt boundary")
            return archive(fd, common, name, data)
        with patch.object(lifecycle, "_archive", side_effect=fail_receipt):
            with self.assertRaises(OSError):
                self.finish_alias_fixture(value)
        self.assertFalse(pending.exists())
        self.assertTrue(final.exists())
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        with self.assertRaisesRegex(IntegrationError, "LOCATOR_COMMIT_UNKNOWN"):
            self.enroll()
        result = self.finish_alias_fixture(value)
        self.assertFalse(result["after"]["present"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})

    def test_alias_requires_owner_and_exact_plan(self):
        value, _, pending = self.alias_fixture()
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        with self.assertRaisesRegex(IntegrationError, "OWNER_APPROVAL_REQUIRED"):
            lifecycle.recover_alias(self.repo, value["record"], 2, "0" * 64, git=self.git_binary, bridge=bridge)
        with self.assertRaisesRegex(IntegrationError, "PLAN_STALE"):
            lifecycle.recover_alias(self.repo, value["record"], 2, "0" * 64,
                                    git=self.git_binary, bridge=bridge, approve_local_owner=True)
        self.assertTrue(pending.exists())

    def test_alias_change_chain_binding(self):
        old = self.enroll()
        self.pin.write_bytes(b"second")
        new = self.change_fixture(old)
        os.link(self.authority / "00000002.event", self.authority / "00000002.event.pending")
        self.finish_alias_fixture(new, previous=old["registration_sha256"])
        self.assertFalse((self.authority / "00000002.event.pending").exists())

    def test_alias_prep_without_payload_leaves_incomplete_state(self):
        value, _, pending = self.alias_fixture(kind=0, prepared=True)
        (self.authority / "00000001.payload").unlink()
        self.finish_alias_fixture(value, kind=0)
        self.assertFalse(pending.exists())
        self.assertEqual({p.name for p in self.authority.iterdir()}, {"00000001.prep"})

    def test_alias_rejects_mixed_partial_staging(self):
        value, _, pending = self.alias_fixture()
        (self.authority / "00000001.payload.pending").write_bytes(b"partial")
        with self.assertRaisesRegex(IntegrationError, "NATIVE_ALIAS_NOT_RECOVERABLE"):
            self.finish_alias_fixture(value)
        self.assertTrue(pending.exists())

    def test_alias_owner_conflict_and_revocation(self):
        value, _, pending = self.alias_fixture()
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(IntegrationError, "NATIVE_ALIAS_NOT_RECOVERABLE"):
                self.finish_alias_fixture(value)
        finally:
            os.close(fd)
        (self.repo / ".git" / host.TOMBSTONE).write_bytes(b"revoked")
        with self.assertRaisesRegex(IntegrationError, "AUTHORITY_REVOKED"):
            self.finish_alias_fixture(value)
        self.assertTrue(pending.exists())

    @unittest.skipUnless(os.environ.get("GOLEM_INTENT_HOST"), "native bridge path required")
    def test_native_bridge_and_owner_lock(self):
        bridge = Path(os.environ["GOLEM_INTENT_HOST"]).resolve()
        value = self.enroll([self.pin, bridge])
        before = {p.name: p.read_bytes() for p in self.authority.iterdir()}
        observed = host.native_inspect(self.repo, value["registration_sha256"],
                                       git=self.git_binary, bridge=bridge)
        self.assertEqual(observed["committed"], 1)
        self.assertEqual(observed["usage"][0][0], 1)
        self.assertEqual(observed["usage"][1:], [[0] * 4] * 2)
        self.assertFalse(observed["execution_authorized"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.authority.iterdir()})
        fd = os.open(self.authority, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(IntegrationError, "NATIVE_INSPECTION_BLOCKED"):
                host.native_inspect(self.repo, value["registration_sha256"], git=self.git_binary, bridge=bridge)
        finally:
            os.close(fd)
        self.assertEqual(len(list(self.authority.iterdir())), 3)


if __name__ == "__main__":
    unittest.main()
