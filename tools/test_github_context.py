"""Candidate scope, ref movement and provider provenance regressions."""
import copy
import unittest

import github_context as context
import github_policy as policy
import test_github_policy as fixtures
from test_github_policy import Provider, SHA


HEAD = "b" * 40
MERGE = "c" * 40


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.c = Provider()
        self.c.base = "https://api.github.com/repos/o/r"
        self.pr = {"kind": "pull_request", "number": 1, "ref_mode": "merge"}
        self.c.objects["/pulls/1"] = {"number": 1, "state": "open", "merged": False,
            "base": {"ref": "main", "sha": SHA, "repo": {"full_name": "o/r"}},
            "head": {"sha": HEAD, "repo": {"id": 2}}, "merge_commit_sha": MERGE}
        self.c.objects["/git/commits/" + MERGE] = {"sha": MERGE,
            "parents": [{"sha": SHA}, {"sha": HEAD}]}
        self.set_ref("refs/pull/1/merge", MERGE)
        self.set_ref("refs/pull/1/head", HEAD)
        self.set_ref("refs/heads/main", SHA)
        self.queue_ref = "refs/heads/gh-readonly-queue/main/pr-1-test"
        self.queue = {"kind": "merge_group", "run_id": 10, "head_ref": self.queue_ref,
                      "head_sha": MERGE, "base_sha": SHA}
        self.set_ref(self.queue_ref, MERGE)
        self.c.objects["/actions/runs/10"] = {"id": 10, "event": "merge_group",
            "head_sha": MERGE, "head_branch": self.queue_ref.removeprefix("refs/heads/"),
            "repository": {"full_name": "o/r"}, "run_attempt": 1}
        self.c.objects[f"/compare/{SHA}...{MERGE}"] = {
            "status": "ahead", "merge_base_commit": {"sha": SHA}}

    def set_ref(self, ref, sha):
        self.c.objects["/git/ref/" + ref.removeprefix("refs/")] = {
            "ref": ref, "object": {"type": "commit", "sha": sha}}

    def test_pr_head_and_merge_are_distinct(self):
        self.assertEqual(context.resolve(self.c, self.pr, "main", SHA)["sha"], MERGE)
        self.pr["ref_mode"] = "head"
        self.assertEqual(context.resolve(self.c, self.pr, "main", SHA)["sha"], HEAD)

    def test_pr_null_merge_metadata_uses_verified_ref_and_parents(self):
        self.c.objects["/pulls/1"]["merge_commit_sha"] = None
        self.assertEqual(context.resolve(self.c, self.pr, "main", SHA)["sha"], MERGE)

    def test_pr_closed_moved_base_or_forged_merge(self):
        original = copy.deepcopy(self.c.objects)
        for mutation in (lambda: self.c.objects["/pulls/1"].update(state="closed"),
                         lambda: self.c.objects["/pulls/1"]["base"].update(sha=HEAD),
                         lambda: self.c.objects["/git/commits/" + MERGE]["parents"].reverse(),
                         lambda: self.set_ref("refs/pull/1/merge", HEAD)):
            self.c.objects = copy.deepcopy(original)
            mutation()
            with self.assertRaises(ValueError):
                context.resolve(self.c, self.pr, "main", SHA)

    def test_queue_requires_provider_event_identity_and_ancestry(self):
        result = context.resolve(self.c, self.queue, "main", SHA)
        self.assertEqual(result["ref"], self.queue_ref)
        self.assertFalse(result["current_merge_authorized"])
        for key, value in (("event", "push"), ("head_sha", HEAD), ("head_branch", "main")):
            old = self.c.objects["/actions/runs/10"][key]
            self.c.objects["/actions/runs/10"][key] = value
            with self.assertRaises(ValueError):
                context.resolve(self.c, self.queue, "main", SHA)
            self.c.objects["/actions/runs/10"][key] = old
        self.c.objects[f"/compare/{SHA}...{MERGE}"]["status"] = "diverged"
        with self.assertRaises(ValueError):
            context.resolve(self.c, self.queue, "main", SHA)

    def test_invalid_scope_and_ref(self):
        for value in ({}, {**self.pr, "extra": True}, {**self.pr, "number": True},
                      {**self.queue, "head_ref": "refs/heads/../x"}):
            with self.assertRaises(ValueError):
                context.validate(value)

    def test_scanning_uses_scoped_instances_not_repository_latest(self):
        fixture = fixtures.Domain(); fixture.setUp()
        self.c.rows = fixture.client.rows
        analysis = self.c.rows["/code-scanning/analyses"][0]
        analysis.update(commit_sha=MERGE, ref="refs/pull/1/merge")
        self.c.rows["/code-scanning/alerts"] = [fixture.alert]
        path = "/code-scanning/alerts/1/instances"
        self.c.rows[path] = [{"ref": "refs/pull/1/merge", "commit_sha": MERGE, "state": "open"}]
        base = {**fixture.base, "candidate_context": self.pr}
        result = policy.scanning_rule(self.c, fixture.scan, MERGE, "main", base)
        self.assertEqual(result["status"], "BLOCKED")
        self.c.rows[path][0]["state"] = "fixed"
        self.assertEqual(policy.scanning_rule(self.c, fixture.scan, MERGE, "main", base)["status"], "PASS")
        self.c.rows[path][0]["commit_sha"] = HEAD
        with self.assertRaises(ValueError):
            policy.scanning_rule(self.c, fixture.scan, MERGE, "main", base)

    def test_scanning_revalidates_candidate_after_queries(self):
        fixture = fixtures.Domain(); fixture.setUp()
        self.c.rows = fixture.client.rows
        self.c.rows["/code-scanning/analyses"][0].update(commit_sha=MERGE, ref="refs/pull/1/merge")
        original = self.c.one
        reads = 0
        def moving(path, **params):
            nonlocal reads
            if path == "/pulls/1":
                reads += 1
                if reads == 2:
                    self.c.objects[path]["base"]["sha"] = HEAD
            return original(path, **params)
        self.c.one = moving
        with self.assertRaises(ValueError):
            policy.scanning_rule(self.c, fixture.scan, MERGE, "main",
                                 {**fixture.base, "candidate_context": self.pr})

    def test_queue_scanning_requires_exact_queue_analysis(self):
        fixture = fixtures.Domain(); fixture.setUp()
        self.c.rows = fixture.client.rows
        analysis = self.c.rows["/code-scanning/analyses"][0]
        analysis.update(commit_sha=MERGE, ref=self.queue_ref)
        base = {**fixture.base, "candidate_context": self.queue}
        result = policy.scanning_rule(self.c, fixture.scan, MERGE, "main", base)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["candidate"]["queue_membership_verified"])
        analysis["ref"] = "refs/heads/main"
        with self.assertRaises(ValueError):
            policy.scanning_rule(self.c, fixture.scan, MERGE, "main", base)

    def test_candidate_base_ref_movement_invalidates_old_context(self):
        self.set_ref("refs/heads/main", HEAD)
        for scope in (self.pr, self.queue):
            with self.assertRaises(ValueError):
                context.resolve(self.c, scope, "main", SHA)


if __name__ == "__main__":
    unittest.main()
