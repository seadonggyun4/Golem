"""Controller and Tk event tests use disposable fixture services, never TopSolar."""
import unittest
from unittest.mock import patch
from pathlib import Path
import ast
import integration_contract as c
import integration_feature_profiles as profiles
import integration_owner_desktop as desktop
import test_integration_m2 as fixture

class Desktop(unittest.TestCase):
    for name in ('setUp','observed','capture','run_call','draft','plan_args','owner_api','approve','query','expect','inventory','save_policy','adapter'):
        locals()[name]=getattr(fixture.Preparations,name)
    def prepare(self):
        initial=self.draft();api,_=self.owner_api(initial['plan']['payload']['action'])
        self.api=api.reads;result=self.draft()
        self.controller=desktop.Controller(profiles.Scoped(api,'task'),api.policy,approve_ui=True)
        self.args={'project_id':'p','work_id':'a',**self.plan_args(result)}
        return api
    def inspect(self):
        with patch.object(self.api,'_read',self.observed):return self.controller.inspect(self.args)
    def export(self,**kw):
        with patch.object(self.api,'_read',self.observed):return self.controller.export('new',self.root,**kw)
    def test_d4_owner_inspect_export_share_transport_participation(self):
        import integration_lifecycle as life
        api=self.prepare();before_work=self.inventory()
        with desktop.entry.connection(profiles.Scoped(api,'task'),api.policy) as scoped:
            self.controller=desktop.Controller(scoped,api.policy,approve_ui=True)
            self.assertEqual(self.controller.drafts(),[self.args])
            self.assertEqual(list(self.registry.root.glob('d5-client-*')),[])
            self.inspect()
            self.expect('PARTICIPANT_OR_WRITER_LIVE',lambda:life.quiet(self.registry,'p'))
            candidate=self.export(confirmed=True)
            self.assertFalse(candidate['policy_applied'])
            self.assertEqual(len(list(self.registry.root.glob('d5-client-*'))),1)
        life.quiet(self.registry,'p')
        self.assertEqual(before_work,self.inventory())
        self.expect('PARTICIPATION_CLOSED',lambda:self.inspect())

    def test_owner_endpoint_drains_before_transport_participant_release(self):
        import integration_lifecycle as life
        from unittest.mock import AsyncMock
        api=self.prepare();events=[];test=self
        class Endpoint:
            def __init__(self,directory,controller,**kw):self.controller=controller
            def start(self):
                self.controller.inspect(test.args)
                events.append('inspect')
            def close(self):
                test.expect('PARTICIPANT_OR_WRITER_LIVE',lambda:life.quiet(test.registry,'p'))
                events.append('joined')
        with patch.object(self.api,'_read',self.observed),patch.object(desktop,'ReviewEndpoint',Endpoint),patch.object(desktop.entry,'serve',new_callable=AsyncMock):
            self.assertEqual(desktop.run(profiles.Scoped(api,'task'),api.policy,approve_ui=True,review_directory=self.root),0)
        self.assertEqual(events,['inspect','joined'])
        life.quiet(self.registry,'p')
        self.assertEqual(len(list(self.registry.root.glob('d5-client-*'))),1)
    def test_inspect_export_same_instance_and_no_policy_activation(self):
        api=self.prepare();before=api.policy.path.read_bytes();self.inspect()
        result=self.export(confirmed=True)
        self.assertTrue(Path(result['candidate_directory'],'review.json').exists())
        self.assertFalse(result['policy_applied']);self.assertEqual(before,api.policy.path.read_bytes())
        self.expect('OWNER_DESKTOP_REVIEW_REQUIRED',lambda:self.export(confirmed=True))
    def test_consent_and_inspection_required(self):
        api=self.prepare()
        self.expect('OWNER_DESKTOP_CONSENT_REQUIRED',lambda:desktop.Controller(profiles.Scoped(api,'task'),api.policy))
        self.expect('OWNER_DESKTOP_REVIEW_REQUIRED',lambda:self.export(confirmed=True))
        self.inspect();self.expect('OWNER_REVIEW_REQUIRED',lambda:self.export())
    def test_d2_first_action_is_candidate_not_empty_d4_authority(self):
        import integration_mutation_contract as actions
        result=self.draft()
        scoped=profiles.Scoped(self.api,'prepare')
        self.controller=desktop.Controller(scoped,self.api.transfer,approve_ui=True)
        self.args={'project_id':'p','work_id':'a',**self.plan_args(result)}
        # Schema-valid empty D4 actions still grant no action. The D2 draft
        # builder is not a dispatch Policy and is never installed by export.
        actions.validate(self.controller.owner.current())
        self.assertEqual(self.controller.owner.current()['actions'],[])
        self.assertNotIsInstance(self.controller.owner,actions.Policy)
        self.assertFalse(hasattr(self.controller.owner,'action'))
        self.inspect();value=self.export(confirmed=True)
        candidate=c.decode(Path(value['candidate_directory'],'policy-candidate.json').read_bytes())
        actions.validate(candidate)
        self.assertEqual(len(candidate['actions']),1)
        self.assertEqual(value['base_policy_kind'],'D2_FIRST_ACTION_DRAFT')
        self.assertFalse(value['policy_applied'])
        self.assertFalse(set(scoped.tools())&set(actions.NAMES))
    def test_local_catalog_requires_current_scope_and_live_instance(self):
        self.prepare()
        rows=self.controller.drafts()
        self.assertEqual(rows,[self.args])
        self.assertIsNone(self.controller.selection)
        self.api.preparation_plans.clear()
        self.assertEqual(self.controller.drafts(),[])

    def test_catalog_expiry_and_busy_do_not_replay_or_authorize(self):
        self.prepare()
        import integration_preparations as prep
        with patch.object(prep.time,'monotonic_ns',return_value=10**30):
            self.assertEqual(self.controller.drafts(),[])
        self.api._lock.acquire()
        try:self.expect('SERVICE_BUSY',self.controller.drafts)
        finally:self.api._lock.release()
        self.assertIsNone(self.controller.selection)

    def test_attachment_drift_is_not_retried(self):
        self.prepare();self.inspect();path=self.root/'attachment.json';path.write_bytes(b'{}');path.chmod(0o600)
        self.expect('OWNER_ATTACHMENT_CHANGED',lambda:self.export(confirmed=True,attachment_path=path,attachment_sha256='0'*64))
        self.expect('OWNER_DESKTOP_REVIEW_REQUIRED',lambda:self.export(confirmed=True))
    def test_current_policy_revocation_blocks_after_view(self):
        api=self.prepare();self.inspect();api.policy.path.write_bytes(api.policy.path.read_bytes()+b' ')
        self.expect('MUTATION_POLICY_CHANGED',lambda:self.export(confirmed=True))
    def test_profile_cannot_bypass_owner_plan_scope(self):
        self.prepare();self.controller.scoped.profile=profiles.definition('read')
        self.expect('FEATURE_PROFILE_SCOPE',self.inspect)
    def test_package_contains_opt_in_ui_without_changing_default_launcher(self):
        import integration_distribution as distribution
        raw=distribution.build('task');value=distribution.verify(raw,c.sha(raw))
        import io,zipfile,json
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertTrue(set(distribution.OWNER_DESKTOP_FILES)<=set(archive.namelist()))
            manifest=json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['server']['entry_point'],'tools/integration_owner_maintenance.py')
            self.assertNotIn('--approve-owner-review-ui',str(manifest))
    def test_no_tcp_or_approval_dispatch_in_ui(self):
        tree=ast.parse(Path(desktop.__file__).read_text())
        calls={ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertFalse(calls&{'HTTPServer','subprocess.run','subprocess.Popen','os.system','eval','exec'})
        sockets=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and ast.unparse(n.func)=='socket.socket']
        self.assertTrue(sockets);self.assertTrue(all(ast.unparse(n.args[0])=='socket.AF_UNIX' for n in sockets))
        self.assertEqual([n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and ast.unparse(n.func)=='self.scoped.call'],['plan_read'])

