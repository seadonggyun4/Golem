"""Source selection must exclude private and generated assets."""
import tempfile
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import verify_alpha
from verify_alpha import selected, snapshot, audit_install
from source_policy import export_sources, FIXTURES


class SourceSnapshotTests(unittest.TestCase):
    def test_clean_suite_keeps_all_tests_with_bounded_parallelism(self):
        commands = []
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.argv", ["verify_alpha.py", "--source", tmp]), \
                 patch.object(verify_alpha, "snapshot"), \
                 patch.object(verify_alpha, "audit_install"), \
                 patch.object(verify_alpha.shutil, "which", return_value="/usr/bin/cc"), \
                 patch("builtins.print"), \
                 patch.object(verify_alpha, "run", side_effect=lambda args, cwd, env: commands.append(args)):
                verify_alpha.main()
        suite = next(args for args in commands if args[0] == "ctest" and "--parallel" in args)
        self.assertEqual(suite[suite.index("--parallel") + 1], "2")
        self.assertIn("--no-tests=error", suite)
        self.assertIn("--output-on-failure", suite)
        self.assertNotIn("-R", suite)

    def test_runtime_harness_dependencies_are_explicit(self):
        for name in ("verify_runtime.py", "test_verify_runtime.py", "verify_agent.py",
                     "benchmark_runtime.py"):
            self.assertTrue(selected("tools/" + name))
        self.assertFalse(selected("tools/local_report.py"))
        self.assertFalse(selected("tools/project-docs/plan.py"))

    def test_scope(self):
        for profile in ("validation", "conan"):
            self.assertTrue(selected("src/workspace/model.c", profile))
            self.assertTrue(selected("src/inventory/git_record.c", profile))
            self.assertTrue(selected("src/inventory/git_record.h", profile))
            self.assertFalse(selected("src/workspace/secrets/key.c", profile))
            self.assertFalse(selected("src/other/workspace/state.c", profile))
        for name in ("src/core/work_run.c", "include/golem/core.h", "CMakeLists.txt"):
            self.assertTrue(selected(name))
        for name in (".git/config", ".env", "project-docs/plan.md", ".golem/journal.bin", "build/cache", "README.md"):
            self.assertFalse(selected(name))
        for name in ("../src/secret", "/src/core.c"):
            with self.assertRaises(ValueError):
                selected(name)

    def test_only_reviewed_fixture_names_are_public(self):
        self.assertTrue(all(selected(name) for name in FIXTURES))
        for name in ("samples/local-report.json", "samples/private-plan.md",
                     "tests/c/fixtures/local.hex", "fuzz/corpus/local.json",
                     "src/worktrees/secret.c", "src/objects/leak.c"):
            self.assertFalse(selected(name), name)

    def test_conan_uses_same_nested_exclusions_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "source"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            for name in ("src/core/a.c", "src/.golem/private.c", "src/project-docs/plan.h",
                         "include/secrets/token.h", "src/worktrees/candidate.c",
                         "src/reports/log.c", "src/ignored.c"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic fixture")
            (root / ".gitignore").write_text("src/ignored.c\n")
            output = root.parent / "export"
            self.assertEqual(export_sources(root, output, "conan"), ["src/core/a.c"])
            (root / "src/link.c").symlink_to(root / "src/core/a.c")
            with self.assertRaises(ValueError):
                export_sources(root, root.parent / "unsafe", "conan")

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
            audit_install(root, platform="darwin")
            with self.assertRaises(ValueError):
                audit_install(root, platform="linux")
            helper = root / "bin/golem-cgroup-exec"
            helper.write_text("synthetic trusted trampoline")
            audit_install(root, platform="linux")
            helper.unlink()
            extra = root / "private-report.md"
            extra.write_text("synthetic private report")
            with self.assertRaises(ValueError):
                audit_install(root, platform="darwin")
            extra.unlink()
            (root / "include/golem/secret.h").symlink_to(root / "share/licenses/Golem/LICENSE")
            with self.assertRaises(ValueError):
                audit_install(root, platform="darwin")


if __name__ == "__main__":
    unittest.main()
