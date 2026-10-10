"""Policy discovery, HTTP revalidation, crash boundaries and collector restart."""
import copy
from email.message import Message
import io as streams
import sys
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error

import agent_io as io
import github_checks as gh
import status_collector as collector
import test_revision_status


class Fixture:
    def __init__(self, sha, checks=None, statuses=None, protected=False, rules=None, legacy=None):
        self.sha, self.checks, self.statuses = sha, checks or [], statuses or []
        self.protected, self.rules, self.legacy = protected, rules or [], legacy
        self.exchanges, self.cache, self.delay = [], {}, 0

    def one(self, path):
        if path.endswith("/protection"):
            if isinstance(self.legacy, Exception):
                raise self.legacy
            return {"required_status_checks": self.legacy}
        return {"protected": self.protected, "commit": {"sha": self.sha}}

    def pages(self, path, key=None, **params):
        if "/rules/" in path:
            return self.rules
        if path.endswith("/check-runs"):
            return [r for r in self.checks if not params.get("status") or r["status"] == params["status"]]
        if path == "/deployments":
            return []
        return self.statuses


class Policy(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.rule = {"type": "required_status_checks", "parameters": {"required_status_checks": [
            {"context": "build", "integration_id": 10}]}}
        self.check = {"id": 1, "head_sha": self.sha, "name": "build", "app": {"id": 10},
                      "status": "completed", "conclusion": "success"}

    def policy(self, **kwargs):
        return gh.discover(Fixture(self.sha, **kwargs), "feature/a")

    def test_union_rules_and_legacy_pinned_apps_and_no_duplicates(self):
        policy = self.policy(protected=True, legacy={"contexts": ["build", "lint"], "checks": [
            {"context": "build", "app_id": 10}]}, rules=[self.rule])
        self.assertEqual(len(policy["checks"]), 2)
        self.assertEqual(policy["checks"][0]["app_id"], 10)
        self.assertEqual(policy["checks"][0]["sources"], ["branch_protection", "ruleset"])

    def test_no_policy_is_not_required_not_pass(self):
        policy = self.policy()
        result = gh.evaluate(policy, [self.check], [], self.sha)
        self.assertEqual(result["status"], "NOT_REQUIRED")
        self.assertTrue(policy["discovery_complete"])

    def test_missing_wrong_app_and_pending_never_pass(self):
        policy = self.policy(rules=[self.rule])
        for rows, status in (([], "MISSING"), ([{**self.check, "app": {"id": 11}}], "MISSING"),
                             ([{**self.check, "status": "queued", "conclusion": None}], "PENDING")):
            result = gh.evaluate(policy, rows, [], self.sha)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["requirements"][0]["status"], status)
        self.assertEqual(gh.evaluate(policy, [self.check], [], self.sha)["status"], "PASS")

    def test_conflict_neutral_skipped_and_legacy_identity(self):
        policy = self.policy(rules=[self.rule])
        for conclusion in ("skipped", "neutral", "cancelled", "failure"):
            self.assertEqual(gh.evaluate(policy, [{**self.check, "conclusion": conclusion}], [], self.sha)["status"], "BLOCKED")
        legacy = [{"id": 2, "context": "build", "state": "success"}]
        self.assertEqual(gh.evaluate(policy, [self.check], legacy, self.sha)["status"], "BLOCKED")
        policy["checks"][0]["app_id"] = None
        self.assertEqual(gh.evaluate(policy, [self.check], legacy, self.sha)["status"], "PASS")
        legacy[0]["state"] = "pending"
        self.assertEqual(gh.evaluate(policy, [self.check], legacy, self.sha)["requirements"][0]["status"], "CONFLICT")

    def test_legacy_uses_documented_newest_first(self):
        policy = self.policy(legacy={"contexts": ["build"]}, protected=True)
        statuses = [{"id": 4, "context": "build", "state": "failure"},
                    {"id": 3, "context": "build", "state": "success"}]
        self.assertEqual(gh.evaluate(policy, [], statuses, self.sha)["requirements"][0]["status"], "FAIL")

    def test_workflows_and_other_check_gates_are_discovered_not_dropped(self):
        workflow = {"repository_id": 1, "path": ".github/workflows/review.yml", "ref": "main"}
        policy = self.policy(rules=[{"type": "workflows", "parameters": {"workflows": [workflow]}},
                                   {"type": "code_scanning", "parameters": {}}])
        result = gh.evaluate(policy, [], [], self.sha)
        self.assertTrue(policy["discovery_complete"])
        self.assertFalse(result["evaluation_complete"])
        self.assertEqual(len(result["requirements"]), 2)
        self.assertEqual(result["status"], "BLOCKED")
        unknown = self.policy(rules=[{"type": "future_required_gate", "parameters": {}}])
        self.assertFalse(gh.evaluate(unknown, [], [], self.sha)["evaluation_complete"])

    def test_ambiguous_legacy_404_not_empty_policy(self):
        with self.assertRaises(gh.APIError):
            self.policy(protected=True, legacy=gh.APIError("HTTP_404"))

    def test_ruleset_only_branch_explicitly_disables_legacy_protection(self):
        fixture = Fixture(self.sha, protected=True, rules=[self.rule], legacy=gh.APIError("HTTP_404"))
        original = fixture.one
        def one(path):
            result = original(path)
            if not path.endswith("/protection"):
                result["protection"] = {"enabled": False, "required_status_checks": {
                    "enforcement_level": "off", "contexts": [], "checks": []}}
            return result
        fixture.one = one
        result = gh.discover(fixture, "main")
        self.assertEqual(result["checks"][0]["context"], "build")
        self.assertTrue(result["discovery_complete"])

    def test_disabled_legacy_summary_cannot_conceal_named_requirements(self):
        fixture = Fixture(self.sha, protected=True, rules=[self.rule])
        fixture.one = lambda path: {"protected": True, "commit": {"sha": self.sha},
            "protection": {"enabled": False, "required_status_checks": {"contexts": ["hidden"]}}}
        with self.assertRaises(ValueError):
            gh.discover(fixture, "main")

    def test_bad_identity_duplicates_and_malformed_rule_fail_closed(self):
        policy = self.policy(rules=[self.rule])
        for checks in ([self.check, self.check], [{**self.check, "head_sha": "f" * 40}],
                       [{**self.check, "status": "bad"}]):
            with self.assertRaises(ValueError):
                gh.evaluate(policy, checks, [], self.sha)
        with self.assertRaises((ValueError, KeyError)):
            self.policy(rules=[{"type": "required_status_checks", "parameters": {}}])


