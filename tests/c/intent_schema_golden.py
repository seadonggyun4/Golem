"""Opt-in lexical/shape/native comparison. Not a QA acceptance evaluator.

Never import this from production. Context-dependent vectors stay NOT_RUN until
executed by their actual QC7 fixture; shape success cannot promote that status.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError('duplicate key: ' + key)
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('probe', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    # A missing optional dependency is a failure, never a silent skip/PASS.
    from jsonschema import Draft202012Validator
    schema = decode((args.root / 'docs/schemas/intent-qc-contracts.v1.schema.json').read_bytes())
    Draft202012Validator.check_schema(schema)
    folder = args.root / 'tests/fixtures/intent/schema-golden'
    manifest = decode((folder / 'manifest.json').read_bytes())
    covered = {case['definition'] for case in manifest['cases'] if case.get('definition')}
    if covered != set(schema['$defs']) or covered != set(manifest['required_definitions']):
        raise ValueError('schema/corpus coverage drift')
    if len({case['id'] for case in manifest['cases']}) != len(manifest['cases']):
        raise ValueError('duplicate golden identity')
    for name, expected in manifest['source_sha256'].items():
        if hashlib.sha256((args.root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('native source changed; review expectations: ' + name)
    report = {'status': 'IN_PROGRESS', 'cases': [], 'authority_verified': False}
    # Exclusive creation preserves prior results, including interrupted runs.
    with args.report.open('x', encoding='utf-8') as output:
        try:
            for case in manifest['cases']:
                path = folder / case['file']
                if path.parent != folder or path.name != case['file']:
                    raise ValueError('non-local golden path')
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != case['sha256']:
                    raise ValueError('golden bytes changed: ' + case['id'])
                definition = case.get('definition')
                if definition:
                    validator = Draft202012Validator({**schema, 'oneOf': [{'$ref': '#/$defs/' + definition}]})
                    try:
                        accepted = validator.is_valid(decode(raw))
                    except (ValueError, UnicodeError):
                        accepted = False
                    if accepted != case['shape_accept']:
                        raise AssertionError('shape mismatch: ' + case['id'])
                item = {'id': case['id'], 'native': 'NOT_RUN', 'shape': 'PASS' if definition else 'NOT_APPLICABLE'}
                if case['native_probe']:
                    # Fixed allowlist: never run mutable QC7 operations here.
                    if case['native_probe'] not in ('policy', 'request', 'completion', 'identity', 'json'):
                        raise ValueError('invalid probe')
                    completed = subprocess.run([str(args.probe.resolve()), case['native_probe']],
                        input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
                    result = decode(completed.stdout)
                    if result['accepted'] != case['native_accept']:
                        raise AssertionError('native mismatch: ' + case['id'])
                    if 'digest' in case and result['digest'] != case['digest']:
                        raise AssertionError('identity mismatch: ' + case['id'])
                    item['native'] = 'PASS'
                report['cases'].append(item)
            report['status'] = 'PARTIAL' if any(x['native'] == 'NOT_RUN' for x in report['cases']) else 'PASS'
        except BaseException as error:
            report['status'] = 'FAIL'
            report['error'] = type(error).__name__ + ': ' + str(error)
            raise
        finally:
            json.dump(report, output, indent=2)
            output.write('\n')


if __name__ == '__main__':
    main()
