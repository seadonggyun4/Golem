"""M0 inventory reconciliation. Never a runtime authorization or product PASS.

Pure comparison: callers supply the selected-source inventory and fresh profile
scan. No self-certification from ledger declarations, no file discovery.
"""
from dataclasses import dataclass
from capability_ledger import validate_observation_ids, metadata_blockers


@dataclass(frozen=True)
class Audit:
    blockers: tuple
    backlog: tuple

    @property
    def inventory_complete(self):
        return not self.blockers


def audit_ledger(ledger, sources, scan, reference_observations=()):
    validate_observation_ids(ledger)
    blockers = list(metadata_blockers(ledger))
    actual = {s.path: s.sha256 for s in sources}
    if len(actual) != len(sources):
        raise ValueError('DUPLICATE_SOURCE')
    recorded = {s['path']: s['sha256'] for s in ledger['sources']}
    for path in sorted(actual.keys() - recorded.keys()):
        blockers.append(('SOURCE_NOT_LISTED', path))
    for path in sorted(recorded.keys() - actual.keys()):
        blockers.append(('SOURCE_NOT_SCANNED', path))
    for path in sorted(actual.keys() & recorded.keys()):
        if actual[path] != recorded[path]:
            blockers.append(('SOURCE_DRIFT', path))
    fresh = {o.id: (o.kind, o.source_path, o.entrypoint, o.selector) for o in scan.observations}
    if len(fresh) != len(scan.observations):
        raise ValueError('DUPLICATE_OBSERVATION')
    prior = {o['id']: (o['kind'], o['source_path'], o['entrypoint'], o['selector'])
             for o in ledger['observations']}
    for identity in sorted(fresh.keys() - prior.keys()):
        blockers.append(('OPERATION_NOT_LISTED', identity))
    for identity in sorted(prior.keys() - fresh.keys()):
        blockers.append(('OPERATION_NOT_OBSERVED', identity))
    for identity in sorted(prior.keys() & fresh.keys()):
        if prior[identity] != fresh[identity]:
            blockers.append(('OBSERVATION_MISMATCH', identity))
    for path, entrypoint, reason in scan.unresolved:
        blockers.append(('SCAN_UNRESOLVED', (path, entrypoint, reason)))
    linked = set()
    backlog = []
    for cap in ledger['capabilities']:
        linked.update(cap['observation_ids'])
        if not cap['observation_ids']:
            blockers.append(('CAPABILITY_WITHOUT_OBSERVATION', cap['id']))
        if not cap['current_routes'] or not cap['target_routes']:
            blockers.append(('ROUTE_UNSPECIFIED', cap['id']))
        for kind, locator in (('test_refs', 'selector'), ('doc_refs', 'anchor')):
            for ref in cap[kind]:
                evidence = [r for r in reference_observations if r.capability_id == cap['id']
                            and r.kind == kind and r.path == ref['path'] and r.locator == ref[locator]]
                if len(evidence) != 1 or not evidence[0].file_bytes_verified:
                    blockers.append(('REFERENCE_BYTES_UNVERIFIED', (cap['id'], kind, ref['path'])))
                    continue
                observed = evidence[0]
                if (ref['path'] not in recorded or
                        observed.observed_sha256 != recorded[ref['path']]):
                    blockers.append(('REFERENCE_SOURCE_DRIFT', (cap['id'], kind, ref['path'])))
                if ref[locator] is not None and observed.locator_unverified:
                    blockers.append(('REFERENCE_LOCATOR_UNVERIFIED', (cap['id'], kind, ref['path'], ref[locator])))
        if not cap['test_refs'] or not cap['doc_refs']:
            blockers.append(('EVIDENCE_REFERENCES_MISSING', cap['id']))
        if set(cap['target_routes']) & {'MCP_READ','MCP_REVIEWED_ACTION'} and (set(cap['target_routes']) - set(cap['current_routes']) or cap['implementation'] != 'IMPLEMENTED'):
            backlog.append(cap['id'])
    for identity in sorted(prior.keys() - linked):
        blockers.append(('OPERATION_UNCLASSIFIED', identity))
    if not actual or not fresh:
        blockers.append(('EMPTY_SCOPE', 'no exhaustive coverage'))
    return Audit(tuple(blockers), tuple(backlog))


def _cell(value):
    # Render all ledger data as text; never raw HTML or Markdown links.
    import html
    return html.escape(str(value), quote=True).replace('|', '&#124;').replace('`', '&#96;').replace('\r', ' ').replace('\n', ' ')


def render_markdown(ledger, audit):
    validate_observation_ids(ledger)
    lines = ['# MCP capability inventory', '',
             'Selected inventory: ' + ('COMPLETE' if audit.inventory_complete else 'INCOMPLETE'),
             '', 'This compares only the explicitly selected scope; it is not repository-wide coverage, execution, authorization or product PASS.', '',
             '| Capability | Implementation | Current routes | Target routes | Review |',
             '| --- | --- | --- | --- | --- |']
    for cap in ledger['capabilities']:
        lines.append('| ' + ' | '.join(_cell(v) for v in (cap['id'], cap['implementation'],
            ', '.join(cap['current_routes']), ', '.join(cap['target_routes']), cap['review_status'])) + ' |')
    lines += ['', '## Observed entrypoints', '', '| Kind | Source | Entrypoint | Selector |', '| --- | --- | --- | --- |']
    for obs in ledger['observations']:
        lines.append('| ' + ' | '.join(_cell(obs[k]) for k in ('kind', 'source_path', 'entrypoint', 'selector')) + ' |')
    lines += ['', '## Blockers', '']
    lines += ['- ' + _cell(reason) + ': ' + _cell(target) for reason, target in audit.blockers]
    lines += ['', '## Delivery backlog', '']
    lines += ['- ' + _cell(identity) for identity in audit.backlog]
    return '\n'.join(lines) + '\n'
