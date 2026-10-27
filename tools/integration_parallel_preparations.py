"""M5 review-only DAG/merge proposals in the existing immutable M2 spool.

This module checks references and graph syntax. No scheduler, edge acceptance,
resource arbiter, target CAS broker, integration QA or merge implementation.
"""
import copy
import integration_contract as c
import integration_preparations as prep
import integration_reads as reads
import integration_backend as backend

NAMES=('parallel_prepare','merge_prepare')
REF=c.obj({'document_id':c.ID,'revision':c.INTEGER,'digest':c.DIGEST})
MEMBER={'type':'string','pattern':'^[A-Za-z0-9_-]{1,24}$','maxLength':24}
CANDIDATE=c.obj({'group_id':MEMBER,'candidate':MEMBER})
TASK=c.obj({'task_id':c.ID,'work_id':c.ID,'selection':REF,'spec_digest':c.DIGEST,
    'source_snapshot':c.DIGEST,'owner_session_id':c.ID,'runtime_binding':c.DIGEST,
    'resources':c.obj({'slots':c.INTEGER,'cpu_millis':c.INTEGER,'memory_bytes':c.INTEGER}),
    'candidate':{**CANDIDATE,'type':['object','null']}})
EDGE=c.obj({'edge_id':c.ID,'predecessor_task':c.ID,'successor_task':c.ID,
    'type':c.enum('ARTIFACT_OBSERVED','QA_ACCEPTED','INTEGRATION_ACCEPTED'),
    'predecessor_spec_digest':c.DIGEST,'selected_attempt_ref':{**c.DIGEST,'type':['string','null']},
    'required_artifact_refs':c.array(c.DIGEST,32,0),'evidence_policy_digest':c.DIGEST,
    'consumption_mode':c.enum('EXPLORATORY','PRODUCT','TARGET_INTEGRATED'),'baseline_digest':c.DIGEST})
DAG=c.obj({'schema':{'const':'golem.parallel-review-input.v1'},'baseline_digest':c.DIGEST,
    'tasks':c.array(TASK,16),'edges':c.array(EDGE,64,0)})
MERGE=c.obj({'schema':{'const':'golem.merge-review-input.v1'},'source_work_id':c.ID,
    'target_work_id':c.ID,'candidate':CANDIDATE,'candidate_result':c.DIGEST,'selection_receipt':c.DIGEST,
    'qa_receipt':c.DIGEST,'review_receipt':c.DIGEST,'baseline_digest':c.DIGEST,
    'source_snapshot':c.DIGEST,'input_digest':c.DIGEST,'tree_digest':c.DIGEST,
    'target_oid':{'type':'string','pattern':'^(?:[a-f0-9]{40}|[a-f0-9]{64})$','maxLength':64},
    'target_ref_generation':c.INTEGER,'target_policy_digest':c.DIGEST})
TEXT={'type':'string','minLength':1,'maxLength':c.LIMIT}
SCHEMAS={'parallel_prepare':c.obj({**prep.CREATE,'proposal_json':TEXT}),
         'merge_prepare':c.obj({**prep.CREATE,'proposal_json':TEXT})}
KINDS=('PARALLEL_REVIEW','MERGE_REVIEW')
UNIMPLEMENTED=('TASK_DAG_SCHEDULER','TYPED_EDGE_EVIDENCE_ACCEPTANCE','RESOURCE_RECEIVER_BROKER',
    'MERGE_QUEUE','INTEGRATION_WORKSPACE_AND_FRESH_QA','TARGET_REF_CAS_BROKER','MERGE_PUBLICATION_RECEIPT')


