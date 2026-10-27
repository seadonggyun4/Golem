"""M2 non-authoritative input/plan preparation in the existing D2 audit scope.

No mutation, registration, owner approval, recovery, arbitrary argv/path, provider
or network call. Plans are immutable, instance-bound and require fresh native
basis at review. Owner-approved D4 bytes remain the only action authority.
"""
import base64
import copy
from pathlib import Path
import tempfile
import time
import uuid
import integration_contract as c
import integration_backend as backend
import integration_registry as r
import execution_record as records
import integration_reads as native_reads
import integration_mutation_contract as actions
import integration_prepare_builders as builders

NAMES=('inputs_prepare','action_prepare','contract_prepare','approved_action_prepare','plan_read','action_confirm')
OWNER_NAMES=('approved_action_prepare','action_confirm')
WORK={'project_id':c.ID,'work_id':c.ID}
CREATE={**WORK,'preparation_request_id':c.ID}
TEXT={'type':'string','maxLength':c.LIMIT}
JSON={'type':'string','minLength':2,'maxLength':c.LIMIT}
PLAN_ID={'type':'string','pattern':'^[a-f0-9]{32}$','maxLength':32}
PLAN_ARGS={**WORK,'plan_id':PLAN_ID,'plan_sha256':c.DIGEST}
SCHEMAS={
 'inputs_prepare':c.obj({**CREATE,'selection_id':c.ID,'target_kind':c.ID,'source_snapshot':c.DIGEST,'byte_budget':{'type':'integer','minimum':1,'maximum':131072}}),
 'action_prepare':c.obj({**CREATE,'tool':c.enum(*actions.NAMES),'session_id':c.ID,'native_binding_id':actions.LABEL,'fields_json':JSON,'body':TEXT,'context_json':TEXT,'count_json':TEXT}),
 'contract_prepare':c.obj({**CREATE,'kind':c.enum('session','document','execution','completion','reentry','role','template','discovery','profile','capsule','binding_request','role_request','approval_request','work_specification','research','redaction'),'request_json':JSON,'body_text':TEXT}),
 'approved_action_prepare':c.obj({**CREATE,'action_id':c.ID}),
 'plan_read':c.obj(PLAN_ARGS),
 'action_confirm':c.obj({**PLAN_ARGS,'action_id':c.ID}),
}
MAX_PLAN_BYTES=1048576
MAX_PLANS=64
MAX_AGE_NS=1800*1000000000


def initialize(service):
    service.preparation_instance=uuid.uuid4().hex
    service.preparation_plans={}
    service.preparation_requests={}


def observe(service,scope,work_id):
    for operation in ('record','status','next'):project=service._authorize(scope,work_id,operation)
    backend._quota(service.registry.root,4)
    before=service._read(scope,work_id,'record')['result']
    status=service._read(scope,work_id,'status')['result'];following=service._read(scope,work_id,'next')['result']
    after=service._read(scope,work_id,'record')['result']
    c.require(c.encoded(before)==c.encoded(after),'OBSERVATION_STALE')
    c.require(isinstance(before,dict) and isinstance(before.get('documents'),list) and all(isinstance(row,dict) for row in before['documents']),'PREPARATION_NATIVE_RECORD')
    c._validate(status.get('sequence'),c.INTEGER);c._validate(following.get('sequence'),c.INTEGER)
    c.require(status['sequence']==following['sequence'] and before.get('status',{}).get('sequence')==status['sequence'],'OBSERVATION_STALE')
    c._validate(following.get('document_generation'),{'type':'integer','minimum':1,'maximum':4097})
    c.require(before.get('work_id')==work_id and before.get('work_specification',{}).get('work_id')==work_id,'WORK_IDENTITY')
    basis={'binding':scope['binding'],'work_id':work_id,'transfer_sha256':service.transfer.digest,
           'project_sha256':c.sha(c.encoded(project)),'producer_sha256':c.sha(c.encoded(service.transfer.current()['producer'])),
           'record_sha256':c.sha(c.encoded(before)),'status_sha256':c.sha(c.encoded(status)),'next_sha256':c.sha(c.encoded(following)),
           'sequence':status['sequence'],'document_generation':following['document_generation']}
    if getattr(service,'parallel_hosts',None) is not None:basis['parallel_host']=service.parallel_hosts.basis(scope['binding']['project_id'],work_id)
    return project,{'record':before,'status':status,'next':following},basis


