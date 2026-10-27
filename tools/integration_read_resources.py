"""Owner-selected M1 file resources, separate from existing D1/D2 approvals.

Only explicit absolute file names are read, through no-follow descriptors. The
model selects an ID, never a filesystem path. Snapshot hashes establish bytes,
not authenticity, content truth, current source completeness or execution rights.
"""
import os
from pathlib import Path
import stat
import tempfile
import integration_contract as c
import integration_registry as r
import integration_backend as backend
import execution_record as records

NAMES=('artifact_read','usage_read','revision_read','configuration_read','bundle_read','events_read')
MODULES=('integration_feature_profiles.py', 'integration_distribution_entry.py', 'integration_distribution.py', 'integration_owner_maintenance.py', 'integration_install.py', 'integration_config.py', 'integration_launch.py', 'integration_hook_contract.py', 'integration_hooks.py', 'integration_recovery.py', 'integration_update.py', 'integration_reload_probe.py', 'integration_mutation_contract.py', 'integration_mutations.py', 'integration_mutation_mcp.py', 'integration_lifecycle.py', 'integration_mcpb.py', 'integration_mcpb_entry.py', 'integration_parallel_hosts.py', 'integration_parallel_preparations.py', 'integration_parallel_reads.py', 'integration_parallel_actions.py', 'integration_quality_actions.py', 'integration_quality_reads.py', 'integration_helper_contract.py', 'usage_pipeline.py', 'integration_task_actions.py', 'integration_preparations.py', 'integration_prepare_builders.py', 'integration_read_resources.py', 'integration_read_views.py', 'agent_io.py', 'agent_lifecycle.py', 'provider_usage.py', 'provider_costs.py', 'billing_evidence.py', 'judgment_record.py', 'evidence_contract.py', 'evidence_adapters.py', 'evidence_export.py', 'revision_status.py', 'remote_status.py', 'github_checks.py', 'github_policy.py', 'github_context.py', 'status_collector.py', 'hosted_usage.py', 'context_resume.py', 'agent_entrypoint.py', 'instruction_bundle.py', 'integration_gateway_contract.py', 'verify_agent.py', 'verify_environment.py', 'verify_runtime.py')
MAX_FILE=1048576
MAX_TOTAL=8*1048576
FILE=c.obj({'file_id':c.ID,'name':{'type':'string','minLength':1,'maxLength':256},'path':c.PATH,'sha256':c.DIGEST,'tools':c.array(c.enum(*NAMES),len(NAMES))})
RESOURCE=c.obj({'resource_id':c.ID,'project_id':c.ID,'work_id':c.ID,'files':c.array(FILE,64)})
POLICY=c.obj({'schema':{'const':'golem.integration-read-resources.v1'},'transfer_policy_sha256':c.DIGEST,
 'data_class':{'const':'EXPLICIT_OWNER_SELECTED_READ_CONTENT'},'assurance':{'const':'LOCAL_COOPERATIVE'},
 'resources':c.array(RESOURCE,64),'producer':c.obj({name:c.DIGEST for name in MODULES})})
ARGS={'project_id':c.ID,'work_id':c.ID,'resource_id':c.ID}
OPTIONS={'type':'string','minLength':2,'maxLength':c.LIMIT}
SCHEMAS={
 'artifact_read':c.obj({**ARGS,'operation':c.enum('bytes','view','report','raw','record','procedure','measure','judgment','facts','lifecycle','export','provider_cost','conformance','declaration','review','research_outcome'),'options_json':OPTIONS}),
 'usage_read':c.obj({**ARGS,'operation':c.enum('totals','provider_cost','billing_view'),'options_json':OPTIONS}),
 'revision_read':c.obj({**ARGS,'operation':c.enum('relations','saved_status'),'options_json':OPTIONS}),
 'configuration_read':c.obj({**ARGS,'operation':c.enum('entrypoint','instruction_manifest','saved_plan','guide','schemas'),'options_json':OPTIONS}),
 'events_read':c.obj({**ARGS,'operation':c.enum('export'),'format':c.enum('jsonl','otlp','prov'),'after':{'type':'string','maxLength':512}}),
 'bundle_read':{'type':'object','oneOf':[
     c.obj({**ARGS,'operation':c.enum('lineage_verify'),'graph_digest':c.DIGEST}),
     c.obj({**ARGS,'operation':c.enum('lineage_trace'),'graph_digest':c.DIGEST,'sequence':{'type':'integer','minimum':1,'maximum':9007199254740991},'mode':c.enum('direct','transitive')}),
     c.obj({**ARGS,'operation':c.enum('cost')}),
     c.obj({**ARGS,'operation':c.enum('replay'),'mode':c.enum('partial','terminal')}),
     c.obj({**ARGS,'operation':c.enum('replay'),'mode':c.enum('partial','terminal'),'expected_head':c.DIGEST}),
     c.obj({**ARGS,'operation':c.enum('output'),'digest':c.DIGEST}),
     c.obj({**ARGS,'operation':c.enum('adapter')}),
 ]},
}


