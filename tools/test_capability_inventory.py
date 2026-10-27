"""Repository static fixtures only: no native process or client invocation."""
import hashlib
import unittest
from dataclasses import replace
from pathlib import Path
from capability_files import SourceFile
from capability_ledger import decode_identified_ledger
from capability_selected_scan import scan_selected
from capability_sample_registry import SOURCES, RULES

class ReviewedInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.ledger=decode_identified_ledger((root/'docs/mcp-m0-observations.json').read_bytes())
        cls.sources=tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in SOURCES)

    def test_every_observed_dispatch_is_classified(self):
        scan=scan_selected(self.ledger,self.sources,RULES)
        observed={o.id for o in scan.observations}
        self.assertEqual(observed,{o['id'] for o in self.ledger['observations']})
        self.assertEqual(observed,{i for c in self.ledger['capabilities'] for i in c['observation_ids']})
        self.assertTrue(any(o.entrypoint=="command-path" and o.selector=="research cohort observe" for o in scan.observations))
        self.assertTrue(any(o.entrypoint=="golem_agent_clock.read" for o in scan.observations))
        # Complete branch classification must not erase unresolved implementation.
        self.assertTrue(scan.unresolved)

    def test_root_work_and_noop_are_not_generic_execution(self):
        caps={c['id']:c for c in self.ledger['capabilities']}
        self.assertIn('--noop',caps['cli.route.run']['rationale'])
        self.assertIn('history/record',caps['cli.route.work']['rationale'])
        self.assertEqual(caps['cli.dispatch.doctor.admission']['target_routes'],['OWNER_ONLY'])

    def test_historical_report_projection_is_a_write_path(self):
        caps={c['id']:c for c in self.ledger['capabilities']}
        for name in ('cli.dispatch.completion.report','cli.dispatch.reentry.report'):
            self.assertEqual(caps[name]['target_routes'],['MCP_REVIEWED_ACTION'])
            self.assertIn('NATIVE_WRITE',caps[name]['effects'])
            self.assertIn('project=true',caps[name]['rationale'])

    def test_reviewed_potential_effects_remain_separate_from_execution(self):
        from capability_effects import inspect_effects
        from capability_effect_registry import EFFECT_REVIEWS
        self.assertFalse(inspect_effects(self.ledger,EFFECT_REVIEWS))
        self.assertFalse(any('UNVERIFIED' in c['effects'] for c in self.ledger['capabilities']))
        # Read-only Work inspection can still publish CLI presentation bytes.
        cap=next(c for c in self.ledger['capabilities'] if c['id']=='cli.dispatch.document.inspect')
        self.assertIn('NATIVE_WRITE',cap['effects'])
        self.assertIn('--output-mode full',cap['constraints']['notes'])

    def test_new_branch_without_review_pin_blocks(self):
        changed=[]
        for f in self.sources:
            if f.path=='src/cli/workflow_template.c':
                raw=f.data.replace(b'"list"',b'"new-command"')
                f=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
            changed.append(f)
        scan=scan_selected(self.ledger,tuple(changed),RULES)
        self.assertIn(('src/cli/workflow_template.c','golem_cli_workflow_template','SOURCE_REVIEW_DRIFT'),scan.unresolved)

    def test_supporting_production_code_stays_unresolved(self):
        scan=scan_selected(self.ledger,self.sources,RULES)
        self.assertIn(('tools/integration_backend.py',None,'UNREGISTERED_SOURCE'),scan.unresolved)
        self.assertNotIn(('docs/agent-session.md',None,'UNREGISTERED_SOURCE'),scan.unresolved)

if __name__=='__main__': unittest.main()
