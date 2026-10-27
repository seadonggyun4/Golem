"""Bounded D4 static edge and prefix observations, not a policy/execution proof."""
import ast
from dataclasses import dataclass
from capability_delegation import PINS, inspect_delegation
from capability_fallback import _shape, _method
from capability_mutation_scope_registry import EXPECTED_SCOPES

@dataclass(frozen=True)
class MutationGraph:
    edges: tuple
    prefix_mapping: tuple
    argv_routes: tuple
    blockers: tuple
    receiver_identity_verified: bool=False
    policy_satisfied: bool=False
    native_execution_verified: bool=False
    unregistered_helpers_traced: bool=False


def _expression(text):
    return _shape(ast.parse(text,mode='eval').body)


def _function(tree,cls,name):
    scopes=tree.body if cls is None else [v for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls for v in n.body]
    matches=[n for n in scopes if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(matches)!=1 or matches[0].decorator_list: raise ValueError('FUNCTION_UNIQUE_UNDECORATED')
    return matches[0]


def _calls(node):
    """Keep exact syntactic ancestry; never infer domination or follow calls."""
    out=[]
    def walk(n,path):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)) and n is not node:
            return
        if isinstance(n,ast.Call): out.append((n,tuple(path)))
        for field,value in ast.iter_fields(n):
            children=value if isinstance(value,list) else [value]
            for i,child in enumerate(children):
                if isinstance(child,ast.AST):
                    condition = (_shape(n.test) if isinstance(n,(ast.If,ast.IfExp,ast.While)) else
                                 tuple(_shape(v) for v in n.items) if isinstance(n,ast.With) else
                                 tuple(_shape(v.type) if v.type else 'bare' for v in n.handlers) if isinstance(n,ast.Try) else None)
                    walk(child,path+[(type(n).__name__,field,i,condition)])
    walk(node,[])
    return sorted(out,key=lambda v:(v[0].lineno,v[0].col_offset))


