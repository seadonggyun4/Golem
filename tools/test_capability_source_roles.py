import copy
import hashlib
import json
import unittest
from dataclasses import asdict,replace
from pathlib import Path

from capability_files import SourceFile
from capability_sample_registry import SOURCES
from capability_source_role_registry import SOURCE_ROLES
from capability_source_roles import observe_source_roles,source_role_cli_scan
from capability_connections import connect_inventory
from capability_audit import Audit


class DependencyRoles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.files=tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in SOURCES)
        cls.ledger=json.loads((root/'docs/mcp-m0-observations.json').read_bytes())

    def test_eight_complete_dependency_interfaces_keep_other_scope_blockers(self):
        original=tuple(('SCAN_UNRESOLVED',(r.path,None,'UNREGISTERED_SOURCE')) for r in SOURCE_ROLES)
        residual=('SCAN_UNRESOLVED',('src/cli/main.c','other_dispatch','C_RESIDUAL_SCOPE_UNVERIFIED'))
        result=connect_inventory(self.ledger,self.files,Audit((*original,residual),()))
        self.assertIn(residual,result.audit.blockers)
        self.assertFalse(set(original)&set(result.audit.blockers))
        for rule in SOURCE_ROLES:
            value=result.observations['source_role.'+rule.path]
            self.assertTrue(value['file_surface_reviewed'])
            self.assertFalse(value['execution_verified'])

    def test_profile_prerequisite_cannot_be_skipped(self):
        result=observe_source_roles(self.files,SOURCE_ROLES,{},self.ledger)
        self.assertTrue(next(v for v in result if v.path=='tools/integration_backend.py').blockers)
        self.assertTrue(next(v for v in result if v.path=='tools/integration_mutation_mcp.py').blockers)

    def test_new_function_with_repin_is_still_unreviewed_surface(self):
        rule=next(r for r in SOURCE_ROLES if r.path=='tools/integration_backend.py')
        source=next(f for f in self.files if f.path==rule.path)
        raw=source.data+b'\ndef new_feature(): pass\n'
        changed=replace(source,data=raw,sha256=hashlib.sha256(raw).hexdigest())
        result=observe_source_roles((changed,),(replace(rule,sha256=changed.sha256),),{'d1_backend':{'blockers':()}},self.ledger)
        self.assertIn(('SOURCE_SYMBOL_SET_CHANGED',rule.path),result[0].blockers)

    def test_source_drift_keeps_generic_obligation(self):
        rule=SOURCE_ROLES[0]
        files=tuple(replace(f,data=f.data+b'\n',sha256=hashlib.sha256(f.data+b'\n').hexdigest()) if f.path==rule.path else f for f in self.files)
        obligation=('SCAN_UNRESOLVED',(rule.path,None,'UNREGISTERED_SOURCE'))
        result=connect_inventory(self.ledger,files,Audit((obligation,),()))
        self.assertIn(obligation,result.audit.blockers)

    def test_new_private_prototype_does_not_get_header_exemption(self):
        rule=next(r for r in SOURCE_ROLES if r.path=='src/cli/output.h')
        f=next(f for f in self.files if f.path==rule.path)
        raw=f.data+b'\nint new_operation(void);\n';changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
        result=observe_source_roles((changed,),(replace(rule,sha256=changed.sha256),),{},self.ledger)
        self.assertTrue(result[0].blockers)

    def test_new_macro_with_repin_does_not_get_whole_header_exemption(self):
        rule=next(r for r in SOURCE_ROLES if r.path=='src/common/record_internal.h')
        f=next(f for f in self.files if f.path==rule.path)
        raw=f.data+b'\n#define NEW_OPERATION(x) unsafe(x)\n'
        changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
        result=observe_source_roles((changed,),(replace(rule,sha256=changed.sha256),),{},self.ledger)
        self.assertIn(('SOURCE_SYMBOL_SET_CHANGED',rule.path),result[0].blockers)

    def test_transfer_owner_cli_names_need_classification(self):
        rule=next(r for r in SOURCE_ROLES if r.cli_argument is not None)
        scan=source_role_cli_scan(self.files,(rule,))
        self.assertEqual(tuple(o.selector for o in scan.observations),('schema','plan'))
        self.assertFalse(scan.unresolved)
        ledger=copy.deepcopy(self.ledger)
        ledger['capabilities']=[c for c in ledger['capabilities'] if c['id']!='owner.transfer.plan']
        result=observe_source_roles(self.files,(rule,),{'d2_fallback':{'blockers':()}},ledger)
        self.assertIn(('SOURCE_CLI_CLASSIFICATION_MISSING','plan'),result[0].blockers)
