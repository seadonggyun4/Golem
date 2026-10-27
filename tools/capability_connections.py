"""Mandatory bounded connections for observed D2/D4 declarations.

Consumes already selected bytes; no implicit reads, execution or authority.
Successful narrow profiles never remove transitive scope blockers.
"""
from dataclasses import asdict, dataclass
from capability_audit import Audit
from capability_fallback import inspect_fallback
from capability_delegation import inspect_delegation
from capability_mutation_graph import inspect_mutation_graph

@dataclass(frozen=True)
class ConnectionAudit:
    audit: Audit
    observations: dict


def connect_inventory(ledger,sources,audit):
    selected={(o['source_path'],o['entrypoint']) for o in ledger['observations']}
    if not selected:return ConnectionAudit(audit,{})
    requested=[]
    if ('tools/integration_service.py','SCHEMAS') in selected:
        requested.append(('d2_fallback',inspect_fallback))
    if ('tools/integration_mutation_contract.py','NAMES') in selected:
        requested.extend((('d4_delegation',inspect_delegation),('d4_mutation_graph',inspect_mutation_graph)))
    blockers=list(audit.blockers); observations={}
    for name,inspect in requested:
        result=inspect(sources)
        observations[name]=asdict(result)
        if result.blockers:
            blockers.append(('CONNECTION_PROFILE_BLOCKED',(name,result.blockers)))
    if ('tools/integration_reads.py','SCHEMAS') in selected or ('tools/integration_read_resources.py','SCHEMAS') in selected:
        from capability_m1 import inspect_m1
        from capability_m1_registry import M1
        from capability_m1_coverage import inspect_coverage
        from capability_m1_coverage_registry import BASELINE_IDS,M1_COVERAGE
        for name,result in (('m1_reads',inspect_m1(sources,M1)),('m1_backlog',inspect_coverage(ledger,sources,BASELINE_IDS,M1_COVERAGE))):
            observations[name]=asdict(result)
            if result.blockers:blockers.append(('M1_PROFILE_BLOCKED',(name,result.blockers)))
    if ('tools/integration_preparations.py','SCHEMAS') in selected:
        from capability_m2 import inspect_m2
        from capability_m2_registry import M2
        from capability_m2_backlog_registry import M2_BACKLOG
        proof=inspect_m2(sources,ledger,M2,M2_BACKLOG)
        observations['m2_preparation']=asdict(proof)
        if proof.blockers:blockers.append(('M2_PROFILE_BLOCKED',proof.blockers))
    if any(s.path=='tools/integration_task_actions.py' for s in sources):
        from capability_m3 import inspect_m3
        from capability_m3_registry import M3
        from capability_m3_backlog_registry import M3_BACKLOG
        proof=inspect_m3(sources,ledger,M3,M3_BACKLOG)
        observations['m3_task_actions']=asdict(proof)
        if proof.blockers:blockers.append(('M3_PROFILE_BLOCKED',proof.blockers))
    if any(s.path=='tools/integration_quality_actions.py' for s in sources):
        from capability_m4 import inspect_m4
        from capability_m4_registry import M4
        from capability_m4_backlog_registry import M4_BACKLOG
        proof=inspect_m4(sources,ledger,M4,M4_BACKLOG)
        observations['m4_quality_evidence']=asdict(proof)
        if proof.blockers:blockers.append(('M4_PROFILE_BLOCKED',proof.blockers))
    if any(s.path=='tools/integration_parallel_actions.py' for s in sources):
        from capability_m5 import inspect_m5
        from capability_m5_registry import M5
        from capability_m5_backlog_registry import M5_BACKLOG
        proof=inspect_m5(sources,ledger,M5,M5_BACKLOG)
        observations['m5_parallel_candidates']=asdict(proof)
        if proof.blockers:blockers.append(('M5_PROFILE_BLOCKED',proof.blockers))
    if any(s.path=='tools/integration_feature_profiles.py' for s in sources):
        from capability_m6 import inspect_m6
        from capability_m6_registry import M6
        from capability_m6_backlog_registry import M6_BACKLOG
        proof=inspect_m6(sources,ledger,M6,M6_BACKLOG)
        observations['m6_feature_distribution']=asdict(proof)
        if proof.blockers:blockers.append(('M6_PROFILE_BLOCKED',proof.blockers))
    # Discharge only the declaration-to-routing obligation that these approved
    # profiles actually prove. Generic C, helper and source obligations remain.
    discharged = set()
    if 'd2_fallback' in observations and not observations['d2_fallback']['blockers']:
        discharged.add(('tools/integration_service.py','SCHEMAS','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
    if all(k in observations and not observations[k]['blockers'] for k in ('d4_delegation','d4_mutation_graph')):
        discharged.add(('tools/integration_mutation_contract.py','NAMES','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
    if 'm1_reads' in observations and not observations['m1_reads']['blockers']:
        for path in ('tools/integration_reads.py','tools/integration_read_resources.py'):
            discharged.add((path,'SCHEMAS','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
    if 'm2_preparation' in observations and not observations['m2_preparation']['blockers']:
        discharged.add(('tools/integration_preparations.py','SCHEMAS','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
    if 'm3_task_actions' in observations and not observations['m3_task_actions']['blockers']:
        discharged.add(('tools/integration_task_actions.py','NAMES','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
    if 'm4_quality_evidence' in observations and not observations['m4_quality_evidence']['blockers']:
        discharged.add(('tools/integration_quality_actions.py','NAMES','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
        discharged.add(('tools/integration_quality_reads.py','SCHEMAS','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
    if 'm5_parallel_candidates' in observations and not observations['m5_parallel_candidates']['blockers']:
        discharged.add(('tools/integration_parallel_actions.py','NAMES','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
        discharged.add(('tools/integration_parallel_reads.py','SCHEMAS','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
        discharged.add(('tools/integration_parallel_preparations.py','SCHEMAS','DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED'))
    blockers = [b for b in blockers if not (b[0]=='SCAN_UNRESOLVED' and b[1] in discharged)]
    paths={s.path for s in sources}
    from capability_backend import inspect_backend
    from capability_transport import inspect_transport
    for path,name,inspect in (
            ('tools/integration_backend.py','d1_backend',inspect_backend),
            ('tools/integration_mutation_mcp.py','d4_transport',inspect_transport)):
        if path not in paths: continue
        proof=inspect(sources)
        observations[name]=asdict(proof)
        if proof.blockers: blockers.append(('CONNECTION_PROFILE_BLOCKED',(name,proof.blockers)))
    from capability_c_edge_registry import C_EDGES
    from capability_c_edges import inspect_c_edge
    for rule in C_EDGES:
        if (rule.caller_path, rule.caller) not in selected: continue
        result=inspect_c_edge(sources,rule)
        name='c_edge.'+rule.caller+'.'+rule.callee
        observations[name]=asdict(result)
        if result.blockers: blockers.append(('C_EDGE_PROFILE_BLOCKED',(name,result.blockers)))
    from capability_c_closure_registry import EVENTS
    from capability_c_closure import inspect_closure
    if (EVENTS.path,EVENTS.function) in selected:
        closure=inspect_closure(sources,ledger,EVENTS)
        observations['c_closure.events']=asdict(closure)
        if closure.blockers:
            blockers.append(('C_CLOSURE_BLOCKED',closure.blockers))
        else:
            resolved=(EVENTS.path,EVENTS.function,'C_RESIDUAL_SCOPE_UNVERIFIED')
            registered_dependencies={n.path for n in EVENTS.native}|{h.path for h in EVENTS.helpers}
            blockers=[b for b in blockers if not (b[0]=='SCAN_UNRESOLVED' and
                (b[1]==resolved or b[1][0] in registered_dependencies and b[1][1:] == (None,'UNREGISTERED_SOURCE')))]
    from capability_source_role_registry import SOURCE_ROLES
    from capability_source_roles import observe_source_roles
    for result in observe_source_roles(sources,SOURCE_ROLES,observations,ledger):
        observations['source_role.'+result.path]=asdict(result)
        if result.blockers:
            blockers.append(('SOURCE_ROLE_BLOCKED',(result.path,result.blockers)))
        elif result.file_surface_reviewed:
            blockers=[b for b in blockers if b!=('SCAN_UNRESOLVED',(result.path,None,'UNREGISTERED_SOURCE'))]
    from capability_public import scan_public_headers
    from capability_public_registry import PUBLIC_HEADERS
    public=scan_public_headers(sources,PUBLIC_HEADERS)
    failed={p for p,_,_ in public.unresolved}
    for rule in PUBLIC_HEADERS:
        if rule.path not in paths or rule.path in failed:continue
        actual=[o for o in public.observations if o.source_path==rule.path]
        if len(actual)!=len(rule.names):continue
        if all(any(c['review_status']=='REVIEWED' and o.id in c['observation_ids']
                   for c in ledger['capabilities']) for o in actual):
            blockers=[b for b in blockers if b!=('SCAN_UNRESOLVED',(rule.path,None,'UNREGISTERED_SOURCE'))]
    from capability_c_graph_registry import GRAPH
    graph_requested=bool(selected & set(map(tuple,GRAPH['roots'])))
    if graph_requested:
        from capability_domains import inspect_domains
        from capability_domain_registry import DOMAINS
        domains,_=inspect_domains(sources,ledger,DOMAINS)
        for api,value in domains.items():
            observations['domain.'+api]=asdict(value)
            if value.blockers:blockers.append(('NATIVE_DOMAIN_BLOCKED',(api,value.blockers)))
        from capability_c_graph import inspect_graph
        from capability_c_graph_registry import GRAPH
        graph=inspect_graph(sources,ledger,GRAPH,{k:asdict(v) for k,v in domains.items()})
        observations['c_graph']=asdict(graph)
        if graph.blockers:blockers.append(('C_GRAPH_BLOCKED',graph.blockers))
        else:
            roots=set(graph.roots)
            blockers=[b for b in blockers if not (b[0]=='SCAN_UNRESOLVED' and
                (b[1][0],b[1][1]) in roots and b[1][2]=='C_RESIDUAL_SCOPE_UNVERIFIED')]
        # Native selector observations are schema surfaces, not CLI execution
        # roots. End at their verified public API ownership contracts, retaining
        # native behavior/runtime callback obligations outside static M0.
        native_surfaces={}
        for rule in __import__('capability_sample_registry').RULES:
            if rule.kind!='NATIVE_OPERATION' or not rule.path.endswith('.c'):continue
            owners=[m['api'] for m in DOMAINS if tuple(m['api_definition'])==(rule.path,rule.entrypoint) or any(p['path']==rule.path and p['function']==rule.entrypoint for p in m['parts'])]
            valid=bool(owners) and all(not domains[api].blockers for api in owners)
            key=(rule.path,rule.entrypoint,'C_RESIDUAL_SCOPE_UNVERIFIED')
            native_surfaces[rule.entrypoint]={'public_owners':tuple(owners),'blockers':() if valid else ('NATIVE_SCHEMA_OWNER_UNVERIFIED',),'execution_verified':False}
            if valid:blockers=[b for b in blockers if b!=('SCAN_UNRESOLVED',key)]
        observations['native_operation_surfaces']={'surfaces':native_surfaces,'blockers':tuple(k for k,v in native_surfaces.items() if v['blockers']),'execution_verified':False}
    from capability_surface import observe_surface
    from capability_surface_registry import SURFACES
    surface,reviewed=observe_surface(sources,ledger,SURFACES)
    observations['whole_file_surfaces']={'reviewed_paths':reviewed,'blockers':surface.unresolved,'execution_verified':False}
    if surface.unresolved:blockers.append(('WHOLE_FILE_SURFACE_BLOCKED',surface.unresolved))
    reviewed=set(reviewed)
    blockers=[b for b in blockers if not (b[0]=='SCAN_UNRESOLVED' and b[1][0] in reviewed and b[1][1:] == (None,'UNREGISTERED_SOURCE'))]
    from capability_effects import inspect_effects
    from capability_effect_registry import EFFECT_REVIEWS
    effect_errors=inspect_effects(ledger,EFFECT_REVIEWS)
    observations['reviewed_effects']={'blockers':effect_errors,'reviewed_capabilities':len(EFFECT_REVIEWS),'execution_verified':False}
    if effect_errors:blockers.extend(effect_errors)
    from capability_boundaries import inspect_boundaries
    from capability_boundary_registry import BOUNDARY_CONTRACTS
    boundary_errors,boundary_reviewed=inspect_boundaries(sources,BOUNDARY_CONTRACTS)
    observations['boundary_contracts']={'reviewed_paths':boundary_reviewed,'blockers':boundary_errors,'execution_verified':False}
    blockers.extend(boundary_errors)
    blockers=[b for b in blockers if not (b[0]=='SCAN_UNRESOLVED' and b[1][0] in boundary_reviewed and b[1][1:] == (None,'UNREGISTERED_SOURCE'))]
    if ('src/agent_session/storage.c','as_publication_guard') in selected:
        from capability_publication import inspect_publication
        from capability_publication_registry import PUBLICATION
        publication=inspect_publication(sources,ledger,PUBLICATION)
        observations['private_publication_guard']=asdict(publication)
        if publication.blockers:blockers.append(('PRIVATE_PUBLICATION_GUARD_BLOCKED',publication.blockers))
    return ConnectionAudit(Audit(tuple(blockers),audit.backlog),observations)


def render_connections(result):
    lines=['','## Static connection checks','','| Profile | Bounded checks | Scope |',
           '| --- | --- | --- |']
    for name,value in result.observations.items():
        status='BLOCKED' if value['blockers'] else 'CONFIRMED'
        lines.append(f'| {name} | {status} | Static structure only; no policy satisfaction or execution proof |')
    if not result.observations: lines.append('No registered D2/D4 declaration in this selected inventory.')
    return '\n'.join(lines)+'\n'
