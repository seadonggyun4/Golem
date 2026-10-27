"""Read-only M0 draft/report command. Never edits the ledger or source tree."""
import argparse
import json
import sys

from capability_audit import Audit, audit_ledger, render_markdown
from capability_scope import tracked_scope, compare_scope,untracked_scope
from capability_scope_registry import TRACKED_PATHS
from capability_evidence import inspect_references
from capability_files import read_sources,read_inventory,INVENTORY_PATH
from capability_ledger import SCHEMA, decode_identified_ledger
from capability_profile import Rule, scan_sources
from capability_selected_scan import scan_selected
from capability_connections import connect_inventory, render_connections
from capability_repository import audit_repository, render_repository


def draft_ledger(sources, scan):
    """Generate observations only; classification is explicitly unreviewed."""
    return {'schema': SCHEMA,
        'sources': [{'path': s.path, 'sha256': s.sha256} for s in sources],
        'observations': [dict(id=o.id, kind=o.kind, source_path=o.source_path,
                              entrypoint=o.entrypoint, selector=o.selector) for o in scan.observations],
        'capabilities': []}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--connection-profiles', action='store_true', help='Observe approved D2 closed-set and D4 direct-edge profiles; no transitive coverage claim')
    parser.add_argument('--handler-profiles', action='store_true', help='Check pinned D2/D4 handlers using explicitly selected source bytes')
    parser.add_argument('--source', action='append', default=[])
    parser.add_argument('--evidence', action='append', default=[])
    parser.add_argument('--reviewed-new', action='append', default=[])
    parser.add_argument('--rule', nargs=5, action='append', default=[],
        metavar=('PATH', 'SHA256', 'KIND', 'ENTRYPOINT', 'SUBJECT'))
    parser.add_argument('--ledger', help='Explicit repository-relative ledger path')
    parser.add_argument('--draft', action='store_true', help='Emit observations without inventing reviewed capabilities')
    args = parser.parse_args(argv)
    if args.draft == bool(args.ledger):
        parser.error('select exactly one of --draft or --ledger')
    try:
        paths = list(args.source)
        if args.ledger and args.ledger!=INVENTORY_PATH and args.ledger not in paths:
            paths.append(args.ledger)
        files = read_sources(args.root, paths, reviewed_new=[p for p in args.reviewed_new if p in paths])
        selected = tuple(f for f in files if f.path in args.source)
        rules = tuple(Rule(p, sha, kind, entry, None if subject == '-' else subject)
                      for p, sha, kind, entry, subject in args.rule)
        scan = scan_sources(selected, rules)
        if args.draft:
            print(json.dumps(draft_ledger(selected, scan), ensure_ascii=False, indent=2))
            # Draft generation is never proof of complete scan; retain blockers.
            print(json.dumps({'scan_unresolved': scan.unresolved, 'inventory_complete': False}), file=sys.stderr)
            return 2
        ledger = decode_identified_ledger(read_inventory(args.root).data if args.ledger==INVENTORY_PATH else next(f.data for f in files if f.path == args.ledger))
        scan = scan_selected(ledger, selected, rules)
        evidence = inspect_references(ledger, args.root, args.evidence,
            reviewed_new=[p for p in args.reviewed_new if p in args.evidence])
        result = audit_ledger(ledger, selected, scan, evidence)
        current_index = tracked_scope(args.root)
        scope = compare_scope(TRACKED_PATHS, current_index)
        result = Audit(result.blockers + tuple(('INDEX_PATH_ADDED', p) for p in scope.added)
                       + tuple(('INDEX_PATH_REMOVED', p) for p in scope.removed), result.backlog)
        if args.handler_profiles:
            from capability_handler import inspect_handler
            from capability_handler_registry import HANDLERS
            handler_blockers = []
            for rule in HANDLERS:
                observed = inspect_handler(selected, rule)
                if not observed.linked:
                    handler_blockers.append(('HANDLER_LINK_UNVERIFIED',
                        (rule.handler_path, rule.method, observed.missing, observed.extra, observed.blockers)))
            result = Audit(result.blockers + tuple(handler_blockers), result.backlog)
        connected = connect_inventory(ledger, selected, result)
        result = connected.audit
        print(render_markdown(ledger, result), end='')
        print(render_connections(connected), end='')
        if args.connection_profiles:
            print('\n```json\n' + json.dumps(connected.observations, indent=2) + '\n```')
        repository = audit_repository(ledger, selected, result, current_index,connected.observations,untracked_scope(args.root))
        print('\n' + render_repository(repository), end='')
        return 0 if result.inventory_complete and repository.inventory_complete else 2
    except (ValueError, OSError) as error:
        # Do not expose arbitrary bytes, paths from exceptions or source content.
        print(json.dumps({'status': 'INVALID_INPUT', 'error_type': type(error).__name__}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
