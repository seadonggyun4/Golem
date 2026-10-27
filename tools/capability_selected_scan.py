"""Separate selected evidence bytes from operation extraction without dropping sources.

Only referenced Markdown/test files can be evidence-only. Production code always
reaches the extractor. This does not exempt any implementation dependency.
"""
from capability_profile import Scan, scan_sources
from capability_ledger import validate_observation_ids


def scan_selected(ledger, sources, rules):
    validate_observation_ids(ledger)
    # Validate the complete supplied batch before role separation (including bounds,
    # duplicate paths and raw hashes); evidence is not a boundary bypass.
    scan_sources(sources, ())
    pins = {v['path']: v['sha256'] for v in ledger['sources']}
    references = {r['path'] for c in ledger['capabilities']
                  for key in ('test_refs', 'doc_refs') for r in c[key]}
    operation_paths = {r.path for r in rules}
    operation_paths.update(o['source_path'] for o in ledger['observations'])
    selected, problems = [], []
    for source in sources:
        path = source.path
        evidence = (path.startswith('docs/') and path.endswith('.md') or
                    path.startswith('tests/') or path.startswith('tools/test_'))
        if evidence and path in references and path not in operation_paths:
            import hashlib
            if pins.get(path) != source.sha256 or hashlib.sha256(source.data).hexdigest() != source.sha256:
                problems.append((path, None, 'EVIDENCE_SOURCE_DRIFT'))
        else:
            selected.append(source)
    scan = scan_sources(tuple(selected), rules)
    from capability_public import scan_public_headers
    from capability_public_registry import PUBLIC_HEADERS
    observations=list(scan.observations); unresolved=list(scan.unresolved)
    public=scan_public_headers(sources,PUBLIC_HEADERS)
    observations.extend(public.observations)
    problems.extend(public.unresolved)
    from capability_source_role_registry import SOURCE_ROLES
    from capability_source_roles import source_role_cli_scan
    role_scan=source_role_cli_scan(sources,SOURCE_ROLES)
    from capability_callbacks import scan_callbacks
    from capability_callback_registry import CALLBACKS
    callbacks=scan_callbacks(sources,CALLBACKS)
    from capability_domains import inspect_domains
    from capability_domain_registry import DOMAINS
    domains,domain_scan=inspect_domains(sources,ledger,DOMAINS)
    # Identical facts from independent approved profiles share one identity.
    # A conflicting identity is never silently overwritten.
    merged={o.id:o for o in observations+list(role_scan.observations)+list(callbacks.observations)}
    for o in domain_scan.observations:
        if o.id in merged and merged[o.id]!=o:raise ValueError("DOMAIN_OBSERVATION_CONFLICT")
        merged[o.id]=o
    from capability_surface import observe_surface
    from capability_surface_registry import SURFACES
    surface,_=observe_surface(sources,ledger,SURFACES)
    for o in surface.observations:
        if o.id in merged and merged[o.id]!=o:raise ValueError("SURFACE_OBSERVATION_CONFLICT")
        merged[o.id]=o
    from capability_publication import scan_publication
    from capability_publication_registry import PUBLICATION
    publication=scan_publication(sources,PUBLICATION)
    for o in publication.observations:
        if o.id in merged and merged[o.id]!=o:raise ValueError('PUBLICATION_OBSERVATION_CONFLICT')
        merged[o.id]=o
    return Scan(tuple(merged.values()),
                tuple(unresolved)+tuple(problems)+role_scan.unresolved+callbacks.unresolved+domain_scan.unresolved+surface.unresolved+publication.unresolved)
