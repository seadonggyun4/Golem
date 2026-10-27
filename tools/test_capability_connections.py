import hashlib
import unittest
from pathlib import Path
from dataclasses import replace
from capability_files import SourceFile
import capability_fallback as fallback
import capability_delegation as delegation

class Connections(unittest.TestCase):
    def inputs(self,mod):
        root=Path(__file__).resolve().parents[1]
        return tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in mod.PINS)
    def changed(self,mod,path,old,new):
        files=list(self.inputs(mod)); pins=dict(mod.PINS)
        for i,f in enumerate(files):
            if f.path==path:
                self.assertIn(old,f.data)
                raw=f.data.replace(old,new,1); pin=hashlib.sha256(raw).hexdigest()
                files[i]=replace(f,data=raw,sha256=pin);pins[path]=pin
        return tuple(files),pins
    def test_actual_d2_remainder(self):
        r=fallback.inspect_fallback(self.inputs(fallback))
        self.assertFalse(r.blockers); paths=dict(r.paths)
        self.assertEqual(set(paths),set(__import__('capability_source').python_literal_names((Path(__file__).resolve().parents[1]/'tools/integration_transfer.py').read_text(),'NAMES',mapping=False)))
        self.assertIn('workflow_read',paths);self.assertIn('events_read',paths)
        self.assertTrue(all(edge=='remainder' for _,edge in paths['history_read']))
        self.assertFalse(r.execution_verified);self.assertFalse(r.authority_verified)
    def test_guard_cannot_be_removed_even_with_fixture_pin(self):
        for mod,fn in ((fallback,fallback.inspect_fallback),(delegation,delegation.inspect_delegation)):
            files,pins=self.changed(mod,'tools/integration_contract.py',b'raise IntegrationError(code)',b'pass')
            self.assertTrue(fn(files,pins).blockers)
    def test_d2_computed_routing_blocks(self):
        files,pins=self.changed(fallback,'tools/integration_service.py',b'if name == "projects_list":',b'if name == selected:')
        self.assertTrue(fallback.inspect_fallback(files,pins).blockers)
    def test_d2_no_name_special_case(self):
        files=self.inputs(fallback);changed=[];pins={}
        for f in files:
            raw=f.data.replace(b'history_read',b'history_new');pin=hashlib.sha256(raw).hexdigest()
            changed.append(replace(f,data=raw,sha256=pin));pins[f.path]=pin
        r=fallback.inspect_fallback(tuple(changed),pins)
        self.assertFalse(r.blockers);self.assertIn('history_new',dict(r.paths))
    def test_actual_d4_only_direct_edge(self):
        r=delegation.inspect_delegation(self.inputs(delegation))
        self.assertFalse(r.blockers);self.assertEqual(len(r.delegated),37)
        self.assertEqual(r.helper,'Service._mutate');self.assertFalse(r.helper_body_verified)
    def test_dynamic_receiver_and_reordered_args_block(self):
        for new in (b'other._mutate(name, args)',b'self._mutate(args, name)'):
            files,pins=self.changed(delegation,'tools/integration_mutations.py',b'self._mutate(name, args)',new)
            self.assertTrue(delegation.inspect_delegation(files,pins).blockers)
    def test_missing_and_drift(self):
        for mod,fn in ((fallback,fallback.inspect_fallback),(delegation,delegation.inspect_delegation)):
            files=self.inputs(mod)
            self.assertTrue(fn(files[1:]).blockers)
            f=files[0];raw=f.data+b'\n'
            self.assertTrue(fn((replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest()),*files[1:])).blockers)

    def test_unregistered_forwarding_blocks(self):
        files,pins=self.changed(delegation,'tools/integration_mutations.py',b'c.bounded(args)',b'unknown(name)\n        c.bounded(args)')
        self.assertTrue(delegation.inspect_delegation(files,pins).blockers)
