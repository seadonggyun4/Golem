"""Mandatory M5 static source/contract proof. Never imports inspected runtime code."""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_m1 import _functions
from capability_fallback import _shape
from capability_c_graph import fingerprint
from capability_c_syntax import plain_definitions
from capability_source import python_literal_names,_tokens

@dataclass(frozen=True)
class M5Observation:
    read_tools:tuple
    action_tools:tuple
    preparation_tools:tuple
    backlog_count:int
    checked_functions:int
    blockers:tuple
    scheduler_implemented:bool=False
    merge_broker_implemented:bool=False
    native_execution_verified:bool=False
    client_e2e:str='NOT_RUN'
    actual_merge:str='NOT_RUN'
    implementation_required:tuple=('TASK_DAG_SCHEDULER','TYPED_EDGE_EVIDENCE_ACCEPTANCE','RESOURCE_RECEIVER_BROKER','MERGE_QUEUE','INTEGRATION_WORKSPACE_AND_FRESH_QA','TARGET_REF_CAS_BROKER','MERGE_PUBLICATION_RECEIPT')


def literal_tuple(tree,name):
    values=[n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
    if len(values)!=1 or not isinstance(values[0],ast.Tuple) or not all(isinstance(n,ast.Constant) and type(n.value) is str for n in values[0].elts):raise ValueError('M5_LITERAL_TUPLE')
    result=tuple(n.value for n in values[0].elts)
    if len(result)!=len(set(result)):raise ValueError('M5_DUPLICATE_LITERAL')
    return result


def inspect_m5(sources,ledger,model,backlog):
    scan_sources(sources,());files={f.path:f for f in sources};trees={};errors=[];checked=0;reads=();actions=();preps=()
    for path,digest in model['pins']:
        f=files.get(path)
        if f is None or f.sha256!=digest:errors.append(('M5_SOURCE_MISSING_OR_DRIFT',path));continue
        if path.endswith('.py'):trees[path]=ast.parse(f.data)
    for path,name,shape in model['functions']:
        node=_functions(trees[path]).get(name) if path in trees else None
        if node is None or fingerprint(_shape(node))!=shape:errors.append(('M5_FUNCTION_CHANGED',(path,name)))
        else:checked+=1
    guards=(
      ('tools/integration_parallel_hosts.py','Hosts.__init__',"c.require(approve_hosts is True,'OWNER_PARALLEL_HOST_APPROVAL_REQUIRED')"),
      ('tools/integration_parallel_hosts.py','Hosts.current',"c.require(c.sha(raw)==self.digest,'PARALLEL_HOST_POLICY_CHANGED')"),
      ('tools/integration_parallel_hosts.py','Hosts.check',"c.require(c.sha(raw)==row['config']['sha256'],'PARALLEL_HOST_CONFIG_CHANGED')"),
      ('tools/integration_parallel_hosts.py','Hosts.check',"self.policy.registry.authorize(scope['binding'],work_id,operation)"),
      ('tools/integration_parallel_hosts.py','Hosts.select',"c.require(len(matches)==1 and matches[0]['action_sha256']==entry['action']['sha256'],'PARALLEL_HOST_ACTION_PIN')"),
      ('tools/integration_parallel_hosts.py','Hosts.select',"c.require(selected['termination'] is not None,'OPERATOR_TERMINATION_ATTESTATION_REQUIRED')"),
      ('tools/integration_parallel_hosts.py','Hosts.select',"c.require(c.sha(raw)==pin['sha256'],'TERMINATION_ATTESTATION_CHANGED')"),
      ('tools/integration_parallel_hosts.py','Hosts.query',"c.require(operation in READ_OPS and operation in row['operations'],'PARALLEL_HOST_QUERY_SCOPE')"),
      ('tools/integration_parallel_hosts.py','Hosts._capture',"records.capture(argv,output,backend.TIMEOUT_SECONDS,cwd=output,observe_source=False,env=backend.ENVIRONMENT,limit=c.MAX_NATIVE)"),
      ('tools/integration_parallel_actions.py','shape',"c.require(not envelope['body'] and not envelope['context_json'] and not envelope['count_json'] and envelope['approval'] is None,'PARALLEL_ENVELOPE_SCOPE')"),
      ('tools/integration_parallel_preparations.py','structure',"c.require(visited==len(tasks),'PARALLEL_CYCLE')"),
      ('tools/integration_parallel_preparations.py','reobserve',"c.require(document.get('digest')==reference['digest'],'PARALLEL_SELECTION_DRIFT')"),
      ('tools/integration_parallel_preparations.py','read',"c.require(before==reobserve(service,scope,plan,current),'OBSERVATION_STALE')"),
      ('tools/integration_parallel_preparations.py','read',"prep.seal(service,scope,args,after,before,payload)"),
      ('tools/integration_mutations.py','Service._admit',"c.require(self.parallel_hosts is not None, 'OWNER_PARALLEL_HOST_REQUIRED')"),
      ('tools/integration_mutations.py','Service._admit',"c.require(not existing_only, 'ORIGINAL_RESULT_NOT_FOUND')"),
      ('tools/integration_mutations.py','Service.result',"self._admit(name, args, existing_only=True)"),
      ('tools/integration_parallel_reads.py','read',"service.parallel_result('workspace_request',{key:args[key] for key in ('project_id','work_id','action_id','request_id')})"),
      ('tools/integration_mutations.py','Service._argv',"self.parallel_hosts.command(entry, value, output)"),
      ('tools/integration_preparations.py','owner_action',"service.parallel_hosts.select(entry,value)"),
    )
    for path,name,expression in guards:
        node=_functions(trees[path]).get(name) if path in trees else None;wanted=_shape(ast.parse(expression,mode='eval').body)
        if node is None or sum(_shape(n)==wanted for n in ast.walk(node) if isinstance(n,ast.Call))!=1:errors.append(('M5_MANDATORY_GUARD_CHANGED',(path,name,expression)))
    try:
        actions=python_literal_names(files['tools/integration_parallel_actions.py'].data.decode(),'NAMES',mapping=False)
        reads=python_literal_names(files['tools/integration_parallel_reads.py'].data.decode(),'NAMES',mapping=False)
        preps=python_literal_names(files['tools/integration_parallel_preparations.py'].data.decode(),'NAMES',mapping=False)
        if set(actions)!={'inventory_capture','candidate_request','workspace_request'} or set(reads)!={'candidate_read','inventory_read','workspace_read'} or set(preps)!={'parallel_prepare','merge_prepare'}:raise ValueError('M5_TOOL_DOMAIN')
        declared=python_literal_names(files['tools/integration_mutation_contract.py'].data.decode(),'NAMES',mapping=False)
        transfer=python_literal_names(files['tools/integration_transfer.py'].data.decode(),'NAMES',mapping=False)
        remote=python_literal_names(files['tools/integration_gateway_contract.py'].data.decode(),'REMOTE_READ_NAMES',mapping=False)
        if not set(actions)<=set(declared) or not set((*reads,*preps))<=set(transfer) or set((*actions,*reads,*preps))&set(remote):raise ValueError('M5_DECLARATION_OR_REMOTE_SCOPE')
        service=trees['tools/integration_service.py'];schema=next(n.value for n in service.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCHEMAS' for t in n.targets))
        for module,names in (('parallel_reads',reads),('parallel_preparations',preps)):
            for name in names:
                values=[v for k,v in zip(schema.keys,schema.values) if isinstance(k,ast.Constant) and k.value==name]
                if len(values)!=1 or _shape(values[0])!=_shape(ast.parse(module+'.SCHEMAS['+repr(name)+']',mode='eval').body):raise ValueError('M5_SCHEMA_ALIAS')
            node=_functions(service)['Service._call_locked'];branches=[]
            for n in ast.walk(node):
                if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and _shape(n.test.left)==_shape(ast.Name(id='name',ctx=ast.Load())) and len(n.test.comparators)==1 and isinstance(n.test.comparators[0],ast.Tuple) and {v.value for v in n.test.comparators[0].elts if isinstance(v,ast.Constant)}==set(names):branches.append(n)
            if len(branches)!=1 or _shape(branches[0].body[0])!=_shape(ast.parse('result = '+module+'.read(self, scope, name, args)').body[0]):raise ValueError('M5_READ_HANDLER')
        candidate=literal_tuple(trees['tools/integration_parallel_actions.py'],'CANDIDATE_OPS')
        workspace=literal_tuple(trees['tools/integration_parallel_actions.py'],'WORKSPACE_OPS')
        query=literal_tuple(trees['tools/integration_parallel_hosts.py'],'READ_OPS')
        if set(candidate)!={'create','enroll','reserve','start','cancel','settle','diff-seal','review','select','cohort-record'} or set(workspace)!={'workspace-create','workspace-resume','workspace-activate','workspace-seal','workspace-retain','workspace-remove'} or set(query)!={'compare','review-check','target-check'}:raise ValueError('M5_NATIVE_OPERATION_DOMAIN')
        unimplemented=literal_tuple(trees['tools/integration_parallel_preparations.py'],'UNIMPLEMENTED')
        if set(unimplemented)!={'TASK_DAG_SCHEDULER','TYPED_EDGE_EVIDENCE_ACCEPTANCE','RESOURCE_RECEIVER_BROKER','MERGE_QUEUE','INTEGRATION_WORKSPACE_AND_FRESH_QA','TARGET_REF_CAS_BROKER','MERGE_PUBLICATION_RECEIPT'}:raise ValueError('M5_UNIMPLEMENTED_OBLIGATION_REMOVED')
        node=_functions(trees['tools/integration_parallel_preparations.py'])['read'];payload=next(n.value for n in ast.walk(node) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='payload' for t in n.targets))
        fields={k.value:v for k,v in zip(payload.keys,payload.values) if isinstance(k,ast.Constant)}
        for key,value in (('scheduler_state','NOT_IMPLEMENTED'),('merge_state','NOT_IMPLEMENTED'),('edge_acceptance','NOT_EVALUATED'),('readiness','NOT_EVALUATED'),('resources_reserved',False),('merge_authorized',False),('qa_pass_verified',False),('target_ref_cas_verified',False)):
            if _shape(fields.get(key))!=_shape(ast.Constant(value=value)):raise ValueError('M5_AUTHORITY_OR_IMPLEMENTATION_PROMOTION')
        for p in ('tools/integration_parallel_actions.py','tools/integration_parallel_preparations.py'):
            for call in (n for n in ast.walk(trees[p]) if isinstance(n,ast.Call)):
                name=call.func.attr if isinstance(call.func,ast.Attribute) else call.func.id if isinstance(call.func,ast.Name) else None
                if name in ('capture','Popen','execute','apply','_mutate','native_action'):raise ValueError('M5_PREPARATION_DISPATCH_FORBIDDEN')
        admit=_functions(trees['tools/integration_mutations.py'])['Service._admit']
        stop=_shape(ast.parse('c.require(not existing_only, "ORIGINAL_RESULT_NOT_FOUND")',mode='eval').body)
        gate=next(n for n in ast.walk(admit) if isinstance(n,ast.Call) and _shape(n)==stop)
        for call in (n for n in ast.walk(admit) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('mkdir','save')):
            if call.lineno<=gate.lineno:raise ValueError('M5_RESULT_READ_CREATES_INTENT')
        expected=ast.parse('if name in parallel.HOST_NAMES and previous.get("tool") == name and previous.get("action") == entry and (directory / "dispatch-intent.json").exists():\n    raise c.IntegrationError("PARALLEL_ACTION_ALREADY_DISPATCHED_REVIEW_ORIGINAL")').body[0]
        if sum(_shape(n)==_shape(expected) for n in ast.walk(admit))!=1:raise ValueError('M5_REDISPATCH_GUARD')
    except (KeyError,ValueError,StopIteration,AttributeError,TypeError,SyntaxError) as e:errors.append(('M5_CONNECTION_UNVERIFIED',str(e)))
    for path,function,anchors in (
      ('src/cli/candidate_host_runtime.c','resolve_member',('golem_document_store_open(b->member.work_root, !readonly, NULL, &b->member.work, NULL)','!strcmp(op, \"compare\")','!strcmp(op, \"review-check\")','!strcmp(op, \"target-check\")')),
      ('src/cli/candidate_host_runtime.c','authorize',('if (!h->attested)','as_active(log.state)','GOLEM_ERR_LEASE_BUSY')),
      ('src/cli/candidate_host_runtime.c','workspace_check',('if (terminating && !h->attested)','as_active(log.state)','as_load(member.work, NULL, NULL, &log)')),
      ('src/cli/candidate_host_runtime.c','ch_call',('golem_work_record(h->parent,','golem_agent_session_call(h->parent,','GOLEM_WORKSPACE_RESUME','GOLEM_WORKSPACE_RETAIN','GOLEM_WORKSPACE_REMOVE','golem_workspace_call(b->member.work, b->member.workspace, operation,','Use typed, operator-attested settle.')),
      ('src/cli/work.c','golem_cli_work',('golem_inventory_policy_validate','golem_inventory_capture','golem_inventory_compare'))):
        try:
            body=next(d[3] for d in plain_definitions(files[path].data.decode()) if d[0]==function)
            for text in anchors:
                if text=='Use typed, operator-attested settle.':continue # comment not executable; raw finish guard below
                anchor=_tokens(text)
                if not any(body[i:i+len(anchor)]==anchor for i in range(len(body)-len(anchor)+1)):raise ValueError('M5_NATIVE_GUARD_OR_API_MISSING')
            if function=='ch_call':
                anchor=_tokens('if (st == GOLEM_OK && !strcmp(op, "finish")) st = GOLEM_ERR_APPROVAL_REQUIRED;')
                if not any(body[i:i+len(anchor)]==anchor for i in range(len(body)-len(anchor)+1)):raise ValueError('M5_RAW_FINISH_ALLOWED')
        except (KeyError,ValueError,StopIteration) as e:errors.append(('M5_NATIVE_CONNECTION_UNVERIFIED',(path,function,str(e))))
    caps={cap['id']:cap for cap in ledger['capabilities']};seen=set()
    for row in backlog:
        cid=row['capability_id'];cap=caps.get(cid)
        if cid in seen or cap is None or cap['review_status']!='REVIEWED' or cap['implementation']!='IMPLEMENTED' or tuple(cap['target_routes'])!=row['target_routes'] or not set(row['target_routes'])<=set(cap['current_routes']):errors.append(('M5_BACKLOG_NOT_CONNECTED',cid))
        seen.add(cid)
        if not set(row['tools'])<=set((*actions,*reads,*preps,'context_publish')) or not row['scope'] or row['client_e2e']!='NOT_RUN' or row['actual_merge']!='NOT_RUN' or row['scheduler_implemented'] or row['merge_broker_implemented'] or row['authority']!='EXPLICIT_D1_D2_D4_AND_OPTIONAL_OWNER_NATIVE_HOST_ONLY':errors.append(('M5_BACKLOG_SCOPE_CHANGED',cid))
    if len(backlog)!=47 or len(seen)!=47 or fingerprint(backlog)!=model['backlog_sha256']:errors.append(('M5_BACKLOG_DOMAIN_CHANGED',None))
    return M5Observation(tuple(reads),tuple(actions),tuple(preps),len(backlog),checked,tuple(errors))