class NativeWindow(unittest.TestCase):
    for name in ('setUp','observed','capture','run_call','draft','plan_args','owner_api','approve','query','expect','inventory','save_policy','adapter','prepare','inspect','export'):
        locals()[name]=getattr(Desktop,name)
    # Native-window checks are opt-in; controller checks above remain headless.
    def test_native_window_review_confirm_and_preserve(self):
        import os,time
        if os.environ.get('GOLEM_TEST_TK')!='1':self.skipTest('native display fixture requires GOLEM_TEST_TK=1')
        import tkinter as tk
        self.prepare();root=tk.Tk();window=desktop.Window(root,self.controller)
        def settle():
            deadline=time.monotonic()+15
            while window.busy and time.monotonic()<deadline:
                root.update();time.sleep(.01)
            root.update();self.assertFalse(window.busy)
        try:
            window.refresh();settle()
            self.assertEqual(window.draft_rows,[self.args])
            window.draft_choice.current(0);window.choose_draft()
            self.assertFalse(window.reviewed)
            self.assertFalse(window.consent.get())
            window.fields['action_id'].set('ui-reviewed')
            with patch.object(self.api,'_read',self.observed):
                window.inspect_button.invoke();settle()
                self.assertTrue(window.reviewed);self.assertFalse(window.consent.get())
                window.fields['action_id'].set('changed');self.assertFalse(window.reviewed)
                window.inspect_button.invoke();settle();window.consent.set(True)
                with patch('tkinter.filedialog.askdirectory',return_value=str(self.root)),patch('tkinter.messagebox.askokcancel',return_value=True):
                    window.export_button.invoke();settle()
                self.assertFalse(window.reviewed)
                self.assertIn('미적용',window.status.get())
                self.assertEqual(len(list(self.root.glob('owner-review-*/review.json'))),1)
                # Disabled button cannot publish the same selection again.
                window.export_button.invoke();root.update()
                self.assertEqual(len(list(self.root.glob('owner-review-*/review.json'))),1)
        finally:root.destroy()


