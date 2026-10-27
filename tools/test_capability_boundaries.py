"""Adversarial static/fixture checks for M0 finite boundary review."""
import copy
import hashlib
import json
import unittest
from dataclasses import replace,asdict
from pathlib import Path
from capability_files import SourceFile
from capability_c_graph import inspect_graph,_try_definition,call_rules,fingerprint
from capability_c_graph_registry import GRAPH
from capability_domains import inspect_domains
from capability_domain_registry import DOMAINS
from capability_surface import observe_surface
from capability_surface_registry import SURFACES
from capability_callbacks import scan_callbacks
from capability_callback_registry import CALLBACKS
from capability_effects import inspect_effects
from capability_effect_registry import EFFECT_REVIEWS

class Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.ledger=json.loads((root/'docs/mcp-m0-observations.json').read_bytes())
        cls._files={s['path']:SourceFile(s['path'],s['sha256'],(root/s['path']).read_bytes()) for s in cls.ledger['sources']}
    def files(self):return tuple(self.__class__._files.values())
    def one(self,name):
        m=copy.deepcopy(GRAPH);node=next(n for n in m['nodes'] if n['name']==name);m['nodes']=[node];m['roots']=[(node['path'],name)];m['try_macros']=();return m
    def test_public_callback_boundary_has_no_execution_or_identity_claim(self):
        r=inspect_graph(self.files(),self.ledger,self.one('as_clock_read'))
        self.assertFalse(r.blockers);self.assertIn('callback.golem_agent_clock.read',r.callback_endpoints)
        self.assertFalse(r.execution_verified);self.assertFalse(r.receiver_identity_verified);self.assertFalse(r.policy_satisfied)
    def test_callback_capability_is_mandatory(self):
        l=copy.deepcopy(self.ledger);l['capabilities']=[c for c in l['capabilities'] if c['id']!='callback.golem_agent_clock.read']
        self.assertTrue(inspect_graph(self.files(),l,self.one('as_clock_read')).blockers)
    def test_workspace_callback_requires_receiver_type_binding(self):
        fs=tuple(f for f in self.files() if f.path!='src/workspace/internal.h')
        self.assertTrue(inspect_graph(fs,self.ledger,self.one('git_run')).blockers)
    def test_repin_cannot_hide_new_call_or_changed_arguments(self):
        m=self.one('as_clock_read');node=m['nodes'][0];f=self.__class__._files[node['path']]
        for old,new in ((b'clock->read(clock->context,',b'clock->read(other,'),(b'uint64_t value',b'uint64_t value')):
            if old==new:continue
            self.assertIn(old,f.data);raw=f.data.replace(old,new,1);changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest());node['sha256']=changed.sha256
            fs=tuple(changed if x.path==f.path else x for x in self.files())
            self.assertTrue(inspect_graph(fs,self.ledger,m).blockers)
    def test_try_is_exact_and_only_two_declared_models(self):
        for p,v in GRAPH['try_macros']:
            raw=self.__class__._files[p].data;_try_definition(raw,v)
            with self.assertRaises(ValueError):_try_definition(raw.replace(b'goto done',b'goto elsewhere'),v)
            with self.assertRaises(ValueError):_try_definition(raw+b'\n#define TRY(call) call\n',v)
    def test_native_domains_follow_actual_api_schema_routes(self):
        r,scan=inspect_domains(self.files(),self.ledger,DOMAINS)
        self.assertFalse([x.blockers for x in r.values() if x.blockers]);self.assertFalse(scan.unresolved)
        self.assertEqual(r['golem_agent_session_resume_context'].operations,('resume',))
        self.assertNotIn('verify',r['golem_execution_call_receipted'].operations)
        self.assertIn('verify',r['golem_execution_call_authorized'].operations)
        self.assertIn('cohort-observe',r['golem_research_call'].operations)
    def test_operation_ownership_cannot_be_assumed_by_api_name(self):
        model=copy.deepcopy(next(m for m in DOMAINS if m['api']=='golem_agent_session_call'));model['route_edges']=()
        r,_=inspect_domains(self.files(),self.ledger,(model,));self.assertTrue(r[model['api']].blockers)
    def test_missing_operation_capability_blocks_native_domain(self):
        l=copy.deepcopy(self.ledger);oid=next(o['id'] for o in l['observations'] if o['entrypoint']=='ap_request' and o['selector']=='revoke')
        for c in l['capabilities']:c['observation_ids']=[x for x in c['observation_ids'] if x!=oid]
        r,_=inspect_domains(self.files(),l,DOMAINS);self.assertTrue(r['golem_approval_call'].blockers)
    def test_whole_file_review_requires_all_classified_operations(self):
        scan,paths=observe_surface(self.files(),self.ledger,SURFACES)
        self.assertFalse(scan.unresolved);self.assertEqual(set(paths),{m['path'] for m in SURFACES})
        self.assertTrue(any(o.selector=='research cohort observe' for o in scan.observations))
        self.assertTrue(any(o.selector=='research-outcome' and o.entrypoint=='argparse:command' for o in scan.observations))
    def test_new_function_is_not_cleared_by_repin(self):
        m=copy.deepcopy(next(m for m in SURFACES if m['path']=='tools/provider_costs.py'));f=self.__class__._files[m['path']];raw=f.data+b'\ndef unreviewed_api(): pass\n';changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest());m['sha256']=changed.sha256
        scan,paths=observe_surface((changed,),self.ledger,(m,));self.assertTrue(scan.unresolved);self.assertFalse(paths)
    def test_effect_omission_is_not_silently_accepted(self):
        self.assertFalse(inspect_effects(self.ledger,EFFECT_REVIEWS));l=copy.deepcopy(self.ledger);next(c for c in l['capabilities'] if c['id']=='cli.dispatch.completion.report')['effects']=['NATIVE_READ']
        self.assertTrue(inspect_effects(l,EFFECT_REVIEWS))
    def test_public_header_callback_signature_drift_blocks(self):
        r=next(r for r in CALLBACKS if r.structure=='golem_agent_clock');f=self.__class__._files[r.path];raw=f.data.replace(b'(*read)',b'(*other)',1);self.assertNotEqual(raw,f.data)
        changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest());scan=scan_callbacks((changed,),(replace(r,sha256=changed.sha256),));self.assertTrue(scan.unresolved)

    def test_callback_arity_is_checked_beyond_snapshot_repin(self):
        from capability_c_syntax import call_sites
        from capability_profile import _c_region
        from capability_source import _tokens
        m=self.one('as_clock_read');node=m['nodes'][0];f=self.__class__._files[node['path']]
        raw=f.data.replace(b'clock->read(clock->context, now, boot)',b'clock->read(clock->context, now)')
        self.assertNotEqual(raw,f.data);changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest());node['sha256']=changed.sha256
        from capability_c_syntax import plain_definitions
        body=next(d[3] for d in plain_definitions(raw.decode()) if d[0]==node['name']);node['body_sha256']=fingerprint(body)
        rules=list(call_rules(node));sites=call_sites(' '.join(body));self.assertEqual(len(rules),len(sites))
        for r,site in zip(rules,sites):r['arguments_sha256']=fingerprint(site.arguments);r['position']=site.position
        node['calls']=rules
        result=inspect_graph(tuple(changed if x.path==f.path else x for x in self.files()),self.ledger,m)
        self.assertTrue(any('CALLBACK_CALL_ARITY_CHANGED' in str(b) for b in result.blockers))

    def test_cli_null_graph_stays_separate_from_private_guard_profile(self):
        # Only CLI-reachable call sites participate. Native publication guards
        # stay behind reviewed public ABI/operation contracts.
        n=next(n for n in GRAPH['nodes'] if n['path']=='src/document/record.c' and n['name']=='publish')
        self.assertIn('guard',n['null_parameters'])
        self.assertNotIn(('src/document/record.c','dw_record_event_guarded'),{(n['path'],n['name']) for n in GRAPH['nodes']})
        self.assertFalse(any(r['kind']=='callback' and r['target']=='as_publication_guard' for n in GRAPH['nodes'] for r in call_rules(n)))

    def test_milestone_review_cannot_be_invented_for_new_gap(self):
        from capability_check import _delivery_details
        from capability_delivery_registry import DELIVERY_REVIEWS
        identities=[cid for cid,_,_ in DELIVERY_REVIEWS]
        self.assertEqual(len(_delivery_details(self.ledger,identities)),len(identities))
        with self.assertRaises(ValueError):_delivery_details(self.ledger,[*identities,'new.unreviewed.operation'])

    def test_package_entrypoint_drift_cannot_hide_in_exclusion(self):
        from capability_boundaries import inspect_boundaries
        from capability_boundary_registry import BOUNDARY_CONTRACTS
        errors,paths=inspect_boundaries(self.files(),BOUNDARY_CONTRACTS)
        self.assertFalse(errors);self.assertIn('bindings/typescript/package.json',paths)
        f=self.__class__._files['bindings/typescript/package.json'];raw=f.data+b'\n';changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
        errors,_=inspect_boundaries(tuple(changed if x.path==f.path else x for x in self.files()),BOUNDARY_CONTRACTS)
        self.assertIn(('BOUNDARY_CONTRACT_MISSING_OR_DRIFT',f.path),errors)

    def test_every_exposed_python_command_has_a_route_or_historical_exclusion(self):
        observations={o['id']:o for o in self.ledger['observations']}
        for m in SURFACES:
            for kind,entry,value in m['operations']:
                if not entry.startswith('argparse:'):continue
                candidates=[o['id'] for o in observations.values() if o['source_path']==m['path'] and o['entrypoint']==entry and o['selector']==value]
                self.assertEqual(len(candidates),1)
                caps=[c for c in self.ledger['capabilities'] if candidates[0] in c['observation_ids']]
                self.assertTrue(any(set(c['target_routes']) & {'MCP_READ','MCP_REVIEWED_ACTION','OWNER_ONLY'} or c['implementation']=='UNSUPPORTED' for c in caps),(m['path'],value))

    def test_callback_return_type_change_is_not_hidden_by_source_repin(self):
        rule=next(r for r in CALLBACKS if r.structure=='golem_agent_clock');f=self.__class__._files[rule.path]
        raw=f.data.replace(b'golem_status (*read)',b'int (*read)',1);self.assertNotEqual(raw,f.data)
        changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
        scan=scan_callbacks((changed,),(replace(rule,sha256=changed.sha256),))
        self.assertTrue(scan.unresolved)

    def test_null_forwarding_requires_literal_value_even_after_snapshot_repin(self):
        from capability_c_syntax import plain_definitions,call_sites
        m=copy.deepcopy(GRAPH);f=self.__class__._files['src/document/record.c']
        raw=f.data.replace(b'}, NULL, NULL);',b'}, arbitrary_guard, NULL);',1);self.assertNotEqual(raw,f.data)
        changed=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
        parsed={d[0]:d[3] for d in plain_definitions(raw.decode())}
        for n in m['nodes']:
            if n['path']!=f.path:continue
            n['sha256']=changed.sha256
            if n['name']!='dw_record_reference':continue
            n['body_sha256']=fingerprint(parsed[n['name']]);rules=list(call_rules(n))
            for rule,site in zip(rules,call_sites(' '.join(parsed[n['name']]))):
                rule['position']=site.position;rule['arguments_sha256']=fingerprint(site.arguments)
            n['calls']=rules
        domains,_=inspect_domains(self.files(),self.ledger,DOMAINS)
        result=inspect_graph(tuple(changed if x.path==f.path else x for x in self.files()),self.ledger,m,{k:asdict(v) for k,v in domains.items()})
        self.assertTrue(any(code=='NULL_FORWARDING_UNVERIFIED' for code,value in result.blockers))
