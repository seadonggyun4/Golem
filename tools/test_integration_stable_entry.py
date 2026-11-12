"""Verified packaged CLI wiring, with fake backend and synthetic observations.

No host/model SDK, installed client, native Work, D2/D4 authority or real model
delivery is exercised. Synthetic observation inputs test parser/correlation
behavior only; their acceptance is not an actual client validation claim.
"""
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time
import unittest
import uuid

import integration_stable_catalog as builder
from test_integration_stable_host import FAKE_BACKEND


SOURCE = Path(__file__).resolve().parents[1] / 'plugins/golem/scripts'


def load_adapter():
    spec = importlib.util.spec_from_file_location('packaged_fixture_adapter', SOURCE / 'launcher.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackagedEntry(unittest.TestCase):
    def setUp(self):
        parent = Path('/private/tmp' if sys.platform == 'darwin' else '/tmp')
        for attempt in range(100):
            self.root = parent / ('e' + uuid.uuid4().hex[:2])
            try:
                self.root.mkdir(mode=0o700)
                break
            except FileExistsError:
                continue
        else:
            self.fail('No short exclusive fixture directory available')
        self.processes = []
        self.addCleanup(self.cleanup)
        self.adapter = load_adapter()
        self.bundle = self.root / 'broker'
        self.built = builder.build_broker(self.bundle)
        self.entry = self.bundle / 'stable_entry.py'
        self.environment = {'PATH':'/usr/bin:/bin', 'HOME':str(self.root), 'TMPDIR':str(self.root)}
        self.catalog = self.write(self.root / 'catalog.json', builder.catalog('read', ['projects_list']))
        (self.root / 'fake-backend.py').write_text(FAKE_BACKEND)

    def cleanup(self):
        uncertain = []
        for process in self.processes:
            if not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                uncertain.append(process.pid)
            if process.poll() is not None:
                process.stdout.close()
                process.stderr.close()
        if uncertain:
            self.fail(f'EOF shutdown unobserved, no signals sent; PIDs {uncertain}; preserved {self.root}')
        shutil.rmtree(self.root)

    def write(self, path, value):
        path.write_bytes(builder.encoded(value))
        path.chmod(0o600)
        return path

    def digest(self, path):
        return builder.digest(path.read_bytes())

    def selection(self, directory, client, label, previous=None):
        state = directory / (label + '-state')
        state.mkdir(mode=0o700)
        launcher = self.write(directory / (label + '-launcher.json'), {'command':sys.executable,
            'args':['-I', '-B', str(self.root / 'fake-backend.py'), str(directory), label, self.digest(self.catalog)]})
        self.adapter.configure(state, launcher, self.digest(launcher), True, client)
        inspected = self.adapter.inspect_state(state, client)
        return self.write(directory / (label + '-selection.json'), {
            'schema':'golem.stable-selection.v1', 'client':client, 'revision':2 if previous else 1,
            'previous_sha256':previous['selection_sha256'] if previous else None,
            'catalog_sha256':self.digest(self.catalog), 'adapter_state':str(state),
            'approval_sha256':inspected['approval_sha256'], 'launcher_sha256':inspected['launcher_sha256']})

    def argv(self, client, store, operation, extra):
        return [sys.executable, '-I', '-B', str(self.entry), operation, '--client', client,
            '--store', str(store), '--reviewed-bundle-sha256', self.built['manifest_sha256'], *extra]

    def cli(self, client, store, operation, *extra, expected=0):
        result = subprocess.run(self.argv(client, store, operation, extra), env=self.environment,
            cwd=self.root, capture_output=True, timeout=10, text=True)
        self.assertEqual(result.returncode, expected, (result.stdout, result.stderr))
        return json.loads(result.stdout or result.stderr)

    def start(self, client, store):
        process = subprocess.Popen(self.argv(client, store, 'serve', []), cwd=self.root,
            env=self.environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0)
        self.processes.append(process)
        return process, bytearray()

    def rpc(self, process, method, request_id=None, params=None):
        value = {'jsonrpc':'2.0', 'method':method}
        if request_id is not None:
            value['id'] = request_id
        if params is not None:
            value['params'] = params
        process.stdin.write(builder.encoded(value))
        process.stdin.flush()

    def read(self, process, buffer):
        deadline = time.monotonic() + 8
        while b'\n' not in buffer:
            remaining = deadline - time.monotonic()
            self.assertGreater(remaining, 0, 'No packaged stdio reply; no automatic retry')
            self.assertTrue(select.select([process.stdout], [], [], remaining)[0], 'Packaged stdio timeout')
            part = os.read(process.stdout.fileno(), 65536)
            self.assertTrue(part, 'Packaged stdio closed before reply')
            buffer.extend(part)
            self.assertLessEqual(len(buffer), 1024 * 1024)
        line, _, rest = buffer.partition(b'\n')
        buffer[:] = rest
        return json.loads(line)

    def readiness(self, client, store, instance, model, refresh=None, expected=0):
        extra = ['--connection-instance', instance, '--model-observation', str(model),
            '--model-observation-sha256', self.digest(model), '--require-tool', 'golem_projects_list']
        if refresh is not None:
            extra += ['--refresh-evidence', str(refresh), '--refresh-evidence-sha256', self.digest(refresh)]
        return self.cli(client, store, 'readiness', *extra, expected=expected)

    def test_verified_packaged_pipeline_for_both_clients(self):
        for client in ('codex', 'claude-desktop'):
            with self.subTest(client=client):
                directory = self.root / client
                directory.mkdir(mode=0o700)
                store = directory / 'store'
                first = self.selection(directory, client, 'old')
                original = self.cli(client, store, 'create', '--catalog', str(self.catalog),
                    '--catalog-sha256', self.digest(self.catalog), '--selection', str(first),
                    '--selection-sha256', self.digest(first), '--approve-selection')
                self.assertFalse(original['execution_authorized'])
                process, buffer = self.start(client, store)
                self.rpc(process, 'initialize', 1, {'protocolVersion':'2025-06-18', 'capabilities':{},
                    'clientInfo':{'name':'packaged-cli-fixture', 'version':'1'}})
                initialized = self.read(process, buffer)
                self.assertEqual(initialized['result']['capabilities'], {'tools':{'listChanged':False}})
                self.rpc(process, 'notifications/initialized')
                self.rpc(process, 'tools/list', 2)
                definitions = self.read(process, buffer)['result']
                marker = definitions['_meta']['golemStableCatalogMarker']
                instance = marker.split(':')[1]
                self.assertEqual([tool['name'] for tool in definitions['tools']], ['golem_projects_list'])
                status = self.cli(client, store, 'status', '--connection-instance', instance)
                self.assertIs(status['ok'], True)
                before = status['value']
                self.assertEqual(before['client'], client)
                self.assertEqual(before['selection_sha256'], original['selection_sha256'])
                # Deliberately synthetic external observation: it tests exact
                # wiring but does not assert any actual model consumed tools.
                observation = {'source':'EXTERNAL_MODEL_DEFINITION_OBSERVATION',
                    'target':{'thread_id':'synthetic-fixture-thread', 'server_name':'fixture-golem'},
                    'thread_id':'synthetic-fixture-thread', 'server_name':'fixture-golem',
                    'turn_id':'synthetic-fixture-turn', 'observed_at_ns':time.time_ns(),
                    'marker':marker, 'tools':['golem_projects_list']}
                model = self.write(directory / 'synthetic-observation.json', observation)
                ready = self.readiness(client, store, instance, model)
                self.assertTrue(ready['preparation_allowed'])
                self.assertFalse(ready['execution_authorized'])
                self.assertFalse(ready['owner_identity_authenticated'])
                self.assertFalse(ready['native_work_verified'])
                self.assertEqual(ready['actual_execution'], 'HOLD')
                for uncertain in ('FAILED', 'UNKNOWN'):
                    evidence = self.write(directory / ('synthetic-' + uncertain.lower() + '.json'),
                        {'state':uncertain, 'attempts':1})
                    blocked = self.readiness(client, store, instance, model, evidence, expected=1)
                    self.assertEqual(blocked['reason'], 'REFRESH_' + uncertain)
                    self.assertFalse(blocked['preparation_allowed'])
                    self.assertFalse(blocked['automatic_retry_allowed'])
                    self.assertEqual(blocked['actual_execution'], 'HOLD')
                wrong = self.write(directory / 'synthetic-wrong-marker.json',
                    {**observation, 'marker':marker[:-1] + ('a' if marker[-1] != 'a' else 'b')})
                blocked = self.readiness(client, store, instance, wrong, expected=1)
                self.assertEqual(blocked['reason'], 'MODEL_FRONTEND_MARKER_MISMATCH')
                second = self.selection(directory, client, 'new', original)
                target = self.cli(client, store, 'publish', '--selection', str(second),
                    '--selection-sha256', self.digest(second), '--expected-head-sha256', original['head_sha256'],
                    '--approve-selection')
                # Selection on disk alone cannot satisfy the live backend stage.
                blocked = self.readiness(client, store, instance, model, expected=1)
                self.assertEqual(blocked['reason'], 'LIVE_SELECTION_OR_CATALOG_MISMATCH')
                refresh = self.cli(client, store, 'refresh', '--connection-instance', instance,
                    '--connection-marker', marker, '--expected-selection-sha256', original['selection_sha256'],
                    '--target-selection-sha256', target['selection_sha256'], '--approve-refresh')
                self.assertTrue(refresh['ok'])
                acknowledgement = self.write(directory / 'refresh-evidence.json', {
                    'state':'ACKNOWLEDGED', 'attempts':1, 'completed_at_ns':time.time_ns(),
                    'target_selection_sha256':target['selection_sha256'],
                    'previous_backend_epoch':before['backend_epoch']})
                ready = self.readiness(client, store, instance, model, acknowledgement)
                self.assertTrue(ready['preparation_allowed'])
                self.assertFalse(ready['execution_authorized'])
                self.assertEqual(ready['actual_execution'], 'HOLD')
                after = self.cli(client, store, 'status', '--connection-instance', instance)['value']
                self.assertEqual(after['definition_marker'], marker)
                self.assertEqual(after['selection_sha256'], target['selection_sha256'])
                self.assertEqual(after['backend_epoch'], before['backend_epoch'] + 1)
                self.assertEqual(after['frontend_catalog']['requests'], before['frontend_catalog']['requests'])
                no_epoch_advance = self.write(directory / 'synthetic-no-advance.json', {
                    'state':'ACKNOWLEDGED', 'attempts':1, 'completed_at_ns':time.time_ns(),
                    'target_selection_sha256':target['selection_sha256'],
                    'previous_backend_epoch':after['backend_epoch']})
                blocked = self.readiness(client, store, instance, model, no_epoch_advance, expected=1)
                self.assertEqual(blocked['reason'], 'POST_ACK_BACKEND_PROOF_NOT_OBSERVED')
                rows = [json.loads(line) for line in (directory / 'backend-events.jsonl').read_text().splitlines()]
                self.assertEqual([row['version'] for row in rows if row.get('method') == 'initialize'], ['old', 'new'])
                self.assertFalse(any(row.get('method') in ('tools/call', 'tools/list') for row in rows))
                process.stdin.close()
                self.assertEqual(process.wait(timeout=5), 0)


if __name__ == '__main__':
    unittest.main()
