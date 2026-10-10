"""Policy semantics and fail-closed evidence boundaries, without remote writes."""
import copy
import unittest

import github_checks as gh
import github_policy as policy
import test_status_collector as fixtures


SHA = "a" * 40
NOW = "2026-10-10T00:00:00Z"
OLD = "2026-10-09T00:00:00Z"
REF = "refs/heads/main"


class Provider:
    def __init__(self):
        self.rows, self.objects, self.calls = {}, {}, []

    def endpoint(self, path, **params):
        return "https://api.github.com/repos/o/r" + path

    def pages(self, path, key=None, **params):
        self.calls.append((path, params))
        value = self.rows.get(path, [])
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    def one(self, path, **params):
        self.calls.append((path, params))
        return copy.deepcopy(self.objects[path])


class Domain(unittest.TestCase):
    def setUp(self):
        self.client = Provider()
        self.base = {"branch_sha": SHA, "other_rules": [], "workflow_rules": []}
        self.scan = {"type": "code_scanning", "parameters": {"code_scanning_tools": [
            {"tool": "CodeQL", "alerts_threshold": "errors", "security_alerts_threshold": "high_or_higher"}]}}
        self.deploy = {"type": "required_deployments", "parameters": {
            "required_deployment_environments": ["staging"]}}
        self.workflow = {"type": "workflows", "ruleset_id": 7, "parameters": {"workflows": [
            {"repository_id": 2, "path": ".github/workflows/required.yml", "sha": "b" * 40}]}}
        self.analysis = {"id": 1, "commit_sha": SHA, "ref": REF, "tool": {"name": "CodeQL", "guid": None},
                         "analysis_key": "analyze", "environment": "{}", "category": "python",
                         "created_at": NOW, "error": "", "warning": ""}
        self.alert = {"number": 1, "state": "open", "tool": {"name": "CodeQL"},
                      "rule": {"severity": "error", "security_severity_level": None, "tags": []},
                      "most_recent_instance": {"ref": REF, "commit_sha": SHA, "state": "open"}}
        self.client.rows["/code-scanning/analyses"] = [self.analysis]
        self.deployment = {"id": 4, "sha": SHA, "environment": "staging", "created_at": NOW}
        self.status = {"id": 5, "state": "success", "environment": "staging", "created_at": NOW,
                       "deployment_url": self.client.endpoint("/deployments/4")}
        self.client.rows["/deployments"] = [self.deployment]
        self.client.rows["/deployments/4/statuses"] = [self.status]
        self.suite = {"id": 8, "after_sha": SHA, "ref": REF, "repository_id": 9,
                      "pushed_at": NOW, "result": "pass"}
        self.client.rows["/rulesets/rule-suites"] = [self.suite]
        self.client.objects["/rulesets/7"] = {"id": 7, "enforcement": "active", "updated_at": OLD,
            "rules": [{"type": "workflows", "parameters": self.workflow["parameters"]}]}
        self.client.objects["/rulesets/rule-suites/8"] = {**self.suite, "rule_evaluations": [
            {"rule_type": "workflows", "rule_source": {"type": "ruleset", "id": 7},
             "enforcement": "active", "result": "pass"}]}

    def run_rule(self, rule):
        base = {**self.base, "workflow_rules": [rule] if rule["type"] == "workflows" else [],
                "other_rules": [] if rule["type"] == "workflows" else [rule]}
        return policy.collect(self.client, base, SHA, "main")[0]

    def test_workflow_exact_pinned_provider_result(self):
        row = self.run_rule(self.workflow)
        self.assertEqual(row["status"], "PASS")
        self.assertFalse(row["current_merge_authorized"])
        self.assertEqual(row["evidence"][0]["ruleset_id"], 7)
        self.assertEqual(self.client.calls[1][1]["evaluate_status"], "active")

    def test_workflow_unpinned_ref_stays_unverified(self):
        self.workflow["parameters"]["workflows"][0].pop("sha")
        self.workflow["parameters"]["workflows"][0]["ref"] = "main"
        self.assertEqual(self.run_rule(self.workflow)["status"], "DEFINITION_REVISION_UNVERIFIED")

    def test_workflow_missing_identity_never_guesses_by_name(self):
        self.workflow.pop("ruleset_id")
        self.assertEqual(self.run_rule(self.workflow)["status"], "POLICY_IDENTITY_UNAVAILABLE")
        self.assertFalse(self.client.calls)

    def test_workflow_missing_suite_and_wrong_commit_ref(self):
        for field, value in (("after_sha", "f" * 40), ("ref", "refs/heads/other")):
            with self.subTest(field=field):
                self.client.rows["/rulesets/rule-suites"] = [{**self.suite, field: value}]
                self.assertEqual(self.run_rule(self.workflow)["status"], "EVALUATION_NOT_OBSERVED")

    def test_workflow_policy_newer_or_equal_is_not_current(self):
        for updated in (NOW, "2026-10-11T00:00:00Z"):
            self.client.objects["/rulesets/7"]["updated_at"] = updated
            self.assertEqual(self.run_rule(self.workflow)["status"], "POLICY_NEWER_THAN_EVALUATION")

    def test_real_ruleset_offset_fraction_timestamp(self):
        self.client.objects["/rulesets/7"]["updated_at"] = "2026-10-09T09:00:00.223+09:00"
        self.assertEqual(self.run_rule(self.workflow)["status"], "PASS")
        self.assertEqual(policy.timestamp("2026-10-10T09:00:00+09:00"), policy.timestamp(NOW))
        for invalid in ("2026-10-10T00:00:00", "2026-13-10T00:00:00Z", "2026-10-10T00:00:00+25:00"):
            with self.assertRaises(ValueError):
                policy.timestamp(invalid)

    def test_workflow_bypass_and_fail_not_pass(self):
        detail = self.client.objects["/rulesets/rule-suites/8"]
        detail["rule_evaluations"][0]["result"] = "fail"
        self.assertEqual(self.run_rule(self.workflow)["status"], "FAIL")
        self.suite["result"] = detail["result"] = "bypass"
        self.assertEqual(self.run_rule(self.workflow)["status"], "BYPASSED")

    def test_workflow_evaluate_mode_wrong_rule_and_duplicate(self):
        detail = self.client.objects["/rulesets/rule-suites/8"]
        match = detail["rule_evaluations"][0]
        match["enforcement"] = "evaluate"
        self.assertEqual(self.run_rule(self.workflow)["status"], "EVALUATION_NOT_OBSERVED")
        match["enforcement"] = "active"
        detail["rule_evaluations"].append(copy.deepcopy(match))
        self.assertEqual(self.run_rule(self.workflow)["status"], "QUERY_OR_VALIDATION_FAILED")

    def test_workflow_latest_failure_and_tie_not_cherry_picked(self):
        self.client.rows["/rulesets/rule-suites"].append({**self.suite, "id": 10})
        self.assertEqual(self.run_rule(self.workflow)["diagnostic"], "AMBIGUOUS_POLICY_RESOURCE_ORDER")

    def test_workflow_creation_exemption_and_future_parameters(self):
        self.workflow["parameters"]["do_not_enforce_on_create"] = True
        self.assertEqual(self.run_rule(self.workflow)["status"], "CREATION_EXEMPT_OR_UNVERIFIED")
        self.workflow["parameters"]["future_semantics"] = True
        self.assertEqual(self.run_rule(self.workflow)["diagnostic"], "UNKNOWN_WORKFLOW_POLICY_PARAMETERS")

    def test_workflow_policy_and_detail_change_detected(self):
        original = self.client.one
        count = {}
        def changing(path, **params):
            result = original(path, **params)
            count[path] = count.get(path, 0) + 1
            if path == "/rulesets/7" and count[path] == 2:
                result["updated_at"] = NOW
            return result
        self.client.one = changing
        self.assertEqual(self.run_rule(self.workflow)["diagnostic"], "WORKFLOW_POLICY_OR_EVALUATION_CHANGED")

    def test_scanning_analysis_and_empty_alerts_pass(self):
        row = self.run_rule(self.scan)
        self.assertEqual(row["status"], "PASS")
        self.assertFalse(row["tools"][0]["vulnerability_free_verified"])

    def test_scanning_missing_analysis_not_empty_success(self):
        self.client.rows["/code-scanning/analyses"] = []
        self.assertEqual(self.run_rule(self.scan)["tools"][0]["status"], "ANALYSIS_NOT_OBSERVED")

    def test_scanning_matrix_old_sha_error_warning_and_duplicate(self):
        for field, value, expected in (("commit_sha", "b" * 40, "ANALYSIS_REVISION_MISMATCH"),
                                        ("error", "failed", "ANALYSIS_FAILED"),
                                        ("warning", "incomplete", "ANALYSIS_WARNING")):
            self.client.rows["/code-scanning/analyses"] = [self.analysis,
                {**self.analysis, "id": 2, "category": "cpp", field: value}]
            self.assertEqual(self.run_rule(self.scan)["tools"][0]["status"], expected)
        self.client.rows["/code-scanning/analyses"] = [self.analysis, self.analysis]
        self.assertEqual(self.run_rule(self.scan)["status"], "QUERY_OR_VALIDATION_FAILED")

    def test_scanning_all_ordinary_thresholds(self):
        self.client.rows["/code-scanning/alerts"] = [self.alert]
        requirement = self.scan["parameters"]["code_scanning_tools"][0]
        for threshold, blocked in policy.ALERTS.items():
            requirement["alerts_threshold"] = threshold
            for severity in ("error", "warning", "note", "none"):
                self.alert["rule"]["severity"] = severity
                with self.subTest(threshold=threshold, severity=severity):
                    self.assertEqual(self.run_rule(self.scan)["status"], "BLOCKED" if severity in blocked else "PASS")

    def test_scanning_all_security_thresholds(self):
        self.client.rows["/code-scanning/alerts"] = [self.alert]
        requirement = self.scan["parameters"]["code_scanning_tools"][0]
        for threshold, blocked in policy.SECURITY.items():
            requirement["security_alerts_threshold"] = threshold
            for severity in ("critical", "high", "medium", "low"):
                self.alert["rule"]["security_severity_level"] = severity
                with self.subTest(threshold=threshold, severity=severity):
                    self.assertEqual(self.run_rule(self.scan)["status"], "BLOCKED" if severity in blocked else "PASS")

    def test_scanning_unknown_security_severity_not_ignored(self):
        self.alert["rule"]["tags"] = ["security"]
        self.client.rows["/code-scanning/alerts"] = [self.alert]
        self.assertEqual(self.run_rule(self.scan)["diagnostic"], "SECURITY_SEVERITY_UNAVAILABLE")

    def test_scanning_closed_historical_alert_not_current_open(self):
        self.alert["state"] = self.alert["most_recent_instance"]["state"] = "fixed"
        self.alert["most_recent_instance"]["commit_sha"] = "f" * 40
        self.client.rows["/code-scanning/alerts"] = [self.alert]
        self.assertEqual(self.run_rule(self.scan)["status"], "PASS")
        self.alert["most_recent_instance"]["state"] = "open"
        self.assertEqual(self.run_rule(self.scan)["diagnostic"], "SCANNING_ALERT_REVISION_MISMATCH")

    def test_scanning_candidate_sha_requires_reference_context(self):
        self.base["branch_sha"] = "f" * 40
        self.assertEqual(self.run_rule(self.scan)["status"], "REFERENCE_CONTEXT_REQUIRED")
        self.assertFalse(self.client.calls)

    def test_scanning_changed_upload_detected(self):
        original = self.client.pages
        count = 0
        def changing(path, **params):
            nonlocal count
            rows = original(path, **params)
            if path.endswith("/analyses"):
                count += 1
                if count == 2:
                    rows[0]["id"] = 100
            return rows
        self.client.pages = changing
        self.assertEqual(self.run_rule(self.scan)["diagnostic"], "SCANNING_ANALYSIS_CHANGED_DURING_QUERY")

    def test_deployment_exact_environment_and_sha(self):
        row = self.run_rule(self.deploy)
        self.assertEqual(row["status"], "PASS")
        self.assertFalse(row["serving_currently_verified"])
        self.assertEqual(self.client.calls[0][1], {"sha": SHA, "environment": "staging"})

    def test_deployment_missing_and_no_status(self):
        self.client.rows["/deployments/4/statuses"] = []
        self.assertEqual(self.run_rule(self.deploy)["environments"][0]["status"], "PENDING")
        self.client.rows["/deployments"] = []
        self.assertEqual(self.run_rule(self.deploy)["environments"][0]["status"], "MISSING")

    def test_deployment_all_states_and_unknown(self):
        for state in ("failure", "error", "pending", "queued", "in_progress", "inactive", "invented"):
            self.status["state"] = state
            self.assertNotEqual(self.run_rule(self.deploy)["status"], "PASS")

    def test_deployment_wrong_sha_environment_and_url(self):
        self.deployment["sha"] = "f" * 40
        self.assertEqual(self.run_rule(self.deploy)["status"], "QUERY_OR_VALIDATION_FAILED")
        self.deployment["sha"] = SHA
        self.status["deployment_url"] = "https://example.invalid/deployment"
        self.assertEqual(self.run_rule(self.deploy)["status"], "QUERY_OR_VALIDATION_FAILED")

    def test_deployment_newer_retry_cannot_expose_old_pass(self):
        self.status["created_at"] = OLD
        self.client.rows["/deployments/4/statuses"].append({**self.status, "id": 6, "created_at": NOW, "state": "pending"})
        self.assertEqual(self.run_rule(self.deploy)["status"], "BLOCKED")

    def test_deployment_all_environments_required(self):
        self.deploy["parameters"]["required_deployment_environments"].append("production")
        # Fake provider must respect its filters just like GitHub; a mismatched
        # response blocks instead of counting staging as production.
        self.assertEqual(self.run_rule(self.deploy)["status"], "QUERY_OR_VALIDATION_FAILED")

    def test_access_failures_are_per_rule_and_retry_preserved(self):
        self.client.rows["/code-scanning/analyses"] = gh.APIError("HTTP_403", 600)
        row = self.run_rule(self.scan)
        self.assertEqual(row["diagnostic"], "HTTP_403")
        self.assertEqual(row["retry_after"], 600)
        self.assertFalse(row["evaluation_complete"])
        self.assertEqual(self.run_rule(self.deploy)["status"], "PASS")

    def test_invalid_policy_parameters_fail_closed(self):
        for rule in ({"type": "code_scanning", "parameters": {}},
                     {"type": "required_deployments", "parameters": {"required_deployment_environments": []}},
                     {"type": "workflows", "parameters": {"workflows": []}}):
            self.assertEqual(self.run_rule(rule)["status"], "QUERY_OR_VALIDATION_FAILED")

    def test_pending_attempt_blocks_previous_domain_pass(self):
        base = {**self.base, "other_rules": [self.scan]}
        for state in ("queued", "in_progress", "waiting", "requested", "pending"):
            row = policy.collect(self.client, base, SHA, "main", checks=[{"id": 101, "status": state}])[0]
            self.assertEqual(row["status"], "EXECUTION_PENDING")
            self.assertEqual(row["pending_check_ids"], [101])
            self.assertEqual(row["observed_domain_status"], "PASS")

    def test_deployment_changed_status_detected(self):
        original = self.client.pages
        count = 0
        def changing(path, **params):
            nonlocal count
            rows = original(path, **params)
            if path.endswith("/statuses"):
                count += 1
                if count == 2:
                    rows[0]["state"] = "failure"
            return rows
        self.client.pages = changing
        self.assertEqual(self.run_rule(self.deploy)["diagnostic"], "REQUIRED_DEPLOYMENT_CHANGED_DURING_QUERY")


