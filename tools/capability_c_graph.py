"""Finite reviewed C graph: exact functions/calls, public ABI/callback endpoints.

No source discovery, compilation, macro expansion, runtime pointer resolution,
policy satisfaction or execution proof. Cycles are finite topology, not recursive
execution analysis. Models are reviewed inputs and never refreshed by a check.
"""
from dataclasses import dataclass
import hashlib,json
from capability_c_syntax import plain_definitions,call_sites,declaration_tokens,public_declaration
from capability_profile import scan_sources,_recorded_region
from capability_source import _tokens,_arguments
from capability_callbacks import declarations
from capability_wrapper import verify_definition

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()

@dataclass(frozen=True)
class GraphObservation:
    roots: tuple
    checked_nodes: int
    checked_calls: int
    public_endpoints: tuple
    callback_endpoints: tuple
    blockers: tuple
    execution_verified: bool=False
    receiver_identity_verified: bool=False
    policy_satisfied: bool=False

def _try_definition(raw,variable):
    expected=_tokens('#define TRY(call) do { '+variable+' = (call); if ('+variable+' != GOLEM_OK) goto done; } while (0)')
    found=[];current=''
    for line in raw.decode().splitlines():
        if current or line.lstrip().startswith('#'):
            current+=line.rstrip().removesuffix('\\')+'\n'
            if not line.rstrip().endswith('\\'):
                t=_tokens(current)
                if t[:3]==('#','define','TRY'):found.append(t)
                current=''
    if found!=[expected]:raise ValueError('TRY_MODEL_CHANGED')

CALL_FIELDS=("expression","arguments_sha256","position","indirect","kind","target","binding","parameter_binding")

def call_rules(node):
    return tuple(c if isinstance(c,dict) else dict(zip(CALL_FIELDS,c)) for c in node["calls"])

