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

if __name__=='__main__':unittest.main()
