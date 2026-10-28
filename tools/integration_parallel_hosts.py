"""Optional owner-selected native candidate host bindings; launch checks do not start a server.

Same-UID/config/socket observations are cooperative identity, not authenticated
human/process identity. Native reducers own locks, admission, fences and CAS.
"""
import argparse
from pathlib import Path
import os
import stat
import sys
import tempfile
import integration_contract as c
import integration_registry as r
import integration_backend as backend
import integration_parallel_actions as actions
import execution_record as records

READ_OPS=('compare','review-check','target-check')
OPS=(*actions.CANDIDATE_OPS,*actions.WORKSPACE_OPS,'compare','review-check','target-check')
TERMINAL=('settle','workspace-seal','workspace-retain','workspace-remove')
SOCKET=c.obj({'path':c.PATH,'identity':c.IDENTITY})
ROOT=c.obj({'path':c.PATH,'identity':c.IDENTITY})
ACTION=c.obj({'action_id':c.ID,'action_sha256':c.DIGEST,'request_digest':c.DIGEST,
              'termination':{**c.PIN,'type':['object','null']}})
QUERY=c.obj({'query_id':c.ID,'operation':c.enum(*READ_OPS),'request':c.PIN,'request_digest':c.DIGEST})
HOST=c.obj({'host_id':c.ID,'project_id':c.ID,'parent_work_id':c.ID,'config':c.PIN,
    'config_digest':c.DIGEST,'socket':SOCKET,'work_ids':c.array(c.ID,16),
    'roots':c.array(ROOT,3),'operations':c.array(c.enum(*OPS),len(OPS)),
    'actions':c.array(ACTION,32,0),'queries':c.array(QUERY,32,0)})
POLICY=c.obj({'schema':{'const':'golem.integration-parallel-hosts.v1'},
    'mutation_policy_sha256':c.DIGEST,'transfer_policy_sha256':c.DIGEST,'hosts':c.array(HOST,16),
    'producer':c.obj({name:c.DIGEST for name in ('integration_parallel_hosts.py','integration_parallel_actions.py','integration_parallel_reads.py')})})
ATTESTATION=c.obj({'schema':{'const':'golem.integration-operator-termination.v1'},
    'host_id':c.ID,'config_digest':c.DIGEST,'action_sha256':c.DIGEST,'request_digest':c.DIGEST,
    'all_workers_stopped':{'const':True},'trust':{'const':'OPERATOR_ATTESTED_NOT_PROCESS_REAPING_OBSERVATION'}})


def producer():
    return {name:c.sha(r.regular(Path(__file__).parent/name)) for name in POLICY['properties']['producer']['properties']}


