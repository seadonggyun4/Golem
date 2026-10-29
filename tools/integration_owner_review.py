"""Owner-host API for immutable candidates, deliberately absent from MCP.

Requires the live M2 service; never resurrects plans or applies policies.
The owner host supplies selections, independently of untrusted draft content.
"""
import copy
from pathlib import Path
import integration_contract as c
import integration_registry as r
import integration_preparations as prep
import integration_prepare_builders as builders
import integration_mutation_contract as actions
import integration_transfer as transfer
import execution_record as records


class FirstActionDraft:
    """Unapproved builder, never a D4 Policy or dispatch authority.

    A D2-only project has no existing D4 actions. Keep D4's minimum-one rule:
    only the finished candidate (after appending the owner selection) is
    validated as D4. The empty intermediate value is never installed or served.
    """
    def __init__(self, selected_transfer):
        c.require(isinstance(selected_transfer,transfer.Transfer),'OWNER_REVIEW_D2_REQUIRED')
        self.transfer=selected_transfer
        self.registry=selected_transfer.registry
        self.path=selected_transfer.path
        self.digest=selected_transfer.digest

    def current(self):
        self.transfer.current()
        return {'schema':'golem.integration-mutations.v1',
                'transfer_policy':{'path':str(self.path),'sha256':self.digest},
                'actions':[],'producer':actions.producer()}

    def authorize(self,entry):
        # Reuse the exact existing D4 path/scope authorization, not a second
        # implementation. This builder exposes no action() or dispatch method.
        return actions.Policy.authorize(self,entry)


def export_candidate(service,args,policy,action_id,destination,*,approve_review=False,native_attachment=None):
    c.require(approve_review is True,'OWNER_REVIEW_REQUIRED')
    c._validate(args,prep.SCHEMAS['plan_read']);c._validate(action_id,c.ID)
    c.require(service._lock.acquire(blocking=False),'SERVICE_BUSY')
    try:
        with service.registry.locked():
            scope=service.transfer.scope(args['project_id'],args['work_id'],'plan_read')
            c.require(policy.transfer.digest==service.transfer.digest,'PREPARATION_POLICY_BINDING')
            baseline=policy.current()
            c.require(all(e['action_id']!=action_id for e in baseline['actions']),'DUPLICATE_ACTION')
            c.require(len(baseline['actions'])<32,'OWNER_REVIEW_ACTION_LIMIT')
            plan=prep.load(service,scope,args);payload=plan['payload']
            c.require(payload['kind']=='DRAFT_ACTION' and not payload['questions'],'OWNER_REVIEW_DRAFT_REQUIRED')
            c.require(payload['entry_review']['tool'] not in ('helper_execute','candidate_request','workspace_request'),'OWNER_REVIEW_SEPARATE_EFFECTS')
            project,observed,basis=prep.observe(service,scope,args['work_id']);prep.compare_basis(plan,basis)
            envelope=copy.deepcopy(payload['action'])
            c.require(c.sha(c.encoded(envelope))==payload['action_sha256'],'PREPARATION_ACTION_CHANGED')
            c.require(envelope['approval'] is None,'OWNER_REVIEW_DRAFT_APPROVAL')
            envelope['approval']=copy.deepcopy(native_attachment)
            entry={**payload['entry_review'],'action_id':action_id,'project_id':args['project_id']}
            request=actions.native_action(entry,envelope)
            builders.validate_observed(entry,envelope,request,observed)
            destination=Path(destination)
            c.require(destination.is_absolute() and not destination.exists() and not destination.is_symlink(),'OWNER_REVIEW_DESTINATION')
            parent=r.real_path(str(destination.parent));service.registry._private(parent)
            c.require(destination.parent==parent,'OWNER_REVIEW_DESTINATION')
            c.require(not destination.is_relative_to(Path(project['root'])) and not destination.is_relative_to(service.registry.root),'OWNER_REVIEW_OUTPUT_SCOPE')
            raw=c.encoded(envelope)
            entry['action']={'path':str(destination/'action.json'),'sha256':c.sha(raw)}
            c._validate(entry,actions.ENTRY);policy.authorize(entry)
            candidate=copy.deepcopy(baseline);candidate['actions'].append(entry);actions.validate(candidate)
            _,_,current=prep.observe(service,scope,args['work_id']);prep.compare_basis(plan,current)
            prep.load(service,scope,args)
            c.require(policy.current()==baseline,'MUTATION_POLICY_CHANGED');actions.native_action(entry,envelope)
            candidate_raw=c.encoded(candidate)
            review={'schema':'golem.owner-action-review.v1','plan_id':args['plan_id'],'plan_sha256':args['plan_sha256'],
                    'basis':basis,'action_id':action_id,'base_policy_sha256':policy.digest,
                    'base_policy_kind':'D2_FIRST_ACTION_DRAFT' if isinstance(policy,FirstActionDraft) else 'EXISTING_D4',
                    'candidate_policy_sha256':c.sha(candidate_raw),'action_sha256':c.sha(raw),
                    'execution_authorized':False,'approval_created':False,'policy_applied':False,
                    'native_admission':'NOT_RUN','live_source_scan':'NOT_RUN','automatic_retry_allowed':False}
            destination.mkdir(mode=0o700)
            # IO failure leaves partial evidence; no overwrite, repair or retry.
            records.save(destination/'action.json',raw)
            records.save(destination/'policy-candidate.json',candidate_raw)
            records.save(destination/'review.json',c.encoded(review))
            return review
    finally:
        service._lock.release()
