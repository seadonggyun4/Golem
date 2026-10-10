"""Real loopback + child-process tests; no provider credentials or model charges."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

import hosted_usage as hosted
import usage_pipeline as pipeline
from test_usage_integrations import scope, otlp


class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        inbox = self.root / "inbox"; inbox.mkdir(mode=0o700)
        bound = scope("claude.otel.v1"); bound.update(session_owned=True, prompt_ids=[])
        mapping = {"schema": "golem.usage-route.v1", "run_id": "cost-run", "sequence": 1,
            "currency": "USD", "tool_calls": {"request": 0}, "inbox": str(inbox), "require_billed": False}
        self.p = pipeline.Pipeline.create(self.root / "pipeline", bound, mapping)

    def test_authenticated_durable_ack_then_restart(self):
        token = "x" * 32
        with hosted.server(self.p, token) as server:
            thread = threading.Thread(target=server.serve_forever); thread.start()
            try:
                endpoint = "http://127.0.0.1:%d/v1/logs" % server.server_port
                for auth, expected in (("bad", 403), (token, 200), (token, 200)):
                    request = Request(endpoint, data=json.dumps(otlp()).encode(),
                        headers={"Authorization": "Bearer " + auth})
                    if expected == 403:
                        with self.assertRaises(HTTPError) as error:
                            urlopen(request, timeout=3)
                        error.exception.close()
                    else:
                        with urlopen(request, timeout=3) as response:
                            self.assertEqual(response.status, expected)
            finally:
                server.shutdown(); thread.join()
        p = pipeline.Pipeline(self.p.directory)
        self.assertEqual(len(p.load()[1]["events"]), 1)
        self.assertEqual(p.close()["native_delivery"], "PUBLISHED")

    def test_owned_child_exports_without_global_configuration(self):
        code = ("import os,json; from urllib.request import Request,urlopen; "
            "body=" + repr(json.dumps(otlp()).encode()) + "; "
            "request=Request(os.environ['OTEL_EXPORTER_OTLP_LOGS_ENDPOINT'],data=body,"
            "headers={'Authorization':os.environ['OTEL_EXPORTER_OTLP_HEADERS'].split('=',1)[1]}); "
            "urlopen(request,timeout=3).close()")
        result = pipeline.run_claude(self.p, [sys.executable, "-c", code, "--session-id", "session"], 10, 0)
        self.assertEqual(result["native_delivery"], "PUBLISHED")
        self.assertEqual(result["child_exit_code"], 0)
        record = next(self.p.directory.glob("child-*/started.json"))
        started = json.loads(record.read_bytes())
        self.assertTrue(started["argv_redacted"])
        self.assertNotIn(b"private prompt", record.read_bytes())
        self.assertFalse(list(record.parent.glob("*.log")))

    def test_child_timeout_reaps_and_preserves_open_unknown_state(self):
        with self.assertRaisesRegex(ValueError, "TIMEOUT"):
            pipeline.run_claude(self.p, [sys.executable, "-c", "import time; time.sleep(30)",
                "--session-id", "session"], 1, 0)
        self.assertFalse(self.p.load()[1]["closed"])
        self.assertEqual(self.p.sync()["native_delivery"], "PENDING")

    def test_common_private_boundary_kills_descendants_and_redacts_arguments(self):
        marker = self.root / "orphan"
        grandchild = "import time; from pathlib import Path; time.sleep(.5); Path(" + repr(str(marker)) + ").touch()"
        code = "import subprocess,sys; subprocess.Popen([sys.executable,'-c'," + repr(grandchild) + "])"
        destination = self.root / "private-child"
        result = pipeline.run_private([sys.executable, "-c", code, "confidential prompt"],
            destination=destination, timeout=3, source=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0)
        time.sleep(.7)
        self.assertFalse(marker.exists())
        self.assertFalse(any(b"confidential prompt" in p.read_bytes() for p in destination.glob("*.json")))


if __name__ == "__main__":
    unittest.main()
