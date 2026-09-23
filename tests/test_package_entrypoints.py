"""The historical Python package must never shadow the native C executable."""
from pathlib import Path
import tomllib
import unittest


class PackageEntrypoints(unittest.TestCase):
    def test_native_cli_name_is_reserved(self):
        root = Path(__file__).resolve().parents[1]
        with (root / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)
        self.assertEqual(project["project"]["scripts"], {"golem-prototype": "golem.cli:main"})
        packages = project["tool"]["setuptools"]["packages"]["find"]
        self.assertEqual(packages["include"], ["golem", "golem.*"])
        self.assertFalse(packages["namespaces"])


if __name__ == "__main__":
    unittest.main()
