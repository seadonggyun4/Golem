"""Common D2 Work Pack with real native CLI, isolated registry and Work only."""
import sys,unittest,json
from pathlib import Path
from integration_d2_mcp import D2
import integration_service as service
import integration_transfer as transfer
import integration_contract as c
from discovery_integration import SOURCE

class WorkPack(D2):
    def test_workpack_native_reads(self):
        path,digest=self.make_policy();api=service.Service(transfer.Transfer(path,digest,approve_data_transfer=True))
        before=self.inventory();pack=(SOURCE/'samples/workpacks/dataset-release-gate.json').read_text()
        for op in ('validate','inspect','compatibility'):
            args={'project_id':'project','work_id':'example-work','operation':op,'pack_json':pack}
            if op=='compatibility':args['core_version']='0.1.0'
            result=api.call('workpack_read',args)
            self.assertEqual(result['state'],'AVAILABLE');self.assertFalse(result['execution_authorized'])
            self.assertEqual(result['result']['exact_digest'],c.sha(pack.encode()))
        proposal=(SOURCE/'samples/workpacks/verifier-proposal.json').read_text()
        value=api.call('workpack_read',{'project_id':'project','work_id':'example-work','operation':'proposal_validate','proposal_json':proposal})
        self.assertTrue(value['result']['structurally_valid']);self.assertFalse(value['result']['authorized'])
        with self.assertRaises(c.IntegrationError):api.call('workpack_read',{'project_id':'project','work_id':'example-work','operation':'validate','pack_json':'{}'})
        self.assertEqual(before,self.inventory())

    def test_native_catalog_resource_snapshot(self):
        import integration_read_resources as resources
        path,digest=self.make_policy();policy=transfer.Transfer(path,digest,approve_data_transfer=True)
        pack=(SOURCE/'samples/workpacks/dataset-release-gate.json').read_bytes();manifest=json.loads(pack)
        entry={**{k:manifest[k] for k in ('id','version','schema','status','intent','negative_intent','capabilities')},'digest':c.sha(pack),'manifest':'pack.json','aliases':['dataset'],'category':'data quality'}
        inputs={'pack.json':pack,'index.json':c.encoded({'schema':'golem.workpack.catalog.v0','entries':[entry]})};files=[]
        for i,(name,raw) in enumerate(inputs.items()):
            f=self.root/name;f.write_bytes(raw);files.append({'file_id':'f'+str(i),'name':name,'path':str(f),'sha256':c.sha(raw),'tools':['workpack_resource_read']})
        resource={'schema':'golem.integration-read-resources.v1','transfer_policy_sha256':digest,'data_class':'EXPLICIT_OWNER_SELECTED_READ_CONTENT','assurance':'LOCAL_COOPERATIVE','resources':[{'project_id':'project','work_id':'example-work','resource_id':'catalog','files':files}],'producer':resources.producer()}
        rp=self.write('resources.json',resource);rp.chmod(0o600);api=service.Service(policy,resources.Resources(rp,c.sha(rp.read_bytes()),policy,approve_resources=True));before=self.inventory()
        for operation in ('list','search'):
            args={'project_id':'project','work_id':'example-work','resource_id':'catalog','operation':operation,'index_name':'index.json'}
            if operation=='search':args['query']='dataset'
            result=api.call('workpack_resource_read',args)['result']['value'];self.assertFalse(result['authorized']);self.assertEqual(len(result['entries']),1)
        self.assertEqual(before,self.inventory())

    def test_reference_observation_is_not_tool_execution(self):
        path,digest=self.make_policy();api=service.Service(transfer.Transfer(path,digest,approve_data_transfer=True));pack=(SOURCE/'samples/workpacks/dataset-release-gate.json').read_text()
        config=json.dumps({'schema':'golem.workpack.truthound-config.v0','producer_version':'3.3.1','producer_digest':'0'*64,'max_file_bytes':104857600,'max_items':100,'max_response_bytes':65536,'timeout_seconds':30})
        capture={'schema':'golem.workpack.truthound-capture.v0','mode':'MOCK','pack_json':pack,'source':{'digest':'a'*64,'size':1},'config_json':config,'results':[{'tool':tool,'response_json':json.dumps({'schema_version':1,'operation':op,'ok':False,'data':None,'truncated':False,'error':{'code':'MOCK_ONLY'}})} for tool,op in [('check_file','check'),('profile_file','profile'),('scan_pii','scan')]]}
        result=api.call('workpack_read',{'project_id':'project','work_id':'example-work','operation':'reference_observe','capture_json':json.dumps(capture),'source_sha256':'a'*64,'config_sha256':c.sha(config.encode()),'pack_sha256':c.sha(pack.encode())})['result']
        self.assertEqual(result['quality'],'TOOL_FAILED');self.assertFalse(result['authorized']);self.assertEqual(result['release_readiness'],'NOT_EVALUATED')

    def test_workpack_protocol_modes(self):
        import asyncio
        from mcp import Client, StdioServerParameters
        path,digest=self.make_policy();before=self.inventory()
        async def exercise():
            for mode in ('auto','legacy'):
                params=StdioServerParameters(command=sys.executable,args=[str(SOURCE/'tools/integration_mcp.py'),'--policy',str(path),'--reviewed-policy-sha256',digest,'--approve-data-transfer'],cwd=str(self.root))
                async with Client(params,mode=mode,read_timeout_seconds=30) as client:
                    tools=await client.list_tools();names={t.name for t in tools.tools}
                    self.assertIn('golem_workpack_read',names);self.assertNotIn('golem_workpack_resource_read',names)
                    value=await client.call_tool('golem_workpack_read',{'project_id':'project','work_id':'example-work','operation':'inspect','pack_json':(SOURCE/'samples/workpacks/dataset-release-gate.json').read_text()})
                    self.assertFalse(value.is_error);self.assertFalse(json.loads(value.content[0].text)['execution_authorized'])
        asyncio.run(asyncio.wait_for(exercise(),90));self.assertEqual(before,self.inventory())

if __name__=='__main__':unittest.main(defaultTest=['WorkPack.test_workpack_native_reads','WorkPack.test_workpack_protocol_modes','WorkPack.test_reference_observation_is_not_tool_execution','WorkPack.test_native_catalog_resource_snapshot'])