class Headless(unittest.TestCase):
    def test_many_connections_never_import_tk_or_construct_controller(self):
        import builtins
        from unittest.mock import AsyncMock
        original=builtins.__import__
        def no_tk(name,*a,**kw):
            if name.startswith('tkinter'):raise AssertionError('background UI import')
            return original(name,*a,**kw)
        with patch('builtins.__import__',no_tk),patch.object(desktop,'Controller',side_effect=AssertionError('UI constructed')),patch.object(desktop.entry,'serve',new_callable=AsyncMock) as serve:
            for _ in range(20):self.assertEqual(desktop.run(__import__('types').SimpleNamespace(profile={'family':'D2'}),None,approve_ui=True),0)
            self.assertEqual(serve.await_count,20)

    def test_optional_review_failure_does_not_break_mcp(self):
        from unittest.mock import AsyncMock
        with patch.object(desktop,'Controller'),patch.object(desktop,'ReviewEndpoint',side_effect=OSError('fixture')),patch.object(desktop.entry,'serve',new_callable=AsyncMock) as serve:
            self.assertEqual(desktop.run(__import__('types').SimpleNamespace(profile={'family':'D2'}),None,approve_ui=True,review_directory='/missing'),0)
            serve.assert_awaited_once()

    def test_close_is_presentation_only(self):
        from unittest.mock import Mock
        window=object.__new__(desktop.Window);window.root=Mock();window.busy=False;window.close()
        window.root.destroy.assert_called_once();self.assertTrue(window.finished)
        window.root.reset_mock();window.busy=True;window.close()
        window.root.withdraw.assert_called_once();window.root.destroy.assert_not_called()


