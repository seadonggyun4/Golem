"""Pinned Python class.method literal comparison observations; never imports code."""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_source import python_literal_names


@dataclass(frozen=True)
class HandlerRule:
    declaration_path: str
    declaration_sha256: str
    declaration: str
    mapping: bool
    handler_path: str
    handler_sha256: str
    method: str
    subject: str


@dataclass(frozen=True)
class HandlerObservation:
    declared: tuple
    compared: tuple
    missing: tuple
    extra: tuple
    blockers: tuple

    @property
    def linked(self):
        return not self.blockers and not self.missing and not self.extra


def inspect_handler(sources, rule):
    # Same whole-input bounds, raw hash and duplicate-path checks as other profiles.
    scan_sources(sources, ())
    if not isinstance(rule, HandlerRule) or type(rule.mapping) is not bool:
        raise ValueError('HANDLER_RULE_INVALID')
    parts = rule.method.split('.')
    if len(parts) != 2 or not all(p.isidentifier() for p in (*parts, rule.subject)):
        raise ValueError('HANDLER_SELECTOR_INVALID')
    files = {s.path:s for s in sources}
    for path, pin in ((rule.declaration_path, rule.declaration_sha256),
                      (rule.handler_path, rule.handler_sha256)):
        if path not in files or files[path].sha256 != pin:
            return HandlerObservation((),(),(),(),(('SOURCE_MISSING_OR_DRIFT',path),))
    declared = python_literal_names(files[rule.declaration_path].data.decode('utf-8'),
                                   rule.declaration, mapping=rule.mapping)
    tree = ast.parse(files[rule.handler_path].data.decode('utf-8'))
    classes = [n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==parts[0]]
    methods = [n for c in classes for n in c.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==parts[1]]
    if len(classes)!=1 or len(methods)!=1:
        return HandlerObservation(tuple(declared),(),tuple(declared),(),(('METHOD_NOT_UNIQUE',rule.method),))
    method=methods[0]; found=set(); blocked=[]
    def uses(node):
        return any(isinstance(n,ast.Name) and n.id==rule.subject for n in ast.walk(node))
    def subject(node):
        return isinstance(node,ast.Name) and node.id==rule.subject
    def visit(node):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)):
            if uses(node): blocked.append(('NESTED_SCOPE',node.lineno))
            return
        if isinstance(node,ast.If) and node.orelse:
            # elif is another explicit comparison; a final else is not inferred.
            if not (len(node.orelse)==1 and isinstance(node.orelse[0],ast.If)):
                blocked.append(('ELSE_FALLBACK',node.lineno))
        if isinstance(node,ast.Compare) and uses(node):
            values=None
            if len(node.ops)==1:
                left,right=node.left,node.comparators[0]; op=node.ops[0]
                if isinstance(op,ast.Eq):
                    other=right if subject(left) else left if subject(right) else None
                    if isinstance(other,ast.Constant) and type(other.value) is str: values=[other.value]
                elif isinstance(op,ast.In) and subject(left) and isinstance(right,(ast.Tuple,ast.List)):
                    if all(isinstance(v,ast.Constant) and type(v.value) is str for v in right.elts):
                        values=[v.value for v in right.elts]
            if values is None: blocked.append(('COMPUTED_COMPARISON',node.lineno))
            else: found.update(values)
        if isinstance(node,ast.Call) and any(uses(v) for v in (*node.args,*(k.value for k in node.keywords))):
            blocked.append(('UNREGISTERED_HELPER',node.lineno))
        if isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign,ast.NamedExpr)) and uses(node):
            blocked.append(('SUBJECT_ASSIGNMENT_OR_ALIAS',node.lineno))
        for child in ast.iter_child_nodes(node): visit(child)
    if method.decorator_list or classes[0].decorator_list:
        blocked.append(('DECORATOR_UNEVALUATED',method.lineno))
    if not any(a.arg==rule.subject for a in (*method.args.posonlyargs,*method.args.args,*method.args.kwonlyargs)):
        blocked.append(('SUBJECT_NOT_PARAMETER',method.lineno))
    for n in method.body: visit(n)
    return HandlerObservation(tuple(sorted(declared)),tuple(sorted(found)),tuple(sorted(set(declared)-found)),
                              tuple(sorted(found-set(declared))),tuple(sorted(set(blocked))))