def inspect_graph(sources,ledger,model,domains=None):
    scan_sources(sources,());files={s.path:s for s in sources};errors=[];parsed={};nodes={(n['path'],n['name']):n for n in model['nodes']}
    if len(nodes)!=len(model['nodes']):raise ValueError('GRAPH_DUPLICATE_NODE')
    checked={};public=set();callbacks=set();calls_count=0;verified_calls={};parameters_by_node={}
    callback_rules={r['id']:r for r in model['callbacks']}
    for path,var in model['try_macros']:
        try:_try_definition(files[path].data,var)
        except (ValueError,KeyError) as e:errors.append(('TRY_UNVERIFIED',path))
    for key,node in nodes.items():
        path,name=key;source=files.get(path)
        if source is None or source.sha256!=node['sha256']:
            errors.append(('GRAPH_SOURCE_MISSING_OR_DRIFT',key));continue
        try:
            if node['wrapper']:
                definition=files.get('src/common/record_internal.h')
                if definition is None or definition.sha256!=model['wrapper_sha256']:raise ValueError('WRAPPER_SOURCE_DRIFT')
                verify_definition(definition.data,node['wrapper'])
                body=_tokens(_recorded_region(source.data.decode(),name,node['wrapper']))
                tokens=_tokens(source.data.decode());matches=[]
                for i,t in enumerate(tokens[:-1]):
                    if t==node['wrapper'] and tokens[i+1]=='(':
                        a=_arguments(tokens,i+1)
                        if a[0]==(name,):matches.append(a[1][1:-1])
                if len(matches)!=1:raise ValueError('WRAPPER_SIGNATURE_UNIQUE')
                parameters=matches[0]
            else:
                if path not in parsed:parsed[path]=plain_definitions(source.data.decode())
                matches=[d for d in parsed[path] if d[0]==name]
                if len(matches)!=1:raise ValueError('FUNCTION_NOT_UNIQUE')
                _,prefix,parameters,body=matches[0]
            parameters_by_node[key]=parameters
            if fingerprint(parameters)!=node['parameters_sha256'] or fingerprint(body)!=node['body_sha256']:
                raise ValueError('FUNCTION_STRUCTURE_CHANGED')
            actual=call_sites(' '.join(body));expected=call_rules(node)
            if len(actual)!=len(expected):raise ValueError('CALL_OCCURRENCE_SET_CHANGED')
            for site,rule in zip(actual,expected):
                if (' '.join(site.expression),fingerprint(site.arguments),site.position,site.indirect)!=(rule['expression'],rule['arguments_sha256'],rule['position'],rule['indirect']):
                    raise ValueError('CALL_ARGUMENT_POSITION_OR_RECEIVER_CHANGED')
                kind=rule['kind'];target=rule['target'];calls_count+=1
                verified_calls[key,site.position]=site
                if kind=='helper':
                    if site.indirect or tuple(target) not in nodes:raise ValueError('HELPER_NOT_REGISTERED')
                    target_node=nodes[tuple(target)]
                    if target[0]!=path and target_node['static']:raise ValueError('CROSS_FILE_STATIC_HELPER')
                elif kind=='public':
                    if site.indirect:raise ValueError('INDIRECT_NATIVE_API')
                    caps=[c for c in ledger['capabilities'] if c['id']=='native.'+target and c['implementation']=='IMPLEMENTED' and c['review_status']=='REVIEWED']
                    if len(caps)!=1:raise ValueError('PUBLIC_CAPABILITY_UNBOUND')
                    endpoint=model['public'][target];header=files.get(endpoint[0])
                    if header is None or header.sha256!=endpoint[1]:raise ValueError('PUBLIC_SOURCE_MISSING_OR_DRIFT')
                    prototype=public_declaration(header.data,target)
                    expected_arity=_arity(prototype[2])
                    if len(site.arguments)!=expected_arity and not (expected_arity==0 and site.arguments==((),)):
                        raise ValueError("PUBLIC_CALL_ARITY_CHANGED")
                    obs=[o for o in ledger['observations'] if o['kind']=='C_PUBLIC_DECLARATION' and o['source_path']==endpoint[0] and o['entrypoint']==target]
                    if len(obs)!=1 or obs[0]['id'] not in caps[0]['observation_ids']:raise ValueError('PUBLIC_OBSERVATION_UNBOUND')
                    if target in model['operation_apis'] and (domains is None or target not in domains or domains[target].get('blockers')):
                        raise ValueError('JSON_OPERATION_DOMAIN_UNVERIFIED')
                    public.add(target)
                elif kind=='external':
                    if site.indirect or target not in model['externals']:raise ValueError('UNREGISTERED_EXTERNAL')
                    declaration_tokens(source.data.decode(),target)
                elif kind=='macro':
                    if site.expression!=('TRY',) or not any(p==path for p,v in model['try_macros']) or len(site.arguments)!=1:
                        raise ValueError('MACRO_UNSUPPORTED')
                elif kind=='callback':
                    cb=callback_rules.get(target)
                    if cb is None or not site.indirect:raise ValueError('CALLBACK_NOT_REGISTERED')
                    header=files.get(cb['path'])
                    if header is None or header.sha256!=cb['sha256'] or not cb['path'].startswith('include/golem/'):
                        raise ValueError('CALLBACK_PUBLIC_SOURCE_DRIFT')
                    if (cb['structure'],cb['field'],tuple(cb['returns']),tuple(cb['parameters'])) not in declarations(header.data):raise ValueError('CALLBACK_DECLARATION_CHANGED')
                    if len(site.arguments)!=_arity(tuple(cb['parameters'])):raise ValueError('CALLBACK_CALL_ARITY_CHANGED')
                    if not any(c['id']==target and c['review_status']=='REVIEWED' for c in ledger['capabilities']):raise ValueError('CALLBACK_CAPABILITY_UNBOUND')
                    if rule['binding']:
                        binding=rule['binding'];f=files.get(binding['path'])
                        if f is None or f.sha256!=binding['sha256'] or not _contains(declaration_tokens(f.data.decode()),tuple(binding['tokens'])):
                            raise ValueError('CALLBACK_RECEIVER_TYPE_BINDING_CHANGED')
                    if not _contains(parameters,tuple(rule['parameter_binding'])):raise ValueError('CALLBACK_PARAMETER_TYPE_BINDING_CHANGED')
                    callbacks.add(target)
                elif kind=='null_callback':
                    if site.expression!=('guard',) or 'guard' not in node['null_parameters'] or not _contains(body,_tokens('if (st == GOLEM_OK && guard) {')):
                        raise ValueError('NULL_CALLBACK_GUARD_UNVERIFIED')
                else:raise ValueError('UNKNOWN_GRAPH_BOUNDARY')
            checked[key]=True
        except (ValueError,UnicodeError,IndexError,KeyError) as e:errors.append(('GRAPH_NODE_UNVERIFIED',(key,str(e))))
    for caller_key,node in nodes.items():
        for edge in call_rules(node):
            if edge['kind']!='helper':continue
            target=tuple(edge['target']);site=verified_calls.get((caller_key,edge['position']))
            if target in parameters_by_node and site is not None:
                arity=_arity(parameters_by_node[target])
                if len(site.arguments)!=arity and not (arity==0 and site.arguments==((),)):
                    errors.append(('HELPER_ARITY_UNVERIFIED',(caller_key,target)))
    # Exact NULL forwarding, only on the explicitly registered two private slots.
    # There is no general value/alias propagation or private callback termination.
    for key,node in nodes.items():
        for parameter in node['null_parameters']:
            if key in map(tuple,model['roots']):errors.append(('NULL_ROOT_PARAMETER',key));continue
            incoming=[]
            for caller_key,caller in nodes.items():
                for edge in call_rules(caller):
                    if edge['kind']=='helper' and tuple(edge['target'])==key:incoming.append((caller_key,caller,edge))
            if not incoming:errors.append(('NULL_SLOT_WITHOUT_INCOMING_EDGE',key))
            for caller_key,caller,edge in incoming:
                site=verified_calls.get((caller_key,edge['position']));index=node['null_indices'][parameter]
                value=site.arguments[index] if site is not None and index<len(site.arguments) else ()
                if value!=('NULL',) and not (len(value)==1 and value[0] in caller['null_parameters']):
                    errors.append(('NULL_FORWARDING_UNVERIFIED',(caller_key,key,parameter)))
    return GraphObservation(tuple(tuple(r) for r in model['roots']),len(checked),calls_count,tuple(sorted(public)),tuple(sorted(callbacks)),tuple(errors))

def _contains(tokens,selected):
    return any(tokens[i:i+len(selected)]==selected for i in range(len(tokens)-len(selected)+1))


def _arity(parameters):
    if parameters in ((),('void',)):return 0
    # Reuse the balanced argument splitter on an explicit declarator, not text
    # comma counting (callback declarators contain nested parameter commas).
    return len(_arguments(('(',*parameters,')'),0))