def producer():
    root=Path(__file__).resolve().parent
    return {name:c.sha(r.regular(root/name)) for name in MODULES}


def relative(name):
    c.require(name and not name.startswith('/') and '\\' not in name,'READ_RESOURCE_NAME')
    parts=name.split('/')
    c.require(len(parts)<=8,'READ_RESOURCE_NAME')
    c.require(all(p not in ('','.','..') and all(ch.isascii() and (ch.isalnum() or ch in '_.-') for ch in p) for p in parts),'READ_RESOURCE_NAME')
    return name


def pinned_bytes(path,digest):
    """Bounded no-follow traversal of the one owner-selected file; no discovery."""
    c._validate(digest,c.DIGEST)
    p=Path(path);c.require(p.is_absolute() and str(p)==path and '..' not in p.parts,'READ_RESOURCE_PATH')
    directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    fd=None
    try:
        for part in p.parts[1:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=child
        fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        before=os.fstat(fd)
        c.require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=MAX_FILE,'READ_RESOURCE_UNSAFE')
        raw=bytearray()
        while len(raw)<=MAX_FILE:
            chunk=os.read(fd,min(65536,MAX_FILE+1-len(raw)))
            if not chunk:break
            raw.extend(chunk)
        after=os.fstat(fd)
        stamp=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode)
        c.require(len(raw)<=MAX_FILE and len(raw)==after.st_size and stamp(before)==stamp(after),'READ_RESOURCE_CHANGED')
        data=bytes(raw);c.require(c.sha(data)==digest,'READ_RESOURCE_DIGEST');return data
    finally:
        if fd is not None:os.close(fd)
        os.close(directory)


class Resources:
    def __init__(self,path,reviewed_sha256,transfer,*,approve_resources=False):
        c.require(approve_resources is True,'OWNER_READ_RESOURCE_APPROVAL_REQUIRED')
        c._validate(reviewed_sha256,c.DIGEST)
        self.path=r.real_path(str(path));self.digest=reviewed_sha256;self.transfer=transfer
        self.current()
    def current(self):
        raw=r.regular(self.path,private=True);c.require(c.sha(raw)==self.digest,'READ_RESOURCE_POLICY_CHANGED')
        value=c.decode(raw);c._validate(value,POLICY)
        c.require(value['transfer_policy_sha256']==self.transfer.digest,'READ_RESOURCE_TRANSFER_BINDING')
        c.require(value['producer']==producer(),'READ_RESOURCE_PRODUCER_CHANGED')
        validate_structure(value)
        return value
    def permitted(self,project_id,work_id,tool):
        return any(v['project_id']==project_id and v['work_id']==work_id and any(tool in f['tools'] for f in v['files']) for v in self.current()['resources'])
    def catalog(self,project_id,work_id,tools):
        result=[]
        for resource in self.current()['resources']:
            if (resource['project_id'],resource['work_id'])!=(project_id,work_id):continue
            selected=[f for f in resource['files'] if set(f['tools']) & set(tools)]
            if selected:result.append({'resource_id':resource['resource_id'],'files':[{'file_id':f['file_id'],'name':f['name'],'sha256':f['sha256'],'tools':[t for t in f['tools'] if t in tools]} for f in selected]})
        return result
    def select(self,project_id,work_id,tool,resource_id):
        found=[v for v in self.current()['resources'] if (v['project_id'],v['work_id'],v['resource_id'])==(project_id,work_id,resource_id)]
        c.require(len(found)==1,'READ_RESOURCE_SCOPE')
        selected=[f for f in found[0]['files'] if tool in f['tools']]
        c.require(bool(selected),'READ_RESOURCE_SCOPE');return selected


