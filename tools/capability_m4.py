"""M4 selected-byte contract checks; no imports/execution of inspected programs."""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_m1 import _functions
from capability_fallback import _shape
from capability_c_graph import fingerprint
from capability_c_syntax import plain_definitions
from capability_source import python_literal_names,_tokens

@dataclass(frozen=True)
class M4Observation:
    read_tools:tuple
    action_tools:tuple
    backlog_count:int
    checked_functions:int
    blockers:tuple
    native_execution_verified:bool=False
    provider_authenticity_verified:bool=False
    client_e2e:str='NOT_RUN'
    external_service_calls:str='NOT_RUN'


def inspect_m4(sources,ledger,model,backlog):
    scan_sources(sources,());files={f.path:f for f in sources};trees={};errors=[];checked=0;reads=();actions=()
    for path,digest in model['pins']:
        f=files.get(path)
        if f is None or f.sha256!=digest:errors.append(('M4_SOURCE_MISSING_OR_DRIFT',path));continue
        if path.endswith('.py'):trees[path]=ast.parse(f.data)
    for path,name,shape in model['functions']:
        node=_functions(trees[path]).get(name) if path in trees else None
        if node is None or fingerprint(_shape(node))!=shape:errors.append(('M4_FUNCTION_CHANGED',(path,name)))
        else:checked+=1
    guards=(
     ('tools/integration_quality_actions.py','shape',"c.require(name in NAMES,'QUALITY_TOOL')"),
     ('tools/integration_quality_actions.py','shape',"c._validate(value,c.obj(rules[name]))"),
     ('tools/integration_quality_actions.py','shape',"c.require(not envelope['body'] and not envelope['context_json'] and not envelope['count_json'] and envelope['approval'] is None,'QUALITY_ENVELOPE_SCOPE')"),
     ('tools/integration_quality_actions.py','shape',"c.require(value['record'].get('work_id',entry['work_id'])==entry['work_id'],'QUALITY_RESEARCH_WORK_BINDING')"),
     ('tools/integration_quality_actions.py','shape',"c.require(set(inbox)=={'snapshots'} and isinstance(inbox['snapshots'],list) and len(inbox['snapshots'])==1,'QUALITY_INBOX_SCOPE')"),
     ('tools/integration_quality_reads.py','read',"c.require(c.encoded(before)==c.encoded(after),'OBSERVATION_STALE')"),
     ('tools/integration_quality_reads.py','command',"c.require(op!='stored_result','STORED_RESULT_HAS_NO_NATIVE_COMMAND')"),
     ('tools/integration_quality_reads.py','read',"service._authorize(scope,args['work_id'],'record')"),
     ('tools/integration_quality_reads.py','read',"c.require(getattr(service,'execution_result',None) is not None,'OWNER_EXECUTION_RESULT_REQUIRED')"),
     ('tools/integration_mutations.py','Service.execution_result',"self._admit('execution_request', args, existing_only=True)"),
     ('tools/integration_mutations.py','Service.execution_result',"c.require((output / 'result.json').exists(), 'ORIGINAL_RESULT_NOT_RECORDED')"),
     ('tools/integration_mutations.py','Service.execution_result',"self._result(output)"),
     ('tools/integration_mutations.py','Service._admit',"c.require(not existing_only, 'ORIGINAL_RESULT_NOT_FOUND')"),
     ('tools/integration_helper_contract.py','Helpers.__init__',"c.require(approve_helpers is True,'OWNER_HELPER_EFFECTS_APPROVAL_REQUIRED')"),
     ('tools/integration_helper_contract.py','Helpers.current',"c.require(c.sha(data)==self.digest,'HELPER_POLICY_CHANGED')"),
     ('tools/integration_helper_contract.py','Helpers.current',"c.require(value['mutation_policy_sha256']==self.policy.digest,'HELPER_MUTATION_POLICY_BINDING')"),
     ('tools/integration_helper_contract.py','Helpers.select',"c.require(row is not None and (row['project_id'],row['work_id'],row['action_sha256'])==(entry['project_id'],entry['work_id'],entry['action']['sha256']),'HELPER_ACTION_SCOPE')"),
     ('tools/integration_helper_contract.py','Helpers.select',"c.require(required<=set(row['effects']),'HELPER_EFFECTS_NOT_APPROVED')"),
     ('tools/integration_helper_contract.py','Helpers.select',"c.require(not row['environment'] or 'CREDENTIALS' in row['effects'],'HELPER_CREDENTIALS_NOT_APPROVED')"),
     ('tools/integration_helper_contract.py','Helpers.select',"c.require(c.sha(r.regular(Path(pin['path']),private=True))==pin['sha256'],'HELPER_INPUT_CHANGED')"),
     ('tools/integration_helper_contract.py','Helpers.environment',"c.require(c.sha(raw)==pin['sha256'],'HELPER_CREDENTIAL_CHANGED')"),
     ('tools/integration_helper_contract.py','Helpers.select',"backend._quota(self.policy.registry.root,0)"),
     ('tools/integration_helper_contract.py','Helpers.capture',"records.capture(argv,output,row['timeout_seconds'],cwd=Path(row['cwd']),observe_source=False,env=environment,limit=c.MAX_NATIVE)"),
     ('tools/integration_mutations.py','Service.__init__',"c.require(helpers is None or helpers.policy.digest == policy.digest, 'HELPER_MUTATION_POLICY_BINDING')"),
     ('tools/integration_mutations.py','Service._admit',"self.helpers.select(entry, value)"),
     ('tools/integration_mutations.py','Service._mutate',"self.helpers.capture(entry, value, output)"),
     ('tools/integration_mutations.py','Service._mutate',"self.helpers.select(entry, value)"),
     ('tools/integration_mutation_mcp.py','main',"c.require(bool(args.helper_policy) == bool(args.reviewed_helper_policy_sha256) == bool(args.approve_helper_effects), 'HELPER_OWNER_ARGUMENTS')"),
    )
    for path,name,expression in guards:
        node=_functions(trees[path]).get(name) if path in trees else None;wanted=_shape(ast.parse(expression,mode='eval').body)
        if node is None or sum(_shape(n)==wanted for n in ast.walk(node) if isinstance(n,ast.Call))!=1:errors.append(('M4_MANDATORY_GUARD_CHANGED',(path,name,expression)))
    try:
        # A historical lookup must have no executable/write fallback, even when
        # source/function fingerprints are deliberately repinned by a fixture.
        historical=_functions(trees['tools/integration_mutations.py'])['Service.execution_result']
        permitted={'c._validate','self._admit','c.require','exists','self._result',
                   'r.regular','c.decode','c.sha','base64.b64encode','decode','len'}
        for call in (n for n in ast.walk(historical) if isinstance(n,ast.Call)):
            name=ast.unparse(call.func)
            if name not in permitted and not (isinstance(call.func,ast.Attribute) and call.func.attr in ('exists','decode')):
                raise ValueError('M4_STORED_RESULT_EFFECT_PATH')
        admit=_functions(trees['tools/integration_mutations.py'])['Service._admit']
        stop=next(n.lineno for n in ast.walk(admit) if isinstance(n,ast.Call) and
            _shape(n)==_shape(ast.parse("c.require(not existing_only, 'ORIGINAL_RESULT_NOT_FOUND')",mode='eval').body))
        writes=[n.lineno for n in ast.walk(admit) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('mkdir','save')]
        if not writes or min(writes)<=stop:raise ValueError('M4_STORED_RESULT_WRITE_FALLBACK')
        actions=python_literal_names(files['tools/integration_quality_actions.py'].data.decode(),'NAMES',mapping=False)
        reads=python_literal_names(files['tools/integration_quality_reads.py'].data.decode(),'NAMES',mapping=False)
        if len(actions)!=7 or len(reads)!=4 or set(actions)&set(reads):raise ValueError('M4_TOOL_DOMAIN')
        declared=python_literal_names(files['tools/integration_mutation_contract.py'].data.decode(),'NAMES',mapping=False)
        schema=python_literal_names(files['tools/integration_quality_reads.py'].data.decode(),'SCHEMAS',mapping=True)
        transfer=python_literal_names(files['tools/integration_transfer.py'].data.decode(),'NAMES',mapping=False)
        if not set(actions)<=set(declared) or set(reads)!=set(schema) or not set(reads)<=set(transfer):raise ValueError('M4_DECLARATION_BINDING')
        service=trees['tools/integration_service.py'];mapping=next(n.value for n in service.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCHEMAS' for t in n.targets))
        for name in reads:
            values=[v for k,v in zip(mapping.keys,mapping.values) if isinstance(k,ast.Constant) and k.value==name]
            if len(values)!=1 or _shape(values[0])!=_shape(ast.parse('quality_reads.SCHEMAS['+repr(name)+']',mode='eval').body):raise ValueError('M4_SCHEMA_ALIAS')
        node=_functions(service)['Service._call_locked'];branch=[]
        for n in ast.walk(node):
            if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and _shape(n.test.left)==_shape(ast.Name(id='name',ctx=ast.Load())) and len(n.test.comparators)==1 and isinstance(n.test.comparators[0],ast.Tuple) and {v.value for v in n.test.comparators[0].elts if isinstance(v,ast.Constant)}==set(reads):branch.append(n)
        if len(branch)!=1 or _shape(branch[0].body[0])!=_shape(ast.parse('result = quality_reads.read(self, scope, name, args)').body[0]):raise ValueError('M4_READ_HANDLER')
        remote=python_literal_names(files['tools/integration_gateway_contract.py'].data.decode(),'REMOTE_READ_NAMES',mapping=False)
        if set((*reads,*actions))&set(remote):raise ValueError('M4_REMOTE_EXPANSION')
        # Separate exact helper authority must be checked before intent and after capture.
        admit=_functions(trees['tools/integration_mutations.py'])['Service._admit']
        expected=ast.parse('if name == "helper_execute" and previous.get("tool") == name and previous.get("action") == entry and (directory / "dispatch-intent.json").exists():\n    raise c.IntegrationError("HELPER_ACTION_ALREADY_DISPATCHED_REVIEW_ORIGINAL")').body[0]
        if sum(_shape(n)==_shape(expected) for n in ast.walk(admit))!=1:raise ValueError('M4_HELPER_REDISPATCH_GUARD')
        for path,function in (('tools/integration_quality_actions.py','draft'),('tools/integration_quality_actions.py','shape')):
            for n in ast.walk(_functions(trees[path])[function]):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('capture','_mutate','execute','apply','native_action','authorize'):raise ValueError('M4_PREPARATION_DISPATCH')
        # C bridges remain read-only or disposable. The original reducers are unchanged.
        definition=next(d for d in plain_definitions(files['src/cli/execution.c'].data.decode()) if d[0]=='golem_cli_execution')
        body=definition[3]
        from capability_profile import _close
        start=next(i for i in range(len(body)-1) if body[i:i+2]==('if','('));end=_close(body,start+1);finish=_close(body,end+1);first=body[end+2:finish]
        if any(n not in first for n in ('golem_execution_call','golem_execution_call_authorized','golem_document_store_open')):raise ValueError('M4_VERIFY_CORE_EDGE')
        wanted=_tokens('golem_document_store_open(argv[3], false, NULL, &store, NULL)')
        if not any(first[i:i+len(wanted)]==wanted for i in range(len(first)-len(wanted)+1)):raise ValueError('M4_VERIFY_WRITABLE')
        for function in ('golem_work_run_cost_inbox_enable','golem_work_run_cost_inbox_sync','golem_work_run_cost_inbox_status','golem_cost_ledger_report_get','golem_cost_ledger_stage_totals_get'):
            body=next(d[3] for d in plain_definitions(files['src/cli/work.c'].data.decode()) if d[0]=='golem_cli_work')
            if body.count(function)!=1:raise ValueError('M4_ACCOUNTING_CORE_EDGE')
        if 'golem_work_run_finish' in body or 'golem_document_store_open' in body:raise ValueError('M4_ACCOUNTING_LIVE_OR_PASS')
        text=files['tools/integration_approval_host.c'].data
        if b'golem_execution_call_receipted' not in text:raise ValueError('M4_ORIGINAL_QA_HOST_EDGE')
        body=next(d[3] for d in plain_definitions(files['src/cli/research.c'].data.decode()) if d[0]=='golem_cli_research')
        if body.count('golem_research_redaction_validate')!=1:raise ValueError('M4_REDACTION_CORE_EDGE')
    except (KeyError,ValueError,StopIteration,AttributeError,SyntaxError) as e:errors.append(('M4_CONNECTION_UNVERIFIED',str(e)))
    if fingerprint(backlog)!=model['backlog_sha256']:errors.append(('M4_FROZEN_BACKLOG_CHANGED',None))
    caps={c['id']:c for c in ledger['capabilities']};seen=set()
    allowed=set((*reads,*actions,'execution_request','approval_read','bundle_read','evidence_read','usage_read'))
    for row in backlog:
        cid=row['capability_id'];cap=caps.get(cid)
        if cid in seen or cap is None or cap['review_status']!='REVIEWED' or cap['implementation']!='IMPLEMENTED' or tuple(cap['target_routes'])!=row['target_routes'] or not set(row['target_routes'])<=set(cap['current_routes']):errors.append(('M4_BACKLOG_NOT_CONNECTED',cid))
        seen.add(cid)
        if not row['tools'] or not set(row['tools'])<=allowed or not row['scope']:errors.append(('M4_BACKLOG_ROUTE_UNREVIEWED',cid))
        if row['client_e2e']!='NOT_RUN' or row['native_execution_verified'] or row['provider_authenticity_verified']:errors.append(('M4_AUTHORITY_PROMOTION',cid))
    if len(backlog)!=83 or len(seen)!=83:errors.append(('M4_BACKLOG_DOMAIN_CHANGED',None))
    return M4Observation(tuple(reads),tuple(actions),len(backlog),checked,tuple(errors))
