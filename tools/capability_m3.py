"""Finite M3 selected-byte proof, never an import of inspected product code."""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_fallback import _shape
from capability_m1 import _functions
from capability_c_graph import fingerprint
from capability_c_syntax import plain_definitions
from capability_source import python_literal_names,_tokens

@dataclass(frozen=True)
class M3Observation:
    tools:tuple
    backlog_count:int
    checked_functions:int
    blockers:tuple
    native_execution_verified:bool=False
    policy_satisfaction_verified:bool=False
    client_e2e:str='NOT_RUN'


def inspect_m3(sources,ledger,model,backlog):
    scan_sources(sources,());files={f.path:f for f in sources};trees={};errors=[];checked=0;names=()
    for path,digest in model['pins']:
        f=files.get(path)
        if f is None or f.sha256!=digest:errors.append(('M3_SOURCE_MISSING_OR_DRIFT',path));continue
        if path.endswith('.py'):trees[path]=ast.parse(f.data)
    for path,name,shape in model['functions']:
        node=_functions(trees[path]).get(name) if path in trees else None
        if node is None or fingerprint(_shape(node))!=shape:errors.append(('M3_FUNCTION_CHANGED',(path,name)))
        else:checked+=1
    guards=(
     ('tools/integration_task_actions.py','shape',"c.require(name in NAMES,'TASK_TOOL')"),
     ('tools/integration_task_actions.py','shape',"c._validate(value,c.obj(fields))"),
     ('tools/integration_task_actions.py','shape',"c.require(not envelope['body'] and not envelope['context_json'] and envelope['approval'] is None,'TASK_ENVELOPE_SCOPE')"),
     ('tools/integration_task_actions.py','shape',"c.require(value[field]['session_id']==entry['session_id'],'NATIVE_OWNER_MAPPING')"),
     ('tools/integration_task_actions.py','shape',"c.require(isinstance(value['action'],dict) and value['action'].get('work_id')==entry['work_id'] and value['action'].get('operation') in ('prepare','finish','run'),'TASK_APPROVAL_SCOPE')"),
     ('tools/integration_task_actions.py','authorize',"c.require(not target.exists() and not target.is_symlink(),'TASK_DESTINATION_EXISTS')"),
     ('tools/integration_task_actions.py','authorize',"c.require(isinstance(repo,dict) and repo.get('root')==project['root'],'TASK_DISCOVERY_SCOPE')"),
     ('tools/integration_task_actions.py','command',"authorize(entry,request,project,require_new=True)"),
     ('tools/integration_mutation_contract.py','Policy.action',"tasks.authorize(entry, request, project)"),
     ('tools/integration_mutations.py','Service._preflight',"tasks.validate_observed(entry, native, {'status': status, 'next': following, 'record': record})"),
     ('tools/integration_prepare_builders.py','build',"tasks.draft(args,observed,key)"),
     ('tools/integration_prepare_builders.py','validator',"tasks.validator(args['tool'],envelope,native)"),
    )
    for path,name,expression in guards:
        node=_functions(trees[path]).get(name) if path in trees else None;wanted=_shape(ast.parse(expression,mode='eval').body)
        if node is None or sum(_shape(n)==wanted for n in ast.walk(node) if isinstance(n,ast.Call))!=1:errors.append(('M3_MANDATORY_GUARD_CHANGED',(path,name,expression)))
    try:
        names=python_literal_names(files['tools/integration_task_actions.py'].data.decode(),'NAMES',mapping=False)
        declared=python_literal_names(files['tools/integration_mutation_contract.py'].data.decode(),'NAMES',mapping=False)
        if len(names)!=20 or not set(names)<=set(declared):raise ValueError('M3_ACTION_DOMAIN')
        remote=python_literal_names(files['tools/integration_gateway_contract.py'].data.decode(),'REMOTE_READ_NAMES',mapping=False)
        if set(names)&set(remote):raise ValueError('M3_REMOTE_EXPANSION')
        for path,method in (('tools/integration_task_actions.py','draft'),('tools/integration_prepare_builders.py','build')):
            node=_functions(trees[path])[method]
            for call in (n for n in ast.walk(node) if isinstance(n,ast.Call)):
                attr=call.func.attr if isinstance(call.func,ast.Attribute) else call.func.id if isinstance(call.func,ast.Name) else None
                if attr in ('capture','_mutate','execute','apply','native_action','Policy','authorize','command'):raise ValueError('M3_DRAFT_DISPATCH')
        # Every added CLI validation branch calls the public parser before opening any store.
        from capability_profile import _close
        for path,function,parser in (
          ('src/cli/agent_session.c','golem_cli_session_binding','golem_session_binding_request_validate'),
          ('src/cli/role.c','golem_cli_role','golem_role_request_validate'),
          ('src/cli/approval.c','golem_cli_approval','golem_approval_request_validate'),
          ('src/cli/document.c','golem_cli_document','golem_work_spec_validate')):
            body=next(d[3] for d in plain_definitions(files[path].data.decode()) if d[0]==function)
            start=next(i for i in range(len(body)-1) if body[i:i+2]==('if','('));end=_close(body,start+1);finish=_close(body,end+1);branch=body[end+2:finish]
            if branch.count(parser)!=1 or any(n in branch for n in ('golem_document_store_open','golem_session_binding_call','golem_role_call','golem_approval_call','golem_document_store_create')):raise ValueError('M3_CORE_VALIDATOR_BRANCH')
        for path,function,parser in (('src/cli/lineage.c','golem_cli_lineage','golem_lineage_store'),('src/cli/adapter.c','golem_cli_adapter','golem_adapter_noop_run_stage')):
            body=next(d[3] for d in plain_definitions(files[path].data.decode()) if d[0]==function)
            if body.count(parser)!=1:raise ValueError('M3_NATIVE_ROUTE_MISSING')
    except (KeyError,ValueError,StopIteration,AttributeError,SyntaxError) as e:errors.append(('M3_CONNECTION_UNVERIFIED',str(e)))
    caps={c['id']:c for c in ledger['capabilities']};seen=set()
    for row in backlog:
        cid=row['capability_id'];cap=caps.get(cid)
        if cid in seen or cap is None or cap['review_status']!='REVIEWED' or cap['implementation']!='IMPLEMENTED' or tuple(cap['target_routes'])!=row['target_routes'] or not set(row['target_routes'])<=set(cap['current_routes']):errors.append(('M3_BACKLOG_NOT_CONNECTED',cid))
        seen.add(cid)
        if not row['tools'] or not set(row['tools'])<=set(names)|{'session_claim','session_begin','session_resume','session_reconcile','session_submit','document_submit','execution_request'}:errors.append(('M3_BACKLOG_ROUTE_UNREVIEWED',cid))
        if row['client_e2e']!='NOT_RUN' or row['authority']!='EXACT_OWNER_D4_ACTION_AND_NATIVE_CONTRACT':errors.append(('M3_BACKLOG_AUTHORITY_PROMOTION',cid))
    if len(backlog)!=60 or len(seen)!=60:errors.append(('M3_BACKLOG_DOMAIN_CHANGED',None))
    return M3Observation(tuple(names),len(backlog),checked,tuple(errors))
