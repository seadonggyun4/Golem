"""Approved finite private publication-guard contract at registered call sites.

Only NULL or the literal as_publication_guard is supported. No general pointer,
value/alias analysis, preprocessing, runtime receiver, policy or execution proof.
Other callers of the same private writers are outside this additive profile.
"""
from dataclasses import dataclass
from capability_profile import scan_sources,Observation,Scan,_wrapper_parameter_name
from capability_c_syntax import plain_definitions,plain_declarations,call_sites
from capability_source import _tokens,_arguments
from capability_c_graph import fingerprint
from capability_ledger import observation_identity

CAPABILITY='internal.publication_guard.fixed_values'
FUNCTIONS=frozenset(('as_commit','as_publication_guard','dw_record_event','dw_record_event_guarded','event_publish','publish'))
# Caller, callee, guard slot, context slot, literal/unchanged parameter pair.
FORWARDING=(
    ('as_commit','dw_record_event_guarded',7,8,('as_publication_guard',),('l',)),
    ('dw_record_event','event_publish',7,8,('NULL',),('NULL',)),
    ('dw_record_event_guarded','event_publish',7,8,('guard',),('context',)),
    ('event_publish','publish',5,6,('guard',),('context',)),
)

@dataclass(frozen=True)
class PublicationObservation:
    allowed_values: tuple
    checked_definitions: tuple
    checked_forwarding: tuple
    blockers: tuple
    scope: str='registered_call_sites_only'
    excluded_entrypoints: tuple=('dw_event_write_guarded',)
    receiver_identity_verified: bool=False
    callee_behavior_verified: bool=False
    policy_satisfied: bool=False
    execution_verified: bool=False


def _structure(sources,model):
    scan_sources(sources,());files={f.path:f for f in sources};errors=[];parsed={};sites={};checked=[];declared={}
    nodes={n['name']:n for n in model['nodes']}
    if len(nodes)!=len(model['nodes']) or set(nodes)!=FUNCTIONS:raise ValueError('PUBLICATION_MODEL_FUNCTION_SET')
    for name,node in nodes.items():
        f=files.get(node['path'])
        try:
            if f is None or f.sha256!=node['sha256']:raise ValueError('PUBLICATION_SOURCE_MISSING_OR_DRIFT')
            found=[d for d in plain_definitions(f.data.decode(),name) if d[0]==name]
            if len(found)!=1:raise ValueError('PUBLICATION_DEFINITION_NOT_UNIQUE')
            _,prefix,parameters,body=found[0]
            if prefix!=tuple(node['prefix']) or parameters!=tuple(node['parameters']) or body!=tuple(node['body']):raise ValueError('PUBLICATION_DEFINITION_CHANGED')
            parsed[name]=(prefix,parameters,body);sites[name]=call_sites(' '.join(body));checked.append(name)
        except (ValueError,UnicodeError) as e:errors.append(('PUBLICATION_DEFINITION_UNVERIFIED',(name,str(e))))
    for rule in model['declarations']:
        f=files.get(rule['path'])
        try:
            if f is None or f.sha256!=rule['sha256']:raise ValueError('PUBLICATION_DECLARATION_SOURCE_DRIFT')
            ds=[d for d in plain_declarations(f.data.decode(),rule['name']) if d[0]==rule['name']]
            if ds!=[(rule['name'],tuple(rule['prefix']),tuple(rule['parameters']))]:raise ValueError('PUBLICATION_DECLARATION_CHANGED')
            declared[rule['name']]=ds[0][1:]
        except (ValueError,UnicodeError) as e:errors.append(('PUBLICATION_DECLARATION_UNVERIFIED',(rule['name'],str(e))))
    for name,(prefix,parameters) in declared.items():
        if name in parsed and _signature(prefix,parameters)!=_signature(*parsed[name][:2]):
            errors.append(('PUBLICATION_SIGNATURE_MISMATCH',name))
    if 'as_publication_guard' in parsed and _signature(*parsed['as_publication_guard'][:2])!=(('golem_status',),(('void','*'),)):
        errors.append(('PUBLICATION_TARGET_SIGNATURE_UNSUPPORTED','as_publication_guard'))
    expected_declarations={'as_publication_guard','as_commit','dw_record_event','dw_record_event_guarded'}
    if len(model['declarations'])!=len(expected_declarations) or {d['name'] for d in model['declarations']}!=expected_declarations:raise ValueError('PUBLICATION_DECLARATION_SET')
    edges={(r['caller'],r['callee']):r for r in model['edges']}
    if len(edges)!=len(FORWARDING) or set(edges)!={(a,b) for a,b,*_ in FORWARDING}:raise ValueError('PUBLICATION_EDGE_SET')
    forwarding=[]
    for caller,callee,guard_index,context_index,guard,context in FORWARDING:
        calls=[s for s in sites.get(caller,()) if s.expression==(callee,) and not s.indirect]
        rule=edges[caller,callee]
        if len(calls)!=1:
            errors.append(('PUBLICATION_CALL_NOT_UNIQUE',(caller,callee)));continue
        site=calls[0]
        if site.position!=rule['position'] or fingerprint(site.arguments)!=rule['arguments_sha256']:
            errors.append(('PUBLICATION_CALL_ARGUMENTS_OR_ORDER_CHANGED',(caller,callee)))
        if len(site.arguments)<=max(guard_index,context_index) or site.arguments[guard_index]!=guard or site.arguments[context_index]!=context:
            errors.append(('PUBLICATION_VALUE_OR_CONTEXT_UNSUPPORTED',(caller,callee)));continue
        forwarding.append((caller,callee,' '.join(guard),' '.join(context)))
    # Independent protocol anchors survive a fixture source/model re-pin. Full
    # bodies additionally bind lexical order and reject new unreviewed calls.
    anchors={
        'as_commit':(
            'if (st == GOLEM_OK) { const char *op = dw_text(e,"operation"); bool fenced = !strcmp(op,"begin") || !strcmp(op,"heartbeat") || !strcmp(op,"submit") || !strcmp(op,"reconcile") || !strcmp(op,"reject_output");',
            'if (fenced) { l->publication_clock = clock; l->publication_observed_ms = dw_uint(e,"observed_ms"); st = dw_record_event_guarded',
        ),
        'dw_record_event_guarded':('if (!guard) return GOLEM_ERR_INVALID_ARGUMENT;',),
        'event_publish':('if (st == GOLEM_OK) st = publish',),
        'publish':('st = golem_evidence_verify(s->cas,payload,&size,NULL); if (st == GOLEM_OK && guard) { golem_status checked = guard(context); if (checked != GOLEM_OK) return checked; } if (st == GOLEM_OK) st = dw_publish(directory,name,bytes);',),
        'as_publication_guard':('as_log *log = context;', 'golem_status st = as_clock_read(log->publication_clock,&now,&boot);', 'return st == GOLEM_OK && (now < log->publication_observed_ms || !as_live(log,now,&boot)) ? GOLEM_ERR_STALE_LEASE : st;'),
    }
    for name,clauses in anchors.items():
        body=parsed.get(name,((),(),()))[2]
        for clause in clauses:
            t=_tokens(clause)
            if sum(body[i:i+len(t)]==t for i in range(len(body)-len(t)+1))!=1:
                errors.append(('PUBLICATION_PROTOCOL_GUARD_OR_ORDER_CHANGED',name))
    for name in ('dw_record_event_guarded','event_publish','publish'):
        parameters=parsed.get(name,((),(),()))[1]
        for pattern in ('golem_status (*guard)(void *)','void *context'):
            t=_tokens(pattern)
            if not any(parameters[i:i+len(t)]==t for i in range(len(parameters)-len(t)+1)):
                errors.append(('PUBLICATION_CALLBACK_PARAMETER_CHANGED',name))
    target_calls=sites.get('as_publication_guard',())
    expected_calls=(('as_clock_read',('log->publication_clock','&now','&boot')),('as_live',('log','now','&boot')))
    actual=tuple((s.expression,s.arguments,s.indirect) for s in target_calls)
    expected=tuple(((name,),tuple(_tokens(a) for a in args),False) for name,args in expected_calls)
    if actual!=expected:errors.append(('PUBLICATION_TARGET_CALL_SET_CHANGED','as_publication_guard'))
    guard_sites=[s for s in sites.get('publish',()) if s.expression==('guard',)]
    if len(guard_sites)!=1 or guard_sites[0].arguments!=(('context',),):errors.append(('PUBLICATION_GUARD_INVOCATION_CHANGED','publish'))
    return tuple(checked),tuple(forwarding),tuple(errors)


