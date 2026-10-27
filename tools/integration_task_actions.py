"""M3 closed task actions. Exact owner-pinned bytes, never arbitrary commands.

Shape and draft construction do not approve or dispatch. Native parsers/reducers
retain their own limits, counters, locks, policy and protection predicates.
"""
import base64
import binascii
import copy
from pathlib import Path
import integration_contract as c
import integration_registry as r
import execution_record as records

NAMES=('session_start','session_heartbeat','session_reject_output','binding_attach',
 'role_enroll','role_assess','completion_finalize','completion_report','reentry_decide',
 'reentry_report','document_project','work_create','context_publish','discovery_snapshot',
 'profile_register','run_link','work_noop_run','adapter_noop_run','lineage_store','approval_request')
TEXT={'type':'string','maxLength':c.LIMIT}
OBJECT={'type':['object','null']}
REV={'type':'integer','minimum':1,'maximum':4096}
GEN={'type':'integer','minimum':1,'maximum':4097}
SEQ={'type':'integer','minimum':0,'maximum':4096}
TTL={'type':'integer','minimum':1,'maximum':3600000}
REPORT={'sequence':{'type':'integer','minimum':1,'maximum':64}}
TOKEN=c.obj({'epoch':REV,'attempt_id':c.ID,'session_id':c.ID})
REF=c.obj({'document_id':c.ID,'revision':REV,'digest':c.DIGEST})
VALIDATORS={'session_start':'session','session_heartbeat':'session','session_reject_output':'session',
 'binding_attach':'binding_request','role_enroll':'role_request','role_assess':'role_request',
 'completion_finalize':'completion','reentry_decide':'reentry','approval_request':'approval_request'}


def binary(text):
    try:value=base64.b64decode(text,validate=True)
    except (ValueError,binascii.Error):raise c.IntegrationError('TASK_BINARY_ENCODING') from None
    c.require(bool(value) and len(value)<=c.LIMIT,'TASK_BINARY_SIZE');return value


