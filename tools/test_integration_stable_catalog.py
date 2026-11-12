"""Opt-in broker/catalog fixtures. No installed client, real policy or Work calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import integration_contract as c
import integration_feature_profiles as profiles
import integration_service as reads
import integration_stable_catalog as builder
import integration_mcp as wire
import integration_mutation_contract as actions

SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/golem/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location('catalog_fixture_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = load('launcher')
contract = load('stable_contract')
contract._VERIFIED_TYPED_INDEX = builder.typed_inventory()


class Catalog(unittest.TestCase):
    def test_explicit_typed_subset_deterministic_and_current_schemas(self):
        first = builder.catalog('task', ['document_submit','projects_list'])
        second = builder.catalog('task', ['projects_list','document_submit'])
        self.assertEqual(first,second)
        self.assertEqual(contract.validate_catalog(builder.encoded(first)),first)
        self.assertEqual(first['tools'][1]['inputSchema'],reads.SCHEMAS['projects_list'])
        self.assertIn('does not grant',first['tools'][0]['description'])
        self.assertEqual([row['name'] for row in first['tools']],['golem_document_submit','golem_projects_list'])

    def test_no_implicit_full_profile_or_unknown_scope(self):
        for profile,names in [('task',[]),('task',['projects_list']*2),
                              ('read',['document_submit']),('task',['generic_dispatch']),
                              ('task',['task_dag_scheduler'])]:
            with self.subTest(profile=profile,names=names),self.assertRaises(c.IntegrationError):
                builder.catalog(profile,names)

    def test_mutating_candidate_never_changes_existing_schema(self):
        before=copy.deepcopy(reads.SCHEMAS['work_inspect'])
        value=builder.catalog('task',['work_inspect'])
        value['tools'][0]['inputSchema']['properties'].clear()
        self.assertEqual(reads.SCHEMAS['work_inspect'],before)

    def test_definition_build_does_not_probe_service_or_dispatch(self):
        with patch('subprocess.Popen',side_effect=AssertionError('no process')):
            value=builder.catalog('task',['document_submit','work_inspect'])
        self.assertEqual(len(value['tools']),2)

    def test_fixed_definition_does_not_change_existing_owner_gate(self):
        class Backend:
            def __init__(self): self.allowed=[];self.calls=[]
            def tools(self): return self.allowed
            def call(self,name,args): self.calls.append((name,args));return {'state':'FIXTURE_ONLY'}
        backend=Backend(); service=profiles.Scoped(backend,'task')
        definitions=builder.encoded(builder.catalog('task',['document_submit']))
        self.assertEqual(service.tools(),[])
        with self.assertRaises(c.IntegrationError):
            service.call('document_submit',{'action_id':'not-approved'})
        self.assertEqual(backend.calls,[])
        backend.allowed=['document_submit']
        self.assertEqual(definitions,builder.encoded(builder.catalog('task',['document_submit'])))
        # A fake backend demonstrates forwarding, not native approval or execution.
        self.assertEqual(service.call('document_submit',{}),{'state':'FIXTURE_ONLY'})
        backend.allowed=[]
        with self.assertRaises(c.IntegrationError): service.call('document_submit',{})
        self.assertEqual(len(backend.calls),1)

    def test_each_profile_explicit_supported_schema_has_valid_catalog(self):
        for profile in profiles.NAMES:
            for name in profiles.definition(profile)['tools']:
                with self.subTest(profile=profile,name=name):
                    value=builder.catalog(profile,[name])
                    self.assertEqual(contract.validate_catalog(builder.encoded(value)),value)


class BackendABI(unittest.TestCase):
    class Instance:
        def create_initialization_options(self, **kwargs):
            return kwargs

    def environment(self, profile='task', names=None):
        return {'GOLEM_STABLE_FRONTEND_ABI':'golem.fixed-tool-catalog.v1',
                'GOLEM_STABLE_FRONTEND_PROFILE':profile,
                'GOLEM_STABLE_FRONTEND_TOOLS':json.dumps(names or ['document_submit','projects_list'])}

    def test_default_backend_options_unchanged(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(wire.initialization_options(self.Instance(),object(),reads.SCHEMAS),{})

    def test_exact_source_schema_evidence_independent_of_owner_actions(self):
        class Service:
            profile=profiles.definition('task')
            def tools(self):raise AssertionError('Do not infer interface from allowed action list')
            def call(self,*args):raise AssertionError('No Work operation during ABI proof')
        with patch.dict(os.environ,self.environment(),clear=True):
            value=wire.initialization_options(self.Instance(),Service(),{**reads.SCHEMAS,**actions.SCHEMAS})
        expected=builder.digest(builder.encoded(builder.catalog('task',['document_submit','projects_list'])))
        self.assertEqual(value,{'experimental_capabilities':{'golem.fixed-tool-catalog.v1':{'catalog_sha256':expected}}})

    def test_partial_or_generic_abi_arguments_block(self):
        for environment in ({'GOLEM_STABLE_FRONTEND_ABI':'golem.fixed-tool-catalog.v1'},
                            self.environment(names=['dispatch_anything']),
                            self.environment(names=['projects_list','projects_list']),
                            dict(self.environment(),GOLEM_STABLE_FRONTEND_ABI='unknown')):
            with self.subTest(environment=environment),patch.dict(os.environ,environment,clear=True),self.assertRaises(c.IntegrationError):
                wire.initialization_options(self.Instance(),object(),reads.SCHEMAS)

    def test_read_backend_and_profile_cannot_claim_mutation_abi(self):
        class Service:profile=profiles.definition('read')
        with patch.dict(os.environ,self.environment(),clear=True):
            with self.assertRaises(c.IntegrationError):
                wire.initialization_options(self.Instance(),object(),reads.SCHEMAS)
            with self.assertRaises(c.IntegrationError):
                wire.initialization_options(self.Instance(),Service(),{**reads.SCHEMAS,**actions.SCHEMAS})

    def test_supplied_backend_schema_mismatch_is_not_current_abi(self):
        wrong=copy.deepcopy(reads.SCHEMAS)
        wrong['projects_list']={'type':'object','properties':{'different':{'type':'string'}}}
        with patch.dict(os.environ,self.environment('read',['projects_list']),clear=True),self.assertRaises(c.IntegrationError):
            wire.initialization_options(self.Instance(),object(),wrong)


class Entry(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='stable-builder-',dir='/private/tmp' if Path('/private/tmp').exists() else None)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.bundle=self.root/'broker'
        self.result=builder.build_broker(self.bundle)
        self.state=self.root/'approved-state';self.state.mkdir(mode=0o700)
        launcher=self.root/'launcher.json'
        builder.write_new(launcher,builder.encoded({'command':sys.executable,'args':['-I','-B','-c','raise SystemExit(79)']}))
        adapter.configure(self.state,launcher,builder.digest(launcher.read_bytes()),True,'codex')
        original=adapter.inspect_state(self.state,'codex')
        self.catalog=self.root/'catalog.json'
        builder.write_new(self.catalog,builder.encoded(builder.catalog('task',['projects_list','document_submit'])))
        self.selection=self.root/'selection.json'
        builder.write_new(self.selection,builder.encoded({
            'schema':'golem.stable-selection.v1','client':'codex','revision':1,'previous_sha256':None,
            'catalog_sha256':builder.digest(self.catalog.read_bytes()),'adapter_state':str(self.state),
            'approval_sha256':original['approval_sha256'],'launcher_sha256':original['launcher_sha256']}))
        self.store=self.root/'stable-state'

    def run_entry(self,operation,*args,client='codex',pin=None):
        result=subprocess.run([sys.executable,'-I','-B',str(self.bundle/'stable_entry.py'),operation,
            '--client',client,'--store',str(self.store),'--reviewed-bundle-sha256',
            pin or self.result['manifest_sha256'],*args],capture_output=True,text=True,timeout=8)
        return result,json.loads(result.stdout or result.stderr)

    def create_args(self):
        return ['--catalog',str(self.catalog),'--catalog-sha256',builder.digest(self.catalog.read_bytes()),
                '--selection',str(self.selection),'--selection-sha256',builder.digest(self.selection.read_bytes()),
                '--approve-selection']

    def test_bundle_exact_closed_inventory_not_installed(self):
        self.assertEqual(set(self.result['files']),set(builder.PROGRAMS)|{'LICENSE','typed-interface.json'})
        self.assertFalse(self.result['installed'])
        self.assertFalse(self.result['execution_authorized'])
        with self.assertRaises(FileExistsError): builder.build_broker(self.bundle)

    def test_create_inspect_never_starts_approved_launcher(self):
        before={p.relative_to(self.state):p.read_bytes() for p in self.state.rglob('*') if p.is_file()}
        result,value=self.run_entry('create',*self.create_args())
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(value['selection']['revision'],1)
        self.assertFalse(value['execution_authorized'])
        result,inspected=self.run_entry('inspect')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(inspected['selection_sha256'],value['selection_sha256'])
        self.assertEqual(before,{p.relative_to(self.state):p.read_bytes() for p in self.state.rglob('*') if p.is_file()})

    def test_wrong_client_rejected_before_store_creation(self):
        result,value=self.run_entry('create',*self.create_args(),client='claude-desktop')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(value['code'],'STABLE_CLIENT')
        self.assertFalse(self.store.exists())

    def test_bundle_drift_rejected_before_selection_or_import(self):
        (self.bundle/'stable_contract.py').write_text('raise RuntimeError("must not import modified module")\n')
        result,value=self.run_entry('create',*self.create_args())
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(value['code'],'STABLE_BUNDLE_PAYLOAD_CHANGED')
        self.assertFalse(self.store.exists())

    def test_exact_bundle_pin_required(self):
        result,value=self.run_entry('create',*self.create_args(),pin='f'*64)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(value['code'],'STABLE_BUNDLE_PIN_CHANGED')
        self.assertFalse(self.store.exists())

    def test_no_selection_approval_has_no_publication(self):
        args=self.create_args();args.remove('--approve-selection')
        result,value=self.run_entry('create',*args)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(value['code'],'OWNER_SELECTION_APPROVAL_REQUIRED')
        self.assertFalse(self.store.exists())

    def test_bundle_symlink_rejected(self):
        source=self.bundle/'LICENSE';raw=source.read_bytes();source.unlink()
        other=self.root/'other';other.write_bytes(raw);source.symlink_to(other)
        result,value=self.run_entry('inspect')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(value['code'],'STABLE_BUNDLE_PATH')

    def test_readiness_requires_pinned_external_evidence_before_status(self):
        result,_=self.run_entry('create',*self.create_args())
        self.assertEqual(result.returncode,0)
        result,value=self.run_entry('readiness','--connection-instance','1'*32,
                                    '--require-tool','golem_projects_list')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(value['code'],'STABLE_OBSERVATION_PIN_REQUIRED')

    def test_unknown_handwritten_typed_definition_rejected_at_store(self):
        candidate=json.loads(self.catalog.read_bytes())
        candidate['tools'][0]['inputSchema']['properties']['arbitrary_command']={'type':'string'}
        candidate['tools_sha256']=builder.digest(builder.encoded(candidate['tools']))
        self.catalog.write_bytes(builder.encoded(candidate))
        selection=json.loads(self.selection.read_bytes())
        selection['catalog_sha256']=builder.digest(self.catalog.read_bytes())
        self.selection.write_bytes(builder.encoded(selection))
        result,value=self.run_entry('create',*self.create_args())
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(value['code'],'TYPED_TOOL_UNSUPPORTED_OR_CHANGED')
        self.assertFalse(self.store.exists())


if __name__ == '__main__':
    unittest.main()
