"""Reproduce the M0 selected sample and repository scope obligations.

Development-only, read-only command. The root and finite public-header selection
are explicit. It never imports inspected programs, edits the ledger, follows
record paths, invokes a native/client process, or changes an installation.
Exit 0 requires both gates; exit 2 is a valid INCOMPLETE report, 1 invalid input.
"""
import argparse
from dataclasses import asdict,replace
import json
import sys

from capability_audit import audit_ledger, render_markdown
from capability_connections import connect_inventory, render_connections
from capability_evidence import inspect_references
from capability_files import read_sources,read_inventory
from capability_ledger import decode_identified_ledger
from capability_obligations import residual_obligations
from capability_public_registry import PUBLIC_HEADERS
from capability_repository import audit_repository, render_repository, REQUIRED_SOURCE_PATHS
from capability_sample_registry import SOURCES, RULES,REVIEWED_NEW_SOURCES
from capability_scope import tracked_scope,untracked_scope
from capability_selected_scan import scan_selected

LEDGER_PATH = 'docs/mcp-m0-observations.json'


def reconcile(root, *, public_headers=False, repository_sources=False):
    paths = list(SOURCES)
    if public_headers:
        paths.extend(r.path for r in PUBLIC_HEADERS if r.path not in paths)
    if repository_sources:
        paths.extend(p for p in REQUIRED_SOURCE_PATHS if p not in paths)
    batch = read_sources(root, paths,reviewed_new=[p for p in REVIEWED_NEW_SOURCES if p in paths])
    inventory=read_inventory(root)
    ledger = decode_identified_ledger(inventory.data)
    sources = tuple(s for s in batch if s.path in SOURCES)
    scan = scan_selected(ledger,sources,RULES)
    references = [p for p in SOURCES if p.startswith(('docs/','tests/','tools/test_'))]
    evidence = inspect_references(ledger,root,references,reviewed_new=[p for p in REVIEWED_NEW_SOURCES if p in references])
    connected = connect_inventory(ledger,sources,audit_ledger(ledger,sources,scan,evidence))
    scope_sources = tuple(s for s in batch if s.path!=LEDGER_PATH)
    from capability_development_registry import DEVELOPMENT_PATHS
    dev_paths=[p for p in DEVELOPMENT_PATHS if p.endswith('.py')]
    development=read_sources(root,dev_paths,reviewed_new=dev_paths)
    repository = audit_repository(ledger,scope_sources,connected.audit,tracked_scope(root),connected.observations,untracked_scope(root),development)
    from capability_native import inspect_native_definitions
    from capability_native_registry import NATIVE_DEFINITIONS,WRAPPER_SHA256
    native_definitions=inspect_native_definitions(scope_sources,NATIVE_DEFINITIONS,WRAPPER_SHA256)
    repository=replace(repository,blockers=repository.blockers+tuple(
        ('NATIVE_DEFINITION_BLOCKED',(v.name,v.blockers)) for v in native_definitions if v.blockers))
    # Describe the remaining connected obligations, not the declaration/profile
    # markers already discharged by a successful narrow connection checker.
    remaining = {b[1] for b in connected.audit.blockers if b[0]=='SCAN_UNRESOLVED'}
    from capability_profile import Scan
    residual = Scan(scan.observations, tuple(v for v in scan.unresolved if v in remaining))
    obligations = residual_obligations(scope_sources,RULES,residual)
    report = dict(inventory_sha256=inventory.sha256, selected_source_count=len(sources), selected_observation_count=len(scan.observations),
        selected_capability_count=len(ledger['capabilities']), selected_inventory_complete=connected.audit.inventory_complete,
        selected_blockers=connected.audit.blockers, delivery_backlog=connected.audit.backlog,
        delivery_backlog_details=_delivery_details(ledger,connected.audit.backlog),
        owner_management_backlog=[c['id'] for c in ledger['capabilities'] if c['target_routes']==['OWNER_ONLY'] and 'OWNER_ONLY' not in c['current_routes']],
        explicitly_unsupported=[c['id'] for c in ledger['capabilities'] if c['implementation']=='UNSUPPORTED'],
        repository=asdict(repository), residual_obligations=[asdict(o) for o in obligations],
        inspected_sources=[dict(path=s.path,sha256=s.sha256) for s in scope_sources],
        native_definitions=[asdict(v) for v in native_definitions],
        static_connections=connected.observations,
        source_reviews=_source_reviews(), repository_boundary_reviews=_boundary_reviews(),
        development_reviews=[dict(path=p,sha256=h,shape_sha256=shape,role=role) for p,h,shape,role in __import__('capability_development_registry').DEVELOPMENT_REVIEWS],
        m1_read_coverage=_m1_coverage_rows(ledger),
        m2_preparation_dependencies=_m2_dependency_rows(ledger),
        m3_action_coverage=[dict(row) for row in __import__("capability_m3_backlog_registry").M3_BACKLOG],
        m4_quality_coverage=[dict(row) for row in __import__("capability_m4_backlog_registry").M4_BACKLOG],
        client_e2e='NOT_RUN',
        native_execution_verified=False, policy_satisfaction_verified=False,
        test_execution_status='NOT_RUN_BY_THIS_COMMAND')
    markdown = render_markdown(ledger,connected.audit)+render_connections(connected)+'\n'+render_repository(repository)
    return report, markdown


