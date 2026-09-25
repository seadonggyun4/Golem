"""Pinned review identity, real QA freshness and historical projection tests."""
import json
import subprocess
import unittest
from pathlib import Path

from candidate_integration import Candidates, Changes, ENV


class CandidateDiff(Candidates):
    def configure(self, *args, **kwargs):
        kwargs.setdefault("mode", "real")
        return super().configure(*args, **kwargs)

    def ready_diff(self, version=4, extra=None, dirty=False, maximum=5, rename=False):
        self.setup_candidates(count=1, actual=True, version=version)
        self.repo = Path(self.members[0]["tree"])
        self.contract["snapshot_plan"]["repositories"][0]["root"] = str(self.repo)
        self.contract["snapshot_plan"]["repositories"][0]["change_policy"]["limit"]["max_changed_paths"] = maximum
        if rename:
            # Declared mandatory input files must remain readable. user.txt is
            # not an oracle here; leave it covered by the full inventory only.
            self.contract["snapshot_plan"]["repositories"][0]["paths"].remove("user.txt")
        self.approval = self.raw("execution", "validate", self.write("candidate-contract.json", self.contract)).strip()
        if dirty:
            (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; } /* dirty */\n")
        self.prepare()
        self.manifest["gates_digest"] = self.raw("candidate", "gates", self.work, self.cp["receipt_digest"]).strip()
        self.register()
        token = self.launch("a")
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        if extra:
            extra()
        self.finish()
        qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="candidate-qa")
        self.assertEqual(qa["record"]["status"], "PASS")
        self.settle("a", token, qa=qa["receipt_digest"])
        self.rpc("$seal", candidate="a")
        return qa

    def review(self, digest, **fields):
        return self.command("review", "a", diff=digest, qa="", decision="PASS", reviewer="reviewer", **fields)

    def test_review_sealed_diff_and_live_freshness(self):
        self.ready_diff()
        key = self.command("diff-seal", "a", redaction="source")["digest"]
        self.assertEqual(key, self.command("diff-seal", "a", redaction="source")["digest"])
        diff = self.command("diff", "a")
        self.assertTrue(diff["complete"], diff)
        change = next(c for c in diff["changes"] if bytes.fromhex(c["path_hex"]) == b"logic.c")
        self.assertIn(b"a-b", bytes.fromhex(change["before_hex"]))
        self.assertIn(b"a+b", bytes.fromhex(change["after_hex"]))
        self.command("select", "a", ok=False)
        self.review("0" * 64, ok=False)
        self.review(key)
        self.command("review-check", "a")
        self.command("review", "a", diff=key, qa="", decision="FAIL", reviewer="reviewer")
        self.command("review-check", "a", ok=False)
        self.review(key)
        self.assertEqual(self.command("compare")["decision"], "SOLE_PASS")
        self.command("select", "a")
        (self.repo / "logic.c").write_text("changed after review\n")
        self.command("review-check", "a", ok=False)
        self.assertEqual(self.command("compare")["decision"], "INCOMPARABLE")
        self.assertEqual(diff, self.command("diff", "a"))
        self.stop_host()
        # Registered tree can disappear; historical reads neither resolve it nor execute Git.
        self.repo.rename(self.repo.with_name("moved-for-history"))
        self.assertEqual(diff, json.loads(self.raw("candidate", "diff", self.parent, "group", "a")))
        self.raw("candidate", "diff", self.parent, "group", "../a", ok=False)

    def test_metadata_and_resealed_projection_invalidate_review(self):
        self.ready_diff(version=5)
        key = self.command("diff-seal", "a", redaction="source")["digest"]
        self.review(key)
        redacted = self.command("diff-seal", "a", redaction="metadata")["digest"]
        self.assertNotEqual(key, redacted)
        projection = self.command("diff", "a")
        self.assertFalse(projection["complete"])
        self.assertTrue(all(not row["path_hex"] and row["before"] is None for row in projection["changes"]))
        self.review(redacted, ok=False)
        self.command("review-check", "a", ok=False)
        self.command("select", "a", ok=False)

    def test_missing_preimage_is_not_fabricated(self):
        self.ready_diff(dirty=True)
        key = self.command("diff-seal", "a", redaction="source")["digest"]
        projection = self.command("diff", "a")
        self.assertFalse(projection["complete"])
        self.review(key, ok=False)

    def test_bounded_large_content_is_not_full_review(self):
        self.ready_diff(extra=lambda: (self.repo / "large.txt").write_text("x" * 18000))
        key = self.command("diff-seal", "a", redaction="source")["digest"]
        projection = self.command("diff", "a")
        self.assertFalse(projection["complete"])
        self.assertTrue(projection["truncated"])
        self.review(key, ok=False)

    def test_host_denial_and_request_injection(self):
        self.ready_diff()
        self.command("diff-seal", "a", redaction="source", path="/etc/passwd", ok=False)
        self.command("diff-seal", "a", redaction="source", revision="HEAD", ok=False)
        self.rpc("$deny", value=True)
        self.command("diff-seal", "a", redaction="source", ok=False)
        self.command("diff", "a", ok=False)

    def test_binary_rename_mode_symlink_and_external_driver(self):
        marker = self.root / "external-driver-ran"
        def changes():
            self.git("config", "diff.evil.command", "touch " + str(marker))
            self.git("config", "diff.evil.textconv", "touch " + str(marker))
            (self.repo / ".gitattributes").write_text("* diff=evil\n")
            (self.repo / "user.txt").rename(self.repo / "renamed.txt")
            (self.repo / "logic.c").chmod(0o755)
            (self.repo / "binary").write_bytes(b"\x00\xff\x1b[2J")
            (self.repo / "link").symlink_to("/outside/never-follow-this")
        self.ready_diff(extra=changes, maximum=8, rename=True)
        key = self.command("diff-seal", "a", redaction="source")["digest"]
        diff = self.command("diff", "a")
        self.assertTrue(diff["complete"], diff)
        rows = {bytes.fromhex(r["path_hex"]).decode(): r for r in diff["changes"]}
        self.assertEqual(rows["user.txt"]["change"], "DELETE")
        self.assertEqual(rows["renamed.txt"]["change"], "ADD")
        self.assertEqual(rows["logic.c"]["after"]["worktree"]["mode"], "100755")
        self.assertEqual(bytes.fromhex(rows["binary"]["after_hex"]), b"\x00\xff\x1b[2J")
        self.assertEqual(bytes.fromhex(rows["link"]["after_hex"]), b"/outside/never-follow-this")
        self.assertFalse(marker.exists())
        self.review(key)

    def test_truncated_inventory_and_corrupt_projection(self):
        def changes():
            for i in range(65):
                (self.repo / f"new-{i}").write_text("x")
        self.ready_diff(version=5, extra=changes, maximum=80)
        key = self.command("diff-seal", "a", redaction="source")["digest"]
        diff = self.command("diff", "a")
        self.assertTrue(diff["truncated"])
        self.assertFalse(diff["complete"])
        self.assertEqual(diff["changed_files"], 66)
        self.review(key, ok=False)
        self.stop_host()
        path = self.parent / "objects/sha256" / key[:2] / key[2:]
        path.chmod(0o600)
        path.write_text("{}")
        self.raw("candidate", "diff", self.parent, "group", "a", ok=False)

    def test_target_needs_its_own_exact_qa_review(self):
        self.ready_diff()
        key = self.command("diff-seal", "a", redaction="source")["digest"]
        self.review(key)
        self.command("select", "a")
        target = Changes("runTest")
        target.setUp()
        try:
            target.work_id = "target-work"
            target.configure(mode="real")
            target.repo = target.root / "target-repo"
            subprocess.run(["/usr/bin/git", "clone", "--quiet", "--no-hardlinks",
                            str(self.original_repo), str(target.repo)], check=True, env=ENV)
            target.contract["snapshot_plan"]["repositories"][0]["root"] = str(target.repo)
            target.approval = target.raw("execution", "validate", target.write("target.json", target.contract)).strip()
            target.prepare()
            (target.repo / "logic.c").write_bytes((self.repo / "logic.c").read_bytes())
            target.finish()
            qa = target.call("run", checkpoint=target.cp["receipt_digest"], attempt_id="target-qa")["receipt_digest"]
            self.rpc("$target", binding=dict(work=str(target.work), tree=str(target.repo), environment="e" * 64))
            self.command("target-check", "a", qa=qa, ok=False)
            self.command("review", "a", diff=key, qa=qa, decision="PASS", reviewer="target-reviewer")
            self.command("target-check", "a", qa=qa)
            newer = target.call("run", checkpoint=target.cp["receipt_digest"], attempt_id="target-qa-2")["receipt_digest"]
            self.assertNotEqual(newer, qa)
            self.command("target-check", "a", qa=newer, ok=False)
            self.command("review", "a", diff=key, qa=newer, decision="PASS", reviewer="target-reviewer")
            self.command("target-check", "a", qa=newer)
            (target.repo / "after-review").write_text("stale")
            self.command("target-check", "a", qa=newer, ok=False)
        finally:
            target.tearDown()


def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite(CandidateDiff(name) for name in sorted(CandidateDiff.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
