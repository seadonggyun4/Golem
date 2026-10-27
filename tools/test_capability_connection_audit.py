import unittest
from pathlib import Path
import hashlib,json
from capability_files import SourceFile
from capability_audit import Audit
from capability_connections import connect_inventory
from capability_delegation import PINS
from capability_fallback import PINS as D2_PINS

class Integration(unittest.TestCase):
    def data(self):
        root=Path(__file__).resolve().parents[1]
        ledger=json.loads((root/'docs/mcp-m0-observations.json').read_bytes())
        ledger['observations']=[o for o in ledger['observations'] if o['kind']=='MCP_TOOL_DECLARATION']
        paths=set(PINS)|set(D2_PINS)
        files=tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in sorted(paths))
        return ledger,files
    def test_required_without_flag(self):
        ledger,files=self.data()
        result=connect_inventory(ledger,files,Audit((('UNRESOLVED','native'),),('later',)))
        self.assertTrue({'d2_fallback','d4_delegation','d4_mutation_graph'} <= result.observations.keys())
        self.assertFalse(any(c=='CONNECTION_PROFILE_BLOCKED' for c,_ in result.audit.blockers))
        self.assertIn(('UNRESOLVED','native'),result.audit.blockers)
        # This fixture intentionally removed CLI observations from its ledger;
        # the transfer source role must now report their missing classification.
        self.assertTrue(any(c=='SOURCE_ROLE_BLOCKED' and value[0]=='tools/integration_transfer.py'
                            for c,value in result.audit.blockers))
        self.assertFalse(result.audit.inventory_complete)
    def test_missing_dependency_blocks(self):
        ledger,files=self.data()
        result=connect_inventory(ledger,tuple(f for f in files if f.path!='tools/integration_contract.py'),Audit((),()))
        self.assertEqual({value[0] for code,value in result.audit.blockers if code=='CONNECTION_PROFILE_BLOCKED'},
                         {'d2_fallback','d4_delegation','d4_mutation_graph'})
        self.assertFalse(result.audit.inventory_complete)
    def test_other_selected_scope_does_not_read_or_require_d4(self):
        result=connect_inventory({'observations':[]},(),Audit((),()))
        self.assertFalse(result.observations)

    def test_only_proven_declaration_obligation_is_discharged(self):
        ledger,files=self.data()
        d2=('SCAN_UNRESOLVED',('tools/integration_service.py','SCHEMAS','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
        other=('SCAN_UNRESOLVED',('tools/integration_service.py','other','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
        r=connect_inventory(ledger,files,Audit((d2,other),()))
        self.assertNotIn(d2,r.audit.blockers);self.assertIn(other,r.audit.blockers)
        missing=connect_inventory(ledger,files[1:],Audit((d2,other),()))
        self.assertIn(d2,missing.audit.blockers)
