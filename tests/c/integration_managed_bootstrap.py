"""Native M2/D4 managed bootstrap on disposable Works; no client or product execution.

Usage: python3 integration_managed_bootstrap.py NATIVE_CLI SOURCE_ROOT
The local owner policy is constructed only inside this test's temporary directory.
Discovery statements are explicitly synthetic; CAS integrity is not their truth.
"""
import base64
import copy
import json
import subprocess
import sys
import unittest

import workflow_integration as workflow

sys.path.insert(0, str(workflow.SOURCE / 'tools'))
import integration_contract as c
import integration_registry as registry
import integration_transfer as transfer
import integration_mutation_contract as contract
import integration_mutations as mutations


class ManagedBootstrap(workflow.Workflow):
    def setUp(self):
        super().setUp()
        self.confirmed()
        self.source = self.validate()['snapshot_digest']
        self.project = self.root / 'project'
        self.work = self.project / '.golem/works/bootstrap'
        self.work.parent.mkdir(parents=True)
        self.docs, self.generation, self.entries = {}, 1, []
        specification = json.loads((workflow.SOURCE / 'samples/documents/work.json').read_text())
        self.cli('work', 'start', self.work, self.write('work-spec.json', specification))
        self.cli('evidence', 'put', self.work, self.write('observation.txt', 'fixture observation\n'))
        self.registry = registry.Registry.create(self.root / 'registry', approve_local_owner=True)
        enrollment = {'schema': 'golem.integration-enrollment.v1',
            'project': registry.describe('project', self.project, workflow.CLI,
                [workflow.SOURCE / 'samples/agent-session/status.json'], [('example-work', self.work)]),
            'grants': [{'schema': 'golem.integration-grant.v1', 'principal_id': 'owner',
                'client_id': 'fixture', 'operations': ['status', 'next', 'record', 'history'],
                'work_ids': ['example-work'], 'destination': 'LOCAL_HOST', 'assurance': 'LOCAL_COOPERATIVE'}]}
        plan = self.registry.plan(enrollment)
        self.registry.apply(enrollment, plan['plan_sha256'], approve_local_owner=True)
        policy = {'schema': 'golem.integration-transfer.v1', 'registry': str(self.registry.root),
            'registry_identity': self.registry.root_identity, 'destination': 'MODEL_SERVICE',
            'destination_id': 'disposable-fixture-no-model', 'max_result_bytes': 8388608,
            'data_class': 'APPROVED_WORK_CONTENT', 'scopes': [{'binding': {
                'schema': 'golem.integration-client-binding.v1', 'project_id': 'project', 'generation': 1,
                'principal_id': 'owner', 'client_id': 'fixture', 'assurance': 'LOCAL_COOPERATIVE'},
                'work_ids': ['example-work'], 'tools': list(transfer.NAMES), 'recipients': []}],
            'producer': transfer.producer()}
        self.transfer_path = self.private('transfer.json', c.encoded(policy))
        self.owner_policy()

    def private(self, name, raw):
        path = self.root / name
        path.write_bytes(raw)
        path.chmod(0o600)
        return path

    def owner_policy(self):
        policy = {'schema': 'golem.integration-mutations.v1',
            'transfer_policy': registry.file_pin(self.transfer_path), 'actions': self.entries,
            'producer': contract.producer()}
        path = self.private('mutations.json', c.encoded(policy))
        self.api = mutations.Service(contract.Policy(path, c.sha(path.read_bytes()), approve_mutations=True))

    def exact(self, tool, native, body='', *, name=None):
        envelope = {'schema': 'golem.integration-native-action.v1',
            'native_json': json.dumps(native) + '\n', 'body': body,
            'context_json': '', 'count_json': '', 'approval': None}
        return self.exact_envelope(tool, envelope, name=name)

    def exact_envelope(self, tool, envelope, *, name=None):
        # The disposable owner selects the exact M2 envelope. In particular,
        # do not parse/re-serialize its embedded native JSON before dispatch.
        name = name or 'fixture-action-' + str(len(self.entries))
        path = self.private(name + '.json', c.encoded(envelope))
        self.entries.append({'action_id': name, 'project_id': 'project', 'work_id': 'example-work',
            'tool': tool, 'session_id': 'fixture-owner', 'native_binding_id': '', 'action': registry.file_pin(path)})
        self.owner_policy()
        return self.api.call(tool, {'project_id': 'project', 'work_id': 'example-work',
            'action_id': name, 'request_id': name})

    def assert_exact_dispatch(self, result, envelope):
        self.assertEqual(result['state'], 'NATIVE_RESULT_RECORDED', result)
        output = self.registry.root / result['local_evidence_id']
        intent = c.decode((output / 'intent.json').read_bytes())
        native_bytes = envelope['native_json'].encode()
        self.assertEqual((output / 'request.json').read_bytes(), native_bytes)
        self.assertEqual(intent['native_sha256'], c.sha(native_bytes))
        self.assertEqual(intent['action_sha256'], c.sha(c.encoded(envelope)))
        selected = self.root / (intent['action']['action_id'] + '.json')
        self.assertEqual(selected.read_bytes(), c.encoded(envelope))
        self.assertEqual(intent['action']['action'], registry.file_pin(selected))

    def prepare(self, tool, fields, body='', *, name):
        before, dispatched = self.inventory(), set(self.registry.root.glob('mutation-*'))
        prepared = self.api.call('action_prepare', {'project_id': 'project', 'work_id': 'example-work',
            'preparation_request_id': name, 'tool': tool,
            'session_id': 'fixture-owner', 'native_binding_id': '',
            'fields_json': json.dumps(fields), 'body': body, 'context_json': '', 'count_json': ''})
        self.assertFalse(prepared['execution_authorized'])
        payload = prepared['plan']['payload']
        self.assertEqual(payload['questions'], [])
        self.assertEqual(payload['owner_registration'], 'NOT_PERFORMED')
        self.assertEqual(payload['action_sha256'], c.sha(c.encoded(payload['action'])))
        self.assertEqual(before, self.inventory())
        self.assertEqual(dispatched, set(self.registry.root.glob('mutation-*')))
        return payload['action']

    @staticmethod
    def document_fields(metadata):
        return {k: v for k, v in metadata.items()
                if k not in ('work_id', 'expected_generation', 'revision', 'supersedes')}

    def inventory(self):
        return {str(p.relative_to(self.work)): (p.stat().st_mode,
                    c.sha(p.read_bytes()) if p.is_file() else None) for p in self.work.rglob('*')}

    def read(self, name, **args):
        return self.api.call(name, {'project_id': 'project', 'work_id': 'example-work', **args})['result']

    def metadata_v2(self, kind='scope', assessment=None):
        metadata = self.metadata(kind, version=2)
        metadata.update(stage='planning', assessment=copy.deepcopy(assessment or self.a))
        return metadata

    def report(self, kind='scope', assessment=None):
        request = self.write('report-assessment.json', assessment or self.a)
        result = subprocess.run([str(workflow.CLI), '--output-mode', 'full', 'discovery', 'report',
            str(request), kind], env=workflow.ENV, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout.decode()

    def submit(self, metadata, body=None, *, envelope=None):
        if envelope is None:
            body = body if body is not None else self.report(metadata['kind'], metadata.get('assessment'))
            result = self.exact('document_submit', metadata, body)
        else:
            self.assertEqual(c.decode(envelope['native_json'].encode()), metadata)
            result = self.exact_envelope('document_submit', envelope)
            self.assert_exact_dispatch(result, envelope)
        self.assertEqual(result['state'], 'NATIVE_RESULT_RECORDED', result)
        reply = result['native_reply']
        self.assertFalse(reply['acceptance_verified'])
        self.generation += 1
        # The mutation endpoint preserves the native CLI's uint64 string.
        self.assertEqual(reply['generation'], str(self.generation))
        self.docs[metadata['document_id']] = reply
        return reply

    def select(self):
        return self.read('workflow_read', operation='select', selection_id='scope',
                         revision=self.docs['scope']['revision'], target_kind='development')

    def selection_metadata(self, selection):
        metadata = self.metadata('stage-selection', 'selection', [selection['scope']], 3)
        metadata['selection'] = selection
        return metadata

    def test_fresh_native_record_m2_scope_selection_and_session_start(self):
        before = self.inventory()
        self.assertEqual(self.read('work_inspect', view='record')['documents'], [])
        self.assertNotIn('document_submit', self.api.tools())
        metadata, body = self.metadata_v2(), self.report()
        action = self.prepare('document_submit', self.document_fields(metadata), body, name='draft-scope')
        self.assertEqual(c.decode(action['native_json'].encode()), metadata)
        self.assertEqual(before, self.inventory())
        self.assertEqual(list(self.registry.root.glob('mutation-*')), [])
        self.submit(metadata, envelope=action)
        selection = self.select()
        self.assertEqual([v['stage'] for v in selection['decisions']],
                         ['planning', 'ux', 'publishing', 'development', 'qa', 'audit'])
        selected = self.selection_metadata(selection)
        selected_action = self.prepare('document_submit', self.document_fields(selected),
            self.body('stage-selection', selected['parents']), name='draft-selection')
        self.submit(selected, envelope=selected_action)
        start_action = self.prepare('session_start', {'selection_id': 'selection'}, name='draft-start')
        start = c.decode(start_action['native_json'].encode())
        self.assertEqual({k: v for k, v in start.items() if k != 'key'},
            {'schema_version': 1, 'operation': 'start', 'work_id': 'example-work',
             'selection_id': 'selection', 'expected_sequence': 0})
        result = self.exact_envelope('session_start', start_action)
        self.assert_exact_dispatch(result, start_action)
        self.assertEqual(len(list(self.registry.root.glob('mutation-*'))), 3)
        status = self.read('work_inspect', view='status')
        self.assertEqual(status['sequence'], 1)
        self.assertIsNone(status['state']['active'])
        self.assertEqual(status['state']['attempts'], 0)
        self.assertEqual(self.read('work_inspect', view='next')['reason'], 'CLAIM_REQUIRED')
        self.assertEqual({row['document_id'] for row in self.read('work_inspect', view='record')['documents']},
                         {'scope', 'selection'})

    def test_exact_mcp_source_capture_to_scope_selection_and_session_start(self):
        # This repository and all exact owner actions exist only in the disposable
        # fixture. Capture is the real D4/native path, not the sample's zero hashes.
        git_env = {**workflow.ENV, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_AUTHOR_DATE': '2000-01-01T00:00:00Z', 'GIT_COMMITTER_DATE': '2000-01-01T00:00:00Z'}
        def git(*args):
            return subprocess.run(['/usr/bin/git', '-C', str(self.project),
                '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', *args],
                check=True, capture_output=True, env=git_env).stdout.decode().strip()
        git('init')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        (self.project / 'code.c').write_text('synthetic bootstrap source\n')
        git('add', 'code.c')
        git('commit', '-m', 'disposable bootstrap baseline')
        head, source_bytes = git('rev-parse', 'HEAD'), (self.project / 'code.c').read_bytes()
        plan = {'schema_version': 1, 'timeout_seconds': 60, 'repositories': [{
            'id': 'fixture-repo', 'root': str(self.project), 'paths': ['code.c'],
            'toolchain': 'Synthetic source; no compiler invocation.',
            'test_configuration': 'No product commands or QA performed.'}]}
        before = self.inventory()
        self.assertNotIn('discovery_snapshot', self.api.tools())
        capture_action = self.prepare('discovery_snapshot', {'plan_json': json.dumps(plan)},
                                      name='draft-source-capture')
        captured = self.exact_envelope('discovery_snapshot', capture_action, name='capture-source')
        self.assert_exact_dispatch(captured, capture_action)
        self.assertFalse(captured['execution_authorized'])
        self.assertFalse(captured['acceptance_verified'])
        self.assertEqual(before, self.inventory())
        self.assertEqual(head, git('rev-parse', 'HEAD'))
        self.assertEqual(source_bytes, (self.project / 'code.c').read_bytes())

        # MCP JSON presentation can reorder object members. Only the preserved
        # native bytes carry the capture ordering used by the native digest.
        wire_reply = c.decode(c.encoded(captured))
        raw = base64.b64decode(wire_reply['native_stdout_base64'], validate=True)
        self.assertEqual(c.sha(raw), wire_reply['native_stdout_sha256'])
        snapshot = json.loads(raw)
        self.assertEqual(snapshot, wire_reply['native_reply'])
        repo = snapshot['repositories'][0]
        self.assertEqual(repo['head'], head)
        self.assertEqual(repo['files'][0]['digest'], c.sha(source_bytes))
        self.assertTrue(repo['files'][0]['tracked'])
        self.assertFalse(repo['files'][0]['dirty'])
        self.a['snapshot'] = snapshot
        self.a['findings'][0].update(repository_id='fixture-repo', path='code.c')
        validated = self.read('native_validate', kind='discovery', request_json=json.dumps(self.a))
        self.assertTrue(validated['scope_ready'])
        self.assertFalse(validated['execution_authorized'])
        self.assertFalse(validated['acceptance_verified'])
        self.source = validated['snapshot_digest']
        self.assertEqual(len(self.source), 64)
        self.assertNotEqual(self.source, head)

        metadata = self.metadata_v2()
        body = self.read('discovery_read', operation='report', kind='scope',
                         request_json=json.dumps(self.a))
        scope_action = self.prepare('document_submit', self.document_fields(metadata), body,
                                    name='captured-draft-scope')
        self.assertEqual(c.decode(scope_action['native_json'].encode())['source_snapshot'], self.source)
        self.submit(metadata, envelope=scope_action)
        selection = self.select()
        selected = self.selection_metadata(selection)
        selection_action = self.prepare('document_submit', self.document_fields(selected),
            self.body('stage-selection', selected['parents']), name='captured-draft-selection')
        self.submit(selected, envelope=selection_action)
        start_action = self.prepare('session_start', {'selection_id': 'selection'},
                                    name='captured-draft-start')
        started = self.exact_envelope('session_start', start_action)
        self.assert_exact_dispatch(started, start_action)
        self.assertEqual(len(list(self.registry.root.glob('mutation-*'))), 4)
        status = self.read('work_inspect', view='status')
        self.assertEqual(status['sequence'], 1)
        self.assertIsNone(status['state']['active'])
        self.assertEqual(status['state']['attempts'], 0)
        self.assertEqual(self.read('work_inspect', view='next')['reason'], 'CLAIM_REQUIRED')
        self.assertEqual({row['document_id'] for row in self.read('work_inspect', view='record')['documents']},
                         {'scope', 'selection'})

    def test_all_three_schema2_kinds_reach_native_parser_and_store(self):
        for kind in ('discovery', 'research', 'scope'):
            with self.subTest(kind=kind):
                self.submit(self.metadata_v2(kind))
        self.assertEqual(self.generation, 4)
        status = self.read('work_inspect', view='status')
        self.assertEqual(status['sequence'], 0)
        self.assertIsNone(status['state'])

    def test_native_parser_rejects_invalid_schema2_metadata(self):
        original = self.metadata_v2()
        body = self.write('native-body.md', self.report())
        changes = ({'kind': 'planning'}, {'stage': 'qa'}, {'assessment': {}},
                   {'source_snapshot': 'f' * 64}, {'requirement_ids': ['FOREIGN']})
        before = self.inventory()
        for change in changes:
            with self.subTest(fields=tuple(change)):
                metadata = {**original, **change}
                self.cli('document', 'validate', self.write('invalid-metadata.json', metadata), body, ok=False)
        self.assertEqual(before, self.inventory())

    def test_reordered_snapshot_is_rejected_not_rehashed_by_m2(self):
        metadata = self.metadata_v2()
        fields = {k: v for k, v in metadata.items()
                  if k not in ('work_id', 'expected_generation', 'revision', 'supersedes')}
        reordered = c.encoded(fields).decode()
        self.assertNotEqual(list(json.loads(reordered)['assessment']['snapshot']),
                            list(metadata['assessment']['snapshot']))
        before = self.inventory()
        with self.assertRaises(c.IntegrationError) as caught:
            self.api.call('action_prepare', {'project_id': 'project', 'work_id': 'example-work',
                'preparation_request_id': 'reordered-scope', 'tool': 'document_submit',
                'session_id': 'fixture-owner', 'native_binding_id': '',
                'fields_json': reordered, 'body': self.report(), 'context_json': '', 'count_json': ''})
        self.assertEqual(caught.exception.code, 'NATIVE_FAILURE')
        self.assertEqual(before, self.inventory())
        self.assertEqual(list(self.registry.root.glob('mutation-*')), [])
        self.assertEqual(list(self.registry.root.glob('read-m2-plan-*')), [])

    def test_missing_cas_evidence_fails_native_submission_without_retry(self):
        metadata = self.metadata_v2()
        metadata['assessment']['findings'][0]['reproduction']['evidence_digest'] = 'f' * 64
        body = self.report(assessment=metadata['assessment'])
        before = self.inventory()
        result = self.exact('document_submit', metadata, body)
        self.assertEqual(result['state'], 'COMMIT_UNKNOWN', result)
        self.assertFalse(result['automatic_retry_allowed'])
        self.assertEqual(before, self.inventory())

    def test_stale_generation_does_not_become_a_new_document(self):
        self.submit(self.metadata_v2())
        metadata = self.metadata_v2('research')
        metadata['expected_generation'] = 1
        before = self.inventory()
        result = self.exact('document_submit', metadata, self.report('research'))
        self.assertEqual(result['state'], 'COMMIT_UNKNOWN', result)
        self.assertFalse(result['automatic_retry_allowed'])
        self.assertEqual(before, self.inventory())

    def test_unready_scope_cannot_select_or_start_a_session(self):
        assessment = json.loads((workflow.SOURCE / 'samples/discovery/assessment.json').read_text())
        self.submit(self.metadata_v2(assessment=assessment))
        before = self.inventory()
        self.cli('workflow', 'select', self.work, 'scope', 1, 'development', ok=False)
        self.cli('session', 'call', self.work, self.write('missing-selection.json', {
            'schema_version': 1, 'operation': 'start', 'work_id': 'example-work',
            'selection_id': 'selection', 'key': 'unready-start', 'expected_sequence': 0}), ok=False)
        self.assertEqual(before, self.inventory())

    def test_stale_scope_reference_cannot_register_stage_selection(self):
        self.submit(self.metadata_v2())
        selection = self.select()
        self.submit(self.metadata_v2())
        metadata = self.selection_metadata(selection)
        before = self.inventory()
        result = self.exact('document_submit', metadata, self.body('stage-selection', metadata['parents']))
        self.assertEqual(result['state'], 'COMMIT_UNKNOWN', result)
        self.assertEqual(before, self.inventory())


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('ManagedBootstrap.' + name,
        sys.modules[__name__]) for name in ManagedBootstrap.__dict__ if name.startswith('test_'))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
