"""M4 finite evidence/research/export actions; native reducers retain authority."""
import copy
from pathlib import Path
import integration_contract as c
import integration_task_actions as tasks
import execution_record as records

NAMES=('evidence_import','proof_publish','research_request','research_export','cost_inbox_reconcile','helper_execute','execution_verify')
TEXT={'type':'string','maxLength':c.LIMIT}
OBJECT={'type':['object','null']}
RESEARCH=('case-create','attempt-plan','attempt-record','outcome-enroll','adjudicate','cohort-create','cohort-observe')


def shape(entry,envelope):
    name=entry['tool'];c.require(name in NAMES,'QUALITY_TOOL')
    value=c.decode(envelope['native_json'].encode());c.require(isinstance(value,dict),'NATIVE_ACTION')
    rules={
      'evidence_import':{'data_base64':TEXT},
      'proof_publish':{'pack_json':TEXT},
      'research_request':{'schema_version':{'const':1},'operation':c.enum(*RESEARCH),'key':c.ID,'record':OBJECT},
      'research_export':{'case_id':c.ID,'redaction_json':TEXT},
      'cost_inbox_reconcile':{'capsule_json':TEXT,'run_id':c.ID,'inbox_json':TEXT},
      'helper_execute':{'helper_id':c.ID},
      'execution_verify':{'schema_version':{'const':1},'operation':{'const':'verify'},'receipt':c.DIGEST},
    }
    c._validate(value,c.obj(rules[name]))
    c.require(not envelope['body'] and not envelope['context_json'] and not envelope['count_json'] and envelope['approval'] is None,'QUALITY_ENVELOPE_SCOPE')
    for key in ('pack_json','redaction_json','capsule_json','inbox_json'):
        if key in value:c.require(isinstance(c.decode(value[key].encode()),dict),'QUALITY_JSON_OBJECT')
    if name=='evidence_import':tasks.binary(value['data_base64'])
    if name=='research_request':
        c.require(isinstance(value['record'],dict),'QUALITY_RESEARCH_RECORD')
        c.require(value['record'].get('work_id',entry['work_id'])==entry['work_id'],'QUALITY_RESEARCH_WORK_BINDING')
        c.require(value['record'].get('project_id',entry['project_id'])==entry['project_id'],'QUALITY_RESEARCH_PROJECT_BINDING')
    if name=='cost_inbox_reconcile':
        inbox=c.decode(value['inbox_json'].encode());c.require(set(inbox)=={'snapshots'} and isinstance(inbox['snapshots'],list) and len(inbox['snapshots'])==1,'QUALITY_INBOX_SCOPE')
        for i,row in enumerate(inbox['snapshots'],1):
            c.require(isinstance(row,dict) and row.get('run_id')==value['run_id'] and str(row.get('sequence'))==str(i),'QUALITY_INBOX_BINDING')
    return value


def draft(args,observed,key):
    value=c.decode(args['fields_json'].encode());c.require(isinstance(value,dict),'PREPARATION_FIELDS_OBJECT')
    c.require(not set(value)&{'key','work_id','expected_sequence','expected_generation','token','input_digest'},'PREPARATION_RESERVED_FIELD')
    value=copy.deepcopy(value);name=args['tool'];sources={};missing=[]
    if name=='execution_verify':
        c.require('schema_version' not in value and 'operation' not in value,'PREPARATION_RESERVED_FIELD');value.update(schema_version=1,operation='verify');sources={'schema_version':'NATIVE_VERSION','operation':'CLOSED_TOOL'}
    if name=='research_request':
        c.require('schema_version' not in value,'PREPARATION_RESERVED_FIELD');value['schema_version']=1;value['key']=key;sources={'schema_version':'NATIVE_VERSION','key':'NEW_PREPARATION_ID'}
    fields={'evidence_import':('data_base64',),'proof_publish':('pack_json',),'research_request':('operation','record'),'research_export':('case_id','redaction_json'),'cost_inbox_reconcile':('capsule_json','run_id','inbox_json'),'helper_execute':('helper_id',),'execution_verify':('receipt',)}[name]
    for field in fields:
        if field not in value:missing.append(field)
    envelope={'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),'body':args['body'],'context_json':args['context_json'],'count_json':args['count_json'],'approval':None}
    entry={field:args[field] for field in ('tool','project_id','work_id','session_id','native_binding_id')}
    if not missing:shape(entry,envelope)
    return envelope,value,entry,missing,sources


def validator(name,envelope,request):
    if name=='research_request':return {'kind':'research','request_json':envelope['native_json']}
    if name=='cost_inbox_reconcile':return {'kind':'capsule','request_json':request['capsule_json']}
    return None


def command(entry,project,work,envelope,output):
    request=shape(entry,envelope);name=entry['tool']
    def save(filename,value):records.save(output/filename,value.encode());return str(output/filename)
    if name=='evidence_import':
        records.save(output/'evidence.bin',tasks.binary(request['data_base64']));return ['evidence','put',work['path'],str(output/'evidence.bin')]
    if name=='proof_publish':
        root=output/'proof';root.mkdir(mode=0o700);return ['proof','publish',save('pack.json',request['pack_json']),str(root)]
    if name=='execution_verify':return ['execution','verify',work['path'],str(output/'request.json')]
    if name=='research_request':return ['research','call',work['path'],str(output/'request.json')]
    if name=='research_export':return ['research','export',work['path'],'--case',request['case_id'],'--output',str(output/'research-export'),'--redact',save('redaction.json',request['redaction_json'])]
    if name=='cost_inbox_reconcile':
        inbox=output/'inbox';inbox.mkdir(mode=0o700)
        for i,row in enumerate(c.decode(request['inbox_json'].encode())['snapshots'],1):records.save(inbox/(str(i).zfill(20)+'.json'),c.encoded(row))
        return ['cost','inbox',save('capsule.json',request['capsule_json']),request['run_id'],str(inbox),str(len(c.decode(request['inbox_json'].encode())['snapshots']))]
    raise c.IntegrationError('QUALITY_HELPER_REQUIRES_SEPARATE_OWNER_POLICY')
