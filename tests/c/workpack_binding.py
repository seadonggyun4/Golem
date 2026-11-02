"""Opt-in M4 binding in disposable native document Works only."""
import sys,pathlib,json,copy,hashlib,subprocess,unittest,fcntl
FAULT=pathlib.Path(sys.argv.pop(3)).resolve()
OLD=pathlib.Path(sys.argv.pop(3)).resolve() if len(sys.argv)>3 else None
from workflow_integration import Workflow
from discovery_integration import CLI,SOURCE,ENV
for name in list(ENV):
    if name.startswith("GOLEM_"): ENV.pop(name)
class Binding(Workflow):
    def prepare(self):
        self.setup_work(mode='documents');self.register_selection()
        self.contract=self.cli('role','template','doc-only')
        self.rd=self.cli('role','validate',self.write('contract.json',self.contract))['contract_digest']
        self.cli('role','call',self.work,self.write('enroll.json',dict(schema_version=1,operation='enroll',selection_id='selection',key='enroll',expected_generation=self.generation,contract=self.contract)),'--approve-contract',self.rd)
        self.pack=json.loads((SOURCE/'samples/workpacks/dataset-release-gate.json').read_text())
        self.pack.update(roles=['doc-only'],capabilities=['document.read','role.evaluate'],inputs=['selection'],evidence=['native-role-assessment'],prohibited_effects=['execution.run','network.upload','release.publish'])
        self.request=dict(schema_version=1,key='binding-one',selection_id='selection',expected_generation=self.generation,mapping='native-documents-v1',role_contract_digest=self.rd,pack_json=json.dumps(self.pack))
        return self.write('bind.json',self.request)
    def snapshot(self):
        return {str(p.relative_to(self.work)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.work.rglob('*') if p.is_file()}
    def test_pack_binding(self):
        request=self.prepare();before=self.snapshot()
        if OLD:
            old=subprocess.run([str(OLD),'workflow','next',str(self.work),'selection'],capture_output=True,env=ENV);self.assertEqual(old.returncode,0,old.stderr)
        resolved=self.cli('pack','resolve',self.work,request);self.assertFalse(resolved['authorized']);self.assertEqual(before,self.snapshot())
        digest=resolved['binding_digest']
        self.cli('pack','bind',self.work,request,ok=False)
        self.cli('pack','bind',self.work,request,'--approve-binding',self.rd,ok=False)
        self.assertEqual(before,self.snapshot())
        first=self.cli('pack','bind',self.work,request,'--approve-binding',digest)
        saved=self.snapshot()
        self.assertEqual(first,self.cli('pack','bind',self.work,request,'--approve-binding',digest));self.assertEqual(saved,self.snapshot())
        report=self.cli('pack','explain',self.work);self.assertEqual(report['receipt_digest'],first['receipt_digest']);self.assertEqual(report['current_mapping'],'APPLICABLE');self.assertFalse(report['execution_authorized'])
        self.assertEqual(saved,self.snapshot())
        if OLD:
            old=subprocess.run([str(OLD),'workflow','next',str(self.work),'selection'],capture_output=True,env=ENV);self.assertNotEqual(old.returncode,0);self.assertIn(b'GOLEM_ERR_CORRUPT_JOURNAL',old.stderr)
        else: print('old reader comparison NOT_RUN: set GOLEM_WORKPACK_BASELINE_CLI')
        self.cli('pack','resolve',self.work,request,ok=False)
        self.cli('pack','bind',self.work,self.write('other.json',dict(self.request,key='other')),'--approve-binding',digest,ok=False)
        self.cli('pack','bind',self.work,self.write('space.json',request.read_text()+' '),'--approve-binding',digest,ok=False)
        self.assertEqual(saved,self.snapshot())
        self.register_selection()
        self.assertEqual(self.cli('pack','explain',self.work)['current_mapping'],'BLOCKED')
        # Exact request remains historical despite subsequent native progress.
        self.assertEqual(first,self.cli('pack','bind',self.work,request,'--approve-binding',digest))
    def test_pack_stale_and_unsupported(self):
        request=self.prepare();digest=self.cli('pack','resolve',self.work,request)['binding_digest'];before=self.snapshot()
        for field,value in [('roles',['proposer']),('capabilities',['execution.run']),('inputs',['source-snapshot']),('evidence',['quality-result']),('prohibited_effects',['document.read']),('core_min','0.2.0')]:
            p=dict(self.pack);p[field]=value
            if field=='core_min':p['core_max']='0.2.0'
            self.cli('pack','resolve',self.work,self.write('bad.json',dict(self.request,pack_json=json.dumps(p))),ok=False)
        for field,value in [('expected_generation',99),('role_contract_digest','0'*64),('selection_id','foreign'),('mapping','external'),('extra',True)]:
            self.cli('pack','resolve',self.work,self.write('bad.json',dict(self.request,**{field:value})),ok=False)
        self.assertEqual(before,self.snapshot())
        self.cli('role','call',self.work,self.write('assess.json',dict(schema_version=1,operation='assess',selection_id='selection',key='assessment',expected_generation=self.generation,review=None)))
        self.cli('pack','bind',self.work,request,'--approve-binding',digest,ok=False)
        updated=self.cli('pack','resolve',self.work,request)['binding_digest'];self.assertNotEqual(digest,updated)
        self.cli('pack','bind',self.work,request,'--approve-binding',updated)
    def test_pack_fault_before(self):
        request=self.prepare()
        p=subprocess.run([str(FAULT),str(self.work),str(request),'0'],capture_output=True,env=ENV,timeout=30);self.assertEqual(p.returncode,0,p.stderr)
    def test_pack_fault_after(self):
        request=self.prepare()
        p=subprocess.run([str(FAULT),str(self.work),str(request),'1'],capture_output=True,env=ENV,timeout=30);self.assertEqual(p.returncode,0,p.stderr)
    def test_pack_session_unknown(self):
        request=self.prepare()
        self.cli('session','call',self.work,self.write('start.json',dict(schema_version=1,operation='start',work_id='example-work',key='start',expected_sequence=0,selection_id='selection')))
        before=self.snapshot()
        self.cli('pack','resolve',self.work,request,ok=False)
        self.assertEqual(before,self.snapshot())
    def test_pack_lock(self):
        request=self.prepare();before=self.snapshot()
        import os
        fd=os.open(self.work,os.O_RDONLY)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.cli('pack','resolve',self.work,request,ok=False)
            self.cli('pack','bind',self.work,request,'--approve-binding','0'*64,ok=False)
        finally:os.close(fd)
        self.assertEqual(before,self.snapshot())
    def test_pack_cas_tamper(self):
        request=self.prepare();digest=self.cli('pack','resolve',self.work,request)['binding_digest'];self.cli('pack','bind',self.work,request,'--approve-binding',digest)
        target=hashlib.sha256(self.request['pack_json'].encode()).hexdigest()
        found=[p for p in self.work.rglob('*') if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==target];self.assertTrue(found)
        p=found[0];p.chmod(0o600);p.write_bytes(b'bad')
        self.cli('pack','explain',self.work,ok=False)
if __name__=='__main__':
    unittest.main(defaultTest=['Binding.test_pack_binding','Binding.test_pack_stale_and_unsupported','Binding.test_pack_cas_tamper','Binding.test_pack_fault_before','Binding.test_pack_fault_after','Binding.test_pack_lock','Binding.test_pack_session_unknown'])
