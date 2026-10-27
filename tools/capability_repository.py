"""Repository scope obligations, independent of the selected sample gate.

Index names are metadata, never input-read authority. Required paths below are
derived from the fixed reviewed index, not a filesystem walk. Selected functions
do not discharge file-wide obligations. Public header coverage means declarations
only; native operation schemas and implementations remain separate obligations.
"""
from dataclasses import dataclass

from capability_audit import _cell
from capability_profile import scan_sources
from capability_scope import compare_scope
from capability_scope_registry import TRACKED_PATHS
from capability_development_registry import DEVELOPMENT_PATHS, DEVELOPMENT_REVIEWS
from capability_public import scan_public_headers
from capability_public_registry import PUBLIC_HEADERS


# Candidate source horizon, not an exhaustive exclusion policy. Other tracked
# paths still need explicit boundary review below; filename heuristics never
# exempt a surface from the final repository gate.
def source_candidate(path):
    return (path.startswith(('src/', 'include/')) or
            path.startswith('tools/') and not path.startswith('tools/test_') and path.endswith(('.py','.c','.h')) or
            path.startswith('bindings/') and not any(part in ('tests','test_bridge.c') for part in path.split('/'))
            and path.endswith(('.c','.h','.py','.mjs','.d.ts')) or
            path.startswith('plugins/') and path.endswith(('.py','.json','SKILL.md')) or
            path in ('source_policy.py','conanfile.py','CMakeLists.txt','CMakePresets.json','pyproject.toml'))


# Explicit product additions retain full-file review after they enter the Git index.
REVIEWED_SOURCE_ADDITIONS = ('tools/integration_reads.py','tools/integration_read_resources.py','tools/integration_read_views.py','tools/integration_preparations.py','tools/integration_prepare_builders.py','tools/integration_task_actions.py','tools/integration_quality_actions.py','tools/integration_quality_reads.py','tools/integration_helper_contract.py','tools/integration_parallel_actions.py','tools/integration_parallel_reads.py','tools/integration_parallel_hosts.py','tools/integration_parallel_preparations.py','tools/integration_feature_profiles.py','tools/integration_distribution.py','tools/integration_distribution_entry.py','tools/integration_owner_maintenance.py','plugins/golem/skills/golem-work/SKILL.md','plugins/golem/skills/golem-work/agents/openai.yaml','plugins/golem/skills/golem-work/references/profiles.md')
# Development analysis has its own pinned content review and explicit boundary
# roles. Tracking it must neither promote it into runtime MCP nor drop a product
# addition's existing surface review. Keep the combined horizon unique.
REVIEWED_DEVELOPMENT_SOURCE_PATHS = frozenset(
    p for p, _, _, role in DEVELOPMENT_REVIEWS
    if p in DEVELOPMENT_PATHS and p.startswith('tools/capability_')
    and role in ('M0_STATIC_ANALYSIS', 'M0_REVIEW_METADATA'))
REQUIRED_SOURCE_PATHS = tuple(dict.fromkeys((
    *(p for p in TRACKED_PATHS if source_candidate(p) and p not in REVIEWED_DEVELOPMENT_SOURCE_PATHS),
    *REVIEWED_SOURCE_ADDITIONS)))


@dataclass(frozen=True)
class RepositoryAudit:
    required_sources: tuple
    selected_required_sources: tuple
    public_observations: tuple
    blockers: tuple
    execution_verified: bool = False
    client_e2e: str = 'NOT_RUN'

    @property
    def inventory_complete(self):
        return not self.blockers


