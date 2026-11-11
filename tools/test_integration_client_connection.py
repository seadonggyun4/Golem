"""Private disposable connection fixtures; no real client/registry/Work dispatch."""
import copy
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import integration_client_connection as connection


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='golem-connection-', dir='/private/tmp' if Path('/private/tmp').is_dir() else None)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.package = self.root/'plugin'
        self.runtime = self.root/'runtime'
        self.state = self.root/'adapter-state'
        self.config = self.root/'config.toml'
        self.policy = self.root/'policy.json'
        self.review = self.root/'review'
        for path in (self.package/'scripts', self.package/'.codex-plugin', self.runtime,
                     self.state/'golem-launcher', self.review):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.adapter = self.package/'scripts/launcher.py'
        self.write(self.adapter, b'# fixture adapter; never execute\n')
        self.write(self.runtime/'integration_owner_desktop.py', b'# fixture runtime\n')
        self.write(self.package/'.codex-plugin/plugin.json', {'name':'golem','version':'0.2.9'})
        self.write(self.policy, {'schema':'fixture','actions':[]})
        self.owner_args = ['--profile','task','--policy',str(self.policy),
                           '--reviewed-policy-sha256',connection.digest(self.policy.read_bytes()),
                           '--approve-owner','--approve-owner-review-ui']
        code = ('import sys;sys.path[:0]='+repr([str(self.runtime)])+
                ';import integration_owner_desktop as m;sys.exit(m.main('+repr(self.owner_args)+'))')
        self.launcher = {'command':'/fixture/python3','args':['-I','-B','-c',code]}
        self.save_approval()
        self.args = ['-I','-B',str(self.adapter),'serve','--client','codex','--state',str(self.state)]
        self.save_config()

    def write(self, path, value):
        raw = value if isinstance(value, bytes) else (json.dumps(value)+'\n').encode()
        path.write_bytes(raw)
        path.chmod(0o600)

    def save_config(self, command='/usr/bin/python3'):
        self.write(self.config, ('unrelated_secret = "fixture-only-hidden"\n[mcp_servers.golem-local]\ncommand = '+json.dumps(command)+
                                 '\nargs = '+json.dumps(self.args)+'\n').encode())

    def save_approval(self):
        raw = json.dumps(self.launcher)+'\n'
        self.write(self.state/'golem-launcher/approval.json',
                   {'schema':'golem.codex-launcher.v1','launcher':raw,
                    'launcher_sha256':connection.digest(raw.encode())})

    def selected(self):
        return connection.selected_connection(self.config)

    def row(self, selected=None, **updates):
        selected = selected or self.selected()
        result = {key:selected[key] for key in ('launcher_sha256','policy_sha256','runtime_sha256',
                                                'adapter_state','package_version')}
        result.update(instance='fixture-live',host_kind='ChatGPT',host_pid=30,pid=31,
                      tools=['golem_projects_list'],tools_count=1)
        result.update(updates)
        return result

    def expect(self, code, action):
        with self.assertRaises(connection.ConnectionError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)


