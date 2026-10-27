"""Static real-source and adversarial fixtures; never invoke a native guard."""
import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import unittest
from capability_files import SourceFile
from capability_publication import inspect_publication,scan_publication,CAPABILITY
from capability_publication_registry import PUBLICATION
from capability_c_syntax import plain_definitions,call_sites
from capability_c_graph import fingerprint

class PrivatePublication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        paths={n['path'] for n in PUBLICATION['nodes']}|{n['path'] for n in PUBLICATION['declarations']}
        cls.sources=tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in sorted(paths))
        cls.ledger=json.loads((root/'docs/mcp-m0-observations.json').read_bytes())
    def mutate(self,path,old,new,*,repin=False,body_model=False,edge_model=False):
        model=copy.deepcopy(PUBLICATION);out=[]
        for f in self.sources:
            if f.path!=path:out.append(f);continue
            self.assertIn(old,f.data);raw=f.data.replace(old,new,1);changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest());out.append(changed)
            for field in ('nodes','declarations'):
                for n in model[field]:
                    if n['path']==path and repin:n['sha256']=changed.sha256
            parsed={d[0]:d for d in plain_definitions(raw.decode())}
            for n in model['nodes']:
                if n['path']==path and body_model:n['body']=parsed[n['name']][3]
            if edge_model:
                for edge in model['edges']:
                    if edge['caller'] not in parsed:continue
                    sites=[s for s in call_sites(' '.join(parsed[edge['caller']][3])) if s.expression==(edge['callee'],)]
                    if len(sites)==1:edge['position']=sites[0].position;edge['arguments_sha256']=fingerprint(sites[0].arguments)
        return tuple(out),model
    def result(self,files=None,model=None,ledger=None):
        return inspect_publication(self.sources if files is None else files,self.ledger if ledger is None else ledger,PUBLICATION if model is None else model)
    def test_actual_two_value_contract_and_static_limits(self):
        r=self.result();self.assertFalse(r.blockers)
        self.assertEqual(r.allowed_values,('NULL','as_publication_guard'));self.assertEqual(len(r.checked_forwarding),4);self.assertEqual(len(r.checked_definitions),6)
        self.assertEqual(r.scope,'registered_call_sites_only');self.assertIn('dw_event_write_guarded',r.excluded_entrypoints)
        self.assertFalse(r.execution_verified);self.assertFalse(r.receiver_identity_verified);self.assertFalse(r.policy_satisfied);self.assertFalse(r.callee_behavior_verified)
        scan=scan_publication(self.sources,PUBLICATION);self.assertEqual(len(scan.observations),1);self.assertFalse(scan.unresolved)
    def test_missing_or_drifted_definition_and_header_block(self):
        for f in self.sources:self.assertTrue(self.result(files=tuple(x for x in self.sources if x.path!=f.path)).blockers)
        fs,m=self.mutate('src/document/record.c',b'if (!guard)',b'if (guard)');self.assertTrue(self.result(fs,m).blockers)
    def test_source_repin_does_not_hide_changed_forwarding(self):
        for new in (b'out, context, guard);',b'out, selected_guard, context);'):
            fs,m=self.mutate('src/document/record.c',b'out, guard, context);',new,repin=True)
            self.assertTrue(self.result(fs,m).blockers)
    def test_alias_dynamic_target_and_context_rejected_beyond_snapshots(self):
        for replacement in (b'&digest, alias, l);',b'&digest, selected(), l);',b'&digest, (callback_type)as_publication_guard, l);',b'&digest, as_publication_guard, other);'):
            fs,m=self.mutate('src/agent_session/storage.c',b'&digest, as_publication_guard, l);',replacement,repin=True,body_model=True,edge_model=True)
            self.assertTrue(any(code=='PUBLICATION_VALUE_OR_CONTEXT_UNSUPPORTED' for code,_ in self.result(fs,m).blockers))
    def test_unguarded_route_cannot_supply_nonnull_value(self):
        fs,m=self.mutate('src/document/record.c',b'out, NULL, NULL);',b'out, as_publication_guard, NULL);',repin=True,body_model=True,edge_model=True)
        self.assertTrue(any(code=='PUBLICATION_VALUE_OR_CONTEXT_UNSUPPORTED' for code,_ in self.result(fs,m).blockers))
    def test_guard_polarity_failure_return_and_publication_order_are_protocol(self):
        for old,new in ((b'if (st == GOLEM_OK && guard)',b'if (st == GOLEM_OK || guard)'),(b'if (checked != GOLEM_OK) return checked;',b'if (checked == GOLEM_OK) return checked;'),(b'guard(context)',b'guard(s)')):
            fs,m=self.mutate('src/document/record.c',old,new,repin=True,body_model=True,edge_model=True)
            self.assertTrue(self.result(fs,m).blockers)
    def test_publication_clock_fence_and_target_body_changes_block(self):
        for old,new in ((b'if (st == GOLEM_OK) {\n        const char *op =',b'if (st != GOLEM_OK) {\n        const char *op ='),(b'l->publication_clock = clock;',b'l->publication_clock = NULL;'),(b'if (fenced)',b'if (!fenced)'),(b'as_log *log = context;',b'as_log *log = other;')):
            fs,m=self.mutate('src/agent_session/storage.c',old,new,repin=True,body_model=True,edge_model=True)
            self.assertTrue(self.result(fs,m).blockers)
    def test_target_cannot_add_unreviewed_indirect_call_even_after_model_update(self):
        fs,m=self.mutate('src/agent_session/storage.c',b'uint64_t now;',b'uint64_t now; callback(context);',repin=True,body_model=True,edge_model=True)
        self.assertTrue(any(code=='PUBLICATION_TARGET_CALL_SET_CHANGED' for code,_ in self.result(fs,m).blockers))
    def test_declaration_signature_change_and_capability_loss_block(self):
        fs,m=self.mutate('src/agent_session/internal.h',b'golem_status as_publication_guard(void *log);',b'void as_publication_guard(void *log);',repin=True)
        self.assertTrue(self.result(fs,m).blockers)
        l=copy.deepcopy(self.ledger);l['capabilities']=[c for c in l['capabilities'] if c['id']!=CAPABILITY];self.assertTrue(self.result(ledger=l).blockers)
    def test_empty_generic_scan_does_not_require_private_profile(self):
        self.assertFalse(scan_publication((),PUBLICATION).observations)
    def test_new_private_guard_is_required_by_integrated_gate(self):
        from capability_connections import connect_inventory
        from capability_audit import Audit
        l=copy.deepcopy(self.ledger);l['capabilities']=[c for c in l['capabilities'] if c['id']!=CAPABILITY]
        result=connect_inventory(l,self.sources,Audit((),()))
        self.assertTrue(any(code=='PRIVATE_PUBLICATION_GUARD_BLOCKED' for code,_ in result.audit.blockers))
    def test_guard_cannot_move_after_publication_even_with_model_repin(self):
        old=b'''    if (st == GOLEM_OK && guard) {
        golem_status checked = guard(context);
        if (checked != GOLEM_OK) return checked;
    }
    if (st == GOLEM_OK) st = dw_publish(directory, name, bytes);'''
        new=b'''    if (st == GOLEM_OK) st = dw_publish(directory, name, bytes);
    if (st == GOLEM_OK && guard) {
        golem_status checked = guard(context);
        if (checked != GOLEM_OK) return checked;
    }'''
        fs,m=self.mutate('src/document/record.c',old,new,repin=True,body_model=True,edge_model=True)
        self.assertTrue(any(code=='PUBLICATION_PROTOCOL_GUARD_OR_ORDER_CHANGED' for code,_ in self.result(fs,m).blockers))
    def test_zero_is_not_an_approved_literal_null_spelling(self):
        fs,m=self.mutate('src/document/record.c',b'out, NULL, NULL);',b'out, 0, NULL);',repin=True,body_model=True,edge_model=True)
        self.assertTrue(any(code=='PUBLICATION_VALUE_OR_CONTEXT_UNSUPPORTED' for code,_ in self.result(fs,m).blockers))
    def test_review_does_not_grant_a_model_route_or_effect(self):
        for field,value in (('target_routes',['MCP_REVIEWED_ACTION']),('effects',['NATIVE_READ','NATIVE_WRITE'])):
            l=copy.deepcopy(self.ledger);next(c for c in l['capabilities'] if c['id']==CAPABILITY)[field]=value
            self.assertTrue(self.result(ledger=l).blockers)
    def test_declaration_and_definition_types_are_compared_beyond_pins(self):
        fs,m=self.mutate('src/agent_session/internal.h',b'golem_status as_publication_guard(void *log);',b'golem_status as_publication_guard(int *log);',repin=True)
        from capability_c_syntax import plain_declarations
        raw=next(f.data for f in fs if f.path=='src/agent_session/internal.h')
        actual=next(d for d in plain_declarations(raw.decode()) if d[0]=='as_publication_guard')
        next(d for d in m['declarations'] if d['name']=='as_publication_guard')['parameters']=actual[2]
        self.assertTrue(any(code=='PUBLICATION_SIGNATURE_MISMATCH' for code,_ in self.result(fs,m).blockers))
