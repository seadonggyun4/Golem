import copy
import hashlib
import unittest
from dataclasses import replace
from capability_evidence import ReferenceObservation
from capability_audit import audit_ledger, render_markdown
from capability_files import SourceFile
from capability_profile import Observation, Scan
from capability_ledger import observation_identity
from capability_report import draft_ledger
from test_capability_ledger import metadata_sample


def fixture():
    ledger = metadata_sample()
    raw = b'int feature_call(void);'
    source = SourceFile('src/feature.c', hashlib.sha256(raw).hexdigest(), raw)
    ledger['sources'][0]['sha256'] = source.sha256
    obs = ledger['observations'][0]
    obs['id'] = observation_identity(**{k: obs[k] for k in ('kind','source_path','entrypoint','selector')})
    ledger['capabilities'][0]['observation_ids'] = [obs['id']]
    scan = Scan((Observation(**obs),), ())
    return ledger, (source,), scan


class AuditChecks(unittest.TestCase):
    def referenced_fixture(self):
        ledger, sources, scan = fixture()
        cap = ledger['capabilities'][0]
        refs = []
        extra = []
        for kind, locator in (('test_refs','selector'), ('doc_refs','anchor')):
            for ref in cap[kind]:
                raw=b'fixture reference'
                digest=hashlib.sha256(raw).hexdigest()
                ledger['sources'].append({'path':ref['path'],'sha256':digest})
                extra.append(SourceFile(ref['path'],digest,raw))
                refs.append(ReferenceObservation(cap['id'],kind,ref['path'],ref[locator],True,digest,len(raw),None,
                    locator_unverified=False,declaration_line=1,locator_diagnostic=None))
        return ledger,(*sources,*extra),scan,tuple(refs)

    def test_reference_bytes_must_match_reviewed_source_pin(self):
        ledger,sources,scan,refs=self.referenced_fixture()
        refs=(replace(refs[0],observed_sha256='0'*64),*refs[1:])
        self.assertIn(('REFERENCE_SOURCE_DRIFT',(ledger['capabilities'][0]['id'],'test_refs',refs[0].path)),
                      audit_ledger(ledger,sources,scan,refs).blockers)

    def test_explicit_missing_selector_is_not_just_file_scope_evidence(self):
        ledger,sources,scan,refs=self.referenced_fixture()
        refs=(replace(refs[0],locator_unverified=True,declaration_line=None,locator_diagnostic='DECLARATION_NOT_UNIQUE_OR_ABSENT'),*refs[1:])
        self.assertTrue(any(c=='REFERENCE_LOCATOR_UNVERIFIED' for c,_ in audit_ledger(ledger,sources,scan,refs).blockers))

    def test_inventory_is_not_delivery_completion(self):
        ledger, sources, scan, refs = self.referenced_fixture()
        cap = ledger['capabilities'][0]
        cap.update(current_routes=['HOST_INTERNAL'], target_routes=['MCP_READ'])
        result = audit_ledger(ledger, sources, scan, refs)
        self.assertTrue(result.inventory_complete)
        self.assertEqual(result.backlog, (cap['id'],))

    def test_source_drift_added_and_removed(self):
        ledger, sources, scan = fixture()
        for changed in ((), (SourceFile('src/new.c', sources[0].sha256, sources[0].data),),
                        (SourceFile(sources[0].path, '0'*64, b'changed'),)):
            self.assertFalse(audit_ledger(ledger, changed, scan).inventory_complete)

    def test_operation_add_remove_and_unclassified(self):
        ledger, sources, scan = fixture()
        self.assertFalse(audit_ledger(ledger, sources, Scan((), ())).inventory_complete)
        ledger['capabilities'] = []
        self.assertIn(('OPERATION_UNCLASSIFIED', scan.observations[0].id),
                      audit_ledger(ledger, sources, scan).blockers)

    def test_unresolved_never_silenced_by_review(self):
        ledger, sources, scan = fixture()
        result = audit_ledger(ledger, sources, Scan(scan.observations, (('src/feature.c', 'feature_call', 'macro'),)))
        self.assertFalse(result.inventory_complete)

    def test_missing_evidence_and_routes(self):
        ledger, sources, scan = fixture()
        ledger['capabilities'][0].update(test_refs=[], current_routes=[])
        self.assertFalse(audit_ledger(ledger, sources, scan).inventory_complete)

    def test_renderer_escapes_untrusted_text_and_preserves_inputs(self):
        ledger, sources, scan = fixture()
        ledger['capabilities'][0]['id'] = '<img src=x>|\n`fake`'
        before = copy.deepcopy(ledger)
        report = render_markdown(ledger, audit_ledger(ledger, sources, scan))
        self.assertNotIn('<img', report)
        self.assertIn('&#124;', report)
        self.assertEqual(before, ledger)

    def test_draft_never_invents_reviews(self):
        ledger, sources, scan = fixture()
        result = draft_ledger(sources, scan)
        self.assertEqual(result['capabilities'], [])
        self.assertFalse(audit_ledger(result, sources, scan).inventory_complete)


if __name__ == '__main__':
    unittest.main()
