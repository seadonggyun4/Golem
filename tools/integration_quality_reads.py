"""M4 fixed native reads. Uploaded artifacts/accounting are untrusted data."""
import base64
from pathlib import Path
import tempfile
import integration_contract as c
import integration_registry as r
import integration_backend as backend
import integration_read_resources as resources
import integration_quality_actions as actions
import execution_record as records

NAMES=('proof_read','research_read','cost_read','execution_read')
WORK={'project_id':c.ID,'work_id':c.ID}
TEXT={'type':'string','maxLength':c.LIMIT}
SEQ={'type':'integer','minimum':1,'maximum':4096}
LABEL={'type':'string','maxLength':64,'pattern':'^[A-Za-z0-9_-]*$'}
def query(operation,**fields):return c.obj({**WORK,'operation':c.enum(operation),**fields})
SCHEMAS={
 'proof_read':{'type':'object','oneOf':[query('render',request_json=TEXT),query('verify',request_json=TEXT,pack_json=TEXT),query('integrity',pack_json=TEXT,manifest_sha256=c.DIGEST),query('verify_dir',files_json=TEXT,manifest_sha256=c.DIGEST)]},
 'research_read':{'type':'object','oneOf':[query('status'),query('inspect',sequence=SEQ),query('report',sequence=SEQ),query('metrics',case_id=LABEL,format=c.enum('json','markdown')),query('compare',cohort_id=c.ID),query('validate',request_json=TEXT),query('redaction_validate',request_json=TEXT),query('observability',case_id=c.ID,format=c.enum('otlp','prov'),redaction_json=TEXT),query('bundle_verify',files_json=TEXT)]},
 'cost_read':query('reconstruct',capsule_json=TEXT,run_id=c.ID,inbox_json=TEXT),
 'execution_read':{'type':'object','oneOf':[query('stored_result',action_id=c.ID,request_id=c.ID),query('describe',request_json=TEXT),query('verify',receipt_digest=c.DIGEST),query('verify_authorized',receipt_digest=c.DIGEST),query('evidence_verify',digest=c.DIGEST),query('receipt_verify',digest=c.DIGEST),query('evidence',digest=c.DIGEST,max_bytes={'type':'integer','minimum':1,'maximum':1048576})]},
}


def files(text,output):
    value=c.decode(text.encode());c.require(isinstance(value,dict) and 1<=len(value)<=32,'QUALITY_ARTIFACT_FILES')
    snapshot=output/'snapshot';snapshot.mkdir(mode=0o700)
    for name,data in value.items():
        resources.relative(name);c.require(isinstance(data,str),'QUALITY_ARTIFACT_TEXT');path=snapshot/name
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);records.save(path,data.encode())
    return str(snapshot)


def command(name,args,work,output):
    c.require(name in NAMES,'UNSUPPORTED_QUALITY_READ');c._validate(args,SCHEMAS[name]);op=args['operation']
    c.require(op!='stored_result','STORED_RESULT_HAS_NO_NATIVE_COMMAND')
    def save(filename,field):
        text=args[field];c.require(isinstance(c.decode(text.encode()),dict),'QUALITY_JSON_OBJECT');records.save(output/filename,text.encode());return str(output/filename)
    if name=='proof_read':
        if op=='render':return ['proof','render',work,save('request-native.json','request_json')]
        if op=='verify':return ['proof','verify',work,save('request-native.json','request_json'),save('pack.json','pack_json')]
        if op=='integrity':return ['proof','integrity',save('pack.json','pack_json'),args['manifest_sha256']]
        return ['proof','verify-dir',files(args['files_json'],output),args['manifest_sha256']]
    if name=='research_read':
        if op=='status':return ['research','status',work]
        if op in ('inspect','report'):return ['research',op,work,str(args['sequence'])]
        if op=='metrics':return ['research','metrics',work,*(['--case',args['case_id']] if args['case_id'] else []),'--format',args['format']]
        if op=='compare':return ['research','compare',work,args['cohort_id']]
        if op in ('validate','redaction_validate'):return ['research','validate' if op=='validate' else 'redaction-validate',save('request-native.json','request_json')]
        if op=='observability':return ['research','observability',work,'--case',args['case_id'],'--format',args['format'],'--redact',save('redaction.json','redaction_json')]
        return ['research','bundle-verify',files(args['files_json'],output)]
    if name=='cost_read':
        envelope={'schema':'golem.integration-native-action.v1','native_json':c.encoded({k:args[k] for k in ('capsule_json','run_id','inbox_json')}).decode(),'body':'','context_json':'','count_json':'','approval':None}
        return actions.command({'tool':'cost_inbox_reconcile'},None,None,envelope,output)
    if op=='describe':return ['approval','describe',work,save('request-native.json','request_json')]
    if op in ('verify','verify_authorized'):
        records.save(output/'request-native.json',c.encoded({'schema_version':1,'operation':'verify','receipt':args['receipt_digest']}))
        return ['execution','verify' if op=='verify' else 'verify-authorized',work,str(output/'request-native.json')]
    if op=='evidence':return ['evidence','read',work,args['digest'],str(args['max_bytes'])]
    return ['evidence','verify' if op=='evidence_verify' else 'verify-receipt',work,args['digest']]


