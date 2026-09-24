"""Real Git fixtures for byte-preserving, conservative source inventories."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HELPER = sys.argv.pop(1)
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)


class Inventory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "a").write_text("original")
        (self.repo / "oracle").write_text("test")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.policy = {"schema_version": 1, "protected": [], "excluded": [],
                       "limit": {"mode": "BOUNDED", "max_changed_paths": 5}}

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", "-C", str(self.repo), *args],
                                       stderr=subprocess.PIPE, env=ENV)

    def run_helper(self, *args, ok=True):
        p = subprocess.run([HELPER, args[0], json.dumps(self.policy), *map(str, args[1:])],
                           capture_output=True, text=True, timeout=70, env=ENV)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)
        self.assertNotEqual(p.returncode, 0, p.stdout)

    def capture(self, ok=True):
        return self.run_helper("capture", self.repo, ok=ok)

    def compare(self, old, ok=True):
        current = self.capture()
        a, b = self.base / "before.json", self.base / "after.json"
        a.write_text(json.dumps(old))
        b.write_text(json.dumps(current))
        return self.run_helper("compare", a, b, ok=ok)

    def test_preexisting_staged_unstaged_untracked(self):
        (self.repo / "a").write_text("user edit")
        before = self.capture()
        self.assertEqual(self.compare(before)["preexisting_paths"], 1)
        self.assertEqual(self.compare(before)["changed_paths"], 0)
        self.git("add", "a")
        staged = self.compare(before)
        self.assertEqual(staged["changed_paths"], 1)
        self.assertTrue(staged["findings"][0]["staged"])
        self.assertFalse(staged["findings"][0]["unstaged"])
        (self.repo / "a").write_text("agent edit")
        (self.repo / "new").write_text("new")
        result = self.compare(before)
        self.assertEqual(result["changed_paths"], 2)
        a = next(f for f in result["findings"] if f["path_hex"] == b"a".hex())
        self.assertTrue(a["staged"] and a["unstaged"] and a["preexisting"])

    def test_rename_protected_deletion_and_limits(self):
        self.policy["protected"] = [{"kind": "EXACT", "pattern": "oracle"}]
        before = self.capture()
        self.git("mv", "oracle", "renamed")
        result = self.compare(before)
        self.assertEqual(result["changed_paths"], 2)
        self.assertEqual(result["protected_paths"], 1)
        self.assertFalse(result["allowed"])

    def test_binary_change_and_linked_worktree_preserve_main(self):
        original = self.repo
        (original / "a").write_bytes(b"user change\x00\xff")
        main_bytes = (original / "a").read_bytes()
        linked = self.base / "linked"
        self.git("worktree", "add", "--detach", str(linked), "HEAD")
        self.repo = linked
        before = self.capture()
        (linked / "binary").write_bytes(bytes(range(256)))
        result = self.compare(before)
        self.assertEqual(result["changed_paths"], 1)
        self.assertTrue(result["allowed"])
        self.assertEqual((original / "a").read_bytes(), main_bytes)

    def test_zero_n_and_n_plus_one(self):
        for maximum in (0, 1, 2):
            self.policy["limit"]["max_changed_paths"] = maximum
            before = self.capture()
            (self.repo / "a").write_text(str(maximum))
            (self.repo / "oracle").write_text(str(maximum))
            result = self.compare(before)
            self.assertEqual(result["changed_paths"], 2)
            self.assertEqual(result["allowed"], maximum == 2)

    def test_ignored_files_require_explicit_exclusion(self):
        (self.repo / ".gitignore").write_text("*.log\n")
        before = self.capture()
        (self.repo / "new.log").write_text("generated")
        self.assertEqual(self.compare(before)["changed_paths"], 1)
        self.policy["excluded"] = [{"kind": "SEGMENT_GLOB", "pattern": "*.log"}]
        before = self.capture()
        (self.repo / "new.log").write_text("changed")
        self.assertEqual(self.compare(before)["changed_paths"], 0)

    def test_protection_overrides_exclusion(self):
        self.policy["excluded"] = [{"kind": "SEGMENT_GLOB", "pattern": "**"}]
        self.policy["protected"] = [{"kind": "EXACT", "pattern": "oracle"}]
        before = self.capture()
        (self.repo / "oracle").unlink()
        self.assertFalse(self.compare(before)["allowed"])

    def test_large_excluded_subtree_is_pruned(self):
        self.policy["excluded"] = [{"kind": "DIR_PREFIX", "pattern": "vendor"}]
        vendor = self.repo / "vendor"
        vendor.mkdir()
        for i in range(4200):
            (vendor / f"dependency-{i}").write_text("excluded")
        self.git("add", "vendor")
        self.git("commit", "-qm", "large tracked dependency tree")
        self.assertGreater(len(self.git("ls-tree", "-r", "-z", "HEAD")), 16384)
        before = self.capture()
        (self.repo / "a").write_text("change")
        self.assertEqual(self.compare(before)["changed_paths"], 1)

    def test_included_capacity_and_protection(self):
        for i in range(1022):
            (self.repo / f"file-{i:04}").write_text("original")
        self.git("add", ".")
        self.git("commit", "-qm", "included capacity")
        self.policy["protected"] = [{"kind": "EXACT", "pattern": "file-1021"}]
        before = self.capture()
        self.assertEqual(len(before["entries"]), 1024)
        (self.repo / "file-1021").write_text("changed")
        result = self.compare(before)
        self.assertEqual(result["changed_paths"], 1)
        self.assertEqual(result["protected_paths"], 1)
        self.assertFalse(result["allowed"])
        (self.repo / "overflow").write_text("must not disappear")
        self.capture(ok=False)

    def test_directory_exclusion_cannot_hide_protected_descendants(self):
        vendor = self.repo / "vendor"
        vendor.mkdir()
        target = vendor / "oracle"
        target.write_text("original")
        self.policy["excluded"] = [{"kind": "DIR_PREFIX", "pattern": "vendor"}]
        for kind, pattern in (("EXACT", "vendor/oracle"),
                              ("DIR_PREFIX", "vendor"),
                              ("SEGMENT_GLOB", "**/oracle")):
            self.policy["protected"] = [{"kind": kind, "pattern": pattern}]
            before = self.capture()
            target.write_text(target.read_text() + "changed")
            result = self.compare(before)
            self.assertEqual(result["protected_paths"], 1)
            self.assertFalse(result["allowed"])

    def test_exact_directory_exclusion_does_not_exclude_children(self):
        (self.repo / "vendor").mkdir()
        self.policy["excluded"] = [{"kind": "EXACT", "pattern": "vendor"}]
        before = self.capture()
        (self.repo / "vendor/new").write_text("visible")
        self.assertEqual(self.compare(before)["changed_paths"], 1)

    def test_filename_bytes(self):
        before = self.capture()
        names = [b" white space ", b"new\nline", b"tab\tname", b"-dash"]
        if sys.platform != "darwin":
            names.append(b"invalid\xff")
        for name in names:
            with open(os.fsencode(self.repo) + b"/" + name, "wb") as f:
                f.write(b"x")
        result = self.compare(before)
        self.assertEqual({f["path_hex"] for f in result["findings"]}, {n.hex() for n in names})

    def test_invalid_utf8_index_identity(self):
        before = self.capture()
        oid = self.git("rev-parse", "HEAD:a").strip()
        subprocess.run(["git", "-C", str(self.repo), "update-index", "-z", "--index-info"],
                       input=b"100644 " + oid + b"\tinvalid\xff\0", check=True, env=ENV)
        self.assertEqual(self.compare(before)["findings"][0]["path_hex"], b"invalid\xff".hex())

    def test_symlink_no_follow_and_mode(self):
        outside = self.base / "outside"
        outside.write_text("secret")
        os.symlink(outside, self.repo / "link")
        before = self.capture()
        outside.write_text("changed secret")
        self.assertEqual(self.compare(before)["changed_paths"], 0)
        (self.repo / "a").chmod(0o755)
        self.assertEqual(self.compare(before)["changed_paths"], 1)

    def test_head_movement_denied(self):
        before = self.capture()
        self.git("commit", "--allow-empty", "-qm", "new head")
        self.assertFalse(self.compare(before)["allowed"])

    def test_unsupported_fifo(self):
        os.mkfifo(self.repo / "pipe")
        self.capture(ok=False)

    def test_case_collision(self):
        self.git("update-index", "--add", "--cacheinfo", "100644",
                 self.git("rev-parse", "HEAD:a").decode().strip(), "A")
        self.capture(ok=False)

    def test_directory_case_collision(self):
        oid = self.git("rev-parse", "HEAD:a").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", "100644", oid, "Dir/x")
        self.git("update-index", "--add", "--cacheinfo", "100644", oid, "dir/y")
        self.capture(ok=False)

    def test_submodule_incomplete(self):
        self.git("update-index", "--add", "--cacheinfo", "160000",
                 self.git("rev-parse", "HEAD").decode().strip(), "sub")
        self.capture(ok=False)

    def test_changed_policy_rejected(self):
        before = self.capture()
        self.policy["limit"] = {"mode": "UNLIMITED"}
        self.compare(before, ok=False)

    def test_subdirectory_is_not_repository_root(self):
        (self.repo / "child").mkdir()
        self.run_helper("capture", self.repo / "child", ok=False)

    def test_unmerged_index_is_incomplete(self):
        oid = self.git("rev-parse", "HEAD:a").strip()
        data = b"0 " + b"0" * 40 + b"\ta\0" + b"100644 " + oid + b" 1\ta\0"
        subprocess.run(["git", "-C", str(self.repo), "update-index", "-z", "--index-info"],
                       input=data, check=True, env=ENV)
        self.capture(ok=False)

    def test_unlimited_and_hex_protection(self):
        self.policy["limit"] = {"mode": "UNLIMITED"}
        self.policy["protected"] = [{"kind": "EXACT", "pattern_hex": b"a".hex()}]
        before = self.capture()
        (self.repo / "new").write_text("new")
        self.assertTrue(self.compare(before)["allowed"])
        (self.repo / "a").unlink()
        self.assertFalse(self.compare(before)["allowed"])

    def test_parent_symlink_is_not_followed(self):
        (self.repo / "dir").mkdir()
        (self.repo / "dir/file").write_text("old")
        self.git("add", "dir")
        (self.repo / "dir/file").unlink()
        (self.repo / "dir").rmdir()
        os.symlink(self.base, self.repo / "dir")
        self.capture(ok=False)

    def test_path_limit_is_not_silent_truncation(self):
        # Two tracked fixture paths plus 1023 untracked paths exceed the cap.
        for i in range(1023):
            (self.repo / f"f{i}").write_text("x")
        self.capture(ok=False)


if __name__ == "__main__":
    unittest.main()