class State(unittest.TestCase):
    git = test_revision_status.RevisionStatus.git
    setUp = test_revision_status.RevisionStatus.setUp
    git_commit = test_revision_status.RevisionStatus.git_commit
    work = test_revision_status.RevisionStatus.work

    def setup_state(self):
        self.config = collector.config(self.index, self.source, "main", 60, 180)
        self.state = collector.directory(self.root / "collector")

    def cycle(self, fixture=None):
        fixture = fixture or Fixture(self.git_commit())
        with patch.object(collector.github, "Client", return_value=fixture):
            return collector.collect(self.config, self.state)

    def test_restart_history_integrity_and_freshness_expiration(self):
        self.setup_state()
        self.cycle()
        first = io.read_json(self.state / "latest.json")["cycle"]
        self.cycle()
        self.assertEqual(len(list(self.state.glob("cycle-*"))), 2)
        self.assertTrue((self.state / first / "manifest.json").exists())
        result = collector.read(self.config, self.state)
        self.assertEqual(result["required_checks"]["status"], "NOT_REQUIRED")
        expires = result["continuous_collection"]["expires_at"]
        self.assertEqual(collector.read(self.config, self.state, expires + 1)["required_checks"]["status"], "EXPIRED_CAPTURE")
        self.assertEqual(collector.read(self.config, self.state, 0)["required_checks"]["status"], "EXPIRED_CAPTURE")
        self.assertFalse(result["native_acceptance_verified"])

    def test_failed_cycle_replaces_historical_success(self):
        self.setup_state()
        self.cycle()
        broken = Fixture(self.git_commit(), protected=True, legacy=gh.APIError("HTTP_403", 1000))
        self.cycle(broken)
        result = collector.read(self.config, self.state)
        self.assertEqual(result["required_checks"]["status"], "DISCOVERY_FAILED")
        self.assertGreaterEqual(result["required_checks"]["recommended_interval"], 1000)

    def test_scope_source_and_tamper_checks(self):
        self.setup_state()
        self.cycle()
        config = {**self.config, "branch": "other"}
        with self.assertRaises(ValueError):
            collector.read(config, self.state)
        (self.source / "changed").write_text("dirty")
        self.assertEqual(collector.read(self.config, self.state)["required_checks"]["status"], "STALE_SOURCE")
        head = io.read_json(self.state / "latest.json")
        (self.state / head["cycle"] / "result.json").write_text("{}")
        with self.assertRaises(ValueError):
            collector.read(self.config, self.state)

    def test_private_state_lock_and_quota(self):
        self.setup_state()
        with collector.lock(self.state):
            with self.assertRaises(ValueError):
                with collector.lock(self.state):
                    pass
        with self.assertRaises(ValueError):
            collector.run(self.config, self.state, max_bytes=1)
        self.state.chmod(0o755)
        with self.assertRaises(ValueError):
            collector.directory(self.state)

    def test_continuous_loop_backoff_and_stop(self):
        self.setup_state()
        stop = threading.Event()
        success = {"required_checks": {"status": "NOT_REQUIRED", "discovery_complete": True, "recommended_interval": 60}}
        with patch.object(collector, "collect", return_value=success) as collect, patch.object(sys, "stdout"), \
                patch.object(stop, "wait", return_value=False) as wait:
            collector.run(self.config, self.state, follow=True, max_cycles=2, stop=stop)
        self.assertEqual(collect.call_count, 2)
        wait.assert_called_once_with(60)
        stop.set()
        with patch.object(collector, "collect") as collect:
            self.assertIsNone(collector.run(self.config, self.state, follow=True, stop=stop))
            collect.assert_not_called()

    def test_policy_change_and_dirty_source_block_current_acceptance(self):
        self.setup_state()
        fixture = Fixture(self.git_commit())
        original = gh.discover
        calls = 0
        def discover(*args):
            nonlocal calls
            value = original(*args)
            calls += 1
            if calls == 2:
                value["branch_sha"] = "f" * 40
            return value
        with patch.object(gh, "discover", side_effect=discover):
            result = self.cycle(fixture)
        self.assertEqual(result["required_checks"]["status"], "DISCOVERY_FAILED")
        (self.source / "dirty").write_text("dirty")
        self.assertEqual(self.cycle()["required_checks"]["status"], "COMMIT_ONLY_DIRTY_SOURCE")

    def test_restart_honors_persisted_rate_delay(self):
        self.setup_state()
        self.cycle(Fixture(self.git_commit(), protected=True, legacy=gh.APIError("HTTP_429", 900)))
        stop = threading.Event()
        with patch.object(stop, "wait", return_value=True) as wait, patch.object(collector, "collect") as collect:
            collector.run(self.config, self.state, stop=stop)
        self.assertGreater(wait.call_args.args[0], 890)
        collect.assert_not_called()

    def test_crash_before_pointer_publish_keeps_previous_complete_cycle(self):
        self.setup_state()
        self.cycle()
        head = (self.state / "latest.json").read_bytes()
        with patch.object(collector, "atomic", side_effect=OSError("injected fsync failure")):
            with self.assertRaises(OSError):
                self.cycle()
        self.assertEqual((self.state / "latest.json").read_bytes(), head)
        self.assertEqual(collector.read(self.config, self.state)["required_checks"]["status"], "NOT_REQUIRED")

    def test_credential_loss_publishes_failure_without_anonymous_fallback(self):
        self.setup_state()
        fixture = Fixture(self.git_commit())
        with patch.object(collector.github, "Client", return_value=fixture):
            result = collector.collect(self.config, self.state, credential_failure=True)
        self.assertEqual(result["required_checks"]["status"], "DISCOVERY_FAILED")
        self.assertEqual(result["required_checks"]["diagnostic"], "CREDENTIAL_UNAVAILABLE")

    def test_pending_rerun_cannot_be_hidden_by_latest_terminal_filter(self):
        self.setup_state()
        sha = self.git_commit()
        rule = {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "build"}]}}
        passed = {"id": 1, "head_sha": sha, "name": "build", "app": {"id": 10},
                  "status": "completed", "conclusion": "success"}
        pending = {**passed, "id": 2, "status": "queued", "conclusion": None}
        fixture = Fixture(sha, checks=[passed], rules=[rule])
        original = fixture.pages
        def pages(path, key=None, **params):
            if params.get("status") == "queued":
                return [pending]
            return original(path, key, **params)
        fixture.pages = pages
        self.assertEqual(self.cycle(fixture)["required_checks"]["status"], "BLOCKED")

    def test_dirty_source_does_not_erase_commit_failure(self):
        self.setup_state()
        (self.source / "dirty").write_text("dirty")
        sha = self.git_commit()
        rule = {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "build"}]}}
        failed = {"id": 1, "head_sha": sha, "name": "build", "app": {"id": 10},
                  "status": "completed", "conclusion": "failure"}
        result = self.cycle(Fixture(sha, checks=[failed], rules=[rule]))["required_checks"]
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["commit_status"], "BLOCKED")

    def test_automatic_deployment_discovery_and_stale_revision(self):
        self.setup_state()
        fixture = Fixture(self.git_commit())
        url = "https://api.github.com/repos/owner/repo/deployments/30"
        deployment = {"id": 30, "environment": "production", "sha": "f" * 40,
                      "url": url, "created_at": "2026-10-10T00:00:00Z"}
        status = {"id": 40, "environment": "production", "state": "success", "deployment_url": url,
                  "url": url + "/statuses/40", "created_at": "2026-10-10T00:01:00Z"}
        def pages(path, **kwargs):
            return [deployment] if path == "/deployments" else [status]
        fixture.pages = pages
        inventory = gh.deployments(fixture, self.index, gh.rs.target_source(self.source, "owner/repo"))
        self.assertTrue(inventory["discovery_complete"])
        self.assertEqual(inventory["evidence"][0]["source_relation"], "STALE")
        self.assertFalse(inventory["environments"][0]["serving_currently_verified"])
        fixture.pages = lambda path, **kw: [deployment, deployment]
        self.assertFalse(gh.deployments(fixture, self.index, inventory["evidence"][0]["source_pin"])["discovery_complete"])