class LocalReview(unittest.TestCase):
    for name in ('setUp','observed','capture','run_call','draft','plan_args','owner_api','approve','query','expect','inventory','save_policy','adapter','prepare','inspect','export'):
        locals()[name]=getattr(Desktop,name)

    def endpoint(self):
        import tempfile
        temp=tempfile.TemporaryDirectory(dir='/tmp');self.addCleanup(temp.cleanup)
        directory=Path(temp.name).resolve();directory.chmod(0o700)
        self.prepare();endpoint=desktop.ReviewEndpoint(directory,self.controller).start();self.addCleanup(endpoint.close)
        self.directory=directory;self.server=endpoint
        return desktop.RemoteController(directory,endpoint.instance)

    def test_real_unix_inspect_export_and_no_replay_after_reconnect(self):
        remote=self.endpoint();before=self.controller.owner.path.read_bytes()
        self.assertEqual(remote.drafts(),[self.args])
        with patch.object(self.api,'_read',self.observed):
            remote.inspect(self.args);result=remote.export('ipc-candidate',self.root,confirmed=True)
            self.assertFalse(result['policy_applied']);self.assertTrue(Path(result['candidate_directory'],'review.json').is_file())
            other=desktop.RemoteController(self.directory,self.server.instance);other.inspect(self.args)
            self.expect('OWNER_EXPORT_ALREADY_ATTEMPTED',lambda:other.export('again',self.root,confirmed=True))
        self.assertEqual(before,self.controller.owner.path.read_bytes());self.assertEqual(len(list(self.root.glob('owner-review-*'))),1)

    def test_connection_metadata_has_kernel_peer_and_does_not_admit_or_call_Work(self):
        import os
        remote=self.endpoint();before_work=self.inventory()
        participants=sorted(self.registry.root.glob('d5-client-*'))
        with patch.object(self.api,'_read',side_effect=AssertionError('no Work read')), \
             patch.object(self.controller.scoped,'call',side_effect=AssertionError('no MCP call')):
            value=remote.connection_status()
        self.assertEqual(value['pid'],os.getpid())
        self.assertEqual(remote.last_peer_pid,os.getpid())
        self.assertEqual(value['policy_sha256'],self.controller.owner.digest)
        self.assertEqual(value['model_tool_delivery'],'NOT_OBSERVED')
        self.assertFalse(value['execution_authorized'])
        self.assertEqual(value['Work_calls'],0)
        self.assertTrue(value['tools'])
        self.assertEqual(participants,sorted(self.registry.root.glob('d5-client-*')))
        self.assertEqual(before_work,self.inventory())

    def test_live_instance_scope_and_expiry_are_reused(self):
        remote=self.endpoint()
        with patch.object(self.api,'_read',self.observed):
            self.expect('PREPARATION_INSTANCE_OR_REFERENCE',lambda:remote.inspect({**self.args,'plan_id':'0'*32}))
            self.expect('TRANSFER_SCOPE',lambda:remote.inspect({**self.args,'work_id':'foreign'}))
        with patch.object(desktop.preparations.time,'monotonic_ns',return_value=10**30):self.assertEqual(remote.drafts(),[])

    def test_auth_request_replay_and_forbidden_operations(self):
        self.endpoint();import uuid
        msg={'instance':self.server.instance,'token':'0'*64,'request_id':uuid.uuid4().hex,'operation':'catalog','arguments':{}}
        self.expect('OWNER_IPC_AUTH',lambda:self.server.dispatch(msg))
        msg['token']=self.server.token;self.assertEqual(self.server.dispatch(msg),[self.args])
        self.expect('OWNER_IPC_REPLAY',lambda:self.server.dispatch(msg))
        for op in ('execute','apply','read_file','approve'):
            self.expect('OWNER_IPC_OPERATION',lambda:self.server.dispatch({**msg,'request_id':uuid.uuid4().hex,'operation':op}))

    def test_lost_export_reply_never_republishes(self):
        import socket
        remote=self.endpoint()
        with patch.object(self.api,'_read',self.observed):
            remote.inspect(self.args)
            original=desktop.send_frame
            def lost(conn,value):
                if isinstance(value,dict) and value.get('ok') is True and isinstance(value.get('value'),dict) and 'candidate_directory' in value['value']:
                    conn.shutdown(socket.SHUT_RDWR);raise OSError('lost reply')
                return original(conn,value)
            with patch.object(desktop,'send_frame',lost):
                self.expect('OWNER_EXPORT_UNKNOWN',lambda:remote.export('lost',self.root,confirmed=True))
            other=desktop.RemoteController(self.directory,self.server.instance);other.inspect(self.args)
            self.expect('OWNER_EXPORT_ALREADY_ATTEMPTED',lambda:other.export('retry',self.root,confirmed=True))
        self.assertEqual(len(list(self.root.glob('owner-review-*/review.json'))),1)

    def test_partial_publication_and_policy_drift_are_preserved(self):
        remote=self.endpoint()
        with patch.object(self.api,'_read',self.observed):
            remote.inspect(self.args);before=self.controller.owner.path.read_bytes()
            self.controller.owner.path.write_bytes(before+b' ')
            self.expect('MUTATION_POLICY_CHANGED',lambda:remote.export('stale',self.root,confirmed=True))
        self.assertEqual(list(self.root.glob('owner-review-*')),[])

    def test_descriptor_drift_and_dead_connection_cannot_be_adopted(self):
        remote=self.endpoint();self.server.close()
        with self.assertRaises((OSError,c.IntegrationError)):remote.drafts()
        self.assertEqual(list(self.directory.glob('*.json')),[])
        self.assertEqual(list(self.directory.glob('*.sock')),[])

    def test_private_directory_symlink_and_path_bounds(self):
        remote=self.endpoint();self.directory.chmod(0o755)
        try:self.expect('OWNER_IPC_DIRECTORY',remote.drafts)
        finally:self.directory.chmod(0o700)
        alias=self.directory/'alias';alias.symlink_to(self.directory,target_is_directory=True)
        self.expect('OWNER_IPC_DIRECTORY',lambda:desktop.private_directory(alias))

    def test_singleton_activation_does_not_create_second_endpoint(self):
        self.endpoint();one=desktop.OwnerInstance(self.directory);self.addCleanup(one.close);self.assertTrue(one.primary);one.start()
        two=desktop.OwnerInstance(self.directory);self.addCleanup(two.close);self.assertFalse(two.primary)
        two.activate();self.assertTrue(one.events.get(timeout=2))
        self.assertEqual(len(list(self.directory.glob('*.sock'))),2) # service + one Owner app

    def test_oversize_frame_rejected_before_payload_read(self):
        import socket
        left,right=socket.socketpair()
        try:
            left.sendall((desktop.IPC_LIMIT+1).to_bytes(4,'big'))
            self.expect('OWNER_IPC_SIZE',lambda:desktop.receive_frame(right))
        finally:left.close();right.close()


