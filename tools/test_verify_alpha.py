"""Source selection must exclude private and generated assets."""
import tempfile
from pathlib import Path
import subprocess
import unittest
from verify_alpha import selected, snapshot, audit_install


class SourceSnapshotTests(unittest.TestCase):
    def test_scope(self):
        for name in ("src/core/work_run.c", "include/golem/core.h", "CMakeLists.txt"):
            self.assertTrue(selected(name))
        for name in (".git/config", ".env", "project-docs/plan.md", ".golem/journal.bin", "build/cache", "README.md"):
            self.assertFalse(selected(name))
        for name in ("../src/secret", "/src/core.c"):
            with self.assertRaises(ValueError):
                selected(name)

    def test_nested_private_assets_and_supported_fixtures(self):
        for name in ("samples/.golem/objects/sha256/ab/data.json", "src/project-docs/private.md",
                     "tests/credentials/account.json", "samples/run.log", "include/private.key",
                     "samples/reports/run.md", "tests/build/result.c", "samples/SECRETS/value.json",
                     "samples/.env", "src/.private/code.c"):
            self.assertFalse(selected(name), name)
        for name in ("tests/c/fixtures/journal/v1_default.hex", "tests/c/CMakeLists.txt",
                     "samples/documents/planning.md", "cmake/GolemConfig.cmake.in", "src/golem/core.py",
                     "fuzz/corpus/adapter_json/request.json"):
            self.assertTrue(selected(name), name)

    def test_public_fuzz_corpus_is_retained(self):
        root = Path(__file__).resolve().parents[1]
        corpus = sorted((root / "fuzz/corpus").rglob("*.json"))
        self.assertGreaterEqual(len(corpus), 3)
        for path in corpus:
            self.assertTrue(selected(path.relative_to(root).as_posix()), str(path))

    def test_historical_fixture_is_copied_verbatim(self):
        root = Path(__file__).resolve().parents[1]
        name = "tests/c/fixtures/completion/v1-store.json"
        self.assertTrue(selected(name))
        self.assertFalse(selected("tests/c/fixtures/completion/local-store.json"))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve()
            snapshot(root, output)
            self.assertEqual((output / name).read_bytes(), (root / name).read_bytes())

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
            (root / "src/reports").mkdir()
            (root / "src/reports/private.py").write_text("synthetic private asset")
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

    def test_installed_inventory_is_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ("bin/golem", "include/golem/completion.h", "lib/libgolem.a",
                     "share/licenses/Golem/LICENSE", "share/licenses/Golem/NOTICE")
            for name in names:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("synthetic public artifact")
            audit_install(root)
            extra = root / "private-report.md"
            extra.write_text("synthetic private report")
            with self.assertRaises(ValueError):
                audit_install(root)
            extra.unlink()
            (root / "include/golem/secret.h").symlink_to(root / "share/licenses/Golem/LICENSE")
            with self.assertRaises(ValueError):
                audit_install(root)


if __name__ == "__main__":
    unittest.main()
