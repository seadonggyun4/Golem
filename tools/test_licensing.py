"""Keep standalone package legal files identical to the canonical root files."""
import json
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = ("LICENSE", "NOTICE", "COMMERCIAL-LICENSE.md")
SPDX = "PolyForm-Noncommercial-1.0.0"


class LicensingTests(unittest.TestCase):
    def test_standalone_package_notices(self):
        for package in ("bindings/python", "bindings/typescript"):
            for name in FILES:
                with self.subTest(package=package, name=name):
                    self.assertEqual((ROOT / name).read_bytes(), (ROOT / package / name).read_bytes())

    def test_package_metadata(self):
        for package in (ROOT, ROOT / "bindings/python"):
            project = tomllib.loads((package / "pyproject.toml").read_text())["project"]
            self.assertEqual(project["license"], SPDX)
            self.assertEqual(set(project["license-files"]), set(FILES))
        node = json.loads((ROOT / "bindings/typescript/package.json").read_text())
        self.assertEqual(node["license"], SPDX)
        self.assertTrue(set(FILES).issubset(node["files"]))


if __name__ == "__main__":
    unittest.main()
