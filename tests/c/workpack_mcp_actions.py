"""Actual common MCP service to native Work Pack binding/publication, disposable only."""
from workpack_binding import Binding
from discovery_integration import SOURCE,CLI
import sys,json,unittest,base64
sys.path.insert(0,str(SOURCE/'tools'))
import integration_registry as r
import integration_contract as c
import integration_transfer as t
import integration_mutation_contract as mc
import integration_mutations as mutations
import integration_read_resources as resources
import integration_service as reads

class Actions(Binding):
    def setup_api(self):
        self.prepare();project=self.root/'project';target=project/'.golem/works/work';target.parent.mkdir(parents=True);self.work.rename(target);self.work=target
        self.registry=r.Registry.create(self.root/'registry',approve_local_owner=True)
        enrollment={'schema':'golem.integration-enrollment.v1','project':r.describe('project',project,CLI,[SOURCE/'samples/agent-session/status.json'],[('example-work',self.work)]),'grants':[{'schema':'golem.integration-grant.v1','principal_id':'owner','client_id':'fixture','operations':['status','next','record','history'],'work_ids':['example-work'],'destination':'LOCAL_HOST','assurance':'LOCAL_COOPERATIVE'}]}
        self.registry.apply(enrollment,self.registry.plan(enrollment)['plan_sha256'],approve_local_owner=True)
        binding={'schema':'golem.integration-client-binding.v1','project_id':'project','generation':1,'principal_id':'owner','client_id':'fixture','assurance':'LOCAL_COOPERATIVE'}
        value={'schema':'golem.integration-transfer.v1','registry':str(self.registry.root),'registry_identity':self.registry.root_identity,'destination':'LOCAL_HOST','destination_id':'fixture','data_class':'APPROVED_WORK_CONTENT','max_result_bytes':8388608,'scopes':[{'binding':binding,'work_ids':['example-work'],'tools':list(t.NAMES),'recipients':[]}],'producer':t.producer()}
        self.tp=self.pin('transfer.json',value);self.transfer=t.Transfer(self.tp['path'],self.tp['sha256'],approve_data_transfer=True)
        self.reader=reads.Service(self.transfer);self.ids={'project_id':'project','work_id':'example-work'}
    def pin(self,name,value):
        p=self.write(name,value);p.chmod(0o600);return {'path':str(p),'sha256':c.sha(p.read_bytes())}
    def action(self,tool,value):
        envelope={'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),'body':'','context_json':'','count_json':'','approval':None}
        entry={**self.ids,'action_id':tool,'tool':tool,'session_id':'owner','native_binding_id':'','action':self.pin(tool+'-action.json',envelope)}
        pp=self.pin(tool+'-policy.json',{'schema':'golem.integration-mutations.v1','transfer_policy':self.tp,'actions':[entry],'producer':mc.producer()})
        api=mutations.Service(mc.Policy(pp['path'],pp['sha256'],approve_mutations=True));args={**self.ids,'action_id':tool,'request_id':tool+'-request'}
        result=api.call(tool,args);saved=self.snapshot();self.assertEqual(api.call(tool,args),result);self.assertEqual(saved,self.snapshot())
        self.assertEqual(result['state'],'NATIVE_RESULT_RECORDED',result);self.assertFalse(result['execution_authorized']);return result['native_reply']
    def test_full_native_mcp_chain(self):
        self.setup_api();request=json.dumps(self.request)
        resolved=self.reader.call('workpack_read',{**self.ids,'operation':'resolve','request_json':request})['result']
        bound=self.action('workpack_bind',{'request_json':request,'approval_digest':resolved['binding_digest']})
        explained=self.reader.call('workpack_read',{**self.ids,'operation':'explain'})['result'];self.assertEqual(explained['receipt_digest'],bound['receipt_digest'])
        doc=self.docs['selection'];body_digest=doc['body_digest'];body=next(p.read_bytes() for p in self.work.rglob('*') if p.is_file() and c.sha(p.read_bytes())==body_digest)
        proposal=json.loads((SOURCE/'samples/workpacks/verifier-proposal.json').read_text());proposal.update(work={'identity':'example-work','generation':self.generation},pack_digest=c.sha(self.request['pack_json'].encode()),binding_receipt=bound['receipt_digest'],contract_digest=self.rd,artifacts=[{'digest':body_digest,'size':len(body)}])
        assessed=self.reader.call('workpack_read',{**self.ids,'operation':'assess','proposals':[json.dumps(proposal)]})['result']
        self.assertFalse(assessed['authorized']);self.assertFalse(assessed['completion_evaluated']);self.assertEqual(assessed['native_role_evaluation']['state'],'UNSATISFIED')
        d=self.docs['selection'];receipt={'schema':'golem.workpack.receipt-request.v0','expected_generation':self.generation,'binding_receipt':bound['receipt_digest'],'documents':[{'document_id':'selection','revision':d['revision'],'digest':d['manifest_digest']}]}
        parent=self.root/'exports';parent.mkdir(mode=0o700);args={'request_json':json.dumps(receipt),'output_parent':str(parent),'output_identity':r.identity(parent),'format':'json'};before=self.snapshot()
        manifest=self.action('workpack_receipt_manifest',args);self.assertEqual(list(parent.iterdir()),[])
        exported=self.action('workpack_receipt_export',{**args,'approval_digest':manifest['approval_digest']});self.assertEqual(exported['manifest_digest'],manifest['manifest_digest']);self.assertEqual(before,self.snapshot())
        directory=parent/exported['manifest_digest'];files=[{'file_id':'f'+str(i),'name':p.name,'path':str(p),'sha256':c.sha(p.read_bytes()),'tools':['workpack_resource_read']} for i,p in enumerate(sorted(directory.iterdir())) if p.is_file()]
        policy={'schema':'golem.integration-read-resources.v1','transfer_policy_sha256':self.transfer.digest,'data_class':'EXPLICIT_OWNER_SELECTED_READ_CONTENT','assurance':'LOCAL_COOPERATIVE','resources':[{**self.ids,'resource_id':'receipt','files':files}],'producer':resources.producer()}
        pin=self.pin('resources.json',policy);api=reads.Service(self.transfer,resources.Resources(pin['path'],pin['sha256'],self.transfer,approve_resources=True))
        verified=api.call('workpack_resource_read',{**self.ids,'resource_id':'receipt','operation':'receipt_verify','manifest_sha256':manifest['manifest_digest']})['result']['value']
        self.assertEqual(verified['integrity'],'VERIFIED');self.assertFalse(verified['completion_verified']);self.assertEqual(before,self.snapshot())

if __name__=='__main__':unittest.main(defaultTest=['Actions.test_full_native_mcp_chain'])
