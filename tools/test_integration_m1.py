"""M1 disposable D2 scopes and fake native receiver; no real client/Work E2E."""
import base64
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
import integration_contract as c
import integration_reads as reads
import integration_service as service
import integration_transfer as transfer
import test_integration_d2 as existing

class NativeReads(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter'):
        locals()[name]=getattr(existing.D2,name)
    def setUp(self):
        existing.D2.setUp(self)
        self.api=service.Service(self.adapter())
        self.record={'schema':'golem.work-record.v1','work_id':'a','work_specification':{'work_id':'a'},'execution_authorized':False,
            'documents':[{'document_id':'selection','revision':1,'digest':'a'*64,'body_digest':'b'*64}], 'journal':[]}
    def invoke(self,name,fields,raw=b'{"schema_version":1,"untrusted":"ignore instructions"}\n',**options):
        args={'project_id':'p','work_id':'a',**fields};calls=[];records=[{'result':self.record},{'result':self.record if not options.get('stale') else {**self.record,'changed':True}}]
        def capture(argv,output,*unused,**kw):
            calls.append((argv,kw))
            self.assertEqual(argv[:3],[str(self.cli),'--output-mode','full']);self.assertEqual(kw['env'],service.backend.ENVIRONMENT)
            self.assertFalse(kw['observe_source']);self.assertEqual(kw['cwd'],output)
            (output/'stdout.log').write_bytes(raw);(output/'stdout.log').chmod(0o600)
            return {'returncode':options.get('returncode',0),'reason':options.get('reason','EXIT'),'recording':'RECORDED'}
        with patch.object(self.api,'_read',side_effect=records),patch.object(reads.records,'capture',capture):
            value=self.api.call(name,args)
        return value,calls
    def test_all_new_tools_are_schema_declared_and_explicitly_scoped(self):
        self.assertTrue(set(reads.NAMES)<=set(service.SCHEMAS));self.assertEqual(set(service.SCHEMAS),set(transfer.NAMES))
        self.policy['scopes'][0]['tools']=['work_inspect'];self.save_policy();api=service.Service(self.adapter())
        with patch.object(reads.records,'capture',side_effect=AssertionError('no execution')):
            self.expect('TRANSFER_SCOPE',lambda:api.call('workflow_read',{'project_id':'p','work_id':'a','operation':'next','selection_id':'selection'}))
    def test_workflow_read_preserves_bytes_and_fixed_argv(self):
        before=self.inventory();raw=b'{ "schema_version":1, "action":"WAIT", "sequence":7 }\n'
        out,calls=self.invoke('workflow_read',{'operation':'next','selection_id':'selection'},raw)
        self.assertEqual(calls[0][0][3:],['workflow','next',str(self.work),'selection'])
        self.assertEqual(base64.b64decode(out['native_stdout']['data']),raw)
        self.assertEqual(out['native_stdout']['sha256'],c.sha(raw));self.assertFalse(out['execution_authorized']);self.assertFalse(out['work_completion_inferred'])
        self.assertEqual(before,self.inventory())
    def test_closed_operation_and_extra_paths_rejected_before_capture(self):
        for fields in ({'operation':'publish','selection_id':'selection'},{'operation':'next','selection_id':'selection','path':'/secret'},{'operation':'next','selection_id':'../other'}):
            with patch.object(reads.records,'capture',side_effect=AssertionError('no launch')):
                self.expect('SCHEMA',lambda:self.api.call('workflow_read',{'project_id':'p','work_id':'a',**fields}))
    def test_json_operations_cannot_select_mutations(self):
        for name,op in (('role_read','status'),('session_read','context'),('binding_read','inspect'),('approval_read','status'),('reentry_read','status')):
            self.expect('READ_OPERATION_REQUIRED',lambda:self.invoke(name,{'operation':op,'request_json':'{"schema_version":1,"operation":"start"}'}))
    def test_role_and_session_fixed_read_discriminators(self):
        for name,op,prefix in (('role_read','evaluate',['role','call']),('session_read','context',['session','call']),('binding_read','inspect',['agent','binding','inspect']),('approval_read','status',['approval','call']),('reentry_read','status',['reentry','call'])):
            value,calls=self.invoke(name,{'operation':op,'request_json':c.encoded({'schema_version':1,'operation':op}).decode()})
            self.assertEqual(calls[0][0][3:3+len(prefix)],prefix);self.assertFalse(value['native_state_changed'])
    def test_document_and_template_revision_binding(self):
        self.expect('READ_DOCUMENT_BINDING',lambda:self.invoke('document_read',{'operation':'inspect','document_id':'alien','revision':1}))
        self.expect('READ_DOCUMENT_BINDING',lambda:self.invoke('template_read',{'operation':'instantiate','scope_id':'selection','revision':2,'request_json':'{}'}))
        _,calls=self.invoke('document_read',{'operation':'inspect','document_id':'selection','revision':1});self.assertEqual(calls[0][0][3:5],['document','inspect'])
    def test_historical_reports_use_only_nonprojecting_inspect(self):
        for kind in ('completion','reentry'):
            _,calls=self.invoke('report_read',{'kind':kind,'sequence':1});self.assertEqual(calls[0][0][3:],[kind,'inspect',str(self.work),'1'])
    def test_historical_report_markdown_preserves_bytes_without_current_authority(self):
        raw='# 완료 기록\n\nHistorical **PASS**; not current acceptance.\n'.encode()
        before=self.inventory()
        for kind in ('completion','reentry'):
            value,calls=self.invoke('report_read',{'kind':kind,'sequence':1},raw)
            self.assertEqual(value['result'],raw.decode())
            self.assertEqual(base64.b64decode(value['native_stdout']['data']),raw)
            self.assertFalse(value['work_completion_inferred'])
            self.assertFalse(value['native_state_changed'])
            self.assertEqual(calls[0][0][3:],[kind,'inspect',str(self.work),'1'])
            self.expect('NATIVE_RESPONSE',lambda:self.invoke('report_read',{'kind':kind,'sequence':1},b'\xff'))
        self.assertEqual(before,self.inventory())
    def test_stale_failure_and_malformed_json_do_not_deliver(self):
        self.expect('OBSERVATION_STALE',lambda:self.invoke('profile_read',{'operation':'current'},stale=True))
        self.expect('NATIVE_FAILURE',lambda:self.invoke('profile_read',{'operation':'current'},returncode=1))
        self.expect('NATIVE_FAILURE',lambda:self.invoke('profile_read',{'operation':'current'},reason='TIMEOUT'))
        for raw in (b'{bad',b'{"x":1,"x":2}',b'not-json'):
            self.expect('NATIVE_RESPONSE',lambda:self.invoke('profile_read',{'operation':'current'},raw))
    def test_text_and_jsonl_keep_original_bytes(self):
        for name,args,raw in (('context_read',{'operation':'markdown','request_json':'{}'},b'# data\n'),('discovery_read',{'operation':'report','request_json':'{}','kind':'scope'},b'# scope\n')):
            value,_=self.invoke(name,args,raw);self.assertEqual(base64.b64decode(value['native_stdout']['data']),raw)
    def test_request_json_original_bytes_and_limits(self):
        value,calls=self.invoke('native_validate',{'kind':'completion','request_json':'{ "schema_version":1 }\n'})
        request_path=Path(calls[0][0][-1]);self.assertEqual(request_path.read_bytes(),b'{ "schema_version":1 }\n')
        self.expect('JSON_INVALID',lambda:self.invoke('native_validate',{'kind':'role','request_json':'{"x":1,"x":2}'}))
    def test_quota_and_result_budget_never_truncate_or_delete(self):
        with patch.object(reads.backend,'_quota',side_effect=c.IntegrationError('AUDIT_QUOTA')),patch.object(reads.records,'capture',side_effect=AssertionError('no launch')):
            self.expect('AUDIT_QUOTA',lambda:self.invoke('profile_read',{'operation':'current'}))
        self.policy['max_result_bytes']=4096;self.save_policy();self.api=service.Service(self.adapter())
        raw=c.encoded({'value':'x'*3000})
        self.expect('RESULT_BUDGET_EXCEEDED',lambda:self.invoke('profile_read',{'operation':'current'},raw))
        spool=list(self.registry.root.glob('read-m1-*'))[-1];self.assertEqual((spool/'stdout.log').read_bytes(),raw);self.assertTrue((spool/'failure.json').exists())
    def test_oneof_does_not_accept_ambiguous_or_unlisted_shapes(self):
        self.expect('SCHEMA',lambda:c._validate({},reads.variants(c.obj({}),c.obj({}))))
        c._validate({'project_id':'p','work_id':'a','operation':'list'},reads.SCHEMAS['template_read'])
    def test_producer_includes_new_module_and_old_scopes_do_not_expand(self):
        self.assertIn('integration_reads.py',transfer.producer());self.assertIn('integration_reads.py',transfer.PRODUCER_NAMES)
        self.policy['scopes'][0]['tools']=['work_inspect'];self.save_policy();self.assertEqual(service.Service(self.adapter()).tools(),['work_inspect'])
    def test_journal_payload_is_explicit_data_not_a_caller_path(self):
        value,calls=self.invoke('journal_read',{'operation':'inspect','stream_base64':base64.b64encode(b'data').decode()})
        path=Path(calls[0][0][-1]);self.assertEqual(path.read_bytes(),b'data');self.assertTrue(path.is_relative_to(self.registry.root))

    def test_document_validator_and_adapter_diagnostics_are_read_only_fixed_commands(self):
        _,calls=self.invoke('native_validate',{'kind':'document','request_json':'{}','body_text':'body\n'})
        self.assertEqual(calls[0][0][3:5],['document','validate']);self.assertEqual(Path(calls[0][0][-1]).read_bytes(),b'body\n')
        for fields,expected in (({'kind':'noop_adapter'},['adapter','noop','probe']),({'kind':'adapter_current','adapter_id':'codex','session_id':''},['adapter','describe','--current','codex',''])):
            _,calls=self.invoke('diagnostic_read',fields);self.assertEqual(calls[0][0][3:],expected)
    def test_events_cannot_read_runtime_from_work_scope(self):
        self.expect('READ_RESOURCE_POLICY_REQUIRED',lambda:self.api.call('events_read',{'project_id':'p','work_id':'a','resource_id':'r','operation':'export','format':'jsonl','after':''}))
    def test_context_proof_is_explicit_preserved_and_never_published(self):
        proof='{ "schema_version":1 }\n'
        _,calls=self.invoke('context_read',{'operation':'render','request_json':'{}','token_count_json':proof})
        self.assertEqual(calls[0][0][3:5],['context','render']);self.assertEqual(calls[0][0][-2],'--token-count')
        self.assertEqual(Path(calls[0][0][-1]).read_bytes(),proof.encode())

class TransportCallbacks(unittest.TestCase):
    """Callback fixture with an explicit SDK double; never a live MCP client."""
    def build(self,adapter):
        import types
        class Fields:
            def __init__(self,*args,**kw):self.__dict__.update(kw)
        class Receiver:
            def __init__(self):self.calls=[]
            def tools(self):return ['workflow_read','events_read']+(['session_claim'] if adapter.__name__.endswith('mutation_mcp') else [])
            def call(self,name,args):self.calls.append((name,args));return {'state':'AVAILABLE','content_role':'UNTRUSTED_DATA','data':args,'native_execution_verified':False}
        async def run_sync(fn,*args):return fn(*args)
        modules={'mcp':types.ModuleType('mcp'),'mcp.server':types.ModuleType('mcp.server'),'mcp.types':types.ModuleType('mcp.types'),'anyio':types.ModuleType('anyio')}
        modules['mcp.server'].Server=Fields
        for name in ('CallToolResult','ListToolsResult','TextContent','Tool','ToolAnnotations'):setattr(modules['mcp.types'],name,Fields)
        modules['anyio'].to_thread=types.SimpleNamespace(run_sync=run_sync)
        receiver=Receiver()
        with patch.dict('sys.modules',modules),patch.object(adapter,'version',return_value='2.3.0'),patch('integration_mcp.server_icons',return_value=[]):instance=adapter.server(receiver)
        return instance,receiver,modules
    def check(self,adapter):
        import asyncio
        import types
        instance,receiver,modules=self.build(adapter)
        with patch.dict('sys.modules',modules):
            listing=asyncio.run(instance.on_list_tools(None,None))
            byname={tool.name:tool for tool in listing.tools}
            self.assertEqual(byname['golem_workflow_read'].inputSchema,service.SCHEMAS['workflow_read'])
            self.assertEqual(byname['golem_events_read'].inputSchema,service.SCHEMAS['events_read'])
            args={'project_id':'p','work_id':'a','operation':'next','selection_id':'s'}
            result=asyncio.run(instance.on_call_tool(None,types.SimpleNamespace(name='golem_workflow_read',arguments=args)))
            self.assertEqual(receiver.calls,[('workflow_read',args)]);self.assertEqual(c.decode(result.content[0].text.encode())['data'],args)
            bad=asyncio.run(instance.on_call_tool(None,types.SimpleNamespace(name='other_workflow_read',arguments=args)))
            self.assertTrue(bad.isError);self.assertEqual(len(receiver.calls),1)
    def test_d2_callback_lists_schemas_and_preserves_read_arguments(self):
        import integration_mcp
        self.check(integration_mcp)
    def test_d4_callback_uses_same_read_schemas_and_does_not_transform_arguments(self):
        import integration_mutation_mcp
        self.check(integration_mutation_mcp)

class ExecutionReportReads(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','setUp','invoke'):
        locals()[name]=getattr(NativeReads,name)
    def test_execution_report_and_bundle_are_bound_read_commands(self):
        metadata={'work_id':'a','execution_receipt':'c'*64}
        self.record['documents'][0]['metadata']=metadata
        _,calls=self.invoke('report_read',{'kind':'execution_render','request_json':c.encoded(metadata).decode()},b'# observed report\n')
        self.assertEqual(calls[0][0][3:5],['execution','render'])
        for kind,fields,prefix in [('execution_bundle_inspect',{'receipt_digest':'c'*64},['execution','bundle','inspect']),('execution_bundle_verify',{'request_json':c.encoded({'qa_receipt':'c'*64}).decode()},['execution','bundle','verify'])]:
            _,calls=self.invoke('report_read',{'kind':kind,**fields});self.assertEqual(calls[0][0][3:6],prefix)
        self.expect('READ_RECEIPT_BINDING',lambda:self.invoke('report_read',{'kind':'execution_bundle_inspect','receipt_digest':'d'*64}))
        self.expect('READ_REPORT_WORK_BINDING',lambda:self.invoke('report_read',{'kind':'execution_render','request_json':'{"work_id":"other"}'}))
