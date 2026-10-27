"""M1 finite views over a private copy of explicitly pinned resource files.

No imports/commands named by file content, no network, no resume/collector or
resource-path resolution. Original read/validation functions retain authority.
"""
import base64
from pathlib import Path
import integration_contract as c
import agent_io as io
import judgment_record as judgments
import agent_lifecycle
import evidence_adapters
import evidence_export
import provider_costs
import billing_evidence
import provider_usage
import revision_status
import verify_agent
import agent_entrypoint
import instruction_bundle
import integration_gateway_contract as gateway
import integration_hook_contract as hooks
import integration_mutation_contract as mutations


def read_bytes(path):
    with path.open('rb') as stream:raw=stream.read(1048577)
    c.require(len(raw)<=1048576,'READ_RESOURCE_FILE_LIMIT')
    return raw


def options(value,fields=()):c.require(set(value)<=set(fields),'READ_RESOURCE_OPTIONS')
def record_binding(root,work):
    record,_=io.load_bundle(root);judgments.validate_binding(record,work);return record


def view(tool,operation,root,args,work):
    if tool=='artifact_read':
        if operation in ('view','report','raw','record','procedure','measure','facts'):
            record_binding(root,work)
        if operation=='view':options(args);return io.view(root)
        if operation=='report':options(args);return {'markdown':io.report(root),'role':'HISTORICAL_CAPTURE_NOT_ACCEPTANCE'}
        if operation=='raw':
            options(args,('step','stream','offset','bytes'));c._validate(args,c.obj({'step':c.ID,'stream':c.enum('stdout.log','stderr.log'),'offset':c.INTEGER,'bytes':{'type':'integer','minimum':1,'maximum':65536}}))
            result=io.read_raw(root,args['step'],args['stream'],args['offset'],args['bytes'])
            with (root/args['step']/args['stream']).open('rb') as stream:stream.seek(args['offset']);raw=stream.read(args['bytes'])
            return {**result,'data_base64':base64.b64encode(raw).decode(),'window_sha256':c.sha(raw)}
        if operation=='record':options(args,('section',));return io.work_record(root,args.get('section','all'))
        if operation=='procedure':options(args);return io.procedure_view(root)
        if operation=='measure':options(args);return io.measure(root)
        if operation=='judgment':
            options(args);record,_=judgments.load(root);c.require(record['binding']==work,'READ_RESOURCE_WORK_BINDING');return judgments.view(root)
        if operation=='facts':
            options(args);value=judgments.facts(root,work)
            return {'facts':judgments.fact_ids(value),'observation_revision':value['observation_revision'],'authenticity_verified':False}
        if operation=='lifecycle':options(args);return agent_lifecycle.inspect(root)
        if operation=='export':options(args,('manifest_sha256',));return evidence_export.verify(root,args.get('manifest_sha256'))
        if operation=='provider_cost':options(args);return provider_costs.load(root)
        if operation=='conformance':options(args);return {'markdown':verify_agent.render_report(read_bytes(root/'report.json'))}
        if operation=='declaration':
            options(args,('actor',));c._validate(args,c.obj({'actor':c.ID}));return evidence_adapters.declaration(read_bytes(root/'artifact'),args['actor'],work)
        if operation=='review':
            options(args,('subject_sha256',));c._validate(args,c.obj({'subject_sha256':c.DIGEST}));return evidence_adapters.review(read_bytes(root/'artifact'),io.read_json(root/'review.json'),args['subject_sha256'],work)
        if operation=='research_outcome':
            options(args,('actor',));c._validate(args,c.obj({'actor':c.ID}));payload=io.read_json(root/'outcome.json');c.require(payload.get('work_id')==work['work_id'],'READ_RESOURCE_WORK_BINDING');return evidence_adapters.research_outcome(payload,args['actor'],work)
    if tool=='usage_read':
        options(args)
        if operation=='provider_cost':return provider_costs.load(root)
        usage,_=billing_evidence.load_records([root/'usage' if operation=='billing_view' else root])
        for record in usage:
            for call in record['calls']:c.require(all(call['attribution'].get(k)==v for k,v in work.items()),'READ_RESOURCE_WORK_BINDING')
        if operation=='totals':return provider_usage.totals(usage)
        if operation=='billing_view':
            return {'reported_totals':provider_usage.totals(usage),'declared_export':io.read_json(root/'billing.json'),
                'declared_receipt':io.read_json(root/'billing-receipt.json'),'delegated_billing_authority_verified':False,
                'billing_reconciled':False,'work_cost_assigned':False,'next_operation':'M4_VERIFY_DELEGATED_BILLING_AUTHORITY'}
    if tool=='revision_read':
        options(args)
        if operation=='relations':
            value=io.read_json(root/'relations.json')
            c.require(set(value)=={'record','target','remote_sha'},'READ_RESOURCE_OPTIONS')
            return {'source_relation':revision_status.source_relation(value['record'],value['target']),
                'remote_relation':revision_status.remote_relation(value['remote_sha'],value['target']),
                'target_basis':'PINNED_CAPTURE_NOT_LIVE_GIT_SCAN','remote_latest_verified':False,'overall_completion':'NOT_INFERRED'}
        if operation=='saved_status':
            value=io.read_json(root/'result.json');c.require(value.get('schema')=='golem.revision-status.v1' and value.get('binding')==work,'READ_RESOURCE_WORK_BINDING')
            return {'capture':value,'freshness':'HISTORICAL_CAPTURE_REVALIDATE_FOR_CURRENT_STATE','live_native_acceptance_verified':False,'remote_latest_verified':False,'overall_completion':'NOT_INFERRED'}
    if tool=='configuration_read':
        if operation=='entrypoint':
            options(args);raw=read_bytes(root/'AGENTS.md');prefix,block,suffix=agent_entrypoint.split_block(raw);outside=prefix+suffix
            return {'agents_sha256':c.sha(raw),'outside_sha256':c.sha(outside),'managed_block':block.decode('utf-8') if block is not None else None,'owner_check':'NOT_RUN','product_acceptance':False}
        if operation=='instruction_manifest':
            options(args);value=io.read_json(root/'manifest.json');instruction_bundle.validate_manifest(value)
            return {'manifest':value,'dependency_resolution':'NOT_RUN','owner_apply_authorized':False}
        if operation=='saved_plan':options(args);return {'plan':io.read_json(root/'plan.json'),'current_basis_verified':False,'owner_apply_authorized':False}
        if operation=='guide':
            options(args,('task',));c.require(set(args)=={'task'} and args['task'] in io.ROUTES,'READ_RESOURCE_OPTIONS')
            return {'task':args['task'],'read_on_demand':io.ROUTES[args['task']]+io.COMMON,'execution_authorized':False}
        if operation=='schemas':
            options(args,('kind',));c.require(set(args)=={'kind'},'READ_RESOURCE_OPTIONS')
            schemas={'gateway_policy':gateway.POLICY,'gateway_revocations':gateway.REVOCATIONS,'hook_profile':hooks.PROFILE,'mutation_policy':mutations.POLICY,'mutation_action':mutations.ACTION,'mutation_decision':mutations.DECISION}
            if args['kind'] in schemas:return {'$schema':'https://json-schema.org/draft/2020-12/schema',**schemas[args['kind']]}
            c.require(args['kind'] in c.CONTRACTS,'READ_RESOURCE_OPTIONS');return c.schema(args['kind'])
    raise c.IntegrationError('UNSUPPORTED_READ_OPERATION')
