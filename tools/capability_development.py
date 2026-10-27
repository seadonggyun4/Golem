"""Explicit review of development-only M0 analysis code, not native capability.

Separate from product sources to avoid self-inventory claiming Work behavior.
Byte pins and AST syntax/declaration facts detect stale reviews. Registry data
has a data-only AST contract, avoiding a self-hash fixed point.
"""
import ast
import hashlib
from capability_c_graph import fingerprint
from capability_profile import scan_sources

REGISTRY='tools/capability_development_registry.py'

def development_shape(raw):
    t=ast.parse(raw)
    symbols=tuple(sorted(n.name for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.AsyncFunctionDef))))
    imports=tuple(sorted(ast.dump(n,include_attributes=False) for n in ast.walk(t) if isinstance(n,(ast.Import,ast.ImportFrom))))
    return fingerprint((symbols,imports))

def inspect_development(sources,models):
    scan_sources(sources,());files={s.path:s for s in sources};errors=[]
    for path,digest,shape,role in models:
        f=files.get(path)
        try:
            if f is None:raise ValueError('DEVELOPMENT_FILE_MISSING')
            if role not in ('M0_STATIC_ANALYSIS','M0_FIXTURE_REGRESSION','M0_REVIEW_METADATA'):raise ValueError('DEVELOPMENT_ROLE')
            if path==REGISTRY:
                tree=ast.parse(f.data)
                body=tree.body[1:] if tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant) else tree.body
                if len(body)!=2 or not all(isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) for n in body):raise ValueError('REVIEW_REGISTRY_NOT_DATA_ONLY')
                for n in body:ast.literal_eval(n.value)
                if {n.targets[0].id for n in body}!={'DEVELOPMENT_PATHS','DEVELOPMENT_REVIEWS'}:raise ValueError('REVIEW_REGISTRY_FIELDS')
            elif f.sha256!=digest or development_shape(f.data)!=shape:raise ValueError('DEVELOPMENT_REVIEW_DRIFT')
        except (ValueError,SyntaxError,TypeError,UnicodeError) as e:errors.append(('DEVELOPMENT_REVIEW_BLOCKED',(path,str(e))))
    if set(files)!={m[0] for m in models}:errors.append(('DEVELOPMENT_SELECTION_MISMATCH',None))
    return tuple(errors)