class StdioHeadless(unittest.TestCase):
    def test_real_mcp_prepare_and_separate_owner_connection(self):
        import os,sys,asyncio,tempfile,json
        try:
            from mcp import ClientSession,StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:self.skipTest('MCP SDK fixture dependencies unavailable')
        with tempfile.TemporaryDirectory(dir='/tmp') as temp:
            directory=Path(temp).resolve();directory.chmod(0o700)
            code='''
import sys,builtins
from unittest.mock import patch
import test_integration_owner_desktop as tests
import integration_owner_desktop as ui
import integration_feature_profiles as profiles
fixture=tests.Desktop();fixture.setUp();api=fixture.api
original=builtins.__import__
def no_tk(name,*a,**kw):
 if name.startswith('tkinter'):raise AssertionError('headless service imported Tk')
 return original(name,*a,**kw)
try:
 with patch.object(api,'_read',fixture.observed),patch.object(tests.fixture.prep.records,'capture',fixture.capture),patch('builtins.__import__',no_tk):
  sys.exit(ui.run(profiles.Scoped(api,'prepare'),api.transfer,approve_ui=True,review_directory=sys.argv[1]))
finally:fixture.doCleanups()
'''
            async def exercise():
                params=StdioServerParameters(command=sys.executable,args=['-c',code,str(directory)],env={'PYTHONPATH':str(Path(__file__).parent)})
                async with stdio_client(params) as (reader,writer):
                    async with ClientSession(reader,writer) as client:
                        await client.initialize();tools=await client.list_tools()
                        self.assertFalse(any('owner_review' in t.name for t in tools.tools))
                        args={'project_id':'p','work_id':'a','preparation_request_id':'stdio-separated','tool':'session_claim','session_id':'owner-session','native_binding_id':'','fields_json':json.dumps({'ttl_ms':60000,'source_snapshot':'0'*64,'byte_budget':65536}),'body':'','context_json':'','count_json':''}
                        result=await client.call_tool('golem_action_prepare',args);self.assertFalse(result.is_error)
                        ids=desktop.connections(directory);self.assertEqual(len(ids),1)
                        remote=desktop.RemoteController(directory,ids[0]);rows=await asyncio.to_thread(remote.drafts);self.assertEqual(len(rows),1)
                        await asyncio.to_thread(remote.inspect,rows[0])
                        del remote # presentation lifetime cannot stop MCP
                        await client.list_tools()
                self.assertEqual(desktop.connections(directory),[])
            asyncio.run(exercise())

class NativeSeparatedApp(unittest.TestCase):
    def test_pinned_stable_tab_preserves_existing_tabs_and_never_probes_on_open(self):
        import os,tempfile
        if os.environ.get('GOLEM_TEST_TK')!='1':self.skipTest('native display fixture requires GOLEM_TEST_TK=1')
        import tkinter as tk
        from tkinter import ttk
        from unittest.mock import Mock
        import integration_stable_owner as stable
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            directory=Path(tmp).resolve();directory.chmod(0o700)
            endpoint=desktop.LocalEndpoint(directory,lambda op,args:[]).start()
            root=tk.Tk();errors=[]
            controller=Mock(clients=('codex','claude-desktop'),config_path=directory/'selected.json',config_sha256='a'*64)
            def check():
                try:
                    tabs=next(child for child in root.winfo_children() if isinstance(child,ttk.Notebook))
                    self.assertEqual([tabs.tab(tab,'text') for tab in tabs.tabs()],
                        ['Owner 후보','기존 연결 진단','고정 연결·실행부 전환'])
                    self.assertEqual(tabs.tab(tabs.select(),'text'),'고정 연결·실행부 전환')
                    controller.inspect.assert_not_called();controller.observe.assert_not_called()
                    controller.publish.assert_not_called();controller.refresh.assert_not_called()
                    identity=c.decode((directory/'owner-app.json').read_bytes())['ui_config']
                    self.assertEqual(identity,{'path':str(directory/'selected.json'),'sha256':'a'*64})
                except Exception as error:errors.append(error)
                finally:root.destroy()
            root.after(150,check)
            try:
                with patch.object(tk,'Tk',return_value=root),patch.object(stable,'StableOwnerController',return_value=controller):
                    self.assertEqual(desktop.owner_app(['--review-directory',str(directory),
                        '--codex-config',str(directory/'absent-codex-config.toml'),
                        '--stable-config',str(directory/'selected.json'),'--stable-config-sha256','a'*64]),0)
                if errors:raise errors[0]
                self.assertEqual(desktop.RemoteController(directory,endpoint.instance).drafts(),[])
            finally:endpoint.close()

    def test_owner_app_close_keeps_service_and_activation_is_singleton(self):
        import os,tempfile
        if os.environ.get('GOLEM_TEST_TK')!='1':self.skipTest('native display fixture requires GOLEM_TEST_TK=1')
        import tkinter as tk
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            directory=Path(tmp).resolve();directory.chmod(0o700)
            endpoint=desktop.LocalEndpoint(directory,lambda op,args:[]).start()
            root=tk.Tk()
            def activate():
                other=desktop.OwnerInstance(directory)
                try:
                    self.assertFalse(other.primary);other.activate()
                finally:other.close()
                root.after(200,root.destroy)
            root.after(200,activate)
            try:
                with patch.object(tk,'Tk',return_value=root):self.assertEqual(desktop.owner_app(['--review-directory',str(directory)]),0)
                self.assertEqual(desktop.RemoteController(directory,endpoint.instance).drafts(),[])
                self.assertEqual(desktop.connections(directory),[endpoint.instance])
            finally:endpoint.close()


