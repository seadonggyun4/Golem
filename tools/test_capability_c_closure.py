import unittest,json,hashlib,copy
from pathlib import Path
from dataclasses import replace
from capability_files import SourceFile
from capability_sample_registry import SOURCES
from capability_c_closure_registry import EVENTS
from capability_c_closure import inspect_closure

class Boundaries(unittest.TestCase):
    def data(self):
        root=Path(__file__).resolve().parents[1]
        sources=tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in SOURCES)
        ledger=json.loads((root/'docs/mcp-m0-observations.json').read_text())
        return sources,ledger
    def test_actual_bounded_closure(self):
        s,l=self.data();r=inspect_closure(s,l,EVENTS)
        self.assertFalse(r.blockers);self.assertEqual(len(r.native),4);self.assertFalse(r.execution_verified)
    def test_capability_or_declaration_missing(self):
        s,l=self.data();l['capabilities']=[c for c in l['capabilities'] if c['id']!=EVENTS.native[0].capability]
        self.assertTrue(inspect_closure(s,l,EVENTS).blockers)
        s,l=self.data();s=tuple(f for f in s if f.path!=EVENTS.native[0].path)
        self.assertTrue(inspect_closure(s,l,EVENTS).blockers)
    def test_helper_drift(self):
        s,l=self.data();s=tuple(replace(f,sha256=hashlib.sha256(f.data+b'\n').hexdigest(),data=f.data+b'\n') if f.path=='src/cli/error.c' else f for f in s)
        self.assertTrue(inspect_closure(s,l,EVENTS).blockers)
    def test_added_call_requires_registration_even_with_new_fixture_pin(self):
        s,l=self.data();changed=[];rule=EVENTS
        for f in s:
            if f.path==EVENTS.path:
                raw=f.data.replace(b'free(bytes);',b'unknown(bytes); free(bytes);');h=hashlib.sha256(raw).hexdigest()
                f=replace(f,data=raw,sha256=h);rule=replace(rule,sha256=h)
            changed.append(f)
        self.assertTrue(inspect_closure(tuple(changed),l,rule).blockers)
    def test_external_boundary_cannot_hide_missing_native(self):
        s,l=self.data();rule=replace(EVENTS,native=())
        self.assertTrue(inspect_closure(s,l,rule).blockers)
    def test_relabelling_native_or_private_helper_as_external_is_not_accepted(self):
        s,l=self.data()
        rule=replace(EVENTS,native=(),external=(*EVENTS.external,*(n.name for n in EVENTS.native)))
        self.assertTrue(any(c=='EXTERNAL_BOUNDARY_UNREGISTERED' for c,_ in inspect_closure(s,l,rule).blockers))
        rule=replace(EVENTS,helpers=(),external=(*EVENTS.external,'cli_error_note'))
        self.assertTrue(inspect_closure(s,l,rule).blockers)
    def test_private_header_is_not_a_public_api_termination(self):
        s,l=self.data()
        rule=replace(EVENTS,native=(replace(EVENTS.native[0],path='src/cli/output.h'),*EVENTS.native[1:]))
        self.assertTrue(any(c=='PRIVATE_DECLARATION_NOT_NATIVE_BOUNDARY' for c,_ in inspect_closure(s,l,rule).blockers))
