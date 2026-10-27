"""Optional M4 owner helper effects, separate from D2 and native QA approval.

Exact owner argv is never supplied by an MCP caller. This is a cooperative local
host contract, not an OS/network sandbox or an authenticated provider assertion.
"""
import os
import copy
from pathlib import Path
import integration_contract as c
import integration_registry as r
import integration_backend as backend
import integration_read_resources as resources
import execution_record as records

HELPERS={
 'agent_io':('agent_io.py',('observe','observe-history','procedure','judgment-write','run')),
 'agent_lifecycle':('agent_lifecycle.py',('run',)),
 'billing_evidence':('billing_evidence.py',('reconcile','native-export')),
 'evidence_export':('evidence_export.py',('create','prepare-raw')),
 'hosted_usage':('hosted_usage.py',('ingest','listen')),
 'provider_costs':('provider_costs.py',('fetch','ingest')),
 'status_collector':('status_collector.py',('collect',)),
 'usage_pipeline':('usage_pipeline.py',('init','pump','listen','run-claude','deliver','close','sync')),
}
EFFECTS=('HOST_EXECUTION','FILESYSTEM_WRITE','NATIVE_WRITE','GIT','NETWORK','CREDENTIALS','SERVICE','EXPORT')
ENV=c.obj({'name':{'type':'string','pattern':'^[A-Z][A-Z0-9_]{0,63}$','maxLength':64},'value_file':c.PIN})
ENTRY=c.obj({'helper_id':c.ID,'project_id':c.ID,'work_id':c.ID,'action_sha256':c.DIGEST,
 'helper':c.enum(*HELPERS),'python':c.PIN,'argv':{'type':'string','minLength':2,'maxLength':c.LIMIT},'cwd':c.PATH,
 'inputs':c.array(c.PIN,64,0),'executables':c.array(c.PIN,32,0),'outputs':c.array(c.PATH,16),
 'effects':c.array(c.enum(*EFFECTS),len(EFFECTS)),'environment':c.array(ENV,16,0),
 'timeout_seconds':{'type':'integer','minimum':1,'maximum':540}})
POLICY=c.obj({'schema':{'const':'golem.integration-helper-effects.v1'},'mutation_policy_sha256':c.DIGEST,
 'assurance':{'const':'LOCAL_COOPERATIVE_EXACT_OWNER_EFFECTS_NOT_SANDBOX'},
 'helpers':c.array(ENTRY,32),'producer':c.obj({name:c.DIGEST for name in (*resources.MODULES,'integration_helper_contract.py','usage_pipeline.py')})})


def producer():
    root=Path(__file__).resolve().parent
    return {name:c.sha(r.regular(root/name)) for name in (*resources.MODULES,'integration_helper_contract.py','usage_pipeline.py')}


def argument_values(argv,flag):
    values=[]
    for i,value in enumerate(argv):
        if value==flag:
            c.require(i+1<len(argv),'HELPER_ARGUMENT_VALUE_REQUIRED');values.append(argv[i+1])
    return values


def check_output_ancestors(target):
    # Known paths may be new, but every existing ancestor must pass no-follow.
    current=target
    for _ in range(2048):
        if current.exists() or current.is_symlink():
            r.real_path(str(current));return
        c.require(current!=current.parent,'HELPER_OUTPUT_ARGUMENT');current=current.parent
    raise c.IntegrationError('HELPER_OUTPUT_ARGUMENT')


