import copy
import hashlib
import unittest
from pathlib import Path

from capability_audit import Audit
from capability_files import SourceFile
from capability_repository import audit_repository, REQUIRED_SOURCE_PATHS, REVIEWED_DEVELOPMENT_SOURCE_PATHS, source_candidate
from capability_scope_registry import TRACKED_PATHS
from capability_ledger import SCHEMA


class RepositoryScope(unittest.TestCase):
    def ledger(self):
        return dict(schema=SCHEMA,sources=[],observations=[],capabilities=[])

    def test_tracked_development_retains_pinned_review_without_runtime_promotion(self):
        self.assertNotIn('tools/capability_check.py', REQUIRED_SOURCE_PATHS)
        self.assertNotIn('src/cli/main.c', REVIEWED_DEVELOPMENT_SOURCE_PATHS)
        self.assertNotIn('tools/integration_distribution.py', REVIEWED_DEVELOPMENT_SOURCE_PATHS)
        self.assertTrue(all(p.startswith('tools/capability_') for p in REVIEWED_DEVELOPMENT_SOURCE_PATHS))
        self.assertIn('tools/integration_distribution.py', REQUIRED_SOURCE_PATHS)
        self.assertEqual(len(REQUIRED_SOURCE_PATHS), len(set(REQUIRED_SOURCE_PATHS)))
        result = audit_repository(self.ledger(), (), Audit((),()), TRACKED_PATHS,
                                  current_untracked=())
        self.assertIn(('DEVELOPMENT_CONTENT_NOT_REVIEWED', None), result.blockers)

    def test_empty_successful_selected_gate_cannot_certify_repository(self):
        result = audit_repository(self.ledger(), (), Audit((),()), TRACKED_PATHS)
        self.assertFalse(result.inventory_complete)
        self.assertEqual(sum(c=='REPOSITORY_SOURCE_NOT_SELECTED' for c,_ in result.blockers),len(REQUIRED_SOURCE_PATHS))
        self.assertFalse(result.execution_verified)
        self.assertEqual(result.client_e2e,'NOT_RUN')

    def test_private_host_sdk_and_plugin_are_in_scope(self):
        for path in ('src/cli/candidate_host_cli.c','src/common/record_internal.h',
                     'tools/integration_backend.py','bindings/native/bridge.c',
                     'bindings/typescript/index.mjs','plugins/golem/scripts/launcher.py',
                     'plugins/golem/.mcp.json','source_policy.py'):
            self.assertIn(path,REQUIRED_SOURCE_PATHS)
        self.assertFalse(source_candidate('tests/c/cli_integration.py'))

    def test_non_candidate_path_requires_explicit_reviewed_boundary(self):
        from unittest.mock import patch
        from capability_boundary_registry import BOUNDARIES
        path='docs/architecture.md'
        with patch('capability_boundary_registry.BOUNDARIES',tuple(r for r in BOUNDARIES if r[0]!=path)):
            result=audit_repository(self.ledger(),(),Audit((),()),TRACKED_PATHS)
        self.assertIn(('REPOSITORY_BOUNDARY_REVIEW_MISSING',path),result.blockers)

    def test_function_or_file_selection_is_not_full_source_review(self):
        path='src/cli/main.c'; raw=b'int dispatch(void){return 0;}'
        f=SourceFile(path,hashlib.sha256(raw).hexdigest(),raw)
        result=audit_repository(self.ledger(),(f,),Audit((),()),TRACKED_PATHS)
        self.assertIn(('SOURCE_OPERATION_REVIEW_MISSING',path),result.blockers)

    def test_all_header_declarations_reveal_original_sample_omissions(self):
        from capability_public_registry import PUBLIC_HEADERS
        root=Path(__file__).resolve().parents[1]
        files=tuple(SourceFile(r.path,r.sha256,(root/r.path).read_bytes()) for r in PUBLIC_HEADERS)
        result=audit_repository(self.ledger(),files,Audit((),()),TRACKED_PATHS)
        self.assertEqual(sum(c=='PUBLIC_API_NOT_LISTED' for c,_ in result.blockers),344)
        self.assertFalse(any(c=='SOURCE_OPERATION_REVIEW_MISSING' for c,_ in result.blockers))
        self.assertFalse(result.inventory_complete)

    def test_added_and_removed_index_path_cannot_be_hidden(self):
        index=(*TRACKED_PATHS[1:],'src/new.c')
        result=audit_repository(self.ledger(),(),Audit((),()),index)
        self.assertIn(('INDEX_PATH_ADDED','src/new.c'),result.blockers)
        self.assertIn(('INDEX_PATH_REMOVED',TRACKED_PATHS[0]),result.blockers)

    def test_untracked_feature_is_not_invisible_to_index_gate(self):
        result=audit_repository(self.ledger(),(),Audit((),()),TRACKED_PATHS,current_untracked=('tools/new_feature.py',))
        self.assertIn(('UNREVIEWED_NEW_PATH','tools/new_feature.py'),result.blockers)

    def test_explicit_development_name_is_not_content_coverage(self):
        result=audit_repository(self.ledger(),(),Audit((),()),TRACKED_PATHS,current_untracked=('tools/capability_check.py',))
        self.assertIn(('DEVELOPMENT_CONTENT_NOT_REVIEWED',None),result.blockers)

    def test_selected_blocker_is_preserved(self):
        result=audit_repository(self.ledger(),(),Audit((('bad','scope'),),()),TRACKED_PATHS)
        self.assertIn(('SELECTED_INVENTORY_BLOCKED',('bad','scope')),result.blockers)
