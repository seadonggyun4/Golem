"""Private disposable exact selection fixtures; no installed settings or Work."""
import copy
import errno
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]/'plugins/golem/scripts'


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS/file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


adapter = module('stable_fixture_adapter', 'launcher.py')
contract = module('stable_fixture_contract', 'stable_contract.py')


class StableContract(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir='/private/tmp' if Path('/private/tmp').exists() else None)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.store = self.root/'stable'
        self.catalog = {'schema':'golem.fixed-tool-catalog.v1', 'profile':'prepare', 'tools':[
            {'name':'golem_action_prepare', 'description':'Typed draft; no approval or execution.',
             'inputSchema':{'type':'object','properties':{'request_id':{'type':'string'}},
                            'required':['request_id'],'additionalProperties':False},
             'annotations':{'readOnlyHint':False,'destructiveHint':False,
                            'idempotentHint':False,'openWorldHint':False}}]}
        self.catalog['tools_sha256'] = contract.digest(contract.encode(self.catalog['tools']))
        self.fixture_index(self.catalog)
        self.addCleanup(setattr,contract,'_VERIFIED_TYPED_INDEX',None)
        self.catalog_path = self.write('catalog-input.json', self.catalog)
        self.catalog_sha = contract.digest(self.catalog_path.read_bytes())
        self.state = self.new_state('codex-old')
        self.initial = self.selection(self.state)
        self.initial_path = self.write('selection-initial.json', self.initial)
        self.initial_sha = contract.digest(self.initial_path.read_bytes())

    def fixture_index(self, catalog):
        # This test-only inventory is deliberately synthetic. Production entry
        # injects its separately pinned inventory of actual supported schemas.
        names=sorted(tool['name'] for tool in catalog['tools'])
        contract._VERIFIED_TYPED_INDEX={'schema':'golem.typed-interface-inventory.v1',
            'profiles':{name:names[:] for name in contract.PROFILES},
            'tools':{tool['name']:copy.deepcopy(tool) for tool in catalog['tools']}}

    def write(self, name, value):
        path = self.root/name
        path.write_bytes(value if isinstance(value, bytes) else contract.encode(value))
        path.chmod(0o600)
        return path

    def new_state(self, name, client='codex'):
        state = self.root/name
        path = self.write(name+'-launcher.json', {'command':sys.executable,'args':['-I','-B','-c',
                              'raise SystemExit("MUST_NOT_EXECUTE")',name]})
        adapter.configure(state, path, contract.digest(path.read_bytes()), True, client)
        return state

    def selection(self, state, revision=1, previous=None, client='codex'):
        approved = adapter.inspect_state(state,client)
        return {'schema':'golem.stable-selection.v1','client':client,'revision':revision,
            'previous_sha256':previous,'catalog_sha256':self.catalog_sha,'adapter_state':str(state),
            'approval_sha256':approved['approval_sha256'],'launcher_sha256':approved['launcher_sha256']}

    def create(self):
        return contract.create(self.store,self.catalog_path,self.catalog_sha,
                               self.initial_path,self.initial_sha,True,adapter)

    def next(self, first, name='next'):
        value = self.selection(self.new_state(name),2,first['selection_sha256'])
        path = self.write(name+'.json',value)
        return path,contract.digest(path.read_bytes())

    def publish(self, first, path, pin):
        return contract.publish(self.store,path,pin,first['head_sha256'],True,adapter)

    def snapshot(self, root=None):
        return {str(p.relative_to(root or self.root)):p.read_bytes()
                for p in (root or self.root).rglob('*') if p.is_file()}

    def test_exact_create_inspect_and_append_preserve_old_authority(self):
        old_authority = self.snapshot(self.state)
        first = self.create()
        self.assertFalse(first['execution_authorized'])
        self.assertEqual(first['publication_state'],'SELECTED_NOT_LIVE_APPLIED')
        self.assertEqual(contract.inspect(self.store,'codex',adapter),first)
        record = (self.store/'records'/'00000000000000000001.json').read_bytes()
        path,pin = self.next(first)
        second = self.publish(first,path,pin)
        self.assertEqual(second['selection']['revision'],2)
        self.assertEqual(second,contract.inspect(self.store,'codex',adapter))
        self.assertEqual((self.store/'records'/'00000000000000000001.json').read_bytes(),record)
        self.assertEqual(self.snapshot(self.state),old_authority)
        historical = contract.inspect_record(self.store,'codex',1,first['selection_sha256'],adapter)
        self.assertFalse(historical['is_current'])
        self.assertEqual(historical['current_head_selection_sha256'],second['selection_sha256'])
        self.assertNotIn('launcher',historical)

    def test_client_isolation_and_invalid_inspection_never_write(self):
        first=self.create()
        before=self.snapshot()
        for fn in (lambda:contract.inspect(self.store,'claude-desktop',adapter),
                   lambda:contract.inspect_record(self.store,'codex',1,'f'*64,adapter),
                   lambda:contract.inspect_record(self.store,'codex',2,'f'*64,adapter)):
            with self.assertRaises(contract.ContractError):fn()
        self.assertEqual(self.snapshot(),before)
        claude=self.new_state('claude','claude-desktop')
        proposal=self.write('wrong-client.json',self.selection(claude,2,first['selection_sha256'],'claude-desktop'))
        with self.assertRaisesRegex(contract.ContractError,'HEAD_FIELDS'):
            self.publish(first,proposal,contract.digest(proposal.read_bytes()))
        self.assertEqual(contract.inspect(self.store,'codex',adapter),first)

    def test_reviewed_bytes_approval_and_initial_revision_reject_before_creation(self):
        for change in ('bytes','approval','revision','owner'):
            with self.subTest(change=change):
                value=copy.deepcopy(self.initial)
                if change=='approval':value['approval_sha256']='f'*64
                if change=='revision':value.update(revision=2,previous_sha256='f'*64)
                path=self.write('invalid-'+change+'.json',value)
                pin='f'*64 if change=='bytes' else contract.digest(path.read_bytes())
                with self.assertRaises(ValueError):
                    contract.create(self.store,self.catalog_path,self.catalog_sha,path,pin,change!='owner',adapter)
                self.assertFalse(self.store.exists())

    def test_duplicate_noncanonical_nonfinite_and_catalog_extra_fields_rejected(self):
        invalid=[b'{"x":1,"x":2}\n',b'{"x":NaN}\n',b'{ "x": 1 }\n',b'{}']
        for raw in invalid:
            with self.subTest(raw=raw),self.assertRaises(contract.ContractError):contract.decode(raw)
        for mutate in (lambda c:c.update(extra=True),lambda c:c.update(profile='unsupported'),
                       lambda c:c['tools'][0].update(outputSchema={}),
                       lambda c:c['tools'][0].update(name='execute_anything'),
                       lambda c:c['tools'][0]['annotations'].update(readOnlyHint=1),
                       lambda c:c['tools'][0].update(inputSchema={'type':'string'})):
            value=copy.deepcopy(self.catalog);mutate(value)
            value['tools_sha256']=contract.digest(contract.encode(value['tools']))
            with self.assertRaises(contract.ContractError):contract.validate_catalog(contract.encode(value))

    def test_catalog_tool_sort_uniqueness_bounds_and_digest(self):
        for tools in ([self.catalog['tools'][0]]*2,
                      [dict(self.catalog['tools'][0],name='golem_z'),dict(self.catalog['tools'][0],name='golem_a')],
                      [],[dict(self.catalog['tools'][0],name=f'golem_t{i:03d}') for i in range(129)]):
            value=dict(self.catalog,tools=tools,tools_sha256=contract.digest(contract.encode(tools)))
            with self.assertRaises(contract.ContractError):contract.validate_catalog(contract.encode(value))
        with self.assertRaisesRegex(contract.ContractError,'CATALOG_TOOLS_DIGEST'):
            contract.validate_catalog(contract.encode(dict(self.catalog,tools_sha256='f'*64)))
        with self.assertRaisesRegex(contract.ContractError,'CATALOG_SIZE'):
            contract.validate_catalog(b' '*(contract.CATALOG_LIMIT+1))

    def test_finite_existing_object_union_preserved_without_schema_rewrite(self):
        value=copy.deepcopy(self.catalog)
        union={'type':'object','oneOf':[copy.deepcopy(value['tools'][0]['inputSchema']),
            {'type':'object','properties':{'kind':{'const':'other'}},'required':['kind'],'additionalProperties':False}]}
        value['tools'][0]['inputSchema']=union
        value['tools_sha256']=contract.digest(contract.encode(value['tools']))
        self.fixture_index(value)
        self.assertEqual(contract.validate_catalog(contract.encode(value))['tools'][0]['inputSchema'],union)
        for bad in ({'type':'object','oneOf':[]},{'type':'object','oneOf':[False]},
                    {'type':'object','oneOf':[{'type':'string','properties':{}}]},
                    {'type':'object','oneOf':[{'type':'object','properties':{}}]*129},
                    {'type':'object','oneOf':[union]}, {'type':'object','oneOf':union['oneOf'],'unexpected':True}):
            value['tools'][0]['inputSchema']=bad
            value['tools_sha256']=contract.digest(contract.encode(value['tools']))
            with self.subTest(schema=bad),self.assertRaisesRegex(contract.ContractError,'TOOL_INPUT_SCHEMA'):
                contract.validate_catalog(contract.encode(value))

    def test_handwritten_tool_or_profile_does_not_bypass_verified_typed_inventory(self):
        raw=contract.encode(self.catalog)
        index=copy.deepcopy(contract._VERIFIED_TYPED_INDEX)
        contract._VERIFIED_TYPED_INDEX=None
        with self.assertRaisesRegex(contract.ContractError,'TYPED_INTERFACE_REQUIRED'):
            contract.validate_catalog(raw)
        contract._VERIFIED_TYPED_INDEX=index
        changed=copy.deepcopy(self.catalog);changed['tools'][0]['name']='golem_dispatch_anything'
        changed['tools_sha256']=contract.digest(contract.encode(changed['tools']))
        with self.assertRaisesRegex(contract.ContractError,'TYPED_TOOL_OUTSIDE_PROFILE'):
            contract.validate_catalog(contract.encode(changed))
        changed=copy.deepcopy(self.catalog);changed['tools'][0]['inputSchema']['properties']['arbitrary_command']={'type':'string'}
        changed['tools_sha256']=contract.digest(contract.encode(changed['tools']))
        with self.assertRaisesRegex(contract.ContractError,'TYPED_TOOL_UNSUPPORTED_OR_CHANGED'):
            contract.validate_catalog(contract.encode(changed))
        contract._VERIFIED_TYPED_INDEX['profiles']['read']=['golem_other']
        with self.assertRaisesRegex(contract.ContractError,'TYPED_INTERFACE_PROFILE'):
            contract.validate_catalog(raw)

    def test_symlink_and_unsafe_private_bytes_block(self):
        link=self.root/'link';link.symlink_to(self.state,target_is_directory=True)
        value=dict(self.initial,adapter_state=str(link))
        with self.assertRaisesRegex(ValueError,'SYMLINK'):
            contract.validate_selection(contract.encode(value),adapter)
        catalog_link=self.root/'catalog-link';catalog_link.symlink_to(self.catalog_path)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):
            contract.create(self.store,catalog_link,self.catalog_sha,self.initial_path,self.initial_sha,True,adapter)
        self.catalog_path.chmod(0o644)
        with self.assertRaisesRegex(contract.ContractError,'UNSAFE_PRIVATE_FILE'):
            contract.read(self.catalog_path,contract.CATALOG_LIMIT,adapter)

    def test_head_cas_stale_publication_and_old_request_never_repeat(self):
        first=self.create();path,pin=self.next(first)
        second=self.publish(first,path,pin)
        before=self.snapshot()
        with self.assertRaisesRegex(contract.ContractError,'HEAD_CAS_MISMATCH'):
            self.publish(first,path,pin)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(contract.inspect(self.store,'codex',adapter),second)

    def test_concurrent_writers_one_commit_other_busy_or_stale(self):
        first=self.create();one=self.next(first,'one');two=self.next(first,'two')
        barrier=threading.Barrier(2);results=[]
        def writer(pair):
            barrier.wait()
            try:results.append(('ok',self.publish(first,*pair)))
            except contract.ContractError as error:results.append(('blocked',str(error)))
        workers=[threading.Thread(target=writer,args=(pair,)) for pair in (one,two)]
        for worker in workers:worker.start()
        for worker in workers:worker.join(timeout=5);self.assertFalse(worker.is_alive())
        self.assertEqual([r[0] for r in results].count('ok'),1)
        self.assertEqual([r[0] for r in results].count('blocked'),1)
        self.assertIn(next(r[1] for r in results if r[0]=='blocked'),('STORE_BUSY','HEAD_CAS_MISMATCH'))
        self.assertEqual(contract.inspect(self.store,'codex',adapter)['selection']['revision'],2)

    def test_shared_admission_serializes_publication_until_bounded_send_returns(self):
        first=self.create();path,pin=self.next(first);outcomes=[]
        with contract.shared_admission(self.store,'codex',first['selection_sha256'],first['head_sha256'],adapter) as current:
            self.assertEqual(current,first)
            def writer():
                try:self.publish(first,path,pin)
                except contract.ContractError as error:outcomes.append(str(error))
            concurrent=threading.Thread(target=writer);concurrent.start();concurrent.join(timeout=3)
            self.assertFalse(concurrent.is_alive())
            self.assertEqual(outcomes,['STORE_BUSY'])
            self.assertFalse((self.store/'pending.json').exists())
        # A separately authorized later attempt can publish; the context never
        # retries the blocked writer or the caller's hypothetical Work send.
        second=self.publish(first,path,pin)
        with self.assertRaisesRegex(contract.ContractError,'ADMISSION_SELECTION_CHANGED'):
            with contract.shared_admission(self.store,'codex',first['selection_sha256'],first['head_sha256'],adapter):
                self.fail('old selection must never yield to dispatch')
        self.assertEqual(contract.inspect(self.store,'codex',adapter),second)

    def test_shared_admission_releases_lock_on_failed_send_without_retry(self):
        first=self.create();path,pin=self.next(first);sends=[]
        with self.assertRaisesRegex(OSError,'lost transport'):
            with contract.shared_admission(self.store,'codex',first['selection_sha256'],first['head_sha256'],adapter):
                sends.append('one');raise OSError('lost transport')
        self.assertEqual(sends,['one'])
        self.assertEqual(self.publish(first,path,pin)['selection']['revision'],2)

    def test_pending_crash_is_preserved_without_repair_or_create_retry(self):
        real=contract._write
        def crash(path,raw):
            if path.name=='catalog.json':raise OSError(errno.ENOSPC,'fixture full')
            real(path,raw)
        with patch.object(contract,'_write',side_effect=crash),self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):self.create()
        before=self.snapshot()
        self.assertTrue((self.store/'pending.json').exists())
        with self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):
            contract.inspect(self.store,'codex',adapter)
        with self.assertRaisesRegex(contract.ContractError,'STORE_EXISTS_NO_RETRY'):self.create()
        self.assertEqual(self.snapshot(),before)

    def test_ENOSPC_after_pending_preserves_old_head_and_partial_record(self):
        first=self.create();path,pin=self.next(first)
        head=(self.store/'head.json').read_bytes();real=contract._write
        def full(target,raw):
            if target.parent.name=='records' and target.name.startswith('00000000000000000002'):
                real(target,raw[:7]);raise OSError(errno.ENOSPC,'fixture full')
            real(target,raw)
        with patch.object(contract,'_write',side_effect=full),self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):self.publish(first,path,pin)
        self.assertEqual((self.store/'head.json').read_bytes(),head)
        self.assertTrue((self.store/'pending.json').exists())
        with self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):
            contract.inspect(self.store,'codex',adapter)
        self.assertEqual((self.store/'records'/'00000000000000000002.json').read_bytes(),path.read_bytes()[:7])

    def test_final_fsync_failure_restores_pending_and_never_claims_success(self):
        first=self.create();path,pin=self.next(first);real=adapter.sync_directory;failed=[]
        def fail_final(directory):
            if directory==self.store and not (self.store/'pending.json').exists() and not failed:
                failed.append(True);raise OSError(errno.EIO,'fixture final sync failure')
            real(directory)
        with patch.object(adapter,'sync_directory',side_effect=fail_final),self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):
            self.publish(first,path,pin)
        self.assertTrue((self.store/'pending.json').exists())
        with self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):
            contract.inspect(self.store,'codex',adapter)

    def test_head_rollback_or_immutable_record_modification_is_blocked(self):
        first=self.create();head=(self.store/'head.json').read_bytes();path,pin=self.next(first)
        self.publish(first,path,pin)
        (self.store/'head.json').write_bytes(head)
        with self.assertRaisesRegex(contract.ContractError,'RECORD_CHAIN_OR_HEAD_ROLLBACK'):
            contract.inspect(self.store,'codex',adapter)

    def test_catalog_and_old_record_modification_are_detected(self):
        first=self.create();path,pin=self.next(first);self.publish(first,path,pin)
        old=self.store/'records'/'00000000000000000001.json'
        value=contract.decode(old.read_bytes());value['launcher_sha256']='f'*64
        old.write_bytes(contract.encode(value))
        with self.assertRaisesRegex(contract.ContractError,'SELECTION_CHAIN'):
            contract.inspect(self.store,'codex',adapter)

    def test_selected_approval_drift_blocks_inspection_and_publication(self):
        first=self.create();path,pin=self.next(first)
        approval=self.state/'golem-launcher'/'approval.json'
        approval.write_bytes(approval.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'INSPECT_APPROVAL_CHANGED'):
            contract.inspect(self.store,'codex',adapter)
        with self.assertRaisesRegex(ValueError,'INSPECT_APPROVAL_CHANGED'):self.publish(first,path,pin)
        self.assertFalse((self.store/'pending.json').exists())

    def test_changed_catalog_and_revision_gaps_block_before_pending(self):
        first=self.create();path,pin=self.next(first)
        for changes in ({'catalog_sha256':'f'*64},{'revision':3},{'previous_sha256':'f'*64}):
            value=contract.decode(path.read_bytes());value.update(changes)
            trial=self.write('invalid-next.json',value)
            with self.assertRaisesRegex(contract.ContractError,'NEXT_SELECTION'):
                self.publish(first,trial,contract.digest(trial.read_bytes()))
            self.assertFalse((self.store/'pending.json').exists())

    def test_concurrent_unlocked_head_change_is_detected_before_replace(self):
        first=self.create();path,pin=self.next(first);real=contract._write
        changed=contract.encode({'untrusted':'external-change'})
        def tamper(target,raw):
            real(target,raw)
            if target.name=='head.pending':(self.store/'head.json').write_bytes(changed)
        with patch.object(contract,'_write',side_effect=tamper),self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):
            self.publish(first,path,pin)
        self.assertEqual((self.store/'head.json').read_bytes(),changed)
        self.assertTrue((self.store/'pending.json').exists())

    def test_target_approval_drift_during_publication_preserves_unknown(self):
        first=self.create();path,pin=self.next(first);real=contract._write
        target_approval=Path(contract.decode(path.read_bytes())['adapter_state'])/'golem-launcher'/'approval.json'
        def tamper(target,raw):
            real(target,raw)
            if target.name=='head.pending':target_approval.write_bytes(target_approval.read_bytes()+b' ')
        with patch.object(contract,'_write',side_effect=tamper),self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):
            self.publish(first,path,pin)
        self.assertTrue((self.store/'pending.json').exists())
        self.assertEqual(contract.decode((self.store/'head.json').read_bytes())['revision'],1)

    def test_missing_head_unexpected_files_and_pending_symlink_never_repair(self):
        self.create()
        extra=self.store/'unexpected';extra.write_bytes(b'preserve')
        with self.assertRaisesRegex(contract.ContractError,'STORE_INCOMPLETE_OR_UNEXPECTED'):
            contract.inspect(self.store,'codex',adapter)
        extra.unlink()  # Disposable fixture mutation, never product repair.
        pending=self.store/'pending.json';pending.symlink_to(self.root/'missing')
        with self.assertRaisesRegex(contract.ContractError,'PUBLICATION_UNKNOWN'):
            contract.inspect(self.store,'codex',adapter)
        self.assertTrue(pending.is_symlink())

    def test_catalog_bytes_modified_or_symlinked_after_creation_block(self):
        self.create();path=self.store/'catalog.json'
        value=copy.deepcopy(self.catalog);value['profile']='read'
        path.write_bytes(contract.encode(value))
        with self.assertRaisesRegex(contract.ContractError,'HEAD_FIELDS'):
            contract.inspect(self.store,'codex',adapter)
        path.unlink();path.symlink_to(self.catalog_path)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):
            contract.inspect(self.store,'codex',adapter)

    def test_selection_scalar_types_bounds_and_path_normalization(self):
        for fields in ({'revision':True},{'revision':257},{'revision':0},{'client':[]},
                       {'adapter_state':str(self.root)+'/../state'},{'approval_sha256':'F'*64}):
            value=dict(self.initial,**fields)
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                contract.validate_selection(contract.encode(value),adapter)

    def test_file_read_identity_change_is_detected(self):
        real=os.read
        def mutate(fd,size):
            raw=real(fd,size)
            self.catalog_path.write_bytes(raw+b' ')
            return raw
        with patch.object(contract.os,'read',side_effect=mutate),self.assertRaisesRegex(contract.ContractError,'FILE_CHANGED'):
            contract.read(self.catalog_path,contract.CATALOG_LIMIT,adapter)


if __name__ == '__main__':
    unittest.main()