def read(service,scope,name,args):
    from integration_read_views import view
    c.require(name in NAMES,'UNSUPPORTED_READ_TOOL');c._validate(args,SCHEMAS[name])
    c.require(service.resources is not None,'READ_RESOURCE_POLICY_REQUIRED')
    project=service._authorize(scope,args['work_id'],'record')
    c.require(not service.resources.path.is_relative_to(Path(project['root'])),'READ_RESOURCE_POLICY_SCOPE')
    selected=service.resources.select(args['project_id'],args['work_id'],name,args['resource_id'])
    capacity=backend._quota(service.registry.root,1)
    payloads=[];size=0
    for f in selected:
        data=pinned_bytes(f['path'],f['sha256']);size+=len(data);c.require(size<=MAX_TOTAL,'READ_RESOURCE_TOTAL_LIMIT');payloads.append((f,data))
    needed_entries=(16 if name in ('bundle_read','events_read') else 6)+sum(len(f['name'].split('/')) for f in selected)
    needed_bytes=size+service.transfer.value['max_result_bytes']+c.LIMIT+(2*c.MAX_NATIVE if name in ('bundle_read','events_read') else 0)
    c.require(capacity['remaining']['bytes']>=needed_bytes and capacity['remaining']['entries']>=needed_entries,'AUDIT_QUOTA')
    output=Path(tempfile.mkdtemp(prefix='read-resource-',dir=service.registry.root))
    records.save(output/'request.json',c.encoded(args))
    try:
        snapshot=output/'snapshot';snapshot.mkdir(mode=0o700)
        total=0;pins=[]
        for f,data in payloads:
            total+=len(data)
            dest=snapshot/relative(f['name']);dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True);records.save(dest,data)
            pins.append({'file_id':f['file_id'],'name':f['name'],'sha256':f['sha256'],'bytes':len(data)})
        options=c.decode(args['options_json'].encode()) if 'options_json' in args else {};c.require(isinstance(options,dict),'READ_RESOURCE_OPTIONS')
        if name=='artifact_read' and args['operation']=='bytes':
            c._validate(options,c.obj({'file_id':c.ID,'offset':c.INTEGER,'max_bytes':{'type':'integer','minimum':1,'maximum':65536}}))
            matches=[(f,data) for f,data in payloads if f['file_id']==options['file_id']];c.require(len(matches)==1,'READ_RESOURCE_FILE_SCOPE')
            f,data=matches[0];start=options['offset'];c.require(start<=len(data),'READ_RESOURCE_WINDOW');window=data[start:start+options['max_bytes']]
            import base64
            result={'file_id':f['file_id'],'sha256':f['sha256'],'offset':start,'bytes':len(window),'data_base64':base64.b64encode(window).decode(),
                'next_offset':min(start+len(window),len(data)),'eof':start+len(window)>=len(data),'source_bytes':len(data)}
        elif name in ('bundle_read','events_read'):
            result=bundle_read(project,args,snapshot,output)
        else:
            result=view(name,args['operation'],snapshot,options,{'project_id':args['project_id'],'work_id':args['work_id']})
        result=logical_paths(result,snapshot,args['resource_id'])
        # No stored provenance is followed. Re-read only the same finite approved
        # files to reject drift while the snapshot view was being calculated.
        for f in selected:pinned_bytes(f['path'],f['sha256'])
        service.resources.select(args['project_id'],args['work_id'],name,args['resource_id']);r.check_project(project)
        backend._quota(service.registry.root,0)
        value={'view':name,'operation':args['operation'],'resource_id':args['resource_id'],'files':pins,
            'result':result,'content_role':'UNTRUSTED_DATA','integrity_scope':'EXPLICIT_FILE_BYTES_ONLY',
            'authenticity_verified':False,'live_native_acceptance_verified':False,'source_completeness_verified':False}
        c.require(len(c.encoded(value))+2048<=service.transfer.value['max_result_bytes'],'RESULT_BUDGET_EXCEEDED')
        records.save(output/'delivery.json',c.encoded(value));return value
    except (c.IntegrationError,OSError,ValueError,KeyError,TypeError) as error:
        records.save(output/'failure.json',c.encoded({'code':getattr(error,'code','READ_RESOURCE_INVALID'),'automatic_retry_allowed':False}))
        failure=error if isinstance(error,(c.IntegrationError,OSError,ValueError)) else c.IntegrationError('READ_RESOURCE_INVALID')
        failure.evidence_path=str(output)
        if failure is not error:raise failure from error
        raise