class Selection(Fixture):
    def test_exact_selected_policy_runtime_package_without_other_config_disclosure(self):
        value = self.selected()
        self.assertEqual(value['adapter_state'], str(self.state))
        self.assertEqual(value['package_version'], '0.2.9')
        self.assertEqual(value['policy_sha256'], connection.digest(self.policy.read_bytes()))
        self.assertEqual(value['runtime_sha256'], connection.digest((self.runtime/'integration_owner_desktop.py').read_bytes()))
        self.assertNotIn('fixture-only-hidden', json.dumps(value))

    def test_direct_script_launcher_is_supported_without_running_it(self):
        launcher = {'command':'/fixture/python3','args':['-I','-B',
                    str(self.runtime/'integration_owner_desktop.py'),*self.owner_args]}
        with patch('subprocess.run', side_effect=AssertionError('not an execution path')):
            result = connection.owner_launch_description(launcher)
        self.assertEqual(result['policy_sha256'], connection.digest(self.policy.read_bytes()))

    def test_literal_parser_never_executes_side_effects(self):
        marker = self.root/'must-not-exist'
        self.launcher['args'][-1] = ('open('+repr(str(marker))+',"w").write("BAD");'+self.launcher['args'][-1])
        self.save_approval()
        result = self.selected()
        self.assertFalse(marker.exists())
        self.assertIsNone(result['policy_sha256'])
        self.assertEqual(result['identity_detail'], 'OPAQUE_OR_CHANGED_LAUNCHER_NOT_EXECUTED')

    def test_non_python_command_cannot_appear_as_selected_owner_launcher(self):
        self.save_config(command='/bin/sh')
        with self.assertRaises(connection.ConnectionError):
            self.selected()

    def test_branch_or_rebound_alias_cannot_supply_declared_current_identity(self):
        original = self.launcher['args'][-1]
        variants = (original.replace(';sys.exit(', ';m = object();sys.exit('),
                    original.replace(';sys.exit(', '\nif False: sys.exit('))
        for code in variants:
            with self.subTest(code=code):
                self.launcher['args'][-1] = code
                self.save_approval()
                value = self.selected()
                self.assertIsNone(value['policy_sha256'])
                self.assertEqual(value['identity_detail'], 'OPAQUE_OR_CHANGED_LAUNCHER_NOT_EXECUTED')

    def test_dynamic_owner_arguments_are_opaque_and_cannot_supply_current_identity(self):
        self.launcher['args'][-1] = 'import integration_owner_desktop as m;m.main(load_arguments())'
        self.save_approval()
        result = self.selected()
        self.assertIsNone(result['policy_sha256'])
        self.assertIsNone(result['runtime_sha256'])
        self.assertEqual(result['identity_detail'], 'OPAQUE_OR_CHANGED_LAUNCHER_NOT_EXECUTED')
        state, mode = connection.compare(result, [self.row(result)], {})
        self.assertNotEqual(mode, 'VERIFIED')

    def test_changed_policy_is_not_a_matching_selected_identity(self):
        self.write(self.policy, {'schema':'fixture','actions':['changed']})
        result = self.selected()
        self.assertIsNone(result['policy_sha256'])
        self.assertIn('OPAQUE_OR_CHANGED', result['identity_detail'])

    def test_approval_bytes_digest_and_client_schema_must_match(self):
        path = self.state/'golem-launcher/approval.json'
        value = json.loads(path.read_bytes())
        value['launcher'] += ' '
        self.write(path, value)
        self.expect('CONNECTION_APPROVAL_CHANGED', self.selected)
        self.save_approval()
        value = json.loads(path.read_bytes());value['schema'] = 'golem.claude-desktop-launcher.v1'
        self.write(path, value)
        self.expect('CONNECTION_APPROVAL_CHANGED', self.selected)

    def test_private_files_symlinks_hardlinks_and_duplicate_json_are_rejected(self):
        self.config.chmod(0o644)
        self.expect('CONNECTION_FILE', self.selected)
        self.config.chmod(0o600)
        link = self.root/'config-link.toml';link.symlink_to(self.config)
        self.expect('CONNECTION_PATH', lambda:connection.selected_connection(link))
        os.link(self.config,self.root/'config-hardlink.toml')
        self.expect('CONNECTION_FILE', self.selected)
        self.expect('CONNECTION_DUPLICATE_FIELD', lambda:connection.decode(b'{"x":1,"x":2}'))

    def test_config_replaced_during_observation_fails_closed(self):
        real_read = connection.read_file
        count = 0
        def changed(path, **kwargs):
            nonlocal count
            raw = real_read(path, **kwargs)
            if Path(path) == self.config:
                count += 1
                if count == 2:
                    return raw + b'\n# concurrent change\n'
            return raw
        with patch.object(connection, 'read_file', side_effect=changed):
            self.expect('CONNECTION_CONFIG_CHANGED', self.selected)

    def test_file_mutation_during_read_is_detected(self):
        real_read = connection.os.read
        def mutate(fd, size):
            raw = real_read(fd,size)
            self.config.write_bytes(self.config.read_bytes()+b'\n# changed\n')
            return raw
        with patch.object(connection.os,'read',side_effect=mutate):
            self.expect('CONNECTION_FILE_CHANGED', lambda:connection.read_file(self.config,private=True))


