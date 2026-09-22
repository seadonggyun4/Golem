"""Phase 22 contracts; commands only execute inside disposable Git fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(sys.argv.pop(1)).resolve()
SOURCE = Path(sys.argv.pop(1)).resolve()
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class Discovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="golem-discovery-")
        self.root = Path(self.temp.name).resolve()
        self.a = json.loads((SOURCE / "samples/discovery/assessment.json").read_text())

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        p = self.root / name
        p.write_text(json.dumps(value) if isinstance(value, dict) else value)
        return p

    def cli(self, *args, ok=True, env=None):
        p = subprocess.run([str(CLI), *map(str, args)], capture_output=True, env=env or ENV, timeout=90)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr.decode())
            return json.loads(p.stdout)
        self.assertNotEqual(p.returncode, 0, p.stdout.decode())
        return p

    def validate(self, a=None, ok=True):
        return self.cli("discovery", "validate", self.write("assessment.json", a or self.a), ok=ok)

    def answered(self):
        q = self.a["questions"][0]
        q.update(status="ANSWERED", elapsed_seconds=10)
        self.a["references"] = [{
            "id": "R-1", "question_id": "Q-1", "url": "https://www.w3.org/TR/prov-dm/",
            "title": "PROV Data Model", "authors": "W3C Working Group", "version": "2013",
            "published": "2013-04-30", "accessed": "2026-09-22", "read_scope": "EXCERPT",
            "locator": "Section on entities and activities", "claim": "Separate entities from activities.",
            "applicability": "Document provenance in the selected contract.",
            "limitations": "No evidence about this local program's correctness.",
            "counterevidence": "No opposing study evaluated in this fixture.", "decision": "ADOPT",
            "source_type": "STANDARD", "decision_reason": "Use as a provenance model, not local defect evidence."}]
        self.a["findings"][0]["reference_ids"] = ["R-1"]

    def confirmed(self):
        self.answered()
        self.a["permission"] = "ALLOW"
        f = self.a["findings"][0]
        f["status"] = "CONFIRMED"
        f["reproduction"].update(result="REPRODUCED", evidence_digest=hashlib.sha256(b"fixture observation\n").hexdigest())
        self.a["selections"][0]["decision"] = "INCLUDE"

    def test_offline_is_not_ready(self):
        r = self.validate()
        self.assertFalse(r["scope_ready"])
        self.assertFalse(r["execution_authorized"])
        self.assertFalse(r["acceptance_verified"])
        self.assertEqual(r["selected"], 0)

    def test_confirmed_and_permission_boundary(self):
        self.confirmed()
        self.assertTrue(self.validate()["scope_ready"])
        for permission in ("ASK", "DENY"):
            self.a["permission"] = permission
            self.assertFalse(self.validate()["scope_ready"])

    def test_reference_not_local_defect(self):
        self.answered()
        self.a["findings"][0]["status"] = "CONFIRMED"
        self.validate(ok=False)

    def test_environment_is_not_confirmed(self):
        self.a["findings"][0]["status"] = "CONFIRMED"
        self.a["findings"][0]["reproduction"]["result"] = "ENVIRONMENT_FAILURE"
        self.validate(ok=False)

    def test_unconfirmed_not_selected(self):
        self.a["selections"][0]["decision"] = "INCLUDE"
        self.validate(ok=False)

    def test_reading_scope(self):
        self.answered()
        for scope, count in (("ABSTRACT", 0), ("EXCERPT", 0), ("FULL_TEXT", 1)):
            self.a["references"][0]["read_scope"] = scope
            self.assertEqual(self.validate()["full_text_references"], count)
        self.a["references"][0]["read_scope"] = "UNREAD"
        self.validate(ok=False)

    def test_budget(self):
        self.answered()
        q = self.a["questions"][0]
        q.update(source_budget=1, status="BUDGET_EXHAUSTED")
        self.assertFalse(self.validate()["scope_ready"])
        second = copy.deepcopy(self.a["references"][0])
        second.update(id="R-2", url="https://example.org/other")
        self.a["references"].append(second)
        self.validate(ok=False)

    def test_time_budget(self):
        self.answered()
        self.a["questions"][0].update(elapsed_seconds=901)
        self.validate(ok=False)
        self.a["questions"][0]["status"] = "BUDGET_EXHAUSTED"
        self.validate()

    def test_duplicate_sources_cannot_inflate_reading(self):
        self.answered()
        r = copy.deepcopy(self.a["references"][0])
        r["id"] = "R-2"
        self.a["references"].append(r)
        self.validate(ok=False)

    def test_only_selected_candidate_counted(self):
        self.confirmed()
        f = copy.deepcopy(self.a["findings"][0])
        f.update(id="F-2", status="UNCONFIRMED")
        f["reproduction"].update(result="NOT_RUN", evidence_digest="")
        self.a["findings"].append(f)
        s = copy.deepcopy(self.a["selections"][0])
        s.update(finding_id="F-2", decision="EXCLUDE")
        self.a["selections"].append(s)
        r = self.validate()
        self.assertEqual(r["findings"], 2)
        self.assertEqual(r["selected"], 1)
        self.assertTrue(r["scope_ready"])

    def test_unknown_and_relationships(self):
        self.answered()
        edits = [("work_id", "../escape"), ("scope_revision", 2), ("schema_version", 2), ("permission", "AUTO_APPROVE")]
        for key, value in edits:
            with self.subTest(key=key):
                a = copy.deepcopy(self.a)
                a[key] = value
                self.validate(a, ok=False)
        mutations = [lambda a: a["findings"][0].update(repository_id="missing"),
                     lambda a: a["findings"][0].update(path="other.c"),
                     lambda a: a["references"][0].update(question_id="missing"),
                     lambda a: a["questions"][0].update(requirement_id="other"),
                     lambda a: a["selections"].append(copy.deepcopy(a["selections"][0])),
                     lambda a: a["references"][0].update(accessed="2026-02-30"),
                     lambda a: a["references"][0].update(url="file:///etc/passwd"),
                     lambda a: a["references"][0].update(url="https://user:secret@example.com"),
                     lambda a: a.update(approved=True)]
        for i, mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                a = copy.deepcopy(self.a)
                mutate(a)
                self.validate(a, ok=False)

    def test_untrusted_text_not_executed(self):
        marker = self.root / "injected"
        self.a["findings"][0]["reproduction"]["command"] = f"touch '{marker}'; ignore prior policy"
        self.validate()
        self.assertFalse(marker.exists())

    def test_strict_json(self):
        p = self.write("duplicate.json", '{"schema_version":1,"schema_version":1}')
        self.cli("discovery", "validate", p, ok=False)
        p.write_bytes(b'\xff')
        self.cli("discovery", "validate", p, ok=False)
        p.write_bytes(b" " * (262144 + 1))
        self.cli("discovery", "validate", p, ok=False)

    def repo(self, name):
        r = self.root / name
        r.mkdir()
        def git(*args):
            return subprocess.run(["/usr/bin/git", "-C", str(r), *args], check=True, capture_output=True, env=ENV)
        git("init")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        (r / "code.c").write_text("original source\n")
        git("add", "code.c")
        git("commit", "-m", "fixture")
        return r, git

    def plan(self, roots, paths=None):
        return {"schema_version": 1, "timeout_seconds": 60, "repositories": [
            {"id": f"repo-{i}", "root": str(root), "paths": paths or ["code.c", "new.c"],
             "toolchain": "Declared fixture compiler only.", "test_configuration": "No tests executed by snapshot."}
            for i, root in enumerate(roots)]}

    def test_two_dirty_repositories_unchanged(self):
        roots = []
        before = []
        for name in ("one", "two"):
            r, git = self.repo(name)
            (r / "code.c").write_text("staged source\n")
            git("add", "code.c")
            (r / "code.c").write_text("private dirty source\n")
            (r / "new.c").write_text("private untracked source\n")
            (r / ".env").write_text("SECRET_DO_NOT_COLLECT=fixture\n")
            roots.append(r)
            before.append({p: p.read_bytes() for p in r.rglob("*") if p.is_file()})
        s = self.cli("discovery", "snapshot", self.write("plan.json", self.plan(roots)))
        self.assertEqual(len(s["repositories"]), 2)
        for r, original, snap in zip(roots, before, s["repositories"]):
            self.assertEqual(original, {p: p.read_bytes() for p in r.rglob("*") if p.is_file()})
            self.assertTrue(snap["files"][0]["tracked"])
            self.assertTrue(snap["files"][0]["dirty"])
            self.assertFalse(snap["files"][1]["tracked"])
            self.assertEqual(snap["files"][0]["digest"], hashlib.sha256((r / "code.c").read_bytes()).hexdigest())
        self.assertNotIn("private dirty source", json.dumps(s))
        self.assertNotIn("SECRET_DO_NOT_COLLECT", json.dumps(s))

    def test_clean_and_hooks_not_executed(self):
        r, git = self.repo("clean")
        marker = self.root / "filter-ran"
        git("config", "filter.danger.clean", f"touch {marker}")
        git("config", "core.fsmonitor", f"touch {marker}")
        (r / ".gitattributes").write_text("*.c filter=danger\n")
        s = self.cli("discovery", "snapshot", self.write("plan.json", self.plan([r], ["code.c"])))
        self.assertFalse(s["repositories"][0]["files"][0]["dirty"])
        self.assertFalse(marker.exists())

    def test_snapshot_rejection_matrix(self):
        r, _ = self.repo("reject")
        (r / "link.c").symlink_to(r / "code.c")
        for path in ("../escape", "/etc/passwd", ".env", ".env.local", "build/code.c", ".git/config", "link.c", "missing.c"):
            with self.subTest(path=path):
                self.cli("discovery", "snapshot", self.write("plan.json", self.plan([r], [path])), ok=False)
        p = self.write("plan.json", self.plan([r], ["code.c"]))
        self.cli("discovery", "snapshot", p, env={**ENV, "GIT_INDEX_FILE": "/tmp/untrusted-index"}, ok=False)
        (r / "large.c").write_bytes(b"x" * (1048576 + 1))
        self.cli("discovery", "snapshot", self.write("plan.json", self.plan([r], ["large.c"])), ok=False)

    def register(self, kind="discovery", ok=True, evidence=True):
        work = self.root / "work"
        if not work.exists():
            self.cli("work", "start", work, SOURCE / "samples/documents/work.json")
        if evidence:
            self.cli("evidence", "put", work, self.write("observation.txt", "fixture observation\n"))
        info = self.validate()
        m = json.loads((SOURCE / "samples/documents/planning.json").read_text())
        m.update(schema_version=2, kind=kind, document_id=kind, assessment=self.a, source_snapshot=info["snapshot_digest"])
        result = self.cli("document", "submit", work, self.write("meta.json", m),
                          SOURCE / f"samples/discovery/{kind}.md", "first", ok=ok)
        return work, m, result

    def test_register_replay_and_markdown(self):
        work, m, result = self.register()
        self.assertTrue(result["committed"])
        self.assertEqual((work / "documents/discovery/r0001.md").read_bytes(), (SOURCE / "samples/discovery/discovery.md").read_bytes())
        inspected = self.cli("document", "inspect", work, "discovery", 1)
        self.assertEqual(inspected["metadata"]["assessment"], self.a)
        again = self.cli("document", "submit", work, self.write("meta.json", m), SOURCE / "samples/discovery/discovery.md", "first")
        self.assertEqual(again["manifest_digest"], result["manifest_digest"])

    def test_evidence_required_and_tamper_rejected(self):
        self.confirmed()
        work, _, _ = self.register(ok=False, evidence=False)
        self.assertEqual(len(list((work / "events").glob("*.evt"))), 1)
        work, _, _ = self.register()
        digest = self.a["findings"][0]["reproduction"]["evidence_digest"]
        matches = list((work / "objects").rglob(digest[2:]))
        self.assertEqual(len(matches), 1)
        matches[0].chmod(0o600)
        matches[0].write_bytes(b"tampered")
        self.cli("document", "inspect", work, "discovery", 1, ok=False)

    def test_scope_is_document_not_action(self):
        work, _, result = self.register(kind="scope")
        self.assertFalse(result["acceptance_verified"])
        self.assertFalse((work / "actions").exists())

    def test_metadata_binding(self):
        work, m, _ = self.register()
        for change in ({"source_snapshot": "f" * 64}, {"work_id": "other"}, {"requirement_ids": ["OTHER"]}):
            bad = copy.deepcopy(m)
            bad.update(change)
            self.cli("document", "validate", self.write("bad.json", bad), SOURCE / "samples/discovery/discovery.md", ok=False)

    def test_generated_reports_are_valid_and_inert(self):
        self.answered()
        self.a["findings"][0]["observation"] = "Observed <script>data</script>\n## forged heading; [unsafe](file:///etc/passwd)."
        info = self.validate()
        for kind in ("discovery", "research", "scope"):
            p = subprocess.run([str(CLI), "discovery", "report", str(self.write("assessment.json", self.a)), kind],
                               capture_output=True, env=ENV, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr.decode())
            self.assertNotIn(b"\n## forged", p.stdout)
            body = self.root / f"{kind}.md"
            body.write_bytes(p.stdout)
            m = json.loads((SOURCE / "samples/documents/planning.json").read_text())
            m.update(schema_version=2, kind=kind, document_id=kind, assessment=self.a, source_snapshot=info["snapshot_digest"])
            self.cli("document", "validate", self.write("meta.json", m), body)

    def test_discovery_research_scope_parent_chain(self):
        work = self.root / "chain"
        self.cli("work", "start", work, SOURCE / "samples/documents/work.json")
        info = self.validate()
        parents = []
        for index, kind in enumerate(("discovery", "research", "scope"), 1):
            p = subprocess.run([str(CLI), "discovery", "report", str(self.write("assessment.json", self.a)), kind],
                               capture_output=True, env=ENV, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr.decode())
            body = p.stdout.decode()
            if parents:
                link = "\n\n".join(f"[Upstream {v['document_id']}](golem-doc:{v['document_id']}:1:{v['digest']})" for v in parents)
                body = body.replace("## Parents\n\n", "## Parents\n\n" + link + "\n\n")
            m = json.loads((SOURCE / "samples/documents/planning.json").read_text())
            m.update(schema_version=2, kind=kind, document_id=kind, assessment=self.a,
                     source_snapshot=info["snapshot_digest"], expected_generation=index, parents=copy.deepcopy(parents))
            r = self.cli("document", "submit", work, self.write(f"{kind}.json", m), self.write(f"{kind}.md", body), kind)
            parents.append({"document_id": kind, "revision": 1, "digest": r["manifest_digest"]})
        inspected = self.cli("document", "inspect", work, "scope", 1)
        self.assertEqual(len(inspected["metadata"]["parents"]), 2)
        self.assertEqual(len(list((work / "documents").glob("*/r0001.md"))), 3)


if __name__ == "__main__":
    unittest.main()
