"""Exact owner-selected Work Pack actions; native approval/CAS remains authoritative."""
from pathlib import Path
import os
import integration_contract as c
import integration_registry as r
import execution_record as records

NAMES=('workpack_bind','workpack_receipt_manifest','workpack_receipt_export')
TEXT={'type':'string','minLength':2,'maxLength':131072}
FIELDS={
 'workpack_bind':{'request_json':TEXT,'approval_digest':c.DIGEST},
 'workpack_receipt_manifest':{'request_json':TEXT,'output_parent':c.PATH,'output_identity':c.IDENTITY,'format':c.enum('json','markdown')},
 'workpack_receipt_export':{'request_json':TEXT,'output_parent':c.PATH,'output_identity':c.IDENTITY,'format':c.enum('json','markdown'),'approval_digest':c.DIGEST},
}

def shape(entry,envelope):
    name=entry['tool'];c.require(name in NAMES,'WORKPACK_ACTION_SCOPE')
    value=c.decode(envelope['native_json'].encode());c._validate(value,c.obj(FIELDS[name]))
    c.require(not envelope['body'] and not envelope['context_json'] and not envelope['count_json'] and envelope['approval'] is None,'WORKPACK_ENVELOPE_SCOPE')
    c.require(len(value['request_json'].encode()) <= (131072 if name=='workpack_bind' else 65536),'WORKPACK_INPUT_LIMIT')
    # Only transport framing here. No duplicate native schema/reducer implementation.
    c.require(isinstance(c.decode(value['request_json'].encode()),dict),'WORKPACK_REQUEST_OBJECT')
    return value

def authorize(entry,value,project,policy):
    if entry['tool']=='workpack_bind':return
    parent=r.real_path(value['output_parent'])
    c.require(r.identity(parent)==value['output_identity'],'WORKPACK_OUTPUT_CHANGED')
    info=parent.stat();c.require(info.st_uid==os.getuid() and info.st_mode & 0o077==0,'WORKPACK_OUTPUT_PRIVATE')
    protected=[Path(project['root']),Path(project['runtime_root']),policy.registry.root,policy.path,policy.transfer.path,Path(entry['action']['path'])]
    for path in protected:
        c.require(not parent.is_relative_to(path) and not path.is_relative_to(parent),'WORKPACK_OUTPUT_SCOPE')

def command(entry,project,work,envelope,output):
    value=shape(entry,envelope);request=output/'workpack-native.json';records.save(request,value['request_json'].encode())
    if entry['tool']=='workpack_bind':return ['pack','bind',work['path'],str(request),'--approve-binding',value['approval_digest']]
    op='manifest' if entry['tool']=='workpack_receipt_manifest' else 'export'
    argv=['receipt',op,work['path'],str(request),value['output_parent'],'--format',value['format']]
    if op=='export':argv+=['--approve-export',value['approval_digest']]
    return argv

def draft(args,observed,key):
    value=c.decode(args['fields_json'].encode());c.require(isinstance(value,dict),'PREPARATION_FIELDS_OBJECT')
    c.require(set(value)<=set(FIELDS[args['tool']]),'SCHEMA')
    missing=[k for k in FIELDS[args['tool']] if k not in value]
    envelope={'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),'body':args['body'],'context_json':args['context_json'],'count_json':args['count_json'],'approval':None}
    entry={k:args[k] for k in ('tool','project_id','work_id','session_id','native_binding_id')}
    if not missing:shape(entry,envelope)
    return envelope,value,entry,missing,{}