def _delivery_details(ledger,identities):
    from capability_delivery_registry import DELIVERY_REVIEWS
    models={cid:(stage,routes) for cid,stage,routes in DELIVERY_REVIEWS}
    if len(models)!=len(DELIVERY_REVIEWS) or set(identities)!=set(models):raise ValueError('DELIVERY_REVIEW_MISSING_OR_STALE')
    caps={c['id']:c for c in ledger['capabilities']};result=[]
    for cid in identities:
        c=caps[cid];stage,routes=models[cid]
        if tuple(c['target_routes'])!=routes or stage not in ('M1','M2','M3','M4','M5','M6'):raise ValueError('DELIVERY_REVIEW_ROUTE_OR_MILESTONE')
        result.append(dict(capability_id=cid,milestone=stage,target_routes=c['target_routes'],
            preparation_dependency='M2' if 'MCP_REVIEWED_ACTION' in routes else None,
            disposition='Reviewed unprovided facade; reuse core contracts. Low-level APIs may be grouped in one typed tool. No grant or runtime delivery claim.'))
    return result


def _m1_coverage_rows(ledger):
    from capability_m1_coverage_registry import M1_COVERAGE
    caps={c['id']:c for c in ledger['capabilities']}
    return [dict(m,observation_ids=caps[m['capability_id']]['observation_ids'],test_refs=caps[m['capability_id']]['test_refs'],client_e2e='NOT_RUN') for m in M1_COVERAGE]


def _m2_dependency_rows(ledger):
    from capability_m2_backlog_registry import M2_BACKLOG
    caps={c['id']:c for c in ledger['capabilities']}
    return [dict(m,observation_ids=caps[m['capability_id']]['observation_ids'],native_dispatch='NOT_IMPLEMENTED_BY_M2',client_e2e='NOT_RUN') for m in M2_BACKLOG]


def _source_reviews():
    from capability_surface_registry import SURFACES
    return [dict(path=m['path'],role=m['role'],rationale=m['rationale'],symbols=m['symbols'],declarations=m['declarations'],literal_branches=m['branches'],operations=m['operations']) for m in SURFACES]

def _boundary_reviews():
    from capability_boundary_registry import BOUNDARIES,BOUNDARY_CONTRACTS
    pins={p:sha for p,sha,_ in BOUNDARY_CONTRACTS}
    return [dict(path=p,role=role,rationale=why,contract_sha256=pins.get(p)) for p,role,why in BOUNDARIES]

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--public-headers',action='store_true',help='Compatibility flag: all 48 pinned public headers are now mandatory')
    parser.add_argument('--repository-sources',action='store_true',help='Select and verify the full fixed source horizon (also the current default)')
    parser.add_argument('--format',choices=('json','markdown'),default='json')
    args=parser.parse_args(argv)
    try:
        result,markdown=reconcile(args.root,public_headers=args.public_headers,repository_sources=args.repository_sources)
        print(json.dumps(result,ensure_ascii=False,indent=2) if args.format=='json' else markdown,end='\n' if args.format=='json' else '')
        return 0 if result['selected_inventory_complete'] and not result['repository']['blockers'] else 2
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'INVALID_INPUT','error_type':type(error).__name__}),file=sys.stderr)
        return 1


if __name__=='__main__':
    sys.exit(main())