def native(service,scope,work_id,project,record,name,args):
    """Only M1 fixed read/validation argv; never a session call or native action."""
    c.require(name in ('workflow_read','native_validate'),'PREPARATION_READ_ROUTE')
    args={'project_id':scope['binding']['project_id'],'work_id':work_id,**args}
    args.pop('preparation_request_id',None)
    if name=='native_validate' and args['kind']!='document':
        c.require(not args.pop('body_text',''),'PREPARATION_BODY_SCOPE')
    c._validate(args,native_reads.SCHEMAS[name])
    capacity=backend._quota(service.registry.root,1)
    c.require(capacity['remaining']['bytes']>=2*c.MAX_NATIVE+c.LIMIT and capacity['remaining']['entries']>=16,'AUDIT_QUOTA')
    output=Path(tempfile.mkdtemp(prefix='read-m2-validation-',dir=service.registry.root))
    records.save(output/'request.json',c.encoded(args))
    try:
        work=next(w for w in project['works'] if w['work_id']==work_id)
        argv=native_reads.command(name,args,work['path'],output,record)
        process=records.capture([project['cli']['path'],'--output-mode','full',*argv],output,backend.TIMEOUT_SECONDS,
            cwd=output,observe_source=False,env=backend.ENVIRONMENT,limit=c.MAX_NATIVE)
        c.require(type(process.get('returncode')) is int and process['returncode']==0 and process.get('reason')=='EXIT' and process.get('recording')=='RECORDED','NATIVE_FAILURE')
        raw=r.regular(output/'stdout.log',c.MAX_NATIVE,private=True);result=native_reads.decode_result(name,args,raw)
        r.check_project(project);backend._quota(service.registry.root,0)
        return {'result':result,'native_stdout':{'encoding':'base64','data':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':c.sha(raw)},
                'validation_scope':'NATIVE_STRUCTURAL_ONLY' if name=='native_validate' else 'NATIVE_REQUIRED_INPUTS_NOT_EXECUTION_AUTHORITY'}
    except (c.IntegrationError,OSError,ValueError) as error:
        records.save(output/'failure.json',c.encoded({'code':getattr(error,'code','IO_OR_CONTRACT_ERROR'),'automatic_retry_allowed':False}))
        error.evidence_path=str(output);raise


def owner_available(service,project_id,work_id):
    policy=service.preparation_policy
    if policy is None:return False
    try:
        c.require(policy.transfer.digest==service.transfer.digest,'PREPARATION_POLICY_BINDING')
        for entry in policy.current()['actions']:
            if (entry['project_id'],entry['work_id'])==(project_id,work_id):
                policy.authorize(entry)
                if entry['tool']=='helper_execute':
                    if getattr(service,'preparation_helpers',None) is None:continue
                    service.preparation_helpers.select(entry,policy.action(entry)[0])
                if entry['tool'] in ('candidate_request','workspace_request'):
                    if getattr(service,'parallel_hosts',None) is None:continue
                    service.parallel_hosts.select(entry,policy.action(entry)[0])
                return True
    except (c.IntegrationError,OSError,ValueError):pass
    return False


def admit_plan(service):
    c.require(len(service.preparation_plans)<MAX_PLANS and sum(p.name.startswith('read-m2-plan-') for p in service.registry.root.iterdir())<MAX_PLANS,'PREPARATION_QUOTA')


def owner_action(service,args):
    c.require(service.preparation_policy is not None,'PREPARATION_OWNER_POLICY_REQUIRED')
    policy=service.preparation_policy
    c.require(policy.transfer.digest==service.transfer.digest,'PREPARATION_POLICY_BINDING')
    entry=next((v for v in policy.current()['actions'] if v['action_id']==args['action_id']),None)
    c.require(entry is not None and (entry['project_id'],entry['work_id'])==(args['project_id'],args['work_id']),'MUTATION_SCOPE')
    policy.authorize(entry);value,request=policy.action(entry)
    if entry["tool"]=="helper_execute":
        c.require(getattr(service,"preparation_helpers",None) is not None,"OWNER_HELPER_EFFECTS_APPROVAL_REQUIRED")
        service.preparation_helpers.select(entry,value)
    if entry['tool'] in ('candidate_request','workspace_request'):
        c.require(getattr(service,'parallel_hosts',None) is not None,'OWNER_PARALLEL_HOST_REQUIRED')
        service.parallel_hosts.select(entry,value)
    return entry,value,request


def public_plan(plan):
    value=copy.deepcopy(plan)
    payload=value['payload']
    if payload['kind']=='OWNER_ACTION':
        payload['entry']={k:v for k,v in payload['entry'].items() if k!='action'}
        if payload['action']['approval'] is not None:
            payload['action']['approval']={'attachment_sha256':c.sha(c.encoded(payload['action']['approval'])),'owner_paths':'NOT_DISCLOSED'}
        payload['owner_pin_paths']='LOCAL_ONLY'
    return value


def seal(service,scope,args,observed,basis,payload):
    capacity=backend._quota(service.registry.root,1)
    admit_plan(service)
    plan_id=uuid.uuid4().hex
    plan={'schema':'golem.integration-preparation.v1','plan_id':plan_id,'instance':service.preparation_instance,
          'created_monotonic_ns':time.monotonic_ns(),'binding':scope['binding'],'project_id':args['project_id'],'work_id':args['work_id'],
          'request_id':uuid.uuid4().hex,'preparation_request_id':args['preparation_request_id'],'basis':basis,'payload':payload,
          'basis_scope':'REGISTERED_WORK_BINDING_PRODUCER_AND_NATIVE_READ_OBSERVATIONS',
          'live_source_scan':'NOT_RUN','native_state_preconditions_checked':False,
          'native_guidance':{'next':observed['next'],'resume_preflight':observed['status'].get('resume_preflight')},
          'execution_authorized':False,'approval_created':False,'native_state_changed':False}
    raw=c.encoded(plan);c.require(len(raw)<=MAX_PLAN_BYTES,'PREPARATION_SIZE_LIMIT')
    response={'view':'preparation','plan_id':plan_id,'plan_sha256':c.sha(raw),'plan':public_plan(plan),
              'preparation_state':'REVIEW_REQUIRED','lifetime':'SERVICE_INSTANCE_30_MINUTES_AND_UNCHANGED_BASIS',
              'read_slots':{'basis':4,'revalidation':4,'validator':1},'content_role':'UNTRUSTED_DATA'}
    c.require(len(c.encoded(response))+2048<=service.transfer.value['max_result_bytes'],'RESULT_BUDGET_EXCEEDED')
    c.require(capacity['remaining']['bytes']>=len(raw)+len(c.encoded(args))+c.LIMIT and capacity['remaining']['entries']>=4,'AUDIT_QUOTA')
    output=service.registry.root/('read-m2-plan-'+plan_id);output.mkdir(mode=0o700)
    records.save(output/'request.json',c.encoded(args));records.save(output/'plan.json',raw)
    service.preparation_plans[plan_id]=c.sha(raw)
    service.preparation_requests[request_identity(scope,args)]=(c.sha(c.encoded(args)),plan_id,c.sha(raw))
    return response


def load(service,scope,args):
    c.require(service.preparation_plans.get(args['plan_id'])==args['plan_sha256'],'PREPARATION_INSTANCE_OR_REFERENCE')
    output=service.registry.root/('read-m2-plan-'+args['plan_id']);r.real_path(str(output));service.registry._private(output)
    raw=r.regular(output/'plan.json',MAX_PLAN_BYTES,private=True)
    c.require(c.sha(raw)==args['plan_sha256'],'PREPARATION_CHANGED')
    plan=c.decode(raw,MAX_PLAN_BYTES)
    c.require(plan['schema']=='golem.integration-preparation.v1' and plan['plan_id']==args['plan_id'] and plan['instance']==service.preparation_instance,'PREPARATION_INSTANCE_OR_REFERENCE')
    c.require(plan['binding']==scope['binding'] and (plan['project_id'],plan['work_id'])==(args['project_id'],args['work_id']),'PREPARATION_SCOPE')
    c.require(0<=time.monotonic_ns()-plan['created_monotonic_ns']<=MAX_AGE_NS,'PREPARATION_EXPIRED')
    return plan


def compare_basis(plan,current):
    c.require(plan['basis']==current,'PREPARATION_STALE')


def confirmed(service,scope,args,plan):
    payload=plan['payload'];c.require(payload['kind']=='OWNER_ACTION','PREPARATION_OWNER_REVIEW_REQUIRED')
    entry,value,request=owner_action(service,args)
    c.require(entry==payload['entry'] and entry['action']['sha256']==payload['action_sha256'] and value==payload['action'],'PREPARATION_ACTION_CHANGED')
    if entry['tool'].startswith('session_'):c.require(request['expected_sequence']==plan['basis']['sequence'],'PREPARATION_STALE')
    return {'view':'preparation_confirmation','plan_id':args['plan_id'],'plan_sha256':args['plan_sha256'],
            'review_state':'OWNER_ACTION_MATCHES_CURRENT_PREPARATION',
            'd4_invocation':{'tool':entry['tool'],'arguments':{'project_id':args['project_id'],'work_id':args['work_id'],'action_id':entry['action_id'],'request_id':plan['request_id']}},
            'd4_admission':'NOT_RUN','native_preconditions':'NOT_CERTIFIED','execution_authorized':False,
            'approval_channel':'UNCHANGED_OWNER_ACTION_POLICY','automatic_retry_allowed':False}


def request_identity(scope,args):
    return c.sha(c.encoded({'binding':scope['binding'],'work_id':args['work_id'],'preparation_request_id':args['preparation_request_id']}))


def review_plan(service,scope,args,confirm=False):
    plan=load(service,scope,args)
    _,observed,basis=observe(service,scope,args['work_id'])
    if plan['payload']['kind'] in ('PARALLEL_REVIEW','MERGE_REVIEW'):
        import integration_parallel_preparations as parallel_preparations
        basis=parallel_preparations.reobserve(service,scope,plan,basis)
    compare_basis(plan,basis)
    result=confirmed(service,scope,args,plan) if confirm else {'view':'preparation','plan_id':args['plan_id'],'plan_sha256':args['plan_sha256'],'plan':public_plan(plan),'preparation_state':'CURRENT_BASIS_REVIEW_REQUIRED','execution_authorized':False}
    if plan['payload']['kind']=='OWNER_ACTION':
        entry,value,_=owner_action(service,{**args,'action_id':plan['payload']['entry']['action_id']})
        c.require(entry==plan['payload']['entry'] and entry['action']['sha256']==plan['payload']['action_sha256'],'PREPARATION_ACTION_CHANGED')
    load(service,scope,args)
    return result


def read(service,scope,name,args):
    c.require(name in NAMES,'UNSUPPORTED_PREPARATION');c._validate(args,SCHEMAS[name])
    if name in OWNER_NAMES:c.require(service.preparation_policy is not None,'PREPARATION_OWNER_POLICY_REQUIRED')
    if name in ('plan_read','action_confirm'):
        backend._quota(service.registry.root,4)
        return review_plan(service,scope,args,confirm=name=='action_confirm')
    original=service.preparation_requests.get(request_identity(scope,args))
    if original is not None:
        digest,plan_id,plan_sha=original
        c.require(digest==c.sha(c.encoded(args)),'PREPARATION_REQUEST_CONFLICT')
        backend._quota(service.registry.root,4)
        return review_plan(service,scope,{'project_id':args['project_id'],'work_id':args['work_id'],'plan_id':plan_id,'plan_sha256':plan_sha})
    backend._quota(service.registry.root,10)
    admit_plan(service)
    project,observed,basis=observe(service,scope,args['work_id'])
    blockers=[];questions=[]
    if name=='inputs_prepare':
        value=native(service,scope,args['work_id'],project,observed['record'],'workflow_read',{**args,'operation':'inputs'})
        payload={'kind':'REQUIRED_INPUTS','observation':value,'blockers':builders.guidance(observed),'questions':[],
                 'execution_input_received_by_model':'NOT_OBSERVED','source_scope':'EXISTING_WORK_CONTRACT_ONLY'}
    elif name=='contract_prepare':
        c.require(args['kind']=='document' or not args['body_text'],'PREPARATION_BODY_SCOPE')
        artifact=c.decode(args['request_json'].encode())
        c.require(isinstance(artifact,dict) and artifact.get('work_id',args['work_id'])==args['work_id'],'PREPARATION_ARTIFACT_WORK_BINDING')
        value=native(service,scope,args['work_id'],project,observed['record'],'native_validate',args)
        payload={'kind':'VALIDATED_ARTIFACT','validation':value,'blockers':[],'questions':[],
                 'native_json':args['request_json'],'body':args['body_text'],'native_state_preconditions_checked':False}
    else:
        if name=='approved_action_prepare':
            entry,envelope,request=owner_action(service,args);sources={};missing=[]
            validation_args={'tool':entry['tool']}
            if entry['tool'].startswith('session_'):c.require(request['expected_sequence']==basis['sequence'],'PREPARATION_STALE')
            payload={'kind':'OWNER_ACTION','entry':entry,'action':envelope,'action_sha256':entry['action']['sha256'],
                     'owner_policy_sha256':service.preparation_policy.digest}
        else:
            envelope,request,entry,missing,sources=builders.build(args,observed,uuid.uuid4().hex)
            validation_args=args
            payload={'kind':'DRAFT_ACTION','entry_review':entry,'action':envelope,'action_sha256':c.sha(c.encoded(envelope)),
                     'owner_registration':'NOT_PERFORMED','manual_input_measurement':{'derived_fields':len(sources),'caller_fields':len(c.decode(args['fields_json'].encode())),'native_request_fields':len(request),'transport_selectors':6,'required_nonempty_text_fields':sum(bool(args[k]) for k in ('body','context_json','count_json')),'basis':'NATIVE_FIELD_COUNTS_EXCLUDE_TRANSPORT_SELECTORS_NOT_AGENT_SUCCESS'}}
        if not missing:builders.validate_observed(entry,envelope,request,observed)
        blockers=builders.guidance(observed,entry['session_id'])
        if missing:questions=[{'field':field,'reason':'CALLER_INPUT_REQUIRED_NO_FABRICATION'} for field in missing];blockers.append({'code':'PREPARATION_INPUTS_MISSING'})
        check=builders.validator(validation_args,envelope,request) if not missing else None
        payload['validation']=native(service,scope,args['work_id'],project,observed['record'],'native_validate',check) if check else {'validation_scope':'D4_REQUEST_SHAPE_ONLY' if not missing else 'NOT_RUN_MISSING_INPUTS'}
        if entry['tool']=='execution_request' and name=='action_prepare':blockers.append({'code':'OWNER_APPROVAL_REQUIRED'})
        if entry['tool']=='helper_execute' and name=='action_prepare':blockers.append({'code':'SEPARATE_OWNER_HELPER_EFFECTS_REQUIRED'})
        if entry['tool'] in ('candidate_request','workspace_request') and name=='action_prepare':blockers.append({'code':'SEPARATE_OWNER_PARALLEL_HOST_REQUIRED'})
        payload.update(blockers=blockers,questions=questions,derived_fields=sources)
    _,after,current=observe(service,scope,args['work_id']);c.require(basis==current,'OBSERVATION_STALE')
    return seal(service,scope,args,after,current,payload)
