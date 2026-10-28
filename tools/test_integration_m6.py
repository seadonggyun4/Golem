"""M6 isolated profiles/packages and existing owner-lifecycle doubles/fixtures."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch, AsyncMock
import integration_contract as c
import integration_feature_profiles as profiles
import integration_distribution as package
import integration_distribution_entry as entry
import integration_owner_maintenance as owner
import integration_install as install
import integration_update as update
import test_integration_install as installation_fixture
import test_integration_update as update_fixture

ROOT=Path(__file__).resolve().parents[1]

class FakeService:
    def __init__(self):self.names=['work_inspect','helper_execute','workspace_request'];self.calls=[]
    def tools(self):return self.names
    def call(self,name,args):self.calls.append((name,args));return {'state':'COMMIT_UNKNOWN','request_id':args.get('request_id'),'automatic_retry_allowed':False}

class ProfileBoundaries(unittest.TestCase):
    def test_unset_client_templates_never_select_optional_authority(self):
        values={'GOLEM_FEATURE_PROFILE':'quality','GOLEM_PROFILE_POLICY':'/never-read','GOLEM_PROFILE_POLICY_SHA256':'a'*64,'GOLEM_APPROVE_PROFILE_OWNER':'true'}
        for name in ('resource','helper','host'):
            values['GOLEM_'+name.upper()+'_POLICY']='${user_config.'+name+'_policy}'
            values['GOLEM_'+name.upper()+'_SHA256']='${user_config.'+name+'_sha256}'
        with patch.dict(os.environ,values,clear=True):
            args=entry.environment()
        for name in ('resource','helper','host'):
            self.assertIsNone(args[name]);self.assertIsNone(args[name+'_digest'])
        with patch.object(entry.actions,'Policy'),patch.object(entry.mutations,'Service'):
            entry.configure(**args)
        for name,consent in (('resource','approve_resources'),('helper','approve_helpers'),('host','approve_host')):
            with self.assertRaises(c.IntegrationError):entry.configure(**{**args,consent:True})
            with self.assertRaises(c.IntegrationError):entry.configure(**{**args,name:'/concrete-owner-file'})

    def test_every_profile_is_current_owner_intersection_and_direct_call_is_checked(self):
        for name in profiles.NAMES:
            backend=FakeService();scoped=profiles.Scoped(backend,name)
            self.assertEqual(scoped.tools(),sorted(set(backend.names)&set(profiles.definition(name)['tools'])))
            if 'helper_execute' not in scoped.tools():
                with self.assertRaises(c.IntegrationError):scoped.call('helper_execute',{})
            backend.names=[]
            with self.assertRaises(c.IntegrationError):scoped.call('work_inspect',{})
            self.assertEqual(backend.calls,[])
    def test_project_discovery_metadata_uses_same_ceiling_without_mutating_backend(self):
        backend=FakeService();backend.names=['projects_list','work_inspect','helper_execute']
        original={'projects':[{'project_id':'p','work_id':'a','tools':['work_inspect','helper_execute'],'read_resources':[{'resource_id':'selected','files':[{'file_id':'hidden','tools':['helper_execute']}]},{'resource_id':'visible','files':[{'file_id':'usage','tools':['usage_read']}]}]}],
                  'audit_read_directory_cost':{'work_inspect':1,'helper_execute':3},'state':'AVAILABLE'}
        with patch.object(backend,'call',return_value=original):result=profiles.Scoped(backend,'read').call('projects_list',{})
        self.assertEqual(result['projects'][0]['tools'],['work_inspect']);self.assertEqual(result['projects'][0]['read_resources'],[{'resource_id':'visible','files':[{'file_id':'usage','tools':['usage_read']}]}])
        self.assertEqual(result['audit_read_directory_cost'],{'work_inspect':1});self.assertEqual(original['projects'][0]['tools'],['work_inspect','helper_execute'])

    def test_scope_does_not_change_uncertainty_or_original_request_id(self):
        backend=FakeService();scoped=profiles.Scoped(backend,'parallel')
        result=scoped.call('workspace_request',{'request_id':'original'})
        self.assertEqual(result['state'],'COMMIT_UNKNOWN');self.assertEqual(result['request_id'],'original');self.assertEqual(len(backend.calls),1)
    def test_no_profile_can_grant_policy_apply_or_unimplemented_scheduler(self):
        import integration_service as reads
        import integration_mutation_contract as actions
        for name in profiles.NAMES:
            value=profiles.definition(name)
            self.assertTrue(set(value['tools'])<=set(reads.SCHEMAS)|set(actions.NAMES))
            self.assertFalse(value['grants_created']);self.assertFalse(value['helper_enabled_by_default']);self.assertFalse(value['parallel_host_enabled_by_default'])
            self.assertEqual(len(value['implementation_required']),7)
            self.assertFalse({'install','approve','merge','schedule','policy_apply'}&set(value['tools']))
        self.assertEqual(set().union(*(set(profiles.definition(name)['tools']) for name in profiles.NAMES)),set(reads.SCHEMAS)|set(actions.NAMES))
    def test_no_policy_read_before_owner_consent_and_no_implicit_helper_or_host(self):
        with patch.object(entry.transfer,'Transfer',side_effect=AssertionError('no policy read')):
            with self.assertRaises(c.IntegrationError):entry.configure('read','/never-read','a'*64)
        for kwargs in ({'helper':'/h','helper_digest':'a'*64,'approve_helpers':True},{'host':'/h','host_digest':'a'*64,'approve_host':True},{'resource':'/r','resource_digest':'a'*64}):
            with self.assertRaises(c.IntegrationError):entry.configure('read','/never-read','a'*64,approve_owner=True,**kwargs)
    def test_entry_delegates_exact_d2_and_d4_policies(self):
        with patch.object(entry.transfer,'Transfer') as transfer,patch.object(entry.reads,'Service') as service:
            scoped,selected=entry.configure('prepare','/owner/policy','a'*64,approve_owner=True)
            transfer.assert_called_once_with(Path('/owner/policy'),'a'*64,approve_data_transfer=True);self.assertIs(scoped.service,service.return_value)
        with patch.object(entry.actions,'Policy') as policy,patch.object(entry.mutations,'Service') as service:
            scoped,selected=entry.configure('task','/owner/policy','b'*64,approve_owner=True)
            policy.assert_called_once_with(Path('/owner/policy'),'b'*64,approve_mutations=True);service.assert_called_once_with(policy.return_value,None,None,None)
    def test_optional_contract_arguments_require_all_flags_and_exact_family(self):
        with patch.object(entry.actions,'Policy') as policy,patch.object(entry.mutations,'Service'),patch.object(entry.helpers,'Helpers') as helper:
            entry.configure('quality','/owner/policy','a'*64,approve_owner=True,helper='/helper',helper_digest='b'*64,approve_helpers=True)
            helper.assert_called_once_with(Path('/helper'),'b'*64,policy.return_value,approve_helpers=True)
        with patch.object(entry.actions,'Policy') as policy,patch.object(entry.mutations,'Service'),patch.object(entry.hosts,'Hosts') as host:
            entry.configure('parallel','/owner/policy','a'*64,approve_owner=True,host='/host',host_digest='b'*64,approve_host=True)
            host.assert_called_once_with(Path('/host'),'b'*64,policy.return_value,approve_hosts=True)

class Packages(unittest.TestCase):
    def test_every_published_input_schema_has_mcp_object_root(self):
        import integration_service as reads
        import integration_mutation_contract as actions
        for name,rule in {**reads.SCHEMAS,**actions.SCHEMAS}.items():
            with self.subTest(tool=name):self.assertEqual(rule.get('type'),'object')
    @classmethod
    def setUpClass(cls):cls.raw=package.build('read')
    def expect(self,code,call):
        with self.assertRaises(c.IntegrationError) as error:call()
        self.assertEqual(error.exception.code,code)
    def test_claude_desktop_requires_descriptions_for_every_config_field(self):
        # Real Claude Desktop rejected M6 before preview when these were absent.
        for profile in profiles.NAMES:
            manifest=package.manifest(profile)
            for name,field in manifest['user_config'].items():
                with self.subTest(profile=profile,field=name):
                    self.assertIsInstance(field.get('description'),str)
                    self.assertGreater(len(field['description'].strip()),0)
                    if field['type']=='boolean':self.assertIs(field['default'],False)
    def altered(self,edit):
        with zipfile.ZipFile(io.BytesIO(self.raw)) as archive:files={name:archive.read(name) for name in archive.namelist()}
        edit(files);out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as archive:
            for name,data in files.items():
                info=zipfile.ZipInfo(name);info.external_attr=0o100600<<16;archive.writestr(info,data)
        return out.getvalue()
    def test_all_five_packages_are_deterministic_and_never_signed_or_installed(self):
        for name in profiles.NAMES:
            first=package.build(name);self.assertEqual(first,package.build(name))
            metadata,files=package.verify(first,c.sha(first))
            self.assertEqual(metadata['profile']['profile'],name);self.assertFalse(metadata['self_contained']);self.assertFalse(metadata['installed']);self.assertEqual(metadata['signature'],'NOT_IMPLEMENTED')
            self.assertIn('plugins/golem/skills/golem-work/SKILL.md',files)
            self.assertTrue(set(package.SCHEMAS)<=set(files))
            self.assertFalse(any('/.golem/' in path or path.endswith('.log') for path in files))
    def test_digest_content_and_undeclared_extra_file_are_rejected(self):
        self.expect('PACKAGE_DIGEST',lambda:package.verify(self.raw,'f'*64))
        raw=self.altered(lambda files:files.__setitem__('tools/integration_contract.py',b'pass'))
        self.expect('PACKAGE_CONTENT_CHANGED',lambda:package.verify(raw,c.sha(raw)))
        def extra(files):
            files['secret-policy.json']=b'private';inventory=c.decode(files['feature-package.json']);inventory['files']['secret-policy.json']=c.sha(b'private');files['feature-package.json']=c.encoded(inventory)
        raw=self.altered(extra);self.expect('PACKAGE_FILE_SCOPE',lambda:package.verify(raw,c.sha(raw)))
    def test_traversal_symlink_duplicate_and_expansion_limit_block(self):
        for path in ('../secret','/secret','a//b','a\\b'):
            raw=self.altered(lambda files:files.__setitem__(path,b'x'))
            self.expect('PACKAGE_PATH',lambda:package.verify(raw,c.sha(raw)))
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as archive:
            info=zipfile.ZipInfo('link');info.external_attr=0o120700<<16;archive.writestr(info,b'/secret')
        raw=out.getvalue();self.expect('PACKAGE_ENTRY',lambda:package.verify(raw,c.sha(raw)))
        out=io.BytesIO()
        with __import__('warnings').catch_warnings():
            __import__('warnings').simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(out,'w') as archive:
                for _ in range(2):
                    info=zipfile.ZipInfo('duplicate');info.external_attr=0o100600<<16;archive.writestr(info,b'x')
        raw=out.getvalue();self.expect('PACKAGE_ENTRY',lambda:package.verify(raw,c.sha(raw)))
        with patch.object(package,'MAX_FILE',1):self.expect('PACKAGE_LIMIT',lambda:package.verify(self.raw,c.sha(self.raw)))
    def test_extraction_is_new_private_destination_without_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();out=root/'package'
            result=package.extract(self.raw,c.sha(self.raw),out)
            self.assertEqual(result['installation'],'NOT_RUN');self.assertFalse(result['grants_created'])
            self.expect('PACKAGE_DESTINATION_EXISTS',lambda:package.extract(self.raw,c.sha(self.raw),out))
            before=(out/'feature-package.json').read_bytes();self.assertEqual(before,(out/'feature-package.json').read_bytes())
    def test_extracted_imports_and_producers_work_from_unrelated_cwd_without_dev_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();out=root/'package';package.extract(self.raw,c.sha(self.raw),out)
            code='import sys;sys.path.insert(0,'+repr(str(out/'tools'))+');import integration_install as i;import integration_feature_profiles as p;import integration_distribution as d;print(len(i.producer()),len(p.definition("read")["tools"]))'
            result=subprocess.run([sys.executable,'-I','-B','-c',code],cwd=root,env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'},capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr.decode());self.assertTrue(result.stdout.strip())
    def test_missing_import_skill_and_forged_assurance_are_refused(self):
        self.expect('PACKAGE_IMPORT_CLOSURE',lambda:package.closure({'tools/example.py':b'import integration_missing'}))
        def promote(files):
            value=c.decode(files['feature-package.json']);value['self_contained']=True;files['feature-package.json']=c.encoded(value)
        raw=self.altered(promote);self.expect('SCHEMA',lambda:package.verify(raw,c.sha(raw)))
        def false_root(files):
            value=c.decode(files['feature-package.json']);value['trust_root']='VERIFIED';files['feature-package.json']=c.encoded(value)
        raw=self.altered(false_root);self.expect('SCHEMA',lambda:package.verify(raw,c.sha(raw)))
    def test_optional_native_artifact_requires_explicit_sha_and_no_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'native';path.write_bytes(b'fixture-not-an-executable')
            self.expect('PACKAGE_NATIVE_CHANGED',lambda:package.build('parallel',native=path,native_sha256='f'*64,target='darwin-arm64'))
            raw=package.build('parallel',native=path,native_sha256=c.sha(path.read_bytes()),target='darwin-arm64')
            metadata,_=package.verify(raw,c.sha(raw));self.assertEqual(metadata['native']['abi_qualification'],'NOT_RUN')

class OwnerLifecycle(unittest.TestCase):
    def test_apply_requires_explicit_owner_and_original_plan_is_not_rewritten(self):
        plan={'operation':'install','bytes':'unchanged'}
        with self.assertRaises(c.IntegrationError):owner.dispatch('installation','apply','/never-read',plan,reviewed_sha256='a'*64)
        with patch.object(owner.install,'Installer') as manager:
            result=owner.dispatch('installation','apply','/state',plan,reviewed_sha256='a'*64,approve_owner=True)
            manager.return_value.apply.assert_called_once_with(plan,'a'*64,approve_installation=True,repair=False)
        with patch.object(owner.update,'Manager') as manager,patch.object(owner.r,'Registry'):
            owner.dispatch('maintenance','apply','/registry',{'operation':'switch'},reviewed_sha256='b'*64,approve_owner=True)
            manager.return_value.apply.assert_called_once_with({'operation':'switch'},'b'*64,approve_maintenance=True)
    def test_no_automatic_repair_or_alternate_operations(self):
        for kind,value in (('installation',{'operation':'repair'}),('maintenance',{'operation':'repair-switch'}),('maintenance',{'operation':'approve'})):
            with self.assertRaises(c.IntegrationError):owner.dispatch(kind,'apply','/never-read',value,reviewed_sha256='a'*64,approve_owner=True)
    def test_uncertain_existing_result_is_preserved_without_retry(self):
        with patch.object(owner.install,'Installer') as manager:
            manager.return_value.apply.side_effect=OSError('partial fixture')
            with self.assertRaises(OSError):owner.dispatch('installation','apply','/state',{'operation':'install'},reviewed_sha256='a'*64,approve_owner=True)
            self.assertEqual(manager.return_value.apply.call_count,1)

class RealTemporaryInstaller(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy'):
        locals()[name]=getattr(installation_fixture.Install,name)
    def setUp(self):installation_fixture.Install.setUp(self)
    def test_bridge_installs_and_removes_only_fixture_configs_losslessly(self):
        before=self.inventory();configs={row['config']:Path(row['config']).read_bytes() for row in self.request['targets']}
        plan=owner.dispatch('installation','plan',self.state,self.request,operation='install')
        result=owner.dispatch('installation','apply',self.state,plan,reviewed_sha256=c.sha(c.encoded(plan)),approve_owner=True)
        self.assertEqual(result['state'],'RELOAD_REQUIRED');self.assertEqual(result['client_activation'],'NOT_OBSERVED')
        self.assertEqual(owner.dispatch('installation','inspect',self.state,{'installation_id':'first'})['state'],'RELOAD_REQUIRED')
        remove=owner.dispatch('installation','plan',self.state,{'installation_id':'first','clients_stopped':'STOPPED_OWNER_ATTESTED'},operation='remove')
        owner.dispatch('installation','apply',self.state,remove,reviewed_sha256=c.sha(c.encoded(remove)),approve_owner=True)
        self.assertEqual(configs,{path:Path(path).read_bytes() for path in configs});self.assertEqual(before,self.inventory())
    def test_partial_config_and_drift_do_not_retry_or_repair(self):
        plan=owner.dispatch('installation','plan',self.state,self.request,operation='install')
        path=Path(self.request['targets'][0]['config']);path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(c.IntegrationError):owner.dispatch('installation','apply',self.state,plan,reviewed_sha256=c.sha(c.encoded(plan)),approve_owner=True)
        self.assertFalse((self.state/'installation-first').exists())

class RealTemporaryMaintenance(unittest.TestCase):
    for name in ('repin','api','invoke','capture','preflight','approve','query','expect','inventory','save_policy','observed'):
        locals()[name]=getattr(update_fixture.D5,name)
    def setUp(self):update_fixture.D5.setUp(self)
    def test_bridge_uses_existing_freeze_fence_and_original_d5_inspection(self):
        before=self.inventory();request={'project_id':'p','freeze_id':'fixture-freeze'}
        plan=owner.dispatch('maintenance','plan',self.registry.root,request,operation='freeze')
        owner.dispatch('maintenance','apply',self.registry.root,plan,reviewed_sha256=c.sha(c.encoded(plan)),approve_owner=True)
        result=owner.dispatch('maintenance','inspect',self.registry.root,{'project_id':'p'})
        self.assertEqual(result['lifecycle']['phase'],'FROZEN');self.assertEqual(before,self.inventory())
        self.expect('PROJECT_MAINTENANCE',lambda:self.invoke())
    def test_reload_ack_without_existing_probe_does_not_ready(self):
        self.freeze=update_fixture.D5.freeze.__get__(self);self.do=update_fixture.D5.do.__get__(self)
        self.freeze()
        request={'project_id':'p','reloads':[{'principal_id':'owner','client_id':'client-a','state':'RELOADED_OWNER_ATTESTED','probe':{'path':str(self.root/'missing-probe'),'sha256':'a'*64}}]}
        with self.assertRaises((c.IntegrationError,OSError)):owner.dispatch('maintenance','plan',self.registry.root,request,operation='ready')

class StartupAdmission(unittest.TestCase):
    def clock(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        return SimpleNamespace(monotonic=Mock(return_value=0),sleep=Mock())

    def test_configuration_rechecks_same_pins_only_after_startup_registry_contention(self):
        args={'profile':'task','policy':'/exact-owner-policy','digest':'a'*64,'approve_owner':True}
        clock=self.clock();expected=(object(),object())
        with patch.object(entry,'time',clock),patch.object(entry,'configure',side_effect=[c.IntegrationError('REGISTRY_BUSY'),expected]) as configure:
            self.assertEqual(entry._configure_startup(args),expected)
        self.assertEqual([v.kwargs for v in configure.call_args_list],[args,args])
        clock.sleep.assert_called_once_with(0.05)

    def test_other_contract_errors_and_io_never_wait_or_retry(self):
        for error in [c.IntegrationError(n) for n in ('PENDING_APPROVAL','ACTION_CHANGED','AUDIT_QUOTA','PROJECT_MAINTENANCE','COMMIT_UNKNOWN','PRODUCER_CHANGED')]+[OSError('partial publication')]:
            clock=self.clock()
            with patch.object(entry,'time',clock),patch.object(entry,'configure',side_effect=error) as configure:
                with self.assertRaises(type(error)):entry._configure_startup({})
            self.assertEqual(configure.call_count,1);clock.sleep.assert_not_called()

    def test_startup_wait_is_bounded_and_preserves_original_busy_error(self):
        clock=self.clock();clock.monotonic.side_effect=[0,entry.STARTUP_WAIT_SECONDS]
        error=c.IntegrationError('REGISTRY_BUSY')
        with patch.object(entry,'time',clock),patch.object(entry,'configure',side_effect=error) as configure:
            with self.assertRaises(c.IntegrationError) as caught:entry._configure_startup({})
        self.assertIs(caught.exception,error);self.assertEqual(configure.call_count,1);clock.sleep.assert_not_called()

    def participation(self,events,failures):
        from contextlib import contextmanager
        @contextmanager
        def enter(*args):
            events.append('enter')
            if failures:
                error=failures.pop(0)
                if error:raise error
            events.append('admitted')
            try:yield
            finally:events.append('released')
        return enter

    def exercise(self,events,failures,run):
        import asyncio
        from types import SimpleNamespace
        service=SimpleNamespace(profile={'family':'D4'})
        owner=SimpleNamespace(registry=object(),transfer=SimpleNamespace(value={'scopes':[]}))
        with patch.object(entry,'time',self.clock()),patch.object(entry.lifecycle,'participation',self.participation(events,failures)),patch.object(entry.mutation_mcp,'run',run):
            asyncio.run(entry.serve(service,owner))

    def test_participation_waits_before_serving_and_releases_original_context(self):
        events=[]
        async def serve(*args):events.append('serve')
        run=AsyncMock(side_effect=serve)
        self.exercise(events,[c.IntegrationError('REGISTRY_BUSY')],run)
        self.assertEqual(events,['enter','enter','admitted','serve','released']);run.assert_awaited_once()

    def test_failure_after_server_admission_cannot_reenter_or_redispatch(self):
        events=[];run=AsyncMock(side_effect=c.IntegrationError('REGISTRY_BUSY'))
        with self.assertRaises(c.IntegrationError):self.exercise(events,[],run)
        self.assertEqual(events,['enter','admitted','released']);run.assert_awaited_once()

    def test_nonbusy_participation_failure_cannot_start_server(self):
        events=[];run=AsyncMock()
        with self.assertRaises(c.IntegrationError):self.exercise(events,[c.IntegrationError('AUDIT_QUOTA')],run)
        self.assertEqual(events,['enter']);run.assert_not_awaited()

    def test_tool_inventory_wait_rechecks_metadata_only_and_stops_at_deadline(self):
        import asyncio
        import anyio
        from types import SimpleNamespace
        from unittest.mock import Mock
        service=SimpleNamespace(tools=Mock(),call=Mock(side_effect=AssertionError('no action')))
        clock=self.clock();run=AsyncMock(side_effect=[c.IntegrationError('REGISTRY_BUSY'),['work_inspect']])
        with patch.object(entry.readonly,'time',clock),patch.object(anyio.to_thread,'run_sync',run),patch.object(anyio,'sleep',AsyncMock()) as sleep:
            self.assertEqual(asyncio.run(entry.readonly.listed_tools(service)),['work_inspect'])
            sleep.assert_awaited_once_with(0.05)
        self.assertEqual([v.args for v in run.call_args_list],[(service.tools,),(service.tools,)])
        service.call.assert_not_called()
        clock.monotonic.side_effect=[0,5]
        with patch.object(entry.readonly,'time',clock),patch.object(anyio.to_thread,'run_sync',AsyncMock(side_effect=c.IntegrationError('REGISTRY_BUSY'))) as run:
            with self.assertRaises(c.IntegrationError):asyncio.run(entry.readonly.listed_tools(service))
            run.assert_awaited_once()

    def test_tool_inventory_other_errors_are_not_retried(self):
        import asyncio
        import anyio
        from types import SimpleNamespace
        for code in ('ACTION_CHANGED','AUDIT_QUOTA','COMMIT_UNKNOWN','PENDING_APPROVAL'):
            run=AsyncMock(side_effect=c.IntegrationError(code))
            with patch.object(entry.readonly,'time',self.clock()),patch.object(anyio.to_thread,'run_sync',run),patch.object(anyio,'sleep',AsyncMock()) as sleep:
                with self.assertRaises(c.IntegrationError):asyncio.run(entry.readonly.listed_tools(SimpleNamespace(tools=object())))
                run.assert_awaited_once();sleep.assert_not_awaited()



class ProjectManagement(unittest.TestCase):
    """All projects, decisions and capture results are disposable fixture data."""
    def setUp(self):
        import test_integration_d2 as d2
        import integration_registry as registry
        import integration_service as reads
        import integration_transfer as transfer
        d2.D2.setUp(self)
        self.management_registry=registry.Registry.create(self.root/'management-registry',approve_local_owner=True)
        self.queue=self.project/'queue';self.queue.mkdir(mode=0o700)
        self.input=self.root/'selected.json';self.input.write_bytes(c.encoded({'operation':'approve'}));self.input.chmod(0o600)
        self.management_path=self.root/'management.json'
        self.value={'schema':'golem.project-management.v1','base_policy':{'path':str(self.policy_path),'sha256':self.digest},
            'registry':str(self.management_registry.root),'registry_identity':self.management_registry.root_identity,
            'destination':'MODEL_SERVICE','destination_id':'synthetic-client','data_class':'APPROVED_MANAGEMENT_CONTENT','max_result_bytes':8388608,
            'producer':owner.management_producer(),'projects':[{'project_id':'p','work_id':'a',
            'targets':[self.target('queue',self.queue,'directory'),self.target('new',self.project/'new-queue','new_directory'),self.target('work',self.work,'work')],
            'inputs':[{'input_id':'selected','file':registry.file_pin(self.input)}],
            'actions':[{'action_id':'status','request':{'operation':'daemon_status','target_id':'queue'},
                        'effects':['NATIVE_READ','AUDIT_WRITE'],'timeout_seconds':5}]}]}
        self.base=transfer.Transfer(self.policy_path,self.digest,approve_data_transfer=True)
        self.base_service=profiles.Scoped(reads.Service(self.base),'read');self.save_management()

    for name in ('approve','query','expect','inventory'):
        import test_integration as base_fixture
        locals()[name]=getattr(base_fixture.Integration,name)
    for name in ('save_policy',):
        import test_integration_d2 as d2_fixture
        locals()[name]=getattr(d2_fixture.D2,name)

    def target(self,identity,path,kind):
        import integration_registry as registry
        return {'target_id':identity,'kind':kind,'path':str(path),'parent_identity':registry.identity(path.parent),
            'identity':registry.identity(path) if path.is_dir() else None,'expected_sha256':owner.management_snapshot(path)}
    def save_management(self):
        self.management_path.write_bytes(c.encoded(self.value));self.management_path.chmod(0o600)
        self.management=owner.ManagementPolicy(self.management_path,c.sha(self.management_path.read_bytes()),self.base,approve_management=True)
        self.api=owner.ManagementService(self.base_service,self.management)
    def args(self,request='one'):return {'project_id':'p','action_id':'status','request_id':request}
    def captured(self,argv,output,*args,**kwargs):
        import execution_record as records
        records.save(output/'stdout.log',c.encoded({'fixture_result':True,'execution_authorized':False}))
        records.save(output/'stderr.log',b'')
        return {'reason':'EXIT','returncode':0,'recording':'RECORDED'}
    def repin_native(self,cli):
        import integration_registry as registry
        import integration_service as reads
        import integration_transfer as transfer
        self.enrollment['project']['cli']=registry.file_pin(cli)
        self.registry=registry.Registry.create(self.root/'new-base-registry',approve_local_owner=True);self.approve()
        self.policy['registry']=str(self.registry.root);self.policy['registry_identity']=self.registry.root_identity
        self.policy['producer']=transfer.producer();self.save_policy()
        self.base=transfer.Transfer(self.policy_path,self.digest,approve_data_transfer=True)
        self.base_service=profiles.Scoped(reads.Service(self.base),'read')
        self.value['base_policy']['sha256']=self.digest;self.save_management()

    def test_default_disabled_and_consent_before_policy_reads(self):
        disabled=owner.ManagementService(self.base_service)
        self.assertFalse(set(owner.MANAGEMENT_SCHEMAS)&set(disabled.tools()))
        self.expect('MANAGEMENT_DISABLED',lambda:disabled.call('management_catalog',{'project_id':'p'}))
        with patch.object(owner.r,'real_path',side_effect=AssertionError('no policy read')):
            self.expect('MANAGEMENT_APPROVAL_REQUIRED',lambda:owner.ManagementPolicy('/never-read','a'*64,self.base))
    def test_catalog_and_preparation_are_non_authoritative_and_do_not_capture(self):
        before=self.inventory()
        with patch.object(owner.records,'capture',side_effect=AssertionError('no dispatch')):
            catalog=self.api.call('management_catalog',{'project_id':'p'})
            prepared=self.api.call('management_prepare',{'project_id':'p','request':{'operation':'daemon_status','target_id':'queue'}})
        self.assertEqual(len(catalog['operations']),18);self.assertEqual(prepared['state'],'PREPARED')
        self.assertFalse(prepared['approval_created']);self.assertFalse(prepared['execution_authorized'])
        self.assertEqual(before,self.inventory());self.assertEqual(list(self.management_registry.root.iterdir()),[])
    def test_schema_cannot_smuggle_argv_shell_paths_or_unknown_operations(self):
        for request in ({'operation':'shell','target_id':'queue'},{'operation':'daemon_status','target_id':'queue','argv':['sh']},{'operation':'daemon_status','target_id':'/secret'}):
            with self.assertRaises(c.IntegrationError):self.api.call('management_prepare',{'project_id':'p','request':request})
    def test_policy_and_input_drift_block_before_capture(self):
        self.management_path.write_bytes(c.encoded({**self.value,'registry':'/other'}))
        self.expect('MANAGEMENT_POLICY_CHANGED',lambda:self.api.tools())
        self.save_management();self.value['projects'][0]['actions'][0]['request']={'operation':'daemon_submit','target_id':'queue','input_id':'selected'};self.save_management()
        self.input.write_bytes(b'changed')
        with patch.object(owner.records,'capture') as capture:
            self.expect('MANAGEMENT_INPUT_CHANGED',lambda:self.api.call('management_request',self.args()))
            capture.assert_not_called()
    def test_target_drift_and_new_destination_reuse_block(self):
        (self.queue/'drift').write_bytes(b'changed')
        result=self.api.call('management_prepare',{'project_id':'p','request':{'operation':'daemon_status','target_id':'queue'}})
        self.assertEqual(result['code'],'MANAGEMENT_TARGET_STALE')
        (self.project/'new-queue').mkdir()
        result=self.api.call('management_prepare',{'project_id':'p','request':{'operation':'daemon_init','target_id':'new'}})
        self.assertEqual(result['code'],'MANAGEMENT_DESTINATION_EXISTS')
    def test_effects_and_foreign_scope_are_checked(self):
        self.value['projects'][0]['actions'][0]['effects']=['NATIVE_WRITE','AUDIT_WRITE'];self.save_management()
        with patch.object(owner.records,'capture') as capture:
            self.expect('MANAGEMENT_EFFECTS_SCOPE',lambda:self.api.call('management_request',self.args()))
            self.expect('MANAGEMENT_PROJECT_SCOPE',lambda:self.api.call('management_catalog',{'project_id':'other'}));capture.assert_not_called()
    def test_exact_once_and_read_only_historical_lookup(self):
        with patch.object(owner.records,'capture',side_effect=self.captured) as capture:
            first=self.api.call('management_request',self.args());self.assertEqual(first['state'],'RECORDED')
            old=self.api.call('management_result',self.args());self.assertTrue(old['historical_result'])
            other=self.api.call('management_request',self.args('different'))
            self.assertEqual(other['state'],'ACTION_ALREADY_DISPATCHED');self.assertEqual(capture.call_count,1)
    def test_timeout_missing_corrupt_results_do_not_redispatch(self):
        with patch.object(owner.records,'capture',side_effect=OSError('lost')) as capture:
            first=self.api.call('management_request',self.args());self.assertEqual(first['state'],'COMMIT_UNKNOWN')
            self.assertEqual(self.api.call('management_result',self.args())['state'],'COMMIT_UNKNOWN')
            self.assertEqual(self.api.call('management_request',self.args('different'))['state'],'ACTION_ALREADY_DISPATCHED')
            self.assertEqual(capture.call_count,1)
    def test_corrupt_stdout_blocks_stored_result(self):
        with patch.object(owner.records,'capture',side_effect=self.captured):self.api.call('management_request',self.args())
        directory=next(self.management_registry.root.glob('management-*'))
        if directory.is_file():directory=next(p for p in self.management_registry.root.glob('management-*') if p.is_dir())
        (directory/'stdout.log').write_bytes(b'corrupt')
        self.assertEqual(self.api.call('management_result',self.args())['state'],'COMMIT_UNKNOWN')
    def test_result_lookup_missing_never_creates_intent(self):
        self.assertEqual(self.api.call('management_result',self.args())['state'],'NOT_FOUND')
        self.assertEqual(list(self.management_registry.root.iterdir()),[])
    def test_recovery_requires_exact_stopped_attestation(self):
        request={'operation':'daemon_recover','target_id':'queue','stopped_attestation_id':'selected'}
        result=self.api.call('management_prepare',{'project_id':'p','request':request})
        self.assertEqual(result['code'],'MANAGEMENT_STOP_ATTESTATION')
    def test_approval_decision_is_original_bytes_and_core_not_python(self):
        self.value['projects'][0]['actions'][0].update(request={'operation':'approval_decide','target_id':'work','input_id':'selected','decision':'approve'},effects=['NATIVE_WRITE','APPROVAL_DECISION','AUDIT_WRITE']);self.save_management()
        raw=self.input.read_bytes()
        def capture(argv,output,*a,**kw):
            self.assertEqual(argv[3:6],['approval','call',str(self.work)])
            self.assertEqual(Path(argv[-1]).read_bytes(),raw)
            return self.captured(argv,output,*a,**kw)
        with patch.object(owner.records,'capture',side_effect=capture):self.assertEqual(self.api.call('management_request',self.args())['state'],'RECORDED')
        self.assertEqual(self.input.read_bytes(),raw)
    def test_fixed_native_routes_have_no_unbounded_daemon_or_shell(self):
        request={'operation':'daemon_run_once','target_id':'queue'}
        _,native,target,inputs,_=self.management.request('p',request)
        argv=owner.management_argv(native,target,inputs,request)
        self.assertEqual(argv,['daemon','run',str(self.queue),'--worker',native['cli']['path'],'--once'])
        self.assertNotIn('daemon_run',owner.MANAGEMENT_OPERATIONS)
    def test_native_pure_probe_uses_real_core_without_service_or_approval(self):
        native=os.environ.get('GOLEM_M6_MANAGEMENT_CLI')
        if not native:self.skipTest('explicit isolated native CLI not supplied')
        self.repin_native(Path(native))
        self.value['projects'][0]['actions'][0].update(request={'operation':'adapter_noop_probe','target_id':'work'})
        self.save_management();before=self.inventory();result=self.api.call('management_request',self.args())
        self.assertEqual(result['state'],'RECORDED',result);self.assertEqual(before,self.inventory())
    def test_claude_manifest_and_all_tools_are_closed_object_schemas(self):
        for name,rule in owner.MANAGEMENT_SCHEMAS.items():self.assertEqual(rule['type'],'object',name)
        for profile in profiles.NAMES:
            manifest=package.manifest(profile)
            self.assertFalse(manifest['user_config']['approve_management']['default'])
            self.assertEqual(manifest['server']['mcp_config']['args'][-2:],['tools/integration_owner_maintenance.py','mcp'])
        self.assertEqual(c.decode(package.schema_payloads()['schemas/project-management.json'])['policy'],owner.MANAGEMENT_POLICY)

    def test_pending_and_partial_publication_never_dispatch_again(self):
        def pending(argv,output,*a,**kw):
            owner.records.save(output/'stdout.log',c.encoded({'state':'PENDING_APPROVAL'}));owner.records.save(output/'stderr.log',b'')
            return {'reason':'EXIT','returncode':0,'recording':'RECORDED'}
        with patch.object(owner.records,'capture',side_effect=pending) as capture:
            self.assertEqual(self.api.call('management_request',self.args())['state'],'PENDING_APPROVAL')
            self.assertEqual(self.api.call('management_request',self.args('other'))['state'],'ACTION_ALREADY_DISPATCHED')
            self.assertEqual(capture.call_count,1)
    def test_disclosure_mismatch_and_symlinks_are_rejected(self):
        self.value['destination_id']='other-client'
        self.expect('MANAGEMENT_DISCLOSURE_SCOPE',self.save_management)
        self.value['destination_id']='synthetic-client';self.save_management()
        (self.queue/'link').symlink_to(self.input)
        with self.assertRaises(c.IntegrationError):owner.management_snapshot(self.queue)
    def test_process_loss_after_intent_cannot_be_retried_under_new_id(self):
        with patch.object(owner.records,'capture',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.api.call('management_request',self.args())
        self.assertEqual(self.api.call('management_result',self.args())['state'],'COMMIT_UNKNOWN')
        with patch.object(owner.records,'capture') as capture:
            self.assertEqual(self.api.call('management_request',self.args('new'))['state'],'ACTION_ALREADY_DISPATCHED');capture.assert_not_called()
    def test_each_fixed_route_uses_native_cli_and_selected_inputs_only(self):
        native={'cli':{'path':'/native/golem'}};target={'path':'/selected/target'};inputs={'selected':{'path':'/selected/input'}}
        for op,(_,fields,_) in owner.MANAGEMENT_OPERATIONS.items():
            request={'operation':op,'target_id':'target'}
            for field in fields:request[field]={'input_id':'selected','anchor':'a'*64,'decision':'approve','stopped_attestation_id':'selected','input_format':'json','output_format':'msgpack','launch_action_id':'start','launch_request_id':'one'}[field]
            argv=owner.management_argv(native,target,inputs,request)
            if op in ('adapter_probe','candidate_serve','candidate_stop'):
                self.assertEqual(argv,[]);continue
            self.assertTrue(argv[0] in ('daemon','journal','adapter','doctor','approval'))
            self.assertNotIn('sh',argv);self.assertNotIn('bash',argv)
    def sdk_client(self,client):
        try:
            from mcp import ClientSession,StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:self.skipTest('explicit MCP SDK not available')
        import asyncio
        self.cli.write_text('#!'+str(Path(sys.executable).resolve())+'\nimport json\nprint(json.dumps({"fixture_result":True,"execution_authorized":False}))\n');self.cli.chmod(0o700)
        self.repin_native(self.cli)
        env={**os.environ,'GOLEM_FEATURE_PROFILE':'read','GOLEM_PROFILE_POLICY':str(self.policy_path),'GOLEM_PROFILE_POLICY_SHA256':self.digest,'GOLEM_APPROVE_PROFILE_OWNER':'true',
            'GOLEM_MANAGEMENT_POLICY':str(self.management_path),'GOLEM_MANAGEMENT_SHA256':self.management.digest,'GOLEM_APPROVE_MANAGEMENT':'true'}
        script=ROOT/'tools/integration_owner_maintenance.py'
        if client=='Codex':
            code='import sys;sys.path[:0]='+repr([str(ROOT/'tools'),*sys.path])+';import integration_owner_maintenance as M;sys.argv=["integration_owner_maintenance.py","mcp"];sys.exit(M.main())'
            args=['-I','-B','-c',code]
        else:args=['-B',str(script),'mcp']
        async def run():
            params=StdioServerParameters(command=sys.executable,args=args,env=env)
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer) as session:
                    await session.initialize();tools=await session.list_tools()
                    names={tool.name for tool in tools.tools};self.assertTrue({'golem_'+n for n in owner.MANAGEMENT_SCHEMAS}<=names)
                    for name,query in [('management_catalog',{'project_id':'p'}),('management_prepare',{'project_id':'p','request':{'operation':'daemon_status','target_id':'queue'}}),('management_request',self.args()),('management_result',self.args())]:
                        reply=await session.call_tool('golem_'+name,query);self.assertFalse(reply.is_error)
                        value=c.decode(reply.content[0].text.encode());self.assertFalse(value['execution_authorized'])
                        if name=='management_prepare':self.assertEqual(value['state'],'PREPARED')
                        if name=='management_result':self.assertTrue(value['stored_result'])
        asyncio.run(run())
    def test_codex_stdio_declaration_and_actual_tool_calls(self):self.sdk_client('Codex')
    def test_claude_entrypoint_and_actual_tool_calls(self):self.sdk_client('Claude')

    def test_work_delegation_does_not_change_existing_unknown_result(self):
        backend=FakeService();api=owner.ManagementService(backend)
        result=api.call('workspace_request',{'request_id':'original'})
        self.assertEqual(result['state'],'COMMIT_UNKNOWN');self.assertEqual(result['request_id'],'original')
        self.assertEqual(len(backend.calls),1)
    def test_common_entry_reuses_startup_wait_only_before_serving(self):
        import asyncio
        from contextlib import nullcontext
        from types import SimpleNamespace
        backend=SimpleNamespace(profile={'family':'D4'});base_owner=SimpleNamespace(registry=object(),transfer=SimpleNamespace(value={'scopes':[]}))
        def no_run(coroutine):coroutine.close()
        with patch.dict(os.environ,{},clear=True),patch.object(entry,'_configure_startup',return_value=(backend,base_owner)),patch.object(owner.life,'participation',side_effect=[c.IntegrationError('REGISTRY_BUSY'),nullcontext()]) as participation,patch.object(entry,'_startup_pause') as pause,patch.object(asyncio,'run',side_effect=no_run):
            self.assertEqual(owner.management_main([]),0);self.assertEqual(participation.call_count,2);pause.assert_called_once()

    def test_existing_maintenance_fence_prevents_any_management_dispatch(self):
        with self.registry.locked(exclusive=True):owner.life.publish(self.registry,'p','FROZEN','fixture-freeze',{})
        with patch.object(owner.records,'capture') as capture:
            self.expect('PROJECT_MAINTENANCE',lambda:self.api.call('management_request',self.args()))
            capture.assert_not_called()
        self.assertEqual(list(self.management_registry.root.iterdir()),[])
    def test_unknown_effect_blocks_another_preapproved_action(self):
        self.value['projects'][0]['actions'].append({**self.value['projects'][0]['actions'][0],'action_id':'another'});self.save_management()
        with patch.object(owner.records,'capture',side_effect=OSError('lost')) as capture:
            self.assertEqual(self.api.call('management_request',self.args())['state'],'COMMIT_UNKNOWN')
            other={**self.args('new-request'),'action_id':'another'}
            self.expect('MANAGEMENT_PROJECT_QUARANTINED',lambda:self.api.call('management_request',other))
            self.assertEqual(capture.call_count,1)

    def test_management_registry_must_not_alias_original_approval_registry(self):
        self.value['registry']=str(self.registry.root);self.value['registry_identity']=self.registry.root_identity
        self.expect('MANAGEMENT_REGISTRY_SEPARATION',self.save_management)
    def test_target_inventory_limit_blocks_before_any_native_process(self):
        for n in range(4097):(self.queue/str(n)).touch()
        with patch.object(owner.records,'capture') as capture:
            result=self.api.call('management_prepare',{'project_id':'p','request':{'operation':'daemon_status','target_id':'queue'}})
            self.assertEqual(result['code'],'MANAGEMENT_TARGET_LIMIT');capture.assert_not_called()

    def test_result_larger_than_request_limit_is_preserved_for_historical_read(self):
        def capture(argv,output,*a,**kw):
            owner.records.save(output/'stdout.log',c.encoded({'payload':'x'*300000}));owner.records.save(output/'stderr.log',b'')
            return {'reason':'EXIT','returncode':0,'recording':'RECORDED'}
        with patch.object(owner.records,'capture',side_effect=capture) as called:
            self.assertEqual(self.api.call('management_request',self.args())['state'],'RECORDED')
            result=self.api.call('management_result',self.args());self.assertEqual(len(result['native_result']['payload']),300000)
            self.assertTrue(result['historical_result']);self.assertEqual(called.call_count,1)

    def test_nonobject_approval_input_is_question_not_protocol_crash(self):
        import integration_registry as registry
        self.input.write_bytes(b'[]');self.value['projects'][0]['inputs'][0]['file']=registry.file_pin(self.input);self.save_management()
        result=self.api.call('management_prepare',{'project_id':'p','request':{'operation':'approval_decide','target_id':'work','input_id':'selected','decision':'approve'}})
        self.assertEqual(result['state'],'NEEDS_OWNER_INPUT');self.assertEqual(result['code'],'MANAGEMENT_DECISION_MISMATCH')
    def test_malformed_capture_observation_retains_unknown_and_never_reexecutes(self):
        with patch.object(owner.records,'capture',return_value={}) as capture:
            self.assertEqual(self.api.call('management_request',self.args())['state'],'COMMIT_UNKNOWN')
            self.assertEqual(self.api.call('management_request',self.args('new'))['state'],'ACTION_ALREADY_DISPATCHED');self.assertEqual(capture.call_count,1)
    def test_corrupt_history_blocks_another_action_without_dispatch(self):
        guard=self.management_registry.root/('management-action-'+'a'*64+'.json');guard.write_bytes(b'[]');guard.chmod(0o600)
        with patch.object(owner.records,'capture') as capture:
            self.expect('MANAGEMENT_HISTORY_UNVERIFIED',lambda:self.api.call('management_request',self.args()))
            capture.assert_not_called()

if __name__=='__main__':unittest.main()


class DeliveryThree(unittest.TestCase):
    """No live candidate service: host launch/stop uses owned process doubles."""
    for name in ('setUp','approve','query','expect','inventory','save_policy','target','save_management','args','repin_native'):
        locals()[name]=getattr(ProjectManagement,name)
    def select(self,operation,target='work',**fields):
        self.value['projects'][0]['inputs']=[{'input_id':'selected','file':owner.r.file_pin(self.input)}]
        request={'operation':operation,'target_id':target,**fields}
        self.value['projects'][0]['actions'][0].update(request=request,effects=list(owner.MANAGEMENT_OPERATIONS[operation][2]))
        self.save_management()
    def test_binary_input_and_output_exact_and_historical_lookup_never_dispatch(self):
        self.input.write_bytes(b'\x00\xffbinary\x00')
        self.select('adapter_convert',input_id='selected',input_format='msgpack',output_format='json')
        calls=[]
        def process(argv,out,cwd,timeout,limit,**kw):
            self.assertEqual(Path(kw['stdin']).read_bytes(),b'\x00\xffbinary\x00');calls.append(argv)
            owner.records.save(out/'stdout.log',b'\x00\xffresult');return {'reason':'EXIT','returncode':0}
        with patch.object(owner,'delivery_process',side_effect=process):
            result=self.api.call('management_request',self.args());again=self.api.call('management_result',self.args())
        import base64
        self.assertEqual(base64.b64decode(result['native_result']['data']),b'\x00\xffresult');self.assertTrue(again['historical_result']);self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][-4:],['adapter','convert','msgpack','json'])
    def test_real_native_json_msgpack_roundtrip_uses_original_codec(self):
        native=os.environ.get('GOLEM_M6_MANAGEMENT_CLI')
        if not native:self.skipTest('explicit isolated native CLI not supplied')
        self.repin_native(Path(native))
        envelope=subprocess.check_output([native,'adapter','noop','probe'],env=owner.backend.ENVIRONMENT)
        self.input.write_bytes(envelope);self.select('adapter_convert',input_id='selected',input_format='json',output_format='msgpack')
        result=self.api.call('management_request',self.args());self.assertEqual(result['state'],'RECORDED',result)
        import base64
        packed=base64.b64decode(result['native_result']['data'])
        restored=subprocess.check_output([native,'adapter','convert','msgpack','json'],input=packed,env=owner.backend.ENVIRONMENT)
        self.assertEqual(c.decode(restored),c.decode(envelope))
    def probe_input(self):
        self.executable=self.root/'fixture-adapter';self.executable.write_bytes(b'fixture only');self.executable.chmod(0o700)
        self.descriptor={'schema':'golem.management-probe.v1','executable':owner.r.file_pin(self.executable),'cwd':str(self.queue),'timeout_ms':100}
        self.input.write_bytes(c.encoded(self.descriptor));self.select('adapter_probe','queue',input_id='selected')
    def test_probe_exact_executable_hash_cwd_timeout_and_explicit_effects(self):
        self.probe_input();calls=[]
        def process(argv,out,*a,**kw):
            calls.append(argv);owner.records.save(out/'stdout.log',b'{"fixture":true}');return {'reason':'EXIT','returncode':0}
        with patch.object(owner,'delivery_process',side_effect=process):result=self.api.call('management_request',self.args())
        self.assertEqual(result['state'],'RECORDED')
        self.assertEqual(calls[0][3:],['adapter','probe',str(self.executable),self.descriptor['executable']['sha256'],str(self.queue),'100','--allow-process'])
        self.assertTrue({'NETWORK','CREDENTIAL','EXPORT'}<=set(result['effects']))
    def test_probe_drift_extra_argv_and_read_effects_do_not_launch(self):
        self.probe_input();self.executable.write_bytes(b'drift')
        with patch.object(owner,'delivery_process') as process:
            self.expect('MANAGEMENT_EXECUTABLE_CHANGED',lambda:self.api.call('management_request',self.args()));process.assert_not_called()
        self.probe_input();self.descriptor['argv']=['sh'];self.input.write_bytes(c.encoded(self.descriptor));self.select('adapter_probe','queue',input_id='selected')
        with patch.object(owner,'delivery_process') as process:
            self.expect('SCHEMA',lambda:self.api.call('management_request',self.args()));process.assert_not_called()
    def test_failed_conversion_quarantines_project_and_cannot_retry_new_id(self):
        self.select('adapter_convert',input_id='selected',input_format='json',output_format='msgpack')
        with patch.object(owner,'delivery_process',return_value={'reason':'TIMEOUT','returncode':None}) as process:
            self.assertEqual(self.api.call('management_request',self.args())['state'],'COMMIT_UNKNOWN')
            self.assertEqual(self.api.call('management_request',self.args('other'))['state'],'ACTION_ALREADY_DISPATCHED');self.assertEqual(process.call_count,1)
    def test_owned_supervisor_has_no_deadline_no_pid_adoption_and_disconnect_cleanup(self):
        import threading
        observed={}
        def process(argv,out,cwd,timeout,limit,**kw):
            observed['timeout']=timeout;kw['started'].set();kw['stop'].wait(5);return {'reason':'STOP_REQUESTED','returncode':0}
        directory=self.root/'supervisor';directory.mkdir(mode=0o700)
        with patch.object(owner,'delivery_process',side_effect=process):
            host=owner.ManagedHost(['/fixture/native','candidate','serve'],directory,'p','a'*64,4096);host.start()
            self.api.hosts[('p','status','one')]=host
            status=self.api.call('management_host_status',self.args());self.assertTrue(status['active']);self.assertIsNone(observed['timeout']);self.assertEqual(status['host_ready'],'NOT_VERIFIED')
            self.api.close();self.assertFalse(host.active());self.assertFalse(host.observation()['all_workers_stopped_attested'])
        other=owner.ManagementService(self.base_service,self.management)
        self.assertEqual(other.call('management_host_status',self.args())['state'],'COMMIT_UNKNOWN')
    def test_host_requires_original_d4_and_does_not_turn_read_scope_into_service_grant(self):
        self.input.write_bytes(c.encoded({'schema':'golem.management-host.v1','host_policy':{'path':'/unread','sha256':'a'*64},'host_id':'selected'}))
        self.select('candidate_serve',input_id='selected')
        with patch.object(owner,'ManagedHost') as host:
            self.expect('MANAGEMENT_HOST_REQUIRES_D4',lambda:self.api.call('management_request',self.args()));host.assert_not_called()
    def test_process_runner_raw_stdin_bound_and_timeout_without_service(self):
        output=self.root/'binary-run';output.mkdir(mode=0o700);self.input.write_bytes(b'\x00\xff')
        result=owner.delivery_process([sys.executable,'-I','-c','import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())'],output,output,5,4096,stdin=self.input)
        self.assertEqual(result['returncode'],0);self.assertEqual((output/'stdout.log').read_bytes(),b'\x00\xff')
        second=self.root/'limit-run';second.mkdir(mode=0o700)
        result=owner.delivery_process([sys.executable,'-I','-c','print("x"*10000)'],second,second,5,100)
        self.assertEqual(result['reason'],'OUTPUT_LIMIT')
        third=self.root/'timeout-run';third.mkdir(mode=0o700)
        result=owner.delivery_process([sys.executable,'-I','-c','import time;time.sleep(2)'],third,third,.1,4096)
        self.assertEqual(result['reason'],'TIMEOUT');self.assertIsNotNone(result['returncode'])
    def test_raw_result_tamper_and_missing_host_lifetime_never_become_current_success(self):
        self.select('adapter_convert',input_id='selected',input_format='json',output_format='msgpack')
        def process(argv,out,*a,**kw):owner.records.save(out/'stdout.log',b'raw');return {'reason':'EXIT','returncode':0}
        with patch.object(owner,'delivery_process',side_effect=process):self.api.call('management_request',self.args())
        record=next(p for p in self.management_registry.root.glob('management-*') if p.is_dir());(record/'stdout.log').write_bytes(b'tamper')
        self.assertEqual(self.api.call('management_result',self.args())['state'],'COMMIT_UNKNOWN')

    def test_owned_record_boundary_supervises_fixture_child_without_service(self):
        import threading
        stop=threading.Event();timer=threading.Timer(.1,stop.set);timer.start();self.addCleanup(timer.join)
        output=self.root/'owned-boundary';output.mkdir(mode=0o700)
        result=owner.delivery_process([sys.executable,'-I','-c','import time;time.sleep(2)'],output,output,None,4096,stop=stop)
        self.assertEqual(result['reason'],'STOP_REQUESTED');self.assertIsNotNone(result['returncode'])
        self.assertTrue((output/'execution-private/result.json').is_file())
        with self.assertRaises(ValueError):owner.records.run_private([sys.executable],destination=self.root/'invalid',timeout=None)
    def test_stdin_backpressure_cannot_escape_deadline(self):
        self.input.write_bytes(b'x'*1048576);output=self.root/'backpressure';output.mkdir(mode=0o700)
        result=owner.delivery_process([sys.executable,'-I','-c','import time;time.sleep(2)'],output,output,.1,4096,stdin=self.input)
        self.assertEqual(result['reason'],'TIMEOUT')

    def test_host_config_bytes_are_rechecked_before_staging_and_launch(self):
        config=self.root/'changed-config.json';config.write_bytes(b'new bytes');config.chmod(0o600)
        row={'config':{'path':str(config),'sha256':c.sha(b'old bytes')}}
        request={'operation':'candidate_serve','input_id':'selected','target_id':'work'}
        output=self.root/'stage-race';output.mkdir(mode=0o700)
        with patch.object(self.management,'host_selection',return_value=(None,row,None,None)),patch.object(owner,'ManagedHost') as host:
            self.expect('MANAGEMENT_HOST_CONFIG_CHANGED',lambda:self.api._delivery(self.args(),{'request':request},{}, {}, {'selected':{}},output));host.assert_not_called()

class DeliveryHostContract(unittest.TestCase):
    """Reuse original D4/M5 fixture and scope checker; socket never listens."""
    for name in ('approve','query','expect','inventory','save_policy','adapter','repin','preflight','set_request','persist'):
        import test_integration_m5 as fixture
        locals()[name]=getattr(fixture.OwnerHost,name)
    def setUp(self):
        import test_integration_m5 as fixture
        fixture.OwnerHost.setUp(self)
    def test_launch_reuses_original_work_config_root_and_producer_checks(self):
        self.socket.close();self.socket_path.unlink()
        native,cfg=self.bridge.check(self.row,launching=True);self.assertEqual(cfg,self.config)
        self.config_path.write_bytes(b'drift')
        self.expect('PARALLEL_HOST_CONFIG_CHANGED',lambda:self.bridge.check(self.row,launching=True))
    def test_launch_rejects_existing_socket_without_unlink_or_adoption(self):
        before=self.socket_path.lstat()
        self.expect('PARALLEL_HOST_SOCKET_EXISTS',lambda:self.bridge.check(self.row,launching=True))
        self.assertEqual(self.socket_path.lstat().st_ino,before.st_ino)
    def test_managed_start_and_explicit_stop_reuse_exact_management_actions(self):
        import threading
        self.socket.close();self.socket_path.unlink()
        registry=owner.r.Registry.create(self.root/'management-registry',approve_local_owner=True)
        descriptor=self.root/'descriptor.json';descriptor.write_bytes(c.encoded({'schema':'golem.management-host.v1','host_policy':owner.r.file_pin(self.host_path),'host_id':'selected'}));descriptor.chmod(0o600)
        path=self.root/'management.json'
        value={'schema':'golem.project-management.v1','base_policy':{'path':str(self.owner.path),'sha256':self.owner.digest},'registry':str(registry.root),'registry_identity':registry.root_identity,'destination':'MODEL_SERVICE','destination_id':self.owner.transfer.value['destination_id'],'data_class':'APPROVED_MANAGEMENT_CONTENT','max_result_bytes':8388608,'producer':owner.management_producer(),'projects':[{'project_id':'p','work_id':'a','targets':[ProjectManagement.target(self,'work',self.work,'work')],'inputs':[{'input_id':'selected','file':owner.r.file_pin(descriptor)}],'actions':[]}]}
        start={'operation':'candidate_serve','target_id':'work','input_id':'selected'};stop={'operation':'candidate_stop','target_id':'work','input_id':'selected','launch_action_id':'start','launch_request_id':'one'}
        value['projects'][0]['actions']=[{'action_id':n,'request':q,'effects':list(owner.MANAGEMENT_OPERATIONS[q['operation']][2]),'timeout_seconds':5} for n,q in [('start',start),('stop',stop)]]
        path.write_bytes(c.encoded(value));path.chmod(0o600)
        policy=owner.ManagementPolicy(path,c.sha(path.read_bytes()),self.owner,approve_management=True)
        api=owner.ManagementService(profiles.Scoped(self.api,'parallel'),policy);self.addCleanup(api.close)
        observed=[]
        def process(argv,out,cwd,timeout,limit,**kw):
            observed.append(argv);kw['started'].set();kw['stop'].wait(5)
            terminal={'reason':'STOP_REQUESTED','returncode':0};owner.records.save(out/'process-result.json',c.encoded(terminal));owner.records.save(out/'process-result-ref.json',c.encoded({'sha256':c.sha(c.encoded(terminal))}));return terminal
        args={'project_id':'p','action_id':'start','request_id':'one'}
        with patch.object(owner,'delivery_process',side_effect=process):
            first=api.call('management_request',args);self.assertEqual(first['state'],'RECORDED',first)
            self.assertEqual(api.call('management_result',args)['state'],'COMMIT_UNKNOWN')
            self.assertTrue(api.call('management_host_status',args)['active'])
            stopped=api.call('management_request',{**args,'action_id':'stop'});self.assertEqual(stopped['state'],'RECORDED',stopped)
            self.assertFalse(api.call('management_host_status',args)['active']);self.assertTrue(api.call('management_result',args)['historical_result'])
            self.assertEqual(len(observed),1);self.assertEqual(observed[0][3:5],['candidate','serve']);self.assertEqual(observed[0][-2:],['--approve-config',self.row['config_digest']])