def inspect_mutation_graph(sources,pins=PINS):
    initial=inspect_delegation(sources,pins)
    if initial.blockers: return MutationGraph((),(),(),initial.blockers)
    files={v.path:v for v in sources}
    tree=ast.parse(files['tools/integration_mutations.py'].data.decode())
    contract=ast.parse(files['tools/integration_mutation_contract.py'].data.decode())
    edges=[]; blockers=[]
    # Exact expressions include receiver/arguments. Multiple authorize calls are intentional.
    specs=(
        ('Service._mutate', 'self._admit(name, args)',1),
        ('Service._mutate', 'self._preflight(entry, native)',1),
        ('Service._mutate', 'self._argv(entry, project, work, value, output)',1),
        ('Service._mutate', 'self.policy.authorize(entry)',3),
        ('Service._mutate', 'self.policy.action(entry)',1),
        ('Service._mutate', 'records.capture(argv, output, 540 if value["approval"] else backend.TIMEOUT_SECONDS, cwd=output, observe_source=False, env=backend.ENVIRONMENT, limit=c.MAX_NATIVE)',1),
        ('Service._admit','self.policy.authorize(entry)',1),
        ('Service._admit','self.policy.action(entry)',1),
        ('Policy.authorize','self.current()',1),
        ('Policy.action','native_action(entry, value)',1),
    )
    methods={}
    for label,expr,count in specs:
        cls,name=label.split('.')
        method=_function(tree if cls=='Service' else contract,cls,name);methods[label]=method
        calls=_calls(method); target=_expression(expr)
        matches=[(n,path) for n,path in calls if _shape(n)==target]
        valid = len(matches)==count and tuple(path for _,path in matches)==EXPECTED_SCOPES.get((label,expr))
        if not valid: blockers.append(('EDGE_ARGUMENT_OR_SCOPE_MISMATCH',label,expr))
        edges.append((label,expr,'CONFIRMED' if valid else 'UNRESOLVED',tuple((n.lineno,path) for n,path in matches)))
    try:
        mutate=methods['Service._mutate']
        calls=_calls(mutate)
        def line(expr):
            matches=[n.lineno for n,_ in calls if _shape(n)==_expression(expr)]
            if len(matches)!=1: raise ValueError('ORDER_EDGE_MISSING')
            return matches[0]
        chain=['self._admit(name, args)','self._preflight(entry, native)',
               'self._argv(entry, project, work, value, output)','self.policy.action(entry)',specs[5][1]]
        positions=[line(e) for e in chain]
        if positions!=sorted(set(positions)): raise ValueError('SOURCE_ORDER_CHANGED')
        capture=[(n,path) for n,path in calls if _shape(n)==_expression(specs[5][1])]
        if not capture or not any(frame[0]=='With' for frame in capture[0][1]): raise ValueError('CAPTURE_ADMISSION_SCOPE')
        names=set(initial.delegated)
        wrapper=_function(contract,None,'native_action')
        handoff=ast.parse('request = action_shape(entry, value)').body[0]
        if _shape(wrapper.body[1])!=_shape(handoff): raise ValueError('ACTION_SHAPE_HANDOFF')
        native=_function(contract,None,'action_shape')
        if len(native.args.kwonlyargs)!=1 or native.args.kwonlyargs[0].arg!='allow_missing_approval' or _shape(native.args.kw_defaults[0])!=_expression('False'): raise ValueError('ACTION_APPROVAL_DEFAULT')
        from capability_source import python_literal_names
        task_names=set(python_literal_names(files['tools/integration_task_actions.py'].data.decode(),'NAMES',mapping=False)) if 'tools/integration_task_actions.py' in files else set()
        branches=[n for n in native.body if isinstance(n,ast.If)]
        quality_names=set(python_literal_names(files['tools/integration_quality_actions.py'].data.decode(),'NAMES',mapping=False)) if 'tools/integration_quality_actions.py' in files else set()
        parallel_names=set(python_literal_names(files['tools/integration_parallel_actions.py'].data.decode(),'NAMES',mapping=False)) if 'tools/integration_parallel_actions.py' in files else set()
        if parallel_names:
            if _shape(branches[0])!=_shape(ast.parse('if name in parallel.NAMES:\n    return parallel.shape(entry, value)').body[0]):raise ValueError('M5_SHAPE_HANDOFF')
            if not parallel_names<=names or parallel_names & (task_names|quality_names):raise ValueError('M5_DOMAIN')
            names=names-parallel_names;branches=branches[1:]
        if quality_names:
            if _shape(branches[0])!=_shape(ast.parse('if name in quality.NAMES:\n    return quality.shape(entry, value)').body[0]):raise ValueError('M4_SHAPE_HANDOFF')
            if not quality_names<=names or quality_names & task_names:raise ValueError('M4_DOMAIN')
            names=names-quality_names;branches=branches[1:]
        if task_names:
            if _shape(branches[0])!=_shape(ast.parse('if name in tasks.NAMES:\n    return tasks.shape(entry, value)').body[0]):raise ValueError('M3_SHAPE_HANDOFF')
            if not task_names<=names:raise ValueError('M3_DOMAIN')
            names=names-task_names
        branch=branches[1] if task_names else branches[0]
        if _shape(branch.test)!=_expression('name.startswith("session_")'): raise ValueError('PREFIX_PREDICATE')
        assignment=ast.parse('operation = name.removeprefix("session_")').body[0]
        if not branch.body or _shape(branch.body[0])!=_shape(assignment): raise ValueError('PREFIX_TRANSFORM')
        mapping=tuple(sorted((n,n[len('session_'):]) for n in names if n.startswith('session_')))
        if len(mapping)!=5 or any(not v for _,v in mapping) or len({v for _,v in mapping})!=len(mapping): raise ValueError('PREFIX_DOMAIN')
        if names-{n for n,_ in mapping}!={'document_submit','execution_request'}: raise ValueError('REMAINDER_DOMAIN')
        argv=_function(tree,'Service','_argv'); branches=[n for n in argv.body if isinstance(n,ast.If)]
        if quality_names:
            first=ast.parse('if tool == "helper_execute":\n    c.require(self.helpers is not None, "OWNER_HELPER_EFFECTS_APPROVAL_REQUIRED")\n    return self.helpers.command(entry, value)').body[0]
            second=ast.parse('if tool in quality.NAMES:\n    return [*argv, *quality.command(entry, project, work, value, output)]').body[0]
            if _shape(branches[0])!=_shape(first):raise ValueError('M4_HELPER_ARGV_HANDOFF')
            branches=branches[1:]
            if parallel_names:
                host=ast.parse('if tool in parallel.HOST_NAMES:\n    c.require(self.parallel_hosts is not None, "OWNER_PARALLEL_HOST_REQUIRED")\n    return [*argv, *self.parallel_hosts.command(entry, value, output)]').body[0]
                ordinary=ast.parse('if tool in parallel.NAMES:\n    return [*argv, *parallel.command(entry, project, work, value, output)]').body[0]
                if len(branches)<2 or _shape(branches[0])!=_shape(host) or _shape(branches[1])!=_shape(ordinary):raise ValueError('M5_ARGV_HANDOFF')
                branches=branches[2:]
            if not branches or _shape(branches[0])!=_shape(second):raise ValueError('M4_ARGV_HANDOFF')
            branches=branches[1:]
        if task_names:
            if _shape(branches[0])!=_shape(ast.parse('if tool in tasks.NAMES:\n    return [*argv, *tasks.command(entry, project, work, value, output)]').body[0]):raise ValueError('M3_ARGV_HANDOFF')
            branches=branches[1:]
        tests=['tool == "session_resume"','tool.startswith("session_")','tool == "document_submit"']
        if len(branches)!=3 or any(_shape(n.test)!=_expression(t) for n,t in zip(branches,tests)): raise ValueError('ARGV_BRANCH_ORDER')
        routes=[]
        expected=[('session','resume'),('session','call'),('document','submit')]
        for branch,pair in zip(branches,expected):
            ret=branch.body[-1]
            if not isinstance(ret,ast.Return) or not isinstance(ret.value,ast.List): raise ValueError('ARGV_RETURN')
            elts=ret.value.elts
            if len(elts)<3 or not isinstance(elts[0],ast.Starred) or _shape(elts[0].value)!=_expression('argv') or tuple(getattr(n,'value',None) for n in elts[1:3])!=pair: raise ValueError('ARGV_ROUTE')
        final=argv.body[-1]
        if not isinstance(final,ast.Return) or not isinstance(final.value,ast.List) or len(final.value.elts)<2 or _shape(final.value.elts[0])!=_expression('approval["host"]["path"]') or _shape(final.value.elts[1])!=_expression('"execute"'): raise ValueError('EXECUTION_HOST_ROUTE')
        for name in sorted(names):
            route=('session','resume') if name=='session_resume' else ('session','call') if name.startswith('session_') else ('document','submit') if name=='document_submit' else ('host','execute')
            routes.append((name,route))
    except (ValueError,StopIteration) as error:
        blockers.append(('GRAPH_SCOPE_UNVERIFIED',str(error)))
        mapping=();routes=[]
    return MutationGraph(tuple(edges),mapping,tuple(routes),tuple(blockers))
