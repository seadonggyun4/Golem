"""Bounded read-only refresh, transport security and historical/live separation."""
from email.message import Message
import io as streams
import math
import sys
import time
import unittest
from unittest.mock import patch
import urllib.error

import agent_io as io
import remote_status as remote
import revision_status as rs
import test_revision_status


class Refresh(unittest.TestCase):
    git = test_revision_status.RevisionStatus.git
    plan = test_revision_status.RevisionStatus.plan
    run_plan = test_revision_status.RevisionStatus.run_plan
    add = test_revision_status.RevisionStatus.add
    run_response = test_revision_status.RevisionStatus.run_response
    git_commit = test_revision_status.RevisionStatus.git_commit
    setUp = test_revision_status.RevisionStatus.setUp
    work = test_revision_status.RevisionStatus.work

    def queries(self, channel="remote_ci", scope="20", resource_id=10):
        return {"schema": "golem.remote-status-query.v1", "queries": [
            {"id": "check", "channel": channel, "scope": scope, "resource_id": resource_id}]}

    def refresh(self, responses, queries=None):
        def get(path, credential, deadline):
            data = responses.pop(0)
            if isinstance(data, Exception):
                raise data
            return data, io.encoded(data)
        self.count += 1
        self.output = self.root / f"refresh-{self.count}"
        with patch.object(remote, "get", side_effect=get):
            return remote.refresh(self.index, self.source, queries or self.queries(), self.output)

    def deployment(self):
        return {"id": 30, "environment": "production", "sha": self.git_commit(),
                "url": "https://api.github.com/repos/owner/repo/deployments/30"}

    def status(self, id=40, state="success", date="2026-10-10T01:00:00Z"):
        return {"id": id, "environment": "production", "state": state, "created_at": date,
                "deployment_url": self.deployment()["url"],
                "url": self.deployment()["url"] + f"/statuses/{id}"}

    def test_live_run_never_grants_native_or_global_completion(self):
        result = self.refresh([self.run_response()])
        self.assertEqual(result["channels"]["remote_ci"]["status"], "PASS")
        row = result["channels"]["remote_ci"]["evidence"][0]
        self.assertTrue(row["remote_latest_verified"])
        self.assertFalse(row["authenticity_verified"])
        self.assertFalse(result["native_acceptance_verified"])
        self.assertFalse(result["remote_latest_verified"])
        verification = row["verification"]
        self.assertEqual(verification["checks"]["execution"]["state"], "OBSERVED")
        self.assertEqual(verification["checks"]["authenticity"]["state"], "NOT_VERIFIED")
        self.assertEqual(result["overall_completion"], "NOT_INFERRED")
        manifest = io.read_json(self.output / "manifest.json")
        self.assertTrue(all(io.digest(self.output / name) == digest for name, digest in manifest.items()))
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.output.iterdir()))

    def test_new_attempt_pending_supersedes_only_exact_historical_run(self):
        self.add("remote_ci", "github-run.v1", self.run_response(), "20")
        result = self.refresh([self.run_response(run_attempt=2, status="in_progress", conclusion=None)])
        channel = result["channels"]["remote_ci"]
        self.assertEqual(channel["status"], "PENDING")
        self.assertEqual(channel["scopes"], {"20": "PENDING"})
        self.assertIn("superseded_by", channel["evidence"][0])
        # Reading the index again never consumes the saved live assertion.
        self.assertFalse(rs.projection(self.index, self.source)["remote_latest_verified"])

    def test_other_run_conflict_preserved(self):
        self.add("remote_ci", "github-run.v1", self.run_response(id=11,
                 html_url="https://github.com/owner/repo/actions/runs/11"), "20")
        result = self.refresh([self.run_response(conclusion="failure")])
        self.assertEqual(result["channels"]["remote_ci"]["status"], "CONFLICT")

    def test_query_failure_blocks_old_pass_and_retains_capture(self):
        self.add("remote_ci", "github-run.v1", self.run_response(), "20")
        result = self.refresh([remote.QueryError("HTTP_429; NO_RETRY")])
        channel = result["channels"]["remote_ci"]
        self.assertEqual(channel["status"], "REMOTE_QUERY_FAILED")
        self.assertEqual(channel["scopes"]["20"], "REMOTE_QUERY_FAILED")
        self.assertEqual(channel["evidence"][0]["status"], "PASS")
        self.assertFalse(channel["evidence"][1]["remote_latest_verified"])
        self.assertTrue((self.output / "result.json").exists())

    def test_wrong_run_repo_workflow_sha_and_dirty_tree(self):
        for changes in ({"id": 11}, {"workflow_id": 21}, {"repository": {"full_name": "other/repo"}}):
            result = self.refresh([self.run_response(**changes)])
            self.assertEqual(result["channels"]["remote_ci"]["status"], "REMOTE_QUERY_FAILED")
        result = self.refresh([self.run_response(head_sha="f" * 40)])
        self.assertEqual(result["channels"]["remote_ci"]["status"], "NO_CURRENT_EVIDENCE")
        (self.source / "dirty.txt").write_text("dirty")
        result = self.refresh([self.run_response()])
        self.assertEqual(result["channels"]["remote_ci"]["status"], "NO_CURRENT_EVIDENCE")

    def test_source_change_during_query_invalidates_live_row(self):
        def get(*args):
            (self.source / "dirty.txt").write_text("changed")
            data = self.run_response()
            return data, io.encoded(data)
        with patch.object(remote, "get", side_effect=get):
            result = remote.refresh(self.index, self.source, self.queries(), self.root / "changed")
        self.assertEqual(result["channels"]["remote_ci"]["status"], "SOURCE_CHANGED")
        self.assertFalse(result["source_stable"])
        row = result["channels"]["remote_ci"]["evidence"][0]
        self.assertEqual(row["status"], "BLOCKED")

    def test_scopes_distinguish_workflows(self):
        queries = self.queries()
        queries["queries"].append({"id": "second", "channel": "remote_ci", "scope": "21", "resource_id": 11})
        result = self.refresh([self.run_response(), self.run_response(id=11, workflow_id=21,
            html_url="https://github.com/owner/repo/actions/runs/11", conclusion="failure")], queries)
        self.assertEqual(result["channels"]["remote_ci"]["scopes"], {"20": "PASS", "21": "FAIL"})

    def test_deployment_latest_by_timestamp_not_list_position_or_id(self):
        result = self.refresh([self.deployment(), [self.status(id=41),
            self.status(id=40, state="inactive", date="2026-10-10T02:00:00Z")]],
            self.queries("deployment", "production", 30))
        channel = result["channels"]["deployment"]
        self.assertEqual(channel["status"], "INACTIVE")
        self.assertFalse(channel["evidence"][0]["details"]["serving_currently_verified"])

    def test_deployment_missing_tied_duplicate_malformed_and_wrong_identity_block(self):
        for statuses in ([], [self.status(), self.status(id=41)], [self.status(), self.status()],
                         [self.status(date="bad")], [{**self.status(), "environment": "other"}]):
            result = self.refresh([self.deployment(), statuses], self.queries("deployment", "production", 30))
            self.assertEqual(result["channels"]["deployment"]["status"], "REMOTE_QUERY_FAILED")

    def test_query_validation_and_output_overlap(self):
        for change in ({"resource_id": True}, {"resource_id": 0}, {"scope": "../20"},
                       {"id": "../../escape"}, {"channel": "completion"}):
            queries = self.queries()
            queries["queries"][0].update(change)
            with self.assertRaises(ValueError):
                remote.validate_queries(queries)
        queries = self.queries()
        queries["queries"] *= 2
        with self.assertRaises(ValueError):
            remote.validate_queries(queries)
        for timeout in (0, 301, math.inf, math.nan, True):
            with self.assertRaises(ValueError):
                remote.refresh(self.index, self.source, self.queries(), self.root / "unused", timeout=timeout)
        with self.assertRaises(ValueError):
            remote.refresh(self.index, self.source, self.queries(), self.source / "output")

    def test_cli_exit_status_is_query_validity_not_completion(self):
        for data, expected in ((self.run_response(conclusion="failure"), 0),
                               (remote.QueryError("HTTP_403"), 1)):
            self.count += 1
            index, query = self.root / "index.json", self.root / "query.json"
            index.write_bytes(io.encoded(self.index))
            query.write_bytes(io.encoded(self.queries()))
            with patch.object(remote, "get") as get, patch.object(sys, "stdout") as stdout:
                if isinstance(data, Exception):
                    get.side_effect = data
                else:
                    get.return_value = data, io.encoded(data)
                code = remote.main([str(index), str(query), "--cwd", str(self.source), "--output",
                                    str(self.root / f"cli-{self.count}")])
                self.assertEqual(code, expected)
                self.assertTrue(stdout.buffer.write.called)

    def test_failed_channel_does_not_erase_valid_other_channel(self):
        self.add()
        result = self.refresh([remote.QueryError("HTTP_404")])
        self.assertEqual(result["channels"]["local_qa"]["status"], "OBSERVED_EXIT_OK")
        self.assertEqual(result["channels"]["remote_ci"]["status"], "REMOTE_QUERY_FAILED")

    def test_rate_limit_stops_remaining_network_requests(self):
        queries = self.queries()
        queries["queries"].append({"id": "second", "channel": "remote_ci", "scope": "21", "resource_id": 11})
        with patch.object(remote, "get", side_effect=remote.QueryError("HTTP_429; NO_RETRY")) as get:
            result = remote.refresh(self.index, self.source, queries, self.root / "rate-limited")
        self.assertEqual(get.call_count, 1)
        rows = result["channels"]["remote_ci"]["evidence"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["diagnostic"], "BATCH_STOPPED_AFTER_ACCESS_OR_RATE_LIMIT_ERROR")

    def test_output_cannot_overwrite_previous_capture(self):
        self.refresh([self.run_response()])
        before = (self.output / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            remote.refresh(self.index, self.source, self.queries(), self.output)
        self.assertEqual((self.output / "manifest.json").read_bytes(), before)


class Transport(unittest.TestCase):
    path = "/repos/owner/repo/actions/runs/10"

    def request(self, raw=b'{}', headers=None, status=200, url=None, credential=None):
        response = streams.BytesIO(raw)
        response.status = status
        response.geturl = lambda: url or remote.ORIGIN + self.path
        response.headers = Message()
        response.headers["Content-Type"] = "application/json"
        for name, value in (headers or {}).items():
            response.headers.replace_header(name, value) if name in response.headers else response.headers.add_header(name, value)
        with patch.object(remote.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            result = remote.get(self.path, credential, time.monotonic() + 5)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, remote.ORIGIN + self.path)
            return result

    def test_strict_json_and_safe_transport(self):
        self.assertEqual(self.request(b'{"ok":true}')[0], {"ok": True})
        for data in (b'{"a":1,"a":2}', b'not json', b'{"secret":"token-value"}',
                     b'[' * 2000 + b'0' + b']' * 2000):
            with self.assertRaises(ValueError):
                self.request(data, credential="token-value")

    def test_bounded_body_and_pagination(self):
        with patch.object(remote, "MAX_BODY", 5):
            with self.assertRaises(ValueError):
                self.request(b'{"abc":1}')
        with self.assertRaises(ValueError):
            self.request(headers={"Link": '<https://evil.test>; rel="next"'})

    def test_reject_content_encoding_origin_status_and_redirect(self):
        for kwargs in ({"headers": {"Content-Type": "text/html"}},
                       {"headers": {"Content-Encoding": "gzip"}}, {"status": 201},
                       {"url": "https://evil.test"}):
            with self.assertRaises(ValueError):
                self.request(**kwargs)
        body = streams.BytesIO(b"secret")
        with self.assertRaises(remote.QueryError):
            remote.NoRedirect().redirect_request(None, body, 302, "", {}, "https://evil.test")
        self.assertTrue(body.closed)

    def test_http_error_no_body_or_retry_and_network_failure(self):
        for code in (401, 403, 404, 429, 500):
            error = urllib.error.HTTPError("", code, "secret", {}, streams.BytesIO(b"secret"))
            with patch.object(remote.urllib.request, "build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaisesRegex(remote.QueryError, f"HTTP_{code}") as caught:
                    remote.get(self.path, None, time.monotonic() + 5)
                self.assertNotIn("secret", str(caught.exception))
                self.assertEqual(opener.return_value.open.call_count, 1)
        with patch.object(remote.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = urllib.error.URLError("secret")
            with self.assertRaisesRegex(remote.QueryError, "NETWORK_OR_TIMEOUT"):
                remote.get(self.path, None, time.monotonic() + 5)

    def test_deadline_bad_credentials_and_endpoint(self):
        with self.assertRaises(ValueError):
            remote.get(self.path, None, time.monotonic() - 1)
        for credential in ("bad\nheader", "x" * 4097):
            with self.assertRaises(ValueError):
                remote.get(self.path, credential, time.monotonic() + 5)
        with self.assertRaises(ValueError):
            remote.get("https://evil.test", None, time.monotonic() + 5)


if __name__ == "__main__":
    unittest.main()
