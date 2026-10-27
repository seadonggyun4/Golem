"""M1 finite native reads through pinned D2 scopes, never arbitrary argv or paths.

Native stdout bytes are retained and returned exactly. Source material remains
untrusted; delivery, integrity and historical results do not create authority.
"""
import base64
import re
from pathlib import Path
import tempfile

import integration_contract as c
import integration_backend as backend
import integration_registry as r
import execution_record as records

NAMES=('workflow_read','template_read','role_read','session_read','binding_read',
       'document_read','context_read','discovery_read','journal_read',
       'profile_read','diagnostic_read','native_validate','report_read','approval_read','reentry_read')
WORK={'project_id':c.ID,'work_id':c.ID}
JSON={'type':'string','minLength':1,'maxLength':c.LIMIT}
REV={'type':'integer','minimum':1,'maximum':4096}
SIZE={'type':'integer','minimum':1,'maximum':1048576}

def variants(*rules):return {'type':'object','oneOf':list(rules)}
def query(operation,**fields):return c.obj({**WORK,'operation':c.enum(operation),**fields})

SCHEMAS={
 'workflow_read':variants(query('next',selection_id=c.ID),query('trace',selection_id=c.ID,revision=REV),query('select',selection_id=c.ID,revision=REV,target_kind=c.ID),query('inputs',selection_id=c.ID,target_kind=c.ID,source_snapshot=c.DIGEST,byte_budget=SIZE)),
 'template_read':variants(query('list'),query('show',name=c.enum('feature','bugfix','review','research')),query('validate',request_json=JSON),query('instantiate',scope_id=c.ID,revision=REV,request_json=JSON)),
 'role_read':variants(query('template',role=c.ID),query('validate',request_json=JSON),query('status',request_json=JSON),query('evaluate',request_json=JSON)),
 'session_read':query('context',request_json=JSON),
 'binding_read':query('inspect',request_json=JSON),
 'document_read':query('inspect',document_id=c.ID,revision=REV),
 'context_read':variants(query('render',request_json=JSON),query('markdown',request_json=JSON),query('read',digest=c.DIGEST,source_snapshot=c.DIGEST),query('render',request_json=JSON,token_count_json=JSON),query('markdown',request_json=JSON,token_count_json=JSON),query('read',digest=c.DIGEST,source_snapshot=c.DIGEST,token_count_json=JSON)),
 'discovery_read':variants(query('validate',request_json=JSON),query('report',request_json=JSON,kind=c.enum('discovery','research','scope'))),
 'journal_read':variants(query('inspect',stream_base64=JSON),query('replay',stream_base64=JSON)),
 'profile_read':query('current'),
 'diagnostic_read':variants(c.obj({**WORK,'kind':c.enum('clock','work','noop_adapter')}),c.obj({**WORK,'kind':c.enum('adapter_current'),'adapter_id':c.ID,'session_id':{'type':'string','maxLength':128}})),
 'native_validate':variants(c.obj({**WORK,'kind':c.enum('capsule','completion','reentry','discovery','role','template','adapter','execution','session','profile','binding_request','role_request','approval_request','work_specification','research','redaction','inventory_policy','candidate_request_digest','candidate_host'),'request_json':JSON}),c.obj({**WORK,'kind':c.enum('document'),'request_json':JSON,'body_text':{'type':'string','maxLength':c.LIMIT}})),
 'report_read':variants(c.obj({**WORK,'kind':c.enum('completion','reentry'),'sequence':{'type':'integer','minimum':1,'maximum':64}}),c.obj({**WORK,'kind':c.enum('execution_render'),'request_json':JSON}),c.obj({**WORK,'kind':c.enum('execution_bundle_inspect'),'receipt_digest':c.DIGEST}),c.obj({**WORK,'kind':c.enum('execution_bundle_verify'),'request_json':JSON})),
 'approval_read':query('status',request_json=JSON),
 'reentry_read':query('status',request_json=JSON),
}

def request(args,output,operation=None):
    """Preserve supplied UTF-8 JSON bytes; native schema validation stays native."""
    raw=args['request_json'].encode('utf-8');value=c.decode(raw)
    c.require(isinstance(value,dict),'NATIVE_REQUEST_OBJECT')
    if operation is not None:c.require(value.get('operation')==operation,'READ_OPERATION_REQUIRED')
    path=output/'request-native.json';records.save(path,raw);return str(path)