def bundle_read(project,args,snapshot,output):
    import base64
    op=args['operation']
    if op=='export':
        c.require(not args['after'] or all(ch in '0123456789abcdefABCDEF:.-_' for ch in args['after']),'EVENT_CURSOR')
        argv=['events',str(snapshot),'--'+args['format'],*(['--after',args['after']] if args['after'] else [])]
    elif op=='lineage_verify':argv=['lineage','verify',str(snapshot/'cas'),args['graph_digest']]
    elif op=='lineage_trace':argv=['lineage','trace',str(snapshot/'cas'),args['graph_digest'],str(args['sequence']),*(['--direct'] if args['mode']=='direct' else [])]
    elif op=='cost':argv=['cost','report',str(snapshot)]
    elif op=='replay':argv=['replay',str(snapshot),*(['--require-terminal'] if args['mode']=='terminal' else []),*(['--expect-chain',args['expected_head']] if 'expected_head' in args else [])]
    elif op=='output':argv=['--output-store',str(snapshot/'cas'),'output','read',args['digest']]
    elif op=='adapter':argv=['adapter','describe',str(snapshot/'descriptor.json')]
    else:raise c.IntegrationError('UNSUPPORTED_READ_OPERATION')
    process=records.capture([project['cli']['path'],'--output-mode','full',*argv],output,backend.TIMEOUT_SECONDS,
        cwd=output,observe_source=False,env=backend.ENVIRONMENT,limit=c.MAX_NATIVE)
    c.require(type(process.get('returncode')) is int and process['returncode']==0 and process['reason']=='EXIT' and process['recording']=='RECORDED','NATIVE_FAILURE')
    raw=r.regular(output/'stdout.log',c.MAX_NATIVE,private=True)
    result={'native_stdout':{'data_base64':base64.b64encode(raw).decode(),'sha256':c.sha(raw),'bytes':len(raw)},'interpretation':'PINNED_ARTIFACT_READ_NOT_CURRENT_WORK_ACCEPTANCE'}
    if op=='export' and args['format']=='jsonl':result['value']=[c.decode(line,c.MAX_NATIVE) for line in raw.splitlines() if line.strip()]
    elif op!='output':result['value']=c.decode(raw,c.MAX_NATIVE)
    return result


def logical_paths(value,snapshot,resource_id):
    """Replace only derived staging pointers; pinned source bytes stay unchanged."""
    if isinstance(value,str) and (value==str(snapshot) or value.startswith(str(snapshot)+'/')):
        return 'resource:'+resource_id+value[len(str(snapshot)):]
    if isinstance(value,dict):return {k:logical_paths(v,snapshot,resource_id) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [logical_paths(v,snapshot,resource_id) for v in value]
    return value


def validate_structure(value):
    c.bounded(value);c._validate(value,POLICY)
    seen=set()
    for resource in value['resources']:
        key=resource['project_id'],resource['work_id'],resource['resource_id'];c.require(key not in seen,'READ_RESOURCE_DUPLICATE');seen.add(key)
        for field in ('file_id','name','path'):c.require(len({f[field] for f in resource['files']})==len(resource['files']),'READ_RESOURCE_DUPLICATE')
        for f in resource['files']:
            relative(f['name'])
            path=Path(f['path']);c.require(path.is_absolute() and str(path)==f['path'] and '..' not in path.parts,'READ_RESOURCE_PATH')


def owner_plan(value):
    """Fill code pins only. Never read selected resources or activate a policy."""
    import copy
    result=copy.deepcopy(value);result['producer']=producer();validate_structure(result)
    return {'policy':result,'policy_sha256':c.sha(c.encoded(result)),
            'state':'OWNER_REVIEW_REQUIRED','resources_read':False,'approval_created':False}

def main(argv=None):
    import argparse
    import sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('schema','plan'));parser.add_argument('--input',type=Path)
    args=parser.parse_args(argv)
    if args.operation=='schema':value={'$schema':'https://json-schema.org/draft/2020-12/schema',**POLICY}
    else:
        c.require(args.input is not None,'INPUT_REQUIRED');value=owner_plan(c.decode(r.regular(args.input,private=True)))
    sys.stdout.buffer.write(c.encoded(value));return 0

if __name__=='__main__':raise SystemExit(main())
