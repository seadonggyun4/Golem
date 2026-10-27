"""Reconcile the frozen M1 backlog with finite facades and retained boundaries.

Pure inspection of caller-selected bytes/ledger. Does not infer execution,
client activation, policy satisfaction or authority from an implementation route.
"""
import ast
from collections import Counter
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_source import python_literal_names

STATUSES=('READ_FACADE','SHARED_CORE_FACADE','HOST_DEPENDENCY','OWNER_BOUNDARY','MIXED_READ_ACTION','PREPARATION_BOUNDARY')

@dataclass(frozen=True)
class M1CoverageObservation:
    baseline_count: int
    dispositions: tuple
    remaining_actions: tuple
    blockers: tuple
    client_e2e: str='NOT_RUN'
    runtime_verified: bool=False
    policy_satisfied: bool=False


def inspect_coverage(ledger,sources,baseline,models):
    scan_sources(sources,());files={f.path:f for f in sources};caps={c['id']:c for c in ledger['capabilities']}
    errors=[];seen=set();counts=Counter();remaining=[]
    if len(baseline)!=120 or len(set(baseline))!=120:errors.append(('M1_BASELINE_DOMAIN_CHANGED',None))
    try:names=set(python_literal_names(files['tools/integration_service.py'].data.decode(),'SCHEMAS',mapping=True))
    except (KeyError,ValueError):names=set();errors.append(('M1_SCHEMAS_MISSING',None))
    options={}
    for path in ('tools/integration_reads.py','tools/integration_read_resources.py'):
        if path not in files:continue
        tree=ast.parse(files[path].data)
        mapping=next((n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCHEMAS' for t in n.targets)),None)
        if not isinstance(mapping,ast.Dict):continue
        for key,node in zip(mapping.keys,mapping.values):
            if not isinstance(key,ast.Constant):continue
            values={a.value for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='enum' for a in n.args if isinstance(a,ast.Constant) and isinstance(a.value,str)}
            values.update(n.args[0].value for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='query' and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str))
            options[key.value]=values
    for m in models:
        cid=m['capability_id'];cap=caps.get(cid)
        if cid in seen:errors.append(('M1_DUPLICATE_DISPOSITION',cid))
        seen.add(cid);counts[m['status']]+=1
        if cap is None or m['status'] not in STATUSES or not m['basis']:errors.append(('M1_DISPOSITION_UNREVIEWED',cid));continue
        if m['tool']:
            if m['tool'] not in names:errors.append(('M1_FACADE_MISSING',cid))
            if set(m['operations'])-options.get(m['tool'],set()):errors.append(('M1_OPERATION_MISSING',cid))
            if 'MCP_READ' not in cap['current_routes']:errors.append(('M1_READ_ROUTE_MISSING',cid))
        if m['status']=='HOST_DEPENDENCY' and not m['tool'] and cap['target_routes']!=['HOST_INTERNAL']:
            errors.append(('M1_HANDLE_BOUNDARY_LOST',cid))
        if m['status'] in ('MIXED_READ_ACTION','PREPARATION_BOUNDARY','OWNER_BOUNDARY'):
            if m['followup'] not in ('M3','M4','M6'):errors.append(('M1_FOLLOWUP_MISSING',cid))
            remaining.append((cid,m['followup']))
            if m['status']=='OWNER_BOUNDARY' and 'OWNER_ONLY' not in cap['target_routes']:errors.append(('M1_OWNER_BOUNDARY_LOST',cid))
            if m['status']!='OWNER_BOUNDARY' and 'MCP_REVIEWED_ACTION' not in cap['target_routes']:errors.append(('M1_ACTION_BOUNDARY_LOST',cid))
    if seen!=set(baseline):errors.append(('M1_BACKLOG_REVIEW_MISSING_OR_EXTRA',tuple(sorted(seen^set(baseline)))))
    return M1CoverageObservation(len(baseline),tuple(sorted(counts.items())),tuple(remaining),tuple(errors))