def observation():
    fields=dict(kind='NATIVE_OPERATION',source_path='src/agent_session/storage.c',entrypoint='as_publication_guard',selector=None)
    return Observation(observation_identity(**fields),**fields)


def scan_publication(sources,model):
    if not any(f.path=='src/agent_session/storage.c' for f in sources):return Scan((),())
    _,_,errors=_structure(sources,model)
    return Scan((observation(),) if not errors else (),tuple((observation().source_path,observation().entrypoint,str(e)) for e in errors))


def inspect_publication(sources,ledger,model):
    definitions,forwarding,errors=_structure(sources,model);errors=list(errors);o=observation()
    found=[v for v in ledger['observations'] if v['id']==o.id and all(v[k]==getattr(o,k) for k in ('kind','source_path','entrypoint','selector'))]
    caps=[c for c in ledger['capabilities'] if c['id']==CAPABILITY and c['review_status']=='REVIEWED' and c['implementation']=='IMPLEMENTED' and c['current_routes']==['HOST_INTERNAL'] and c['target_routes']==['HOST_INTERNAL'] and c['effects']==['NATIVE_READ'] and c['observation_ids']==[o.id]]
    if len(found)!=1 or len(caps)!=1:errors.append(('PUBLICATION_CAPABILITY_UNBOUND',CAPABILITY))
    return PublicationObservation(('NULL','as_publication_guard'),definitions,forwarding,tuple(errors))


def _signature(prefix,parameters):
    """Finite declarator spelling shared with approved recorder parameter parser.

    Parameter names may differ (frame/out, log/context); their types and callback
    declarators must match. No typedef or ABI resolution is performed.
    """
    types=[]
    for parameter in _arguments(('(',*parameters,')'),0):
        if parameter==('void',):continue
        name=_wrapper_parameter_name(parameter)
        index=parameter.index(name)
        types.append(parameter[:index]+parameter[index+1:])
    return tuple(t for t in prefix if t not in ('static','extern')),tuple(types)
