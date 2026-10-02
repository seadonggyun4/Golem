"""Growing two-stream history must not reuse a shifting combined offset."""
import subprocess
import sys
import unittest
from work_record_integration import Record
import workflow_integration as fixture
sys.path.insert(0, str(fixture.SOURCE / "tools"))
import agent_io


class History(Record):
    def page(self, cursor=None, limit=256, ok=True):
        return self.cli("work", "history", self.work, self.write("poll.json", dict(
            schema_version=2, work_id="example-work", limit=limit, cursor=cursor)), ok=ok)

    def start(self):
        self.register_selection()
        self.cli("session", "call", self.work, self.write("start.json", dict(
            schema_version=1, operation="start", work_id="example-work", key="start",
            expected_sequence=0, selection_id="selection")))

    def test_poll_empty_delta_and_append_in_both_streams(self):
        self.prepare()
        before = self.inventory()
        first = self.page()
        self.assertEqual(first["mode"], "FULL")
        self.assertFalse(first["has_more"])
        empty = self.page(first["cursor"])
        self.assertEqual(empty["mode"], "DELTA")
        self.assertEqual(empty["events"], [])
        self.assertEqual(before, self.inventory())
        self.start()
        delta = self.page(first["cursor"])
        self.assertEqual(delta["mode"], "DELTA")
        self.assertEqual({e["stream"] for e in delta["events"]}, {"document", "agent"})
        self.assertFalse(delta["execution_authorized"])
        self.assertEqual(delta, self.page(first["cursor"]))

    def test_paging_while_document_stream_grows_does_not_skip_agent_events(self):
        self.prepare()
        self.start()
        self.cli("session", "call", self.work, self.write("claim.json", dict(
            schema_version=1, operation="claim", work_id="example-work", key="claim",
            expected_sequence=1, session_id="fixture", expected_generation=self.generation,
            source_snapshot=self.source, byte_budget=16777216, ttl_ms=300000)))
        first = self.page(limit=1)
        self.assertEqual(len(first["events"]), 2)
        self.assertLess(first["cursor"]["agent_sequence"], first["agent_total"])
        self.assertTrue(first["has_more"])
        self.managed("planning")
        pages = [first]
        while pages[-1]["has_more"]:
            self.assertLess(len(pages), 20)
            pages.append(self.page(pages[-1]["cursor"], limit=1))
        rows = [e for p in pages for e in p["events"]]
        key = lambda e: (e["stream"], e["sequence"])
        self.assertEqual(len({key(e) for e in rows}), len(rows))
        self.assertEqual(sorted(rows, key=key), sorted(self.page()["events"], key=key))
        self.assertEqual(self.page(pages[-1]["cursor"])["events"], [])

    def test_invalid_unknown_cross_work_and_wrong_prefix_reset_explicitly(self):
        self.prepare()
        first = self.page()
        bad = [False, "untrusted", {}, {**first["cursor"], "schema_version": 99}]
        for field, value in (("document_head", "a" * 64), ("agent_head", "b" * 64),
                             ("document_sequence", 10000), ("agent_sequence", True),
                             ("work_id", "another"), ("work_anchor", "c" * 64)):
            bad.append({**first["cursor"], field: value})
        for cursor in bad:
            with self.subTest(cursor=cursor):
                result = self.page(cursor)
                self.assertEqual(result["mode"], "FULL")
                self.assertTrue(result["fallback"])
                self.assertEqual(result["events"], first["events"])

    def test_corrupt_current_prefix_never_becomes_full_success(self):
        self.prepare()
        first = self.page()
        event = next(self.work.rglob("00000001.evt"))
        event.chmod(0o600)
        event.write_bytes(b"broken")
        self.assertEqual(self.page(first["cursor"], ok=False).stdout, b"")

    def test_limits_and_legacy_paging_contract(self):
        self.prepare()
        for limit in (0, True, 257, -1):
            self.assertEqual(self.page(limit=limit, ok=False).stdout, b"")
        old = dict(schema_version=1, work_id="example-work", after=0, limit=256,
                   document_head="", agent_head="")
        baseline = self.cli("work", "history", self.work, self.write("old.json", old))
        self.assertEqual(self.page()["events"], baseline["events"])
        self.start()
        old.update(after=baseline["next_after"], document_head=baseline["document_head"],
                   agent_head=baseline["agent_head"])
        self.cli("work", "history", self.work, self.write("old.json", old), ok=False)

    def test_recorded_observer_resumes_only_hash_pinned_evidence(self):
        self.prepare()
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True, env=fixture.ENV)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
                        "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture"],
                       check=True, env=fixture.ENV)
        scope = dict(cli=str(fixture.CLI), work=str(self.work), work_id="example-work", query="history-v2")
        previous = None
        for i in range(3):
            output = agent_io.private_directory(self.root / f"observation-{i}")
            revision = agent_io.digest(previous / "record.json") if previous else None
            plan = agent_io.history_plan(fixture.CLI, self.work, "example-work", output,
                                         "code", scope, previous, revision if i != 2 else "0" * 64)
            agent_io.run(plan, repo, output, scope)
            result = agent_io.view(output)
            self.assertEqual(result["status"], "RECORDED", result)
            fields = result["steps"][0]["observed"]["fields"]
            self.assertEqual(fields["mode"], "DELTA" if i == 1 else "FULL")
            if i == 1:
                self.assertEqual(result["steps"][0]["observed"]["returned_events"], 0)
            previous = output


if __name__ == "__main__":
    # Reuse fixture methods, not the parent's unrelated test cases.
    names = [n for n in History.__dict__ if n.startswith("test_")]
    if "--restricted" in sys.argv:
        names = ["test_invalid_unknown_cross_work_and_wrong_prefix_reset_explicitly",
                 "test_corrupt_current_prefix_never_becomes_full_success"]
    if "--paging-only" in sys.argv:
        names = ["test_paging_while_document_stream_grows_does_not_skip_agent_events"]
    suite = unittest.TestSuite(History(n) for n in names)
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
