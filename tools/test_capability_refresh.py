import os
from pathlib import Path
import tempfile
import unittest
from capability_refresh import write_artifacts

class FixedOutputs(unittest.TestCase):
    def test_unrelated_file_and_reviewed_ledger_are_never_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();(root/'docs').mkdir()
            for name in ('mcp-m0-observations.json','../producer.py'):
                with self.assertRaises(ValueError):write_artifacts(str(root),{name:'overwrite'})
    def test_symlink_and_hardlink_cannot_redirect_document_write(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();(root/'docs').mkdir();target=root/'preserved';target.write_text('preserve')
            output=root/'docs/mcp-m0-reconciliation.json';output.symlink_to(target)
            with self.assertRaises((ValueError,OSError)):write_artifacts(str(root),{output.name:'overwrite'})
            self.assertEqual(target.read_text(),'preserve');output.unlink();os.link(target,output)
            with self.assertRaises(ValueError):write_artifacts(str(root),{output.name:'overwrite'})
            self.assertEqual(target.read_text(),'preserve')
    def test_only_requested_generated_document_is_refreshed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();(root/'docs').mkdir();ledger=root/'docs/mcp-m0-observations.json';ledger.write_text('preserved')
            write_artifacts(str(root),{'mcp-m0-reconciliation.json':'new\n'})
            self.assertEqual((root/'docs/mcp-m0-reconciliation.json').read_text(),'new\n');self.assertEqual(ledger.read_text(),'preserved')
    def test_inventory_drift_between_check_and_render_blocks(self):
        from unittest.mock import patch
        from capability_refresh import artifacts
        from capability_files import SourceFile
        with patch('capability_refresh.reconcile',return_value=({'inventory_sha256':'0'*64},'')),patch('capability_refresh.read_inventory',return_value=SourceFile('docs/mcp-m0-observations.json','1'*64,b'{}')):
            with self.assertRaisesRegex(ValueError,'INVENTORY_CHANGED_DURING_RENDER'):artifacts('/explicit/root')
    def test_later_source_drift_cannot_be_mixed_with_old_complete_report(self):
        from unittest.mock import patch
        import hashlib
        import json
        from capability_refresh import artifacts
        from capability_files import SourceFile
        from capability_ledger import SCHEMA
        raw=json.dumps(dict(schema=SCHEMA,sources=[],observations=[],capabilities=[])).encode();digest=hashlib.sha256(raw).hexdigest()
        report=dict(inventory_sha256=digest,selected_blockers=[],delivery_backlog=[],inspected_sources=[])
        with patch('capability_refresh.reconcile',return_value=(report,'')),patch('capability_refresh.read_inventory',return_value=SourceFile('docs/mcp-m0-observations.json',digest,raw)),patch('capability_refresh.read_sources',return_value=(SourceFile('new.c',hashlib.sha256(b'new').hexdigest(),b'new'),)):
            with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED_DURING_RENDER'):artifacts('/explicit/root')
