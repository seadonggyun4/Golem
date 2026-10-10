"""Revision joins, provider snapshots and native authority boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import agent_io as io
import revision_status as rs
import test_agent_io


class RevisionStatus(unittest.TestCase):
    git = test_agent_io.AgentIO.git
    plan = test_agent_io.AgentIO.plan
    run_plan = test_agent_io.AgentIO.run_plan
    work = {"project_id": "project", "work_id": "work"}

    def setUp(self):
        test_agent_io.AgentIO.setUp(self)
        self.git("remote", "add", "origin", "https://github.com/owner/repo.git")
        self.index = {"schema": rs.SCHEMA, "repository": "owner/repo", "binding": self.work, "entries": []}

    def add(self, channel="local_qa", adapter="command.v1", data=None, scope="suite", script=None):
        script = script or (f"print({json.dumps(data)!r})" if data is not None else "print('ok')")
        bundle = self.run_plan(self.plan(script), {**self.work, "selection": scope})
        entry = {"id": f"evidence-{self.count}", "channel": channel, "adapter": adapter,
                 "bundle": str(bundle), "revision": io.digest(bundle / "record.json"),
                 "step": "check", "scope": scope}
        self.index["entries"].append(entry)
        return bundle

    def view(self):
        return rs.projection(self.index, self.source)

    def run_response(self, **changes):
        return {"id": 10, "run_attempt": 1, "workflow_id": 20,
                "repository": {"full_name": "owner/repo"},
                "head_sha": self.git_commit(), "html_url": "https://github.com/owner/repo/actions/runs/10",
                "status": "completed", "conclusion": "success", **changes}

    def git_commit(self):
        return rs.records.git(self.source, "rev-parse", "HEAD").decode().strip()

    def completion(self, **changes):
        return {"schema_version": 1, "action": "DONE", "execution_authorized": False,
                "acceptance_verified": True, "selection": {"document_id": "selection"},
                "receipt_digest": "a" * 64, "completion": {"record": {"evidence_root": "b" * 64}}, **changes}

    def test_empty_index_does_not_claim_completion(self):
        result = self.view()
        self.assertTrue(all(c["status"] == "NOT_OBSERVED" for c in result["channels"].values()))
        self.assertFalse(result["native_acceptance_verified"])
        self.assertEqual(result["overall_completion"], "NOT_INFERRED")

    def test_exit_zero_not_semantic_pass(self):
        self.add()
        self.assertEqual(self.view()["channels"]["local_qa"]["status"], "OBSERVED_EXIT_OK")

    def test_local_dirty_tree_changes_invalidate_same_commit(self):
        self.add()
        (self.source / "new.txt").write_text("uncommitted")
        channel = self.view()["channels"]["local_qa"]
        self.assertEqual(channel["status"], "NO_CURRENT_EVIDENCE")
        self.assertEqual(channel["evidence"][0]["source_relation"], "STALE")

    def test_junit_pass_failed_skipped_and_empty(self):
        for xml, expected in (("<testsuite tests='1'><testcase/></testsuite>", "PASS"),
                              ("<testsuite><testcase><failure/></testcase></testsuite>", "FAIL"),
                              ("<testsuite><testcase><skipped/></testcase></testsuite>", "PARTIAL"),
                              ("<testsuite/>", "NOT_RUN")):
            self.index["entries"] = []
            self.add(adapter="junit.v1", script=f"print({xml!r})")
            self.assertEqual(self.view()["channels"]["local_qa"]["status"], expected)

    def test_junit_counter_lie_and_entities_rejected(self):
        for xml in (b"<testsuite tests='2'><testcase/></testsuite>",
                    b"<!DOCTYPE a [<!ENTITY x 'oops'>]><testsuite/>"):
            with self.assertRaises(ValueError):
                rs.junit(xml)

    def test_remote_success_is_not_latest_or_native_completion(self):
        self.add("remote_ci", "github-run.v1", self.run_response(), "20")
        result = self.view()
        self.assertEqual(result["channels"]["remote_ci"]["status"], "PASS")
        self.assertFalse(result["remote_latest_verified"])
        self.assertFalse(result["native_acceptance_verified"])

    def test_remote_same_commit_does_not_cover_dirty_source(self):
        self.add("remote_ci", "github-run.v1", self.run_response(), "20")
        (self.source / "new.txt").write_text("dirty")
        result = self.view()["channels"]["remote_ci"]
        self.assertEqual(result["status"], "NO_CURRENT_EVIDENCE")
        self.assertEqual(result["evidence"][0]["source_relation"], "COMMIT_ONLY_DIRTY_SOURCE")

    def test_other_commit_and_repository_rejected_or_stale(self):
        self.add("remote_ci", "github-run.v1", self.run_response(head_sha="f" * 40), "20")
        self.assertEqual(self.view()["channels"]["remote_ci"]["status"], "NO_CURRENT_EVIDENCE")
        self.add("remote_ci", "github-run.v1", self.run_response(repository={"full_name": "fork/repo"}), "20")
        self.assertEqual(self.view()["channels"]["remote_ci"]["status"], "INVALID_EVIDENCE")

    def test_ci_pending_cancelled_neutral_not_pass(self):
        for changes, expected in (({"status": "in_progress", "conclusion": None}, "PENDING"),
                                  ({"conclusion": "cancelled"}, "CANCELLED"),
                                  ({"conclusion": "neutral"}, "NEUTRAL")):
            self.assertEqual(rs.github_run(self.run_response(**changes), "owner/repo", "20")[0], expected)

    def test_same_revision_conflicting_runs_never_choose_pass(self):
        self.add("remote_ci", "github-run.v1", self.run_response(), "20")
        self.add("remote_ci", "github-run.v1", self.run_response(conclusion="failure"), "20")
        self.assertEqual(self.view()["channels"]["remote_ci"]["status"], "CONFLICT")

    def test_historical_native_done_requires_live_revalidation(self):
        self.add("completion", "native-completion.v1", self.completion(), "selection")
        result = self.view()
        self.assertEqual(result["channels"]["completion"]["status"], "REVALIDATE_REQUIRED")
        self.assertFalse(result["native_acceptance_verified"])

    def test_native_response_inconsistency_rejected(self):
        for response in (self.completion(acceptance_verified=False), self.completion(receipt_digest=""),
                         self.completion(selection={"document_id": "different"})):
            with self.assertRaises(ValueError):
                rs.native_completion(response, "selection")

    def test_deployment_inactive_and_identity_checks(self):
        url = "https://api.github.com/repos/owner/repo/deployments/10"
        data = {"deployment": {"id": 10, "url": url, "sha": self.git_commit(), "environment": "production"},
                "status": {"id": 30, "url": url + "/statuses/30", "deployment_url": url,
                           "environment": "production", "state": "inactive"}}
        self.add("deployment", "github-deployment.v1", data, "production")
        self.assertEqual(self.view()["channels"]["deployment"]["status"], "INACTIVE")
        data["status"]["deployment_url"] += "-wrong"
        with self.assertRaises(ValueError):
            rs.github_deployment(data, "owner/repo", "production")

    def test_tampering_and_bad_revision_keeps_other_channels(self):
        bundle = self.add()
        self.add("remote_ci", "github-run.v1", self.run_response(), "20")
        (bundle / "check/stdout.log").write_text("corrupt")
        result = self.view()
        self.assertEqual(result["channels"]["local_qa"]["status"], "INVALID_EVIDENCE")
        self.assertEqual(result["channels"]["remote_ci"]["status"], "PASS")

    def test_target_changed_during_projection_blocks_native(self):
        target = rs.target_source(self.source, "owner/repo")
        with patch.object(rs, "target_source", side_effect=[target, {**target, "dirty": True}]):
            result = self.view()
        self.assertFalse(result["source_stable"])
        self.assertFalse(result["native_acceptance_verified"])

    def test_fresh_query_pin_cannot_survive_source_change_before_projection(self):
        target = rs.target_source(self.source, "owner/repo")
        fresh = {"channel": "completion", "source_relation": "CURRENT", "status": "PASS",
                 "freshness": "LIVE_NATIVE_QUERY", "source_pin": target}
        (self.source / "changed.txt").write_text("new revision")
        result = rs.projection(self.index, self.source, fresh)
        self.assertFalse(result["native_acceptance_verified"])

    def test_evidence_wrong_revision_work_and_missing_bundle(self):
        self.add()
        self.index["entries"][0]["revision"] = "0" * 64
        self.assertEqual(self.view()["channels"]["local_qa"]["status"], "INVALID_EVIDENCE")
        self.index["entries"][0]["bundle"] = str(self.root / "missing")
        self.assertEqual(self.view()["channels"]["local_qa"]["status"], "INVALID_EVIDENCE")

    def test_source_mutation_during_command_is_not_current_evidence(self):
        self.add(script="from pathlib import Path; Path('mutated.txt').write_text('changed')")
        channel = self.view()["channels"]["local_qa"]
        self.assertEqual(channel["status"], "NO_CURRENT_EVIDENCE")
        self.assertEqual(channel["evidence"][0]["source_relation"], "CHANGED_DURING_EXECUTION")

    def test_origin_and_invalid_adapter_contract(self):
        self.git("remote", "set-url", "origin", "https://github.com/fork/repo.git")
        with self.assertRaises(ValueError):
            self.view()
        self.add()
        self.index["entries"][0]["adapter"] = "unknown"
        with self.assertRaises(ValueError):
            rs.validate(self.index)

    def test_cli_read_only_projection(self):
        self.add()
        path = self.root / "index.json"
        io.save(path, io.encoded(self.index))
        result = subprocess.run([sys.executable, rs.__file__, str(path), "--cwd", str(self.source)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(io.strict_json(result.stdout)["execution_authorized"])

    def test_process_failure_not_pass_and_preserves_reason(self):
        self.add(script="raise SystemExit(7)")
        channel = self.view()["channels"]["local_qa"]
        self.assertEqual(channel["status"], "PROCESS_FAILED")
        self.assertEqual(channel["evidence"][0]["process"]["returncode"], 7)

    def test_cli_live_arguments_must_be_complete(self):
        path = self.root / "index.json"
        io.save(path, io.encoded(self.index))
        result = subprocess.run([sys.executable, rs.__file__, str(path), "--cwd", str(self.source),
                                 "--selection", "selection"], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires", io.strict_json(result.stderr)["diagnostic"])

    def test_malformed_provider_state_and_index_bounds(self):
        with self.assertRaises(ValueError):
            rs.github_run(self.run_response(status="in_progress"), "owner/repo", "20")
        self.add()
        self.index["entries"] *= 129
        with self.assertRaises(ValueError):
            rs.validate(self.index)

    def test_failed_deployment_is_not_discarded(self):
        url = "https://api.github.com/repos/owner/repo/deployments/10"
        data = {"deployment": {"id": 10, "url": url, "sha": self.git_commit(), "environment": "prod"},
                "status": {"id": 30, "url": url + "/statuses/30", "deployment_url": url,
                           "environment": "prod", "state": "failure"}}
        self.add("deployment", "github-deployment.v1", data, "prod")
        self.assertEqual(self.view()["channels"]["deployment"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
