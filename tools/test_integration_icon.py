"""Public MCP branding only; no project grants, Work or client settings."""
import base64
from importlib.metadata import PackageNotFoundError, version
import struct
import unittest
from unittest.mock import patch

import integration_contract as c
import integration_mcp as branding


class Icon(unittest.TestCase):
    def test_bounded_pinned_png(self):
        data = branding.icon_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (256, 256))
        self.assertLessEqual(len(data), 163840)
        self.assertEqual(c.sha(data), branding.ICON_SHA256)

    def test_changed_asset_is_not_advertised(self):
        with patch.object(branding, "regular", return_value=b"unapproved replacement"):
            with self.assertRaisesRegex(c.IntegrationError, "MCP_ICON_CHANGED"):
                branding.icon_bytes()

    def test_all_server_initialization_metadata(self):
        try:
            if version("mcp") != "2.3.0" or version("mcp-types") != "2.3.0":
                self.skipTest("Pinned MCP SDK required")
            version("uvicorn")
            version("PyJWT")
        except PackageNotFoundError:
            self.skipTest("Install tools/requirements-gateway.txt for SDK metadata test")
        import integration_mutation_mcp as mutations
        from integration_gateway import Gateway
        for server in (branding.server(None), mutations.server(None), Gateway.__new__(Gateway).server()):
            with self.subTest(server=server.name):
                options = server.create_initialization_options()
                self.assertEqual(len(options.icons), 1)
                icon = options.icons[0]
                self.assertEqual(icon.mime_type, "image/png")
                self.assertEqual(icon.sizes, ["256x256"])
                self.assertTrue(icon.src.startswith("data:image/png;base64,"))
                self.assertLess(len(icon.src), c.LIMIT)
                self.assertEqual(base64.b64decode(icon.src.split(",", 1)[1], validate=True), branding.icon_bytes())


if __name__ == "__main__":
    unittest.main()
