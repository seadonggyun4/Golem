import hashlib
import json
import unittest
from unittest.mock import patch
from capability_execution import inspect_execution


def raw(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def meta(data):
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def execution():
    objects = {'started.json': {'schema': 'golem.execution-observation.v1', 'state': 'STARTED',
        'invocation_id': 'one', 'argv': ['python3','-m','unittest'], 'extra_logs': []},
        'result.json': {'schema': 'golem.execution-observation.v1', 'state': 'FINISHED',
        'invocation_id': 'one', 'process': {'returncode': 0, 'reason': 'EXIT'}},
        'source-before.json': {'status': 'UNAVAILABLE'}, 'source-after.json': {'status': 'UNAVAILABLE'}}
    files = {'execution/'+k: raw(v) for k,v in objects.items()}
    files['stdout.log'] = b'OK\n'
    files['stderr.log'] = b''
    manifest = {'schema':'golem.execution-manifest.v1',
                'files':{k:meta(files['execution/'+k]) for k in objects},
                'logs': {k:meta(files[k]) for k in ('stdout.log','stderr.log')}, 'native_files':{}}
    files['execution/manifest.json'] = raw(manifest)
    return files


def agent():
    plan={'schema':'golem.agent-command-plan.v1','task':'code','commands':[{'id':'test','argv':['python3','-m','unittest'],'timeout':30}]}
    identity=hashlib.sha256(raw(plan)).hexdigest()
    source={'commit':'a'*40,'tree_sha256':'b'*64,'files':{}}
    record={'schema':'golem.agent-observation.v1','plan_sha256':identity,'steps':[
        {'id':'test','status':'EXIT_OK','returncode':0,'reason':'EXIT','logs':{'stdout.log':meta(b'OK')}}]}
    files={'plan.json':raw(plan),'started.json':raw({'schema':'golem.agent-observation.v1','plan_sha256':identity}),
           'record.json':raw(record),'source-before.json':raw(source),'source-after.json':raw(source),'test/stdout.log':b'OK'}
    child=execution()
    files.update({'test/'+p:b for p,b in child.items()})
    record['steps'][0]['logs']={'stdout.log':meta(child['stdout.log'])}
    files['record.json']=raw(record)
    files['manifest.json']=raw({'schema':'golem.agent-observation-manifest.v1','files':{p:hashlib.sha256(b).hexdigest() for p,b in files.items()}})
    return files, source


class Adapters(unittest.TestCase):
    def test_execution_integrity_not_test_pass(self):
        with patch('builtins.open', side_effect=AssertionError('no IO')):
            result=inspect_execution(execution(),'execution')
        self.assertTrue(result.file_integrity_verified)
        self.assertFalse(result.test_execution_verified)
        self.assertFalse(result.authenticity_verified)
        self.assertIsNone(result.source_matches)

    def test_tampered_log_rejected(self):
        files=execution(); files['stdout.log']=b'forged'
        with self.assertRaisesRegex(ValueError,'DIGEST'):
            inspect_execution(files,'execution')

    def test_missing_and_extra_block(self):
        files=execution(); del files['execution/result.json']
        self.assertFalse(inspect_execution(files,'execution').file_integrity_verified)
        files=execution(); files['extra']=b''
        self.assertFalse(inspect_execution(files,'execution').file_integrity_verified)

    def test_native_not_silently_ignored(self):
        files=execution(); manifest=json.loads(files['execution/manifest.json'])
        manifest['native_files']={'a'*32+'/':{'kind':'directory'}}
        files['execution/manifest.json']=raw(manifest)
        self.assertFalse(inspect_execution(files,'execution').file_integrity_verified)

    def test_agent_plan_and_step_binding(self):
        files,source=agent(); result=inspect_execution(files,'agent',expected_source=source)
        self.assertTrue(result.file_integrity_verified)
        self.assertTrue(result.source_matches)
        self.assertFalse(result.sufficiency_verified)
        source['commit']='c'*40
        self.assertFalse(inspect_execution(files,'agent',expected_source=source).source_matches)

    def test_agent_native_child_is_verified_without_execution_claim(self):
        files,_=agent(); child=execution(); identity='b'*32
        prefix='native/'+identity+'/'
        values={'started.json':{'schema':'golem.native-record.v1','id':identity,'state':'STARTED'},
                'result.json':{'schema':'golem.native-record.v1','id':identity,'state':'FINISHED','recording_status':0}}
        for name,value in values.items(): child[prefix+name]=raw(value)
        child[prefix+'manifest.json']=raw({n:hashlib.sha256(child[prefix+n]).hexdigest() for n in values})
        manifest=json.loads(child['execution/manifest.json'])
        manifest['native_files']={identity+'/':{'kind':'directory'}, **{identity+'/'+n:meta(child[prefix+n]) for n in (*values,'manifest.json')}}
        child['execution/manifest.json']=raw(manifest)
        files.update({'test/'+p:b for p,b in child.items()})
        files['manifest.json']=raw({'schema':'golem.agent-observation-manifest.v1','files':{p:hashlib.sha256(b).hexdigest() for p,b in files.items() if p!='manifest.json'}})
        result=inspect_execution(files,'agent')
        self.assertTrue(result.file_integrity_verified)
        self.assertFalse(result.authenticity_verified)
        self.assertIn(('CHILD_SOURCE_UNOBSERVED','test/source'),result.blockers)

    def test_child_exit_mismatch_with_valid_outer_hashes(self):
        files, _ = agent()
        record=json.loads(files['record.json']); record['steps'][0]['returncode']=7
        files['record.json']=raw(record)
        manifest=json.loads(files['manifest.json'])
        manifest['files']['record.json']=hashlib.sha256(files['record.json']).hexdigest()
        files['manifest.json']=raw(manifest)
        with self.assertRaisesRegex(ValueError, 'CHILD_EXIT_MISMATCH'):
            inspect_execution(files,'agent')

    def test_child_missing_is_not_success(self):
        files,_=agent(); del files['test/execution/result.json']
        manifest=json.loads(files['manifest.json'])
        del manifest['files']['test/execution/result.json']
        files['manifest.json']=raw(manifest)
        result=inspect_execution(files,'agent')
        self.assertFalse(result.file_integrity_verified)
        self.assertIn(('CHILD_INTEGRITY_UNVERIFIED','test'), result.blockers)

    def test_parent_and_child_share_node_budget(self):
        files,_=agent()
        with patch('capability_execution.NODES_MAX', 45):
            with self.assertRaisesRegex(ValueError,'JSON_NODE_LIMIT'):
                inspect_execution(files,'agent')

    def test_agent_forged_plan_even_rehashed_manifest(self):
        files,_=agent(); plan=json.loads(files['plan.json']); plan['task']='docs'; files['plan.json']=raw(plan)
        manifest=json.loads(files['manifest.json']); manifest['files']['plan.json']=hashlib.sha256(files['plan.json']).hexdigest()
        files['manifest.json']=raw(manifest)
        with self.assertRaisesRegex(ValueError,'PLAN_BINDING'):
            inspect_execution(files,'agent')

    def test_private_redacted_not_same_proof(self):
        files={p:raw(v) for p,v in {
            'started.json':{'schema':'golem.private-process-observation.v1','argv_redacted':True,'streams_recorded':False},
            'result.json':{'schema':'golem.private-process-result.v1','returncode':0,'reason':'EXIT'},
            'source-before.json':{},'source-after.json':{}}.items()}
        result=inspect_execution(files,'private')
        self.assertFalse(result.file_integrity_verified)
        self.assertEqual(result.commands,())
        self.assertIn(('NO_MANIFEST_BINDING','private'),result.blockers)

    def test_native_complete_manifest_is_integrity_only(self):
        files=execution(); identity='a'*32; prefix='native/'+identity+'/'
        values={'started.json':{'schema':'golem.native-record.v1','id':identity,'state':'STARTED'},
                'result.json':{'schema':'golem.native-record.v1','id':identity,'state':'FINISHED','recording_status':0}}
        for name,value in values.items(): files[prefix+name]=raw(value)
        files[prefix+'manifest.json']=raw({name:hashlib.sha256(files[prefix+name]).hexdigest() for name in values})
        manifest=json.loads(files['execution/manifest.json'])
        manifest['native_files']={identity+'/':{'kind':'directory'}, **{identity+'/'+n:meta(files[prefix+n]) for n in (*values,'manifest.json')}}
        files['execution/manifest.json']=raw(manifest)
        result=inspect_execution(files,'execution')
        self.assertTrue(result.file_integrity_verified)
        self.assertFalse(result.test_execution_verified)
        files[prefix+'result.json']=b'{}'
        with self.assertRaises(ValueError): inspect_execution(files,'execution')

    def test_unknown_and_incomplete_source_not_inferred(self):
        with self.assertRaises(ValueError): inspect_execution({},'auto')
        with self.assertRaisesRegex(ValueError,'EXPECTED_SOURCE_INCOMPLETE'):
            inspect_execution(execution(),'execution',expected_source={})


if __name__=='__main__': unittest.main()
