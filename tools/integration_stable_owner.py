"""Explicit Owner UI controller for the opt-in fixed-catalog broker.

This is an owner-local presentation/control adapter, never a Work or policy
issuer. It loads an exact reviewed broker snapshot and delegates storage,
transition and readiness decisions to that broker. Existing client settings
are not read or written. External model evidence keeps its original timestamp.
"""
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import importlib.util
from itertools import islice
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from types import SimpleNamespace


SCHEMA = 'golem.stable-owner-report.v1'
CONFIG_SCHEMA = 'golem.stable-owner-ui.v1'
CLIENTS = frozenset(('codex', 'claude-desktop'))
MAX_RECORDS = 512
PIN = re.compile(r'[a-f0-9]{64}\Z')
TOOL = re.compile(r'golem_[a-z0-9_]{1,120}\Z')


class StableOwnerError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise StableOwnerError(code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pin(value):
    return type(value) is str and PIN.fullmatch(value) is not None


def _path(value):
    require(isinstance(value, (str, Path)), 'OWNER_PATH_REQUIRED')
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'OWNER_UNSAFE_PATH')
    return path


def _read(path, limit=65536, private=True):
    """Bootstrap only: broker payload and authority checks remain delegated."""
    path = _path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        mask = 0o077 if private else 0o022
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and
                before.st_nlink == 1 and before.st_mode & mask == 0 and
                before.st_size <= limit, 'OWNER_UNSAFE_FILE')
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        require(len(raw) == before.st_size and len(raw) <= limit and all(
            getattr(before, key) == getattr(after, key) for key in
            ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')),
            'OWNER_FILE_CHANGED')
        return raw
    finally:
        os.close(fd)


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'OWNER_DUPLICATE_FIELD')
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode(), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(StableOwnerError('OWNER_NONFINITE_JSON')))
        require(encoded(value) == raw, 'OWNER_NONCANONICAL_JSON')
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise StableOwnerError('OWNER_INVALID_JSON') from error


def _directory(path):
    path = _path(path)
    info = path.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
            stat.S_IMODE(info.st_mode) == 0o700, 'OWNER_PRIVATE_DIRECTORY_REQUIRED')
    return path


def _write_new(path, value):
    raw = encoded(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)
    return {'path': str(path), 'sha256': digest(raw)}


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _finish_record(path, pending):
    # Follow the existing publication durability rule: uncertain final cleanup
    # retains a poison marker best-effort; never rerun the recorded effect.
    os.unlink(path)
    try:
        _sync_directory(path.parent)
    except OSError:
        try:
            _write_new(path, pending)
        except OSError:
            pass
        raise


def _code(error):
    code = getattr(error, 'code', str(error))
    return code if type(code) is str and re.fullmatch('[A-Z][A-Z0-9_]{0,127}', code) else 'OWNER_OPERATION_FAILED'


def _load_bundle(directory, pin):
    """Execute the exact approved bootstrap, then its existing closed loader."""
    directory = _path(directory)
    manifest_raw = _read(directory / 'broker-manifest.json', 16384, private=False)
    require(digest(manifest_raw) == pin, 'OWNER_BUNDLE_PIN_CHANGED')
    manifest = _decode(manifest_raw)
    require(type(manifest) is dict and manifest.get('schema') == 'golem.stable-broker-bundle.v1'
            and type(manifest.get('files')) is dict, 'OWNER_BUNDLE_MANIFEST')
    raw = _read(directory / 'stable_entry.py', 1024 * 1024, private=False)
    require(digest(raw) == manifest['files'].get('stable_entry.py'), 'OWNER_ENTRY_PIN_CHANGED')
    name = '_golem_owner_bootstrap_' + pin
    spec = importlib.util.spec_from_loader(name, loader=None, origin=str(directory / 'stable_entry.py'))
    entry = importlib.util.module_from_spec(spec)
    entry.__file__ = str(directory / 'stable_entry.py')
    exec(compile(raw, entry.__file__, 'exec'), entry.__dict__)
    actual, payloads = entry.verified_bundle(pin)
    require(actual == directory and payloads['stable_entry.py'] == raw, 'OWNER_BUNDLE_CHANGED')
    adapter = entry.module(directory, payloads, 'launcher')
    inventory = _decode(payloads['typed-interface.json'])
    contract = entry.module(directory, payloads, 'stable_contract', {'_VERIFIED_TYPED_INDEX': inventory})
    legacy = entry.module(directory, payloads, 'connection_relay')
    relay = entry.module(directory, payloads, 'stable_relay', {'_VERIFIED_LEGACY': legacy})
    readiness = entry.module(directory, payloads, 'stable_readiness')
    require(callable(getattr(readiness, 'correlate_definitions', None)), 'OWNER_CORRELATION_UNAVAILABLE')
    return SimpleNamespace(entry=entry, adapter=adapter, contract=contract, relay=relay, readiness=readiness)