def _document(record,document_id,revision):
    c.require(isinstance(record.get('documents'),list) and all(isinstance(v,dict) for v in record['documents']),'READ_DOCUMENT_BINDING')
    rows=[v for v in record.get('documents',[]) if v.get('document_id')==document_id and v.get('revision')==revision]
    c.require(len(rows)==1,'READ_DOCUMENT_BINDING');return rows[0]


def _receipt(record,digest):
    c._validate(digest,c.DIGEST)
    rows=record.get('documents',[])
    c.require(isinstance(rows,list) and any(isinstance(row,dict) and isinstance(row.get('metadata'),dict) and row['metadata'].get('execution_receipt')==digest for row in rows),'READ_RECEIPT_BINDING')
    return digest


def command(name,args,work,output,before):
    """Closed native argv construction. Every filesystem name comes from owner scope or this private spool."""
    op=args.get('operation')
    if name=='workflow_read':
        selection=args['selection_id']
        if op in ('trace','select'):_document(before,selection,args['revision'])
        base=['workflow',op,work,selection]
        if op=='next':return base
        if op=='trace':return [*base,str(args['revision'])]
        if op=='select':return [*base,str(args['revision']),args['target_kind']]
        return [*base,args['target_kind'],args['source_snapshot'],str(args['byte_budget'])]
    if name=='template_read':
        if op=='list':return ['workflow','template','list']
        if op=='show':return ['workflow','template','show',args['name']]
        if op=='validate':return ['workflow','template','validate',request(args,output)]
        _document(before,args['scope_id'],args['revision'])
        return ['workflow','template','instantiate',work,args['scope_id'],str(args['revision']),request(args,output)]
    if name=='role_read':
        if op=='template':return ['role','template',args['role']]
        if op=='validate':return ['role','validate',request(args,output)]
        return ['role','call',work,request(args,output,op)]
    if name=='session_read':return ['session','call',work,request(args,output,'context')]
    if name=='binding_read':return ['agent','binding','inspect',work,request(args,output,'inspect')]
    if name=='document_read':
        _document(before,args['document_id'],args['revision'])
        return ['document','inspect',work,args['document_id'],str(args['revision'])]
    if name=='context_read':
        suffix=[]
        if 'token_count_json' in args:
            raw=args['token_count_json'].encode('utf-8');c.require(isinstance(c.decode(raw),dict),'TOKEN_PROOF_OBJECT')
            path=output/'token-count.json';records.save(path,raw);suffix=['--token-count',str(path)]
        if op=='read':return ['context','read',work,args['digest'],args['source_snapshot'],*suffix]
        return ['context',op,work,request(args,output),*suffix]
    if name=='discovery_read':
        path=request(args,output)
        return ['discovery',op,path,*([args['kind']] if op=='report' else [])]
    if name=='journal_read':
        import binascii
        try:raw=base64.b64decode(args['stream_base64'],validate=True)
        except (ValueError,binascii.Error):raise c.IntegrationError('JOURNAL_ENCODING') from None
        c.require(bool(raw) and len(raw)<=c.LIMIT,'JOURNAL_SIZE')
        path=output/'input-journal.bin';records.save(path,raw)
        return ['journal','inspect',str(path)] if op=='inspect' else ['replay',str(path)]
    if name=='profile_read':return ['profile','current',work]
    if name=='diagnostic_read':
        if args['kind']=='noop_adapter':return ['adapter','noop','probe']
        if args['kind']=='adapter_current':return ['adapter','describe','--current',args['adapter_id'],args['session_id']]
        return ['doctor',args['kind'],*([work] if args['kind']=='work' else [])]
    if name=='native_validate':
        if args['kind']=='document':
            body=output/'document-body.bin';records.save(body,args['body_text'].encode('utf-8'))
            return ['document','validate',request(args,output),str(body)]
        kind=args['kind']
        validation_routes={'binding_request':['agent','binding','validate'],'role_request':['role','request-validate'],'approval_request':['approval','validate'],'work_specification':['work','validate'],'redaction':['research','redaction-validate'],'inventory_policy':['inventory','validate'],'candidate_request_digest':['candidate','request-digest'],'candidate_host':['candidate','host-validate']}
        if kind in validation_routes:return [*validation_routes[kind],request(args,output)]
        family='workflow' if kind=='template' else kind
        return ['adapter','describe',request(args,output)] if kind=='adapter' else [family,*(['template'] if kind=='template' else []),'validate',request(args,output)]
    if name=='report_read':
        kind=args['kind']
        if kind=='execution_render':
            path=request(args,output);value=c.decode(Path(path).read_bytes());c.require(value.get('work_id')==args['work_id'],'READ_REPORT_WORK_BINDING')
            _receipt(before,value.get('execution_receipt'))
            return ['execution','render',work,path]
        if kind in ('execution_bundle_inspect','execution_bundle_verify'):
            if kind=='execution_bundle_verify':
                path=request(args,output);value=c.decode(Path(path).read_bytes());digest=value.get('qa_receipt')
            else:digest=args['receipt_digest']
            _receipt(before,digest)
            return ['execution','bundle','verify',work,path] if kind=='execution_bundle_verify' else ['execution','bundle','inspect',work,digest]
        return [kind,'inspect',work,str(args['sequence'])]
    if name=='reentry_read':return ['reentry','call',work,request(args,output,'status')]
    if name=='approval_read':return ['approval','call',work,request(args,output,'status')]
    raise c.IntegrationError('UNSUPPORTED_READ_TOOL')


