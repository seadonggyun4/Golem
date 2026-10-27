import hashlib
import unittest
from capability_files import SourceFile
from capability_selected_scan import scan_selected
from test_capability_audit import fixture

class EvidenceScope(unittest.TestCase):
    def source(self,path):
        b=b'# evidence\n'; return SourceFile(path,hashlib.sha256(b).hexdigest(),b)

    def test_only_bound_evidence_is_separated(self):
        ledger, sources, _=fixture()
        doc=self.source('docs/explanation.md')
        ledger['sources'].append({'path':doc.path,'sha256':doc.sha256})
        ledger['capabilities'][0]['doc_refs']=[{'path':doc.path,'anchor':None}]
        scan=scan_selected(ledger,(*sources,doc),())
        self.assertNotIn((doc.path,None,'UNREGISTERED_SOURCE'),scan.unresolved)
        self.assertIn((sources[0].path,None,'UNREGISTERED_SOURCE'),scan.unresolved)

    def test_production_code_cannot_be_exempted_by_reference(self):
        ledger,sources,_=fixture()
        ledger['capabilities'][0]['test_refs']=[{'path':sources[0].path,'selector':None}]
        self.assertIn((sources[0].path,None,'UNREGISTERED_SOURCE'),scan_selected(ledger,sources,()).unresolved)

    def test_unreferenced_test_is_not_silently_excluded(self):
        ledger,sources,_=fixture(); test=self.source('tests/new.py')
        self.assertIn((test.path,None,'UNREGISTERED_SOURCE'),scan_selected(ledger,(*sources,test),()).unresolved)

    def test_changed_evidence_remains_blocked(self):
        ledger,sources,_=fixture(); doc=self.source('docs/explanation.md')
        ledger['sources'].append({'path':doc.path,'sha256':'0'*64})
        ledger['capabilities'][0]['doc_refs']=[{'path':doc.path,'anchor':None}]
        self.assertIn((doc.path,None,'EVIDENCE_SOURCE_DRIFT'),scan_selected(ledger,(*sources,doc),()).unresolved)

    def test_evidence_duplicates_and_invalid_hash_cannot_bypass_reader_contract(self):
        ledger,sources,_=fixture(); doc=self.source('docs/explanation.md')
        ledger['sources'].append({'path':doc.path,'sha256':doc.sha256})
        ledger['capabilities'][0]['doc_refs']=[{'path':doc.path,'anchor':None}]
        with self.assertRaises(ValueError):
            scan_selected(ledger,(*sources,doc,doc),())
        invalid=SourceFile(doc.path,doc.sha256,b'changed')
        with self.assertRaises(ValueError):
            scan_selected(ledger,(*sources,invalid),())
