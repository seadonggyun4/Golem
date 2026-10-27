"""M5 bounded native candidate/inventory observations; no scheduler or merge authority."""
import integration_contract as c
import integration_quality_reads as quality
import execution_record as records

NAMES = ('candidate_read', 'inventory_read', 'workspace_read')
TEXT = {'type':'string','minLength':1,'maxLength':c.LIMIT}
MEMBER = {'type':'string','pattern':'^[A-Za-z0-9_-]{1,24}$','maxLength':24}
WORK = {'project_id':c.ID,'work_id':c.ID}


def query(operation, **fields):
    return c.obj({**WORK,'operation':c.enum(operation),**fields})


SCHEMAS = {
    'workspace_read':query('result',action_id=c.ID,request_id=c.ID),
    'candidate_read': {'type':'object','oneOf': [query('validate',request_json=TEXT),
        query('host_validate',request_json=TEXT),query('request_digest',request_json=TEXT),
        query('gates',checkpoint=c.DIGEST),query('status',group_id=MEMBER),
        query('diff',group_id=MEMBER,candidate=MEMBER),query('context_candidate',request_json=TEXT),
        query('compare',query_id=c.ID),query('review_check',query_id=c.ID),query('target_check',query_id=c.ID)]},
    'inventory_read': {'type':'object','oneOf':[query('validate',policy_json=TEXT),
        query('compare',baseline_json=TEXT,current_json=TEXT,policy_json=TEXT)]},
}


def command(name,args,work,output):
    c.require(name in NAMES,'UNSUPPORTED_PARALLEL_READ')
    c._validate(args,SCHEMAS[name])
    op=args['operation']
    def save(filename,field):
        raw=args[field].encode('utf-8')
        c.require(isinstance(c.decode(raw),dict),'PARALLEL_JSON_OBJECT')
        records.save(output/filename,raw)
        return str(output/filename)
    c.require(name!='workspace_read','OWNER_PARALLEL_HOST_REQUIRED')
    if name=='inventory_read':
        policy=save('inventory-policy.json','policy_json')
        if op=='validate':return ['inventory','validate',policy]
        return ['inventory','compare',save('baseline.json','baseline_json'),save('current.json','current_json'),policy]
    if op in ('validate','host_validate','request_digest'):
        return ['candidate',op.replace('_','-'),save('candidate-input.json','request_json')]
    c.require(op not in ('compare','review_check','target_check'),'OWNER_PARALLEL_HOST_REQUIRED')
    if op=='gates':return ['candidate','gates',work,args['checkpoint']]
    if op=='status':return ['candidate','status',work,args['group_id']]
    if op=='diff':return ['candidate','diff',work,args['group_id'],args['candidate']]
    return ['context','candidate',work,save('candidate-context.json','request_json')]


def read(service,scope,name,args):
    if name=='workspace_read':
        c._validate(args,SCHEMAS[name])
        c.require(getattr(service,'parallel_result',None) is not None,'OWNER_PARALLEL_RESULT_REQUIRED')
        result=service.parallel_result('workspace_request',{key:args[key] for key in ('project_id','work_id','action_id','request_id')})
        return {'view':'workspace_read','operation':'result','result':result,'historical_result':True,
            'current_workspace_verified':False,'merge_authorized':False,'target_adoption_verified':False}
    return quality.read(service,scope,name,args)


def host_read(service,scope,name,args):
    if name!='candidate_read':return None
    hosts=getattr(service,'parallel_hosts',None)
    op=args['operation']
    if op in ('compare','review_check','target_check'):
        c.require(hosts is not None,'OWNER_PARALLEL_HOST_REQUIRED')
        return hosts.query(args['project_id'],args['work_id'],op.replace('_','-'),args['query_id'])
    if hosts is None:return None
    row=hosts.parent(args['project_id'],args['work_id'])
    if row is None or op not in ('status','diff','gates'):return None
    hosts.probe(row)
    request={'operation':op}
    request.update({key:args[key] for key in ('group_id','candidate','checkpoint') if key in args})
    raw=hosts._capture(row,c.encoded(request))
    hosts.probe(row)
    return raw
