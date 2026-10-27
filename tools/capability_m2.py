"""Finite M2 preparation/owner-handoff checks over selected bytes, never execute.

Frozen functions plus independent guards distinguish shape/plan review from D4
approval, admission and native effects. No imports of inspected implementations.
"""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_fallback import _shape
from capability_m1 import _functions
from capability_c_graph import fingerprint
from capability_c_syntax import plain_definitions
from capability_source import python_literal_names,_tokens

@dataclass(frozen=True)
class M2Observation:
    tools: tuple
    checked_functions: int
    backlog_dependencies: int
    retained_delivery_milestones: tuple
    blockers: tuple
    approval_created: bool=False
    native_execution_verified: bool=False
    client_e2e: str='NOT_RUN'


def inspect_m2(sources,ledger,model,backlog):
    scan_sources(sources,());files={f.path:f for f in sources};trees={};errors=[];checked=0
    for path,digest in model['pins']:
        f=files.get(path)
        if f is None or f.sha256!=digest:errors.append(('M2_SOURCE_MISSING_OR_DRIFT',path));continue
        if path.endswith('.py'):trees[path]=ast.parse(f.data)
    for path,name,shape in model['functions']:
        try:
            node=_functions(trees[path])[name]
            if fingerprint(_shape(node))!=shape:raise ValueError('M2_FUNCTION_STRUCTURE_CHANGED')
            checked+=1
        except (KeyError,ValueError) as e:errors.append(('M2_FUNCTION_UNVERIFIED',(path,name,str(e))))
    guards=(
      ('tools/integration_preparations.py','native',"c.require(name in ('workflow_read','native_validate'),'PREPARATION_READ_ROUTE')"),
      ('tools/integration_preparations.py','native',"c._validate(args,native_reads.SCHEMAS[name])"),
      ('tools/integration_preparations.py','owner_action',"c.require(service.preparation_policy is not None,'PREPARATION_OWNER_POLICY_REQUIRED')"),
      ('tools/integration_preparations.py','owner_action',"c.require(policy.transfer.digest==service.transfer.digest,'PREPARATION_POLICY_BINDING')"),
      ('tools/integration_preparations.py','load',"c.require(service.preparation_plans.get(args['plan_id'])==args['plan_sha256'],'PREPARATION_INSTANCE_OR_REFERENCE')"),
      ('tools/integration_preparations.py','load',"c.require(c.sha(raw)==args['plan_sha256'],'PREPARATION_CHANGED')"),
      ('tools/integration_preparations.py','load',"c.require(plan['binding']==scope['binding'] and (plan['project_id'],plan['work_id'])==(args['project_id'],args['work_id']),'PREPARATION_SCOPE')"),
      ('tools/integration_preparations.py','load',"c.require(0<=time.monotonic_ns()-plan['created_monotonic_ns']<=MAX_AGE_NS,'PREPARATION_EXPIRED')"),
      ('tools/integration_preparations.py','compare_basis',"c.require(plan['basis']==current,'PREPARATION_STALE')"),
      ('tools/integration_preparations.py','confirmed',"c.require(payload['kind']=='OWNER_ACTION','PREPARATION_OWNER_REVIEW_REQUIRED')"),
      ('tools/integration_preparations.py','confirmed',"c.require(entry==payload['entry'] and entry['action']['sha256']==payload['action_sha256'] and value==payload['action'],'PREPARATION_ACTION_CHANGED')"),
      ('tools/integration_preparations.py','read',"c.require(digest==c.sha(c.encoded(args)),'PREPARATION_REQUEST_CONFLICT')"),
      ('tools/integration_mutation_contract.py','native_action','action_shape(entry, value)'),
      ('tools/integration_mutation_contract.py','native_action','c.require(c.sha(data) == decision_pin["sha256"], "DECISION_CHANGED")'),
      ('tools/integration_mutation_contract.py','action_shape','c.require(allow_missing_approval is True, "PENDING_APPROVAL")'),
      ('tools/integration_mutations.py','Service.__init__','reads.Service(policy.transfer, resources, preparation_policy=policy)'),
    )
    for path,name,expression in guards:
        node=_functions(trees[path]).get(name) if path in trees else None
        shape=_shape(ast.parse(expression,mode='eval').body)
        if node is None or sum(_shape(n)==shape for n in ast.walk(node) if isinstance(n,ast.Call))!=1:
            errors.append(('M2_MANDATORY_GUARD_CHANGED',(path,name,expression)))
    names=()
    try:
        path='tools/integration_preparations.py'
        names=python_literal_names(files[path].data.decode(),'NAMES',mapping=False)
        if len(names)!=6 or set(names)!=set(python_literal_names(files[path].data.decode(),'SCHEMAS',mapping=True)):raise ValueError('M2_DECLARED_SET')
        service=trees['tools/integration_service.py'];schema=next(n.value for n in service.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCHEMAS' for t in n.targets))
        for name in names:
            values=[v for k,v in zip(schema.keys,schema.values) if isinstance(k,ast.Constant) and k.value==name]
            if len(values)!=1 or _shape(values[0])!=_shape(ast.parse('preparations.SCHEMAS['+repr(name)+']',mode='eval').body):raise ValueError('M2_SCHEMA_BINDING')
        handler=_functions(service)['Service._call_locked'];branches=[]
        for n in ast.walk(handler):
            if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='name' and len(n.test.ops)==1 and isinstance(n.test.ops[0],ast.In) and isinstance(n.test.comparators[0],ast.Tuple):
                domain=[v.value for v in n.test.comparators[0].elts if isinstance(v,ast.Constant)]
                if set(domain)==set(names):branches.append(n)
        wanted=_shape(ast.parse('result = preparations.read(self, scope, name, args)').body[0])
        if len(branches)!=1 or _shape(branches[0].body[0])!=wanted:raise ValueError('M2_HANDLER_BINDING')
        remote=python_literal_names(files['tools/integration_gateway_contract.py'].data.decode(),'REMOTE_READ_NAMES',mapping=False)
        if set(names)&set(remote):raise ValueError('M2_REMOTE_EXPANSION')
        functions=_functions(trees['tools/integration_mutation_contract.py']);shape=functions['action_shape'];wrapper=functions['native_action']
        if [n.arg for n in wrapper.args.args]!=['entry','value'] or wrapper.args.kwonlyargs:raise ValueError('M2_DISPATCH_SHAPE_ARGUMENTS')
        if len(shape.args.kwonlyargs)!=1 or shape.args.kwonlyargs[0].arg!='allow_missing_approval' or _shape(shape.args.kw_defaults[0])!=_shape(ast.Constant(value=False)):raise ValueError('M2_APPROVAL_DEFAULT_CHANGED')
        # Pure shape function must never acquire assets, processes or policies.
        banned={'capture','run','regular','file_pin','open','native_action','Policy','authorize','execute','_mutate'}
        for call in (n for n in ast.walk(shape) if isinstance(n,ast.Call)):
            name=call.func.id if isinstance(call.func,ast.Name) else call.func.attr if isinstance(call.func,ast.Attribute) else None
            if name is None or name in banned:raise ValueError('M2_SHAPE_NOT_PURE')
        for path in ('tools/integration_preparations.py','tools/integration_prepare_builders.py'):
            for call in (n for n in ast.walk(trees[path]) if isinstance(n,ast.Call)):
                if isinstance(call.func,ast.Attribute) and call.func.attr in ('_mutate','execute','apply','native_action'):raise ValueError('M2_ACTION_DISPATCH_FORBIDDEN')
        definition=next(d for d in plain_definitions(files['src/cli/agent_session.c'].data.decode()) if d[0]=='golem_cli_agent_session')
        body=definition[3];text=' '.join(body)
        from capability_profile import _close
        start=next(i for i in range(len(body)-1) if body[i:i+2]==('if','('));end=_close(body,start+1)
        if body[start+2:end]!=_tokens('argc == 4 && !strcmp(argv[2], "validate")') or body[end+1]!='{':raise ValueError('M2_SESSION_VALIDATE_BRANCH')
        finish=_close(body,end+1);validation=body[end+2:finish]
        if any(v in validation for v in ('golem_document_store_open','golem_agent_session_call','golem_agent_session_resume_context')):raise ValueError('M2_VALIDATOR_STORE_OR_MUTATION')
        anchor=_tokens('golem_agent_request_validate((golem_bytes){input.data, input.size}, NULL)')
        if sum(validation[i:i+len(anchor)]==anchor for i in range(len(validation)-len(anchor)+1))!=1:raise ValueError('M2_CORE_VALIDATOR_MISSING')
    except (KeyError,ValueError,StopIteration,AttributeError,SyntaxError) as e:errors.append(('M2_CONNECTION_UNVERIFIED',str(e)))
    caps={c['id']:c for c in ledger['capabilities']};seen=set();milestones={}
    for row in backlog:
        cid=row['capability_id'];cap=caps.get(cid)
        if cid in seen or cap is None or cap['review_status']!='REVIEWED' or tuple(cap['target_routes'])!=row['target_routes']:
            errors.append(('M2_BACKLOG_MISSING_OR_CHANGED',cid));continue
        seen.add(cid);milestones[row['milestone']]=milestones.get(row['milestone'],0)+1
        if row['preparation_tool'] not in names or not row['basis'] or not row['remaining_obligation']:
            errors.append(('M2_DEPENDENCY_UNREVIEWED',cid))
    if len(backlog)!=134 or len(seen)!=134:errors.append(('M2_BACKLOG_DOMAIN_CHANGED',None))
    return M2Observation(tuple(names),checked,len(backlog),tuple(sorted(milestones.items())),tuple(errors))
