"""Deterministic review-only feature artifacts. No installer, trust root or release certification."""
import argparse
import ast
import io
import json
from pathlib import Path
import stat
import sys
import zipfile
import integration_contract as c
import integration_registry as r
import integration_feature_profiles as profiles
import integration_mcpb as legacy
import integration_transfer as transfer
import execution_record as records

MAX_ARCHIVE=134217728
MAX_FILE=67108864
MAX_FILES=256
SCHEMAS=('schemas/d2-tools.json','schemas/d4-actions.json','schemas/installation.json','schemas/maintenance.json','schemas/feature-profiles.json')
SKILLS=('plugins/golem/skills/golem-setup/SKILL.md','plugins/golem/skills/golem-setup/agents/openai.yaml',
        'plugins/golem/skills/golem-work/SKILL.md','plugins/golem/skills/golem-work/agents/openai.yaml',
        'plugins/golem/skills/golem-work/references/profiles.md')
DOCUMENTS=('tools/requirements-mcp.txt','docs/mcp-m6-distribution.ko.md','docs/integration-install.md','docs/integration-d5.md',
           'docs/mcp-m5-parallel-candidates.ko.md')


NATIVE=c.obj({'sha256':c.DIGEST,'target':c.enum('darwin-arm64','linux-x86_64','linux-arm64'),
              'abi_qualification':{'const':'NOT_RUN'},'dynamic_dependencies':{'const':'NOT_VERIFIED'}})
INVENTORY=c.obj({'schema':{'const':'golem.integration-feature-package.v1'},'profile':{'type':['object','null']},
 'target':c.enum('external-runtime','darwin-arm64','linux-x86_64','linux-arm64'),
 'native':{**NATIVE,'type':['object','null']},
 'files':{'type':['object','null']},
 'runtime_delivery':{'const':'EXTERNAL_OWNER_PINNED_PYTHON_SDK_AND_NATIVE_REQUIRED'},'self_contained':{'const':False},
 'signature':{'const':'NOT_IMPLEMENTED'},'trust_root':{'const':'NOT_SELECTED'},'host_manifest_qualification':{'const':'NOT_RUN'},
 'installed':{'const':False},'activated':{'const':False},'execution_authorized':{'const':False},'actual_installation':{'const':'NOT_RUN'}})


def relative(name):
    c.require(isinstance(name,str) and name and '\\' not in name and '\x00' not in name and
        all(part not in ('','.','..') for part in name.split('/')) and not name.startswith('/'),'PACKAGE_PATH')
    return name


