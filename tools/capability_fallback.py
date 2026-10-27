"""D2 closed-set branch attribution. No execution, helper tracing or authority.

Pins are explicit review inputs. Branch paths describe only direct name predicates;
non-routing predicates, calls and side effects are not certified by this profile.
"""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_source import python_literal_names

PINS = {
    'tools/integration_service.py':'c068fd6f888868e311568f4e82c93b7cf5a6107f68cac75059f520bb58e7a7c5',
    'tools/integration_transfer.py':'3f022eab8ddf364a3e7c5f2d895eaebdb280ac7b31f3204d673358f40d9be68c',
    'tools/integration_contract.py':'e2c5e3ec5142f888fd4fcf6f2bd1193fd77ff52f4f4234e54df7ec997aac6fdb',
}

@dataclass(frozen=True)
class FallbackObservation:
    paths: tuple
    blockers: tuple
    routing_only: bool = True
    execution_verified: bool = False
    authority_verified: bool = False


def _shape(node):
    return ast.dump(node,include_attributes=False)


def _method(tree,name):
    classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Service']
    methods=[n for c in classes for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(classes)!=1 or len(methods)!=1 or classes[0].decorator_list or methods[0].decorator_list:
        raise ValueError('METHOD_SHAPE')
    return methods[0]


def inspect_fallback(sources, pins=PINS):
    scan_sources(sources,())
    files={s.path:s for s in sources}
    if set(pins)!=set(PINS): raise ValueError('PIN_SET')
    drift=tuple(('SOURCE_MISSING_OR_DRIFT',p) for p,h in pins.items() if p not in files or files[p].sha256!=h)
    if drift: return FallbackObservation((),drift)
    trees={p:ast.parse(files[p].data.decode('utf-8')) for p in pins}
    service=trees['tools/integration_service.py']; contract=trees['tools/integration_contract.py']
    try:
        names=set(python_literal_names(files['tools/integration_transfer.py'].data.decode(),'NAMES',mapping=False))
        schemas=set(python_literal_names(files['tools/integration_service.py'].data.decode(),'SCHEMAS',mapping=True))
        if names!=schemas: raise ValueError('DECLARATION_SET_MISMATCH')
        imports=[n for n in service.body if isinstance(n,(ast.Import,ast.ImportFrom))]
        expected=ast.parse('import integration_contract as c\nfrom integration_transfer import NAMES').body
        if any(sum(_shape(n)==_shape(e) for n in imports)!=1 for e in expected): raise ValueError('IMPORT_BINDING')
        guard=[n for n in contract.body if isinstance(n,ast.FunctionDef) and n.name=='require']
        model=ast.parse('def require(condition, code):\n    if not condition:\n        raise IntegrationError(code)').body[0]
        if len(guard)!=1 or _shape(guard[0])!=_shape(model): raise ValueError('GUARD_NOT_REJECTING')
        entry=_method(service,'call'); handler=_method(service,'_call_locked')
        first=ast.parse('c.require(name in NAMES, "UNSUPPORTED_TOOL")').body[0]
        if not entry.body or _shape(entry.body[0])!=_shape(first): raise ValueError('MEMBERSHIP_GUARD_MISSING')
        target=ast.parse('return self._call_locked(name, args)').body[0]
        returns=[n for n in ast.walk(entry) if isinstance(n,ast.Return)]
        if len(returns)!=1 or _shape(returns[0])!=_shape(target): raise ValueError('HANDOFF_BINDING')
        for method in (entry,handler):
            for n in ast.walk(method):
                if isinstance(n,ast.Name) and n.id=='name' and isinstance(n.ctx,ast.Store): raise ValueError('SUBJECT_REASSIGNMENT')
                if isinstance(n,(ast.Assign,ast.AnnAssign,ast.NamedExpr)) and isinstance(n.value,ast.Name) and n.value.id=='name': raise ValueError('SUBJECT_ALIAS')
        paths={name:[] for name in names}
        def predicate(test):
            if not any(isinstance(n,ast.Name) and n.id=='name' for n in ast.walk(test)): return None
            if isinstance(test,ast.Compare) and len(test.ops)==1 and isinstance(test.left,ast.Name) and test.left.id=='name':
                right=test.comparators[0]
                if isinstance(test.ops[0],ast.Eq) and isinstance(right,ast.Constant) and type(right.value) is str: return {right.value}
                if isinstance(test.ops[0],ast.In) and isinstance(right,(ast.Tuple,ast.List)) and all(isinstance(v,ast.Constant) and type(v.value) is str for v in right.elts): return {v.value for v in right.elts}
            raise ValueError('COMPUTED_ROUTING_PREDICATE')
        def walk(node,domain):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda,ast.ClassDef,ast.comprehension)):
                return
            if isinstance(node,(ast.If,ast.IfExp)):
                matched=predicate(node.test)
                if matched is not None:
                    if not matched<=names: raise ValueError('UNDECLARED_BRANCH')
                    yes,no=domain & matched,domain-matched
                    for name in yes: paths[name].append((node.lineno,'literal'))
                    for name in no: paths[name].append((node.lineno,'remainder'))
                    left=node.body if isinstance(node.body,list) else [node.body]
                    right=node.orelse if isinstance(node.orelse,list) else [node.orelse]
                    for child in left: walk(child,yes)
                    for child in right: walk(child,no)
                    return
                # A non-name condition that hides name routing is unsupported.
                if any(isinstance(n,(ast.If,ast.IfExp)) and any(isinstance(v,ast.Name) and v.id=='name' for v in ast.walk(n.test)) for n in ast.walk(node) if n is not node):
                    raise ValueError('CONDITIONAL_ROUTING_SCOPE')
                return
            for child in ast.iter_child_nodes(node): walk(child,domain)
        for node in handler.body: walk(node,names)
        if any(not p for p in paths.values()): raise ValueError('UNATTRIBUTED_NAME')
        return FallbackObservation(tuple((n,tuple(paths[n])) for n in sorted(names)),())
    except (ValueError,SyntaxError) as error:
        return FallbackObservation((),(('PROFILE_UNSUPPORTED',str(error)),))
