"""QC6 finite transport. Native QC4/QC5 own semantics; no UI or approval issuance."""
from pathlib import Path
import os
import select
import subprocess
import tempfile
import time
import integration_contract as c
import integration_registry as r
import integration_backend as backend
import intent_authority as authority
import intent_bootstrap as bootstrap
import execution_record as records

ACTIONS=('intent_qa_accept','intent_completion_finalize')
READ='intent_read'
READ_SCHEMA=c.obj({'project_id':c.ID,'work_id':c.ID,'query_id':c.ID})
BINDING=c.obj({'binding_id':c.ID,'project_id':c.ID,'work_id':c.ID,
    'operation':c.enum('assess','current','resume','enrollment-inspect','accept','finalize'),
    'action_id':{'type':'string','maxLength':64},'action_sha256':c.DIGEST,
    'packet':c.PIN,'review_root':c.obj({'path':c.PATH,'identity':c.IDENTITY})})
POLICY=c.obj({'schema':{'const':'golem.integration-intent-host.v1'},
    'transfer_policy_sha256':c.DIGEST,'mutation_policy_sha256':c.DIGEST,
    'registration_sha256':c.DIGEST,'repository':c.PATH,'git':c.PIN,'bridge':c.PIN,
    'bindings':c.array(BINDING,32),
    'producer':c.obj({'integration_intent.py':c.DIGEST})})

def shape(entry,envelope):
    c.require(entry['tool'] in ACTIONS,'INTENT_ACTION_TOOL')
    c.require(not envelope['body'] and not envelope['context_json'] and not envelope['count_json'] and envelope['approval'] is None,'INTENT_ENVELOPE_SCOPE')
    value=c.decode(envelope['native_json'].encode());c._validate(value,c.obj({'binding_id':c.ID}));return value

