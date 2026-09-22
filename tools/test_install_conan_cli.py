from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from install_conan_cli import install


class InstallerTests(unittest.TestCase):
    def test_existing_installation_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prefix = root / "installed"
            prefix.mkdir()
            with patch("install_conan_cli.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    install("conan", "golem/0.1.0", prefix, root / "bin")
                run.assert_not_called()

    def test_broken_command_link_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            (root / "bin/golem").symlink_to(root / "missing")
            with self.assertRaises(ValueError):
                install("conan", "golem/0.1.0", root / "new", root / "bin")
            self.assertTrue((root / "bin/golem").is_symlink())

    def test_failed_deployment_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("install_conan_cli.subprocess.run", side_effect=RuntimeError("synthetic failure")):
                with self.assertRaises(RuntimeError):
                    install("conan", "golem/0.1.0", root / "new", root / "bin")
            self.assertFalse((root / "new").exists())
            self.assertFalse((root / "bin/golem").exists())
            self.assertFalse(list(root.glob(".golem-install-*")))


if __name__ == "__main__":
    unittest.main()