class Hosts:
    def __init__(self,path,digest,policy,*,approve_hosts=False):
        c.require(approve_hosts is True,'OWNER_PARALLEL_HOST_APPROVAL_REQUIRED')
        self.path=r.real_path(str(path));c._validate(digest,c.DIGEST)
        self.digest=digest;self.policy=policy
        self.value=self.current()

    def current(self):
        self.policy.current()
        raw=r.regular(self.path,private=True)
        c.require(c.sha(raw)==self.digest,'PARALLEL_HOST_POLICY_CHANGED')
        value=c.decode(raw);c._validate(value,POLICY)
        c.require(value['mutation_policy_sha256']==self.policy.digest and
            value['transfer_policy_sha256']==self.policy.transfer.digest,'PARALLEL_HOST_POLICY_BINDING')
        c.require(value['producer']==producer(),'PRODUCER_CHANGED')
        c.require(len({row['host_id'] for row in value['hosts']})==len(value['hosts']) and
            len({(row['project_id'],row['parent_work_id']) for row in value['hosts']})==len(value['hosts']) and
            len({row['project_id'] for row in value['hosts']})==len(value['hosts']), 'DUPLICATE_HOST')
        return value

    def parent(self,project_id,work_id):
        return next((row for row in self.current()['hosts'] if
            (row['project_id'],row['parent_work_id'])==(project_id,work_id)),None)

    def check(self,row,*,launching=False,stop_owned=False):
        c.require(row in self.current()['hosts'],'PARALLEL_HOST_SCOPE')
        scope=self.policy.transfer.scope(row['project_id'],row['parent_work_id'],'work_inspect')
        project=None
        for work_id in row['work_ids']:
            self.policy.transfer.scope(row['project_id'],work_id,'work_inspect')
            for operation in ('record','status','next'):
                project=self.policy.registry.authorize(scope['binding'],work_id,operation)
        c.require(row['parent_work_id'] in row['work_ids'],'PARALLEL_HOST_PARENT_SCOPE')
        raw=r.regular(Path(row['config']['path']),private=True)
        c.require(c.sha(raw)==row['config']['sha256'],'PARALLEL_HOST_CONFIG_CHANGED')
        cfg=c.decode(raw);c.require(isinstance(cfg,dict),'PARALLEL_HOST_CONFIG')
        # These are equality/scope bindings, not a second native config parser.
        works={w['path']:w['work_id'] for w in project['works']}
        parent=next(w for w in project['works'] if w['work_id']==row['parent_work_id'])
        bindings=cfg.get('bindings');target=cfg.get('target')
        c.require(cfg.get('parent')==parent['path'] and cfg.get('repository_root')==project['root'] and
            isinstance(bindings,list) and bindings and all(isinstance(b,dict) for b in bindings),'PARALLEL_HOST_CONFIG_SCOPE')
        paths=[cfg['parent'],*[b.get('work') for b in bindings]]
        if target is not None:
            c.require(isinstance(target,dict),'PARALLEL_HOST_CONFIG_SCOPE');paths.append(target.get('work'))
        c.require(all(path in works for path in paths) and len(set(paths))==len(paths) and
            {works[path] for path in paths}==set(row['work_ids']),'PARALLEL_HOST_WORK_SCOPE')
        root=Path(project['root']);runtime=Path(project['runtime_root'])
        for pin in (self.path,Path(row['config']['path'])):
            c.require(not pin.is_relative_to(root),'PARALLEL_HOST_OWNER_SCOPE')
        expected={cfg.get('repository_root'),cfg.get('worktree_root'),cfg.get('admission')}
        c.require({item['path'] for item in row['roots']}==expected and len(expected)==3,'PARALLEL_HOST_ROOT_SCOPE')
        for item in row['roots']:
            path=r.real_path(item['path'])
            c.require(r.identity(path)==item['identity'],'PARALLEL_HOST_ROOT_CHANGED')
            c.require(path==root or path!=runtime and path.is_relative_to(runtime),'PARALLEL_HOST_ROOT_SCOPE')
        for binding in bindings:
            for key in ('tree','build','temp'):
                path=Path(binding.get(key,''))
                c.require(path.is_absolute() and '..' not in path.parts and path.is_relative_to(runtime) and path!=runtime,'PARALLEL_HOST_PATH_SCOPE')
                c.require(all(not part.is_symlink() for part in (path,*path.parents)),'SYMLINK')
                ancestor=path
                while not ancestor.exists():ancestor=ancestor.parent
                r.real_path(str(ancestor))
        if target is not None:
            c.require(Path(target.get('tree',''))==root,'PARALLEL_HOST_TARGET_SCOPE')
        sock=Path(row['socket']['path']);r.real_path(str(sock.parent));directory=sock.parent.stat()
        c.require(directory.st_uid==os.getuid() and directory.st_mode&0o077==0,'PARALLEL_HOST_SOCKET_OWNER_SCOPE')
        c.require(not sock.is_relative_to(root),'PARALLEL_HOST_SOCKET_OWNER_SCOPE')
        if launching:
            c.require(not sock.exists() and not sock.is_symlink(),'PARALLEL_HOST_SOCKET_EXISTS')
        elif not stop_owned:
            r.real_path(str(sock));info=sock.lstat()
            c.require(stat.S_ISSOCK(info.st_mode) and info.st_uid==os.getuid() and info.st_mode&0o077==0 and
                {'device':info.st_dev,'inode':info.st_ino}==row['socket']['identity'],'PARALLEL_HOST_SOCKET_CHANGED')
        return project,cfg

    def basis(self,project_id,work_id):
        row=self.parent(project_id,work_id)
        if row is None:return None
        self.check(row)
        return {'policy_sha256':self.digest,'host_id':row['host_id'],'config_sha256':row['config']['sha256'],
                'config_digest':row['config_digest'],'socket_identity':row['socket']['identity']}

    def select(self,entry,envelope):
        value=actions.shape(entry,envelope)
        row=next((row for row in self.current()['hosts'] if row['host_id']==value['host_id']),None)
        c.require(row is not None and (row['project_id'],row['parent_work_id'])==
            (entry['project_id'],entry['work_id']),'PARALLEL_HOST_ACTION_SCOPE')
        project,cfg=self.check(row)
        matches=[a for a in row['actions'] if a['action_id']==entry['action_id']]
        c.require(len(matches)==1 and matches[0]['action_sha256']==entry['action']['sha256'],'PARALLEL_HOST_ACTION_PIN')
        selected=matches[0];request=c.decode(value['request_json'].encode());op=request['operation']
        c.require(op in row['operations'],'PARALLEL_HOST_OPERATION_SCOPE')
        if op in TERMINAL:
            c.require(selected['termination'] is not None,'OPERATOR_TERMINATION_ATTESTATION_REQUIRED')
            pin=selected['termination'];path=Path(pin['path'])
            c.require(not path.is_relative_to(Path(project['root'])),'PARALLEL_HOST_OWNER_SCOPE')
            raw=r.regular(path,private=True);c.require(c.sha(raw)==pin['sha256'],'TERMINATION_ATTESTATION_CHANGED')
            attested=c.decode(raw);c._validate(attested,ATTESTATION)
            c.require((attested['host_id'],attested['config_digest'],attested['action_sha256'],attested['request_digest'])==
                (row['host_id'],row['config_digest'],entry['action']['sha256'],selected['request_digest']),'TERMINATION_ATTESTATION_SCOPE')
        else:c.require(selected['termination'] is None,'UNEXPECTED_TERMINATION_ATTESTATION')
        return row,selected,project

    def _capture(self,row,request,*,approval=None,termination=False,digest=False):
        project,cfg=self.check(row);backend._quota(self.policy.registry.root,1)
        output=Path(tempfile.mkdtemp(prefix='read-m5-host-',dir=self.policy.registry.root))
        path=output/'request.json';records.save(path,request)
        argv=[project['cli']['path'],'--output-mode','full','candidate',
            *(['host-validate',str(path)] if digest else ['call',row['socket']['path'],str(path)])]
        if approval is not None:argv+=['--approve-request',approval]
        if termination:argv+=['--attest-termination',approval]
        process=records.capture(argv,output,backend.TIMEOUT_SECONDS,cwd=output,observe_source=False,env=backend.ENVIRONMENT,limit=c.MAX_NATIVE)
        c.require(process.get('returncode')==0 and process.get('reason')=='EXIT' and process.get('recording')=='RECORDED','PARALLEL_HOST_NATIVE_FAILURE')
        raw=r.regular(output/'stdout.log',c.MAX_NATIVE,private=True);self.check(row)
        records.save(output/'observation.json',c.encoded({'stdout_sha256':c.sha(raw),'execution_authorized':False}))
        backend._quota(self.policy.registry.root,0)
        return raw

    def probe(self,row):
        raw=self._capture(row,r.regular(Path(row['config']['path']),private=True),digest=True)
        c.require(raw in (row['config_digest'].encode(),(row['config_digest']+'\n').encode()),'PARALLEL_HOST_NATIVE_CONFIG_DIGEST')
        info=c.decode(self._capture(row,c.encoded({'operation':'host-info'})),c.MAX_NATIVE)
        cfg=c.decode(r.regular(Path(row['config']['path']),private=True))
        c.require(info=={'config_digest':row['config_digest'],'parent_work_id':row['parent_work_id'],
            'repository_id':cfg['repository_id']},'PARALLEL_HOST_SERVER_CONFIG_CHANGED')

    def read(self,scope,work_id,operation):
        c.require(operation in ('record','status','next'),'PARALLEL_HOST_READ_SCOPE')
        row=self.parent(scope['binding']['project_id'],work_id)
        c.require(row is not None,'PARALLEL_HOST_SCOPE');self.probe(row)
        result=c.decode(self._capture(row,c.encoded({'operation':'work-'+operation})),c.MAX_NATIVE)
        c.require(isinstance(result,dict) and result.get('execution_authorized') in (None,False),'PARALLEL_HOST_READ_CONTRACT')
        if operation=='record':c.require(result.get('schema')=='golem.work-record.v1' and result.get('work_id')==work_id and result.get('work_specification',{}).get('work_id')==work_id,'WORK_IDENTITY')
        return {'result':result,'observations_atomic':False,'native_state_changed':False}

    def command(self,entry,envelope,output):
        row,selected,_=self.select(entry,envelope)
        request=actions.shape(entry,envelope)
        path=output/'host-request.json';records.save(path,request['request_json'].encode())
        return ['candidate','call',row['socket']['path'],str(path),'--approve-request',selected['request_digest'],
            *(['--attest-termination',selected['request_digest']] if selected['termination'] else [])]

    def query(self,project_id,work_id,operation,query_id):
        row=self.parent(project_id,work_id);c.require(row is not None,'OWNER_PARALLEL_HOST_REQUIRED')
        c.require(operation in READ_OPS and operation in row['operations'],'PARALLEL_HOST_QUERY_SCOPE')
        matches=[q for q in row['queries'] if q['query_id']==query_id and q['operation']==operation]
        c.require(len(matches)==1,'PARALLEL_HOST_QUERY_SCOPE');query=matches[0]
        project,_=self.check(row);pin=query['request'];path=Path(pin['path'])
        c.require(not path.is_relative_to(Path(project['root'])),'PARALLEL_HOST_OWNER_SCOPE')
        raw=r.regular(path,private=True);c.require(c.sha(raw)==pin['sha256'],'PARALLEL_HOST_QUERY_CHANGED')
        request=c.decode(raw);c.require(isinstance(request,dict) and request.get('operation')==operation,'PARALLEL_HOST_QUERY_SCOPE')
        self.probe(row)
        result=self._capture(row,raw,approval=query['request_digest'])
        self.probe(row)
        return result


def owner_cli():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=('schema','plan'))
    parser.add_argument('--input',type=Path);args=parser.parse_args()
    if args.operation=='schema':value=POLICY
    else:
        c.require(args.input is not None,'INPUT_REQUIRED');value=c.decode(r.regular(args.input,private=True))
        value['producer']=producer();c._validate(value,POLICY)
    sys.stdout.buffer.write(c.encoded(value))


if __name__=='__main__':
    owner_cli()
