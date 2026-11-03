"""Offline QC7 transcript comparison; never launches native or opens a Work.

Only explicitly supplied fixture logs are read. A passing checkpoint is historical
fixture evidence, never current product authorization or proof of human identity.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
from intent_schema_golden import decode

LIMIT = 32 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(folder, name):
    if Path(name).name != name:
        raise ValueError('non-local transcript member')
    path = folder / name
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
        raise ValueError('non-regular or oversized transcript')
    raw = path.read_bytes()
    if len(raw) > LIMIT:
        raise ValueError('oversized transcript')
    return raw


def collect(root, logs):
    from jsonschema import Draft202012Validator
    schema_raw = (root / 'docs/schemas/intent-qc-contracts.v1.schema.json').read_bytes()
    schema = decode(schema_raw)
    golden_raw = (root / 'tests/fixtures/intent/context-golden.json').read_bytes()
    golden = decode(golden_raw)
    Draft202012Validator.check_schema(schema)
    validators = {name: Draft202012Validator({**schema, 'oneOf': [{'$ref': '#/$defs/' + name}]})
                  for name in schema['$defs']}
    by_schema = {}
    for name, shape in schema['$defs'].items():
        for branch in shape.get('oneOf', [shape]):
            tag = branch.get('properties', {}).get('schema', {}).get('const')
            if tag:
                by_schema[tag] = name
    observed = set()
    shapes = []

    def visit(value, location, depth=0):
        if depth > 64:
            raise ValueError('nested transcript limit')
        if isinstance(value, str):
            if value.startswith('{') or value.startswith('['):
                try:
                    nested = decode(value.encode())
                except (ValueError, UnicodeError):
                    return
                visit(nested, location + '/embedded', depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, location + '/' + str(index), depth + 1)
        elif isinstance(value, dict):
            name = by_schema.get(value.get('schema'))
            if value.get('schema_version') == 3 and value.get('operation') in ('resume', 'finalize'):
                name = 'completion-request'
            if value.get('type') == 'intent-qa-observation':
                name = 'qa-observation'
            if value.get('type') == 'intent-enrollment':
                name = 'enrollment-event'
            if name:
                errors = sorted(error.message for error in validators[name].iter_errors(value))
                shapes.append({'definition': name, 'location': location, 'errors': errors})
                observed.add(name)
            for key, child in value.items():
                visit(child, location + '/' + key, depth + 1)

    checkpoints = []
    seen = set()
    for path in sorted(logs.glob('context-*.json')):
        marker = decode(read(logs, path.name))
        name = marker['checkpoint']
        if name not in golden['checkpoints'] or name in seen:
            raise ValueError('unknown/duplicate checkpoint')
        seen.add(name)
        expected = golden['checkpoints'][name]
        stem = marker['stem']
        files = {}
        for suffix in ('request.json', 'stdout', 'stderr', 'meta.json'):
            filename = stem + '.' + suffix
            raw = read(logs, filename)
            if digest(raw) != marker['sha256'][suffix]:
                raise ValueError('transcript hash mismatch')
            files[suffix] = raw
        meta = decode(files['meta.json'])
        request = decode(files['request.json'])
        if meta['returncode'] != 0 or meta['fault'] or request['op'] != expected['operation']:
            raise ValueError('checkpoint is not the expected successful native call')
        for source, sha in marker['source_sha256'].items():
            if source not in golden['sources'] or digest((root / source).read_bytes()) != sha:
                raise ValueError('fixture producer drift')
        if set(marker['source_sha256']) != set(golden['sources']):
            raise ValueError('incomplete fixture producer pins')
        output = decode(files['stdout'])
        for pointer, want in expected['equals'].items():
            actual = output
            for component in pointer.split('/'):
                actual = actual[component]
            if type(actual) is not type(want) or actual != want:
                raise ValueError('checkpoint result mismatch: ' + name + '/' + pointer)
        visit(request, name + '/request')
        visit(output, name + '/result')
        checkpoints.append({'checkpoint': name, 'comparison': 'PASS', 'stdout_sha256': digest(files['stdout'])})
    missing = sorted(set(golden['checkpoints']) - seen)
    missing_shapes = sorted(set(schema['$defs']) - observed)
    shape_failures = [item for item in shapes if item['errors']]
    return {'status': 'FAIL' if shape_failures else 'PARTIAL' if missing or missing_shapes else 'PASS',
            'schema_sha256': digest(schema_raw), 'golden_sha256': digest(golden_raw),
            'checkpoints': checkpoints, 'shapes': shapes, 'missing_checkpoints': missing,
            'unobserved_definitions': missing_shapes, 'unobserved_status': 'NOT_RUN',
            'authority_verified': False, 'scope': 'HISTORICAL_DISPOSABLE_FIXTURE_ONLY'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('logs', type=Path)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    with args.report.open('x', encoding='utf-8') as stream:
        report = {'status': 'FAIL', 'authority_verified': False}
        try:
            report = collect(args.root.resolve(), args.logs.resolve())
        except BaseException as exc:
            report['error'] = type(exc).__name__ + ': ' + str(exc)
            raise
        finally:
            json.dump(report, stream, indent=2)
            stream.write('\n')
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
