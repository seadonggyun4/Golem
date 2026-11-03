"""Read-only packet/capture comparison; no host invocation and no authority claim."""
import argparse
import json
from pathlib import Path
from intent_context_golden import read, digest
from intent_schema_golden import decode


def compare(root, folder):
    from jsonschema import Draft202012Validator
    schema = decode((root / 'docs/schemas/intent-qc-contracts.v1.schema.json').read_bytes())
    record = decode(read(folder, 'transport.json'))
    # An explicit transcript descriptor, never inferred from a model statement.
    if set(record) != {'kind', 'files', 'returncode', 'expected_operation'}:
        raise ValueError('transport descriptor fields')
    if record['kind'] not in ('NATIVE_HOST', 'MOCK'):
        raise ValueError('transport provenance kind')
    if set(record['files']) != {'packet.json', 'stdout', 'stderr'}:
        raise ValueError('transport members')
    raw = {name: read(folder, name) for name in record['files']}
    for name, value in raw.items():
        if digest(value) != record['files'][name]:
            raise ValueError('transport bytes changed')
    packet = decode(raw['packet.json'])
    Draft202012Validator({**schema, 'oneOf': [{'$ref': '#/$defs/product-host-packet'}]}).validate(packet)
    if packet['operation'] != record['expected_operation']:
        raise ValueError('unexpected host operation')
    for field, definition in (('policy', 'review-host-policy'), ('bundle', 'review-host-bundle'),
                              ('control', 'product-access'), ('material', 'product-material')):
        Draft202012Validator({**schema, 'oneOf': [{'$ref': '#/$defs/' + definition}]}).validate(decode(packet[field].encode()))
    for field in ('policy', 'bundle'):
        if digest(packet[field].encode()) != packet[field + '_sha256']:
            raise ValueError('host input pin mismatch')
    # No accepting a missing response, nonzero exit, mock or arbitrary stdout as native success.
    outcome = 'NOT_RUN' if record['kind'] == 'MOCK' else 'UNKNOWN'
    if record['returncode'] == 0 and raw['stdout']:
        result = decode(raw['stdout'])
        definition = 'qa-assessment' if result.get('schema') == 'golem.intent.qa-assessment.v1' else None
        if definition:
            Draft202012Validator({**schema, 'oneOf': [{'$ref': '#/$defs/' + definition}]}).validate(result)
        outcome = 'SHAPE_OBSERVED' if record['kind'] == 'NATIVE_HOST' else 'NOT_RUN'
    return {'status': 'PARTIAL', 'packet_shape': 'PASS', 'native_result': outcome,
            'kind': record['kind'], 'authority_verified': False,
            'missing': ['independent host invocation/FD/registration evidence and scenario assertion'],
            'packet_sha256': digest(raw['packet.json'])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('logs', type=Path)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    with args.report.open('x') as out:
        result = {'status': 'FAIL'}
        try:
            result = compare(args.root, args.logs)
        except BaseException as exc:
            result['error'] = str(exc)
            raise
        finally:
            json.dump(result, out, indent=2)
    raise SystemExit(1)  # Shape-only evidence never qualifies the host campaign.


if __name__ == '__main__':
    main()
