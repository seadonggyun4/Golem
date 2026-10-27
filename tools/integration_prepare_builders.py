"""M2 draft construction from observed native fields, never native admission.

Common fences are copied from the scoped snapshot. Caller prose, evidence and
source attribution remain untrusted. Pure D4 shape checking creates no approval.
"""
import copy
import integration_contract as c
import integration_mutation_contract as actions
import integration_task_actions as tasks
import integration_quality_actions as quality
import integration_parallel_actions as parallel

AUTO_FIELDS=('work_id','key','expected_sequence','expected_generation','token','input_digest')

def reference(row):
    value={k:row[k] for k in ('document_id','revision','digest')}
    c._validate(value,actions.REFERENCE);return value


def latest(record,document_id):
    rows=[row for row in record['documents'] if row.get('document_id')==document_id]
    return max(rows,key=lambda row:row['revision']) if rows else None


def active(status):
    state=status.get('state')
    return state.get('active') or {} if isinstance(state,dict) else {}


def token(status,owner):
    current=active(status)
    c.require(current.get('session_id')==owner,'PREPARATION_OWNER_MISMATCH')
    value={k:current.get(k) for k in ('epoch','attempt_id','session_id')}
    c._validate(value,actions.TOKEN);return value


def build(args,observed,key):
    if args["tool"] in parallel.NAMES:return parallel.draft(args,observed,key)
    if args["tool"] in quality.NAMES:return quality.draft(args,observed,key)
    if args["tool"] in tasks.NAMES:return tasks.draft(args,observed,key)
    fields=c.decode(args['fields_json'].encode());c.require(isinstance(fields,dict),'PREPARATION_FIELDS_OBJECT')
    c.require(not set(fields)&set(AUTO_FIELDS),'PREPARATION_RESERVED_FIELD')
    value=copy.deepcopy(fields);target=args['tool'];status=observed['status'];following=observed['next'];record=observed['record']
    sequence=status['sequence'];owner=args['session_id'];current=active(status)
    missing=[];sources={};operation=target.removeprefix('session_') if target.startswith('session_') else value.get('operation')
    def need(name):
        if name not in value:missing.append(name)
    def derive(name,data,source):value[name]=data;sources[name]=source
    if target.startswith('session_'):
        c.require('schema_version' not in fields and 'operation' not in fields,'PREPARATION_RESERVED_FIELD')
        derive('schema_version',2 if args['native_binding_id'] and operation in ('claim','resume') else 1,'D4_BINDING_FORM')
        derive('operation',operation,'CLOSED_D4_TOOL');derive('work_id',args['work_id'],'SCOPED_WORK')
        derive('expected_sequence',sequence,'NATIVE_STATUS_SEQUENCE');derive('key',key,'NEW_PREPARATION_ID')
        if operation in ('claim','resume'):
            derive('session_id',owner,'SUPPLIED_LABEL_NOT_AUTHENTICATED_IDENTITY');need('ttl_ms')
            if args['native_binding_id']:derive('binding_id',args['native_binding_id'],'SUPPLIED_OWNER_MAPPING_RECHECK_AT_CONFIRMATION')
            if operation=='claim':
                derive('expected_generation',following['document_generation'],'NATIVE_NEXT_DOCUMENT_GENERATION')
                for name in ('source_snapshot','byte_budget'):need(name)
            elif args['native_binding_id']:derive('token',token(status,owner) if current else None,'NATIVE_ACTIVE_FENCE')
        else:
            derive('token',token(status,owner),'NATIVE_ACTIVE_FENCE')
            derive('input_digest',current.get('manifest_digest'),'NATIVE_ACTIVE_MANIFEST_DIGEST')
        if operation in ('submit','reconcile'):
            derive('source_snapshot',current.get('source_snapshot'),'NATIVE_ACTIVE_SOURCE_SNAPSHOT')
            for name in ('output','evidence'):need(name)
            if operation=='reconcile':need('resolution')
            if value.get('output') is not None:
                row=latest(record,value['output'].get('document_id'))
                c.require(row is not None and reference(row)==value['output'],'PREPARATION_OUTPUT_BINDING')
    elif target=='document_submit':
        for name in ('schema_version','document_id','kind','stage','producer_attempt','requirement_ids','source_snapshot','scope_revision','template_version','policy_version'):need(name)
        if 'document_id' in value:
            row=latest(record,value['document_id']);derive('revision',row['revision']+1 if row else 1,'NATIVE_LATEST_DOCUMENT_REVISION')
            derive('supersedes',row['digest'] if row else '','NATIVE_LATEST_MANIFEST_DIGEST')
        parent_ids=value.pop('parent_ids',None)
        c.require(not (parent_ids is not None and 'parents' in value),'PREPARATION_PARENT_FORMS')
        if parent_ids is not None:
            c._validate(parent_ids,c.array(c.ID,64,0));parents=[]
            for document_id in parent_ids:
                row=latest(record,document_id);c.require(row is not None,'PREPARATION_PARENT_BINDING');parents.append(reference(row))
            derive('parents',parents,'NATIVE_LATEST_REGISTERED_REFERENCES')
        else:
            need('parents')
            for parent in value.get('parents',[]):
                c._validate(parent,actions.REFERENCE);row=latest(record,parent['document_id'])
                c.require(row is not None and reference(row)==parent,'PREPARATION_PARENT_BINDING')
        derive('work_id',args['work_id'],'SCOPED_WORK');derive('expected_generation',following['document_generation'],'NATIVE_NEXT_DOCUMENT_GENERATION')
        if not args['body']:missing.append('body')
    elif target=='execution_request':
        c.require(operation in ('prepare','finish','run'),'PREPARATION_EXECUTION_OPERATION')
        c.require('schema_version' not in fields,'PREPARATION_RESERVED_FIELD')
        derive('schema_version',1,'D4_EXECUTION_REQUEST_VERSION')
        for name in (('contract',) if operation=='prepare' else ('checkpoint','attempt_id') if operation=='run' else ('checkpoint',)):need(name)
        if current:derive('token',token(status,owner),'NATIVE_ACTIVE_FENCE')
    else:raise c.IntegrationError('PREPARATION_TARGET')
    envelope={'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),
              'body':args['body'],'context_json':args['context_json'],'count_json':args['count_json'],'approval':None}
    entry={'tool':target,'work_id':args['work_id'],'session_id':owner,'native_binding_id':args['native_binding_id']}
    if not missing:actions.action_shape(entry,envelope,allow_missing_approval=True)
    return envelope,value,entry,sorted(set(missing)),sources