class OwnerAppConfiguration(unittest.TestCase):
    """Configuration identity is not an approval or installed-code attestation."""
    def setUp(self):
        import tempfile
        temp=tempfile.TemporaryDirectory(dir='/tmp');self.addCleanup(temp.cleanup)
        self.directory=Path(temp.name).resolve();self.directory.chmod(0o700)
        self.identity={'path':str(self.directory/'owner-config.json'),'sha256':'a'*64}

    def instance(self,identity=None):
        instance=desktop.OwnerInstance(self.directory,ui_config=identity)
        self.addCleanup(instance.close);return instance

    def test_same_pinned_configuration_activates_only_existing_app(self):
        first=self.instance(self.identity);first.start()
        second=self.instance(dict(self.identity));self.assertFalse(second.primary)
        second.activate();self.assertTrue(first.events.get(timeout=2))
        self.assertEqual(len(list(self.directory.glob('*.sock'))),1)
        self.assertEqual(c.decode((self.directory/'owner-app.json').read_bytes())['ui_config'],self.identity)

    def test_old_unbound_app_is_not_success_for_new_stable_configuration(self):
        first=self.instance();first.start();before=(self.directory/'owner-app.json').read_bytes()
        second=self.instance(self.identity)
        with self.assertRaisesRegex(c.IntegrationError,'OWNER_APP_CONFIG_MISMATCH'):second.activate()
        self.assertTrue(first.events.empty())
        self.assertEqual((self.directory/'owner-app.json').read_bytes(),before)
        self.assertEqual(len(list(self.directory.glob('*.sock'))),1)

    def test_absent_or_changed_config_never_activates_other_config(self):
        first=self.instance(self.identity);first.start()
        for identity in (None,{**self.identity,'sha256':'b'*64},
                         {**self.identity,'path':str(self.directory/'different.json')}):
            with self.subTest(identity=identity):
                second=self.instance(identity)
                with self.assertRaisesRegex(c.IntegrationError,'OWNER_APP_CONFIG_MISMATCH'):second.activate()
        self.assertTrue(first.events.empty())

    def test_activation_endpoint_rechecks_identity_after_record_tampering(self):
        first=self.instance(self.identity);first.start()
        changed={**self.identity,'sha256':'b'*64}
        path=self.directory/'owner-app.json'
        path.write_bytes(c.encoded({'instance':first.endpoint.instance,'ui_config':changed}))
        second=self.instance(changed)
        with self.assertRaisesRegex(c.IntegrationError,'OWNER_APP_ACTIVATION'):second.activate()
        self.assertTrue(first.events.empty())

    def test_partial_optional_pin_is_rejected_before_owner_app_or_Tk(self):
        from unittest.mock import Mock
        import contextlib,io
        for args in (['--stable-config',self.identity['path']],['--stable-config-sha256',self.identity['sha256']]):
            with self.subTest(args=args),patch.object(desktop,'OwnerInstance',new=Mock()) as instance:
                with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                    desktop.owner_app(['--review-directory',str(self.directory),*args])
                instance.assert_not_called()

    def test_mismatched_config_bytes_fail_before_lock_or_tk(self):
        from unittest.mock import Mock
        import integration_stable_owner as stable
        path=self.directory/'owner-config.json';path.write_bytes(b'{}\n');path.chmod(0o600)
        with patch.object(desktop,'OwnerInstance',new=Mock()) as instance:
            with self.assertRaisesRegex(stable.StableOwnerError,'OWNER_CONFIG_CHANGED'):
                desktop.owner_app(['--review-directory',str(self.directory),'--stable-config',str(path),
                    '--stable-config-sha256','a'*64])
            instance.assert_not_called()