def closure(payloads):
    """Static local import presence. Not third-party ABI/runtime qualification."""
    names={Path(path).stem for path in payloads if path.startswith('tools/') and path.endswith('.py')}
    missing=set()
    for path,raw in payloads.items():
        if not path.startswith('tools/') or not path.endswith('.py'):continue
        for node in ast.walk(ast.parse(raw)):
            modules=[item.name.split('.')[0] for item in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else []
            for name in modules:
                if (name.startswith('integration_') or name in ('execution_record','verify_agent','usage_pipeline','agent_io','agent_lifecycle','provider_usage','provider_costs','hosted_usage','billing_evidence','evidence_export','status_collector')) and name not in names:missing.add(name)
    c.require(not missing,'PACKAGE_IMPORT_CLOSURE')


def schema_payloads():
    import integration_service as reads
    import integration_mutation_contract as actions
    import integration_install as install
    import integration_update as update
    return {SCHEMAS[0]:c.encoded(reads.SCHEMAS),SCHEMAS[1]:c.encoded({'tools':actions.SCHEMAS,'action':actions.ACTION,'policy':actions.POLICY}),
        SCHEMAS[2]:c.encoded(install.SPECS),SCHEMAS[3]:c.encoded(update.SPEC),
        SCHEMAS[4]:c.encoded([profiles.definition(name) for name in profiles.NAMES])}


def manifest(profile):
    value=legacy.manifest();spec=profiles.definition(profile)
    value['version']='0.1.8'
    value['name']='golem-'+profile;value['display_name']='Golem '+profile
    value['description']='Owner-scoped '+profile+' feature ceiling. External pinned runtime required; no automatic grants.'
    value['server']['entry_point']='tools/integration_distribution_entry.py'
    value['server']['mcp_config']['args']=['run','--directory','${__dirname}','tools/integration_distribution_entry.py']
    fields={
      'policy':('file','Existing reviewed '+spec['family']+' policy',True),
      'policy_sha256':('string','Exact owner-reviewed policy digest',True),
      'approve_owner':('boolean','Explicit consent to this existing owner policy',True),
      'resource_policy':('file','Optional explicit resource policy',False),'resource_sha256':('string','Optional resource digest',False),'approve_resources':('boolean','Explicit resource consent',False)}
    if profile=='quality':fields.update(helper_policy=('file','Separate exact helper-effects policy',False),helper_sha256=('string','Exact helper policy digest',False),approve_helpers=('boolean','Explicit helper effects consent',False))
    if profile=='parallel':fields.update(host_policy=('file','Separate exact native host policy',False),host_sha256=('string','Exact host policy digest',False),approve_host=('boolean','Explicit host contract consent',False))
    value['user_config']={name:{'type':kind,'title':title,'description':title+'. Selecting a value never grants additional authority.',
        'required':required,**({'default':False} if kind=='boolean' else {})} for name,(kind,title,required) in fields.items()}
    env={'GOLEM_FEATURE_PROFILE':profile,'GOLEM_PROFILE_POLICY':'${user_config.policy}',
        'GOLEM_PROFILE_POLICY_SHA256':'${user_config.policy_sha256}','GOLEM_APPROVE_PROFILE_OWNER':'${user_config.approve_owner}',
        'GOLEM_RESOURCE_POLICY':'${user_config.resource_policy}','GOLEM_RESOURCE_SHA256':'${user_config.resource_sha256}',
        'GOLEM_APPROVE_RESOURCES':'${user_config.approve_resources}'}
    if profile=='quality':env.update(GOLEM_HELPER_POLICY='${user_config.helper_policy}',GOLEM_HELPER_SHA256='${user_config.helper_sha256}',GOLEM_APPROVE_HELPERS='${user_config.approve_helpers}')
    if profile=='parallel':env.update(GOLEM_HOST_POLICY='${user_config.host_policy}',GOLEM_HOST_SHA256='${user_config.host_sha256}',GOLEM_APPROVE_HOST='${user_config.approve_host}')
    value['server']['mcp_config']['env']=env
    return value


def build(profile,*,native=None,native_sha256=None,target='external-runtime'):
    root=Path(__file__).resolve().parents[1];spec=profiles.definition(profile)
    c.require(target in ('external-runtime','darwin-arm64','linux-x86_64','linux-arm64'),'PACKAGE_TARGET')
    c.require(bool(native)==bool(native_sha256),'PACKAGE_NATIVE_PIN_REQUIRED')
    c.require(not native or target!='external-runtime','PACKAGE_NATIVE_TARGET_REQUIRED')
    with zipfile.ZipFile(io.BytesIO(legacy.build())) as package:payloads={name:package.read(name) for name in package.namelist()}
    for path in (*SKILLS,*DOCUMENTS):payloads[path]=r.regular(root/path,16777216)
    payloads.update(schema_payloads())
    payloads['manifest.json']=c.encoded(manifest(profile));closure(payloads)
    native_pin=None
    if native:
        c._validate(native_sha256,c.DIGEST);raw=r.regular(Path(native),MAX_FILE)
        c.require(c.sha(raw)==native_sha256,'PACKAGE_NATIVE_CHANGED')
        payloads['native/golem']=raw;native_pin={'sha256':native_sha256,'target':target,'abi_qualification':'NOT_RUN','dynamic_dependencies':'NOT_VERIFIED'}
    inventory={'schema':'golem.integration-feature-package.v1','profile':spec,'target':target,'native':native_pin,
        'files':{path:c.sha(raw) for path,raw in sorted(payloads.items())},
        'runtime_delivery':'EXTERNAL_OWNER_PINNED_PYTHON_SDK_AND_NATIVE_REQUIRED','self_contained':False,
        'signature':'NOT_IMPLEMENTED','trust_root':'NOT_SELECTED','host_manifest_qualification':'NOT_RUN',
        'installed':False,'activated':False,'execution_authorized':False,'actual_installation':'NOT_RUN'}
    payloads['feature-package.json']=c.encoded(inventory)
    c.require(len(payloads)<=MAX_FILES and sum(map(len,payloads.values()))<=MAX_ARCHIVE,'PACKAGE_LIMIT')
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as package:
        for path,raw in sorted(payloads.items()):
            relative(path);info=zipfile.ZipInfo(path,date_time=(2020,1,1,0,0,0));info.create_system=3
            info.external_attr=(0o100700 if path=='native/golem' else 0o100600)<<16;info.compress_type=zipfile.ZIP_DEFLATED
            package.writestr(info,raw)
    c.require(len(output.getvalue())<=MAX_ARCHIVE,'PACKAGE_LIMIT')
    return output.getvalue()


def verify(raw,reviewed_sha256):
    c._validate(reviewed_sha256,c.DIGEST)
    c.require(len(raw)<=MAX_ARCHIVE and c.sha(raw)==reviewed_sha256,'PACKAGE_DIGEST')
    payloads={};total=0;folded=set()
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        c.require(0<len(package.infolist())<=MAX_FILES,'PACKAGE_LIMIT')
        for info in package.infolist():
            c.require(info.filename==info.orig_filename,'PACKAGE_PATH')
            name=relative(info.filename);mode=info.external_attr>>16
            c.require(name not in payloads and name.casefold() not in folded and stat.S_ISREG(mode) and
                mode & 0o077==0 and not mode & 0o7000 and not info.flag_bits&1,'PACKAGE_ENTRY')
            c.require(info.file_size<=MAX_FILE,'PACKAGE_LIMIT');total+=info.file_size;c.require(total<=MAX_ARCHIVE,'PACKAGE_LIMIT')
            payloads[name]=package.read(info);folded.add(name.casefold())
    c.require('feature-package.json' in payloads,'PACKAGE_INVENTORY')
    inventory=c.decode(payloads.pop('feature-package.json'),16777216)
    c.require(isinstance(inventory,dict) and inventory.get('schema')=='golem.integration-feature-package.v1','PACKAGE_INVENTORY')
    c._validate(inventory,INVENTORY)
    c.require(isinstance(inventory['profile'],dict) and isinstance(inventory['files'],dict),'PACKAGE_INVENTORY')
    if inventory['native'] is not None:c._validate(inventory['native'],NATIVE)
    profile=inventory['profile']['profile'];c.require(inventory['profile']==profiles.definition(profile),'PACKAGE_PROFILE_CHANGED')
    c.require(inventory['files']=={path:c.sha(data) for path,data in sorted(payloads.items())},'PACKAGE_CONTENT_CHANGED')
    c.require(c.decode(payloads['manifest.json'])==manifest(profile),'PACKAGE_MANIFEST_CHANGED')
    c.require(inventory['self_contained'] is False and inventory['installed'] is False and inventory['activated'] is False and
        inventory['execution_authorized'] is False and inventory['signature']=='NOT_IMPLEMENTED','PACKAGE_ASSURANCE_PROMOTION')
    c.require(set(SKILLS)<=set(payloads) and set(DOCUMENTS)<=set(payloads),'PACKAGE_RESOURCE_MISSING')
    # A forged inventory cannot introduce private files or extra executable paths.
    allowed={'manifest.json','pyproject.toml','assets/Golem-mcp.png','LICENSE',
        *('tools/'+name for name in (*transfer.PRODUCER_NAMES,'integration_mcpb_entry.py')),*SKILLS,*DOCUMENTS,*SCHEMAS}
    if inventory['native'] is not None:
        c.require(inventory['target'] in ('darwin-arm64','linux-x86_64','linux-arm64') and inventory['native']['target']==inventory['target'] and inventory['native']['sha256']==c.sha(payloads.get('native/golem',b'')),'PACKAGE_NATIVE_CHANGED');allowed.add('native/golem')
    c.require(set(payloads)==allowed,'PACKAGE_FILE_SCOPE')
    c.require(all(payloads.get(name)==raw for name,raw in schema_payloads().items()),'PACKAGE_SCHEMA_CHANGED')
    closure(payloads)
    return inventory,payloads


def extract(raw,reviewed_sha256,destination):
    inventory,payloads=verify(raw,reviewed_sha256)
    destination=Path(destination);r.real_path(str(destination.parent));r.Registry._private(destination.parent)
    c.require(not destination.exists() and not destination.is_symlink(),'PACKAGE_DESTINATION_EXISTS')
    destination.mkdir(mode=0o700)
    for name,data in sorted(payloads.items()):
        path=destination/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);records.save(path,data)
        if name=='native/golem':path.chmod(0o700)
    records.save(destination/'feature-package.json',c.encoded(inventory))
    return {'state':'EXTRACTED_REVIEW_ARTIFACT','installation':'NOT_RUN','activation':'NOT_RUN','grants_created':False,'profile':inventory['profile']['profile']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=('catalog','build','verify','extract'))
    parser.add_argument('--profile',choices=profiles.NAMES);parser.add_argument('--input',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--reviewed-sha256');parser.add_argument('--native',type=Path);parser.add_argument('--reviewed-native-sha256');parser.add_argument('--target',default='external-runtime');args=parser.parse_args()
    try:
        if args.operation=='catalog':result=[profiles.definition(name) for name in profiles.NAMES]
        elif args.operation=='build':
            c.require(args.output is not None and args.profile is not None,'PACKAGE_OUTPUT_REQUIRED')
            raw=build(args.profile,native=args.native,native_sha256=args.reviewed_native_sha256,target=args.target)
            r.real_path(str(args.output.parent));c.require(not args.output.exists() and not args.output.is_symlink(),'PACKAGE_DESTINATION_EXISTS');records.save(args.output,raw)
            result={'sha256':c.sha(raw),'bytes':len(raw),'installed':False,'approval_created':False}
        else:
            c.require(args.input is not None,'PACKAGE_INPUT_REQUIRED');raw=r.regular(args.input,MAX_ARCHIVE,private=True)
            result=verify(raw,args.reviewed_sha256)[0] if args.operation=='verify' else extract(raw,args.reviewed_sha256,args.output)
        sys.stdout.buffer.write(c.encoded(result));return 0
    except (c.IntegrationError,OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as error:
        sys.stderr.write(c.encoded({'state':'BLOCKED_OR_PARTIAL','code':getattr(error,'code','PACKAGE_INVALID'),'automatic_retry_allowed':False}).decode());return 1


if __name__=='__main__':sys.exit(main())
