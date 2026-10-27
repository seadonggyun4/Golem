"""Pinned D4 declaration references and one explicit helper edge, not execution."""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_source import python_literal_names
from capability_fallback import _shape, _method

PINS={'tools/integration_parallel_actions.py':'fba94f6a466bdf9b013ab8ad939ed80d5232bb2dd7ea64da3d2912ff2eb02dc3',
'tools/integration_quality_actions.py':'9952c0b371fdbcccb13e1ae2872690c541e16c0e076e19588483f5cbd14e02a0',
'tools/integration_task_actions.py':'070b6c35d8ea0e6f0cbd53706c56c579b7bfe6a43a93406f7e6894a7f2924002',

 'tools/integration_mutations.py':'93fbe43fee8d26acde873bd7d41b8edbd099e61dd0e904e58fbc3fa2278731dc',
 'tools/integration_mutation_contract.py':'6c3b342b1a7859fa863979dc9ca41585084c716597e5159f17176c6c024f9410',
 'tools/integration_service.py':'c068fd6f888868e311568f4e82c93b7cf5a6107f68cac75059f520bb58e7a7c5',
 'tools/integration_contract.py':'e2c5e3ec5142f888fd4fcf6f2bd1193fd77ff52f4f4234e54df7ec997aac6fdb',
}
@dataclass(frozen=True)
class DelegationObservation:
    reads: tuple
    delegated: tuple
    helper: str
    blockers: tuple
    helper_body_verified: bool=False
    execution_verified: bool=False
    authority_verified: bool=False


def inspect_delegation(sources,pins=PINS):
    scan_sources(sources,())
    files={s.path:s for s in sources}
    if set(pins)!=set(PINS): raise ValueError('PIN_SET')
    drift=tuple(('SOURCE_MISSING_OR_DRIFT',p) for p,h in pins.items() if p not in files or files[p].sha256!=h)
    if drift: return DelegationObservation((),(),'',drift)
    try:
        trees={p:ast.parse(files[p].data.decode()) for p in pins}
        root=trees['tools/integration_mutations.py']
        expected=ast.parse('import integration_service as reads\nimport integration_mutation_contract as contract\nimport integration_contract as c').body
        imports=[n for n in root.body if isinstance(n,ast.Import)]
        if any(sum(_shape(n)==_shape(e) for n in imports)!=1 for e in expected): raise ValueError('IMPORT_BINDING')
        names=set(python_literal_names(files['tools/integration_mutation_contract.py'].data.decode(),'NAMES',mapping=False))
        reads=set(python_literal_names(files['tools/integration_service.py'].data.decode(),'SCHEMAS',mapping=True))
        if names & reads: raise ValueError('DECLARATION_OVERLAP')
        guard=[n for n in trees['tools/integration_contract.py'].body if isinstance(n,ast.FunctionDef) and n.name=='require']
        model=ast.parse('def require(condition, code):\n    if not condition:\n        raise IntegrationError(code)').body[0]
        if len(guard)!=1 or _shape(guard[0])!=_shape(model): raise ValueError('GUARD_NOT_REJECTING')
        entry=_method(root,'call'); helper=_method(root,'_mutate')
        for method in (entry,helper):
            if [a.arg for a in method.args.args]!=['self','name','args'] or method.args.defaults or method.args.vararg or method.args.kwarg or method.args.kwonlyargs or method.args.posonlyargs:
                raise ValueError('PARAMETER_BINDING')
        first=ast.parse('if name in reads.SCHEMAS:\n    return self.reads.call(name, args)\nc.require(name in contract.NAMES, "UNSUPPORTED_TOOL")').body
        if len(entry.body)<2 or any(_shape(a)!=_shape(b) for a,b in zip(entry.body[:2],first)): raise ValueError('DISPATCH_GUARD')
        calls=[n for n in ast.walk(entry) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_mutate']
        target=ast.parse('self._mutate(name, args)',mode='eval').body
        if len(calls)!=1 or _shape(calls[0])!=_shape(target): raise ValueError('HELPER_EDGE')
        returns=[n for n in ast.walk(entry) if isinstance(n,ast.Return)]
        expected_returns=[first[0].body[0],ast.parse('return self._mutate(name, args)').body[0]]
        if sorted(_shape(n) for n in returns)!=sorted(_shape(n) for n in expected_returns): raise ValueError('RETURN_EDGE')
        allowed_name_calls={_shape(target),_shape(first[0].body[0].value),_shape(first[1].value),_shape(ast.parse('c._validate(args, contract.SCHEMAS[name])',mode='eval').body)}
        for n in ast.walk(entry):
            if isinstance(n,ast.Call) and any(isinstance(v,ast.Name) and v.id=='name' for a in (*n.args,*(k.value for k in n.keywords)) for v in ast.walk(a)) and _shape(n) not in allowed_name_calls:
                raise ValueError('UNREGISTERED_FORWARDING')
            if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id in ('name','args','self'): raise ValueError('ARGUMENT_REASSIGNMENT')
            if isinstance(n,(ast.Assign,ast.AnnAssign,ast.NamedExpr)) and isinstance(n.value,ast.Name) and n.value.id in ('name','args','self'): raise ValueError('ARGUMENT_ALIAS')
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)) and n is not entry: raise ValueError('NESTED_SCOPE')
        return DelegationObservation(tuple(sorted(reads)),tuple(sorted(names)),'Service._mutate',())
    except (ValueError,SyntaxError) as error:
        return DelegationObservation((),(),'',(('PROFILE_UNSUPPORTED',str(error)),))
