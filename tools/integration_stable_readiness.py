"""Pure readiness classification for opt-in fixed frontend definitions.

The v2 marker identifies a frontend instance/catalog, not its backend epoch.
Fresh backend evidence is required independently after each owner transition.
All inputs are caller-collected observations; none authenticates an owner,
grants a call or releases Work execution HOLD. This module performs no I/O.
"""
import hashlib
import json
import re
from collections.abc import Mapping


MAX_AGE_NS = 300 * 1_000_000_000
MAX_TOOLS = 128
MODEL_SOURCE = 'EXTERNAL_MODEL_DEFINITION_OBSERVATION'
FRONTEND_ABI = 'golem.fixed-tool-catalog.v1'
DIGEST = re.compile(r'[a-f0-9]{64}\Z')
TOOL = re.compile(r'golem_[a-z0-9_]{1,120}\Z')
MARKER = re.compile(r'golem-catalog-v2:([a-f0-9]{32}):([a-f0-9]{64}):([a-f0-9]{32})\Z')


def _match(expression, value):
    return type(value) is str and expression.fullmatch(value) is not None


def _positive(value):
    return type(value) is int and 0 < value < (1 << 63)


def _identifier(value):
    return type(value) is str and 0 < len(value) <= 128 and not any(ord(c) < 32 for c in value)


def _tools(value):
    return type(value) in (list, tuple) and len(value) <= MAX_TOOLS and all(
        _match(TOOL, name) for name in value) and len(set(value)) == len(value)


def _fresh(value, now_ns):
    return _positive(value) and 0 <= now_ns-value <= MAX_AGE_NS


def _canonical_digest(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False)+'\n').encode()).hexdigest()