class StableOwnerController:
    """One explicit action at a time; no polling, selection adoption or replay."""
    def __init__(self, config_path, config_sha256):
        self.config_path = _path(config_path)
        require(_pin(config_sha256), 'OWNER_CONFIG_PIN_REQUIRED')
        self.config_sha256 = config_sha256
        self._lock = threading.Lock()
        self._reviews = {}
        self._uncertain_instances = set()
        # A readable historical ACK cannot prove that its writer observed the
        # final durable completion. In particular unlink+sync and a subsequent
        # poison write may both fail. Reopened UI must not erase that ambiguity.
        self._confirmed_refresh_results = set()
        self.config = self._config()
        self.clients = tuple(sorted(self.config['clients']))

    def _config(self):
        raw = _read(self.config_path)
        require(digest(raw) == self.config_sha256, 'OWNER_CONFIG_CHANGED')
        value = _decode(raw)
        require(type(value) is dict and set(value) == {'schema', 'records_directory', 'clients'}
                and value['schema'] == CONFIG_SCHEMA and type(value['clients']) is dict
                and 0 < len(value['clients']) <= 2 and set(value['clients']) <= CLIENTS,
                'OWNER_CONFIG_FIELDS')
        _directory(value['records_directory'])
        stores = []
        for client, item in value['clients'].items():
            require(type(item) is dict and set(item) == {'bundle_directory', 'bundle_sha256', 'store', 'required_tools'},
                    'OWNER_CLIENT_CONFIG_FIELDS')
            _path(item['bundle_directory'])
            stores.append(str(_path(item['store'])))
            require(_pin(item['bundle_sha256']), 'OWNER_BUNDLE_PIN_REQUIRED')
            names = item['required_tools']
            require(type(names) is list and 0 < len(names) <= 128 and all(
                type(name) is str and TOOL.fullmatch(name) for name in names) and
                names == sorted(set(names)), 'OWNER_REQUIRED_TOOLS')
        require(len(set(stores)) == len(stores), 'OWNER_CLIENT_STORE_ISOLATION')
        return value

    @contextmanager
    def _operation(self, client):
        require(self._lock.acquire(blocking=False), 'OWNER_OPERATION_BUSY')
        try:
            config = self._config()
            require(type(client) is str and client in config['clients'], 'OWNER_CLIENT_NOT_SELECTED')
            item = config['clients'][client]
            modules = _load_bundle(Path(item['bundle_directory']), item['bundle_sha256'])
            selected = modules.contract.inspect(Path(item['store']), client, modules.adapter)
            names = {tool['name'] for tool in selected['catalog']['tools']}
            require(set(item['required_tools']) <= names, 'OWNER_REQUIRED_TOOLS_OUTSIDE_CATALOG')
            yield config, item, modules, selected
        finally:
            self._lock.release()

    def _report(self, client, selected, modules, **values):
        report = {'schema': SCHEMA, 'state': 'OBSERVED_NOT_AUTHORIZED', 'client': client,
            'selected': selected, 'connections': modules.relay.descriptors(client),
            'live': None, 'model_observation': None, 'readiness': None, 'review': None,
            'result': None, 'error': None, 'execution_authorized': False,
            'automatic_retry_allowed': False, 'actual_execution': 'HOLD'}
        report.update(values)
        return report

    def inspect(self, client):
        with self._operation(client) as (_, _, modules, selected):
            return self._report(client, selected, modules)

    def _observe(self, client, item, modules, selected, path, pin):
        model = modules.entry.observation(_path(path), pin)
        marker = modules.relay.parse_definition_marker(model.get('marker'))
        require(marker['catalog_sha256'] == selected['catalog_sha256'], 'OWNER_MODEL_CATALOG_MISMATCH')
        endpoint = modules.relay.endpoint(client, marker['instance'])
        require(endpoint['endpoint_state'] == 'PRESENT', 'OWNER_CONNECTION_CLOSED_OR_UNKNOWN')
        reply = modules.relay.request(client, marker['instance'], 'status', {})
        require(reply.get('ok') is True and type(reply.get('value')) is dict, 'OWNER_STATUS_UNAVAILABLE')
        live = {**reply['value'], 'observed_at_ns': time.time_ns()}
        require(live.get('client') == client and live.get('instance') == marker['instance'], 'OWNER_STATUS_TARGET_MISMATCH')
        require(modules.contract.inspect(Path(item['store']), client, modules.adapter) == selected,
                'OWNER_SELECTION_CHANGED_DURING_OBSERVATION')
        correlation = modules.readiness.correlate_definitions(selected, live, model, time.time_ns())
        return model, live, endpoint, correlation

    def observe(self, client, model_path, model_sha256):
        with self._operation(client) as (config, item, modules, selected):
            model, live, _, _ = self._observe(client, item, modules, selected, model_path, model_sha256)
            refresh = self._refresh_evidence(config, client, live['instance'])
            readiness = modules.readiness.classify(selected, live, model, item['required_tools'], time.time_ns(), refresh)
            return self._report(client, selected, modules, state=readiness['state'],
                live=live, model_observation=model, readiness=readiness)

    def _review(self, kind, client, values):
        value = {'kind': kind, 'client': client, 'config_sha256': self.config_sha256,
                 'reviewed_at_ns': time.time_ns(), **values}
        token = digest(encoded(value))
        value['token'] = token
        self._reviews[token] = copy.deepcopy(value)
        return value

    def review_selection(self, client, path, sha):
        with self._operation(client) as (_, item, modules, selected):
            path = _path(path)
            raw = modules.contract.read(path, modules.contract.SELECTION_LIMIT, modules.adapter)
            require(_pin(sha) and digest(raw) == sha, 'OWNER_SELECTION_PIN_CHANGED')
            candidate = modules.contract.validate_selection(raw, modules.adapter)
            require(candidate['client'] == client and candidate['revision'] == selected['selection']['revision'] + 1
                    and candidate['previous_sha256'] == selected['selection_sha256']
                    and candidate['catalog_sha256'] == selected['catalog_sha256'], 'OWNER_SELECTION_NOT_NEXT')
            modules.adapter.inspect_state(Path(candidate['adapter_state']), client,
                expected_approval_sha256=candidate['approval_sha256'], expected_launcher_sha256=candidate['launcher_sha256'])
            review = self._review('publish', client, {'selection_path': str(path),
                'selection_sha256': sha, 'selection': candidate,
                'expected_head_sha256': selected['head_sha256'],
                'old_selection_sha256': selected['selection_sha256'], 'store': item['store']})
            return self._report(client, selected, modules, state='SELECTION_REVIEW_REQUIRED', review=review)

    def review_refresh(self, client, model_path, model_sha256):
        with self._operation(client) as (config, item, modules, selected):
            model, live, endpoint, correlation = self._observe(client, item, modules, selected, model_path, model_sha256)
            require(correlation.get('correlated') is True, correlation.get('reason', 'OWNER_MODEL_UNCORRELATED'))
            prior = self._refresh_evidence(config, client, live['instance'])
            require(prior is None or prior.get('state') not in ('FAILED', 'UNKNOWN'),
                    'OWNER_PREVIOUS_TRANSITION_UNCERTAIN')
            require(live.get('state') == 'READY' and live.get('busy') is False and live.get('failure') is None
                    and type(live.get('pending')) is int and live['pending'] == 0
                    and type(live.get('server_pending')) is int and live['server_pending'] == 0,
                    'OWNER_CONNECTION_BUSY_OR_UNCERTAIN')
            require(live.get('selection_sha256') != selected['selection_sha256'], 'OWNER_ALREADY_SELECTED')
            # Existing contract validates the old lineage and original approval;
            # it deliberately remains historical, never is_current=True.
            historical = modules.contract.inspect_record(Path(item['store']), client,
                live.get('selection_revision'), live.get('selection_sha256'), modules.adapter)
            require(historical['catalog_sha256'] == selected['catalog_sha256'], 'OWNER_CATALOG_CHANGED')
            review = self._review('refresh', client, {'instance': live['instance'],
                'marker': model['marker'], 'old_selection_sha256': live['selection_sha256'],
                'target_selection_sha256': selected['selection_sha256'],
                'expected_head_sha256': selected['head_sha256'], 'previous_backend_epoch': live['backend_epoch'],
                'descriptor_sha256': endpoint['descriptor_sha256'], 'store': item['store'],
                'model_path': str(_path(model_path)), 'model_sha256': model_sha256})
            return self._report(client, selected, modules, state='TRANSITION_REVIEW_REQUIRED',
                live=live, model_observation=model, readiness=correlation, review=review)

    def _selected_review(self, client, token, kind, modules):
        require(_pin(token) and token in self._reviews, 'OWNER_REVIEW_REQUIRED')
        review = copy.deepcopy(self._reviews[token])
        require(review['kind'] == kind and review['client'] == client and
                review['config_sha256'] == self.config_sha256, 'OWNER_REVIEW_TARGET_CHANGED')
        require(0 <= time.time_ns() - review['reviewed_at_ns'] <= modules.readiness.MAX_AGE_NS,
                'OWNER_REVIEW_STALE')
        return review

    @contextmanager
    def _journal_lock(self, config):
        directory = _directory(config['records_directory'])
        fd = os.open(directory / 'owner.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                    and stat.S_IMODE(info.st_mode) == 0o600, 'OWNER_UNSAFE_JOURNAL_LOCK')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise StableOwnerError('OWNER_JOURNAL_BUSY') from error
            require(len(list(islice(directory.iterdir(), MAX_RECORDS + 1))) <= MAX_RECORDS - 3,
                    'OWNER_JOURNAL_LIMIT')
            yield directory
        finally:
            os.close(fd)

    def _effect(self, config, review, invoke):
        identity = {key: review[key] for key in ('kind', 'client', 'store')}
        identity.update({'selection_sha256': review['selection_sha256']} if review['kind'] == 'publish' else
                        {'instance': review['instance'], 'target_selection_sha256': review['target_selection_sha256']})
        key = digest(encoded(identity))
        with self._journal_lock(config) as directory:
            attempt_path, result_path = directory / ('attempt-' + key + '.json'), directory / ('result-' + key + '.json')
            pending_path = directory / ('pending-' + key + '.json')
            require(not any(os.path.lexists(path) for path in (attempt_path, result_path, pending_path)),
                    'OWNER_EFFECT_ALREADY_ATTEMPTED')
            attempt = {'schema': 'golem.stable-owner-attempt.v1', 'identity': identity,
                'review': review, 'started_at_ns': time.time_ns(), 'automatic_retry_allowed': False}
            # The attempt is durable before any publication/IPC effect. A
            # partial journal write prevents dispatch and is never repaired.
            try:
                attempt_ref = _write_new(attempt_path, attempt)
                pending = {'schema': 'golem.stable-owner-pending.v1', 'identity': identity, 'attempt': attempt_ref}
                _write_new(pending_path, pending)
            except Exception as error:
                return {'state': 'RESULT_UNKNOWN', 'error': _code(error), 'attempt_path': str(attempt_path)}
            try:
                response = invoke()
                blocked = response.get('ok') is False or response.get('state') in ('BLOCKED', 'RESULT_UNKNOWN')
                state = ('RESULT_UNKNOWN' if 'UNKNOWN' in str(response.get('code', '')) or
                         response.get('state') == 'RESULT_UNKNOWN' else 'BLOCKED') if blocked else 'ACKNOWLEDGED'
                error = response.get('code') if blocked else None
            except Exception as caught:
                response, error = None, _code(caught)
                # Once dispatched, an exception is not proof of no effect.
                state = 'RESULT_UNKNOWN'
            result = {'schema': 'golem.stable-owner-result.v1', 'identity': identity,
                'attempt': attempt_ref, 'state': state, 'error': error, 'response': response,
                'completed_at_ns': time.time_ns(), 'previous_backend_epoch': review.get('previous_backend_epoch'),
                'automatic_retry_allowed': False, 'execution_authorized': False}
            try:
                result_ref = _write_new(result_path, result)
                _finish_record(pending_path, pending)
            except Exception as caught:
                if review['kind'] == 'refresh':
                    self._uncertain_instances.add((review['client'], review['instance']))
                return {'state': 'RESULT_UNKNOWN', 'error': _code(caught), 'attempt': attempt_ref,
                        'result_path': str(result_path), 'pending_path': str(pending_path)}
            return {**result, 'record': result_ref}

    def publish(self, client, review_token, approve=False):
        with self._operation(client) as (config, item, modules, selected):
            require(approve is True, 'OWNER_EXACT_PUBLICATION_CONFIRMATION_REQUIRED')
            review = self._selected_review(client, review_token, 'publish', modules)
            require(review['expected_head_sha256'] == selected['head_sha256'] and review['store'] == item['store'],
                    'OWNER_REVIEW_SELECTION_CHANGED')
            result = self._effect(config, review, lambda: modules.contract.publish(Path(item['store']),
                Path(review['selection_path']), review['selection_sha256'], review['expected_head_sha256'], True, modules.adapter))
            self._reviews.pop(review_token, None)
            # No automatic status request or readiness promotion follows a
            # publication. The caller explicitly observes/reviews next.
            published = result['response'] if result['state'] == 'ACKNOWLEDGED' else selected
            return self._report(client, published, modules,
                state='SELECTED_NOT_LIVE_APPLIED' if result['state'] == 'ACKNOWLEDGED' else result['state'],
                result=result, error=result.get('error'))

    def refresh(self, client, review_token, approve=False):
        with self._operation(client) as (config, item, modules, selected):
            require(approve is True, 'OWNER_EXACT_TRANSITION_CONFIRMATION_REQUIRED')
            review = self._selected_review(client, review_token, 'refresh', modules)
            require(review['expected_head_sha256'] == selected['head_sha256'] and review['store'] == item['store'],
                    'OWNER_REVIEW_SELECTION_CHANGED')
            model, live, endpoint, correlation = self._observe(client, item, modules, selected,
                review['model_path'], review['model_sha256'])
            require(correlation.get('correlated') is True, correlation.get('reason', 'OWNER_MODEL_UNCORRELATED'))
            require(endpoint['descriptor_sha256'] == review['descriptor_sha256'] and
                    live.get('definition_marker') == review['marker'] and
                    live.get('selection_sha256') == review['old_selection_sha256'] and
                    live.get('backend_epoch') == review['previous_backend_epoch'] and live.get('state') == 'READY'
                    and live.get('busy') is False and live.get('failure') is None
                    and type(live.get('pending')) is int and live['pending'] == 0
                    and type(live.get('server_pending')) is int and live['server_pending'] == 0,
                    'OWNER_REVIEW_CONNECTION_CHANGED')
            result = self._effect(config, review, lambda: modules.relay.request(client, review['instance'], 'refresh', {
                'expected_selection_sha256': review['old_selection_sha256'],
                'target_selection_sha256': review['target_selection_sha256'],
                'expected_definition_marker': review['marker']}))
            if result['state'] == 'ACKNOWLEDGED':
                self._confirmed_refresh_results.add(result['record']['sha256'])
            self._reviews.pop(review_token, None)
            return self._report(client, selected, modules,
                state='POST_TRANSITION_OBSERVATION_REQUIRED' if result['state'] == 'ACKNOWLEDGED' else result['state'],
                live=live, model_observation=model, result=result, error=result.get('error'))

    def _refresh_evidence(self, config, client, instance):
        if (client, instance) in self._uncertain_instances:
            return {'state': 'UNKNOWN', 'attempts': 1}
        directory = _directory(config['records_directory'])
        entries = list(islice(directory.iterdir(), MAX_RECORDS + 1))
        require(len(entries) <= MAX_RECORDS, 'OWNER_JOURNAL_LIMIT')
        records = []
        for path in sorted(entries):
            if not re.fullmatch(r'attempt-[0-9a-f]{64}\.json', path.name):
                continue
            attempt = _decode(_read(path, 131072))
            identity = attempt.get('identity', {})
            if identity.get('kind') != 'refresh' or identity.get('client') != client or identity.get('instance') != instance:
                continue
            result_path = directory / path.name.replace('attempt-', 'result-', 1)
            pending_path = directory / path.name.replace('attempt-', 'pending-', 1)
            if os.path.lexists(pending_path) or not result_path.exists():
                return {'state': 'UNKNOWN', 'attempts': 1}
            result = _decode(_read(result_path, 1024 * 1024))
            require(result.get('identity') == identity and result.get('attempt') ==
                    {'path': str(path), 'sha256': digest(_read(path, 131072))}, 'OWNER_JOURNAL_RESULT_MISMATCH')
            if result.get('state') != 'ACKNOWLEDGED':
                return {'state': 'UNKNOWN' if result.get('state') == 'RESULT_UNKNOWN' else 'FAILED', 'attempts': 1}
            if digest(_read(result_path, 1024 * 1024)) not in self._confirmed_refresh_results:
                return {'state': 'UNKNOWN', 'attempts': 1,
                        'reason': 'HISTORICAL_ACK_NOT_OBSERVED_IN_THIS_UI'}
            records.append(result)
        if not records:
            return None
        result = max(records, key=lambda item: item['completed_at_ns'])
        return {'state': 'ACKNOWLEDGED', 'attempts': 1, 'completed_at_ns': result['completed_at_ns'],
            'previous_backend_epoch': result['previous_backend_epoch'],
            'target_selection_sha256': result['identity']['target_selection_sha256']}
