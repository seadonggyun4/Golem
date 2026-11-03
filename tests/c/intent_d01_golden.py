"""Offline D01 writer-race result check; does not rerun writers or native calls."""
from intent_context_golden import read, digest
from intent_schema_golden import decode


def compare(folder):
    records = {}
    for name, codes in (
        ('registration-race.json', ('AUTHORITY_REGISTRATION_BUSY', 'PLAN_STALE')),
        ('revocation-race.json', ('AUTHORITY_REGISTRATION_BUSY', 'AUTHORITY_REVOKED')),
    ):
        raw = read(folder, name)
        rows = decode(raw)
        if not isinstance(rows, list) or len(rows) != 2 or sum(row[0] == 'OK' for row in rows) != 1:
            raise ValueError('D01 race winner cardinality')
        loser = next(row for row in rows if row[0] != 'OK')
        if loser[0] != 'BLOCKED' or not any(code in loser[1] for code in codes):
            raise ValueError('D01 race refusal mismatch')
        records[name] = digest(raw)
    for lock in ('hold', 'hold-authority'):
        for op in ('register', 'revoke'):
            name = lock + '-' + op + '.json'
            raw = read(folder, name)
            result = decode(raw)
            if result[0] != 'BLOCKED' or 'AUTHORITY_REGISTRATION_BUSY' not in result[1]:
                raise ValueError('D01 held-lock writer not blocked')
            records[name] = digest(raw)
    raw = read(folder, 'result.json')
    if decode(raw) != dict(status='PASS', authority_unchanged=True, locator_unchanged=True, retries=0):
        raise ValueError('D01 preservation assertion mismatch')
    records['result.json'] = digest(raw)
    return dict(comparison='PASS', scope='FIXTURE_ASSERTIONS_ONLY', files=records,
                authority_verified=False, native_schema_equivalence='NOT_APPLICABLE')