def audit_repository(ledger, sources, selected_audit, current_index, profiles=None,current_untracked=None,development_sources=()):
    from capability_ledger import validate_observation_ids
    validate_observation_ids(ledger)
    scan_sources(sources, ())
    difference = compare_scope(TRACKED_PATHS, current_index)
    available = {s.path:s for s in sources}
    blockers = [('SELECTED_INVENTORY_BLOCKED', b) for b in selected_audit.blockers]
    blockers.extend(('INDEX_PATH_ADDED', p) for p in difference.added)
    blockers.extend(('INDEX_PATH_REMOVED', p) for p in difference.removed)
    from capability_development_registry import DEVELOPMENT_PATHS, DEVELOPMENT_REVIEWS,DEVELOPMENT_REVIEWS
    from capability_development import inspect_development
    dev_blockers=inspect_development(development_sources,DEVELOPMENT_REVIEWS) if development_sources else (("DEVELOPMENT_CONTENT_NOT_REVIEWED",None),)
    blockers.extend(dev_blockers)
    if current_untracked is None:
        blockers.append(('UNTRACKED_SCOPE_NOT_OBSERVED','untracked names must also be reconciled'))
    else:
        compare_scope(current_untracked,current_untracked)
        blockers.extend(('UNREVIEWED_NEW_PATH',p) for p in sorted(set(current_untracked)-set(DEVELOPMENT_PATHS)-set(REVIEWED_SOURCE_ADDITIONS)))

    for path in REQUIRED_SOURCE_PATHS:
        if path not in available:
            blockers.append(('REPOSITORY_SOURCE_NOT_SELECTED', path))
    referenced={r['path'] for c in ledger['capabilities'] for field in ('test_refs','doc_refs') for r in c[field]}
    operation_paths={o['source_path'] for o in ledger['observations']}
    recorded={s['path']:s['sha256'] for s in ledger['sources']}
    # Only already-reviewed, pinned, explicitly selected evidence files can use
    # the existing evidence-only role. All other exclusions require review.
    evidence_only={p for p in referenced if p in available and p not in operation_paths and
                   (p.startswith(('docs/','tests/','tools/test_'))) and
                   recorded.get(p)==available[p].sha256}
    from capability_boundary_registry import BOUNDARIES
    boundaries={p:(role,why) for p,role,why in BOUNDARIES}
    if len(boundaries)!=len(BOUNDARIES):raise ValueError('DUPLICATE_BOUNDARY')
    if set(boundaries)&set(REQUIRED_SOURCE_PATHS):raise ValueError('SOURCE_CANNOT_BE_BOUNDARY_EXCLUSION')
    if any(not role or not why for role,why in boundaries.values()):raise ValueError('UNREVIEWED_BOUNDARY')
    for path in sorted(set(TRACKED_PATHS)-set(REQUIRED_SOURCE_PATHS)-evidence_only-set(boundaries)):
        blockers.append(('REPOSITORY_BOUNDARY_REVIEW_MISSING',path))
    from capability_boundaries import inspect_boundaries
    from capability_boundary_registry import BOUNDARY_CONTRACTS
    boundary_errors,_=inspect_boundaries(sources,BOUNDARY_CONTRACTS)
    blockers.extend(boundary_errors)
    public = scan_public_headers(sources, PUBLIC_HEADERS)
    blockers.extend(('PUBLIC_HEADER_UNRESOLVED', value) for value in public.unresolved)
    declared_ids = {o['id'] for o in ledger['observations']}
    for observation in public.observations:
        if observation.id not in declared_ids:
            blockers.append(('PUBLIC_API_NOT_LISTED', (observation.source_path, observation.entrypoint)))
    full_header_paths = {r.path for r in PUBLIC_HEADERS if r.path in available and
                         available[r.path].sha256 == r.sha256}
    full_header_paths.difference_update(v[0] for v in public.unresolved)
    from capability_source_roles import observe_source_roles
    from capability_source_role_registry import SOURCE_ROLES
    reviewed_dependencies={r.path for r in observe_source_roles(sources,SOURCE_ROLES,profiles,ledger)
                           if r.file_surface_reviewed and not r.blockers}
    from capability_surface import observe_surface
    from capability_surface_registry import SURFACES
    surface_scan,surface_reviewed=observe_surface(sources,ledger,SURFACES)
    blockers.extend(('WHOLE_SOURCE_UNVERIFIED',v) for v in surface_scan.unresolved)
    reviewed_dependencies.update(surface_reviewed)
    # Only the explicit whole-file surface review establishes implementation
    # file review. Do not silently treat a selected function as the entire file.
    for path in sorted(set(REQUIRED_SOURCE_PATHS) & available.keys() - full_header_paths - reviewed_dependencies):
        blockers.append(('SOURCE_OPERATION_REVIEW_MISSING', path))
    # A ledger can include untracked development code, but it cannot make it
    # source-reviewed merely by listing its bytes or putting it in test_refs.
    for path in sorted(available.keys() - set(TRACKED_PATHS)):
        if source_candidate(path) and (path not in REVIEWED_SOURCE_ADDITIONS or path not in reviewed_dependencies):
            blockers.append(('NEW_SOURCE_OPERATION_REVIEW_MISSING', path))
    return RepositoryAudit(REQUIRED_SOURCE_PATHS,
        tuple(p for p in REQUIRED_SOURCE_PATHS if p in available), public.observations, tuple(blockers))


def render_repository(result):
    lines = ['# M0 repository scope reconciliation', '',
        'Repository inventory: ' + ('COMPLETE' if result.inventory_complete else 'INCOMPLETE'), '',
        f'Candidate source surfaces: {len(result.required_sources)}; explicitly selected: {len(result.selected_required_sources)}. Other tracked paths still require explicit boundary review.',
        f'Public declarations observed in selected headers: {len(result.public_observations)}.',
        'This is static inventory reconciliation, never native execution, authority or product acceptance. Client E2E: NOT_RUN.', '',
        '## Required sources', '', '| Source | Selected |', '| --- | --- |']
    selected = set(result.selected_required_sources)
    lines.extend('| '+_cell(p)+' | '+('YES' if p in selected else 'NO')+' |' for p in result.required_sources)
    lines.extend(('', '## Blockers', ''))
    lines.extend('- '+_cell(code)+': '+_cell(value) for code,value in result.blockers)
    return '\n'.join(lines)+'\n'