def decode_result(name,args,raw):
    op=args.get('operation')
    if (name=='template_read' and op=='validate') or (name=='native_validate' and args['kind'] in ('template','execution','candidate_request_digest','candidate_host')):
        c.require(re.fullmatch(b'[0-9a-f]{64}\n?',raw) is not None,'NATIVE_RESPONSE')
        return {'digest':raw.strip().decode('ascii'),'role':'HASH_ONLY_NOT_SCHEMA_VALIDATION' if args.get('kind')=='candidate_request_digest' else 'NATIVE_VALIDATION_DIGEST_NOT_ACCEPTANCE'}
    if (name=='context_read' and op=='markdown') or (name=='discovery_read' and op=='report') or (name=='report_read' and args['kind']=='execution_render'):
        try:return raw.decode('utf-8',errors='strict')
        except UnicodeError:raise c.IntegrationError('NATIVE_RESPONSE') from None
    try:
        value=c.decode(raw,c.MAX_NATIVE)
        c.require(isinstance(value,(dict,list)),'NATIVE_RESPONSE')
        return value
    except c.IntegrationError:raise c.IntegrationError('NATIVE_RESPONSE') from None


def read(service,scope,name,args):
    """Recheck scoped authorization and unchanged native record around one read."""
    c.require(name in NAMES,'UNSUPPORTED_READ_TOOL');c._validate(args,SCHEMAS[name])
    work_id=args['work_id'];project=service._authorize(scope,work_id,'record')
    backend._quota(service.registry.root,3)
    before=service._read(scope,work_id,'record')['result']
    project=service._authorize(scope,work_id,'record')
    work=next(w for w in project['works'] if w['work_id']==work_id)
    backend._quota(service.registry.root,2)
    output=Path(tempfile.mkdtemp(prefix='read-m1-',dir=service.registry.root))
    records.save(output/'request.json',c.encoded(args))
    try:
        argv=command(name,args,work['path'],output,before)
        process=records.capture([project['cli']['path'],'--output-mode','full',*argv],output,
            backend.TIMEOUT_SECONDS,cwd=output,observe_source=False,env=backend.ENVIRONMENT,limit=c.MAX_NATIVE)
        c.require(type(process.get('returncode')) is int and process['returncode']==0 and process['reason']=='EXIT' and process['recording']=='RECORDED','NATIVE_FAILURE')
        raw=r.regular(output/'stdout.log',c.MAX_NATIVE,private=True)
        r.check_project(project)
        after=service._read(scope,work_id,'record')['result']
        c.require(c.encoded(before)==c.encoded(after),'OBSERVATION_STALE')
        result={'view':name,'operation':args.get('operation',args.get('kind',args.get('format'))),
            'native_stdout':{'encoding':'base64','data':base64.b64encode(raw).decode('ascii'),'bytes':len(raw),'sha256':c.sha(raw)},
            'work_record_sha256':c.sha(c.encoded(after)),'content_role':'UNTRUSTED_DATA',
            'command_contract':'FIXED_READ_ONLY_NATIVE_ARGV','interpretation':'NO_COMPLETION_OR_EXECUTION_AUTHORITY_INFERRED'}
        result['result']=decode_result(name,args,raw)
        c.require(len(c.encoded(result))+2048<=service.transfer.value['max_result_bytes'],'RESULT_BUDGET_EXCEEDED')
        records.save(output/'delivery.json',c.encoded(result));return result
    except (c.IntegrationError,OSError,ValueError) as error:
        records.save(output/'failure.json',c.encoded({'code':getattr(error,'code','IO_OR_CONTRACT_ERROR'),'automatic_retry_allowed':False}))
        error.evidence_path=str(output);raise
