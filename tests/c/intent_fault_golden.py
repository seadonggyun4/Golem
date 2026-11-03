"""Offline comparison of fault/race snapshots. No native execution or repair."""
import argparse
import json
from pathlib import Path
from intent_context_golden import read, digest
from intent_schema_golden import decode


def compare(root, logs):
    from jsonschema import Draft202012Validator
    golden = decode((root / 'tests/fixtures/intent/fault-golden.json').read_bytes())
    schema = decode((root / 'docs/schemas/intent-qc-contracts.v1.schema.json').read_bytes())
    definitions = {'intent_observation_events': 'qa-observation',
                   'intent_enrollment_event': 'enrollment-event'}
    results = []
    seen = set()
    for path in sorted(logs.glob('scenario-*.json')):
        item = decode(read(logs, path.name))
        case = item['case']
        if case not in golden['cases'] or case in seen:
            raise ValueError('unknown/duplicate scenario')
        seen.add(case)
        want = golden['cases'][case]
        if item['retries'] != 0 or sorted(item['returncodes']) != want['returncodes']:
            raise ValueError('retry or exit mismatch')
        if not item['files']:
            raise ValueError('missing native transcripts')
        snapshots = []
        for name, sha in item['files'].items():
            raw = read(logs, name)
            if digest(raw) != sha:
                raise ValueError('changed native transcript')
            if name.endswith('.stdout'):
                try:
                    value = decode(raw)
                except (ValueError, UnicodeError):
                    continue  # failed/lost response is not successful JSON evidence
                if isinstance(value, dict) and 'authority_payload_status' in value:
                    snapshots.append(value)
        before, after = item['before'], item['after']
        if before not in snapshots or after not in snapshots:
            raise ValueError('snapshot not backed by native stdout')
        for key, delta in want['delta'].items():
            if after[key] - before[key] != delta:
                raise ValueError('native state delta mismatch: ' + case + '/' + key)
        if 'pending' in want and after['pending'] is not want['pending']:
            raise ValueError('pending state mismatch')
        checked = []
        for value in (before, after):
            for key, definition in definitions.items():
                objects = value.get(key, [])
                if isinstance(objects, dict):
                    objects = [objects]
                for obj in objects:
                    Draft202012Validator({**schema, 'oneOf': [{'$ref': '#/$defs/' + definition}]}).validate(obj)
                    checked.append(definition)
            for obj in value['authority_payloads']:
                tag = obj.get('schema', '')
                if tag in ('golem.intent.qa-acceptance.v1', 'golem.intent.qa-acceptance-prepared.v1'):
                    definition = tag[len('golem.intent.'):-3]
                    Draft202012Validator({**schema, 'oneOf': [{'$ref': '#/$defs/' + definition}]}).validate(obj)
                    checked.append(definition)
            if value['pending'] and (value['authority_payload_status'] != 'NOT_RUN_PENDING' or value['authority_payloads']):
                raise ValueError('pending payload must remain unobserved')
        results.append({'case': case, 'comparison': 'PASS', 'definitions': sorted(set(checked)),
                        'pending_payloads': 'NOT_RUN' if after['pending'] else 'OBSERVED'})
    return {'status': 'PARTIAL' if set(golden['cases']) != seen else 'PASS', 'results': results,
            'missing': sorted(set(golden['cases']) - seen), 'authority_verified': False,
            'scope': 'HISTORICAL_FIXTURE_ONLY'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('logs', type=Path)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    with args.report.open('x') as stream:
        result = {'status': 'FAIL'}
        try:
            result = compare(args.root, args.logs)
        except BaseException as exc:
            result['error'] = str(exc)
            raise
        finally:
            json.dump(result, stream, indent=2)
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