class HTTP(unittest.TestCase):
    def response(self, address, value, **headers):
        response = streams.BytesIO(io.encoded(value))
        response.status = 200
        response.geturl = lambda: address
        response.headers = Message()
        response.headers["Content-Type"] = "application/json"
        for key, val in headers.items():
            response.headers[key.replace("_", "-")] = val
        return response

    def test_etag_revalidation_survives_new_client_and_corruption_refetches(self):
        cache = {}
        client = gh.Client("owner/repo", cache=cache)
        address = client.endpoint("/branches/main")
        client.opener.open = lambda *a, **k: self.response(address, {"ok": True}, ETag='"one"')
        self.assertEqual(client.get(address)[0], {"ok": True})
        next_client = gh.Client("owner/repo", cache=copy.deepcopy(cache))
        def unchanged(request, **kwargs):
            self.assertEqual(request.get_header("If-none-match"), '"one"')
            raise urllib.error.HTTPError(address, 304, "", Message(), streams.BytesIO())
        next_client.opener.open = unchanged
        self.assertEqual(next_client.get(address)[0], {"ok": True})
        self.assertEqual(next_client.exchanges[0]["http_status"], 304)
        client.cache[address]["sha256"] = "0" * 64
        def refetch(request, **kwargs):
            self.assertIsNone(request.get_header("If-none-match"))
            return self.response(address, {"ok": False})
        client.opener.open = refetch
        self.assertEqual(client.get(address)[0], {"ok": False})

    def test_pagination_exact_origin_and_complete_count(self):
        client = gh.Client("owner/repo")
        first = client.endpoint("/commits/sha/check-runs", filter="latest", per_page=100)
        second = first + "&page=2"
        client.opener.open = lambda req, **kw: self.response(req.full_url,
            {"total_count": 2, "check_runs": [1 if req.full_url == first else 2]},
            **({"Link": f'<{second}>; rel="next"'} if req.full_url == first else {}))
        self.assertEqual(client.pages("/commits/sha/check-runs", "check_runs", filter="latest"), [1, 2])
        for next_url in (second.replace("api.github.com", "evil.test"), second + "&filter=all",
                         second.replace("/commits/sha/", "/commits/other/"), second.replace("page=2", "page=3")):
            client = gh.Client("owner/repo")
            client.opener.open = lambda req, **kw: self.response(req.full_url, [], Link=f'<{next_url}>; rel="next"')
            with self.assertRaises(ValueError):
                client.pages("/commits/sha/check-runs", filter="latest")

    def test_rate_errors_redact_and_honor_retry_time(self):
        client = gh.Client("owner/repo")
        headers = Message()
        headers["Retry-After"] = "900"
        def error(*args, **kwargs):
            raise urllib.error.HTTPError("", 429, "secret", headers, streams.BytesIO(b"secret"))
        client.opener.open = error
        with self.assertRaises(gh.APIError) as caught:
            client.get(client.endpoint("/branches/main"))
        self.assertEqual(caught.exception.retry_after, 900)
        self.assertNotIn("secret", str(caught.exception))

    def test_unsafe_repo_endpoint_origin_and_budget(self):
        for repo in ("../repo", "owner/..", "owner/repo/other"):
            with self.assertRaises(ValueError):
                gh.Client(repo)
        client = gh.Client("owner/repo", budget=1)
        with self.assertRaises(ValueError):
            client.get("https://evil.test")
        client.budget = 0
        with self.assertRaises(ValueError):
            client.get(client.endpoint("/branches/main"))

    def test_page_count_mismatch_and_304_without_intact_cache_block(self):
        client = gh.Client("owner/repo")
        client.opener.open = lambda req, **kw: self.response(req.full_url, {"total_count": 2, "check_runs": [1]})
        with self.assertRaises(ValueError):
            client.pages("/commits/sha/check-runs", "check_runs")
        def unchanged(*args, **kwargs):
            raise urllib.error.HTTPError("", 304, "", Message(), streams.BytesIO())
        client.opener.open = unchanged
        with self.assertRaises(gh.APIError):
            client.one("/branches/main")

    def test_transport_refuses_secret_echo_encoding_and_wrong_identity(self):
        client = gh.Client("owner/repo", credential="private-token")
        address = client.endpoint("/branches/main")
        for value, headers in (({"token": "private-token"}, {}), ({}, {"Content_Encoding": "gzip"})):
            client.opener.open = lambda req, **kw: self.response(address, value, **headers)
            with self.assertRaises(ValueError):
                client.get(address)
        client.opener.open = lambda req, **kw: self.response("https://evil.test", {})
        with self.assertRaises(ValueError):
            client.get(address)


if __name__ == "__main__":
    unittest.main()
