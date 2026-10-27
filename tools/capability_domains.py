"""Finite native operation contracts, not runtime validation/authority proofs."""
from dataclasses import dataclass
from capability_profile import scan_sources,Observation,Scan,_c_region,_recorded_region
from capability_source import _tokens,c_comparison_values
from capability_ledger import observation_identity
from capability_c_graph import fingerprint

@dataclass(frozen=True)
class DomainObservation:
    api: str
    operations: tuple
    blockers: tuple
    execution_verified: bool=False
    policy_satisfied: bool=False

def inspect_domains(sources,ledger,models):
    scan_sources(sources,());files={s.path:s for s in sources};results={};observations=[];problems=[]
    emitted=set()
    for model in models:
        blockers=list(_routes(files,model,ledger));operations=set()
        for part in model['parts']:
            f=files.get(part['path'])
            try:
                if f is None or f.sha256!=part['sha256']:raise ValueError('DOMAIN_SOURCE_MISSING_OR_DRIFT')
                body=(_recorded_region(f.data.decode(),part['function'],part['wrapper']) if part['wrapper'] else _c_region(f.data.decode(),part['function'],False))
                if fingerprint(_tokens(body))!=part['body_sha256']:raise ValueError('DOMAIN_BODY_STRUCTURE_CHANGED')
                names=c_comparison_values(body,part['subject'])
                if tuple(names)!=tuple(part['names']):raise ValueError('DOMAIN_SELECTOR_SET_CHANGED')
                for name in names:
                    fields=dict(kind='NATIVE_OPERATION',source_path=f.path,entrypoint=part['function'],selector=name)
                    oid=observation_identity(**fields)
                    if oid not in emitted:observations.append(Observation(oid,**fields));emitted.add(oid)
                    if not any(c['review_status']=='REVIEWED' and oid in c['observation_ids'] for c in ledger['capabilities']):
                        blockers.append(('DOMAIN_OPERATION_UNCLASSIFIED',(part['function'],name)))
                operations.update(names)
            except (ValueError,UnicodeError) as e:
                blockers.append(('DOMAIN_UNVERIFIED',(part['path'],part['function'],str(e))))
                problems.append((part['path'],part['function'],'NATIVE_DOMAIN_UNVERIFIED'))
        # Explicit constant/enum domains use exact registered source tokens;
        # no macro expansion, computed value interpretation or switch inference.
        for constant in model['constants']:
            f=files.get(constant['path'])
            if f is None or f.sha256!=constant['sha256'] or fingerprint(_tokens(f.data.decode()))!=constant['tokens_sha256']:
                blockers.append(('CONSTANT_DOMAIN_SOURCE_DRIFT',constant['path']));continue
            for name in constant['names']:
                fields=dict(kind='NATIVE_OPERATION',source_path=constant['path'],entrypoint=constant['entrypoint'],selector=name)
                oid=observation_identity(**fields)
                if oid not in emitted:observations.append(Observation(oid,**fields));emitted.add(oid)
                if not any(c['review_status']=='REVIEWED' and oid in c['observation_ids'] for c in ledger['capabilities']):
                    blockers.append(('DOMAIN_OPERATION_UNCLASSIFIED',(constant['entrypoint'],name)))
            operations.update(constant['names'])
        if tuple(sorted(operations))!=tuple(model['operations']):blockers.append(('DOMAIN_UNION_CHANGED',model['api']))
        results[model['api']]=DomainObservation(model['api'],tuple(sorted(operations)),tuple(blockers))
    return results,Scan(tuple(observations),tuple(problems))


def _routes(files,model,ledger):
    """Check finite concrete API-to-schema ownership paths, not runtime reachability."""
    from capability_c_syntax import plain_definitions,call_sites
    from capability_wrapper import verify_definition
    from capability_native_registry import WRAPPER_SHA256
    errors=[];bodies={}
    from capability_native_registry import NATIVE_DEFINITIONS
    rule=next((n for n in NATIVE_DEFINITIONS if n.name==model['api']),None)
    caps=[c for c in ledger['capabilities'] if c['id']=='native.'+model['api'] and c['review_status']=='REVIEWED']
    observations=[o for o in ledger['observations'] if o['kind']=='C_PUBLIC_DECLARATION' and o['entrypoint']==model['api'] and rule is not None and o['source_path']==rule.header_path]
    if len(caps)!=1 or len(observations)!=1 or observations[0]['id'] not in caps[0]['observation_ids']:
        errors.append(('DOMAIN_PUBLIC_CAPABILITY_UNBOUND',model['api']))
    for node in model.get('route_nodes',()):
        key=(node['path'],node['name']);f=files.get(key[0])
        try:
            if f is None or f.sha256!=node['sha256']:raise ValueError('ROUTE_SOURCE_DRIFT')
            if node['wrapper']:
                definition=files.get('src/common/record_internal.h')
                if definition is None or definition.sha256!=WRAPPER_SHA256:raise ValueError('ROUTE_WRAPPER_DRIFT')
                verify_definition(definition.data,node['wrapper'])
                body=_tokens(_recorded_region(f.data.decode(),key[1],node['wrapper']))
            else:
                matches=[d for d in plain_definitions(f.data.decode()) if d[0]==key[1]]
                if len(matches)!=1:raise ValueError('ROUTE_DEFINITION_NOT_UNIQUE')
                body=matches[0][3]
            if fingerprint(body)!=node['body_sha256']:raise ValueError('ROUTE_BODY_CHANGED')
            bodies[key]=body
        except (ValueError,UnicodeError) as e:errors.append(('DOMAIN_ROUTE_UNVERIFIED',(key,str(e))))
    edges={k:set() for k in bodies}
    for caller,target,(position,args_digest,name) in model.get('route_edges',()):
        caller=tuple(caller);target=tuple(target)
        sites=call_sites(' '.join(bodies.get(caller,())))
        if (target not in bodies or target[1]!=name or not any(s.position==position and s.expression==(name,) and not s.indirect and fingerprint(s.arguments)==args_digest for s in sites)):
            errors.append(('DOMAIN_ROUTE_EDGE_CHANGED',(caller,target)));continue
        edges[caller].add(target)
    root=tuple(model.get('api_definition',()))
    if len(root)!=2 or root[1]!=model['api'] or root not in bodies:errors.append(('DOMAIN_API_DEFINITION_UNBOUND',model['api']))
    seen=set();todo=[root]
    while todo:
        k=todo.pop()
        if k in seen:continue
        seen.add(k);todo.extend(edges.get(k,()))
    if any((p['path'],p['function']) not in seen for p in model['parts']):errors.append(('DOMAIN_SCHEMA_UNREACHABLE',model['api']))
    return tuple(errors)