def guidance(observed,owner=''):
    """Expose native reasons, never reproduce the native permission predicate."""
    hint=observed['status'].get('resume_preflight') or {};following=observed['next']
    rows=[]
    if following.get('action') in ('BLOCKED','WAIT'):rows.append({'code':'NATIVE_NEXT_'+following['action'],'reason':following.get('reason'),'authority':'NATIVE_OBSERVATION'})
    if hint.get('owner_session_id') and owner and hint['owner_session_id']!=owner:rows.append({'code':'DIFFERENT_NATIVE_OWNER','authority':'NATIVE_OBSERVATION'})
    return rows


def validator(args,envelope,native):
    if args["tool"] in parallel.NAMES:return parallel.validator(args["tool"],envelope,native)
    if args["tool"] in quality.NAMES:return quality.validator(args["tool"],envelope,native)
    if args["tool"] in tasks.NAMES:return tasks.validator(args["tool"],envelope,native)
    if args['tool'].startswith('session_'):return {'kind':'session','request_json':envelope['native_json']}
    if args['tool']=='document_submit':return {'kind':'document','request_json':envelope['native_json'],'body_text':envelope['body']}
    if native['operation']=='prepare':return {'kind':'execution','request_json':c.encoded(native['contract']).decode()}
    return None


def validate_observed(entry,envelope,request,observed):
    """Field equality to observed fences; not the native state/permission reducer."""
    if entry["tool"] in parallel.NAMES:return None
    if entry["tool"] in quality.NAMES:return None
    if entry["tool"] in tasks.NAMES:return tasks.validate_observed(entry,request,observed)
    name=entry['tool'];status=observed['status'];following=observed['next'];record=observed['record']
    if name.startswith('session_'):
        operation=name.removeprefix('session_')
        c.require(request['expected_sequence']==status['sequence'],'PREPARATION_STALE')
        if operation in ('claim','resume'):
            binding=(status.get('state') or {}).get('binding')
            if binding is not None:
                c.require(isinstance(binding,dict) and request.get('binding_id')==binding.get('binding_id') and request.get('session_id')==binding.get('session_id'),'PREPARATION_BINDING_CHANGED')
            else:c.require(not entry['native_binding_id'],'PREPARATION_BINDING_CHANGED')
        if operation=='claim':
            c.require(request['expected_generation']==following['document_generation'],'PREPARATION_STALE')
            state=status.get('state') or {};row=latest(record,state.get('selection_id'))
            c.require(row is not None and isinstance(row.get('metadata'),dict) and row['metadata'].get('source_snapshot')==request['source_snapshot'],'PREPARATION_SELECTION_BINDING')
        if operation not in ('claim','resume'):
            c.require(request['token']==token(status,entry['session_id']),'PREPARATION_TOKEN_CHANGED')
            c.require(request['input_digest']==active(status).get('manifest_digest'),'PREPARATION_INPUT_CHANGED')
        if operation in ('submit','reconcile'):
            c.require(request['source_snapshot']==active(status).get('source_snapshot'),'PREPARATION_SOURCE_CHANGED')
            if request.get('output') is not None:
                row=latest(record,request['output'].get('document_id'))
                c.require(row is not None and reference(row)==request['output'],'PREPARATION_OUTPUT_BINDING')
    elif name=='document_submit':
        c.require(request['expected_generation']==following['document_generation'],'PREPARATION_STALE')
        row=latest(record,request['document_id'])
        c.require(request['revision']==(row['revision']+1 if row else 1) and request['supersedes']==(row['digest'] if row else ''),'PREPARATION_DOCUMENT_CHANGED')
        for parent in request['parents']:
            row=latest(record,parent['document_id']);c.require(row is not None and reference(row)==parent,'PREPARATION_PARENT_BINDING')
    elif active(status):
        c.require(request.get('token')==token(status,entry['session_id']),'PREPARATION_TOKEN_CHANGED')
