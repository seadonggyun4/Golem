"""Readiness evidence fixtures only; no installed client, host or Work calls."""
import copy
import hashlib
import json
import unittest

import integration_connection_readiness as readiness


NOW = 2_000_000_000_000_000_000


def fixture():
    marker = {'instance': 'a'*32, 'child_generation': 2, 'catalog_generation': 3,
              'definition_nonce': 'b'*32}
    catalog = {'schema': 'golem.host-tool-catalog-observation.v1',
        'child_generation': 2, 'catalog_generation': 3,
        'state': 'HOST_CATALOG_RESPONSE_SENT', 'requests': 2, 'responses': 2, 'errors': 0,
        'list_changed_notifications_sent': 1, 'last_complete_generation': 3,
        'last_complete_sha256': 'c'*64, 'last_complete_pages': 2,
        'current_complete_sha256': 'c'*64, 'current_complete_pages': 2,
        'model_delivery_verified': False}
    selected = {'server_name': 'golem-local', 'config_sha256': 'd'*64,
        'approval_sha256': 'e'*64, 'launcher_sha256': 'f'*64,
        'adapter_state': '/fixture/adapter-state', 'package_version': '0.2.11'}
    live = {'instance': marker['instance'], 'definition_nonce': marker['definition_nonce'],
        'state': 'READY', 'busy': False, 'host_catalog': catalog,
        'selected_state': selected['adapter_state'], 'launcher_sha256': selected['launcher_sha256'],
        'approval_sha256': selected['approval_sha256'], 'plugin_version': selected['package_version'],
        'observed_at_ns': NOW-1_000_000_000, 'definition_tool_count':2,
        'definition_tools_sha256':hashlib.sha256(json.dumps(
            ['golem_document_submit','golem_projects_list'],separators=(',',':')).encode()).hexdigest()}
    model = {'source': readiness.MODEL_SOURCE, 'thread_id': 'intended-chat', 'turn_id': 'next-turn',
        'server_name': 'golem-local', 'observed_at_ns': NOW-2_000_000_000,
        'marker': marker, 'tools': ['golem_projects_list', 'golem_document_submit']}
    return {'selected': selected, 'target': {'thread_id': 'intended-chat', 'server_name': 'golem-local'},
            'live': live, 'model': model, 'now_ns': NOW, 'required_tools': ('golem_document_submit',)}


