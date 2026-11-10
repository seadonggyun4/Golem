"""M6 independent guard regressions; inspected product modules never executed."""
import ast
import copy
import hashlib
from dataclasses import replace
from pathlib import Path
import unittest
from capability_files import SourceFile
from capability_ledger import decode_identified_ledger
from capability_m1 import _functions
from capability_fallback import _shape
from capability_c_graph import fingerprint
from capability_m6 import inspect_m6
from capability_m6_registry import M6
from capability_m6_backlog_registry import M6_BACKLOG

class DistributionProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[1]
        cls.files=tuple(SourceFile(p,hashlib.sha256((cls.root/p).read_bytes()).hexdigest(),(cls.root/p).read_bytes()) for p,_ in M6['pins'])
        cls.ledger=decode_identified_ledger((cls.root/'docs/mcp-m0-observations.json').read_bytes())
    def changed(self,path,old,new,shapes=False):
        model=copy.deepcopy(M6);files=[]
        for f in self.files:
            if f.path==path:
                self.assertIn(old,f.data);raw=f.data.replace(old,new,1);f=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
                model['pins']=tuple((p,f.sha256 if p==path else h) for p,h in model['pins'])
                if shapes:
                    functions=_functions(ast.parse(raw));model['functions']=tuple((p,n,fingerprint(_shape(functions[n])) if p==path else h) for p,n,h in model['functions'])
            files.append(f)
        return tuple(files),model
    def inspect(self,files=None,model=None,backlog=None,ledger=None):
        return inspect_m6(self.files if files is None else files,self.ledger if ledger is None else ledger,M6 if model is None else model,M6_BACKLOG if backlog is None else backlog)
    def test_current_source_and_83_owner_boundaries_are_preserved(self):
        result=self.inspect();self.assertFalse(result.blockers,result.blockers);self.assertEqual(result.owner_backlog_count,83)
        self.assertEqual(len(result.profiles),5);self.assertFalse(result.owner_backlog_discharged);self.assertEqual(result.actual_reload,'NOT_RUN')
    def test_missing_source_and_byte_drift_block(self):
        self.assertTrue(self.inspect(files=()).blockers)
        files,_=self.changed('tools/integration_feature_profiles.py',b'FEATURE_PROFILE_UNKNOWN',b'CHANGED');self.assertTrue(self.inspect(files=files).blockers)
    def test_owner_intersection_and_direct_call_guards_survive_repin(self):
        for old in (b"c.require(name in self.profile['tools'],'FEATURE_PROFILE_SCOPE')",b"c.require(name in self.service.tools(),'FEATURE_OWNER_SCOPE')"):
            files,model=self.changed('tools/integration_feature_profiles.py',old,b'pass',True);self.assertTrue(self.inspect(files,model).blockers)
    def test_profile_does_not_supply_policy_consent_or_separate_effects(self):
        files,model=self.changed('tools/integration_feature_profiles.py',b"'grants_created':False",b"'grants_created':True",True);self.assertTrue(self.inspect(files,model).blockers)
        for old in (b"c.require(approve_owner is True,'OWNER_PROFILE_APPROVAL_REQUIRED')",b"c.require(not helper or profile=='quality','FEATURE_HELPER_SCOPE')",b"c.require(not host or profile=='parallel','FEATURE_HOST_SCOPE')"):
            files,model=self.changed('tools/integration_distribution_entry.py',old,b'pass',True);self.assertTrue(self.inspect(files,model).blockers)
    def test_original_digest_and_native_owner_apply_paths_remain_exact(self):
        for old,new in ((b'approve_installation=True,repair=False',b'approve_installation=True,repair=True'),(b'approve_maintenance=True',b'approve_maintenance=False')):
            files,model=self.changed('tools/integration_owner_maintenance.py',old,new,True);self.assertTrue(self.inspect(files,model).blockers)
    def test_immutable_files_and_new_destination_guard_cannot_disappear(self):
        for old in (b"c._validate(inventory,INVENTORY)",b"c.require(set(payloads)==allowed,'PACKAGE_FILE_SCOPE')",b"c.require(not destination.exists() and not destination.is_symlink(),'PACKAGE_DESTINATION_EXISTS')"):
            files,model=self.changed('tools/integration_distribution.py',old,b'pass',True);self.assertTrue(self.inspect(files,model).blockers)
    def test_review_package_cannot_claim_signed_installed_or_self_contained(self):
        for old,new in ((b"'self_contained':False",b"'self_contained':True"),(b"'signature':'NOT_IMPLEMENTED'",b"'signature':'VERIFIED'"),(b"'installed':False",b"'installed':True")):
            files,model=self.changed('tools/integration_distribution.py',old,new,True);self.assertTrue(self.inspect(files,model).blockers)
    def test_owner_backlog_cannot_be_deleted_or_promoted_to_verified_installation(self):
        self.assertTrue(self.inspect(backlog=M6_BACKLOG[1:]).blockers)
        rows=copy.deepcopy(M6_BACKLOG);rows[0]['actual_installation']='PASS';self.assertTrue(self.inspect(backlog=rows).blockers)
        ledger=copy.deepcopy(self.ledger);cap=next(cap for cap in ledger['capabilities'] if cap['id']==M6_BACKLOG[0]['capability_id']);cap['current_routes']=[]
        self.assertTrue(self.inspect(ledger=ledger).blockers)

    def test_startup_wait_cannot_expand_to_action_retry_or_other_errors_after_repin(self):
        for old,new in ((b"error.code != 'REGISTRY_BUSY'",b"error.code != 'COMMIT_UNKNOWN'"),
                        (b'STARTUP_WAIT_SECONDS = 5',b'STARTUP_WAIT_SECONDS = 500'),
                        (b'return configure(**args)',b'return service.call("execution_request", args)'),
                        (b'except c.IntegrationError as error:',b'except Exception as error:')):
            files,model=self.changed('tools/integration_distribution_entry.py',old,new,True)
            self.assertTrue(self.inspect(files,model).blockers)

    def assert_lifecycle_guard(self,path,old,new):
        files,model=self.changed(path,old,new,True)
        blockers=self.inspect(files,model).blockers
        self.assertTrue(any(code=='M6_OWNER_LIFECYCLE_CHANGED' for code,_ in blockers),blockers)
        self.assertFalse(any(code in ('M6_SOURCE_MISSING_OR_DRIFT','M6_FUNCTION_CHANGED') for code,_ in blockers),blockers)

    def test_lazy_functions_cannot_be_omitted_from_the_review_model(self):
        for name in ('CallAdmission.operation','AdmittedService.call','connection'):
            model=copy.deepcopy(M6)
            model['functions']=tuple(row for row in model['functions'] if row[1]!=name)
            self.assertIn(('M6_OWNER_LIFECYCLE_CHANGED','M6_LAZY_FUNCTION_MODEL_MISSING'),self.inspect(model=model).blockers)

    def test_lazy_admission_reuses_finite_registry_busy_only_wait(self):
        for old,new in ((b"error.code == 'REGISTRY_BUSY'",b"error.code == 'COMMIT_UNKNOWN'"),
                        (b'time.monotonic() + 5',b'time.monotonic() + 500'),
                        (b'candidate.__enter__()',b'self.service.call("execution_request", {})'),
                        (b'except c.IntegrationError as error:',b'except Exception as error:')):
            self.assert_lifecycle_guard('tools/integration_lifecycle.py',old,new)

    def test_lazy_call_failure_and_close_cannot_reset_or_release_early(self):
        for old,new in ((b"c.require(not self._closed, 'PARTICIPATION_CLOSED')",b'pass'),
                        (b"c.require(self._failure is None, self._failure or 'PARTICIPATION_ADMISSION_FAILED')",b'pass'),
                        (b"self._failure = getattr(error, 'code', 'PARTICIPATION_ADMISSION_FAILED')",b'self._failure = None'),
                        (b'self._inflight += 1',b'self._inflight += 0'),
                        (b'while self._inflight:',b'while False:'),
                        (b'self._condition.wait()',b'pass'),
                        (b'participant.__exit__(None, None, None)',b'pass')):
            self.assert_lifecycle_guard('tools/integration_lifecycle.py',old,new)

    def test_lazy_actual_call_must_be_inside_operation_context(self):
        self.assert_lifecycle_guard('tools/integration_lifecycle.py',
            b'with self.admission.operation():\n            return self._service.call(name, args)',
            b'with self.admission.operation():\n            pass\n        return self._service.call(name, args)')
        self.assert_lifecycle_guard('tools/integration_lifecycle.py',
            b'return getattr(self._service, name)',
            b'with self.admission.operation():\n            return getattr(self._service, name)')

    def test_lazy_discovery_cannot_reintroduce_eager_participation(self):
        self.assert_lifecycle_guard('tools/integration_distribution_entry.py',
            b'with connection(service,owner) as admitted:',
            b'with lifecycle.participation(owner.registry, []) as admitted:')
        self.assert_lifecycle_guard('tools/integration_mcp.py',
            b'names = await listed_tools(service)',
            b'with service.admission.operation():\n            names = await listed_tools(service)')
        self.assert_lifecycle_guard('tools/integration_reload_probe.py',
            b'runtime_before = runtime()',
            b'runtime_before = runtime()\n    life.CallAdmission(None, [])')

    def test_lazy_connection_preserves_d2_bypass_and_same_guard_reuse(self):
        for old,new in ((b"service.profile['family']=='D2' or isinstance(service,lifecycle.AdmittedService)",b"service.profile['family']=='D4' or isinstance(service,lifecycle.AdmittedService)"),
                        (b'yield lifecycle.AdmittedService(service,admission)',b'yield service'),
                        (b'await mutation_mcp.run(admitted)',b'await mutation_mcp.run(service)')):
            self.assert_lifecycle_guard('tools/integration_distribution_entry.py',old,new)

    def test_direct_and_management_transports_cannot_handoff_raw_service(self):
        self.assert_lifecycle_guard('tools/integration_mutation_mcp.py',
            b'asyncio.run(run(lifecycle.AdmittedService(service, admission)))',b'asyncio.run(run(service))')
        self.assert_lifecycle_guard('tools/integration_owner_maintenance.py',
            b'instance=management_server(admitted)',b'instance=management_server(service)')
        self.assert_lifecycle_guard('tools/integration_owner_maintenance.py',
            b'asyncio.run(run(admitted))',b'asyncio.run(run(service))')
        self.assert_lifecycle_guard('tools/integration_owner_maintenance.py',
            b"finally:await __import__('anyio').to_thread.run_sync(service.close)",b'finally:pass')

    def test_owner_export_and_worker_join_remain_inside_connection(self):
        self.assert_lifecycle_guard('tools/integration_owner_desktop.py',
            b'with entry.connection(scoped,owner) as scoped:',b'with nullcontext(scoped) as scoped:')
        self.assert_lifecycle_guard('tools/integration_owner_desktop.py',
            b'self.scoped.admission.operation() if isinstance(self.scoped,lifecycle.AdmittedService) else nullcontext()',b'nullcontext()')
        self.assert_lifecycle_guard('tools/integration_owner_desktop.py',
            b'finally:\n            if endpoint is not None:endpoint.close()',b'finally:\n            pass')

    def test_retained_participant_quota_freeze_and_drain_are_not_weakened(self):
        for old,new in ((b'len(list(registry.root.glob("d5-client-*"))) < 128',b'len(list(registry.root.glob("d5-client-*"))) < 1024'),
                        (b'len(clients) <= 128 and len(writers) <= 128',b'len(clients) <= 1024 and len(writers) <= 128'),
                        (b'fence(registry, binding["project_id"])',b'pass'),
                        (b'with registry.locked(exclusive=True):\n        from integration_backend import _quota',b'with registry.locked():\n        from integration_backend import _quota'),
                        (b'value is None or value["phase"] == "OPEN"',b'value is None or value["phase"] in ("OPEN", "FROZEN")')):
            self.assert_lifecycle_guard('tools/integration_lifecycle.py',old,new)

    def test_management_guards_and_exactly_once_reservation_survive_repin(self):
        for old in (b"c.require(approve_management is True,'MANAGEMENT_APPROVAL_REQUIRED')",
                    b"c.require(self.policy is not None,'MANAGEMENT_DISABLED')",
                    b"c.require(set(action['effects'])==set(required),'MANAGEMENT_EFFECTS_SCOPE')",
                    b"c.require(management_snapshot(path)==target['expected_sha256'],'MANAGEMENT_TARGET_STALE')",
                    b"life.fence(transfer.registry,args['project_id'])",
                    b"c.require(previous.get('state') not in ('COMMIT_UNKNOWN','PENDING_APPROVAL'),'MANAGEMENT_PROJECT_QUARANTINED')"):
            files,model=self.changed('tools/integration_owner_maintenance.py',old,b'pass',True)
            self.assertTrue(self.inspect(files,model).blockers)
        files,model=self.changed('tools/integration_owner_maintenance.py',b"records.save(guard,c.encoded({'intent':directory.name,**binding}))",b'pass',True)
        self.assertTrue(self.inspect(files,model).blockers)


    def test_delivery_scope_and_explicit_stop_guards_survive_repin(self):
        for old in (b"c.require(hasattr(self.base,'transfer'),'MANAGEMENT_HOST_REQUIRES_D4')",
                    b"c.require(owned is not None and owned.descriptor==inputs[request['input_id']]['sha256'],'MANAGEMENT_HOST_NOT_OWNED')",
                    b"c.require(any(a['request']==expected_stop and set(a['effects'])==set(MANAGEMENT_OPERATIONS['candidate_stop'][2]) for a in project['actions']),'MANAGEMENT_HOST_STOP_ACTION_REQUIRED')"):
            files,model=self.changed('tools/integration_owner_maintenance.py',old,b'pass',True)
            self.assertTrue(self.inspect(files,model).blockers)

    def test_owner_ipc_fence_and_no_automatic_window_survive_repin(self):
        for old,new in ((b"c.require(request not in self.seen,'OWNER_IPC_REPLAY')",b'pass'),
                        (b"c.require(key not in self.exports,'OWNER_EXPORT_ALREADY_ATTEMPTED')",b'pass'),
                        (b"c.require(args['confirmed'] is True,'OWNER_REVIEW_REQUIRED')",b'pass'),
                        (b'socket.AF_UNIX',b'socket.AF_INET'),
                        (b'        endpoint=None',b'        import tkinter\n        endpoint=None')):
            files,model=self.changed('tools/integration_owner_desktop.py',old,new,True)
            self.assertTrue(self.inspect(files,model).blockers)

if __name__=='__main__':unittest.main()
