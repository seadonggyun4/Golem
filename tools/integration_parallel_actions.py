"""M5 exact project inventory capture. No candidate host, scheduler or merge authority."""
import copy
import integration_contract as c
import execution_record as records

NAMES = ('inventory_capture','candidate_request','workspace_request')
HOST_NAMES = ('candidate_request','workspace_request')
CANDIDATE_OPS = ('create','enroll','reserve','start','cancel','settle','diff-seal','review','select','cohort-record')
WORKSPACE_OPS = ('workspace-create','workspace-resume','workspace-activate','workspace-seal','workspace-retain','workspace-remove')
TEXT = {'type':'string','minLength':1,'maxLength':c.LIMIT}


def shape(entry,envelope):
    c.require(entry['tool'] in NAMES,'PARALLEL_TOOL')
    value=c.decode(envelope['native_json'].encode())
    if entry['tool']=='inventory_capture':
        c._validate(value,c.obj({'policy_json':TEXT}))
        c.require(isinstance(c.decode(value['policy_json'].encode()),dict),'INVENTORY_POLICY_OBJECT')
    else:
        c._validate(value,c.obj({'host_id':c.ID,'request_json':TEXT}))
        request=c.decode(value['request_json'].encode())
        c.require(isinstance(request,dict) and request.get('operation') in
            (CANDIDATE_OPS if entry['tool']=='candidate_request' else WORKSPACE_OPS),'HOST_OPERATION_SCOPE')
        c.require(request.get('operation')!='finish','HOST_TYPED_SETTLEMENT_REQUIRED')
    c.require(not envelope['body'] and not envelope['context_json'] and not envelope['count_json'] and envelope['approval'] is None,'PARALLEL_ENVELOPE_SCOPE')
    return value


def draft(args,observed,key):
    value=c.decode(args['fields_json'].encode())
    c.require(isinstance(value,dict),'PREPARATION_FIELDS_OBJECT')
    value=copy.deepcopy(value)
    required=('policy_json',) if args['tool']=='inventory_capture' else ('host_id','request_json')
    missing=[field for field in required if field not in value]
    envelope={'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),
        'body':args['body'],'context_json':args['context_json'],'count_json':args['count_json'],'approval':None}
    entry={field:args[field] for field in ('tool','project_id','work_id','session_id','native_binding_id')}
    if not missing:shape(entry,envelope)
    return envelope,value,entry,missing,{}


def validator(name,envelope,request):
    if name=='inventory_capture':return {'kind':'inventory_policy','request_json':request['policy_json']}
    return None


def command(entry,project,work,envelope,output):
    value=shape(entry,envelope)
    c.require(entry['tool']=='inventory_capture','OWNER_PARALLEL_HOST_REQUIRED')
    records.save(output/'inventory-policy.json',value['policy_json'].encode())
    return ['inventory','capture',project['root'],str(output/'inventory-policy.json')]
