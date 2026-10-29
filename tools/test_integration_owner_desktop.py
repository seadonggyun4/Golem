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
        # The old native D4 contract still rejects an empty action array.
        self.expect('SCHEMA',lambda:actions.validate(self.controller.owner.current()))
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
    def test_no_network_listener_or_approval_dispatch_in_ui(self):
        tree=ast.parse(Path(desktop.__file__).read_text())
        calls={ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertFalse(calls&{'socket.socket','HTTPServer','subprocess.run','subprocess.Popen','os.system','eval','exec'})
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

class StdioWindow(unittest.TestCase):
    def test_real_stdio_prepare_and_native_window_share_instance(self):
        import os,sys,asyncio,tempfile,json
        if os.environ.get('GOLEM_TEST_TK')!='1':self.skipTest('native stdio fixture requires GOLEM_TEST_TK=1')
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as temp:
            result_path=Path(temp)/'result.json'
            code='''
import sys,json
from pathlib import Path
from unittest.mock import patch
import test_integration_owner_desktop as tests
import integration_owner_desktop as ui
import integration_feature_profiles as profiles
fixture=tests.Desktop();fixture.setUp();api=fixture.api
initial=api.transfer.path.read_bytes()
class FixtureWindow(ui.Window):
 def __init__(self,root,controller):
  super().__init__(root,controller);self.started=False;root.after(100,self.check)
 def check(self):
  plans=self.controller.reads.preparation_plans
  if not self.started and plans:
   plan_id=list(plans)[-1]
   for k,v in dict(project_id='p',work_id='a',plan_id=plan_id,plan_sha256=plans[plan_id],action_id='stdio-ui').items():self.fields[k].set(v)
   self.started=True;self.inspect_button.invoke()
  elif self.started and self.reviewed and not self.busy:
   self.consent.set(True)
   with patch('tkinter.filedialog.askdirectory',return_value=str(fixture.root)),patch('tkinter.messagebox.askokcancel',return_value=True):self.export_button.invoke()
  if list(fixture.root.glob('owner-review-*/review.json')):
   result=json.loads(next(fixture.root.glob('owner-review-*/review.json')).read_text())
   result['existing_policy_unchanged']=api.transfer.path.read_bytes()==initial
   Path(sys.argv[1]).write_text(json.dumps(result));return
  self.root.after(100,self.check)
try:
 with patch.object(api,'_read',fixture.observed),patch.object(tests.fixture.prep.records,'capture',fixture.capture),patch.object(ui,'Window',FixtureWindow):
  rc=ui.run(profiles.Scoped(api,'prepare'),api.transfer,approve_ui=True)
  value=json.loads(Path(sys.argv[1]).read_text());value['transport_closed']=rc==0;Path(sys.argv[1]).write_text(json.dumps(value))
  sys.exit(rc)
finally:fixture.doCleanups()
'''
            async def exercise():
                params=StdioServerParameters(command=sys.executable,args=['-c',code,str(result_path)],env={'PYTHONPATH':str(Path(__file__).parent)})
                async with stdio_client(params) as (reader,writer):
                    async with ClientSession(reader,writer) as client:
                        await client.initialize();tools=await client.list_tools()
                        self.assertFalse(any('owner_review' in t.name for t in tools.tools))
                        args={'project_id':'p','work_id':'a','preparation_request_id':'stdio-ui-draft','tool':'session_claim','session_id':'owner-session','native_binding_id':'','fields_json':json.dumps({'ttl_ms':60000,'source_snapshot':'0'*64,'byte_budget':65536}),'body':'','context_json':'','count_json':''}
                        result=await client.call_tool('golem_action_prepare',args);self.assertFalse(result.is_error)
                        async def wait_result():
                            while not result_path.exists():await asyncio.sleep(.05)
                        await asyncio.wait_for(wait_result(),30)
                        value=json.loads(result_path.read_text());self.assertTrue(value['existing_policy_unchanged']);self.assertFalse(value['policy_applied']);self.assertFalse(value['execution_authorized'])
            asyncio.run(exercise())
            self.assertTrue(json.loads(result_path.read_text()).get('transport_closed'))
