"""Finite feature ceilings. Packaging/profile selection never grants authority."""
import copy
import integration_contract as c

NAMES=('read','prepare','task','quality','parallel')
READ=('projects_list','work_inspect','history_read','context_get','handoff_prepare','evidence_read','completion_check',
      'workflow_read','template_read','role_read','session_read','binding_read','document_read','context_read',
      'discovery_read','events_read','journal_read','profile_read','diagnostic_read','native_validate','report_read',
      'approval_read','reentry_read','artifact_read','usage_read','revision_read','configuration_read','bundle_read',
      'proof_read','research_read','cost_read','execution_read','candidate_read','inventory_read')
PREP=('inputs_prepare','action_prepare','contract_prepare','plan_read','parallel_prepare','merge_prepare')
OWNER_PREP=('approved_action_prepare','action_confirm')
BASE_ACTIONS=('session_claim','session_begin','session_resume','session_reconcile','session_submit','document_submit','execution_request')
TASK_ACTIONS=('session_start','session_heartbeat','session_reject_output','binding_attach','role_enroll','role_assess',
 'completion_finalize','completion_report','reentry_decide','reentry_report','document_project','work_create','context_publish',
 'discovery_snapshot','profile_register','run_link','work_noop_run','adapter_noop_run','lineage_store','approval_request')
QUALITY_ACTIONS=('evidence_import','proof_publish','research_request','research_export','cost_inbox_reconcile','helper_execute','execution_verify')
PARALLEL_ACTIONS=('inventory_capture','candidate_request','workspace_request')
UNIMPLEMENTED=('TASK_DAG_SCHEDULER','TYPED_EDGE_EVIDENCE_ACCEPTANCE','RESOURCE_RECEIVER_BROKER','MERGE_QUEUE',
 'INTEGRATION_WORKSPACE_AND_FRESH_QA','TARGET_REF_CAS_BROKER','MERGE_PUBLICATION_RECEIPT')


def definition(name):
    c.require(name in NAMES,'FEATURE_PROFILE_UNKNOWN')
    domains={'read':READ,'prepare':(*READ,*PREP),'task':(*READ,*PREP,*OWNER_PREP,*BASE_ACTIONS,*TASK_ACTIONS),
        'quality':(*READ,*PREP,*OWNER_PREP,*QUALITY_ACTIONS,'execution_request','approval_request'),
        'parallel':(*READ,*PREP,*OWNER_PREP,*PARALLEL_ACTIONS,'workspace_read','context_publish')}
    return {'schema':'golem.integration-feature-profile.v1','profile':name,
        'family':'D2' if name in ('read','prepare') else 'D4','tools':sorted(set(domains[name])),
        'authority':'INTERSECTION_WITH_CURRENT_OWNER_POLICY_ONLY','grants_created':False,
        'resources_enabled_by_default':False,'helper_enabled_by_default':False,'parallel_host_enabled_by_default':False,
        'required_contracts':['D1_LOCAL_HOST','D2_DISCLOSURE']+(['D4_EXACT_ACTION'] if name not in ('read','prepare') else []),
        'conditional_contracts':{'external_files':'M1_EXPLICIT_RESOURCE','helper_execute':'M4_SEPARATE_EXACT_EFFECTS',
            'candidate_request/workspace_request':'M5_SEPARATE_NATIVE_HOST_AND_TERMINATION'},
        'effects':'PER_TOOL_NATIVE_CONTRACT_NOT_INFERRED_FROM_PROFILE',
        'implementation_required':list(UNIMPLEMENTED),'installation':'NOT_RUN','activation':'NOT_RUN',
        'client_e2e':'NOT_RUN','work_completion_verified':False}


class Scoped:
    def __init__(self,service,profile):
        self.service=service;self.profile=definition(profile)

    def tools(self):
        return sorted(set(self.service.tools()) & set(self.profile['tools']))

    def call(self,name,args):
        c.require(name in self.profile['tools'],'FEATURE_PROFILE_SCOPE')
        c.require(name in self.service.tools(),'FEATURE_OWNER_SCOPE')
        result=self.service.call(name,args)
        if name=='projects_list':
            # Restrict integration discovery metadata only. Native/Work action
            # replies and immutable result bytes pass through unchanged.
            c.require(isinstance(result,dict) and isinstance(result.get('projects'),list),'FEATURE_DISCOVERY_CONTRACT')
            result=copy.deepcopy(result)
            for project in result['projects']:
                project['tools']=[tool for tool in project['tools'] if tool in self.profile['tools']]
                for resource in project.get('read_resources',[]):
                    for file in resource['files']:
                        file['tools']=[tool for tool in file['tools'] if tool in self.profile['tools']]
                    resource['files']=[file for file in resource['files'] if file['tools']]
                project['read_resources']=[resource for resource in project.get('read_resources',[]) if resource['files']]
            if 'audit_read_directory_cost' in result:
                result['audit_read_directory_cost']={tool:cost for tool,cost in result['audit_read_directory_cost'].items() if tool in self.profile['tools']}
            result['feature_profile']={'profile':self.profile['profile'],'authority':'CURRENT_OWNER_SCOPE_INTERSECTION'}
        return result