def structure(name,value):
    c._validate(value,DAG if name=='parallel_prepare' else MERGE)
    if name=='merge_prepare':
        c.require(value['source_work_id']!=value['target_work_id'],'MERGE_WORK_ISOLATION')
        return [value['source_work_id'],value['target_work_id']]
    tasks={task['task_id']:task for task in value['tasks']}
    c.require(len(tasks)==len(value['tasks']) and len({t['work_id'] for t in tasks.values()})==len(tasks),'PARALLEL_DUPLICATE_TASK_OR_WORK')
    c.require(len({edge['edge_id'] for edge in value['edges']})==len(value['edges']),'PARALLEL_DUPLICATE_EDGE')
    successors={task_id:[] for task_id in tasks};indegree={task_id:0 for task_id in tasks};pairs=set()
    for edge in value['edges']:
        start,end=edge['predecessor_task'],edge['successor_task']
        c.require(start in tasks and end in tasks and start!=end,'PARALLEL_EDGE_REFERENCE')
        c.require((start,end,edge['type']) not in pairs,'PARALLEL_DUPLICATE_EDGE');pairs.add((start,end,edge['type']))
        c.require(edge['predecessor_spec_digest']==tasks[start]['spec_digest'] and edge['baseline_digest']==value['baseline_digest'],'PARALLEL_EDGE_DRIFT')
        c.require((edge['type']=='ARTIFACT_OBSERVED' and edge['consumption_mode']=='EXPLORATORY') or
            (edge['type']=='QA_ACCEPTED' and edge['consumption_mode']=='PRODUCT') or
            (edge['type']=='INTEGRATION_ACCEPTED' and edge['consumption_mode']=='TARGET_INTEGRATED'),'PARALLEL_EDGE_MODE')
        successors[start].append(end);indegree[end]+=1
    pending=[task for task in tasks if indegree[task]==0];visited=0
    while pending:
        task=pending.pop();visited+=1
        for following in successors[task]:
            indegree[following]-=1
            if indegree[following]==0:pending.append(following)
    c.require(visited==len(tasks),'PARALLEL_CYCLE')
    return [task['work_id'] for task in value['tasks']]


def reobserve(service,scope,plan,anchor_basis=None):
    payload=plan['payload'];proposal=payload['proposal'];name='parallel_prepare' if payload['kind']=='PARALLEL_REVIEW' else 'merge_prepare'
    work_ids=structure(name,proposal);bases={}
    for work_id in work_ids:
        selected=service.transfer.scope(scope['binding']['project_id'],work_id,'work_inspect')
        c.require(selected['binding']==scope['binding'],'PARALLEL_WORK_BINDING')
        _,observed,basis=prep.observe(service,selected,work_id)
        if name=='parallel_prepare':
            task=next(t for t in proposal['tasks'] if t['work_id']==work_id)
            reference=task['selection'];document=reads._document(observed['record'],reference['document_id'],reference['revision'])
            c.require(document.get('digest')==reference['digest'],'PARALLEL_SELECTION_DRIFT')
        bases[work_id]=basis
    if anchor_basis is None:_,_,anchor_basis=prep.observe(service,scope,plan['work_id'])
    return {**anchor_basis,'parallel_works':bases}


def read(service,scope,name,args):
    c.require(name in NAMES,'UNSUPPORTED_PARALLEL_PREPARATION');c._validate(args,SCHEMAS[name])
    value=c.decode(args['proposal_json'].encode());structure(name,value)
    original=service.preparation_requests.get(prep.request_identity(scope,args))
    if original is not None:
        digest,plan_id,plan_sha=original
        c.require(digest==c.sha(c.encoded(args)),'PREPARATION_REQUEST_CONFLICT')
        return prep.review_plan(service,scope,{**{k:args[k] for k in ('project_id','work_id')},'plan_id':plan_id,'plan_sha256':plan_sha})
    prep.admit_plan(service);backend._quota(service.registry.root,4)
    _,observed,basis=prep.observe(service,scope,args['work_id'])
    payload={'kind':'PARALLEL_REVIEW' if name=='parallel_prepare' else 'MERGE_REVIEW','proposal':copy.deepcopy(value),
        'implementation_required':list(UNIMPLEMENTED),'scheduler_state':'NOT_IMPLEMENTED','merge_state':'NOT_IMPLEMENTED',
        'edge_acceptance':'NOT_EVALUATED','readiness':'NOT_EVALUATED','resources_reserved':False,
        'owner_labels_authenticated':False,'artifact_integrity_verified':False,'qa_pass_verified':False,
        'target_applicability_verified':False,'target_ref_cas_verified':False,'merge_authorized':False,
        'references_role':'CALLER_DECLARED_REFERENCES_NOT_NATIVE_ISSUED_RECEIPT_CERTIFICATION',
        'blockers':[{'code':'IMPLEMENTATION_REQUIRED','features':list(UNIMPLEMENTED)}],'questions':[]}
    plan={'payload':payload,'work_id':args['work_id']}
    before=reobserve(service,scope,plan,basis)
    _,after,current=prep.observe(service,scope,args['work_id'])
    c.require(before==reobserve(service,scope,plan,current),'OBSERVATION_STALE')
    return prep.seal(service,scope,args,after,before,payload)