def shape(entry,envelope):
    name=entry['tool'];c.require(name in NAMES,'TASK_TOOL')
    value=c.decode(envelope['native_json'].encode());c.require(isinstance(value,dict),'NATIVE_ACTION')
    common={'schema_version':{'const':1},'key':c.ID}
    work={**common,'work_id':{'const':entry['work_id']},'expected_sequence':SEQ}
    session={**work,'operation':{'const':name.removeprefix('session_')}}
    rules={
      'session_start':{**session,'selection_id':c.ID},
      'session_heartbeat':{**session,'token':TOKEN,'ttl_ms':TTL},
      'session_reject_output':{**session,'token':TOKEN,'input_digest':c.DIGEST,'source_snapshot':c.DIGEST,'expected_generation':GEN,'output':REF,'evidence':c.array(c.DIGEST,64),'approval_digest':c.DIGEST},
      'binding_attach':{**work,'operation':{'const':'attach'},'session_id':{'const':entry['session_id']},'descriptor_digest':c.DIGEST,'native_thread_id':TEXT,'token':OBJECT,'ttl_ms':TTL},
      'role_enroll':{**common,'operation':{'const':'enroll'},'selection_id':c.ID,'expected_generation':GEN,'contract':OBJECT},
      'role_assess':{**common,'operation':{'const':'assess'},'selection_id':c.ID,'expected_generation':GEN,'review':OBJECT},
      'completion_finalize':{**common,'schema_version':{'type':'integer','minimum':1,'maximum':2},'operation':{'const':'finalize'},'selection_id':c.ID,'expected_generation':GEN,'issues':c.array(OBJECT,32,0)},
      'completion_report':REPORT,'reentry_report':REPORT,
      'document_project':{'document_id':c.ID,'revision':REV},
      'work_create':{'relative_directory':c.ID,'specification_json':TEXT},
      'context_publish':{'request_json':TEXT,'token_count_json':TEXT},
      'discovery_snapshot':{'plan_json':TEXT},
      'profile_register':{'profile_json':TEXT,'key':c.ID},
      'run_link':{'binding':c.DIGEST,'journal_base64':TEXT,'run_id':c.ID,'records':c.INTEGER,'bytes':c.INTEGER,'chain_head':c.DIGEST},
      'work_noop_run':{'capsule_json':TEXT},
      'adapter_noop_run':{'request_json':TEXT},
      'lineage_store':{'graph_base64':TEXT},
      'approval_request':{**common,'operation':{'const':'request'},'action':OBJECT,'ttl_ms':TTL},
    }
    if name=='reentry_decide':
        fields={**common,'operation':{'const':'decide'},'expected_sequence':{'type':'integer','minimum':0,'maximum':63},'failure_receipt':c.DIGEST,'classification':c.enum('REQUIREMENTS','UX','PUBLISHING','IMPLEMENTATION','TEST_DEFECT','ENVIRONMENT','PERMISSION','BUDGET','LEASE','UNKNOWN','EXTERNAL_EFFECT_UNKNOWN'),'hypothesis':TEXT,'confidence':c.enum('LOW','MEDIUM','HIGH'),'verification':TEXT,'affected_requirements':c.array(c.ID,64),'evidence_refs':c.array(c.DIGEST,8),'policy':OBJECT}
        if 'previous_decision' in value:fields['previous_decision']=c.DIGEST
    else:fields=rules[name]
    c._validate(value,c.obj(fields))
    c.require(not envelope['body'] and not envelope['context_json'] and envelope['approval'] is None,'TASK_ENVELOPE_SCOPE')
    if name=='role_enroll':c._validate(c.decode(envelope['count_json'].encode()),c.obj({'contract_digest':c.DIGEST}))
    else:c.require(not envelope['count_json'],'TASK_ENVELOPE_SCOPE')
    for field in ('token',):
        if field in value and value[field] is not None:
            c._validate(value[field],TOKEN);c.require(value[field]['session_id']==entry['session_id'],'NATIVE_OWNER_MAPPING')
    if name=='approval_request':
        c.require(isinstance(value['action'],dict) and value['action'].get('work_id')==entry['work_id'] and value['action'].get('operation') in ('prepare','finish','run'),'TASK_APPROVAL_SCOPE')
    for field in ('specification_json','request_json','profile_json','capsule_json','plan_json'):
        if field in value:c.require(isinstance(c.decode(value[field].encode()),dict),'TASK_JSON_OBJECT')
    if name=='context_publish' and value['token_count_json']:c.require(isinstance(c.decode(value['token_count_json'].encode()),dict),'TOKEN_PROOF_OBJECT')
    if name=='run_link':c.require(len(binary(value['journal_base64']))==value['bytes'],'TASK_JOURNAL_SIZE')
    if name=='lineage_store':binary(value['graph_base64'])
    return value


