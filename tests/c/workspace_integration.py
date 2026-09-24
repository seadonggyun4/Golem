"""Real Git effects are confined to disposable fixtures, never the source repo."""
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI, HELPER, SOURCE = (Path(sys.argv.pop(1)).resolve() for _ in range(3))
ENV = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "WS_"))}


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="golem-workspace-")
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.trees = self.root / "trees"
        self.trees.mkdir()
        self.work = self.root / "work"
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "tracked").write_text("original\n")
        (self.repo / ".gitignore").write_text("ignored\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.base = self.git("rev-parse", "HEAD").stdout.decode().strip()
        p = subprocess.run([str(CLI), "work", "start", str(self.work),
                            str(SOURCE / "samples/documents/work.json")],
                           capture_output=True, env=ENV, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        self.path = self.trees / "example-work" / "candidate"

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args, cwd=None):
        return subprocess.run(["/usr/bin/git", "-C", str(cwd or self.repo), *args],
                              check=True, capture_output=True, env=ENV, timeout=30)

    def call(self, operation, candidate="candidate", base=None, evidence="-", root=None,
             env=None, ok=True):
        p = subprocess.run([str(HELPER), str(self.work), str(self.repo), str(root or self.trees),
                            candidate, str(operation), base or self.base, evidence],
                           capture_output=True, env={**ENV, **(env or {})}, timeout=90)
        if not ok:
            self.assertNotEqual(p.returncode, 0, p.stdout)
            return p
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        state, path, receipt = p.stdout.decode().splitlines()
        return int(state), Path(path), receipt

    def retained(self):
        ready = self.call(1)
        self.call(3)
        self.call(4)
        self.call(5, evidence=ready[2])
        return ready

    def test_lifecycle_and_receipts_survive_removal(self):
        ready = self.retained()
        self.assertEqual(ready[0], 2)
        self.assertEqual((self.path / "tracked").read_text(), "original\n")
        self.assertEqual(self.call(2)[0], 5)
        self.assertEqual(self.call(6)[0], 7)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.call(2)[0], 7)
        self.assertEqual(len(list((self.work / "workspaces/candidate").iterdir())), 7)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.decode().strip(), self.base)

    def test_special_files_and_empty_directories_are_preserved(self):
        self.retained()
        fifo = self.path / "user-fifo"
        os.mkfifo(fifo)
        self.call(6, ok=False)
        self.assertTrue(fifo.exists())
        self.assertEqual(self.call(2)[0], 5)
        fifo.unlink()
        empty = self.path / "user-empty"
        empty.mkdir()
        self.call(6, ok=False)
        self.assertTrue(empty.is_dir())
        empty.rmdir()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            # macOS Unix socket paths are limited to 104 bytes.
            old = os.getcwd()
            try:
                os.chdir(self.path)
                sock.bind("user.sock")
            finally:
                os.chdir(old)
            self.call(6, ok=False)
            self.assertTrue((self.path / "user.sock").exists())
            self.assertEqual(self.call(2)[0], 5)
        finally:
            sock.close()

    def test_tracked_directory_removal_and_nested_special_file(self):
        (self.repo / "dir").mkdir()
        (self.repo / "dir/tracked").write_text("preserved in Git\n")
        self.git("add", "dir")
        self.git("commit", "-qm", "tracked directory")
        self.base = self.git("rev-parse", "HEAD").stdout.decode().strip()
        self.retained()
        fifo = self.path / "dir/pipe"
        os.mkfifo(fifo)
        self.call(6, ok=False)
        self.assertTrue(fifo.exists())
        self.assertEqual(self.call(2)[0], 5)
        fifo.unlink()
        empty = self.path / "dir/empty"
        empty.mkdir()
        self.call(6, ok=False)
        self.assertTrue(empty.is_dir())
        empty.rmdir()
        self.assertEqual(self.call(6)[0], 7)
        self.assertFalse(self.path.exists())

    def test_dirty_main_is_not_copied_stashed_or_reset(self):
        (self.repo / "tracked").write_text("user change\n")
        (self.repo / "new").write_text("untracked\n")
        before = self.git("status", "--porcelain=v1", "-z").stdout
        self.call(1)
        self.assertEqual(self.git("status", "--porcelain=v1", "-z").stdout, before)
        self.assertEqual((self.path / "tracked").read_text(), "original\n")
        self.assertFalse((self.path / "new").exists())

    def test_dirty_untracked_ignored_and_new_commit_not_removed(self):
        self.retained()
        for name in ("tracked", "new", "ignored"):
            path = self.path / name
            previous = path.read_bytes() if path.exists() else None
            path.write_text("preserve me\n")
            self.call(6, ok=False)
            self.assertEqual(path.read_text(), "preserve me\n")
            if previous is None:
                path.unlink()
            else:
                path.write_bytes(previous)
        (self.path / "tracked").write_text("committed\n")
        self.git("add", "tracked", cwd=self.path)
        self.git("commit", "-qm", "candidate change", cwd=self.path)
        self.call(6, ok=False)
        self.assertTrue(self.path.exists())

    def test_policy_and_lifecycle_cannot_be_skipped(self):
        self.call(1, env={"WS_DENY": "1"}, ok=False)
        self.assertFalse(self.path.exists())
        self.call(1)
        self.call(6, ok=False)
        self.call(4, ok=False)
        self.call(3)
        self.call(6, ok=False)
        self.call(4)
        self.call(5, evidence="0" * 64, ok=False)
        self.assertTrue(self.path.exists())

    def test_filter_rejected_and_hooks_not_run(self):
        marker = self.root / "executed"
        hook = self.repo / ".git/hooks/post-checkout"
        hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
        hook.chmod(0o700)
        self.git("config", "filter.evil.smudge", f"touch '{marker}'")
        self.call(1, ok=False)
        self.assertFalse(marker.exists())
        self.git("config", "--remove-section", "filter.evil")
        self.call(1)
        self.assertFalse(marker.exists())

    def test_foreign_path_and_path_traversal_preserved(self):
        self.path.mkdir(parents=True)
        (self.path / "foreign").write_text("owned by user")
        self.call(1, ok=False)
        self.assertEqual((self.path / "foreign").read_text(), "owned by user")
        for candidate in ("../escape", "/absolute", ".", "a/b", "a.b"):
            self.call(1, candidate=candidate, ok=False)

    def test_symlink_root_and_changed_registration_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.trees, target_is_directory=True)
        self.call(1, root=alias, ok=False)
        self.call(1)
        other = self.root / "trees-other"
        other.mkdir()
        self.call(2, root=other, ok=False)
        self.call(1, candidate="second", root=other, ok=False)
        self.assertTrue(self.path.exists())

    def test_owner_marker_tampering_refused(self):
        self.retained()
        admin = Path(self.git("rev-parse", "--absolute-git-dir", cwd=self.path).stdout.decode().strip())
        marker = admin / "golem-owner"
        marker.chmod(0o600)
        marker.write_text("foreign")
        self.call(2, ok=False)
        self.call(6, ok=False)
        self.assertTrue(self.path.exists())

    def test_interrupted_add_never_adopted_or_reexecuted(self):
        # check #6 occurs after the successful Git add, before metadata query.
        p = self.call(1, env={"WS_CRASH_AT": "6"}, ok=False)
        self.assertEqual(p.returncode, 77)
        self.assertTrue(self.path.exists())
        before = self.git("worktree", "list", "--porcelain").stdout
        self.assertEqual(self.call(2)[0], 8)
        self.call(1, ok=False)
        self.call(6, ok=False)
        self.assertEqual(self.git("worktree", "list", "--porcelain").stdout, before)

    def test_missing_ledger_record_rejected(self):
        self.retained()
        (self.work / "workspaces/candidate/0003").unlink()
        self.call(2, ok=False)
        self.assertTrue(self.path.exists())

    def test_hidden_index_changes_not_removed(self):
        self.retained()
        self.git("update-index", "--assume-unchanged", "tracked", cwd=self.path)
        (self.path / "tracked").write_text("hidden user edit\n")
        self.call(6, ok=False)
        self.assertEqual((self.path / "tracked").read_text(), "hidden user edit\n")

    def test_crash_after_metadata_and_checkout_is_attention(self):
        for count in (7, 8, 9):
            candidate = f"crash-{count}"
            p = self.call(1, candidate=candidate, env={"WS_CRASH_AT": str(count)}, ok=False)
            self.assertEqual(p.returncode, 77)
            self.assertEqual(self.call(2, candidate=candidate)[0], 8)
            self.call(6, candidate=candidate, ok=False)
            self.assertTrue((self.path.parent / candidate).exists())

    def test_interrupted_cleanup_never_repeated(self):
        self.retained()
        p = self.call(6, env={"WS_CRASH_AT": "7"}, ok=False)
        self.assertEqual(p.returncode, 77)
        self.assertEqual(self.call(2)[0], 8)
        self.call(6, ok=False)
        self.assertTrue(self.path.exists())

    def test_cancellation_preserves_main(self):
        before = self.git("status", "--porcelain=v1", "-z").stdout
        self.call(1, env={"WS_EXPIRE": "1"}, ok=False)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.git("status", "--porcelain=v1", "-z").stdout, before)

    def test_symlink_work_parent_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.path.parent.symlink_to(outside, target_is_directory=True)
        self.call(1, ok=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_effective_include_filter_and_partial_clone_refused(self):
        extra = self.root / "extra.config"
        extra.write_text("[filter \"x\"]\n process = echo unsafe\n")
        self.git("config", "include.path", str(extra))
        self.call(1, ok=False)
        self.git("config", "--unset", "include.path")
        self.git("config", "remote.origin.promisor", "true")
        self.call(1, ok=False)
        self.assertFalse(self.path.exists())

    def test_replaced_root_identity_refused(self):
        self.call(1)
        original = self.root / "original-trees"
        self.trees.rename(original)
        self.trees.mkdir()
        self.call(2, ok=False)
        self.assertTrue((original / "example-work/candidate/tracked").exists())

    def test_changed_git_backlink_refused(self):
        self.retained()
        admin = Path(self.git("rev-parse", "--absolute-git-dir", cwd=self.path).stdout.decode().strip())
        (admin / "gitdir").write_text(str(self.repo / ".git") + "\n")
        self.call(2, ok=False)
        self.call(6, ok=False)
        self.assertTrue(self.path.exists())

    def test_git_metadata_is_not_a_candidate_root(self):
        self.call(1, root=self.repo / ".git", ok=False)
        self.assertFalse((self.repo / ".git/example-work").exists())

    def test_current_generation_and_duplicate_create_do_not_reexecute(self):
        ready = self.call(1)
        self.call(1, ok=False)
        self.assertEqual(self.call(2), ready)
        self.call(3)
        self.assertEqual(self.call(2)[0], 3)

    def test_attached_branch_not_silently_adopted(self):
        self.call(1)
        self.git("switch", "-c", "unexpected-branch", cwd=self.path)
        self.call(2, ok=False)
        self.assertTrue(self.path.exists())

    def test_large_and_unusual_untracked_inventory_fails_closed(self):
        self.retained()
        for i in range(500):
            (self.path / f"untracked-{i:04d}-long-filename-for-output-bound.txt").write_text("x")
        (self.path / "newline\nfilename").write_text("preserve")
        self.call(6, ok=False)
        self.assertEqual((self.path / "newline\nfilename").read_text(), "preserve")
        self.assertEqual(self.call(2)[0], 5)

    def test_git_admin_collision_suffix_is_not_candidate_identity(self):
        candidate = "a" * 64
        self.call(1, candidate=candidate)
        self.work = self.root / "second-work"
        spec = json.loads((SOURCE / "samples/documents/work.json").read_text())
        spec["work_id"] = "second-work"
        path = self.root / "second-spec.json"
        path.write_text(json.dumps(spec))
        p = subprocess.run([str(CLI), "work", "start", str(self.work), str(path)],
                           capture_output=True, env=ENV, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        ready = self.call(1, candidate=candidate)
        self.assertEqual(ready[0], 2)
        self.assertEqual(self.call(2, candidate=candidate), ready)


if __name__ == "__main__":
    unittest.main()
