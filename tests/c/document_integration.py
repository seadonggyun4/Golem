"""Phase 21 actual CLI contracts; private temporary fixture data only."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = str(Path(sys.argv.pop(1)).resolve())
SAMPLES = Path(sys.argv.pop(1)).resolve()
TMP = Path(sys.argv.pop(1)).resolve()
SPEC = json.loads((SAMPLES / "work.json").read_text())
META = json.loads((SAMPLES / "planning.json").read_text())
BODY = (SAMPLES / "planning.md").read_bytes()

class Documents(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TMP, prefix="document-")
        self.root = Path(self.temp.name).resolve()
        self.work = self.root / "work"
        self.spec, self.meta, self.body = copy.deepcopy(SPEC), copy.deepcopy(META), BODY

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args, ok=True):
        p = subprocess.run([CLI, *map(str, args)], capture_output=True, timeout=30)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr.decode())
            return json.loads(p.stdout)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        return p

    def start(self):
        f = self.root / "work.json"
        f.write_text(json.dumps(self.spec))
        return self.call("work", "start", self.work, f)

    def inputs(self):
        m, b = self.root / "meta.json", self.root / "body.md"
        m.write_text(json.dumps(self.meta))
        b.write_bytes(self.body)
        return m, b

    def submit(self, key="request-1", ok=True):
        return self.call("document", "submit", self.work, *self.inputs(), key, ok=ok)

    def inspect(self, id="planning", revision=1, ok=True):
        return self.call("document", "inspect", self.work, id, revision, ok=ok)

    def project(self, ok=True):
        return self.call("document", "project", self.work, "planning", 1, ok=ok)

    def test_roundtrip(self):
        self.start()
        a = self.submit()
        self.assertFalse(a["acceptance_verified"])
        self.assertTrue(a["projection_ready"])
        self.assertEqual(a, self.submit())
        self.assertEqual(a, self.inspect())
        self.assertEqual(a["body_digest"], hashlib.sha256(BODY).hexdigest())
        self.assertEqual((self.work / "documents/planning/r0001.md").read_bytes(), BODY)
        self.assertEqual(len(list((self.work / "events").glob("*.evt"))), 2)

    def test_revision_and_idempotent_history(self):
        self.start()
        a = self.submit()
        self.meta.update(revision=2, expected_generation=2, supersedes=a["manifest_digest"])
        self.body += b"\nThe revised plan retains the original acceptance boundary.\n"
        b = self.submit("request-2")
        self.assertEqual(self.inspect()["body_digest"], a["body_digest"])
        self.assertEqual(self.inspect(revision=2)["body_digest"], b["body_digest"])
        self.meta, self.body = copy.deepcopy(META), BODY
        self.assertEqual(self.submit(), a)

    def test_conflicting_key(self):
        self.start()
        self.submit()
        self.body += b"\nChanged contents.\n"
        self.submit(ok=False)

    def test_parent_links_and_stale_parent(self):
        self.start()
        a = self.submit()
        parent = {"document_id": "planning", "revision": 1, "digest": a["manifest_digest"]}
        self.meta.update(document_id="design", parents=[parent], expected_generation=2)
        link = f'[Planning](golem-doc:planning:1:{a["manifest_digest"]})'
        self.body = BODY.replace(b"This initial plan has no upstream document revisions.",
                                 ("The upstream contract is " + link + ".").encode())
        self.submit("child")
        self.meta = copy.deepcopy(META)
        self.meta.update(revision=2, expected_generation=3, supersedes=a["manifest_digest"])
        self.body = BODY
        self.submit("parent-r2")
        self.meta.update(document_id="another-child", revision=1, supersedes="",
                         expected_generation=4, parents=[parent])
        self.body = BODY.replace(b"This initial plan has no upstream document revisions.",
                                 ("The upstream contract is " + link + ".").encode())
        self.submit("stale-child", ok=False)

    def test_bad_metadata_matrix(self):
        self.start()
        changes = [
            {"document_id": "../escape"}, {"document_id": "."},
            {"revision": 2}, {"expected_generation": 2}, {"work_id": "another"},
            {"schema_version": 2}, {"template_version": 2}, {"scope_revision": 2},
            {"policy_version": 2}, {"stage": "qa"}, {"kind": "unknown"},
            {"producer_attempt": ""}, {"source_snapshot": "bad"},
            {"requirement_ids": ["REQ-1", "REQ-1"]}, {"requirement_ids": ["REQ-UNKNOWN"]},
            {"parents": [{"document_id": "missing", "revision": 1, "digest": "0" * 64}]},
            {"parents": [{"document_id": "planning", "revision": 1, "digest": "0" * 64}]},
            {"revision": True}, {"extra": "unknown"}, {"supersedes": "0" * 64}
        ]
        for change in changes:
            with self.subTest(change=change):
                self.meta = copy.deepcopy(META)
                self.meta.update(change)
                self.submit(ok=False)
        self.assertEqual(len(list((self.work / "events").glob("*.evt"))), 1)

    def test_markdown_negative_matrix(self):
        self.start()
        fence = bytes([96]) * 3
        examples = [b"", b"# Empty\n", BODY.replace(b"## Purpose", b"## NotPurpose"),
                    fence + b"\n" + BODY + b"\n" + fence,
                    b"> " + BODY.replace(b"\n", b"\n> "),
                    BODY + b"\n## Purpose\nDuplicate content.\n",
                    BODY.replace(b"REQ-1", b"REQ-2"), BODY + b"\xff",
                    BODY + b"\x00", BODY + b"\xed\xa0\x80",
                    BODY + b"\xf4\x90\x80\x80", b"x" * (1048576 + 1)]
        for replacement in (b"**TODO** TBD TODO...", b"<!-- actual words are hidden -->",
                            fence + b"\n## Purpose\nThis is code only.\n" + fence):
            examples.append(BODY.replace(b"Keep the document registration contract explicit and bounded.",
                                         replacement))
        for body in examples:
            with self.subTest(size=len(body)):
                self.body = body
                self.submit(ok=False)

    def test_duplicate_json_nested_and_escaped(self):
        self.start()
        m, b = self.inputs()
        original = m.read_text()
        texts = [
            original.replace('"revision": 1', '"revision": 1, "revision": 1'),
            original.replace('"revision": 1', '"revision": 1, "revi\\u0073ion": 1'),
            original + "{}",
            original.replace('"producer_attempt": "local-author-1"', '"producer_attempt": "a\\u0000b"')]
        for text in texts:
            m.write_text(text)
            self.call("document", "submit", self.work, m, b, "key", ok=False)

    def test_policy(self):
        for permission in ("DENY", "ASK_ALWAYS"):
            with self.subTest(permission=permission):
                self.work = self.root / permission
                self.spec["permission"] = permission
                self.start()
                self.submit(ok=False)

    def test_revision_budget(self):
        self.spec["max_revisions"] = 1
        self.start()
        a = self.submit()
        self.assertEqual(self.submit(), a)
        self.meta.update(revision=2, expected_generation=2, supersedes=a["manifest_digest"])
        self.submit("next", ok=False)

    def test_work_schema(self):
        f = self.root / "invalid.json"
        for change in ({"acceptance": []}, {"max_revisions": 0}, {"request": ""},
                       {"acceptance": [SPEC["acceptance"][0]] * 2},
                       {"permission": "ALLOW_EVERYTHING"}, {"schema_version": 99}):
            f.write_text(json.dumps(dict(SPEC, **change)))
            self.call("work", "start", self.work, f, ok=False)
            self.assertFalse(self.work.exists())

    def test_no_overwrite_work(self):
        self.start()
        self.submit()
        self.call("work", "start", self.work, self.root / "work.json", ok=False)
        self.inspect()

    def test_symlinks(self):
        self.start()
        self.submit()
        alias = self.root / "alias"
        alias.symlink_to(self.work, target_is_directory=True)
        self.call("document", "inspect", alias, "planning", 1, ok=False)
        m, b = self.inputs()
        alias.unlink()
        alias.symlink_to(b)
        self.call("document", "submit", self.work, m, alias, "other", ok=False)

    def test_projection_recovery(self):
        self.start()
        (self.work / "documents").write_text("obstruction")
        a = self.submit()
        self.assertTrue(a["committed"])
        self.assertFalse(a["projection_ready"])
        (self.work / "documents").unlink()
        self.assertTrue(self.project()["projection_ready"])
        self.assertEqual(self.inspect()["manifest_digest"], a["manifest_digest"])

    def test_projection_tamper_is_not_overwritten(self):
        self.start()
        self.submit()
        path = self.work / "documents/planning/r0001.md"
        path.chmod(0o600)
        path.write_text("tampered")
        self.assertFalse(self.inspect()["projection_ready"])
        self.project(ok=False)
        self.assertEqual(path.read_text(), "tampered")

    def test_projection_symlink(self):
        self.start()
        self.submit()
        path = self.work / "documents/planning/r0001.md"
        path.unlink()
        target = self.root / "private"
        target.write_text("keep")
        path.symlink_to(target)
        self.project(ok=False)
        self.assertEqual(target.read_text(), "keep")

    def test_cas_corruption(self):
        self.start()
        a = self.submit()
        digest = a["body_digest"]
        obj = self.work / "objects/sha256" / digest[:2] / digest[2:]
        obj.chmod(0o600)
        obj.write_bytes(b"x" * len(BODY))
        self.inspect(ok=False)

    def test_missing_middle_event(self):
        self.start()
        a = self.submit()
        self.meta.update(revision=2, expected_generation=2, supersedes=a["manifest_digest"])
        self.submit("next")
        (self.work / "events/00000002.evt").unlink()
        self.inspect(ok=False)

    def test_corrupt_frame_and_unknown_file(self):
        self.start()
        self.submit()
        event = self.work / "events/00000002.evt"
        data = event.read_bytes()
        event.chmod(0o600)
        event.write_bytes(data[:-1])
        self.inspect(ok=False)
        event.write_bytes(data)
        (self.work / "events/garbage").write_bytes(b"x")
        self.inspect(ok=False)

    def test_pending_orphan_ignored(self):
        self.start()
        (self.work / "events/.pending-interrupted").write_bytes(b"incomplete")
        self.submit()
        self.inspect()

    def test_generation_race(self):
        self.start()
        m, b = self.inputs()
        args = [CLI, "document", "submit", str(self.work), str(m), str(b)]
        p = subprocess.Popen([*args, "one"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        q = subprocess.Popen([*args, "two"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate(timeout=30)
        q.communicate(timeout=30)
        self.assertEqual(sorted([p.returncode, q.returncode]), [0, 1])
        self.assertEqual(len(list((self.work / "events").glob("*.evt"))), 2)

    def test_kind_contracts(self):
        extras = {"ux": ("ux", "Flows"), "publishing": ("publishing", "Interface"),
                  "development-plan": ("development", "Changes"),
                  "development-result": ("development", "Results"),
                  "qa-plan": ("qa", "Cases"), "qa-result": ("qa", "Results"),
                  "completion": ("audit", "Outcome"), "research": ("planning", "Sources"),
                  "failure": ("qa", "Failure")}
        for kind, (stage, heading) in extras.items():
            self.meta = dict(META, kind=kind, stage=stage)
            self.body = BODY.replace(b"## Acceptance", ("## " + heading).encode())
            self.call("document", "validate", *self.inputs())

    def test_korean_content(self):
        self.body = BODY.replace(b"Keep the document registration contract explicit and bounded.",
                                "등록된 문서의 원본과 변경 이력을 유지합니다.".encode())
        self.call("document", "validate", *self.inputs())

if __name__ == "__main__":
    unittest.main()