class Readiness(unittest.TestCase):
    def check_block(self, expected, data):
        result = readiness.classify(**data)
        self.assertEqual(result['reason'], expected)
        self.assertFalse(result['preparation_allowed'])
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['automatic_retry_allowed'])
        return result

    def test_exact_current_chat_correlation_only_allows_unapproved_preparation(self):
        data = fixture(); before = copy.deepcopy(data)
        result = readiness.classify(**data)
        self.assertEqual(result['state'], 'PREPARATION_READY_NOT_AUTHORIZED')
        self.assertTrue(result['preparation_allowed'])
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['owner_identity_authenticated'])
        self.assertFalse(result['native_work_verified'])
        self.assertEqual(result['stages']['same_chat_model_tools'], 'EXTERNALLY_OBSERVED')
        self.assertEqual(result['next_step'], 'PREPARE_NEW_UNAPPROVED_ACTION_UNDER_EXISTING_CONTRACTS')
        self.assertEqual(data, before)

    def test_disk_configuration_alone_is_not_live_delivery(self):
        data = fixture(); data.update(live=None, model=None)
        result = self.check_block('INTENDED_LIVE_TRANSPORT_NOT_OBSERVED', data)
        self.assertEqual(result['stages']['disk_selection'], 'OBSERVED')
        self.assertEqual(result['stages']['same_chat_model_tools'], 'NOT_OBSERVED')

    def test_absent_or_invalid_selection_is_not_success(self):
        data = fixture(); data['selected'] = None
        self.check_block('DISK_SELECTION_NOT_OBSERVED', data)
        for key in ('config_sha256', 'approval_sha256', 'launcher_sha256'):
            data = fixture(); data['selected'][key] = None
            self.check_block('DISK_SELECTION_INVALID', data)

    def test_wrong_selected_server_is_rejected(self):
        data = fixture(); data['selected']['server_name'] = 'another-server'
        self.check_block('DISK_SELECTION_INVALID', data)

    def test_each_live_pin_and_state_must_match_current_selection(self):
        for key in ('selected_state', 'launcher_sha256', 'approval_sha256', 'plugin_version'):
            with self.subTest(key=key):
                data = fixture(); data['live'][key] = 'different'
                self.check_block('LIVE_SELECTION_MISMATCH', data)

    def test_busy_unknown_or_uninitialized_transport_blocks(self):
        for values in ({'busy': True}, {'busy': None}, {'state': 'UNKNOWN'}, {'state': 'STARTING'}):
            data = fixture(); data['live'].update(values)
            self.check_block('LIVE_TRANSPORT_BUSY_OR_UNCERTAIN', data)

    def test_missing_or_old_or_future_timestamps_never_invent_freshness(self):
        for target, expected in (('live', 'LIVE_OBSERVATION_STALE_OR_UNDATED'),
                                 ('model', 'MODEL_OBSERVATION_STALE_OR_UNDATED')):
            for timestamp in (None, True, NOW+1, NOW-readiness.DEFAULT_MAX_AGE_NS-1):
                with self.subTest(target=target, timestamp=timestamp):
                    data = fixture(); data[target]['observed_at_ns'] = timestamp
                    self.check_block(expected, data)

    def test_fresh_live_status_must_be_after_model_inventory(self):
        data = fixture(); data['model']['observed_at_ns'] = NOW
        self.check_block('LIVE_OBSERVATION_PRECEDES_MODEL', data)

    def test_catalog_notification_without_relist_blocks(self):
        data = fixture()
        data['live']['host_catalog'].update(state='HOST_CATALOG_NOT_RELISTED', requests=0, responses=0,
            current_complete_sha256=None, current_complete_pages=None)
        result = self.check_block('CURRENT_HOST_CATALOG_NOT_OBSERVED', data)
        self.assertEqual(result['stages']['live_connection'], 'CURRENT_RELAY_CHAT_UNCONFIRMED')

    def test_historical_catalog_hash_does_not_qualify_current_generation(self):
        data = fixture(); data['live']['host_catalog']['last_complete_generation'] = 2
        self.check_block('CURRENT_HOST_CATALOG_NOT_OBSERVED', data)

    def test_pending_partial_error_and_missing_catalog_block(self):
        for state in ('HOST_CATALOG_REQUEST_PENDING', 'HOST_CATALOG_PARTIAL_RESPONSE', 'HOST_CATALOG_ERROR_SENT'):
            data = fixture(); data['live']['host_catalog']['state'] = state
            self.check_block('CURRENT_HOST_CATALOG_NOT_OBSERVED', data)
        data = fixture(); data['live']['host_catalog'] = None
        self.check_block('LIVE_CORRELATION_MARKER_NOT_OBSERVED', data)

    def test_host_catalog_cannot_self_claim_model_delivery(self):
        data = fixture(); data['live']['host_catalog']['model_delivery_verified'] = True
        self.check_block('CURRENT_HOST_CATALOG_NOT_OBSERVED', data)

    def test_invalid_page_count_hash_or_counts_fail_closed(self):
        values = ({'current_complete_pages': True}, {'current_complete_pages': 129},
                  {'current_complete_sha256': None}, {'last_complete_sha256': '1'*64},
                  {'responses': 3}, {'requests': True}, {'errors': 3}, {'last_complete_pages': 1})
        for update in values:
            data = fixture(); data['live']['host_catalog'].update(update)
            self.check_block('CURRENT_HOST_CATALOG_NOT_OBSERVED', data)

    def test_forwarded_catalog_and_ready_relay_are_not_model_evidence(self):
        data = fixture(); data['model'] = None
        result = self.check_block('SAME_CHAT_MODEL_DEFINITIONS_NOT_OBSERVED', data)
        self.assertEqual(result['stages']['host_catalog'], 'CURRENT_RESPONSE_FORWARDED_MODEL_UNCONFIRMED')

    def test_same_pid_plan_ownership_and_agent_claim_are_not_definition_observations(self):
        for source in ('SAME_PID', 'PLAN_OWNER', 'AGENT_SUCCESS_CLAIM', 'STANDALONE_PROBE'):
            data = fixture(); data['model']['source'] = source
            self.check_block('MODEL_OBSERVATION_SOURCE_UNSUPPORTED', data)

    def test_wrong_chat_server_and_absent_turn_block(self):
        for key, value in (('thread_id', 'another-chat'), ('server_name', 'another-server'), ('turn_id', '')):
            data = fixture(); data['model'][key] = value
            self.check_block('MODEL_CHAT_OR_TURN_MISMATCH', data)

    def test_marker_from_wrong_transport_or_previous_child_catalog_blocks(self):
        for key, value in (('instance', 'c'*32), ('definition_nonce', 'd'*32),
                           ('child_generation', 1), ('catalog_generation', 4)):
            data = fixture(); data['model']['marker'][key] = value
            self.check_block('MODEL_CORRELATION_MARKER_STALE_OR_WRONG_TRANSPORT', data)

    def test_malformed_and_extended_markers_are_rejected(self):
        for key, value in (('instance', 'non-opaque'), ('child_generation', True),
                           ('catalog_generation', 0), ('definition_nonce', ''), ('claim', 'approved')):
            data = fixture(); data['model']['marker'][key] = value
            self.check_block('MODEL_CORRELATION_MARKER_INVALID', data)

    def test_required_definition_missing_stays_blocked_despite_marker_match(self):
        data = fixture(); data['model']['tools'] = ['golem_projects_list']
        data['live']['definition_tool_count']=1
        data['live']['definition_tools_sha256']=hashlib.sha256(b'["golem_projects_list"]').hexdigest()
        result = self.check_block('REQUIRED_MODEL_TOOL_DEFINITIONS_MISSING', data)
        self.assertEqual(result['observed_tools'], ['golem_projects_list'])

    def test_copied_current_marker_cannot_promote_stale_extra_or_missing_tool_names(self):
        for names in (['golem_projects_list'],
                      ['golem_projects_list','golem_document_submit','golem_execution_request']):
            data = fixture(); data['model']['tools']=names
            self.check_block('MODEL_TOOL_INVENTORY_MISMATCH',data)

    def test_absent_or_malformed_current_tool_inventory_remains_unobserved(self):
        for fields in ({'definition_tool_count':None},{'definition_tool_count':True},
                       {'definition_tools_sha256':None},{'definition_tools_sha256':'not-sha'}):
            data = fixture(); data['live'].update(fields)
            self.check_block('CURRENT_DEFINITION_INVENTORY_NOT_OBSERVED',data)

    def test_definitions_observation_without_expected_preparation_tool_is_not_ready(self):
        data = fixture(); data['required_tools'] = ()
        result = self.check_block('PREPARATION_TOOLS_NOT_SELECTED', data)
        self.assertEqual(result['stages']['same_chat_model_tools'], 'EXTERNALLY_OBSERVED')

    def test_invalid_tool_inventory_does_not_claim_delivery(self):
        for names in (None, ['golem_projects_list']*2, ['shell'], ['golem_x']*257):
            data = fixture(); data['model']['tools'] = names
            self.check_block('MODEL_TOOL_DEFINITIONS_INVALID', data)

    def test_reload_ack_alone_does_not_certify_delivery(self):
        data = fixture(); data.update(model=None, refresh={'state': 'ACKNOWLEDGED', 'attempts': 1})
        self.check_block('SAME_CHAT_MODEL_DEFINITIONS_NOT_OBSERVED', data)

    def test_failed_and_unknown_refresh_preserve_block_even_if_later_definitions_match(self):
        for state in ('FAILED', 'UNKNOWN'):
            data = fixture(); data['refresh'] = {'state': state, 'attempts': 1}
            self.check_block('REFRESH_'+state, data)

    def test_repeated_or_fabricated_attempt_state_blocks(self):
        for value in ({'state': 'ACKNOWLEDGED', 'attempts': 2},
                      {'state': 'NOT_ATTEMPTED', 'attempts': 1},
                      {'state': 'ACKNOWLEDGED', 'attempts': 0},
                      {'state': 'ACKNOWLEDGED', 'attempts': True},
                      {'state': 'REPAIRED', 'attempts': 1}):
            data = fixture(); data['refresh'] = value
            self.check_block('REFRESH_REPEAT_OR_INVALID', data)

    def test_valid_no_refresh_and_ack_allow_separate_matching_evidence(self):
        for value in ({'state': 'NOT_ATTEMPTED', 'attempts': 0}, {'state': 'ACKNOWLEDGED', 'attempts': 1}):
            data = fixture(); data['refresh'] = value
            self.assertTrue(readiness.classify(**data)['preparation_allowed'])

    def test_caller_cannot_extend_diagnostic_window_or_pass_bad_target(self):
        for update in ({'max_age_ns': readiness.DEFAULT_MAX_AGE_NS+1}, {'now_ns': True},
                       {'required_tools': ['golem_x', 'golem_x']},
                       {'target': {'thread_id': 'a', 'server_name': 'golem-local', 'approved': True}}):
            data = fixture(); data.update(update)
            with self.assertRaises(ValueError): readiness.classify(**data)


if __name__ == '__main__':
    unittest.main()
