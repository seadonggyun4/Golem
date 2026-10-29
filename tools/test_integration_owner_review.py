"""Disposable fixtures only; native admission and Desktop UI are not executed."""
from unittest.mock import patch
import integration_contract as c
import integration_owner_review as review
import integration_preparations as prep
import unittest
import test_integration_m2 as fixture

class OwnerReview(unittest.TestCase):
    for name in ('setUp','observed','capture','run_call','draft','plan_args','owner_api','approve','query','expect','inventory','save_policy','adapter'):
        locals()[name]=getattr(fixture.Preparations,name)
    def export(self,result,**kwargs):
        args={'project_id':'p','work_id':'a',**self.plan_args(result)}
        with patch.object(self.api,'_read',self.observed):
            return review.export_candidate(self.api,args,self.owner_policy,'new-action',self.root/'candidate',**kwargs)
    def prepare_review(self):
        result=self.draft();api,_=self.owner_api(result['plan']['payload']['action'])
        self.owner_policy=api.policy
        return result
    def test_export_candidate_only(self):
        result=self.prepare_review();before=self.owner_policy.path.read_bytes();work=self.inventory()
        output=self.export(result,approve_review=True)
        action=c.decode((self.root/'candidate/action.json').read_bytes())
        self.assertEqual(action,result['plan']['payload']['action'])
        self.assertEqual(self.owner_policy.path.read_bytes(),before);self.assertEqual(work,self.inventory())
        self.assertFalse(output['policy_applied']);self.assertFalse(output['execution_authorized'])
        self.expect('OWNER_REVIEW_DESTINATION',lambda:self.export(result,approve_review=True))
    def test_consent_stale_instance_loss(self):
        result=self.prepare_review();self.expect('OWNER_REVIEW_REQUIRED',lambda:self.export(result))
        self.status['sequence']+=1
        self.expect('OBSERVATION_STALE',lambda:self.export(result,approve_review=True))
        self.status['sequence']-=1;prep.initialize(self.api)
        self.expect('PREPARATION_INSTANCE_OR_REFERENCE',lambda:self.export(result,approve_review=True))
        self.assertFalse((self.root/'candidate').exists())
    def test_attachment_cannot_add_authority(self):
        result=self.prepare_review()
        self.expect('ACTION_APPROVAL_SCOPE',lambda:self.export(result,approve_review=True,native_attachment={}))
        self.assertFalse((self.root/'candidate').exists())
    def test_existing_action_id_and_revoked_policy_block(self):
        result=self.prepare_review()
        args={'project_id':'p','work_id':'a',**self.plan_args(result)}
        self.expect('DUPLICATE_ACTION',lambda:review.export_candidate(self.api,args,self.owner_policy,'reviewed',self.root/'candidate',approve_review=True))
        self.owner_policy.path.write_bytes(self.owner_policy.path.read_bytes()+b' ')
        self.expect('MUTATION_POLICY_CHANGED',lambda:self.export(result,approve_review=True))
        self.assertFalse((self.root/'candidate').exists())
    def test_changed_basis_blocks_even_with_consistent_sequence(self):
        result=self.prepare_review();self.following['document_generation']+=1
        self.expect('PREPARATION_STALE',lambda:self.export(result,approve_review=True))
        self.assertFalse((self.root/'candidate').exists())
    def test_io_failure_is_preserved_not_repaired(self):
        result=self.prepare_review()
        original=review.records.save
        def fail(path,data,**kw):
            if path.name=='policy-candidate.json':raise OSError('fixture failure')
            return original(path,data,**kw)
        with patch.object(review.records,'save',fail):
            with self.assertRaises(OSError):self.export(result,approve_review=True)
        self.assertTrue((self.root/'candidate/action.json').exists())
        self.assertFalse((self.root/'candidate/review.json').exists())
        self.expect('OWNER_REVIEW_DESTINATION',lambda:self.export(result,approve_review=True))
