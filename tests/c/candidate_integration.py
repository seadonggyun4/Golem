"""Trusted-host contract tests; no provider subprocesses or paid agent calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

from execution_change_integration import Changes
from discovery_integration import CLI, SOURCE, ENV

HELPER = Path(sys.argv.pop(1)).resolve()


class Candidates(Changes):
    def tearDown(self):
        self.stop_host()
        super().tearDown()

    def stop_host(self):
        p = getattr(self, "host", None)
        if p is not None:
            try:
                p.stdin.write('{"operation":"$quit"}\n')
                p.stdin.flush()
            except BrokenPipeError:
                pass
            _, err = p.communicate(timeout=20)
            self.host = None
            self.assertEqual(p.returncode, 0, err)

    def rpc(self, operation, ok=True, **fields):
        try:
            self.host.stdin.write(json.dumps({"operation": operation, **fields}) + "\n")
            self.host.stdin.flush()
        except BrokenPipeError:
            _, error = self.host.communicate(timeout=20)
            code, self.host = self.host.returncode, None
            self.fail(f"host failed before {operation}: exit={code}; stderr={error}")
        line = self.host.stdout.readline()
        if not line:
            _, error = self.host.communicate(timeout=20)
            code, self.host = self.host.returncode, None
            self.fail(f"host failed during {operation}: exit={code}; stderr={error}")
        result = json.loads(line)
        self.assertEqual(result["status"] == 0, ok, result)
        self.last_rpc = result
        return result["result"]

    def command(self, op, candidate=None, ok=True, **fields):
        return self.rpc(op, ok=ok, group_id="group", **({"candidate": candidate} if candidate is not None else {}), **fields)

    def new_work(self, name):
        spec = json.loads((SOURCE / "samples/documents/work.json").read_text())
        spec["work_id"] = name
        path = self.root / name
        self.cli("work", "start", path, self.write(name + ".json", spec))
        return path

    def setup_candidates(self, count=2, mode="current", actual=False, alias=False, parent_alias=False,
                         version=4, large=False):
        if actual:
            self.configure(version=version)
            if large:
                self.large_repository()
        else:
            self.repo = self.root / "main"
            self.repo.mkdir()
            (self.repo / "seed").write_text("unchanged\n")
            self.git("init", "-q")
            self.git("config", "user.email", "fixture@example.invalid")
            self.git("config", "user.name", "Fixture")
            self.git("add", ".")
            self.git("commit", "-qm", "fixture")
        self.original_repo = self.repo
        base = subprocess.check_output(["/usr/bin/git", "-C", str(self.repo), "rev-parse", "HEAD"], env=ENV).decode().strip()
        self.parent = self.new_work("parent")
        for name in ("admission", "trees"):
            (self.root / name).mkdir()
        self.members = []
        candidates = []
        for i in range(count):
            name = chr(97 + i)
            work = self.work if actual and i == 0 else self.new_work("child-" + name)
            work_id = "example-work" if actual and i == 0 else "child-" + name
            build, temp = self.root / ("build-" + name), self.root / ("tmp-" + name)
            build.mkdir()
            temp.mkdir()
            self.members.append(dict(id=name, work=str(work), tree=str(self.root / "trees" / work_id / name),
                                     build=str(build), temp=str(temp), environment="e" * 64))
            candidates.append(dict(id=name, work_id=work_id, session_id="agent-" + name,
                runtime_binding="a" * 64, environment_digest="e" * 64,
                resources=dict(cpu=1000, memory=1024, io=1, tokens=10, nano_cost=10)))
        if alias:
            self.members[1]["build"] = self.members[0]["build"]
        if parent_alias:
            self.members[0]["temp"] = str(self.parent)
        config = dict(parent=str(self.parent), admission=str(self.root / "admission"),
            repository=str(self.repo), worktrees=str(self.root / "trees"), base=base, mode=mode,
            members=self.members)
        self.host = subprocess.Popen([str(HELPER), str(self.write("host.json", config))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=ENV)
        for m in self.members:
            self.rpc("$provision", candidate=m["id"])
        self.manifest = dict(schema_version=1, group_id="group", parallel_opt_in=count > 1,
            task_digest="b" * 64, base_commit=base, gates_digest="c" * 64,
            protocol_digest="d" * 64, currency="USD",
            limits=dict(workers=min(count, 2), cpu=2000, memory=8192, io=2, tokens=100, nano_cost=100),
            candidates=candidates, cohort=None)

    def register(self):
        self.rpc("create", manifest=self.manifest)
        for m in self.members:
            self.command("enroll", m["id"])

    def launch(self, name):
        self.command("reserve", name)
        token = self.rpc("$grant")
        self.command("start", name, token=token)
        return token

    def settle(self, name, token, qa="", cost=2, tokens=3, known=True, cancelled=False, ok=True):
        proof = self.rpc("$proof")["digest"]
        return self.command("finish", name, ok=ok, token=token, termination=proof, qa=qa,
            cancelled=cancelled, tokens_known=known, cost_known=known,
            tokens=tokens if known else 0, nano_cost=cost if known else 0)

    def test_parallel_workers_isolated_and_bounded(self):
        self.setup_candidates(count=3, mode="worker")
        self.register()
        a, b = self.launch("a"), self.launch("b")
        trees = [Path(m["tree"]) for m in self.members[:2]]
        deadline = time.monotonic() + 3
        while not all((p / "worker.started").exists() for p in trees) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(all((p / "worker.started").exists() for p in trees))
        self.assertTrue(all(not (p / "worker.done").exists() for p in trees))
        self.command("reserve", "c", ok=False)
        self.settle("a", a, ok=False)
        for name, token in (("a", a), ("b", b)):
            self.rpc("$wait", candidate=name)
            self.settle(name, token)
            self.rpc("$ack", candidate=name, key="cf-group-" + name)
            tree = Path(self.members[ord(name) - 97]["tree"])
            self.assertEqual((tree / "worker.done").read_text(), "done")
        self.assertFalse((self.original_repo / "worker.started").exists())
        report = self.command("compare")
        self.assertEqual(report["decision"], "INCOMPARABLE")
        self.assertEqual(report["known_nano_cost"], 4)
        self.assertEqual(report["dispatch_intent_denominator"], 2)
        self.assertEqual(report["candidate_denominator"], 3)
        self.assertEqual(report["task_denominator"], 1)
        self.command("reserve", "c")

    def test_intent_failure_never_redispatches(self):
        self.setup_candidates(count=1)
        self.register()
        self.command("reserve", "a")
        token = self.rpc("$grant")
        self.rpc("$fail-start", value=True)
        self.command("start", "a", token=token, ok=False)
        self.rpc("$fail-start", value=False)
        self.command("start", "a", token=token, ok=False)
        self.assertEqual(self.last_rpc["starts"], 1)
        self.assertEqual(self.command("status")["candidates"][0]["state"], "START_INTENT")
        self.settle("a", token, cancelled=True)
        self.assertEqual(self.command("compare")["cancelled"], 1)

    def test_stale_token_and_unknown_cost_no_refund(self):
        self.setup_candidates()
        self.manifest["limits"]["nano_cost"] = 10
        self.register()
        token = self.launch("a")
        stale = {**token, "epoch": token["epoch"] + 1}
        self.settle("a", stale, ok=False)
        self.settle("a", token, known=False)
        self.settle("a", token, known=False)
        self.command("reserve", "b", ok=False)
        report = self.command("compare")
        self.assertFalse(report["cost_complete"])
        self.assertEqual(report["winner"], "")

    def test_actual_overrun_blocks_remaining_candidate(self):
        self.setup_candidates()
        self.register()
        token = self.launch("a")
        self.settle("a", token, cost=11)
        self.command("reserve", "b", ok=False)
        self.assertTrue(self.command("compare")["over_budget"])

    def test_overrun_blocks_already_granted_candidate(self):
        self.setup_candidates()
        self.register()
        token = self.launch("a")
        self.command("reserve", "b")
        other = self.rpc("$grant")
        self.settle("a", token, cost=11)
        self.command("start", "b", token=other, ok=False)
        self.assertEqual(self.last_rpc["starts"], 1)
        self.settle("b", other, cancelled=True, cost=0, tokens=0)

    def test_reopen_rejects_old_execution_token(self):
        self.setup_candidates(count=1)
        self.register()
        token = self.launch("a")
        self.rpc("$reopen")
        self.settle("a", token, ok=False)
        self.command("start", "a", token=token, ok=False)
        self.assertEqual(self.last_rpc["starts"], 1)
        current = self.rpc("$token", key="cf-group-a")
        self.settle("a", current)
        self.assertEqual(self.command("status")["candidates"][0]["state"], "FINISHED")

    def test_corrupt_and_missing_group_events(self):
        self.setup_candidates(count=1)
        self.register()
        self.stop_host()
        folder = self.parent / "candidate-groups/group"
        marker = folder / "0001"
        before = marker.read_bytes()
        marker.chmod(0o600)
        marker.write_bytes(b"0" * 64)
        self.raw("candidate", "status", self.parent, "group", ok=False)
        marker.write_bytes(before)
        self.raw("candidate", "status", self.parent, "group")
        marker.unlink()
        self.raw("candidate", "status", self.parent, "group", ok=False)

    def test_cohort_exports_group_not_attempt_success(self):
        self.setup_candidates()
        self.stop_host()
        members = []
        for i, arm in enumerate(("NON_USE", "PARTIAL_USE", "FULL_USE")):
            case = json.loads((SOURCE / "samples/research/case.json").read_text())
            case.update(work_id="parent", case_id="case-" + str(i))
            r = self.cli("research", "case", "create", self.parent, self.write("case.json", case), "case-" + str(i))
            members.append(dict(case_id=case["case_id"], case_digest=r["record_digest"], arm=arm, block_id="block"))
        protocol = dict(schema_version=1, unit="TASK_BEST_OF_N", candidate_count=2,
                        limits=self.manifest["limits"], currency="USD")
        receipt = self.cli("evidence", "put", self.parent, self.write("protocol.json", protocol))
        protocol_digest = receipt["digest"]
        digest = members[0]["case_digest"]
        self.manifest.update(protocol_digest=protocol_digest, task_digest=digest, gates_digest=digest)
        definition = dict(schema_version=1, work_id="parent", cohort_id="study", design="MATCHED_BLOCKS",
            members=members, protocol_digest=protocol_digest, task_digest=digest, evaluation_digest=digest,
            acceptance_digest=digest, environment_digest=digest)
        # Environment is a CAS-backed declared contract, not a provider score.
        for c, m in zip(self.manifest["candidates"], self.members):
            c["environment_digest"] = digest
            m["environment"] = digest
        cohort = self.cli("research", "cohort", "create", self.parent, self.write("cohort.json", definition), "cohort")
        self.manifest["cohort"] = dict(cohort_id="study", cohort_digest=cohort["record_digest"], case_id="case-2")
        config = json.loads((self.root / "host.json").read_text())
        config["members"] = self.members
        self.host = subprocess.Popen([str(HELPER), str(self.write("host.json", config))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=ENV)
        bad = copy.deepcopy(self.manifest)
        bad["limits"]["tokens"] += 1
        self.rpc("create", manifest=bad, ok=False)
        self.register()
        for name in ("a", "b"):
            token = self.launch(name)
            self.settle(name, token, cancelled=name == "b")
        self.command("cohort-record")
        self.command("cohort-record", ok=False)
        self.stop_host()
        result = self.cli("research", "compare", self.parent, "study")
        self.assertEqual(result["arms"][2]["declared_status_counts"]["NOT_DONE"], 1)

    def test_duplicate_identity_optin_alias_and_permissions(self):
        self.setup_candidates(alias=True)
        bad = copy.deepcopy(self.manifest)
        bad["parallel_opt_in"] = False
        self.rpc("create", manifest=bad, ok=False)
        for field in ("id", "work_id", "session_id"):
            bad = copy.deepcopy(self.manifest)
            bad["candidates"][1][field] = bad["candidates"][0][field]
            self.rpc("create", manifest=bad, ok=False)
        self.rpc("create", manifest=self.manifest)
        self.command("enroll", "a")
        self.command("enroll", "b", ok=False)
        self.command("reserve", "a", ok=False)
        self.command("enroll", "", ok=False)
        self.command("reserve", "a", parent=1, ok=False)
        self.rpc("$deny", value=True)
        self.command("compare", ok=False)
        self.command("status")

    def test_parent_work_cannot_be_a_candidate_output_root(self):
        self.setup_candidates(count=1, parent_alias=True)
        self.rpc("create", manifest=self.manifest)
        self.command("enroll", "a", ok=False)
        self.assertEqual(self.command("status")["candidates"][0]["state"], "PLANNED")

    def test_manifest_cli_rejects_ambiguous_schema(self):
        sample = json.loads((SOURCE / "samples/candidates/group.json").read_text())
        good = self.raw("candidate", "validate", self.write("manifest.json", sample)).strip()
        self.assertEqual(len(good), 64)
        for change in ({"schema_version": True}, {"schema_version": 2}, {"unknown": 1}, {"parallel_opt_in": 1}):
            self.raw("candidate", "validate", self.write("manifest.json", dict(sample, **change)), ok=False)
        malformed = json.dumps(sample).replace('"schema_version": 1', '"schema_version": 1,"schema_version": 1')
        self.raw("candidate", "validate", self.write("manifest.json", malformed), ok=False)
        sample["limits"]["tokens"] = 2 ** 63
        self.raw("candidate", "validate", self.write("manifest.json", sample), ok=False)

    def test_cancel_waits_for_termination(self):
        self.setup_candidates(count=1, mode="worker")
        self.register()
        token = self.launch("a")
        self.command("cancel", "a", token=token)
        self.assertEqual(self.command("status")["candidates"][0]["state"], "CANCEL_REQUESTED")
        self.rpc("$wait", candidate="a")
        self.settle("a", token, cancelled=True)
        self.rpc("$ack", candidate="a", key="cf-group-a")
        report = self.command("compare")
        self.assertEqual(report["cancelled"], 1)
        self.assertEqual(report["known_nano_cost"], 2)
        self.assertEqual(report["decision"], "INCOMPARABLE")

    def test_real_qa_selection_and_stale_source(self):
        self.check_qa_selection()

    def test_v5_large_qa_selection_and_target(self):
        self.check_qa_selection(version=5, target_version=5, large=True)

    def test_v4_candidate_v5_target_compatibility(self):
        self.check_qa_selection(target_version=5)

    def check_qa_selection(self, version=4, target_version=4, large=False):
        self.setup_candidates(count=1, actual=True, version=version, large=large)
        self.repo = Path(self.members[0]["tree"])
        self.contract["snapshot_plan"]["repositories"][0]["root"] = str(self.repo)
        self.approval = self.raw("execution", "validate", self.write("candidate-contract.json", self.contract)).strip()
        self.prepare()
        self.manifest["gates_digest"] = self.raw("candidate", "gates", self.work, self.cp["receipt_digest"]).strip()
        self.register()
        token = self.launch("a")
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="candidate-qa")
        self.assertEqual(qa["record"]["status"], "PASS")
        self.settle("a", token, qa=qa["receipt_digest"])
        self.rpc("$seal", candidate="a")
        report = self.command("compare")
        self.assertEqual(report["decision"], "SOLE_PASS", report)
        self.assertEqual(report, self.command("compare"))
        self.assertEqual(report["winner"], "a")
        if version == 5:
            ref = qa["record"]["snapshot"]["repositories"][0]["inventory_ref"]
            path = self.object_path(ref["digest"])
            saved = path.read_bytes()
            self.assertEqual(len(json.loads(saved)["entries"]), 1024 if large else 4)
            backup = path.with_name(path.name + ".backup")
            path.rename(backup)
            self.assertEqual(self.command("compare")["decision"], "INCOMPARABLE")
            backup.rename(path)
            path.chmod(0o600)
            path.write_bytes(b"x" * len(saved))
            self.assertEqual(self.command("compare")["decision"], "INCOMPARABLE")
            path.write_bytes(saved)
            path.chmod(0o400)
            self.assertEqual(self.command("compare")["decision"], "SOLE_PASS")
        selected = self.command("select", "a")
        self.assertFalse(selected["selection"]["merge_authorized"])
        self.assertTrue(selected["selection"]["requires_target_revalidation"])
        self.command("target-check", "a", qa=qa["receipt_digest"], ok=False)
        for extra in (False, True):
            target = Changes("runTest")
            target.setUp()
            try:
                target.work_id = "target-work"
                target.configure(version=target_version)
                target.repo = target.root / "target-repo"
                subprocess.run(["/usr/bin/git", "clone", "--quiet", "--no-hardlinks",
                                str(self.original_repo), str(target.repo)], check=True, env=ENV)
                if extra:
                    (target.repo / ("source-1019.c" if large else "unrelated")).write_text("not selected\n")
                target.contract["snapshot_plan"]["repositories"][0]["root"] = str(target.repo)
                target.approval = target.raw("execution", "validate",
                    target.write("target-contract.json", target.contract)).strip()
                target.prepare()
                (target.repo / "logic.c").write_bytes((self.repo / "logic.c").read_bytes())
                target.finish()
                target_qa = target.call("run", checkpoint=target.cp["receipt_digest"], attempt_id="target-qa")
                self.assertEqual(target_qa["record"]["status"], "PASS")
                self.rpc("$target", binding=dict(work=str(target.work), tree=str(target.repo), environment="e"*64))
                checked = self.command("target-check", "a", qa=target_qa["receipt_digest"], ok=not extra)
                if not extra:
                    self.assertTrue(checked["selected_patch_verified"])
                    self.assertFalse(checked["merge_authorized"])
                    self.assertEqual(len(checked["scoped_patch_identity"]), 64)
                    (target.repo / "after-qa").write_text("stale")
                    self.command("target-check", "a", qa=target_qa["receipt_digest"], ok=False)
            finally:
                target.tearDown()
        (self.repo / "late-change.c").write_text("late edit\n")
        self.assertEqual(self.command("compare")["decision"], "INCOMPARABLE")
        self.command("select", "a", ok=False)
        self.assertEqual((self.original_repo / "user.txt").read_text(), "preexisting uncommitted user work\n")


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Candidates(name) for name in Candidates.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
