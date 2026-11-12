"""Disposable Owner controller integration; no real client/model/Work calls."""
import copy
import errno
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import integration_stable_owner as owner
import test_integration_stable_entry as packaged


class StableOwner(unittest.TestCase):
    def setUp(self):
        # Reuse the existing verified packaged fake-broker fixture utilities,
        # without inheriting or rerunning its separate test methods.
        self.fx = packaged.PackagedEntry('test_verified_packaged_pipeline_for_both_clients')
        self.fx.setUp()
        self.addCleanup(self.fx.cleanup)
        self.root = self.fx.root
        self.home = patch.dict(os.environ, {'HOME': str(self.root)})
        self.home.start()
        self.addCleanup(self.home.stop)
        self.clients = {}
        self.initial = {}
        for client in ('codex', 'claude-desktop'):
            directory = self.root / client
            directory.mkdir(mode=0o700)
            store = directory / 'store'
            selection = self.fx.selection(directory, client, 'old')
            self.initial[client] = self.fx.cli(client, store, 'create', '--catalog', str(self.fx.catalog),
                '--catalog-sha256', self.fx.digest(self.fx.catalog), '--selection', str(selection),
                '--selection-sha256', self.fx.digest(selection), '--approve-selection')
            self.clients[client] = {'bundle_directory': str(self.fx.bundle),
                'bundle_sha256': self.fx.built['manifest_sha256'], 'store': str(store),
                'required_tools': ['golem_projects_list']}
        self.records = self.root / 'owner-records'
        self.records.mkdir(mode=0o700)
        self.config = self.fx.write(self.root / 'ui-config.json', {'schema': owner.CONFIG_SCHEMA,
            'records_directory': str(self.records), 'clients': self.clients})
        self.pin = self.fx.digest(self.config)
        self.controller = owner.StableOwnerController(self.config, self.pin)

    def start(self, client='codex'):
        store = Path(self.clients[client]['store'])
        process, buffer = self.fx.start(client, store)
        self.fx.rpc(process, 'initialize', 1, {'protocolVersion': '2025-06-18', 'capabilities': {},
            'clientInfo': {'name': 'owner-controller-fixture', 'version': '1'}})
        self.fx.read(process, buffer)
        self.fx.rpc(process, 'notifications/initialized')
        self.fx.rpc(process, 'tools/list', 2)
        definitions = self.fx.read(process, buffer)['result']
        marker = definitions['_meta']['golemStableCatalogMarker']
        model = {'source': 'EXTERNAL_MODEL_DEFINITION_OBSERVATION',
            'target': {'thread_id': 'synthetic-thread-' + client, 'server_name': 'fixture-golem'},
            'thread_id': 'synthetic-thread-' + client, 'server_name': 'fixture-golem',
            'turn_id': 'synthetic-turn', 'observed_at_ns': time.time_ns(),
            'marker': marker, 'tools': ['golem_projects_list']}
        path = self.fx.write(self.root / client / 'synthetic-model.json', model)
        return process, path, self.fx.digest(path), model

    def proposal(self, client='codex', label='new'):
        path = self.fx.selection(self.root / client, client, label, self.initial[client])
        return path, self.fx.digest(path)

    def publish(self, client='codex'):
        path, pin = self.proposal(client)
        preview = self.controller.review_selection(client, path, pin)
        result = self.controller.publish(client, preview['review']['token'], approve=True)
        self.assertEqual(result['state'], 'SELECTED_NOT_LIVE_APPLIED')
        return result

    def test_both_clients_exact_owner_flow_preserves_frontend_and_hold(self):
        for client in ('codex', 'claude-desktop'):
            with self.subTest(client=client):
                process, path, pin, model = self.start(client)
                first = self.controller.observe(client, path, pin)
                self.assertTrue(first['readiness']['preparation_allowed'])
                original_pid = first['live']['pid']
                original_epoch = first['live']['backend_epoch']
                original_requests = first['live']['frontend_catalog']['requests']
                proposed, proposed_pin = self.proposal(client)
                review = self.controller.review_selection(client, proposed, proposed_pin)
                self.assertEqual(review['review']['kind'], 'publish')
                with self.assertRaisesRegex(owner.StableOwnerError, 'CONFIRMATION_REQUIRED'):
                    self.controller.publish(client, review['review']['token'])
                published = self.controller.publish(client, review['review']['token'], approve=True)
                self.assertEqual(published['selected']['selection']['revision'], 2)
                self.assertIsNone(published['review'])
                stale = self.controller.observe(client, path, pin)
                self.assertFalse(stale['readiness']['preparation_allowed'])
                transition = self.controller.review_refresh(client, path, pin)
                self.assertEqual(transition['readiness']['state'], 'EXTERNAL_CORRELATION_ONLY')
                self.assertFalse(transition['readiness']['preparation_allowed'])
                self.assertEqual(transition['review']['kind'], 'refresh')
                with self.assertRaisesRegex(owner.StableOwnerError, 'CONFIRMATION_REQUIRED'):
                    self.controller.refresh(client, transition['review']['token'])
                ack = self.controller.refresh(client, transition['review']['token'], approve=True)
                self.assertEqual(ack['state'], 'POST_TRANSITION_OBSERVATION_REQUIRED')
                self.assertIsNone(ack['readiness'])
                self.assertIsNone(ack['review'])
                fresh = self.controller.observe(client, path, pin)
                self.assertTrue(fresh['readiness']['preparation_allowed'])
                self.assertEqual(fresh['live']['pid'], original_pid)
                self.assertEqual(process.pid, original_pid)
                self.assertGreater(fresh['live']['backend_epoch'], original_epoch)
                self.assertEqual(fresh['live']['definition_marker'], model['marker'])
                self.assertEqual(fresh['live']['frontend_catalog']['requests'], original_requests)
                self.assertEqual(fresh['model_observation']['observed_at_ns'], model['observed_at_ns'])
                self.assertFalse(fresh['execution_authorized'])
                self.assertEqual(fresh['actual_execution'], 'HOLD')
                self.assertFalse(fresh['automatic_retry_allowed'])
                reopened = owner.StableOwnerController(self.config, self.pin)
                historical = reopened.observe(client, path, pin)
                self.assertFalse(historical['readiness']['preparation_allowed'])
                self.assertEqual(historical['readiness']['reason'], 'REFRESH_UNKNOWN')
        self.assertEqual(len(list(self.records.glob('attempt-*.json'))), 4)
        self.assertEqual(len(list(self.records.glob('result-*.json'))), 4)

    def test_explicit_config_and_bundle_pins_block_drift(self):
        with self.assertRaisesRegex(owner.StableOwnerError, 'CONFIG_CHANGED'):
            owner.StableOwnerController(self.config, '0' * 64)
        value = json.loads(self.config.read_bytes())
        value['clients']['codex']['required_tools'] = ['golem_execute_anything']
        self.fx.write(self.config, value)
        with self.assertRaisesRegex(owner.StableOwnerError, 'CONFIG_CHANGED'):
            self.controller.inspect('codex')
        changed = owner.StableOwnerController(self.config, self.fx.digest(self.config))
        with self.assertRaisesRegex(owner.StableOwnerError, 'OUTSIDE_CATALOG'):
            changed.inspect('codex')

    def test_bundle_payload_drift_is_rejected_before_execution(self):
        payload = self.fx.bundle / 'stable_relay.py'
        payload.write_bytes(payload.read_bytes() + b'\nraise RuntimeError("MUST_NOT_EXECUTE")\n')
        with self.assertRaisesRegex(ValueError, 'STABLE_BUNDLE_PAYLOAD_CHANGED'):
            self.controller.inspect('codex')

    def test_client_isolation_and_config_unknown_fields(self):
        value = json.loads(self.config.read_bytes())
        value['clients']['claude-desktop']['store'] = value['clients']['codex']['store']
        bad = self.fx.write(self.root / 'same-store.json', value)
        with self.assertRaisesRegex(owner.StableOwnerError, 'STORE_ISOLATION'):
            owner.StableOwnerController(bad, self.fx.digest(bad))
        with self.assertRaisesRegex(owner.StableOwnerError, 'CLIENT_NOT_SELECTED'):
            self.controller.inspect('portable')
        proposed, pin = self.proposal('claude-desktop')
        with self.assertRaisesRegex(owner.StableOwnerError, 'SELECTION_NOT_NEXT'):
            self.controller.review_selection('codex', proposed, pin)
        value = json.loads(self.config.read_bytes()); value['command'] = '/bin/sh'
        bad = self.fx.write(self.root / 'unknown-field.json', value)
        with self.assertRaisesRegex(owner.StableOwnerError, 'CONFIG_FIELDS'):
            owner.StableOwnerController(bad, self.fx.digest(bad))

    def test_observation_changed_wrong_target_and_stale_are_not_repaired(self):
        _, path, pin, model = self.start()
        with self.assertRaisesRegex(ValueError, 'OBSERVATION_CHANGED'):
            self.controller.observe('codex', path, '0' * 64)
        for name, update, reason in (
            ('old', {'observed_at_ns': time.time_ns() - 301 * 10**9}, 'MODEL_OBSERVATION_STALE_OR_UNDATED'),
            ('thread', {'thread_id': 'different-thread'}, 'MODEL_TARGET_OR_TURN_MISMATCH'),
            ('tools', {'tools': ['golem_work_inspect']}, 'MODEL_FULL_TOOL_INVENTORY_MISMATCH')):
            with self.subTest(name=name):
                bad = self.fx.write(self.root / (name + '.json'), {**model, **update})
                result = self.controller.observe('codex', bad, self.fx.digest(bad))
                self.assertEqual(result['readiness']['reason'], reason)
                self.assertFalse(result['readiness']['preparation_allowed'])
                self.assertEqual(result['model_observation']['observed_at_ns'], update.get('observed_at_ns', model['observed_at_ns']))
        with self.assertRaises((FileNotFoundError, ValueError)):
            self.controller.observe('claude-desktop', path, pin)

    def test_wrong_catalog_or_nonce_marker_cannot_select_another_frontend(self):
        _, path, pin, model = self.start()
        parts = model['marker'].split(':')
        wrong = list(parts); wrong[2] = '0' * 64
        bad = self.fx.write(self.root / 'wrong-catalog.json', {**model, 'marker': ':'.join(wrong)})
        with self.assertRaisesRegex(owner.StableOwnerError, 'MODEL_CATALOG_MISMATCH'):
            self.controller.observe('codex', bad, self.fx.digest(bad))
        wrong = list(parts); wrong[3] = 'f' * len(parts[3])
        bad = self.fx.write(self.root / 'wrong-nonce.json', {**model, 'marker': ':'.join(wrong)})
        observed = self.controller.observe('codex', bad, self.fx.digest(bad))
        self.assertEqual(observed['readiness']['reason'], 'MODEL_FRONTEND_MARKER_MISMATCH')
        self.assertFalse(observed['readiness']['preparation_allowed'])

    def test_owner_confirmation_and_exact_head_cas_are_not_replaced_by_ui_review(self):
        proposed, pin = self.proposal()
        review = self.controller.review_selection('codex', proposed, pin)
        other = owner.StableOwnerController(self.config, self.pin)
        selected = other.review_selection('codex', proposed, pin)
        other.publish('codex', selected['review']['token'], approve=True)
        with self.assertRaisesRegex(owner.StableOwnerError, 'REVIEW_SELECTION_CHANGED'):
            self.controller.publish('codex', review['review']['token'], approve=True)
        self.assertEqual(len(list(self.records.glob('attempt-*.json'))), 1)

    def test_stale_review_and_different_client_token_block_before_effect(self):
        proposed, pin = self.proposal()
        review = self.controller.review_selection('codex', proposed, pin)
        token = review['review']['token']
        with self.assertRaisesRegex(owner.StableOwnerError, 'REVIEW_TARGET_CHANGED'):
            self.controller.publish('claude-desktop', token, approve=True)
        with patch.object(owner.time, 'time_ns', return_value=review['review']['reviewed_at_ns'] + 301 * 10**9):
            with self.assertRaisesRegex(owner.StableOwnerError, 'REVIEW_STALE'):
                self.controller.publish('codex', token, approve=True)
        self.assertFalse(list(self.records.iterdir()))

    def test_selection_bytes_changed_after_review_do_not_publish(self):
        proposed, pin = self.proposal()
        review = self.controller.review_selection('codex', proposed, pin)
        before = self.controller.inspect('codex')['selected']
        raw = json.loads(proposed.read_bytes()); raw['revision'] = 3
        self.fx.write(proposed, raw)
        result = self.controller.publish('codex', review['review']['token'], approve=True)
        self.assertEqual(result['state'], 'RESULT_UNKNOWN')
        self.assertEqual(self.controller.inspect('codex')['selected'], before)
        self.assertEqual(len(list(self.records.glob('attempt-*.json'))), 1)

    def test_journal_lock_contention_prevents_dispatch(self):
        proposed, pin = self.proposal()
        review = self.controller.review_selection('codex', proposed, pin)
        before = self.controller.inspect('codex')['selected']
        with self.controller._journal_lock(self.controller.config):
            with self.assertRaisesRegex(owner.StableOwnerError, 'JOURNAL_BUSY'):
                self.controller.publish('codex', review['review']['token'], approve=True)
        self.assertEqual(self.controller.inspect('codex')['selected'], before)
        self.assertFalse(list(self.records.glob('attempt-*.json')))

    def test_busy_or_unknown_connection_blocks_transition_review(self):
        _, path, pin, _ = self.start()
        self.publish()
        modules = owner._load_bundle(self.fx.bundle, self.fx.built['manifest_sha256'])
        original = modules.relay.request
        for changed in ({'busy': True, 'pending': 1}, {'state': 'UNKNOWN', 'failure': 'UNCERTAIN'}):
            def status(*args, **kwargs):
                reply = original(*args, **kwargs)
                reply['value'].update(changed)
                return reply
            with self.subTest(changed=changed), patch.object(owner, '_load_bundle', return_value=modules), patch.object(modules.relay, 'request', side_effect=status):
                with self.assertRaisesRegex(owner.StableOwnerError, 'BUSY_OR_UNCERTAIN'):
                    self.controller.review_refresh('codex', path, pin)
        self.assertEqual(len(list(self.records.glob('attempt-*.json'))), 1)

    def test_connection_became_busy_after_preview_does_not_dispatch_refresh(self):
        _, path, pin, _ = self.start()
        self.publish()
        review = self.controller.review_refresh('codex', path, pin)
        modules = owner._load_bundle(self.fx.bundle, self.fx.built['manifest_sha256'])
        original = modules.relay.request
        def busy(client, instance, operation, arguments):
            self.assertEqual(operation, 'status', 'must not dispatch refresh after changed status')
            reply = original(client, instance, operation, arguments)
            reply['value'].update(busy=True, pending=1)
            return reply
        with patch.object(owner, '_load_bundle', return_value=modules), patch.object(modules.relay, 'request', side_effect=busy):
            with self.assertRaisesRegex(owner.StableOwnerError, 'REVIEW_CONNECTION_CHANGED'):
                self.controller.refresh('codex', review['review']['token'], approve=True)
        self.assertEqual(len(list(self.records.glob('attempt-*.json'))), 1)

    def test_uncertain_refresh_is_durable_and_not_retried_after_ui_reopen(self):
        _, path, pin, _ = self.start()
        self.publish()
        review = self.controller.review_refresh('codex', path, pin)
        modules = owner._load_bundle(self.fx.bundle, self.fx.built['manifest_sha256'])
        original = modules.relay.request
        effects = []
        def lost(client, instance, operation, arguments):
            if operation == 'refresh':
                effects.append((client, instance))
                raise TimeoutError('reply lost')
            return original(client, instance, operation, arguments)
        with patch.object(owner, '_load_bundle', return_value=modules), patch.object(modules.relay, 'request', side_effect=lost):
            result = self.controller.refresh('codex', review['review']['token'], approve=True)
        self.assertEqual(result['state'], 'RESULT_UNKNOWN')
        self.assertEqual(len(effects), 1)
        reopened = owner.StableOwnerController(self.config, self.pin)
        observed = reopened.observe('codex', path, pin)
        self.assertEqual(observed['readiness']['reason'], 'REFRESH_UNKNOWN')
        with self.assertRaisesRegex(owner.StableOwnerError, 'PREVIOUS_TRANSITION_UNCERTAIN'):
            reopened.review_refresh('codex', path, pin)
        self.assertEqual(len(effects), 1)
        self.assertEqual(len(list(self.records.glob('attempt-*.json'))), 2)

    def test_result_sync_failure_retains_unknown_even_if_backend_did_change(self):
        _, path, pin, _ = self.start()
        self.publish()
        review = self.controller.review_refresh('codex', path, pin)
        original = owner._write_new
        def interrupted(path, value):
            reference = original(path, value)
            if value.get('schema') == 'golem.stable-owner-result.v1':
                raise OSError(errno.ENOSPC, 'fixture result sync failed after visible bytes')
            return reference
        with patch.object(owner, '_write_new', side_effect=interrupted):
            result = self.controller.refresh('codex', review['review']['token'], approve=True)
        self.assertEqual(result['state'], 'RESULT_UNKNOWN')
        self.assertEqual(len(list(self.records.glob('pending-*.json'))), 1)
        # A result file with visible ACK bytes does not erase the uncertainty.
        reopened = owner.StableOwnerController(self.config, self.pin)
        observed = reopened.observe('codex', path, pin)
        self.assertEqual(observed['live']['selection_sha256'], review['review']['target_selection_sha256'])
        self.assertGreater(observed['live']['backend_epoch'], review['review']['previous_backend_epoch'])
        self.assertEqual(observed['readiness']['reason'], 'REFRESH_UNKNOWN')
        self.assertFalse(observed['readiness']['preparation_allowed'])
        with self.assertRaisesRegex(owner.StableOwnerError, 'PREVIOUS_TRANSITION_UNCERTAIN'):
            reopened.review_refresh('codex', path, pin)

    def test_final_cleanup_and_repoison_failure_cannot_promote_historical_ack(self):
        _, path, pin, _ = self.start()
        self.publish()
        review = self.controller.review_refresh('codex', path, pin)
        write, sync = owner._write_new, owner._sync_directory
        pending_writes = {}
        def no_repoison(path, value):
            if path.name.startswith('pending-'):
                pending_writes[path] = pending_writes.get(path, 0) + 1
                if pending_writes[path] > 1:
                    raise OSError(errno.ENOSPC, 'fixture cannot persist poison')
            return write(path, value)
        def failed_cleanup(directory):
            if len(list(self.records.glob('result-*.json'))) == 2 and not list(self.records.glob('pending-*.json')):
                raise OSError(errno.EIO, 'fixture final unlink sync failed')
            return sync(directory)
        with patch.object(owner, '_write_new', side_effect=no_repoison), patch.object(owner, '_sync_directory', side_effect=failed_cleanup):
            result = self.controller.refresh('codex', review['review']['token'], approve=True)
        self.assertEqual(result['state'], 'RESULT_UNKNOWN')
        self.assertFalse(list(self.records.glob('pending-*.json')))
        self.assertEqual(len(list(self.records.glob('result-*.json'))), 2)
        reopened = owner.StableOwnerController(self.config, self.pin)
        observed = reopened.observe('codex', path, pin)
        self.assertEqual(observed['live']['selection_sha256'], review['review']['target_selection_sha256'])
        self.assertEqual(observed['readiness']['reason'], 'REFRESH_UNKNOWN')
        self.assertFalse(observed['readiness']['preparation_allowed'])
        with self.assertRaisesRegex(owner.StableOwnerError, 'PREVIOUS_TRANSITION_UNCERTAIN'):
            reopened.review_refresh('codex', path, pin)

    def test_journal_enospc_prevents_dispatch_and_preserves_partial_attempt(self):
        proposed, pin = self.proposal()
        review = self.controller.review_selection('codex', proposed, pin)
        before = self.controller.inspect('codex')['selected']
        def no_space(path, value):
            path.write_bytes(b'{"partial":')
            path.chmod(0o600)
            raise OSError(errno.ENOSPC, 'fixture full')
        with patch.object(owner, '_write_new', side_effect=no_space):
            result = self.controller.publish('codex', review['review']['token'], approve=True)
        self.assertEqual(result['state'], 'RESULT_UNKNOWN')
        self.assertEqual(self.controller.inspect('codex')['selected'], before)
        self.assertEqual(len(list(self.records.glob('attempt-*.json'))), 1)
        self.assertFalse(list(self.records.glob('result-*.json')))
        next_review = self.controller.review_selection('codex', proposed, pin)
        with self.assertRaisesRegex(owner.StableOwnerError, 'EFFECT_ALREADY_ATTEMPTED'):
            self.controller.publish('codex', next_review['review']['token'], approve=True)

    def test_closed_connection_cannot_be_reviewed_and_descriptor_is_preserved(self):
        process, path, pin, model = self.start()
        process.stdin.close()
        process.wait(timeout=5)
        rows = self.controller.inspect('codex')['connections']
        row = next(row for row in rows if row['instance'] == model['marker'].split(':')[1])
        self.assertEqual(row['endpoint_state'], 'ABSENT')
        with self.assertRaisesRegex(owner.StableOwnerError, 'CLOSED_OR_UNKNOWN'):
            self.controller.review_refresh('codex', path, pin)


if __name__ == '__main__':
    unittest.main()