def draft(args,observed,key):
    value=c.decode(args['fields_json'].encode());c.require(isinstance(value,dict) and set(value)<= {'binding_id'},'INTENT_DRAFT_FIELDS')
    envelope={'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),'body':args['body'],'context_json':args['context_json'],'count_json':args['count_json'],'approval':None}
    entry={k:args[k] for k in ('tool','project_id','work_id','session_id','native_binding_id')}
    missing=[] if 'binding_id' in value else ['binding_id']
    if not missing:shape(entry,envelope)
    return envelope,value,entry,missing,{'binding_id':'UNAPPROVED_OWNER_HOST_REFERENCE'}

class Hosts:
    def __init__(self,path,digest,policy,*,approve_intent=False):
        c.require(approve_intent is True,'OWNER_INTENT_HOST_REQUIRED')
        self.path=r.real_path(str(path));self.digest=digest;self.policy=policy
        c._validate(digest,c.DIGEST);self.current()
    def current(self):
        self.policy.current();raw=r.regular(self.path,private=True)
        c.require(c.sha(raw)==self.digest,'INTENT_POLICY_CHANGED');value=c.decode(raw);c._validate(value,POLICY)
        c.require(value['mutation_policy_sha256']==self.policy.digest and value['transfer_policy_sha256']==self.policy.transfer.digest,'INTENT_POLICY_BINDING')
        c.require(value['producer']=={'integration_intent.py':c.sha(r.regular(Path(__file__)))},'PRODUCER_CHANGED')
        c.require(len({b['binding_id'] for b in value['bindings']})==len(value['bindings']),'DUPLICATE_INTENT_BINDING')
        for key in ('git','bridge'):c.require(r.file_pin(Path(value[key]['path']))==value[key],'INTENT_PROGRAM_CHANGED')
        return value
    def permitted(self,project,work):
        return any((b['project_id'],b['work_id'])==(project,work) and b['operation'] in ('assess','current','resume','enrollment-inspect') for b in self.current()['bindings'])
    def binding(self,binding_id,project,work):
        cfg=self.current();row=next((b for b in cfg['bindings'] if b['binding_id']==binding_id),None)
        c.require(row is not None and (row['project_id'],row['work_id'])==(project,work),'INTENT_SCOPE')
        scope=self.policy.transfer.scope(project,work,'work_inspect')
        registered=self.policy.registry.authorize(scope['binding'],work,'record')
        c.require(registered['root']==cfg['repository'],'INTENT_REPOSITORY_SCOPE')
        workpath=next(w['path'] for w in registered['works'] if w['work_id']==work)
        raw=r.regular(Path(row['packet']['path']),c.LIMIT,private=True)
        c.require(c.sha(raw)==row['packet']['sha256'],'INTENT_PACKET_CHANGED');packet=c.decode(raw)
        packet_fields={'schema':{'const':'golem.intent-product-host.v1'},'work':c.PATH,'operation':c.enum('assess','current','resume','accept','finalize')}
        packet_fields.update({key:{'type':'string','maxLength':c.LIMIT} for key in ('policy','bundle','control','material','request','policy_name','bundle_name')})
        packet_fields.update(policy_sha256=c.DIGEST,bundle_sha256=c.DIGEST)
        if row['operation']=='enrollment-inspect':
            c._validate(packet,bootstrap.PACKET)
            c.require(packet['operation']=='enrollment-inspect' and row['action_id']=='' and
                      row['action_sha256']=='0'*64 and packet['approval']=='0'*64 and
                      packet['enrollment']=='','INTENT_INSPECTION_ONLY')
        else:
            c._validate(packet,c.obj(packet_fields))
        c.require(packet.get('work')==workpath and packet.get('operation')==row['operation'],'INTENT_PACKET_SCOPE')
        root=r.real_path(row['review_root']['path']);c.require(r.identity(root)==row['review_root']['identity'],'INTENT_REVIEW_ROOT_CHANGED')
        for field in ('policy','bundle'):
            name=packet[field+'_name'];c.require(isinstance(name,str) and name not in ('','.','..') and '/' not in name,'INTENT_FILE_NAME')
            selected=r.regular(root/name,private=True)
            c.require(c.sha(selected)==packet[field+'_sha256'] and selected==packet[field].encode(),'INTENT_REVIEW_PIN_CHANGED')
        return cfg,row,raw
    def select(self,entry,envelope):
        value=shape(entry,envelope);cfg,row,raw=self.binding(value['binding_id'],entry['project_id'],entry['work_id'])
        expected='accept' if entry['tool']=='intent_qa_accept' else 'finalize'
        c.require(row['operation']==expected and row['action_id']==entry['action_id'] and row['action_sha256']==entry['action']['sha256'],'INTENT_EXACT_ACTION')
        return cfg,row,raw
    def capture(self,entry,envelope,output):
        cfg,row,raw=self.select(entry,envelope)
        return self._capture(cfg,row,raw,output)
    def _capture(self,cfg,row,raw,output):
        result={'returncode':None,'reason':'UNKNOWN','recording':'RECORDED'};stdout=bytearray();stderr=bytearray()
        try:
            with authority.authorized_root(cfg['repository'],cfg['registration_sha256'],git=Path(cfg['git']['path'])) as (fd,record):
                c.require(cfg['bridge'] in record['authority']['pins'],'INTENT_REGISTERED_BRIDGE_REQUIRED')
                reviewfd=os.open(row['review_root']['path'],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                try:
                    info=os.fstat(reviewfd);c.require({'device':info.st_dev,'inode':info.st_ino}==row['review_root']['identity'] and info.st_uid==os.getuid() and not info.st_mode&0o077,'INTENT_REVIEW_ROOT_CHANGED')
                    def exchange(process,deadline):
                        # Drain both streams while sending the bounded packet: a
                        # full stderr pipe must not deadlock a large request.
                        streams={process.stdout.fileno():stdout,process.stderr.fileno():stderr}
                        pending=memoryview(raw);input_fd=process.stdin.fileno()
                        os.set_blocking(input_fd,False)
                        for pipe in streams:os.set_blocking(pipe,False)
                        while streams or pending:
                            remaining=deadline-time.monotonic();c.require(remaining>0,'INTENT_TIMEOUT')
                            ready,writable,_=select.select(list(streams),[input_fd] if pending else [],[],remaining)
                            if writable:
                                pending=pending[os.write(input_fd,pending[:65536]):]
                                if not pending:process.stdin.close()
                            for pipe in ready:
                                chunk=os.read(pipe,65536)
                                if not chunk:del streams[pipe];continue
                                c.require(len(streams[pipe])+len(chunk)<=c.LIMIT,'INTENT_OUTPUT_LIMIT');streams[pipe].extend(chunk)
                        process.wait(timeout=max(.01,deadline-time.monotonic()))
                        result.update(returncode=process.returncode,reason='EXIT')
                    argv=[cfg['bridge']['path'],'--product-fd',str(fd),cfg['registration_sha256'],str(reviewfd)]
                    if row.get('operation')=='enrollment-inspect':
                        argv=[cfg['bridge']['path'],'--bootstrap-fd',str(fd),cfg['registration_sha256'],str(reviewfd),c.sha(raw)]
                    records.run_private(
                        argv,
                        destination=output/'process',timeout=30,env=backend.ENVIRONMENT,
                        source=Path(cfg['repository']),protocol=exchange,protocol_stderr=True,pass_fds=(fd,reviewfd))
                finally:
                    os.close(reviewfd)
            c.require(self.binding(row['binding_id'],row['project_id'],row['work_id'])==(cfg,row,raw),'INTENT_POSTCHECK_CHANGED')
            return result
        except subprocess.TimeoutExpired:
            raise c.IntegrationError('INTENT_TIMEOUT') from None
        finally:
            records.save(output/'stdout.log',bytes(stdout));records.save(output/'stderr.log',bytes(stderr))
            records.save(output/'intent-capture.json',c.encoded(result))
    def read(self,service,scope,args):
        service._authorize(scope,args['work_id'],'record')
        cfg,row,raw=self.binding(args['query_id'],args['project_id'],args['work_id'])
        c.require(row['operation'] in ('assess','current','resume','enrollment-inspect') and row['action_id']=='','INTENT_READ_ONLY')
        backend._quota(service.registry.root,1)
        output=Path(tempfile.mkdtemp(prefix='read-intent-',dir=service.registry.root))
        process=self._capture(cfg,row,raw,output)
        c.require(process['returncode']==0 and process['reason']=='EXIT','INTENT_NATIVE_FAILURE')
        native=r.regular(output/'stdout.log',c.LIMIT,private=True)
        result={'native':c.decode(native),'native_sha256':c.sha(native),'native_utf8':native.decode(),'view':'intent_read',
                'interpretation':'NATIVE_RESULT_ONLY','historical_result':False,'execution_authorized':False,'automatic_retry_allowed':False}
        c.require(len(c.encoded(result))+2048<=service.transfer.value['max_result_bytes'],'RESULT_BUDGET_EXCEEDED')
        records.save(output/'delivery.json',c.encoded(result));return result
