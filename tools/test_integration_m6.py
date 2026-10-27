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


if __name__=='__main__':unittest.main()
