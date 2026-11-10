"""Disposable D5 admission/lifetime fixtures; no installed client or live Work."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

import integration_contract as c
import integration_distribution_entry as entry
import integration_feature_profiles as profiles
import integration_lifecycle as life
import integration_mutations as mutations
import test_integration_mutations as fixture


class Participation(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.D4()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.registry = self.fixture.registry
        self.bindings = [self.fixture.query()["binding"]]

    def admission(self):
        return life.CallAdmission(self.registry, self.bindings)

    def participants(self):
        return sorted(self.registry.root.glob("d5-client-*"))

    def files(self):
        return {str(p.relative_to(self.registry.root)): c.sha(p.read_bytes())
                for p in self.registry.root.rglob("*") if p.is_file()}

    def backend(self):
        service = Mock()
        service.tools.return_value = ["projects_list"]
        service.call.return_value = {"state": "OBSERVED"}
        return service

    def freeze(self):
        with self.registry.locked(exclusive=True):
            life.publish(self.registry, "p", "FROZEN", "fixture-freeze", {})

    def error(self, code, callback):
        with self.assertRaises(c.IntegrationError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_fifty_unused_contexts_and_metadata_leave_registry_identical(self):
        before = self.files()
        service = self.backend()
        for _ in range(50):
            with self.admission() as admission:
                wrapped = life.AdmittedService(service, admission)
                self.assertEqual(wrapped.tools(), ["projects_list"])
                self.assertEqual(wrapped.tools(), ["projects_list"])
        service.call.assert_not_called()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.participants(), [])

    def test_first_call_retains_one_record_until_close_and_never_deletes_it(self):
        service = self.backend()
        admission = self.admission()
        with admission:
            wrapped = life.AdmittedService(service, admission)
            self.assertEqual(self.participants(), [])
            for index in range(3):
                wrapped.call("projects_list", {"fixture_index": index})
            self.assertEqual(len(self.participants()), 1)
            self.error("PARTICIPANT_OR_WRITER_LIVE", lambda: life.quiet(self.registry, "p"))
            retained = self.files()
        life.quiet(self.registry, "p")
        self.assertEqual(retained, self.files())
        self.assertEqual(service.call.call_count, 3)
        self.error("PARTICIPATION_CLOSED", lambda: wrapped.call("projects_list", {}))
        self.assertEqual(service.call.call_count, 3)
        admission.close()
        self.assertEqual(retained, self.files())

    def test_concurrent_first_calls_share_one_participant_without_serializing_bodies(self):
        service = self.backend()
        entered = threading.Barrier(3)
        release = threading.Event()
        def body(name, args):
            entered.wait(timeout=5)
            if not release.wait(5):
                raise AssertionError("fixture call was not released")
            return args
        service.call.side_effect = body
        with self.admission() as admission, ThreadPoolExecutor(max_workers=2) as pool:
            wrapped = life.AdmittedService(service, admission)
            futures = [pool.submit(wrapped.call, "projects_list", {"index": index}) for index in range(2)]
            try:
                entered.wait(timeout=5)
                self.assertEqual(len(self.participants()), 1)
                self.error("PARTICIPANT_OR_WRITER_LIVE", lambda: life.quiet(self.registry, "p"))
            finally:
                release.set()
            self.assertEqual([f.result(timeout=5) for f in futures], [{"index": 0}, {"index": 1}])
        self.assertEqual(service.call.call_count, 2)
        life.quiet(self.registry, "p")

    def test_close_waits_for_inflight_body_before_releasing_kernel_lock(self):
        entered, release, closing, closed = [threading.Event() for _ in range(4)]
        service = self.backend()
        def body(*args):
            entered.set()
            if not release.wait(5):
                raise AssertionError("fixture call was not released")
            return {"state": "COMMIT_UNKNOWN"}
        service.call.side_effect = body
        admission = self.admission()
        self.addCleanup(admission.close)
        wrapped = life.AdmittedService(service, admission)
        def close():
            closing.set()
            admission.close()
            closed.set()
        with ThreadPoolExecutor(max_workers=2) as pool:
            call = pool.submit(wrapped.call, "projects_list", {})
            self.assertTrue(entered.wait(5))
            cleanup = pool.submit(close)
            self.assertTrue(closing.wait(5))
            try:
                self.assertFalse(closed.wait(0.05))
                self.error("PARTICIPANT_OR_WRITER_LIVE", lambda: life.quiet(self.registry, "p"))
                self.error("PARTICIPATION_CLOSED", lambda: wrapped.call("projects_list", {}))
            finally:
                release.set()
            self.assertEqual(call.result(timeout=5), {"state": "COMMIT_UNKNOWN"})
            cleanup.result(timeout=5)
        self.assertTrue(closed.is_set())
        life.quiet(self.registry, "p")
        self.assertEqual(len(self.participants()), 1)

    def test_unused_connection_does_not_block_freeze_and_first_call_is_fenced(self):
        service = self.backend()
        with self.admission() as admission:
            wrapped = life.AdmittedService(service, admission)
            self.freeze()
            life.quiet(self.registry, "p")
            before = self.files()
            for _ in range(2):
                self.error("PROJECT_MAINTENANCE", lambda: wrapped.call("projects_list", {}))
            self.assertEqual(self.files(), before)
            self.assertEqual(self.participants(), [])
            service.call.assert_not_called()

    def test_used_connection_blocks_drain_and_existing_action_fence_still_applies(self):
        api = self.fixture.api()
        original_work = self.fixture.inventory()
        with self.admission() as admission:
            wrapped = life.AdmittedService(api, admission)
            wrapped.call("projects_list", {})
            self.freeze()
            self.error("PARTICIPANT_OR_WRITER_LIVE", lambda: life.quiet(self.registry, "p"))
            with patch.object(mutations.records, "capture") as capture:
                self.error("PROJECT_MAINTENANCE", lambda: wrapped.call("session_claim", self.fixture.args))
            capture.assert_not_called()
        life.quiet(self.registry, "p")
        self.assertEqual(original_work, self.fixture.inventory())

    def test_partial_admission_failure_is_terminal_and_retains_partial_record(self):
        service = self.backend()
        with self.admission() as admission:
            wrapped = life.AdmittedService(service, admission)
            with patch.object(life.records, "save", side_effect=OSError("fixture full disk")) as save:
                with self.assertRaises(OSError):
                    wrapped.call("projects_list", {})
                retained = self.files()
                self.assertEqual(len(self.participants()), 1)
                self.assertTrue((self.participants()[0] / "live.lock").is_file())
                self.assertFalse((self.participants()[0] / "participant.json").exists())
                self.error("PARTICIPATION_ADMISSION_FAILED", lambda: wrapped.call("projects_list", {}))
                self.assertEqual(save.call_count, 1)
            service.call.assert_not_called()
        self.assertEqual(retained, self.files())

    def test_only_pre_admission_registry_busy_waits_and_never_retries_call_body(self):
        original = life.participation
        entries = []
        @contextmanager
        def contended(*args):
            entries.append(True)
            if len(entries) == 1:
                raise c.IntegrationError("REGISTRY_BUSY")
            with original(*args) as result:
                yield result
        service = self.backend()
        service.call.side_effect = c.IntegrationError("REGISTRY_BUSY")
        with patch.object(life, "participation", contended), patch.object(life.time, "sleep") as pause:
            with self.admission() as admission:
                wrapped = life.AdmittedService(service, admission)
                self.error("REGISTRY_BUSY", lambda: wrapped.call("projects_list", {}))
            pause.assert_called_once_with(0.05)
        self.assertEqual(len(entries), 2)
        self.assertEqual(service.call.call_count, 1)
        self.assertEqual(len(self.participants()), 1)

    def test_admission_busy_deadline_is_bounded_and_failure_is_terminal(self):
        @contextmanager
        def busy(*args):
            raise c.IntegrationError("REGISTRY_BUSY")
            yield
        service = self.backend()
        with patch.object(life, "participation", side_effect=busy) as participate, \
             patch.object(life.time, "monotonic", side_effect=[0, 5]), patch.object(life.time, "sleep") as pause:
            with self.admission() as admission:
                wrapped = life.AdmittedService(service, admission)
                for _ in range(2):
                    self.error("REGISTRY_BUSY", lambda: wrapped.call("projects_list", {}))
            self.assertEqual(participate.call_count, 1)
            pause.assert_not_called()
        service.call.assert_not_called()
        self.assertEqual(self.participants(), [])

    def test_d1_revocation_after_discovery_still_prevents_native_dispatch(self):
        api = self.fixture.api()
        api.tools()
        self.fixture.approve("revoke")
        with self.admission() as admission, patch.object(mutations.records, "capture") as capture:
            wrapped = life.AdmittedService(api, admission)
            self.error("PROJECT_APPROVAL_REQUIRED", lambda: wrapped.call("session_claim", self.fixture.args))
        capture.assert_not_called()

    def test_policy_drift_after_discovery_still_prevents_native_dispatch(self):
        api = self.fixture.api()
        api.tools()
        self.fixture.mutation_path.write_bytes(self.fixture.mutation_path.read_bytes() + b" ")
        with self.admission() as admission, patch.object(mutations.records, "capture") as capture:
            wrapped = life.AdmittedService(api, admission)
            self.error("MUTATION_POLICY_CHANGED", lambda: wrapped.call("session_claim", self.fixture.args))
        capture.assert_not_called()

    def test_native_pin_drift_after_discovery_still_prevents_dispatch(self):
        api = self.fixture.api()
        api.tools()
        self.fixture.cli.write_bytes(self.fixture.cli.read_bytes() + b"\n# changed fixture\n")
        with self.admission() as admission, patch.object(mutations.records, "capture") as capture:
            wrapped = life.AdmittedService(api, admission)
            self.error("PIN_MISMATCH", lambda: wrapped.call("session_claim", self.fixture.args))
        capture.assert_not_called()

    def test_uncertain_result_reuses_existing_guard_and_never_redispatches(self):
        api = self.fixture.api()
        original_work = self.fixture.inventory()
        with self.admission() as admission, patch.object(api, "_preflight", self.fixture.preflight), \
             patch.object(mutations.records, "capture", side_effect=OSError("fixture response lost")) as capture:
            wrapped = life.AdmittedService(api, admission)
            first = wrapped.call("session_claim", self.fixture.args)
            self.assertEqual(first["state"], "COMMIT_UNKNOWN")
            self.assertEqual(wrapped.call("session_claim", self.fixture.args), first)
            self.error("WORK_MUTATION_UNRESOLVED", lambda: wrapped.call("session_claim", {**self.fixture.args, "request_id": "other"}))
            self.assertEqual(capture.call_count, 1)
            self.assertEqual(len(self.participants()), 1)
        self.assertEqual(original_work, self.fixture.inventory())

    def test_connection_reuses_outer_admission_and_leaves_d2_contract_unchanged(self):
        api = self.fixture.api()
        owner = api.policy
        for name in ("read", "prepare"):
            scoped = profiles.Scoped(api.reads, name)
            with entry.connection(scoped, owner) as selected:
                self.assertIs(selected, scoped)
            self.assertEqual(self.participants(), [])
        scoped = profiles.Scoped(api, "task")
        with entry.connection(scoped, owner) as outer:
            with entry.connection(outer, owner) as inner:
                self.assertIs(inner, outer)
                inner.call("projects_list", {})
            self.error("PARTICIPANT_OR_WRITER_LIVE", lambda: life.quiet(self.registry, "p"))
        self.assertEqual(len(self.participants()), 1)
        life.quiet(self.registry, "p")

    def test_two_processes_compete_for_last_slot_without_raising_the_quota(self):
        for _ in range(127):
            with life.participation(self.registry, self.bindings):
                pass
        retained = self.files()
        code = '''
import json,sys
sys.path.insert(0,sys.argv[1])
from pathlib import Path
import integration_contract as c
import integration_registry as r
import integration_lifecycle as life
registry=r.Registry(Path(sys.argv[2]));bindings=json.loads(sys.argv[3])
print('READY',flush=True);sys.stdin.readline()
try:
 with life.CallAdmission(registry,bindings) as admission:
  with admission.operation(): print('ADMITTED',flush=True)
except c.IntegrationError as error: print(error.code,flush=True)
'''
        children = [subprocess.Popen([sys.executable, "-I", "-B", "-c", code,
                    str(Path(__file__).parent), str(self.registry.root), json.dumps(self.bindings)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    for _ in range(2)]
        try:
            for child in children:
                self.assertEqual(child.stdout.readline().strip(), "READY")
            for child in children:
                child.stdin.write("GO\n"); child.stdin.flush()
            results = [child.communicate(timeout=10) for child in children]
            self.assertEqual(sorted(out.strip() for out, err in results), ["ADMITTED", "PARTICIPATION_QUOTA"])
            self.assertTrue(all(child.returncode == 0 for child in children))
            self.assertTrue(all(not err for out, err in results))
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill(); child.communicate()
        self.assertEqual(len(self.participants()), 128)
        after = self.files()
        for name, digest in retained.items():
            self.assertEqual(after[name], digest)
        life.quiet(self.registry, "p")
        service = self.backend()
        with self.admission() as admission:
            wrapped = life.AdmittedService(service, admission)
            self.assertEqual(wrapped.tools(), ["projects_list"])
            self.error("PARTICIPATION_QUOTA", lambda: wrapped.call("projects_list", {}))
        service.call.assert_not_called()
        self.assertEqual(len(self.participants()), 128)

    def test_fifty_actual_sdk_stdio_discoveries_cover_all_four_desktop_entries(self):
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            self.skipTest("pinned MCP SDK fixture dependencies unavailable")
        # Existing immutable participation remains intact; discovery must not
        # consume the one remaining slot or execute this synthetic native CLI.
        for _ in range(127):
            with life.participation(self.registry, self.bindings):
                pass
        self.fixture.policy["scopes"][0]["tools"] = ["projects_list", "work_inspect"]
        self.fixture.save_policy()
        self.fixture.repin()
        # Keep the public D4 schema's existing exact claim action unused.
        # Discovery must stay side-effect free even when an action is exposed.
        digest = self.fixture.mutation_digest
        before, work_before = self.files(), self.fixture.inventory()
        code = '''
import builtins,os,sys
tools,policy,digest,mode=sys.argv[1:];sys.path.insert(0,tools)
import execution_record as records
def forbidden(*a,**kw):raise AssertionError('discovery must not dispatch native work')
records.capture=forbidden
original=builtins.__import__
def imported(name,*a,**kw):
 if name.startswith('tkinter'):raise AssertionError('discovery must not import Tk')
 return original(name,*a,**kw)
builtins.__import__=imported
if mode=='direct':
 import integration_mutation_mcp as module
 sys.argv=['golem','--policy',policy,'--reviewed-policy-sha256',digest,'--approve-mutations']
elif mode=='management':
 import integration_owner_maintenance as module
 for key in list(os.environ):
  if key.startswith('GOLEM_'):del os.environ[key]
 os.environ.update(GOLEM_FEATURE_PROFILE='task',GOLEM_PROFILE_POLICY=policy,GOLEM_PROFILE_POLICY_SHA256=digest,GOLEM_APPROVE_PROFILE_OWNER='true')
 sys.argv=['golem','mcp']
elif mode=='owner':
 import integration_owner_desktop as module
 sys.argv=['golem','--profile','task','--policy',policy,'--reviewed-policy-sha256',digest,'--approve-owner','--approve-owner-review-ui']
else:
 import integration_distribution_entry as module
 sys.argv=['golem','--profile','task','--policy',policy,'--reviewed-policy-sha256',digest,'--approve-owner']
raise SystemExit(module.main())
'''
        modes = ("distribution", "direct", "management", "owner")
        async def check(mode, call=False):
            params = StdioServerParameters(command=sys.executable, args=["-I", "-B", "-c", code,
                str(Path(__file__).parent), str(self.fixture.mutation_path), digest, mode])
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()
                    for _ in range(2):
                        listed = await client.list_tools()
                        self.assertEqual(sorted(t.name for t in listed.tools), ["golem_projects_list", "golem_session_claim", "golem_work_inspect"])
                    if call:
                        reply = await client.call_tool("golem_projects_list", {})
                        return json.loads(reply.content[0].text)
        async def discover():
            semaphore = asyncio.Semaphore(5)
            async def one(index):
                async with semaphore:
                    await check(modes[index % len(modes)])
            await asyncio.gather(*(one(index) for index in range(50)))
        asyncio.run(discover())
        self.assertEqual(self.files(), before)
        self.assertEqual(self.fixture.inventory(), work_before)
        self.assertEqual(len(self.participants()), 127)
        self.assertEqual(asyncio.run(check("distribution", call=True))["state"], "AVAILABLE")
        self.assertEqual(len(self.participants()), 128)
        rejected = asyncio.run(check("direct", call=True))
        self.assertEqual(rejected["code"], "PARTICIPATION_QUOTA")
        self.assertEqual(len(self.participants()), 128)
        self.assertEqual(self.fixture.inventory(), work_before)
        life.quiet(self.registry, "p")

    def test_actual_stdio_eof_waits_for_dispatched_worker_and_preserves_participant(self):
        try:
            import mcp
        except ImportError:
            self.skipTest("pinned MCP SDK fixture dependencies unavailable")
        started = self.fixture.root / "worker-started"
        release = self.fixture.root / "worker-release"
        finished = self.fixture.root / "worker-finished"
        original_work = self.fixture.inventory()
        code = '''
import asyncio,sys,time
from pathlib import Path
tools,policy,digest,started,release,finished=sys.argv[1:];sys.path.insert(0,tools)
import integration_distribution_entry as entry
import execution_record as records
def forbidden(*a,**kw):raise AssertionError('fixture must not execute native work')
records.capture=forbidden
service,owner=entry.configure('task',policy,digest,approve_owner=True)
original=service.call
def blocked(name,args):
 Path(started).write_text('one call')
 deadline=time.monotonic()+8
 while not Path(release).exists():
  if time.monotonic()>=deadline:raise AssertionError('fixture worker release missing')
  time.sleep(.01)
 value=original(name,args)
 Path(finished).write_text('body finished')
 return value
service.call=blocked
asyncio.run(entry.serve(service,owner))
'''
        child = subprocess.Popen([sys.executable, "-I", "-B", "-c", code,
            str(Path(__file__).parent), str(self.fixture.mutation_path), self.fixture.mutation_digest,
            str(started), str(release), str(finished)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def send(value):
            child.stdin.write(json.dumps(value) + "\n")
            child.stdin.flush()
        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "disposable-eof-fixture", "version": "1"}}})
            initialized = json.loads(child.stdout.readline())
            self.assertEqual(initialized["id"], 1)
            self.assertIn("result", initialized)
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "golem_projects_list", "arguments": {}}})
            deadline = time.monotonic() + 5
            while not started.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(started.is_file())
            child.stdin.close()
            child.stdin = None
            self.freeze()
            self.error("PARTICIPANT_OR_WRITER_LIVE", lambda: life.quiet(self.registry, "p"))
            with self.assertRaises(subprocess.TimeoutExpired):
                child.wait(timeout=0.05)
            self.assertFalse(finished.exists())
            release.write_text("release only this fixture worker")
            out, err = child.communicate(timeout=8)
            self.assertEqual(child.returncode, 0, err)
            self.assertTrue(finished.is_file())
            self.assertEqual(len(self.participants()), 1)
            retained = self.files()
            life.quiet(self.registry, "p")
            self.assertEqual(self.files(), retained)
            self.assertEqual(self.fixture.inventory(), original_work)
        finally:
            release.write_text("release fixture cleanup")
            if child.poll() is None:
                child.kill(); child.communicate()


if __name__ == "__main__":
    unittest.main()
