"""Binding/fencing/history tests. Host observation is synthetic, not provider auth."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
import session_integration as fixture

HELPER = Path(sys.argv.pop(1)).resolve()


class Binding(fixture.Session):
    # Existing lifecycle tests are inherited to exercise legacy compatibility too.
    def descriptor(self, adapter="codex", resume=True):
        value = dict(adapter_id=adapter, adapter_version="fixture-v1", current_agent=1,
                     domain="golem.adapter-descriptor.v1", effect=0,
                     features_known=7, features_supported=1 if resume else 0,
                     hidden_prompt_known=0, inputs_known=0, inputs_supported=0,
                     protocol_version=1, sandbox=0, schema_version=1, session_id="",
                     simulation=0, stages=63, tools=[])
        body = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return self.cli("evidence", "put", self.work, self.write("descriptor.json", body))["digest"]

    def binding_raw(self, r, mode="self", ok=True):
        args = [str(HELPER), str(self.work), str(self.write("binding.json", r)),
                str(self.now), str(self.boot), mode]
        p = subprocess.run(args, capture_output=True, env=fixture.fixture.ENV, timeout=90)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr.decode())
            return json.loads(p.stdout)
        self.assertNotEqual(p.returncode, 0, p.stdout.decode())
        return p

    def attach(self, session="agent-a", native="provider:thread/한글:1", adapter="codex",
               token=None, mode="self", ok=True, resume=True):
        self.key += 1
        r = dict(schema_version=1, operation="attach", work_id="example-work",
                 key=f"binding-{self.key}", expected_sequence=self.seq, session_id=session,
                 descriptor_digest=self.descriptor(adapter, resume), native_thread_id=native,
                 token=token, ttl_ms=10000)
        result = self.binding_raw(r, mode, ok)
        self.last_binding = r
        if ok:
            self.seq = result["sequence"]
            self.binding_id = result["state"]["binding"]["binding_id"]
        return result

    def bound_claim(self):
        r = self.request("claim", schema_version=2, binding_id=self.binding_id,
                         session_id="agent-a", expected_generation=self.generation,
                         source_snapshot=self.source, byte_budget=1048576, ttl_ms=10000)
        self.active = r["state"]["active"]
        self.token = {k: self.active[k] for k in ("epoch", "attempt_id", "session_id")}
        return r

    def inspect_binding(self):
        return self.binding_raw(dict(schema_version=1, operation="inspect", work_id="example-work"), "inspect")

    def history(self, request=None, ok=True):
        if request is None:
            request = dict(schema_version=1, work_id="example-work", after=0, limit=256,
                           document_head="", agent_head="")
        return self.cli("work", "history", self.work, self.write("history.json", request), ok=ok)

    def test_binding_privacy_and_provenance(self):
        self.setup_session()
        r = self.attach()
        b = r["state"]["binding"]
        self.assertEqual(b["provenance"], "SELF_REPORTED")
        self.assertEqual(b["reconnect"], "CLAIMED")
        self.assertEqual(b["native_thread_digest"], hashlib.sha256("provider:thread/한글:1".encode()).hexdigest())
        self.assertNotIn("provider:thread/", json.dumps(r))
        self.assertNotIn("native_thread_id", json.dumps(self.inspect_binding()))
        self.assertEqual(self.binding_raw(self.last_binding), r)
        self.assertEqual(self.inspect_binding()["sequence"], self.seq)
        observed = self.attach(adapter="claude", mode="host")
        self.assertEqual(observed["state"]["binding"]["provenance"], "HOST_OBSERVED")
        self.assertNotEqual(b["binding_id"], observed["state"]["binding"]["binding_id"])
        self.assertEqual(self.attach(native="", resume=False)["state"]["binding"]["reconnect"], "UNAVAILABLE")

    def test_bound_lifecycle_rejects_legacy_claim_and_resume(self):
        self.setup_session()
        self.attach()
        self.claim(ok=False)
        self.bound_claim()
        self.begin()
        self.request("resume", session_id="agent-a", ttl_ms=10000, ok=False)
        self.output()
        self.submit()
        self.assertEqual(self.history()["agent_history"], "RECORDED")

    def test_reattach_fences_all_old_actions_and_preserves_output(self):
        self.setup_session()
        self.attach()
        self.bound_claim()
        self.begin()
        self.output()
        old, old_id = copy.deepcopy(self.token), self.binding_id
        self.binding_raw(dict(binding_id=old_id, token=old), "fence")
        self.attach(token=None, ok=False)
        r = self.attach(token=old, adapter="claude")
        self.assertEqual(r["state"]["active"]["state"], "RECOVERY_REQUIRED")
        self.binding_raw(dict(binding_id=old_id, token=old), "fence", ok=False)
        self.request("heartbeat", token=old, ttl_ms=10000, ok=False)
        self.submit(ok=False)
        self.token = {k: r["state"]["active"][k] for k in old}
        self.binding_raw(dict(binding_id=self.binding_id, token=self.token), "fence")
        self.request("reconcile", token=self.token, input_digest=self.active["manifest_digest"],
                     source_snapshot=self.source, output=self.ref, evidence=[self.evidence],
                     resolution="ADOPT_OUTPUT")
        self.assertEqual(len(list((self.work / "documents/planning").glob("*.md"))), 1)

    def test_bound_resume_and_expired_fence(self):
        self.setup_session()
        self.attach()
        self.bound_claim()
        self.begin()
        old = copy.deepcopy(self.token)
        self.now += 10000
        self.binding_raw(dict(binding_id=self.binding_id, token=old), "fence", ok=False)
        self.request("resume", schema_version=2, binding_id=self.binding_id, token=None,
                     session_id="agent-a", ttl_ms=10000, ok=False)
        r = self.request("resume", schema_version=2, binding_id=self.binding_id, token=old,
                         session_id="agent-a", ttl_ms=10000)
        self.assertGreater(r["state"]["active"]["epoch"], old["epoch"])
        self.request("heartbeat", token=old, ttl_ms=10000, ok=False)

    def test_malformed_and_host_denial_no_mutation(self):
        self.setup_session()
        self.attach(mode="deny", ok=False)
        for native in ("x" * 1025, "bad\nline", "x\x00y"):
            self.attach(native=native, ok=False)
        self.assertEqual(self.inspect_binding()["sequence"], self.seq)
        self.attach()
        for field in ("provenance", "host_identity", "secret", "access_token"):
            bad = dict(self.last_binding, **{field: "HOST_OBSERVED"})
            self.binding_raw(bad, ok=False)
        bad = dict(self.last_binding, descriptor_digest="f" * 64, key="unknown", expected_sequence=self.seq)
        self.binding_raw(bad, ok=False)

    def test_history_paging_readonly_and_stale_cursor(self):
        self.setup_session()
        self.attach()
        self.bound_claim()
        self.begin()
        before = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        first = self.history(dict(schema_version=1, work_id="example-work", after=0, limit=2,
                                  document_head="", agent_head=""))
        result, events = first, list(first["events"])
        while result["has_more"]:
            request = dict(schema_version=1, work_id="example-work", after=result["next_after"], limit=2,
                           document_head=first["document_head"], agent_head=first["agent_head"])
            result = self.history(request)
            events.extend(result["events"])
        self.assertEqual(len(events), first["total"])
        self.assertEqual(len({(e["stream"], e["sequence"]) for e in events}), len(events))
        self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()})
        self.request("heartbeat", token=self.token, ttl_ms=10000)
        self.history(request, ok=False)

    def test_missing_agent_prefix_is_error(self):
        self.setup_session()
        self.attach()
        (self.work / "agent-events/00000001.evt").unlink()
        self.history(ok=False)
        self.binding_raw(dict(schema_version=1, operation="inspect", work_id="example-work"), "inspect", ok=False)

    def test_actual_binding_cli(self):
        self.setup_session(actual=True)
        self.key += 1
        r = dict(schema_version=1, operation="attach", work_id="example-work", key="cli-bind",
                 expected_sequence=self.seq, session_id="agent-a", descriptor_digest=self.descriptor(),
                 native_thread_id="local:thread", token=None, ttl_ms=10000)
        out = self.cli("agent", "binding", "attach", self.work, self.write("attach.json", r))
        self.seq = out["sequence"]
        inspect = dict(schema_version=1, operation="inspect", work_id="example-work")
        self.assertEqual(self.cli("agent", "binding", "inspect", self.work,
                         self.write("inspect.json", inspect))["sequence"], self.seq)

    def test_runtime_identity_pairing_and_history_links(self):
        self.setup_session()
        self.attach()
        profile = json.loads((fixture.fixture.SOURCE / "samples/runtime-profile.json").read_text())
        self.cli("profile", "register", self.work, self.write("profile.json", profile), "unknown-profile")
        self.request("claim", schema_version=2, binding_id=self.binding_id, session_id="agent-a",
                     expected_generation=self.generation, source_snapshot=self.source,
                     byte_budget=1048576, ttl_ms=10000, ok=False)
        profile["adapter_descriptor_digest"] = self.last_binding["descriptor_digest"]
        self.cli("profile", "register", self.work, self.write("profile.json", profile), "bound-profile")
        self.bound_claim()
        self.begin()
        rows = self.history()["events"]
        began = next(e for e in rows if e["stream"] == "agent" and e["operation"] == "begin")
        self.assertEqual(began["binding_id"], self.binding_id)
        self.assertEqual(began["runtime_binding"], self.active["runtime_binding"])
        self.assertEqual(began["epoch"], self.token["epoch"])

    def test_missing_descriptor_cas_fails_closed(self):
        self.setup_session()
        self.attach()
        digest = self.last_binding["descriptor_digest"]
        (self.work / "objects/sha256" / digest[:2] / digest[2:]).unlink()
        self.binding_raw(dict(schema_version=1, operation="inspect", work_id="example-work"), "inspect", ok=False)
        self.history(ok=False)

    def test_attachment_race_has_one_winner(self):
        self.setup_session()
        digest = self.descriptor()
        processes = []
        for i in range(2):
            r = dict(schema_version=1, operation="attach", work_id="example-work", key=f"race-bind-{i}",
                     expected_sequence=self.seq, session_id=f"agent-{i}", descriptor_digest=digest,
                     native_thread_id=f"same-provider:thread", token=None, ttl_ms=10000)
            path = self.write(f"bind-race-{i}.json", r)
            processes.append(subprocess.Popen([str(HELPER), str(self.work), str(path), str(self.now),
                                               str(self.boot), "self"], stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, env=fixture.fixture.ENV))
        outputs = [p.communicate(timeout=90) for p in processes]
        self.assertEqual(sum(p.returncode == 0 for p in processes), 1, outputs)


if __name__ == "__main__":
    unittest.main()
