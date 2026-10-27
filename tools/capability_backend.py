"""D1 closed read-domain to fixed native argv observations; no native execution."""
import ast
from dataclasses import dataclass

from capability_profile import scan_sources
from capability_fallback import _shape
from capability_mutation_graph import _function

PINS={
    'tools/integration_backend.py':'af4c53f28db212c96a830b6ec282f3e2c7a0b7db97aab2ff2e484d525271125e',
    'tools/integration_contract.py':'e2c5e3ec5142f888fd4fcf6f2bd1193fd77ff52f4f4234e54df7ec997aac6fdb',
}


@dataclass(frozen=True)
class BackendObservation:
    operation_routes: tuple
    blockers: tuple
    execution_verified: bool=False
    authority_verified: bool=False
    native_read_only_verified: bool=False


def _expr(text):
    return _shape(ast.parse(text,mode='eval').body)


def _assignment(tree,name):
    nodes=[n.value for n in tree.body if isinstance(n,ast.Assign) and
           any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
    if len(nodes)!=1: raise ValueError('ASSIGNMENT_NOT_UNIQUE')
    return nodes[0]


def inspect_backend(sources,pins=PINS):
    scan_sources(sources,())
    if set(pins)!=set(PINS): raise ValueError('PIN_SET')
    files={s.path:s for s in sources}
    drift=tuple(('SOURCE_MISSING_OR_DRIFT',p) for p,h in pins.items() if p not in files or files[p].sha256!=h)
    if drift: return BackendObservation((),drift)
    try:
        backend=ast.parse(files['tools/integration_backend.py'].data.decode())
        contract=ast.parse(files['tools/integration_contract.py'].data.decode())
        imports=ast.parse('import integration_contract as contract\nfrom integration_contract import IntegrationError, decode, encoded, require, sha, validate').body
        if any(sum(_shape(e)==_shape(n) for n in backend.body)!=1 for e in imports): raise ValueError('IMPORT_BINDING')
        query=_assignment(contract,'QUERY')
        if not isinstance(query,ast.Call) or not isinstance(query.args[0],ast.Dict): raise ValueError('QUERY_SHAPE')
        operations=[v for k,v in zip(query.args[0].keys,query.args[0].values) if isinstance(k,ast.Constant) and k.value=='operation']
        expected='enum("status", "next", "record", "history")'
        if len(operations)!=1 or _shape(operations[0])!=_expr(expected): raise ValueError('QUERY_OPERATION_SET')
        contracts=_assignment(contract,'CONTRACTS')
        reads=[v for k,v in zip(contracts.keys,contracts.values) if isinstance(k,ast.Constant) and k.value=='read']
        if len(reads)!=1 or _shape(reads[0])!=_expr('QUERY'): raise ValueError('QUERY_CONTRACT_BINDING')
        require=_function(contract,None,'require')
        model=ast.parse('def require(condition, code):\n if not condition:\n  raise IntegrationError(code)').body[0]
        if _shape(require)!=_shape(model): raise ValueError('GUARD_NOT_REJECTING')
        native=_function(backend,None,'_native'); read=_function(backend,None,'read')
        if _shape(read.body[0])!=_shape(ast.parse('validate("read", request)').body[0]): raise ValueError('READ_VALIDATION_GUARD')
        route=ast.parse('if operation in ("status", "next"):\n command = ["session", "call"]\nelse:\n command = ["work", operation]').body[0]
        matches=[n for n in native.body if isinstance(n,ast.If) and _shape(n)==_shape(route)]
        if len(matches)!=1: raise ValueError('NATIVE_ROUTE_SHAPE')
        writes=[n for n in ast.walk(native) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id=='command']
        if len(writes)!=2: raise ValueError('COMMAND_REASSIGNMENT')
        for method,subject in ((native,'operation'),(read,'request')):
            for node in ast.walk(method):
                if isinstance(node,ast.Name) and node.id==subject and isinstance(node.ctx,ast.Store):
                    raise ValueError('SUBJECT_REASSIGNMENT')
                if isinstance(node,(ast.Assign,ast.AnnAssign,ast.NamedExpr)) and isinstance(node.value,ast.Name) and node.value.id==subject:
                    raise ValueError('SUBJECT_ALIAS')
        argv=[n.value for n in native.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='argv' for t in n.targets)]
        if len(argv)!=1 or _shape(argv[0])!=_expr('[project["cli"]["path"], "--output-mode", "full", *command, work["path"], str(request_path)]'):
            raise ValueError('ARGV_BINDING')
        for name, count in (('operation',2),('command',3),('argv',2)):
            if sum(isinstance(n,ast.Name) and n.id==name for n in ast.walk(native))!=count:
                raise ValueError('ROUTING_SUBJECT_ESCAPE')
        capture=[n for n in ast.walk(native) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='capture']
        expected_capture='records.capture(argv, destination, TIMEOUT_SECONDS, cwd=destination, observe_source=False, env=ENVIRONMENT, limit=contract.MAX_NATIVE)'
        if len(capture)!=1 or _shape(capture[0])!=_expr(expected_capture): raise ValueError('CAPTURE_BINDING')
        forwarded=[n for n in ast.walk(read) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_native']
        expected_calls=[
            '_native(project, work, "record", native_request, output / "record")',
            '_native(project, work, request["operation"], native_request, output / request["operation"])']
        if sorted(_shape(n) for n in forwarded)!=sorted(_expr(n) for n in expected_calls): raise ValueError('READ_NATIVE_FORWARDING')
        routes=(('status',('session','call')),('next',('session','call')),('record',('work','record')),('history',('work','history')))
        return BackendObservation(routes,())
    except (ValueError,SyntaxError,AttributeError,IndexError) as error:
        return BackendObservation((),(('BACKEND_PROFILE_UNSUPPORTED',str(error)),))
