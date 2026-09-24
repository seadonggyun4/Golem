"""Conditional handoffs and immutable revision freshness; no agent execution."""
import copy
import json
import subprocess
import unittest
import discovery_integration as fixture
from discovery_integration import CLI, SOURCE, ENV


class Workflow(unittest.TestCase):
    setUp = fixture.Discovery.setUp
    tearDown = fixture.Discovery.tearDown
    write = fixture.Discovery.write
    cli = fixture.Discovery.cli
    validate = fixture.Discovery.validate
    answered = fixture.Discovery.answered
    confirmed = fixture.Discovery.confirmed

    def body(self, kind, parents):
        extra = {"stage-selection": "Stages", "planning": "Acceptance", "ux": "Flows",
                 "publishing": "Interface", "development-plan": "Changes", "development-result": "Results",
                 "qa-plan": "Cases", "qa-result": "Results", "completion": "Outcome", "scope": "Selection"}[kind]
        sections = ["Purpose", "Scope", "Parents", "Evidence", "Decisions", "Requirements", "Work", "Validation", "Risks", extra]
        text = f"# Fixture {kind}\n\n"
        for section in sections:
            text += f"## {section}\n\nREQ-1 fixture explanation for {section}; structural evidence only.\n\n"
            if section == "Parents":
                for p in parents:
                    text += f"[Parent {p['document_id']}](golem-doc:{p['document_id']}:{p['revision']}:{p['digest']})\n\n"
        return text

    def metadata(self, kind, doc_id=None, parents=None, version=1):
        doc_id = doc_id or kind
        prev = self.docs.get(doc_id)
        stage = {"stage-selection": "planning", "scope": "planning", "development-plan": "development",
                 "development-result": "development", "qa-plan": "qa", "qa-result": "qa", "completion": "audit"}.get(kind, kind)
        return {"schema_version": version, "work_id": getattr(self, "work_id", "example-work"), "document_id": doc_id,
                "revision": prev["revision"] + 1 if prev else 1, "kind": kind, "stage": stage,
                "producer_attempt": "fixture", "parents": parents or [], "requirement_ids": ["REQ-1"],
                "scope_revision": 1, "template_version": 1, "policy_version": 1,
                "source_snapshot": self.source, "supersedes": prev["manifest_digest"] if prev else "",
                "expected_generation": self.generation}

    def publish(self, m, ok=True):
        path = self.write("metadata.json", m)
        body = self.write("body.md", self.body(m["kind"], m["parents"]))
        r = self.cli("document", "submit", self.work, path, body, f"key-{m['document_id']}-{m['revision']}", ok=ok)
        if ok:
            self.generation += 1
            self.docs[m["document_id"]] = r
        return r

    def setup_work(self, ui=False, mode="development"):
        self.confirmed()
        self.a["work_id"] = getattr(self, "work_id", "example-work")
        self.a["selections"][0].update(needs_ux=ui, needs_publishing=ui)
        self.source = self.validate()["snapshot_digest"]
        self.work = self.root / "work"
        self.docs = {}
        self.generation = 1
        spec = json.loads((SOURCE / "samples/documents/work.json").read_text())
        spec["work_id"] = getattr(self, "work_id", "example-work")
        self.cli("work", "start", self.work, self.write("work-spec.json", spec))
        self.cli("evidence", "put", self.work, self.write("log.txt", "fixture observation\n"))
        scope = self.metadata("scope", version=2)
        scope["assessment"] = self.a
        self.publish(scope)
        self.selection = self.cli("workflow", "select", self.work, "scope", 1, mode)

    def register_selection(self, p=None, parents=None, ok=True):
        p = p or self.selection
        m = self.metadata("stage-selection", "selection", parents or [p["scope"]], 3)
        m["selection"] = p
        return self.publish(m, ok=ok)

    def inputs(self, kind, ok=True, budget=16777216):
        return self.cli("workflow", "inputs", self.work, "selection", kind, self.source, budget, ok=ok)

    def managed(self, kind, doc_id=None):
        manifest = self.inputs(kind)
        m = self.metadata(kind, doc_id, manifest["direct"], 4)
        m["input_manifest"] = manifest
        return self.publish(m)

    def next(self):
        return self.cli("workflow", "next", self.work, "selection")

    def trace(self, doc, revision=1):
        return self.cli("workflow", "trace", self.work, doc, revision)

    def test_internal_work_skips_only_interface_stages(self):
        self.setup_work()
        self.assertEqual([v["status"] for v in self.selection["decisions"]],
                         ["REQUIRED", "NOT_APPLICABLE", "NOT_APPLICABLE", "REQUIRED", "REQUIRED", "REQUIRED"])
        self.register_selection()
        for kind in ("planning", "development-plan", "development-result", "qa-plan", "qa-result", "completion"):
            self.assertEqual(self.next()["target_kind"], kind)
            self.managed(kind)
        final = self.next()
        self.assertEqual(final["action"], "VERIFY_COMPLETION")
        self.assertFalse(final["acceptance_verified"])
        self.assertFalse(final["execution_authorized"])

    def test_ui_cannot_omit_required_stage(self):
        self.setup_work(ui=True)
        self.assertTrue(all(v["status"] == "REQUIRED" for v in self.selection["decisions"]))
        for stage in (0, 1, 2, 3, 4, 5):
            p = copy.deepcopy(self.selection)
            p["decisions"][stage]["status"] = "NOT_APPLICABLE"
            self.register_selection(p, ok=False)
        self.register_selection()
        self.managed("planning")
        self.inputs("development-plan", ok=False)
        self.managed("ux")
        self.inputs("development-plan", ok=False)
        self.managed("publishing")
        m = self.inputs("development-plan")
        self.assertEqual({v["document_id"] for v in m["direct"]}, {"selection", "planning", "ux", "publishing"})
        self.managed("development-plan")

    def test_transitive_stale_and_deterministic_next(self):
        self.setup_work()
        self.register_selection()
        for kind in ("planning", "development-plan", "development-result", "qa-plan", "qa-result"):
            self.managed(kind)
        self.assertEqual(self.trace("qa-result")["state"], "CURRENT")
        self.managed("planning")
        self.assertEqual(self.trace("planning")["state"], "SUPERSEDED")
        self.assertEqual(self.trace("planning", 2)["state"], "CURRENT")
        for kind in ("development-plan", "development-result", "qa-plan", "qa-result"):
            self.assertEqual(self.trace(kind)["state"], "STALE")
        self.assertEqual(self.next(), self.next())
        self.assertEqual(self.next()["action"], "REVISE_DOCUMENT")
        self.assertEqual(self.next()["target_kind"], "development-plan")
        self.inputs("qa-plan", ok=False)

    def test_stale_manifest_cannot_commit(self):
        self.setup_work()
        self.register_selection()
        self.managed("planning")
        manifest = self.inputs("development-plan")
        m = self.metadata("development-plan", parents=manifest["direct"], version=4)
        m["input_manifest"] = manifest
        self.managed("planning")
        self.publish(m, ok=False)
        m["expected_generation"] = self.generation
        m["input_manifest"]["generation"] = self.generation
        self.publish(m, ok=False)
        self.managed("development-plan")

    def test_missing_and_tampered_manifest_rejected(self):
        self.setup_work(ui=True)
        self.register_selection()
        for kind in ("planning", "ux", "publishing"):
            self.managed(kind)
        manifest = self.inputs("development-plan")
        for field in ("documents", "direct", "total_bytes", "selection"):
            v = copy.deepcopy(manifest)
            if field in ("documents", "direct"):
                v[field].pop()
            elif field == "total_bytes":
                v[field] -= 1
            else:
                v[field]["digest"] = "f" * 64
            m = self.metadata("development-plan", parents=v["direct"], version=4)
            m["input_manifest"] = v
            self.publish(m, ok=False)

    def test_context_budget_no_silent_truncation(self):
        self.setup_work()
        self.register_selection()
        self.inputs("planning", budget=1, ok=False)
        m = self.inputs("planning")
        self.assertGreater(m["total_bytes"], 1)
        self.assertEqual(len(m["documents"]), 2)

    def test_unrelated_work_does_not_change_inputs(self):
        self.setup_work()
        self.register_selection()
        before = self.inputs("planning")
        other = self.root / "other"
        self.cli("work", "start", other, SOURCE / "samples/documents/work.json")
        self.cli("document", "submit", other, SOURCE / "samples/documents/planning.json", SOURCE / "samples/documents/planning.md", "other")
        self.assertEqual(before, self.inputs("planning"))

    def test_cross_work_and_duplicate_parent_denied(self):
        self.setup_work()
        p = copy.deepcopy(self.selection)
        p["scope"]["digest"] = "f" * 64
        for d in p["decisions"]:
            d["evidence"] = p["scope"]
        self.register_selection(p, ok=False)
        self.register_selection(parents=[self.selection["scope"], self.selection["scope"]], ok=False)

    def test_unqualified_legacy_document_is_not_current_input(self):
        self.setup_work()
        self.register_selection()
        self.publish(self.metadata("planning", "legacy-plan"))
        self.assertEqual(self.next()["target_kind"], "planning")
        self.inputs("development-plan", ok=False)

    def test_documents_mode_has_no_fake_implementation_result(self):
        self.setup_work(mode="documents")
        self.register_selection()
        self.inputs("development-result", ok=False)
        for kind in ("planning", "development-plan", "qa-plan", "qa-result", "completion"):
            self.managed(kind)
        self.assertEqual(self.next()["action"], "VERIFY_COMPLETION")

    def test_modified_projection_not_a_registered_input(self):
        self.setup_work()
        self.register_selection()
        p = self.work / "documents/selection/r0001.md"
        p.chmod(0o600)
        p.write_text("externally changed")
        self.inputs("planning", ok=False)
        self.cli("workflow", "next", self.work, "selection", ok=False)

    def test_snapshot_and_requirement_mismatch_rejected(self):
        self.setup_work()
        self.register_selection()
        manifest = self.inputs("planning")
        self.cli("workflow", "inputs", self.work, "selection", "planning", "f" * 64, 16777216, ok=False)
        m = self.metadata("planning", parents=manifest["direct"], version=4)
        m["input_manifest"] = manifest
        m["requirement_ids"] = ["UNRELATED"]
        self.publish(m, ok=False)

    def test_reuse_requires_scope_bound_review(self):
        self.setup_work(ui=True)
        e = self.publish(self.metadata("ux", "existing-ux"))
        ref = {"document_id": "existing-ux", "revision": 1, "digest": e["manifest_digest"]}
        self.selection["decisions"][1].update(status="REUSED", reuse={"document": ref, "review_digest": "f" * 64})
        parents = [self.selection["scope"], ref]
        self.register_selection(parents=parents, ok=False)
        review = {"schema_version": 1, "work_id": "example-work", "document": ref,
                  "scope": self.selection["scope"], "source_snapshot": self.source,
                  "policy_version": 1, "template_version": 1, "decision": "REUSE",
                  "reason": "Reviewed this existing interface against the selected scope and snapshot."}
        receipt = self.cli("evidence", "put", self.work, self.write("review.json", review))
        wrong = copy.deepcopy(review)
        wrong["scope"]["digest"] = "f" * 64
        bad = self.cli("evidence", "put", self.work, self.write("wrong-review.json", wrong))
        self.selection["decisions"][1]["reuse"]["review_digest"] = bad["digest"]
        self.register_selection(parents=parents, ok=False)
        self.selection["decisions"][1]["reuse"]["review_digest"] = receipt["digest"]
        self.register_selection(parents=parents)
        self.managed("planning")
        self.assertEqual(self.next()["target_kind"], "publishing")
        self.managed("publishing")
        self.managed("development-plan")
        self.assertIn("existing-ux", {v["document_id"] for v in self.trace("development-plan")["closure"]})

    def test_scope_update_invalidates_selection(self):
        self.setup_work()
        self.register_selection()
        self.managed("planning")
        m = self.metadata("scope", version=2)
        m["assessment"] = self.a
        self.publish(m)
        self.assertEqual(self.trace("selection")["state"], "STALE")
        self.assertEqual(self.trace("planning")["state"], "STALE")
        self.cli("workflow", "next", self.work, "selection", ok=False)

    def test_reuse_cannot_invalidate_its_own_selection_ancestor(self):
        self.setup_work(ui=True)
        self.register_selection()
        self.managed("planning")
        e = self.managed("ux")
        ref = {"document_id": "ux", "revision": 1, "digest": e["manifest_digest"]}
        review = {"schema_version": 1, "work_id": "example-work", "document": ref,
                  "scope": self.selection["scope"], "source_snapshot": self.source,
                  "policy_version": 1, "template_version": 1, "decision": "REUSE",
                  "reason": "Cannot make a new selection depend on its old revision through UX."}
        evidence = self.cli("evidence", "put", self.work, self.write("review.json", review))
        self.selection["decisions"][1].update(status="REUSED", reuse={"document": ref, "review_digest": evidence["digest"]})
        self.register_selection(parents=[self.selection["scope"], ref], ok=False)
        self.assertEqual(self.trace("selection")["state"], "CURRENT")

    def test_ambiguous_managed_kind_fails_closed(self):
        self.setup_work()
        self.register_selection()
        self.managed("planning", "plan-a")
        self.managed("planning", "plan-b")
        self.inputs("development-plan", ok=False)


if __name__ == "__main__":
    unittest.main()