def draft(args,observed,key):
    value=c.decode(args['fields_json'].encode());c.require(isinstance(value,dict),'PREPARATION_FIELDS_OBJECT')
    c.require(not set(value)&{'key','expected_sequence','expected_generation','work_id','token','input_digest'},'PREPARATION_RESERVED_FIELD')
    value=copy.deepcopy(value);name=args['tool'];sources={};missing=[]
    def derive(field,data,origin):value[field]=data;sources[field]=origin
    def need(field):
        if field not in value:missing.append(field)
    if name.startswith('session_') or name=='binding_attach':
        c.require(not set(value)&{'schema_version','operation'},'PREPARATION_RESERVED_FIELD')
        derive('schema_version',1,'CORE_VERSION');derive('operation',name.removeprefix('session_') if name.startswith('session_') else 'attach','CLOSED_TOOL')
        derive('work_id',args['work_id'],'SCOPED_WORK');derive('key',key,'NEW_PREPARATION_ID');derive('expected_sequence',observed['status']['sequence'],'NATIVE_SESSION_SEQUENCE')
        active=(observed['status'].get('state') or {}).get('active')
        if name=='session_start':need('selection_id')
        elif name=='binding_attach':
            derive('session_id',args['session_id'],'CALLER_LABEL');derive('token',{k:active[k] for k in ('epoch','attempt_id','session_id')} if active else None,'NATIVE_ACTIVE_TOKEN')
            for f in ('descriptor_digest','native_thread_id','ttl_ms'):need(f)
        else:
            c.require(active and active['session_id']==args['session_id'],'PREPARATION_OWNER_MISMATCH')
            derive('token',{k:active[k] for k in ('epoch','attempt_id','session_id')},'NATIVE_ACTIVE_TOKEN')
            if name=='session_heartbeat':need('ttl_ms')
            else:
                derive('input_digest',active['manifest_digest'],'NATIVE_ACTIVE_MANIFEST');derive('source_snapshot',active['source_snapshot'],'NATIVE_ACTIVE_SOURCE')
                derive('expected_generation',observed['next']['document_generation'],'NATIVE_DOCUMENT_GENERATION')
                for f in ('output','evidence','approval_digest'):need(f)
    elif name in ('role_enroll','role_assess','completion_finalize','approval_request','reentry_decide'):
        c.require(not set(value)&{'schema_version','operation'},'PREPARATION_RESERVED_FIELD')
        derive('schema_version',value.pop('completion_schema_version',1) if name=='completion_finalize' else 1,'EXPLICIT_COMPLETION_PREDICATE_VERSION' if name=='completion_finalize' else 'CORE_VERSION');derive('operation',{'role_enroll':'enroll','role_assess':'assess','completion_finalize':'finalize','approval_request':'request','reentry_decide':'decide'}[name],'CLOSED_TOOL');derive('key',key,'NEW_PREPARATION_ID')
        if name in ('role_enroll','role_assess','completion_finalize'):
            derive('expected_generation',observed['next']['document_generation'],'NATIVE_DOCUMENT_GENERATION');need('selection_id');need({'role_enroll':'contract','role_assess':'review','completion_finalize':'issues'}[name])
        elif name=='approval_request':need('action');need('ttl_ms')
        else:
            # Reentry sequence is its own domain: caller supplies explicit read observation.
            c.require('reentry_sequence' in value,'PREPARATION_REENTRY_SEQUENCE_REQUIRED')
            derive('expected_sequence',value.pop('reentry_sequence'),'EXPLICIT_REENTRY_DOMAIN_OBSERVATION')
            for f in ('failure_receipt','classification','hypothesis','confidence','verification','affected_requirements','evidence_refs','policy'):need(f)
    else:
        required={'completion_report':('sequence',),'reentry_report':('sequence',),'document_project':('document_id','revision'),'work_create':('relative_directory','specification_json'),'context_publish':('request_json','token_count_json'),'discovery_snapshot':('plan_json',),'profile_register':('profile_json',),'run_link':('binding','journal_base64','run_id','records','bytes','chain_head'),'work_noop_run':('capsule_json',),'adapter_noop_run':('request_json',),'lineage_store':('graph_base64',)}[name]
        if name=='profile_register':derive('key',key,'NEW_PREPARATION_ID')
        for f in required:need(f)
    envelope={'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),'body':args['body'],'context_json':args['context_json'],'count_json':args['count_json'],'approval':None}
    entry={k:args[k] for k in ('tool','work_id','session_id','native_binding_id')}
    if name=='role_enroll' and not args['count_json']:missing.append('count_json.contract_digest')
    if not missing:shape(entry,envelope)
    return envelope,value,entry,sorted(set(missing)),sources


def validator(tool,envelope,request):
    if tool in VALIDATORS:return {'kind':VALIDATORS[tool],'request_json':envelope['native_json']}
    fields={'work_create':('work_specification','specification_json'),'profile_register':('profile','profile_json'),'work_noop_run':('capsule','capsule_json')}
    if tool in fields:
        kind,field=fields[tool];return {'kind':kind,'request_json':request[field]}
    return None


def validate_observed(entry,request,observed):
    name=entry['tool'];record=observed['record'];state=observed['status'].get('state') or {};active=state.get('active')
    if name.startswith('session_') or name=='binding_attach':c.require(request['expected_sequence']==observed['status']['sequence'],'PREPARATION_STALE')
    if 'token' in request:
        token={k:active[k] for k in ('epoch','attempt_id','session_id')} if active else None
        c.require(request['token']==token,'PREPARATION_TOKEN_CHANGED')
    if 'expected_generation' in request:c.require(request['expected_generation']==observed['next']['document_generation'],'PREPARATION_STALE')
    if name=='session_reject_output':
        c.require(active and request['input_digest']==active['manifest_digest'] and request['source_snapshot']==active['source_snapshot'],'PREPARATION_INPUT_CHANGED')
    for field in ('selection_id','output'):
        if field in request:
            ref=request[field];ident=ref['document_id'] if isinstance(ref,dict) else ref
            rows=[row for row in record['documents'] if row['document_id']==ident]
            c.require(bool(rows),'PREPARATION_REFERENCE_BINDING')
            row=max(rows,key=lambda v:v['revision'])
            if isinstance(ref,dict):c.require({k:row[k] for k in ('document_id','revision','digest')}==ref,'PREPARATION_REFERENCE_BINDING')
    if name=='document_project':
        c.require(any(row['document_id']==request['document_id'] and row['revision']==request['revision'] for row in record['documents']),'PREPARATION_REFERENCE_BINDING')


def authorize(entry,request,project,*,require_new=False):
    """Extra owner-scoped filesystem authority, checked again at argv creation."""
    name=entry['tool']
    if name=='work_create':
        spec=c.decode(request['specification_json'].encode());c._validate(spec.get('work_id'),c.ID)
        c.require(spec['work_id'] not in {w['work_id'] for w in project['works']},'TASK_WORK_ALREADY_REGISTERED')
        target=Path(project['root'])/request['relative_directory']
        if require_new:c.require(not target.exists() and not target.is_symlink(),'TASK_DESTINATION_EXISTS')
        c.require(r.real_path(project['root'])==Path(project['root']),'TASK_DESTINATION_PARENT')
    if name=='discovery_snapshot':
        plan=c.decode(request['plan_json'].encode())
        c.require(isinstance(plan.get('repositories'),list),'TASK_DISCOVERY_SCOPE')
        for repo in plan['repositories']:
            c.require(isinstance(repo,dict) and repo.get('root')==project['root'],'TASK_DISCOVERY_SCOPE')
            c.require(isinstance(repo.get('paths'),list) and all(isinstance(p,str) and not Path(p).is_absolute() and '..' not in Path(p).parts and '.git' not in Path(p).parts and r.real_path(str(Path(project['root'])/p)).is_relative_to(Path(project['root'])) for p in repo['paths']),'TASK_DISCOVERY_SCOPE')


def command(entry,project,work,value,output):
    request=shape(entry,value);authorize(entry,request,project,require_new=True);name=entry['tool'];path=str(output/'request.json');root=work['path']
    def save(filename,text):
        records.save(output/filename,text.encode());return str(output/filename)
    if name in ('session_start','session_heartbeat','session_reject_output'):return ['session','call',root,path]
    if name=='binding_attach':return ['agent','binding','attach',root,path]
    if name in ('role_enroll','role_assess'):
        suffix=['--approve-contract',c.decode(value['count_json'].encode())['contract_digest']] if name=='role_enroll' else []
        # Exact owner-reviewed digest; never reproduce json-c hashing in Python.
        return ['role','call',root,path,*suffix]
    if name=='completion_finalize':return ['completion','call',root,path]
    if name=='reentry_decide':return ['reentry','call',root,path]
    if name in ('completion_report','reentry_report'):return [name.split('_')[0],'report',root,str(request['sequence'])]
    if name=='document_project':return ['document','project',root,request['document_id'],str(request['revision'])]
    if name=='work_create':return ['work','start',str(Path(project['root'])/request['relative_directory']),save('work-specification.json',request['specification_json'])]
    if name=='context_publish':
        suffix=['--token-count',save('token-count.json',request['token_count_json'])] if request['token_count_json'] else []
        return ['context','publish',root,save('context-request.json',request['request_json']),*suffix]
    if name=='discovery_snapshot':return ['discovery','snapshot',save('discovery-plan.json',request['plan_json'])]
    if name=='profile_register':return ['profile','register',root,save('profile.json',request['profile_json']),request['key']]
    if name=='run_link':
        records.save(output/'journal.bin',binary(request['journal_base64']))
        return ['profile','link',root,request['binding'],str(output/'journal.bin'),request['run_id'],str(request['records']),str(request['bytes']),request['chain_head']]
    if name=='work_noop_run':return ['run','--noop',save('capsule.json',request['capsule_json']),'--output',str(output/'simulation')]
    if name=='adapter_noop_run':return ['adapter','noop','run-file',root,save('adapter-request.json',request['request_json'])]
    if name=='lineage_store':
        records.save(output/'graph.bin',binary(request['graph_base64']));return ['lineage','store',root,str(output/'graph.bin')]
    if name=='approval_request':return ['approval','call',root,path]
    raise c.IntegrationError('TASK_TOOL')