class Integration(unittest.TestCase):
    git = fixtures.State.git
    setUp = fixtures.State.setUp
    git_commit = fixtures.State.git_commit
    work = fixtures.State.work
    setup_state = fixtures.State.setup_state
    cycle = fixtures.State.cycle

    def test_snapshot_domain_failure_not_unsupported_or_empty(self):
        rule = {"type": "required_deployments", "parameters": {"required_deployment_environments": ["staging"]}}
        self.setup_state()
        result = self.cycle(fixtures.Fixture(self.git_commit(), rules=[rule]))
        required = result["required_checks"]
        self.assertEqual(required["status"], "BLOCKED")
        self.assertTrue(required["evaluation_complete"])
        self.assertEqual(required["requirements"][0]["environments"][0]["status"], "MISSING")

    def test_result_binding_cannot_substitute_another_policy(self):
        with self.assertRaises(ValueError):
            gh.evaluate({"checks": [], "workflows": [], "other_rules": []}, [], [], SHA,
                        [{"rule": {"type": "code_scanning"}, "status": "PASS"}])

    def test_domain_query_failure_preserves_retry_and_persisted_backoff(self):
        rule = {"type": "required_deployments", "parameters": {"required_deployment_environments": ["staging"]}}
        self.setup_state()
        fixture = fixtures.Fixture(self.git_commit(), rules=[rule])
        original = fixture.pages
        def pages(path, key=None, **params):
            if path == "/deployments" and params:
                raise gh.APIError("HTTP_429", 900)
            return original(path, key, **params)
        fixture.pages = pages
        result = self.cycle(fixture)
        self.assertTrue(result["required_checks"]["policy_evidence_failed"])
        self.assertGreaterEqual(result["required_checks"]["recommended_interval"], 900)
        self.assertEqual(fixtures.io.read_json(self.state / "latest.json")["consecutive_failures"], 1)


if __name__ == "__main__":
    unittest.main()