def _names_digest(value):
    # Matches the relay's observation of full tool names, not catalog bytes.
    return hashlib.sha256(json.dumps(sorted(value), sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _selected(value):
    """Check snapshot consistency, never reread disk or validate native grants."""
    if not isinstance(value, Mapping):
        return None
    selection, catalog = value.get('selection'), value.get('catalog')
    if not isinstance(selection, dict) or not isinstance(catalog, dict):
        return None
    if (set(selection) != {'schema', 'client', 'revision', 'previous_sha256',
            'catalog_sha256', 'adapter_state', 'approval_sha256', 'launcher_sha256'}
            or selection['schema'] != 'golem.stable-selection.v1'
            or selection['client'] not in ('codex', 'claude-desktop')
            or type(selection['revision']) is not int or not 1 <= selection['revision'] <= 256
            or type(selection['adapter_state']) is not str or not selection['adapter_state'].startswith('/')
            or '..' in selection['adapter_state'].split('/')
            or not all(_match(DIGEST, selection[key]) for key in
                       ('catalog_sha256', 'approval_sha256', 'launcher_sha256'))):
        return None
    if ((selection['revision'] == 1 and selection['previous_sha256'] is not None) or
            (selection['revision'] > 1 and not _match(DIGEST, selection['previous_sha256']))):
        return None
    if (set(catalog) != {'schema', 'profile', 'tools', 'tools_sha256'}
            or catalog['schema'] != FRONTEND_ABI
            or catalog['profile'] not in ('read', 'prepare', 'task', 'quality', 'parallel')
            or type(catalog['tools']) is not list or not 0 < len(catalog['tools']) <= MAX_TOOLS):
        return None
    definitions = catalog['tools']
    if not all(type(tool) is dict and type(tool.get('inputSchema')) is dict for tool in definitions):
        return None
    names = [tool.get('name') for tool in definitions]
    if not _tools(names) or names != sorted(names):
        return None
    try:
        selection_sha, catalog_sha = _canonical_digest(selection), _canonical_digest(catalog)
        head_sha = _canonical_digest({'schema':'golem.stable-head.v1', 'client':selection['client'],
            'revision':selection['revision'], 'selection_sha256':selection_sha, 'catalog_sha256':catalog_sha})
        valid = (value.get('is_current') is True and
            value.get('selection_sha256') == selection_sha == value.get('current_head_selection_sha256') and
            value.get('catalog_sha256') == catalog_sha == selection['catalog_sha256'] and
            value.get('head_sha256') == head_sha and catalog['tools_sha256'] == _canonical_digest(definitions))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return None
    return (selection, catalog, names) if valid else None


def correlate_definitions(selected, live, model, now_ns):
    """Correlate a fixed frontend with external chat evidence, never a backend.

    This is useful while a new selection is published but the old backend is
    still live. It cannot report preparation readiness or authorize a refresh.
    The existing exact transition controller and native call gates remain
    responsible for their own decisions.
    """
    if not _positive(now_ns):
        raise ValueError('OBSERVATION_CLOCK')
    result = {'schema':'golem.stable-definition-correlation.v1', 'state':'BLOCKED',
        'correlated':False, 'frontend_bound':False, 'reason':'DISK_SELECTION_NOT_OBSERVED',
        'next_step':'INSPECT_EXACT_STABLE_SELECTION', 'target':None, 'observed_tools':[],
        'frontend_catalog':'NOT_OBSERVED', 'same_chat_model_tools':'NOT_OBSERVED',
        'preparation_allowed':False, 'execution_authorized':False,
        'owner_identity_authenticated':False, 'native_work_verified':False,
        'automatic_retry_allowed':False, 'actual_execution':'HOLD'}

    def block(reason, step):
        result.update(reason=reason, next_step=step)
        return result

    snapshot = _selected(selected)
    if snapshot is None:
        return block('DISK_SELECTION_INVALID_OR_UNOBSERVED', 'INSPECT_EXACT_STABLE_SELECTION')
    selection, catalog, names = snapshot
    if not isinstance(live, Mapping):
        return block('LIVE_BACKEND_NOT_OBSERVED', 'OBSERVE_NEW_BACKEND_STATUS')
    if not _fresh(live.get('observed_at_ns'), now_ns):
        return block('LIVE_OBSERVATION_STALE_OR_UNDATED', 'OBSERVE_NEW_BACKEND_STATUS')
    if (live.get('schema') != 'golem.stable-connection-relay.v1'
            or live.get('frontend_abi') != FRONTEND_ABI):
        return block('LIVE_FRONTEND_ABI_MISMATCH', 'REVIEW_FRONTEND_COMPATIBILITY')
    if (live.get('client') != selection['client']
            or live.get('catalog_sha256') != selected['catalog_sha256']
            or live.get('catalog_tools_sha256') != catalog['tools_sha256']):
        return block('LIVE_SELECTION_OR_CATALOG_MISMATCH', 'REVIEW_EXACT_SELECTED_TRANSITION')
    marker = live.get('definition_marker')
    parsed = MARKER.fullmatch(marker) if type(marker) is str else None
    if parsed is None or parsed.group(1) != live.get('instance') or parsed.group(2) != selected['catalog_sha256']:
        return block('LIVE_FRONTEND_MARKER_INVALID', 'OBSERVE_CURRENT_FRONTEND_STATUS')
    result['frontend_bound'] = True
    frontend = live.get('frontend_catalog')
    if not isinstance(frontend, Mapping):
        return block('FRONTEND_CATALOG_NOT_FORWARDED', 'OBSERVE_FIXED_DEFINITIONS_IN_TARGET_CHAT')
    counts = [frontend.get(key) for key in ('requests', 'responses', 'errors')]
    if (frontend.get('schema') != 'golem.stable-frontend-catalog-observation.v1'
            or frontend.get('state') != 'HOST_CATALOG_RESPONSE_SENT'
            or frontend.get('catalog_sha256') != selected['catalog_sha256']
            or frontend.get('definition_marker') != marker
            or frontend.get('model_delivery_verified') is not False
            or not _match(DIGEST, frontend.get('current_complete_sha256'))
            or not all(type(value) is int and 0 <= value < (1 << 63) for value in counts)
            or not 0 <= counts[2] < counts[1] <= counts[0]):
        return block('FRONTEND_CATALOG_NOT_FORWARDED', 'OBSERVE_FIXED_DEFINITIONS_IN_TARGET_CHAT')
    if (type(live.get('definition_tool_count')) is not int or live['definition_tool_count'] != len(names)
            or live.get('definition_tools_sha256') != _names_digest(names)):
        return block('LIVE_DEFINITION_INVENTORY_MISMATCH', 'OBSERVE_CURRENT_FRONTEND_STATUS')
    result['frontend_catalog'] = 'FIXED_RESPONSE_FORWARDED_MODEL_UNCONFIRMED'
    if not isinstance(model, Mapping) or model.get('source') != MODEL_SOURCE:
        return block('EXTERNAL_MODEL_DEFINITIONS_NOT_OBSERVED', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    target = model.get('target')
    if (not isinstance(target, Mapping) or set(target) != {'thread_id', 'server_name'}
            or not all(_identifier(target[key]) for key in target)
            or model.get('thread_id') != target['thread_id'] or model.get('server_name') != target['server_name']
            or not _identifier(model.get('turn_id'))):
        return block('MODEL_TARGET_OR_TURN_MISMATCH', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    result['target'] = dict(target)
    if not _fresh(model.get('observed_at_ns'), now_ns):
        return block('MODEL_OBSERVATION_STALE_OR_UNDATED', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    if model['observed_at_ns'] > live['observed_at_ns']:
        return block('LIVE_OBSERVATION_PRECEDES_MODEL', 'OBSERVE_NEW_BACKEND_STATUS')
    if model.get('marker') != marker:
        return block('MODEL_FRONTEND_MARKER_MISMATCH', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    if not _tools(model.get('tools')) or _names_digest(model['tools']) != _names_digest(names):
        return block('MODEL_FULL_TOOL_INVENTORY_MISMATCH', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    result.update(state='EXTERNAL_CORRELATION_ONLY', correlated=True,
        reason='FIXED_CHAT_DEFINITIONS_CORRELATED_BACKEND_NOT_ADMITTED',
        next_step='REVIEW_EXACT_TRANSITION_AND_CURRENT_BACKEND_SEPARATELY',
        observed_tools=sorted(model['tools']), same_chat_model_tools='EXTERNALLY_CORRELATED_FIXED_DEFINITIONS')
    return result


def classify(selected, live, model, required_tools, now_ns, refresh=None):
    """Use an exact selected snapshot, fresh status and external chat evidence.

    ``model`` requires source, target={thread_id,server_name}, observed thread_id,
    server_name, turn_id, observed_at_ns, marker (v2 string) and full tool names.
    The target is explicitly selected by the caller, never inferred from a PID.
    ``live`` is stable_relay.status plus a collector timestamp after its reply.
    ACK evidence includes completed_at_ns, target_selection_sha256 and the
    previous_backend_epoch. ACK alone cannot restore readiness: a later status
    must observe the new exact selection and a strictly newer backend epoch.
    No host tools/list repetition is required when the frontend ABI is unchanged.
    """
    if not _positive(now_ns):
        raise ValueError('OBSERVATION_CLOCK')
    if not _tools(required_tools):
        raise ValueError('REQUIRED_TOOL_NAMES')
    result = {'schema':'golem.stable-connection-readiness.v1', 'state':'BLOCKED',
        'reason':'DISK_SELECTION_NOT_OBSERVED', 'next_step':'INSPECT_EXACT_STABLE_SELECTION',
        'stages':{'disk_selection':'NOT_OBSERVED', 'frontend_catalog':'NOT_OBSERVED',
                  'same_chat_model_tools':'NOT_OBSERVED', 'backend_selection':'NOT_OBSERVED'},
        'preparation_allowed':False, 'execution_authorized':False,
        'owner_identity_authenticated':False, 'native_work_verified':False,
        'automatic_retry_allowed':False, 'observation_source':MODEL_SOURCE,
        'required_tools':list(required_tools), 'observed_tools':[], 'target':None,
        'host_relist_required':False, 'actual_execution':'HOLD'}

    def block(reason, step):
        result.update(reason=reason, next_step=step)
        return result

    snapshot = _selected(selected)
    if snapshot is None:
        return block('DISK_SELECTION_INVALID_OR_UNOBSERVED', 'INSPECT_EXACT_STABLE_SELECTION')
    selection, catalog, names = snapshot
    result['stages']['disk_selection'] = 'EXACT_SNAPSHOT_CONSISTENT'
    acknowledged = False
    if refresh is not None:
        if not isinstance(refresh, Mapping):
            return block('REFRESH_EVIDENCE_INVALID', 'PRESERVE_AND_REVIEW_TRANSITION')
        attempts, state = refresh.get('attempts'), refresh.get('state')
        if (type(attempts) is not int or attempts not in (0, 1) or
                state not in ('NOT_ATTEMPTED', 'ACKNOWLEDGED', 'FAILED', 'UNKNOWN') or
                (attempts == 0) != (state == 'NOT_ATTEMPTED')):
            return block('REFRESH_REPEAT_OR_INVALID', 'PRESERVE_AND_REVIEW_TRANSITION')
        if state in ('FAILED', 'UNKNOWN'):
            return block('REFRESH_'+state, 'PRESERVE_AND_REVIEW_TRANSITION')
        acknowledged = state == 'ACKNOWLEDGED'
        if acknowledged and (not _positive(refresh.get('completed_at_ns'))
                or refresh['completed_at_ns'] > now_ns
                or not _positive(refresh.get('previous_backend_epoch'))
                or refresh.get('target_selection_sha256') != selected['selection_sha256']):
            return block('REFRESH_ACK_PROOF_INVALID', 'OBSERVE_NEW_BACKEND_STATUS')

    if not isinstance(live, Mapping):
        return block('LIVE_BACKEND_NOT_OBSERVED', 'OBSERVE_NEW_BACKEND_STATUS')
    if not _fresh(live.get('observed_at_ns'), now_ns):
        return block('LIVE_OBSERVATION_STALE_OR_UNDATED', 'OBSERVE_NEW_BACKEND_STATUS')
    if (live.get('schema') != 'golem.stable-connection-relay.v1'
            or live.get('frontend_abi') != FRONTEND_ABI):
        return block('LIVE_FRONTEND_ABI_MISMATCH', 'REVIEW_FRONTEND_COMPATIBILITY')
    if (live.get('state') != 'READY' or live.get('busy') is not False
            or live.get('failure') is not None or live.get('pending') != 0
            or type(live.get('pending')) is not int or live.get('server_pending') != 0
            or type(live.get('server_pending')) is not int or not _positive(live.get('backend_epoch'))
            or not _positive(live.get('selection_revision'))):
        return block('LIVE_BACKEND_BUSY_OR_UNCERTAIN', 'PRESERVE_AND_INSPECT_TRANSITION')
    exact = {'client':selection['client'], 'selected_state':selection['adapter_state'],
        'selection_revision':selection['revision'], 'selection_sha256':selected['selection_sha256'],
        'head_sha256':selected['head_sha256'], 'approval_sha256':selection['approval_sha256'],
        'launcher_sha256':selection['launcher_sha256'], 'catalog_sha256':selected['catalog_sha256'],
        'catalog_tools_sha256':catalog['tools_sha256']}
    if any(live.get(key) != value for key, value in exact.items()):
        return block('LIVE_SELECTION_OR_CATALOG_MISMATCH', 'REVIEW_EXACT_SELECTED_TRANSITION')
    if acknowledged and (live['observed_at_ns'] <= refresh['completed_at_ns'] or
            live['backend_epoch'] <= refresh['previous_backend_epoch']):
        return block('POST_ACK_BACKEND_PROOF_NOT_OBSERVED', 'OBSERVE_NEW_BACKEND_STATUS')
    correlation = correlate_definitions(selected, live, model, now_ns)
    if correlation['frontend_bound']:
        result['stages']['backend_selection'] = 'CURRENT_EXACT_BACKEND_OBSERVED'
    result['target'] = correlation['target']
    result['observed_tools'] = correlation['observed_tools']
    for stage in ('frontend_catalog', 'same_chat_model_tools'):
        result['stages'][stage] = correlation[stage]
    if not correlation['correlated']:
        return block(correlation['reason'], correlation['next_step'])
    if not required_tools:
        return block('PREPARATION_TOOLS_NOT_SELECTED', 'SELECT_REQUIRED_TYPED_DEFINITIONS')
    if not set(required_tools).issubset(names):
        return block('REQUIRED_MODEL_TOOL_DEFINITIONS_MISSING', 'REVIEW_FIXED_CATALOG_SCOPE')
    result.update(state='PREPARATION_READY_NOT_AUTHORIZED', preparation_allowed=True,
        reason='FIXED_CHAT_DEFINITIONS_AND_FRESH_BACKEND_CORRELATED',
        next_step='PREPARE_UNAPPROVED_EXACT_ACTION_UNDER_EXISTING_CONTRACTS')
    return result