class PublicationFault(unittest.TestCase):
    for name in ('setUp','observed','capture','run_call','draft','plan_args','owner_api','approve','query','expect','inventory','save_policy','adapter','prepare','inspect','export','endpoint'):
        locals()[name]=getattr(LocalReview,name)
    # Only this fault test is added; inherited protocol regressions intentionally
    # remain in LocalReview rather than running them a second time.
    def test_partial_candidate_files_remain_and_retry_is_fenced(self):
        remote=self.endpoint();import integration_owner_review as review
        original=review.records.save
        def fail_last(path,data,**kw):
            if path.name=='review.json':raise OSError('fixture publication interruption')
            return original(path,data,**kw)
        with patch.object(self.api,'_read',self.observed):
            remote.inspect(self.args)
            with patch.object(review.records,'save',fail_last):
                self.expect('OWNER_IPC_FAILED',lambda:remote.export('partial',self.root,confirmed=True))
            other=desktop.RemoteController(self.directory,self.server.instance);other.inspect(self.args)
            self.expect('OWNER_EXPORT_ALREADY_ATTEMPTED',lambda:other.export('retry',self.root,confirmed=True))
        dirs=list(self.root.glob('owner-review-*'));self.assertEqual(len(dirs),1)
        self.assertTrue((dirs[0]/'action.json').is_file());self.assertTrue((dirs[0]/'policy-candidate.json').is_file());self.assertFalse((dirs[0]/'review.json').exists())

class MultiConnection(unittest.TestCase):
    def test_three_real_stdio_connections_have_no_tk_and_distinct_live_plans(self):
        import sys,asyncio,tempfile,json
        from contextlib import AsyncExitStack
        try:
            from mcp import ClientSession,StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:self.skipTest('MCP SDK fixture dependencies unavailable')
        with tempfile.TemporaryDirectory(dir='/tmp') as temp:
            directory=Path(temp).resolve();directory.chmod(0o700)
            code='''
import sys,builtins
from unittest.mock import patch
import test_integration_owner_desktop as tests
import integration_owner_desktop as ui
import integration_feature_profiles as profiles
fixture=tests.Desktop();fixture.setUp();api=fixture.api
original=builtins.__import__
def no_tk(name,*a,**kw):
 if name.startswith('tkinter'):raise AssertionError('background Tk')
 return original(name,*a,**kw)
try:
 with patch.object(api,'_read',fixture.observed),patch.object(tests.fixture.prep.records,'capture',fixture.capture),patch('builtins.__import__',no_tk):
  sys.exit(ui.run(profiles.Scoped(api,'prepare'),api.transfer,approve_ui=True,review_directory=sys.argv[1]))
finally:fixture.doCleanups()
'''
            async def exercise():
                async with AsyncExitStack() as stack:
                    clients=[]
                    for _ in range(3):
                        params=StdioServerParameters(command=sys.executable,args=['-c',code,str(directory)],env={'PYTHONPATH':str(Path(__file__).parent)})
                        reader,writer=await stack.enter_async_context(stdio_client(params))
                        client=await stack.enter_async_context(ClientSession(reader,writer));clients.append(client)
                    await asyncio.gather(*(client.initialize() for client in clients))
                    await asyncio.gather(*(client.list_tools() for client in clients))
                    args={'project_id':'p','work_id':'a','preparation_request_id':'multi-draft','tool':'session_claim','session_id':'owner-session','native_binding_id':'','fields_json':json.dumps({'ttl_ms':60000,'source_snapshot':'0'*64,'byte_budget':65536}),'body':'','context_json':'','count_json':''}
                    result=await clients[0].call_tool('golem_action_prepare',args);self.assertFalse(result.is_error)
                    ids=desktop.connections(directory);self.assertEqual(len(ids),3)
                    remotes=[desktop.RemoteController(directory,key) for key in ids]
                    rows=await asyncio.gather(*(asyncio.to_thread(remote.drafts) for remote in remotes))
                    self.assertEqual(sorted(map(len,rows)),[0,0,1])
                    plan=next(row[0] for row in rows if row)
                    for remote,row in zip(remotes,rows):
                        if not row:
                            with self.assertRaisesRegex(c.IntegrationError,'PREPARATION_INSTANCE_OR_REFERENCE'):
                                await asyncio.to_thread(remote.inspect,plan)
                    # Owner app is never started, yet every MCP remains usable.
                    await asyncio.gather(*(client.list_tools() for client in clients))
                self.assertEqual(desktop.connections(directory),[])
            asyncio.run(exercise())

