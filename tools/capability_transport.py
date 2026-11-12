"""Finite D4 stdio declared-name transformation and callback handoff.

Static callback expressions only. SDK behavior, service receiver identity,
actual allowed-tool lists and client delivery are deliberately unverified.
"""
import ast
from dataclasses import dataclass

from capability_profile import scan_sources
from capability_fallback import _shape, inspect_fallback
from capability_delegation import inspect_delegation
from capability_mutation_graph import _function

PINS = {'tools/integration_mutation_mcp.py': 'f4b46e88211d6eed17d1dd41b71b8deb25715ebd1c69c88d3384f7cc126fe082', 'tools/integration_mcp.py': 'ecdb07eb7ae8a90bde379aae8340bf33a90e0c063e8b4fb412c995815c506f2b'}


@dataclass(frozen=True)
class TransportObservation:
    declared_tool_names: tuple
    blockers: tuple
    callback_expressions_only: bool=True
    runtime_receiver_verified: bool=False
    client_delivery_verified: bool=False


def _expr(text):
    return _shape(ast.parse(text,mode='eval').body)


def inspect_transport(sources,pins=PINS):
    scan_sources(sources,())
    if set(pins)!=set(PINS): raise ValueError('PIN_SET')
    files={s.path:s for s in sources}
    drift=tuple(('SOURCE_MISSING_OR_DRIFT',p) for p,h in pins.items() if p not in files or files[p].sha256!=h)
    if drift: return TransportObservation((),drift)
    read=inspect_fallback(sources); mutation=inspect_delegation(sources)
    if read.blockers or mutation.blockers:
        return TransportObservation((),(('DECLARED_DOMAIN_UNVERIFIED',(read.blockers,mutation.blockers)),))
    try:
        tree=ast.parse(files['tools/integration_mutation_mcp.py'].data.decode())
        imports=ast.parse('import integration_contract as c\nimport integration_service as reads\nimport integration_mutation_contract as contract\nimport integration_mutations as mutations\nimport integration_lifecycle as lifecycle\nimport integration_intent as intent').body
        if any(sum(_shape(e)==_shape(n) for n in tree.body)!=1 for e in imports): raise ValueError('IMPORT_BINDING')
        server=_function(tree,None,'server')
        nested={n.name:n for n in server.body if isinstance(n,ast.AsyncFunctionDef)}
        if set(nested)!={'list_tools','call_tool'}: raise ValueError('CALLBACK_SET')
        listing=nested['list_tools']; calling=nested['call_tool']
        def require_expression(node,text,count=1):
            if sum(_shape(n)==_expr(text) for n in ast.walk(node))!=count: raise ValueError('CALLBACK_BINDING')
        require_expression(listing,'readonly.listed_tools(service)')
        if sum(_shape(n)==_shape(ast.parse('import integration_mcp as readonly').body[0]) for n in tree.body)!=1:
            raise ValueError('METADATA_HELPER_IMPORT')
        metadata=ast.parse(files['tools/integration_mcp.py'].data.decode())
        helpers=[n for n in metadata.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='listed_tools' and not n.decorator_list]
        if len(helpers)!=1:raise ValueError('METADATA_HELPER_NOT_UNIQUE')
        helper=helpers[0]
        expected=ast.parse('''async def listed_tools(service):
    """Bounded contention wait for read-only tool metadata, never tool calls."""
    import anyio
    deadline = time.monotonic() + 5
    while True:
        try:
            return await anyio.to_thread.run_sync(service.tools)
        except c.IntegrationError as error:
            if error.code != 'REGISTRY_BUSY' or time.monotonic() >= deadline:
                raise
            await anyio.sleep(0.05)
''').body[0]
        if _shape(helper)!=_shape(expected):raise ValueError('METADATA_WAIT_NOT_READ_ONLY_BOUNDED')
        require_expression(listing,'"golem_" + name')
        require_expression(listing,'(contract.SCHEMAS if name in contract.NAMES else reads.SCHEMAS)[name]')
        require_expression(calling,'c.require(params.name.startswith("golem_"), "UNSUPPORTED_TOOL")')
        require_expression(calling,'anyio.to_thread.run_sync(service.call, params.name[6:], params.arguments)')
        # Reassignment or aliases would invalidate the direct expression binding.
        for method in (server,listing,calling):
            for n in ast.walk(method):
                if isinstance(n,ast.Name) and n.id in ('service','params') and isinstance(n.ctx,ast.Store):
                    raise ValueError('CALLBACK_ARGUMENT_REASSIGNMENT')
                if isinstance(n,(ast.Assign,ast.AnnAssign,ast.NamedExpr)):
                    if isinstance(n.value,(ast.Name,ast.Attribute,ast.Subscript)) and any(
                            isinstance(v,ast.Name) and v.id in ('service','params') for v in ast.walk(n.value)):
                        raise ValueError('CALLBACK_ARGUMENT_ALIAS')
                    targets=n.targets if isinstance(n,ast.Assign) else [n.target]
                    if any(isinstance(v,ast.Name) and v.id in ('service','params')
                           for target in targets for v in ast.walk(target)):
                        raise ValueError('CALLBACK_ARGUMENT_REASSIGNMENT')
        result=server.body[-1]
        if not isinstance(result,ast.Return) or not isinstance(result.value,ast.Call): raise ValueError('SERVER_RETURN')
        bindings={k.arg:k.value for k in result.value.keywords}
        if _shape(bindings.get('on_list_tools'))!=_expr('list_tools') or _shape(bindings.get('on_call_tool'))!=_expr('call_tool'):
            raise ValueError('SDK_CALLBACK_BINDING')
        runs=[n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='run']
        if len(runs)!=1: raise ValueError('RUN_NOT_UNIQUE')
        run=runs[0]
        require_expression(run,'server(service)')
        main=_function(tree,None,'main')
        # Direct stdio must retain admission through the whole transport. The
        # M6 profile checks CallAdmission's mutex/failure/drain implementation;
        # this independent profile checks the declared transport receiver and
        # rejects a raw service, a different guard or an unguarded extra run.
        expected=ast.parse('''with lifecycle.CallAdmission(policy.registry, bindings) as admission:
    service = mutations.Service(policy, resources, helpers, parallel_hosts, intent_hosts)
    asyncio.run(run(lifecycle.AdmittedService(service, admission)))
''').body[0]
        contexts=[n for n in ast.walk(main) if isinstance(n,ast.With) and
                  any(_shape(item.context_expr)==_expr('lifecycle.CallAdmission(policy.registry, bindings)') for item in n.items)]
        if len(contexts)!=1 or _shape(contexts[0])!=_shape(expected):raise ValueError('ADMITTED_TRANSPORT_LIFETIME')
        required_calls={
            'lifecycle.CallAdmission':'lifecycle.CallAdmission(policy.registry, bindings)',
            'mutations.Service':'mutations.Service(policy, resources, helpers, parallel_hosts, intent_hosts)',
            'lifecycle.AdmittedService':'lifecycle.AdmittedService(service, admission)',
            'run':'run(lifecycle.AdmittedService(service, admission))',
            'asyncio.run':'asyncio.run(run(lifecycle.AdmittedService(service, admission)))',
        }
        for receiver,expression in required_calls.items():
            calls=[n for n in ast.walk(main) if isinstance(n,ast.Call) and ast.unparse(n.func)==receiver]
            if len(calls)!=1 or _shape(calls[0])!=_expr(expression):raise ValueError('ADMITTED_TRANSPORT_RECEIVER')
        bindings=ast.parse("bindings = [scope['binding'] for scope in policy.transfer.value['scopes']]").body[0]
        assignments=[n for n in ast.walk(main) if isinstance(n,(ast.Assign,ast.AnnAssign,ast.NamedExpr,ast.AugAssign)) and
                     any(isinstance(v,ast.Name) and v.id=='bindings' and isinstance(v.ctx,ast.Store) for target in
                         (n.targets if isinstance(n,ast.Assign) else [n.target]) for v in ast.walk(target))]
        if len(assignments)!=1 or _shape(assignments[0])!=_shape(bindings):raise ValueError('ADMITTED_TRANSPORT_BINDINGS')
        require_expression(main,'contract.Policy(args.policy, args.reviewed_policy_sha256, approve_mutations=args.approve_mutations)')
        require_expression(main,"c.require(bool(args.intent_host_policy)==bool(args.reviewed_intent_host_policy_sha256)==bool(args.approve_intent_host),'INTENT_OWNER_ARGUMENTS')")
        require_expression(main,'intent.Hosts(args.intent_host_policy,args.reviewed_intent_host_policy_sha256,policy,approve_intent=True) if args.intent_host_policy else None')
        require_expression(main,'c.require(bool(args.read_resources) == bool(args.reviewed_read_resources_sha256) == bool(args.approve_read_resources), "READ_RESOURCE_OWNER_ARGUMENTS")')
        require_expression(main,'readonly.Resources(args.read_resources, args.reviewed_read_resources_sha256, policy.transfer, approve_resources=True) if args.read_resources else None')
        require_expression(main,'c.require(bool(args.helper_policy) == bool(args.reviewed_helper_policy_sha256) == bool(args.approve_helper_effects), "HELPER_OWNER_ARGUMENTS")')
        require_expression(main,'helper_contract.Helpers(args.helper_policy, args.reviewed_helper_policy_sha256, policy, approve_helpers=True) if args.helper_policy else None')
        require_expression(main,'c.require(bool(args.parallel_host_policy) == bool(args.reviewed_parallel_host_policy_sha256) == bool(args.approve_parallel_host), \"PARALLEL_HOST_OWNER_ARGUMENTS\")')
        require_expression(main,'host_contract.Hosts(args.parallel_host_policy, args.reviewed_parallel_host_policy_sha256, policy, approve_hosts=True) if args.parallel_host_policy else None')
        declared=tuple(sorted('golem_'+name for name in (*mutation.reads,*mutation.delegated)))
        if len(declared)!=len(set(declared)): raise ValueError('PREFIX_COLLISION')
        return TransportObservation(declared,())
    except (ValueError,SyntaxError,AttributeError,TypeError,StopIteration) as error:
        return TransportObservation((),(('TRANSPORT_PROFILE_UNSUPPORTED',str(error)),))