class Helpers:
    def __init__(self,path,digest,policy,*,approve_helpers=False):
        c.require(approve_helpers is True,'OWNER_HELPER_EFFECTS_APPROVAL_REQUIRED')
        c._validate(digest,c.DIGEST);self.path=r.real_path(str(path));self.digest=digest;self.policy=policy;self.current()
    def current(self):
        data=r.regular(self.path,private=True);c.require(c.sha(data)==self.digest,'HELPER_POLICY_CHANGED');value=c.decode(data);c._validate(value,POLICY)
        c.require(value['producer']==producer(),'PRODUCER_CHANGED')
        c.require(value['mutation_policy_sha256']==self.policy.digest,'HELPER_MUTATION_POLICY_BINDING');self.policy.current()
        c.require(len({row['helper_id'] for row in value['helpers']})==len(value['helpers']),'DUPLICATE_HELPER')
        return value
    def select(self,entry,envelope):
        request=c.decode(envelope['native_json'].encode());row=next((x for x in self.current()['helpers'] if x['helper_id']==request['helper_id']),None)
        c.require(row is not None and (row['project_id'],row['work_id'],row['action_sha256'])==(entry['project_id'],entry['work_id'],entry['action']['sha256']),'HELPER_ACTION_SCOPE')
        project,_=self.policy.authorize(entry);c.require(not self.path.is_relative_to(Path(project['root'])),'HELPER_POLICY_SCOPE')
        row=copy.deepcopy(row);row['argv']=c.decode(row['argv'].encode())
        c.require(isinstance(row['argv'],list) and 1<=len(row['argv'])<=128,'HELPER_ARGV_SCOPE')
        for argument in row['argv']:c._validate(argument,c.PATH)
        helper,modes=HELPERS[row['helper']];c.require(row['argv'][0] in modes,'HELPER_MODE_SCOPE')
        c.require('--follow' not in row['argv'],'HELPER_UNBOUNDED_SERVICE')
        work=next(w for w in project['works'] if w['work_id']==entry['work_id'])
        c.require(all(path==project['cli']['path'] for path in argument_values(row['argv'],'--cli')),'HELPER_CLI_BINDING')
        for flag,expected in (('--work',work['path']),('--work-id',entry['work_id']),('--project-id',entry['project_id']),('--cwd',project['root'])):
            c.require(all(value==expected for value in argument_values(row['argv'],flag)),'HELPER_ARGUMENT_BINDING')
        required={'HOST_EXECUTION','FILESYSTEM_WRITE'}
        if row['helper'] in ('agent_io','agent_lifecycle'):required|={'NATIVE_WRITE','GIT'}
        if row['helper'] in ('provider_costs','status_collector') and row['argv'][0] in ('fetch','collect'):required|={'NETWORK','CREDENTIALS'}
        if row['helper'] in ('hosted_usage','usage_pipeline') and row['argv'][0] in ('listen','run-claude'):required|={'NETWORK','CREDENTIALS','SERVICE'}
        if row['helper'] in ('evidence_export','billing_evidence','usage_pipeline'):required.add('EXPORT')
        c.require(required<=set(row['effects']),'HELPER_EFFECTS_NOT_APPROVED')
        c.require(not row['environment'] or 'CREDENTIALS' in row['effects'],'HELPER_CREDENTIALS_NOT_APPROVED')
        c.require(len({x['name'] for x in row['environment']})==len(row['environment']),'DUPLICATE_HELPER_ENVIRONMENT')
        c.require(all(x['name'] not in ('PATH','HOME','PYTHONPATH','PYTHONHOME','LD_PRELOAD','DYLD_INSERT_LIBRARIES') and not x['name'].startswith(('GIT_','LD_','DYLD_','PYTHON')) for x in row['environment']),'HELPER_ENVIRONMENT_SCOPE')
        c.require(r.real_path(row['cwd'])==Path(row['cwd']),'HELPER_CWD_SCOPE')
        for path in row['outputs']:
            target=Path(path);c.require(target.is_absolute() and '..' not in target.parts and not target.is_relative_to(Path(project['root'])) and target.parent==self.policy.registry.root and target.name.startswith('helper-output-'+entry['work_id']+'-'),'HELPER_OUTPUT_SCOPE')
            if target.exists():self.policy.registry._private(r.real_path(path))
            else:r.real_path(str(target.parent))
        output_roots=[Path(path) for path in row['outputs']]
        for flag in ('--output','--state','--directory','--store'):
            for value in argument_values(row['argv'],flag):
                target=Path(value);c.require(any(target==root or target.is_relative_to(root) for root in output_roots) and '..' not in target.parts,'HELPER_OUTPUT_ARGUMENT');check_output_ancestors(target)
        if row['helper']=='evidence_export':
            index=2;c.require(len(row['argv'])>index and any(Path(row['argv'][index])==root or Path(row['argv'][index]).is_relative_to(root) for root in output_roots),'HELPER_OUTPUT_ARGUMENT');check_output_ancestors(Path(row['argv'][index]))
        backend._quota(self.policy.registry.root,0)
        for pin in (row['python'],*row['executables']):
            c.require(r.file_pin(Path(pin['path']))==pin and os.access(pin['path'],os.X_OK),'HELPER_EXECUTABLE_CHANGED')
        for pin in row['inputs']:c.require(c.sha(r.regular(Path(pin['path']),private=True))==pin['sha256'],'HELPER_INPUT_CHANGED')
        executable_names={Path(pin['path']).name for pin in row['executables']}
        if row['helper']=='status_collector' and 'gh' in argument_values(row['argv'],'--credentials'):
            c.require('gh' in executable_names,'HELPER_CREDENTIAL_EXECUTABLE_NOT_PINNED')
        if row['helper']=='billing_evidence' and (row['argv'][0]=='reconcile' or '--export' in row['argv']):
            c.require('openssl' in executable_names,'HELPER_BILLING_EXECUTABLE_NOT_PINNED')
        if row['helper']=='usage_pipeline' and row['argv'][0]=='run-claude':
            c.require('--' in row['argv'],'HELPER_COMMAND_SCOPE');command=row['argv'][row['argv'].index('--')+1:]
            c.require(command and command[0] in {pin['path'] for pin in row['executables']},'HELPER_COMMAND_EXECUTABLE_NOT_PINNED')
        self.check_plans(row,project)
        return row
    def check_plans(self,row,project):
        """Only scope equality; original helper validates/reduces its own plan."""
        if row['helper'] not in ('agent_io','agent_lifecycle'):return
        argv=row['argv'];plans=argument_values(argv,'--plan');c.require(len(plans)<=1,'HELPER_AMBIGUOUS_PLAN')
        path=plans[0] if plans else argv[1] if row['helper']=='agent_lifecycle' and len(argv)>1 else None
        if path is None:return
        pins={pin['path']:pin['sha256'] for pin in row['inputs']};executables={pin['path']:pin['sha256'] for pin in row['executables']}
        c.require(path in pins,'HELPER_PLAN_NOT_PINNED');plan=c.decode(r.regular(Path(path),private=True))
        c.require(plan.get('cwd',project['root'])==project['root'],'HELPER_PLAN_CWD_BINDING')
        commands=plan.get('commands',[]) if row['helper']=='agent_io' else [command for phase in plan.get('phases',{}).values() for command in phase]
        c.require(isinstance(commands,list) and 1<=len(commands)<=32,'HELPER_COMMAND_SCOPE')
        for command in commands:
            c.require(isinstance(command,dict) and isinstance(command.get('argv'),list) and command['argv'] and command['argv'][0] in executables,'HELPER_COMMAND_EXECUTABLE_NOT_PINNED')
        for path,digest in plan.get('inputs',{}).items():c.require(pins.get(path)==digest,'HELPER_PLAN_INPUT_SCOPE')
    def environment(self,row):
        value={**backend.ENVIRONMENT,'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'}
        value['PATH']=':'.join(dict.fromkeys([*(str(Path(pin['path']).parent) for pin in row['executables']),'/usr/bin','/bin']))
        for item in row['environment']:
            pin=item['value_file'];raw=r.regular(Path(pin['path']),private=True);c.require(c.sha(raw)==pin['sha256'],'HELPER_CREDENTIAL_CHANGED')
            token=raw.decode('utf-8').rstrip('\n');c.require(bool(token) and '\x00' not in token and '\n' not in token,'HELPER_CREDENTIAL_FORMAT');value[item['name']]=token
        return value
    def command(self,entry,envelope):
        row=self.select(entry,envelope);self.environment(row)
        module=HELPERS[row['helper']][0]
        return [row['python']['path'],'-S',str(Path(__file__).resolve().parent/module),*row['argv']]
    def capture(self,entry,envelope,output):
        row=self.select(entry,envelope);argv=self.command(entry,envelope);environment=self.environment(row)
        # Private output authorization is separate; return only historical capture.
        return records.capture(argv,output,row['timeout_seconds'],cwd=Path(row['cwd']),observe_source=False,env=environment,limit=c.MAX_NATIVE)


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('schema','plan'))
    parser.add_argument('--input',type=Path)
    args=parser.parse_args()
    if args.operation=='schema':value={'$schema':'https://json-schema.org/draft/2020-12/schema',**POLICY}
    else:
        c.require(args.input is not None,'INPUT_REQUIRED');value=c.decode(r.regular(args.input,private=True));value['producer']=producer();c._validate(value,POLICY)
    import sys
    sys.stdout.buffer.write(c.encoded(value))

if __name__=='__main__':main()