class ConnectionList(unittest.TestCase):
    def test_search_sort_closed_history_and_no_requests_or_deletion(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            directory=Path(tmp).resolve();directory.chmod(0o700)
            calls=[]
            a=desktop.LocalEndpoint(directory,lambda op,args:calls.append(op),label='Zulu Codex').start()
            b=desktop.LocalEndpoint(directory,lambda op,args:calls.append(op),label='alpha Claude').start()
            try:
                model=desktop.ConnectionCatalog(directory);model.refresh()
                self.assertEqual([r['label'] for r in model.visible()],['alpha Claude','Zulu Codex'])
                self.assertEqual([r['label'] for r in model.visible(order='name_desc')],['Zulu Codex','alpha Claude'])
                self.assertEqual(model.visible('CLAUDE alpha')[0]['instance'],b.instance)
                self.assertEqual(model.visible(a.instance[:12])[0]['instance'],a.instance)
                self.assertEqual(model.visible('no such connection'),[])
                before=a.record.read_bytes();b.close();model.refresh()
                self.assertEqual([r['instance'] for r in model.visible()],[a.instance])
                self.assertEqual(model.rows[b.instance]['state'],'closed')
                self.assertEqual(len(model.visible(show_closed=True)),2)
                self.assertEqual(a.record.read_bytes(),before);self.assertEqual(calls,[])
            finally:a.close();b.close()

    def test_unsafe_socket_and_stale_record_not_reported_live(self):
        import tempfile,socket
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            directory=Path(tmp).resolve();directory.chmod(0o700)
            endpoint=desktop.LocalEndpoint(directory,lambda *_:None).start()
            try:
                model=desktop.ConnectionCatalog(directory)
                endpoint.path.chmod(0o666);model.refresh()
                self.assertEqual(model.rows[endpoint.instance]['state'],'invalid')
                endpoint.path.chmod(0o600)
                endpoint.socket.close();model.refresh()
                # A stale socket file cannot establish process liveness.
                self.assertEqual(model.rows[endpoint.instance]['state'],'record')
                self.assertIn('미확인',desktop.CONNECTION_STATES['record'])
            finally:endpoint.close()

    def test_native_browser_selection_filter_refresh_and_closed_disable(self):
        import os,tempfile
        if os.environ.get('GOLEM_TEST_TK')!='1':self.skipTest('native display fixture requires GOLEM_TEST_TK=1')
        import tkinter as tk
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            directory=Path(tmp).resolve();directory.chmod(0o700)
            a=desktop.LocalEndpoint(directory,lambda *_:None,label='same label').start()
            b=desktop.LocalEndpoint(directory,lambda *_:None,label='same label').start()
            root=tk.Tk();opened=[]
            try:
                view=desktop.ConnectionBrowser(root,directory,opened.append);root.update()
                self.assertEqual(view.tree.selection(),())
                view.tree.focus_force();view.tree.event_generate('<Down>');root.update()
                first=view.tree.get_children()[0]
                self.assertEqual(view.tree.selection(),(first,))
                self.assertEqual(view.tree.focus(),first)
                view.tree.selection_set(a.instance);root.update()
                view.order.set('이름 역순');view.render();root.update()
                self.assertEqual(view.tree.selection(),(a.instance,))
                self.assertEqual(view.tree.focus(),a.instance)
                view.open_selected();self.assertEqual(opened,[a.instance])
                view.query.set(b.instance);root.update()
                self.assertEqual(view.tree.selection(),());view.open_selected();self.assertEqual(opened,[a.instance])
                view.query.set('');view.tree.selection_set(a.instance);a.close();view.refresh();root.update()
                self.assertFalse(view.tree.exists(a.instance));self.assertEqual(view.tree.selection(),())
                view.show_closed.set(True);view.render();view.tree.selection_set(a.instance);root.update()
                self.assertIn('disabled',view.open_button.state());view.open_selected();self.assertEqual(opened,[a.instance])
                self.assertEqual(desktop.connections(directory),[b.instance])
            finally:root.destroy();a.close();b.close()
