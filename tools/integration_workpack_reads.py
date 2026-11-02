"""Work Pack transport only. Native parsers decide semantics; no authority inferred."""
import integration_contract as c
import execution_record as records

NAMES=('workpack_read',)
TEXT={'type':'string','minLength':2,'maxLength':262144}
PACK={'type':'string','minLength':2,'maxLength':65536}
WORK={'project_id':c.ID,'work_id':c.ID}
def query(operation,**fields):return c.obj({**WORK,'operation':{'const':operation},**fields})
SCHEMAS={'workpack_read':{'type':'object','oneOf':[
    query('validate',pack_json=PACK),query('inspect',pack_json=PACK),
    query('compatibility',pack_json=PACK,core_version={'type':'string','maxLength':64,'pattern':r'^[0-9]+\.[0-9]+\.[0-9]+$'}),
    query('resolve',request_json=TEXT),query('explain'),
    query('proposal_validate',proposal_json=PACK),
    query('assess',proposals=c.array(PACK,8)),
    query('reference_observe',capture_json=TEXT,source_sha256=c.DIGEST,config_sha256=c.DIGEST,pack_sha256=c.DIGEST),
]}}
RESOURCE_SCHEMA={'type':'object','oneOf':[
    c.obj({**WORK,'resource_id':c.ID,'operation':{'const':'list'},'index_name':{'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$','maxLength':128}}),
    c.obj({**WORK,'resource_id':c.ID,'operation':{'const':'search'},'index_name':{'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$','maxLength':128},'query':{'type':'string','minLength':1,'maxLength':256}}),
    c.obj({**WORK,'resource_id':c.ID,'operation':{'const':'receipt_verify'},'manifest_sha256':c.DIGEST}),
]}

def command(name,args,work,output):
    c._validate(args,SCHEMAS[name]);op=args['operation']
    def save(filename,text,limit):
        raw=text.encode();c.require(len(raw)<=limit,'WORKPACK_INPUT_LIMIT')
        records.save(output/filename,raw);return str(output/filename)
    if op in ('validate','inspect','compatibility'):
        argv=['pack',op,save('pack.json',args['pack_json'],65536)]
        return argv+(['--core-version',args['core_version']] if op=='compatibility' else [])
    if op=='resolve':return ['pack','resolve',work,save('binding.json',args['request_json'],131072)]
    if op=='explain':return ['pack','explain',work]
    if op=='proposal_validate':return ['pack','proposal-validate',save('proposal.json',args['proposal_json'],65536)]
    if op=='assess':return ['pack','assess',work,*[save('proposal-'+str(i)+'.json',p,65536) for i,p in enumerate(args['proposals'])]]
    return ['pack','reference-observe',save('capture.json',args['capture_json'],262144),'--expect-source',args['source_sha256'],'--expect-config',args['config_sha256'],'--expect-pack',args['pack_sha256']]

def resource_command(args,snapshot):
    c._validate(args,RESOURCE_SCHEMA);op=args['operation']
    if op=='receipt_verify':return ['receipt','verify',str(snapshot),'--expect-manifest',args['manifest_sha256']]
    return ['pack',op,*([args['query']] if op=='search' else []),'--catalog',str(snapshot/args['index_name'])]
