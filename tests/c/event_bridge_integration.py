"""Real loopback HTTP, immutable source, bounded observers and reconnects."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import select
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import urlsplit

BRIDGE, FIXTURE = map(Path, sys.argv[1:3])
del sys.argv[1:3]


class Events(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="golem-sse-")
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "admission"
        self.source.mkdir(mode=0o700)
        self.token = self.root / "token"
        self.secret = secrets.token_hex(32)
        self.token.write_text(self.secret + "\n")
        self.token.chmod(0o600)
        self.connections = []
        self.process = None
        self.run_fixture("fixture")
        self.start()

    def run_fixture(self, mode):
        subprocess.run([str(FIXTURE), mode, str(self.source)], check=True,
                       capture_output=True, timeout=30)

    def start(self):
        self.errors = tempfile.TemporaryFile()
        self.process = subprocess.Popen([str(BRIDGE), str(self.source), str(self.token), "0"],
                                        stdout=subprocess.PIPE, stderr=self.errors)
        self.assertTrue(select.select([self.process.stdout], [], [], 10)[0], "bridge startup timeout")
        self.url = self.process.stdout.readline().decode().strip()
        self.assertTrue(self.url.startswith("http://127.0.0.1:"), self.url)
        self.port = urlsplit(self.url).port

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait()
                self.fail("bridge did not shut down")
            self.errors.seek(0)
            error = self.errors.read().decode()
            self.assertEqual(self.process.returncode, 0, error)
            self.assertNotIn("Sanitizer", error)
            self.process.stdout.close(); self.errors.close()
            self.process = None

    def tearDown(self):
        for c in self.connections:
            c.close()
        self.stop()
        self.tmp.cleanup()

    def connect(self, path="/events", headers=None, method="GET"):
        h = {"Authorization": "Bearer " + self.secret}
        if headers:
            h.update(headers)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=8)
        self.connections.append(c)
        c.request(method, path, headers=h)
        return c, c.getresponse()

    def frame(self, r):
        lines = []
        while True:
            line = r.readline().decode()
            self.assertTrue(line, "unexpected stream close")
            if line == "\n":
                return "".join(lines)
            lines.append(line)

    def digest_source(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.source.iterdir() if p.is_file()}

    def test_readonly_redaction_reconnect_and_restart(self):
        before = self.digest_source()
        c, r = self.connect()
        self.assertEqual(r.status, 200)
        self.assertIn("transient_worker_gap", self.frame(r))
        first = self.frame(r)
        self.assertNotIn("secret-", first)
        cursor = first.split("id: ", 1)[1].splitlines()[0]
        c.close()
        _, second = self.connect(headers={"Last-Event-ID": cursor})
        self.assertEqual(second.status, 200)
        self.frame(second)
        event = self.frame(second)
        self.assertNotIn("id: " + cursor + "\n", event)
        self.assertEqual(self.digest_source(), before)
        self.stop(); self.start()
        _, resumed = self.connect(headers={"Last-Event-ID": cursor})
        self.assertEqual(resumed.status, 200)
        self.frame(resumed)
        self.assertEqual(self.frame(resumed), event)
        self.assertEqual(self.digest_source(), before)

    def test_auth_host_origin_query_and_methods(self):
        for kwargs, status in [({"headers": {"Authorization": "Bearer wrong"}}, 401),
                               ({"headers": {"Host": "evil.example"}}, 403),
                               ({"headers": {"Origin": "http://evil.example"}}, 403),
                               ({"path": "/events?token=" + self.secret}, 400),
                               ({"method": "POST"}, 400),
                               ({"headers": {"Last-Event-ID": "bad\nid: injection"}}, None)]:
            if status is None:
                with self.assertRaises(ValueError): self.connect(**kwargs)
            else:
                _, r = self.connect(**kwargs)
                self.assertEqual(r.status, status); r.read()

    def test_invalid_and_retention_cursor(self):
        c, r = self.connect(); self.frame(r)
        cursor = self.frame(r).split("id: ", 1)[1].splitlines()[0]
        c.close()
        forged = cursor[:2] + ("a" if cursor[2] != "a" else "b") + cursor[3:]
        _, r = self.connect(headers={"Last-Event-ID": forged})
        self.assertEqual(r.status, 409); r.read()
        self.run_fixture("fill")
        time.sleep(0.6)
        _, r = self.connect(headers={"Last-Event-ID": cursor})
        self.assertEqual(r.status, 410); r.read()
        _, r = self.connect()
        self.assertEqual(r.status, 200)

    def test_subscriber_limit_isolated_from_writer(self):
        for _ in range(32):
            _, r = self.connect()
            self.assertEqual(r.status, 200)
        _, r = self.connect()
        self.assertEqual(r.status, 503); r.read()
        # Clients do not drain their streams. They must never acquire the writer lock.
        self.run_fixture("fill")
        self.assertIsNone(self.process.poll())

    def test_rotation_and_heartbeat(self):
        _, r = self.connect()
        for _ in range(7): self.frame(r)  # source + six durable fixture events
        self.assertIn(": heartbeat", self.frame(r))
        self.token.write_text(secrets.token_hex(32) + "\n")
        self.assertIn("authorization_changed", self.frame(r))
        self.assertEqual(r.read(), b"")
        _, denied = self.connect()
        self.assertEqual(denied.status, 503)

    def test_connection_churn_releases_slots(self):
        for _ in range(40):
            c, r = self.connect()
            self.assertEqual(r.status, 200)
            self.frame(r)
            r.close(); c.close()
        time.sleep(0.3)
        _, r = self.connect()
        self.assertEqual(r.status, 200)

    def test_bad_credential_permissions_fail_closed(self):
        self.stop()
        self.token.chmod(0o644)
        p = subprocess.run([str(BRIDGE), str(self.source), str(self.token), "0"],
                           capture_output=True, timeout=10)
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn(self.secret.encode(), p.stderr + p.stdout)


if __name__ == "__main__":
    unittest.main()