class Observation(Fixture):
    def test_standalone_probe_never_proves_Desktop_or_model_delivery(self):
        monitor = connection.ConnectionMonitor(self.config,self.review,
            observer=lambda:[self.row(host_kind='INDEPENDENT_STDIO')])
        observed = monitor.inspect()
        self.assertNotEqual(observed['reload']['mode'],'VERIFIED')
        self.assertEqual(observed['model_tool_delivery'],'NOT_OBSERVED')
        self.assertEqual(observed['Work_calls'],0)

    def test_all_actual_Desktop_rows_must_match_and_unknown_rows_prevent_completion(self):
        selected = self.selected()
        current = self.row(selected)
        self.assertEqual(connection.compare(selected,[current],{})[1],'VERIFIED')
        self.assertNotEqual(connection.compare(selected,[self.row(selected),self.row(selected,policy_sha256='e'*64)],{})[1],'VERIFIED')
        self.assertNotEqual(connection.compare(selected,[self.row(selected),{'state':'LEGACY_OR_UNAVAILABLE'}],{})[1],'VERIFIED')

    def test_current_fingerprints_without_valid_tools_do_not_verify_service(self):
        selected = self.selected()
        for tools in (None, [], ['golem_projects_list']*2, ['not_golem'], [1]):
            with self.subTest(tools=tools):
                self.assertNotEqual(connection.compare(selected,[self.row(selected,tools=tools)],{})[1],'VERIFIED')

    def test_manual_refresh_does_not_execute_reconnect_or_touch_files(self):
        before = {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        monitor = connection.ConnectionMonitor(self.config,self.review,observer=lambda:[])
        with patch('subprocess.run',side_effect=AssertionError('no host command')):
            result = monitor.request_refresh(expected_token=monitor.inspect()['refresh_token'])
        self.assertEqual(result['reload']['mode'],'MANUAL_RESTART_REQUIRED')
        self.assertFalse(monitor.attempted)
        self.assertEqual(before,{str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_exact_menu_from_observed_Desktop_and_no_guessed_host(self):
        monitor = connection.ConnectionMonitor(self.config,self.review,
            observer=lambda:[self.row(policy_sha256='f'*64)])
        self.assertIn('ChatGPT → ChatGPT 종료', '\n'.join(monitor.inspect()['reload']['steps']))
        monitor.observer = lambda:[]
        self.assertNotIn('ChatGPT → ChatGPT 종료', '\n'.join(monitor.inspect()['reload']['steps']))

    def test_same_uid_process_ancestry_distinguishes_Desktop_from_other_servers(self):
        entries = {10:{'pid':10,'ppid':20,'uid':os.getuid(),'exe':'/fixture/python'},
                   20:{'pid':20,'ppid':30,'uid':os.getuid(),
                       'exe':'/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'}}
        value = connection.desktop_parent(10,entries.__getitem__)
        self.assertEqual(value['host_kind'],'ChatGPT')
        self.assertEqual(value['host_pid'],20)
        entries[20]['uid'] += 1
        self.expect('PROCESS_OWNER',lambda:connection.desktop_parent(10,entries.__getitem__))
        entries[20].update(uid=os.getuid(),exe='/usr/local/bin/codex',ppid=10)
        self.expect('PROCESS_ANCESTRY',lambda:connection.desktop_parent(10,entries.__getitem__))


class OfficialControl(Fixture):
    def test_missing_or_changed_refresh_selection_never_dispatches(self):
        class Control:
            def __init__(self): self.identity={'host_pid':30,'inode':10}
            def inspect(self, **kwargs):
                return {'verified_desktop':True,'reload_supported':True,
                        'socket_identity':copy.deepcopy(self.identity)}
            def reload(self, **kwargs): raise AssertionError('stale target must not dispatch')
        control = Control()
        monitor = connection.ConnectionMonitor(self.config,self.review,control=control,observer=lambda:[])
        self.expect('REFRESH_SELECTION_CHANGED', monitor.request_refresh)
        token = monitor.inspect()['refresh_token']
        control.identity['inode'] += 1
        self.expect('REFRESH_SELECTION_CHANGED', lambda:monitor.request_refresh(expected_token=token))
        token = monitor.inspect()['refresh_token']
        self.write(self.config,self.config.read_bytes()+b'\n# owner changed configuration\n')
        self.expect('REFRESH_SELECTION_CHANGED', lambda:monitor.request_refresh(expected_token=token))
        self.assertFalse(monitor.attempted)

    def test_manual_report_cannot_become_unconfirmed_host_wide_refresh(self):
        class Control:
            def __init__(self): self.available=False
            def inspect(self, **kwargs):
                return {'verified_desktop':self.available,'reload_supported':self.available,
                        'socket_identity':{'host_pid':30,'inode':10} if self.available else None}
            def reload(self, **kwargs): raise AssertionError('changed scope must not dispatch')
        control = Control()
        monitor = connection.ConnectionMonitor(self.config,self.review,control=control,observer=lambda:[])
        observed = monitor.inspect()
        self.assertEqual(observed['reload']['mode'],'MANUAL_RESTART_REQUIRED')
        control.available=True
        self.expect('REFRESH_SELECTION_CHANGED',lambda:monitor.request_refresh(expected_token=observed['refresh_token']))
        self.assertFalse(monitor.attempted)

    def test_monitor_uses_actual_control_signature_and_ACK_requires_verification(self):
        import integration_codex_control as control
        identity = {'host_pid':40,'host_kind':'ChatGPT','inode':123}
        calls = []
        class Proxy:
            reload_dispatched = False
            def __init__(self,*args): pass
            def initialize(self): calls.append('initialize')
            def call(self,method,params=None):
                calls.append(method)
                self.reload_dispatched = True
                return {}
            def close(self): calls.append('close')
        live = control.CodexControl('/fixture/codex','/fixture/control.sock')
        monitor = connection.ConnectionMonitor(self.config,self.review,control=live,observer=lambda:[])
        with patch.object(live,'_identity',return_value=identity),patch.object(control,'_Proxy',Proxy):
            token = monitor.inspect()['refresh_token']
            result = monitor.request_refresh(expected_token=token)
            self.assertEqual(result['reload']['mode'],'REFRESH_QUEUED')
            self.assertEqual(result['model_tool_delivery'],'NOT_OBSERVED')
            self.expect('REFRESH_ALREADY_ATTEMPTED_NO_RETRY',
                        lambda:monitor.request_refresh(expected_token=token))
        self.assertEqual(calls.count('config/mcpServer/reload'),1)
        self.assertEqual(calls,['initialize','config/mcpServer/reload','close'])

    def test_unknown_reload_response_is_preserved_without_second_dispatch(self):
        import integration_codex_control as control
        identity = {'host_pid':40,'host_kind':'Codex','inode':123}
        calls = []
        class Proxy:
            reload_dispatched = False
            def __init__(self,*args): pass
            def initialize(self): pass
            def call(self,method,params=None):
                calls.append(method)
                self.reload_dispatched = True
                raise OSError('reply lost')
            def close(self): pass
        live = control.CodexControl('/fixture/codex','/fixture/control.sock')
        monitor = connection.ConnectionMonitor(self.config,self.review,control=live,observer=lambda:[])
        with patch.object(live,'_identity',return_value=identity),patch.object(control,'_Proxy',Proxy):
            token = monitor.inspect()['refresh_token']
            result = monitor.request_refresh(expected_token=token)
            self.assertEqual(result['reload']['mode'],'VERIFY_REQUIRED')
            self.assertEqual(result['refresh_result']['state'],'REFRESH_UNKNOWN')
            self.expect('REFRESH_ALREADY_ATTEMPTED_NO_RETRY',
                        lambda:monitor.request_refresh(expected_token=token))
        self.assertEqual(calls,['config/mcpServer/reload'])


class EndpointHistory(Fixture):
    """Retained metadata is not a live admission slot or a completion claim."""
    def setUp(self):
        super().setUp()
        import integration_owner_desktop as desktop
        self.desktop = desktop
        self.active = set()
        self.calls = []
        self.reply = self.row(schema='golem.owner-connection-status.v1')
        self.reply.pop('instance')
        self.errors = {}
        original = Path.lstat
        def info(path, *args, **kwargs):
            if path.parent == self.review and path.suffix == '.sock' and path.stem in self.active:
                problem = self.errors.get(path.stem)
                if isinstance(problem, Exception):
                    raise problem
                return SimpleNamespace(st_mode=stat.S_IFSOCK|0o600,
                    st_uid=os.getuid()+(1 if problem == 'wrong-uid' else 0), st_dev=1, st_ino=99)
            return original(path, *args, **kwargs)
        self.addCleanup(patch.stopall)
        patch.object(Path,'lstat',side_effect=info,autospec=True).start()
        def remote(directory, instance):
            self.calls.append(instance)
            def status():
                if self.errors.get(instance) == 'refused':
                    raise ConnectionRefusedError('fixture stale socket')
                return copy.deepcopy(self.reply)
            return SimpleNamespace(last_peer_pid=31,connection_status=status)
        patch.object(desktop,'RemoteController',side_effect=remote).start()
        self.monitor = connection.ConnectionMonitor(self.config,self.review,
            ancestry=lambda pid:{'host_kind':'ChatGPT','host_pid':30})
        self.monitor.relay = SimpleNamespace(descriptors=lambda:[])

    def record(self, number, *, active=False, timestamp=None):
        instance = f'{number:032x}'
        path = self.review/(instance+'.json')
        self.write(path, {'instance':instance,'token':'a'*64,'kind':'review','label':'fixture'})
        if timestamp is not None:
            os.utime(path,ns=(timestamp,timestamp))
        if active:
            self.active.add(instance)
        return instance

    def test_forty_missing_endpoints_do_not_hide_live_Desktop_or_delete_history(self):
        for number in range(40): self.record(number)
        current = self.record(100,active=True)
        before = {p.name:p.read_bytes() for p in self.review.glob('*.json')}
        report = self.monitor.inspect()
        self.assertEqual(self.calls,[current])
        self.assertEqual(report['reload']['mode'],'VERIFIED')
        self.assertEqual(report['connections'][0]['instance'],current)
        closed = [r for r in report['connections'] if r['state']==connection.ENDPOINT_ABSENT]
        self.assertEqual(len(closed),40)
        self.assertTrue(all('NOT_PROCESS_OR_WORK_COMPLETION' in r['reason'] for r in closed))
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.review.glob('*.json')})
        self.assertEqual(report['model_tool_delivery'],'NOT_OBSERVED')

    def test_forty_retained_socket_paths_prioritize_new_record_but_remain_partial(self):
        for number in range(40):
            old = self.record(number,active=True,timestamp=1)
            self.errors[old]='refused'
        current = self.record(100,active=True,timestamp=2)
        report = self.monitor.inspect()
        self.assertEqual(self.calls[0],current)
        self.assertEqual(len(self.calls),16)
        self.assertEqual(report['connections'][0]['state'],'CURRENT_ACTIVE_SERVICE')
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')
        self.assertTrue(any(r.get('reason')=='BOUNDED_OBSERVATION_LIMIT' for r in report['connections']))
        self.assertEqual(len(list(self.review.glob('*.json'))),41)
        self.assertFalse(any('정상 종료한 뒤' in s for s in report['reload']['steps']))

    def test_seventeen_live_candidates_keep_budget_and_block_global_current(self):
        for number in range(17): self.record(number,active=True,timestamp=1)
        report=self.monitor.inspect()
        self.assertEqual(self.calls,[f'{i:032x}' for i in range(16)])
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')
        self.assertEqual(report['Work_calls'],0)

    def test_invalid_descriptor_socket_symlink_uid_and_permission_are_not_closed(self):
        current=self.record(100,active=True)
        wrong=self.record(1,active=True);self.errors[wrong]='wrong-uid'
        denied=self.record(2,active=True);self.errors[denied]=PermissionError('fixture')
        linked=self.record(3)
        (self.review/(linked+'.sock')).symlink_to(self.policy)
        malformed=self.record(4);self.write(self.review/(malformed+'.json'),{'invalid':True})
        stale=self.record(5,active=True);self.errors[stale]='refused'
        report=self.monitor.inspect()
        self.assertIn(current,self.calls)
        self.assertFalse(any(r.get('state')==connection.ENDPOINT_ABSENT for r in report['connections']))
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')

    def test_absent_endpoint_that_reappears_is_unobserved_not_closed(self):
        absent=self.record(1)
        current=self.record(2,active=True)
        remote=self.desktop.RemoteController.side_effect
        def appear(directory, instance):
            value=remote(directory,instance)
            self.active.add(absent)
            return value
        self.desktop.RemoteController.side_effect=appear
        report=self.monitor.inspect()
        self.assertEqual(self.calls,[current])
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')
        self.assertFalse(any(r.get('state')==connection.ENDPOINT_ABSENT for r in report['connections']))

    def test_descriptor_change_and_peer_pid_mismatch_remain_unknown(self):
        target=self.record(1,active=True)
        self.reply['pid']=999
        report=self.monitor.inspect()
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')
        self.assertEqual(report['connections'][0]['reason'],'CONNECTION_PEER_PID')
        self.reply['pid']=31
        remote=self.desktop.RemoteController.side_effect
        def change(directory, instance):
            value=remote(directory,instance)
            path=self.review/(target+'.json')
            raw=json.loads(path.read_bytes());raw['label']='changed';self.write(path,raw)
            return value
        self.desktop.RemoteController.side_effect=change
        report=self.monitor.inspect()
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')
        self.assertEqual(report['connections'][0]['reason'],'CONNECTION_ENDPOINT_CHANGED')

    def test_owner_catalog_limit_is_not_silently_expanded(self):
        for number in range(129): self.record(number)
        report=self.monitor.inspect()
        self.assertEqual(self.calls,[])
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')
        self.assertEqual(report['connections'][0]['reason'],'OWNER_CONNECTION_LIMIT')

    def test_peer_metadata_cannot_forge_local_closed_or_verified_state(self):
        self.record(1,active=True)
        self.reply.update(state=connection.ENDPOINT_ABSENT,relay_current=True)
        report=self.monitor.inspect()
        self.assertEqual(report['connections'][0]['reason'],'CONNECTION_STATUS_FIELDS')
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')


class Relay(Fixture):
    def setUp(self):
        super().setUp()
        selected=self.selected()
        class FakeRelay:
            def __init__(self):
                self.rows={key*32:{'instance':key*32,'pid':50+i,'state':'READY','busy':False,
                    'plugin_version':selected['package_version'],'selected_state':'/fixture/old-state',
                    'launcher_sha256':'d'*64,'approval_sha256':'e'*64,
                    'kind':'codex-connection-relay'} for i,key in enumerate(('a','b'))}
                self.calls=[]
                self.failure=None
            def descriptors(self):
                return [self.endpoint(key) for key in self.rows]
            def endpoint(self, key):
                return {'instance':key,'pid':self.rows[key]['pid'],'kind':'codex-connection-relay',
                        'discovery_mtime_ns':self.rows[key].get('discovery_mtime_ns',0),
                        'endpoint_state':self.rows[key].get('endpoint_state','PRESENT')}
            def request(self,instance,operation,params):
                if operation=='status':
                    value={k:v for k,v in self.rows[instance].items() if k not in ('endpoint_state','discovery_mtime_ns')}
                    return {'ok':True,'value':copy.deepcopy(value)}
                self.calls.append((instance,operation,copy.deepcopy(params)))
                if self.failure: raise self.failure
                row=self.rows[instance]
                row.update(launcher_sha256=params['launcher_sha256'],
                           approval_sha256=params['approval_sha256'],selected_state=params['state'])
                return {'ok':True,'value':{'state':'READY','model_tool_delivery':'NOT_OBSERVED'}}
        self.relay=FakeRelay()
        self.monitor=connection.ConnectionMonitor(self.config,self.review,observer=lambda:[],
            relay=self.relay,ancestry=lambda pid:{'host_kind':'ChatGPT','host_pid':40})

    def refresh(self, token=None, target='a'*32):
        return self.monitor.request_refresh(expected_token=token,connection_instance=target)

    def test_current_exact_selection_is_observed_without_refresh_or_dispatch(self):
        selected=self.selected()
        for row in self.relay.rows.values():
            row.update(launcher_sha256=selected['launcher_sha256'],
                       approval_sha256=selected['approval_sha256'],selected_state=selected['adapter_state'])
        result=self.monitor.inspect()
        self.assertNotEqual(result['reload']['mode'],'GOLEM_RELAY_AVAILABLE')
        self.assertFalse(any(row.get('refreshable') for row in result['connections']))
        self.assertEqual(self.relay.calls,[])
        self.assertEqual(result['model_tool_delivery'],'NOT_OBSERVED')

    def test_standalone_or_mismatched_peer_cannot_be_refresh_target(self):
        self.monitor.ancestry=lambda pid:{'host_kind':'INDEPENDENT_STDIO','host_pid':None}
        observed=self.monitor.inspect()
        self.assertFalse(any(row.get('refreshable') for row in observed['connections']))
        self.monitor.ancestry=lambda pid:{'host_kind':'ChatGPT','host_pid':40}
        real=self.relay.request
        def wrong_peer(instance,operation,params):
            value=real(instance,operation,params)
            if operation=='status': value['value']['pid']+=100
            return value
        with patch.object(self.relay,'request',side_effect=wrong_peer):
            observed=self.monitor.inspect()
        self.assertFalse(any(row.get('refreshable') for row in observed['connections']))
        self.assertTrue(all(row['state']=='RELAY_UNAVAILABLE' for row in observed['connections']))
        self.assertEqual(self.relay.calls,[])

    def test_wrong_target_or_missing_token_never_dispatches(self):
        observed=self.monitor.inspect()
        self.expect('REFRESH_SELECTION_CHANGED',lambda:self.refresh())
        self.expect('REFRESH_CONNECTION_SELECTION_REQUIRED',
                    lambda:self.refresh(observed['refresh_token'],target='c'*32))
        self.assertEqual(self.relay.calls,[])

    def test_two_relays_dispatch_only_selected_target_with_exact_selected_pins(self):
        observed=self.monitor.inspect()
        self.assertEqual(observed['reload']['mode'],'GOLEM_RELAY_AVAILABLE')
        selected=observed['selected']
        result=self.refresh(observed['refresh_token'],target='b'*32)
        self.assertEqual(result['reload']['mode'],'VERIFY_REQUIRED')
        self.assertEqual(result['model_tool_delivery'],'NOT_OBSERVED')
        self.assertEqual(self.relay.calls,[('b'*32,'refresh',{
            'expected_launcher_sha256':'d'*64,'expected_approval_sha256':'e'*64,
            'state':selected['adapter_state'],'approval_sha256':selected['approval_sha256'],
            'launcher_sha256':selected['launcher_sha256'],'config_sha256':selected['config_sha256']})])
        self.assertEqual(self.relay.rows['a'*32]['selected_state'],'/fixture/old-state')

    def test_reply_loss_blocks_same_target_and_does_not_dispatch_again(self):
        observed=self.monitor.inspect()
        self.relay.failure=OSError('fixture reply lost after dispatch')
        with self.assertRaises(OSError): self.refresh(observed['refresh_token'])
        self.expect('REFRESH_ALREADY_ATTEMPTED_NO_RETRY',
                    lambda:self.refresh(self.monitor.inspect()['refresh_token']))
        self.assertEqual(len(self.relay.calls),1)

    def test_new_observation_allows_other_relay_without_repeating_first(self):
        self.refresh(self.monitor.inspect()['refresh_token'],target='a'*32)
        self.refresh(self.monitor.inspect()['refresh_token'],target='b'*32)
        self.assertEqual([(i,op) for i,op,_ in self.relay.calls],
                         [('a'*32,'refresh'),('b'*32,'refresh')])

    def test_forty_absent_relay_endpoints_do_not_consume_live_budget(self):
        template=copy.deepcopy(self.relay.rows['a'*32])
        for number in range(40):
            key=f'{number:032x}'
            self.relay.rows[key]=dict(template,instance=key,endpoint_state='ABSENT')
        with patch.object(self.relay,'request',wraps=self.relay.request) as request:
            report=self.monitor.inspect()
        self.assertEqual(request.call_count,2)
        self.assertEqual(sum(r.get('state')==connection.ENDPOINT_ABSENT for r in report['connections']),40)
        self.assertEqual(report['connections'][0]['instance'],'a'*32)
        self.assertEqual(len(self.relay.rows),42)

    def test_relay_unknown_and_budget_sentinel_block_current_Desktop(self):
        self.monitor.observer=lambda:[self.row()]
        selected=self.selected()
        template=copy.deepcopy(self.relay.rows['a'*32])
        template.update(launcher_sha256=selected['launcher_sha256'],approval_sha256=selected['approval_sha256'],
                        selected_state=selected['adapter_state'])
        self.relay.rows={f'{i:032x}':dict(template,instance=f'{i:032x}') for i in range(17)}
        with patch.object(self.relay,'request',wraps=self.relay.request) as request:
            report=self.monitor.inspect()
        self.assertEqual(request.call_count,16)
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')
        self.relay.rows={f'{0:032x}':dict(template,instance=f'{0:032x}',endpoint_state='UNKNOWN')}
        self.assertEqual(self.monitor.inspect()['reload']['mode'],'OBSERVATION_INCOMPLETE')

    def test_latest_relay_found_among_retained_socket_records_without_global_current(self):
        selected=self.selected()
        template=copy.deepcopy(self.relay.rows['a'*32])
        template.update(launcher_sha256=selected['launcher_sha256'],approval_sha256=selected['approval_sha256'],
                        selected_state=selected['adapter_state'])
        self.relay.rows={f'{i:032x}':dict(template,instance=f'{i:032x}',discovery_mtime_ns=1) for i in range(40)}
        newest='f'*32
        self.relay.rows[newest]=dict(template,instance=newest,discovery_mtime_ns=2)
        original=self.relay.request
        def status(instance,operation,arguments):
            if instance != newest: raise ConnectionRefusedError('fixture retained socket')
            return original(instance,operation,arguments)
        with patch.object(self.relay,'request',side_effect=status) as request:
            report=self.monitor.inspect()
        self.assertEqual(request.call_count,16)
        self.assertEqual(request.call_args_list[0].args[0],newest)
        self.assertTrue(report['connections'][0]['relay_current'])
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')

    def test_relay_response_cannot_override_local_absence_or_current_fields(self):
        self.monitor.observer=lambda:[self.row()]
        original=self.relay.request
        def forged(instance,operation,arguments):
            response=original(instance,operation,arguments)
            response['value'].update(state=connection.ENDPOINT_ABSENT,relay_current=True)
            return response
        with patch.object(self.relay,'request',side_effect=forged):
            report=self.monitor.inspect()
        self.assertEqual(report['reload']['mode'],'OBSERVATION_INCOMPLETE')
        self.assertTrue(all(row['state']=='RELAY_UNAVAILABLE' for row in report['connections'][1:]))

    def test_observed_relay_is_not_hidden_by_UI_history_display_limit(self):
        import integration_connection_ui as ui
        self.monitor.observer=lambda:[{'instance':f'{i:032x}','state':'NOT_OBSERVED'} for i in range(128)]
        report=self.monitor.inspect()
        shown=ui.presentation(report)
        self.assertEqual(shown['relay_targets'],{'0':'a'*32,'1':'b'*32})
        self.assertEqual(len(report['connections']),130)
        self.assertEqual(len(shown['rows']),128)
        self.assertNotEqual(report['reload']['mode'],'VERIFIED')


if __name__ == '__main__':
    unittest.main()
