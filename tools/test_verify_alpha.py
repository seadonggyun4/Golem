"""Source selection must exclude private and generated assets."""
import tempfile
from pathlib import Path
import subprocess
import unittest
from verify_alpha import selected, snapshot


class SourceSnapshotTests(unittest.TestCase):
    def test_scope(self):
        for name in ("src/core/work_run.c", "include/golem/core.h", "CMakeLists.txt"):
            self.assertTrue(selected(name))
        for name in (".git/config", ".env", "project-docs/plan.md", ".golem/journal.bin", "build/cache", "README.md"):
            self.assertFalse(selected(name))
        for name in ("../src/secret", "/src/core.c"):
            with self.assertRaises(ValueError):
                selected(name)

    def test_git_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "src").mkdir()
            (root / "src/core.c").write_text("core")
            (root / "src/tracked.key").write_text("synthetic tracked fixture")
            subprocess.run(["git", "add", "src/tracked.key"], cwd=root, check=True)
            (root / ".gitignore").write_text("*.key\n")
            (root / "src/private.key").write_text("synthetic excluded fixture")
            (root / "src/deleted.c").write_text("deleted")
            subprocess.run(["git", "add", "src/deleted.c"], cwd=root, check=True)
            (root / "src/deleted.c").unlink()
            output = root / "snapshot"
            output.mkdir()
            snapshot(root, output)
            self.assertEqual([p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()], ["src/core.c"])

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "src").mkdir()
            (root / "private").write_text("synthetic fixture")
            (root / "src/link.c").symlink_to(root / "private")
            output = root / "snapshot"
            output.mkdir()
            with self.assertRaises(ValueError):
                snapshot(root, output)


if __name__ == "__main__":
    unittest.main()
