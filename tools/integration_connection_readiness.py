"""Pure classification of connection evidence; never an authorization issuer.

The caller collects disk selection, a fresh relay status and independently
observed tool definitions from the intended chat. This module performs no I/O,
reload, tool call or clock read. A marker is correlation evidence, not an
identity credential: copied text, agent claims and a matching PID cannot
establish authenticated owner approval. Even a ready result only permits the
*workflow* to prepare a new, unapproved exact action under existing contracts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Mapping


DIGEST = re.compile(r'[a-f0-9]{64}\Z')
OPAQUE_ID = re.compile(r'[a-f0-9]{32}\Z')
TOOL = re.compile(r'golem_[a-z0-9_]{1,120}\Z')
DEFAULT_MAX_AGE_NS = 300 * 1_000_000_000
MAX_TOOLS = 256
MODEL_SOURCE = 'EXTERNAL_MODEL_DEFINITION_OBSERVATION'


@dataclass(frozen=True)
class DefinitionMarker:
    instance: str
    child_generation: int
    catalog_generation: int
    definition_nonce: str

    @classmethod
    def from_mapping(cls, value: Mapping) -> 'DefinitionMarker':
        if not isinstance(value, Mapping) or set(value) != {
                'instance', 'child_generation', 'catalog_generation', 'definition_nonce'}:
            raise ValueError('DEFINITION_MARKER_FIELDS')
        marker = cls(**value)
        if (not _match(OPAQUE_ID, marker.instance) or
                not _match(OPAQUE_ID, marker.definition_nonce) or
                not _positive(marker.child_generation) or
                not _positive(marker.catalog_generation) or
                marker.child_generation > marker.catalog_generation):
            raise ValueError('DEFINITION_MARKER_VALUE')
        return marker


@dataclass(frozen=True)
class ChatTarget:
    thread_id: str
    server_name: str

    @classmethod
    def from_mapping(cls, value: Mapping) -> 'ChatTarget':
        if not isinstance(value, Mapping) or set(value) != {'thread_id', 'server_name'}:
            raise ValueError('CHAT_TARGET_FIELDS')
        result = cls(**value)
        if not _identifier(result.thread_id) or not _identifier(result.server_name):
            raise ValueError('CHAT_TARGET_VALUE')
        return result


def _match(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def _positive(value):
    return type(value) is int and 0 < value <= (1 << 63) - 1


def _identifier(value):
    return type(value) is str and 0 < len(value) <= 128 and not any(ord(c) < 32 for c in value)


def _tool_names(value):
    return (type(value) in (tuple, list) and len(value) <= MAX_TOOLS and
            all(_match(TOOL, name) for name in value) and len(set(value)) == len(value))


def _fresh(value, now_ns, max_age_ns):
    return _positive(value) and 0 <= now_ns - value <= max_age_ns


def _catalog_current(value, marker):
    if not isinstance(value, Mapping):
        return False
    integers = ('requests', 'responses', 'errors', 'list_changed_notifications_sent')
    if not all(type(value.get(key)) is int and 0 <= value[key] <= (1 << 63) - 1
               for key in integers):
        return False
    pages = value.get('current_complete_pages')
    return (value.get('schema') == 'golem.host-tool-catalog-observation.v1' and
            value.get('state') == 'HOST_CATALOG_RESPONSE_SENT' and
            value.get('model_delivery_verified') is False and
            value.get('child_generation') == marker.child_generation and
            value.get('catalog_generation') == marker.catalog_generation and
            value.get('last_complete_generation') == marker.catalog_generation and
            _match(DIGEST, value.get('current_complete_sha256')) and
            value.get('last_complete_sha256') == value['current_complete_sha256'] and
            type(pages) is int and 1 <= pages <= 128 and
            value.get('last_complete_pages') == pages and
            value['errors'] <= value['responses'] <= value['requests'] and
            value['responses'] >= pages)


def classify(*, selected: Mapping | None, target: Mapping,
             live: Mapping | None = None, model: Mapping | None = None,
             refresh: Mapping | None = None, now_ns: int,
             required_tools=(), max_age_ns: int = DEFAULT_MAX_AGE_NS) -> dict:
    """Return bounded readiness facts from evidence collected by the caller.

    ``selected`` is the current validated ``selected_connection`` result.
    ``live`` is the selected relay's status with an explicit ``observed_at_ns``
    and ``definition_nonce`` (and generation fields, or its ``host_catalog``).
    ``definition_tools_sha256``/``definition_tool_count`` must describe the
    current complete catalog's original tool names (sorted canonical JSON).
    ``model`` contains source, exact thread/server/turn, observation time, parsed
    marker and tool names observed in that chat's model tool definitions. It is
    externally observed metadata, not a signed host/owner attestation.

    All times are explicit epoch nanoseconds from one observation workflow. The
    diagnostic freshness bound does not renew any plan, lease or authorization.
    A caller must not fill absent observations from a plan, shared PID, expected
    result, another chat, or a freshly started stand-alone probe.
    """
    chat = ChatTarget.from_mapping(target)
    if not _positive(now_ns) or not _positive(max_age_ns) or max_age_ns > DEFAULT_MAX_AGE_NS:
        raise ValueError('OBSERVATION_CLOCK_OR_BOUND')
    if not _tool_names(required_tools):
        raise ValueError('REQUIRED_TOOL_NAMES')
    result = {
        'schema': 'golem.connection-readiness.v1',
        'target': asdict(chat),
        'state': 'BLOCKED',
        'stages': {'disk_selection': 'NOT_OBSERVED', 'live_connection': 'NOT_OBSERVED',
                   'host_catalog': 'NOT_OBSERVED', 'same_chat_model_tools': 'NOT_OBSERVED'},
        'preparation_allowed': False,
        'execution_authorized': False,
        'owner_identity_authenticated': False,
        'native_work_verified': False,
        'automatic_retry_allowed': False,
        'observation_source': MODEL_SOURCE,
        'required_tools': list(required_tools),
        'observed_tools': [],
        'next_step': 'INSPECT_CURRENT_DISK_SELECTION',
        'reason': 'DISK_SELECTION_NOT_OBSERVED',
    }

    def blocked(reason, next_step):
        result.update(reason=reason, next_step=next_step)
        return result

    if not isinstance(selected, Mapping):
        return result
    if (selected.get('server_name') != chat.server_name or
            not all(_match(DIGEST, selected.get(key)) for key in
                    ('config_sha256', 'approval_sha256', 'launcher_sha256')) or
            not _identifier(selected.get('package_version')) or
            type(selected.get('adapter_state')) is not str or
            not selected['adapter_state'].startswith('/')):
        return blocked('DISK_SELECTION_INVALID', 'INSPECT_CURRENT_DISK_SELECTION')
    result['stages']['disk_selection'] = 'OBSERVED'

    if refresh is not None:
        if not isinstance(refresh, Mapping):
            return blocked('REFRESH_EVIDENCE_INVALID', 'PRESERVE_AND_REVIEW_REFRESH_RESULT')
        attempts, state = refresh.get('attempts'), refresh.get('state')
        if (type(attempts) is not int or attempts not in (0, 1) or
                state not in ('NOT_ATTEMPTED', 'ACKNOWLEDGED', 'FAILED', 'UNKNOWN') or
                (attempts == 0) != (state == 'NOT_ATTEMPTED')):
            return blocked('REFRESH_REPEAT_OR_INVALID', 'PRESERVE_AND_REVIEW_REFRESH_RESULT')
        if state in ('FAILED', 'UNKNOWN'):
            return blocked('REFRESH_'+state, 'PRESERVE_AND_REVIEW_REFRESH_RESULT')

    if not isinstance(live, Mapping):
        return blocked('INTENDED_LIVE_TRANSPORT_NOT_OBSERVED', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    if not _fresh(live.get('observed_at_ns'), now_ns, max_age_ns):
        return blocked('LIVE_OBSERVATION_STALE_OR_UNDATED', 'OBSERVE_CURRENT_RELAY_STATUS')
    if live.get('state') != 'READY' or live.get('busy') is not False:
        return blocked('LIVE_TRANSPORT_BUSY_OR_UNCERTAIN', 'PRESERVE_AND_INSPECT_TRANSPORT')
    if (live.get('selected_state') != selected['adapter_state'] or
            live.get('launcher_sha256') != selected['launcher_sha256'] or
            live.get('approval_sha256') != selected['approval_sha256'] or
            live.get('plugin_version') != selected['package_version']):
        return blocked('LIVE_SELECTION_MISMATCH', 'USE_SUPPORTED_RECONNECT_THEN_REOBSERVE')
    catalog = live.get('host_catalog')
    generation = catalog if isinstance(catalog, Mapping) else live
    try:
        marker = DefinitionMarker.from_mapping({
            'instance': live.get('instance'),
            'child_generation': generation.get('child_generation'),
            'catalog_generation': generation.get('catalog_generation'),
            'definition_nonce': live.get('definition_nonce'),
        })
    except ValueError:
        return blocked('LIVE_CORRELATION_MARKER_NOT_OBSERVED', 'OBSERVE_CURRENT_RELAY_STATUS')
    result['stages']['live_connection'] = 'CURRENT_RELAY_CHAT_UNCONFIRMED'
    if not _catalog_current(catalog, marker):
        return blocked('CURRENT_HOST_CATALOG_NOT_OBSERVED', 'USE_SUPPORTED_HOST_RELIST_THEN_REOBSERVE')
    result['stages']['host_catalog'] = 'CURRENT_RESPONSE_FORWARDED_MODEL_UNCONFIRMED'

    if not isinstance(model, Mapping):
        return blocked('SAME_CHAT_MODEL_DEFINITIONS_NOT_OBSERVED', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    if model.get('source') != MODEL_SOURCE:
        return blocked('MODEL_OBSERVATION_SOURCE_UNSUPPORTED', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    if (model.get('thread_id') != chat.thread_id or model.get('server_name') != chat.server_name or
            not _identifier(model.get('turn_id'))):
        return blocked('MODEL_CHAT_OR_TURN_MISMATCH', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    if not _fresh(model.get('observed_at_ns'), now_ns, max_age_ns):
        return blocked('MODEL_OBSERVATION_STALE_OR_UNDATED', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    # The live observation is collected after the model inventory. An older
    # live status cannot demonstrate the marker still names the current child.
    if model['observed_at_ns'] > live['observed_at_ns']:
        return blocked('LIVE_OBSERVATION_PRECEDES_MODEL', 'OBSERVE_CURRENT_RELAY_STATUS')
    try:
        observed_marker = DefinitionMarker.from_mapping(model.get('marker'))
    except ValueError:
        return blocked('MODEL_CORRELATION_MARKER_INVALID', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    if observed_marker != marker:
        return blocked('MODEL_CORRELATION_MARKER_STALE_OR_WRONG_TRANSPORT', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    if not _tool_names(model.get('tools')):
        return blocked('MODEL_TOOL_DEFINITIONS_INVALID', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    result['observed_tools'] = sorted(model['tools'])
    count, inventory_digest = live.get('definition_tool_count'), live.get('definition_tools_sha256')
    if type(count) is not int or not 0 < count <= MAX_TOOLS or not _match(DIGEST, inventory_digest):
        return blocked('CURRENT_DEFINITION_INVENTORY_NOT_OBSERVED', 'OBSERVE_CURRENT_RELAY_STATUS')
    observed_digest = hashlib.sha256(json.dumps(result['observed_tools'],
        ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
    if count != len(result['observed_tools']) or inventory_digest != observed_digest:
        return blocked('MODEL_TOOL_INVENTORY_MISMATCH', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    result['stages']['live_connection'] = 'EXTERNALLY_CORRELATED_WITH_INTENDED_CHAT'
    result['stages']['same_chat_model_tools'] = 'EXTERNALLY_OBSERVED'
    if not required_tools:
        return blocked('PREPARATION_TOOLS_NOT_SELECTED', 'SELECT_EXPECTED_PREPARATION_DEFINITIONS')
    if not set(required_tools).issubset(model['tools']):
        return blocked('REQUIRED_MODEL_TOOL_DEFINITIONS_MISSING', 'OBSERVE_INTENDED_CHAT_DEFINITIONS')
    result.update(state='PREPARATION_READY_NOT_AUTHORIZED', preparation_allowed=True,
                  reason='CURRENT_CHAT_DEFINITIONS_CORRELATED',
                  next_step='PREPARE_NEW_UNAPPROVED_ACTION_UNDER_EXISTING_CONTRACTS')
    return result