def read(service,scope,name,args):
    import integration_parallel_reads as parallel
    c.require(name in (*NAMES,*parallel.NAMES),'UNSUPPORTED_QUALITY_READ')
    c._validate(args,(parallel.SCHEMAS if name in parallel.NAMES else SCHEMAS)[name])
    project=service._authorize(scope,args['work_id'],'record')
    if name=='execution_read' and args['operation']=='stored_result':
        c.require(getattr(service,'execution_result',None) is not None,'OWNER_EXECUTION_RESULT_REQUIRED')
        return service.execution_result({key:args[key] for key in ('project_id','work_id','action_id','request_id')})
    backend._quota(service.registry.root,3)
    before=service._read(scope,args['work_id'],'record')['result'];work=next(w for w in project['works'] if w['work_id']==args['work_id'])
    output=Path(tempfile.mkdtemp(prefix='read-m4-',dir=service.registry.root));records.save(output/'request.json',c.encoded(args))
    try:
        host_raw=parallel.host_read(service,scope,name,args) if name in parallel.NAMES else None
        if host_raw is None:
            argv=(parallel.command if name in parallel.NAMES else command)(name,args,work['path'],output)
            process=records.capture([project['cli']['path'],'--output-mode','full',*argv],output,backend.TIMEOUT_SECONDS,cwd=output,observe_source=False,env=backend.ENVIRONMENT,limit=c.MAX_NATIVE)
            c.require(type(process.get('returncode')) is int and process['returncode']==0 and process['reason']=='EXIT' and process['recording']=='RECORDED','NATIVE_FAILURE')
        else:records.save(output/'stdout.log',host_raw)
        raw=r.regular(output/'stdout.log',c.MAX_NATIVE,private=True);r.check_project(project)
        after=service._read(scope,args['work_id'],'record')['result'];c.require(c.encoded(before)==c.encoded(after),'OBSERVATION_STALE')
        markdown=name=='research_read' and (args['operation']=='report' or args.get('format')=='markdown')
        digest_output=name=='candidate_read' and args['operation'] in ('validate','host_validate','request_digest','gates')
        if digest_output and host_raw is None:
            value={'native_digest':raw.decode('ascii').strip(),
                'digest_role':'JSON_C_REQUEST_HASH_ONLY_NO_SCHEMA_VALIDATION' if args['operation']=='request_digest' else
                    'CHECKPOINT_GATES_DIGEST_NOT_APPROVAL' if args['operation']=='gates' else 'NATIVE_SCHEMA_VALIDATION_DIGEST_NOT_ACCEPTANCE'}
            c._validate(value['native_digest'],c.DIGEST)
        else:
            value=raw.decode('utf-8') if markdown else c.decode(raw,c.MAX_NATIVE)
        c.require(isinstance(value,(dict,list,str)),'NATIVE_RESPONSE')
        result={'view':name,'operation':args['operation'],'result':value,'native_stdout':{'encoding':'base64','data':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':c.sha(raw)},'work_record_sha256':c.sha(c.encoded(after)),
          'content_role':'UNTRUSTED_DATA','integrity_does_not_prove_truth':True,'current_native_acceptance_verified':False,'provider_authenticity_verified':False,'execution_authorized':False,
          'scheduler_implemented':False,'merge_authorized':False,'target_adoption_verified':False,'token_budget_verified':False,
          'accounting_scope':'DISPOSABLE_DECLARED_RUN_RECONSTRUCTION_NOT_LIVE_RUN_OR_PROVIDER_AUTHENTICATION' if name=='cost_read' else 'NOT_APPLICABLE'}
        backend._quota(service.registry.root,0);c.require(len(c.encoded(result))+2048<=service.transfer.value['max_result_bytes'],'RESULT_BUDGET_EXCEEDED')
        records.save(output/'delivery.json',c.encoded(result));return result
    except (c.IntegrationError,OSError,ValueError) as error:
        records.save(output/'failure.json',c.encoded({'code':getattr(error,'code','QUALITY_READ_INVALID'),'automatic_retry_allowed':False}));error.evidence_path=str(output);raise
