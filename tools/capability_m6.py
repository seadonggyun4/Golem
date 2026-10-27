"""M6 selected-byte profile/package/owner/skill checks. No inspected code execution."""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_m1 import _functions
from capability_fallback import _shape
from capability_c_graph import fingerprint
from capability_source import python_literal_names

@dataclass(frozen=True)
class M6Observation:
    profiles:tuple
    owner_backlog_count:int
    checked_functions:int
    blockers:tuple
    owner_backlog_discharged:bool=False
    actual_installation:str='NOT_RUN'
    actual_reload:str='NOT_RUN'
    client_e2e:str='NOT_RUN'
    self_contained_runtime:str='NOT_IMPLEMENTED'
    signing_trust_root:str='NOT_SELECTED'
    scheduler_or_merge_implemented:bool=False


def inspect_m6(sources,ledger,model,backlog):
    scan_sources(sources,());files={f.path:f for f in sources};trees={};errors=[];checked=0;names=()
    for path,digest in model['pins']:
        f=files.get(path)
        if f is None or f.sha256!=digest:errors.append(('M6_SOURCE_MISSING_OR_DRIFT',path));continue
        if path.endswith('.py'):trees[path]=ast.parse(f.data)
    for path,name,shape in model['functions']:
        node=_functions(trees[path]).get(name) if path in trees else None
        if node is None or fingerprint(_shape(node))!=shape:errors.append(('M6_FUNCTION_CHANGED',(path,name)))
        else:checked+=1
    guards=(
      ('tools/integration_feature_profiles.py','Scoped.tools',"sorted(set(self.service.tools()) & set(self.profile['tools']))"),
      ('tools/integration_feature_profiles.py','Scoped.call',"c.require(name in self.profile['tools'],'FEATURE_PROFILE_SCOPE')"),
      ('tools/integration_feature_profiles.py','Scoped.call',"c.require(name in self.service.tools(),'FEATURE_OWNER_SCOPE')"),
      ('tools/integration_distribution_entry.py','configure',"c.require(approve_owner is True,'OWNER_PROFILE_APPROVAL_REQUIRED')"),
      ('tools/integration_distribution_entry.py','configure',"c.require(not helper or profile=='quality','FEATURE_HELPER_SCOPE')"),
      ('tools/integration_distribution_entry.py','configure',"c.require(not host or profile=='parallel','FEATURE_HOST_SCOPE')"),
      ('tools/integration_distribution_entry.py','configure',"actions.Policy(Path(policy),digest,approve_mutations=True)"),
      ('tools/integration_distribution_entry.py','configure',"transfer.Transfer(Path(policy),digest,approve_data_transfer=True)"),
      ('tools/integration_distribution_entry.py','configure',"helpers.Helpers(Path(helper),helper_digest,owner,approve_helpers=True)"),
      ('tools/integration_distribution_entry.py','configure',"hosts.Hosts(Path(host),host_digest,owner,approve_hosts=True)"),
      ('tools/integration_distribution_entry.py','_configure_startup','configure(**args)'),
      ('tools/integration_distribution_entry.py','serve','startup.enter_context(lifecycle.participation(owner.registry,bindings))'),
      ('tools/integration_distribution_entry.py','_startup_pause','time.sleep(0.05)'),
      ('tools/integration_distribution.py','verify',"c.require(len(raw)<=MAX_ARCHIVE and c.sha(raw)==reviewed_sha256,'PACKAGE_DIGEST')"),
      ('tools/integration_distribution.py','verify',"c.require(inventory['files']=={path:c.sha(data) for path,data in sorted(payloads.items())},'PACKAGE_CONTENT_CHANGED')"),
      ('tools/integration_distribution.py','verify',"c._validate(inventory,INVENTORY)"),
      ('tools/integration_distribution.py','verify',"c.require(set(payloads)==allowed,'PACKAGE_FILE_SCOPE')"),
      ('tools/integration_distribution.py','extract',"c.require(not destination.exists() and not destination.is_symlink(),'PACKAGE_DESTINATION_EXISTS')"),
      ('tools/integration_owner_maintenance.py','dispatch',"c.require(approve_owner is True,'OWNER_LIFECYCLE_APPROVAL_REQUIRED')"),
      ('tools/integration_owner_maintenance.py','dispatch',"manager.apply(value,reviewed_sha256,approve_installation=True,repair=False)"),
      ('tools/integration_owner_maintenance.py','dispatch',"manager.apply(value,reviewed_sha256,approve_maintenance=True)"),
    )
    for path,name,expression in guards:
        node=_functions(trees[path]).get(name) if path in trees else None;expected=_shape(ast.parse(expression,mode='eval').body)
        if node is None or sum(_shape(n)==expected for n in ast.walk(node) if isinstance(n,ast.Call))!=1:errors.append(('M6_MANDATORY_GUARD_CHANGED',(path,name,expression)))
    try:
        names=python_literal_names(files['tools/integration_feature_profiles.py'].data.decode(),'NAMES',mapping=False)
        if set(names)!={'read','prepare','task','quality','parallel'}:raise ValueError('M6_PROFILE_DOMAIN')
        declared=set(python_literal_names(files['tools/integration_service.py'].data.decode(),'SCHEMAS',mapping=True))|set(python_literal_names(files['tools/integration_mutation_contract.py'].data.decode(),'NAMES',mapping=False))
        tree=trees['tools/integration_feature_profiles.py']
        for assignment in ('READ','PREP','OWNER_PREP','BASE_ACTIONS','TASK_ACTIONS','QUALITY_ACTIONS','PARALLEL_ACTIONS'):
            if not set(python_literal_names(files['tools/integration_feature_profiles.py'].data.decode(),assignment,mapping=False))<=declared:raise ValueError('M6_UNPROVIDED_TOOL')
        from capability_m5 import literal_tuple
        if set(literal_tuple(tree,'UNIMPLEMENTED'))!={'TASK_DAG_SCHEDULER','TYPED_EDGE_EVIDENCE_ACCEPTANCE','RESOURCE_RECEIVER_BROKER','MERGE_QUEUE','INTEGRATION_WORKSPACE_AND_FRESH_QA','TARGET_REF_CAS_BROKER','MERGE_PUBLICATION_RECEIPT'}:raise ValueError('M6_M5_UNIMPLEMENTED_OBLIGATION_REMOVED')
        definition=_functions(tree)['definition'];returned=next(n.value for n in ast.walk(definition) if isinstance(n,ast.Return))
        flags={key.value:value for key,value in zip(returned.keys,returned.values) if isinstance(key,ast.Constant)}
        for key in ('grants_created','resources_enabled_by_default','helper_enabled_by_default','parallel_host_enabled_by_default','work_completion_verified'):
            if _shape(flags.get(key))!=_shape(ast.Constant(value=False)):raise ValueError('M6_PROFILE_AUTHORITY_PROMOTION')
        wrapper=_functions(tree)['Scoped.call']
        delegated=_shape(ast.parse('self.service.call(name,args)',mode='eval').body)
        if sum(_shape(n)==delegated for n in ast.walk(wrapper) if isinstance(n,ast.Call))!=1 or _shape(wrapper.body[-1])!=_shape(ast.parse('return result').body[0]):raise ValueError('M6_PROFILE_HANDOFF')
        discovery=[n for n in wrapper.body if isinstance(n,ast.If)]
        if len(discovery)!=1 or _shape(discovery[0].test)!=_shape(ast.parse("name=='projects_list'",mode='eval').body):raise ValueError('M6_NATIVE_RESULT_REWRITE')
        fn=_functions(trees['tools/integration_distribution_entry.py'])['configure']
        first=_shape(ast.parse("c.require(approve_owner is True,'OWNER_PROFILE_APPROVAL_REQUIRED')").body[0])
        if _shape(fn.body[1])!=first:raise ValueError('M6_POLICY_READ_BEFORE_CONSENT')
        entry=trees['tools/integration_distribution_entry.py'];startup=_functions(entry)
        limit=next(n.value for n in entry.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='STARTUP_WAIT_SECONDS' for t in n.targets))
        if ast.literal_eval(limit)!=5:raise ValueError('M6_STARTUP_WAIT_BOUND_CHANGED')
        expected=ast.parse("if error.code != 'REGISTRY_BUSY' or time.monotonic() >= deadline:\n    raise error").body[0]
        if _shape(startup['_startup_pause'].body[1])!=_shape(expected):raise ValueError('M6_STARTUP_ERROR_OR_DEADLINE_CHANGED')
        for name in ('_configure_startup','serve'):
            for handler in (n for n in ast.walk(startup[name]) if isinstance(n,ast.ExceptHandler)):
                if _shape(handler.type)!=_shape(ast.parse('c.IntegrationError',mode='eval').body):raise ValueError('M6_STARTUP_EXCEPTION_EXPANSION')
            for loop in (n for n in ast.walk(startup[name]) if isinstance(n,ast.While)):
                if any(isinstance(n,ast.Await) for n in ast.walk(loop)):raise ValueError('M6_REQUEST_HANDLER_IN_STARTUP_LOOP')
                allowed={'configure','_startup_pause','startup.enter_context','lifecycle.participation'}
                if any(ast.unparse(n.func) not in allowed for n in ast.walk(loop) if isinstance(n,ast.Call)):raise ValueError('M6_ACTION_IN_STARTUP_LOOP')
        for path in ('tools/integration_distribution.py','tools/integration_owner_maintenance.py'):
            for call in (n for n in ast.walk(trees[path]) if isinstance(n,ast.Call)):
                attr=call.func.attr if isinstance(call.func,ast.Attribute) else call.func.id if isinstance(call.func,ast.Name) else None
                if attr in ('Popen','capture','system','execv','execve','kill','rmtree'):raise ValueError('M6_AUTOMATIC_EXECUTION_OR_DELETION')
        for field in ('INSTALL_OPS','MAINTENANCE_OPS'):
            value=next(n.value for n in trees['tools/integration_owner_maintenance.py'].body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==field for t in n.targets))
            allowed=ast.literal_eval(value)
            if any('repair' in op for op in allowed) or not set(allowed)<=({'install','remove','bootstrap'} if field=='INSTALL_OPS' else {'freeze','stage','verify','switch','restore','thaw','ready'}):raise ValueError('M6_REPAIR_OR_APPROVAL_EXPANSION')
        build=_functions(trees['tools/integration_distribution.py'])['build']
        dictionaries=[n for n in ast.walk(build) if isinstance(n,ast.Dict)]
        inv=next(n for n in dictionaries if any(isinstance(k,ast.Constant) and k.value=='self_contained' for k in n.keys))
        fields={k.value:v for k,v in zip(inv.keys,inv.values) if isinstance(k,ast.Constant)}
        for key,value in (('self_contained',False),('signature','NOT_IMPLEMENTED'),('trust_root','NOT_SELECTED'),('host_manifest_qualification','NOT_RUN'),('installed',False),('activated',False),('execution_authorized',False)):
            if _shape(fields.get(key))!=_shape(ast.Constant(value=value)):raise ValueError('M6_PACKAGE_ASSURANCE_PROMOTION')
        setup=files['plugins/golem/skills/golem-setup/SKILL.md'].data.decode();work=files['plugins/golem/skills/golem-work/SKILL.md'].data.decode()
        if 'name: golem-setup' not in setup or 'name: golem-work' not in work or 'not installation or connection management' not in work:raise ValueError('M6_SKILL_ROUTING')
        if 'golem_action_confirm' not in work or 'COMMIT_UNKNOWN' not in work or 'references/profiles.md' not in work:raise ValueError('M6_WORK_CONTRACT_MISSING')
        manifest=__import__('json').loads(files['plugins/golem/.codex-plugin/plugin.json'].data)
        if manifest['skills']!='./skills/' or manifest['extensions']['com.openai']['onboardingSkill']!='./skills/golem-setup/SKILL.md':raise ValueError('M6_SKILL_MANIFEST')
    except (KeyError,ValueError,StopIteration,TypeError,AttributeError,SyntaxError) as e:errors.append(('M6_CONTRACT_UNVERIFIED',str(e)))
    caps={cap['id']:cap for cap in ledger['capabilities']};seen=set()
    for row in backlog:
        cid=row['capability_id'];cap=caps.get(cid)
        if cid in seen or cap is None or tuple(cap['current_routes'])!=row['current_routes'] or tuple(cap['target_routes'])!=row['target_routes'] or tuple(cap['effects'])!=row['effects'] or cap['review_status']!='REVIEWED':errors.append(('M6_OWNER_BOUNDARY_CHANGED',cid))
        seen.add(cid)
        if not row['owner_backlog_retained'] or row['actual_installation']!='NOT_RUN' or row['native_execution_verified'] or not row['scope'] or not row['source_paths']:errors.append(('M6_OWNER_AUTHORITY_PROMOTION',cid))
    if len(backlog)!=83 or len(seen)!=83 or fingerprint(backlog)!=model['backlog_sha256']:errors.append(('M6_BACKLOG_DOMAIN_CHANGED',None))
    return M6Observation(tuple(names),len(backlog),checked,tuple(errors))
