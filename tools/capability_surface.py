"""Whole-file inventory facts; implementation internals are not new tool authority.

Static symbol and literal-branch inventory, separate from selected call proofs.
Each file has a reviewed role, full structural model and explicit source pin.
No imports, command execution, preprocessing or dynamic dispatch inference.
"""
import ast
import json
import re
from dataclasses import dataclass
from capability_c_syntax import plain_definitions,plain_declarations,declaration_tokens
from capability_c_graph import fingerprint
from capability_source import _tokens,_arguments,c_comparison_values
from capability_profile import Observation,Scan,scan_sources
from capability_ledger import observation_identity


def python_facts(text):
    tree=ast.parse(text);symbols=[];branches=[];declarations=[]
    def walk(body,prefix=''):
        for n in body:
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                name=prefix+n.name;symbols.append(name)
                if isinstance(n,ast.ClassDef):walk(n.body,name+'.')
    walk(tree.body)
    # Literal comparisons are facts, not inferred receiver identity or paths.
    for n in ast.walk(tree):
        if isinstance(n,ast.Compare):
            values=[n.left,*n.comparators]
            literals=[]
            for v in values:
                if isinstance(v,ast.Constant) and type(v.value) is str:literals.append(v.value)
                elif isinstance(v,(ast.Tuple,ast.List,ast.Set)) and all(isinstance(x,ast.Constant) and type(x.value)is str for x in v.elts):literals.extend(x.value for x in v.elts)
            if literals:
                subject=ast.dump(n.left,include_attributes=False)
                branches.extend((subject,v) for v in literals)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('add_argument','add_parser'):
            declarations.append(ast.dump(n,include_attributes=False))
    return dict(symbols=tuple(sorted(set(symbols))),branches=tuple(sorted(set(branches))),declarations=tuple(sorted(declarations)),structure=fingerprint(ast.dump(tree,include_attributes=False)))


def c_facts(text):
    tokens=_tokens(text);symbols=[d[0] for d in plain_definitions(text)]
    # Known wrapper invocation names are declarations, never macro expansion.
    for i,t in enumerate(tokens[:-1]):
        if t in ('GOLEM_RECORDED_API','GOLEM_RECORDED_REQUIRED_API','GOLEM_RECORDED_RELEASE_API') and tokens[i+1]=='(':
            a=_arguments(tokens,i+1)
            if len(a[0])!=1:raise ValueError('WRAPPER_NAME_UNSUPPORTED')
            symbols.append(a[0][0])
    branches=[]
    for i,t in enumerate(tokens[:-1]):
        if t in ('strcmp','strncmp') and tokens[i+1]=='(':
            args=_arguments(tokens,i+1)
            if len(args)<2:raise ValueError('COMPARISON_ARITY')
            for j in (0,1):
                if args[j] and all(x.startswith('"') for x in args[j]):
                    try:value=''.join(json.loads(x) for x in args[j])
                    except ValueError:raise ValueError('COMPARISON_LITERAL') from None
                    branches.append((' '.join(args[1-j]),value))
    declarations=tuple((n,tuple(p),tuple(a)) for n,p,a in plain_declarations(text))
    return dict(symbols=tuple(sorted(symbols)),branches=tuple(sorted(set(branches))),declarations=declarations,structure=fingerprint(tokens))


def facts(path,data,language):
    text=data.decode('utf-8')
    if language=='python':return python_facts(text)
    if language=='c':return c_facts(text)
    # JSON/config/JS/TS/package contracts have a reviewed full token/text model;
    # explicit exported methods and operations are registered separately below.
    if language=='json':
        value=json.loads(text)
        return dict(symbols=(),branches=(),declarations=(),structure=fingerprint(value))
    if language=='javascript':
        symbols=tuple(sorted(set(re.findall(r'\b(?:export\s+)?(?:async\s+)?(?:function|class)\s+(\w+)|^\s*(\w+)\s*\([^;\n]*\)\s*\{',text,re.M))))
        return dict(symbols=symbols,branches=(),declarations=(),structure=fingerprint(text))
    return dict(symbols=(),branches=(),declarations=(),structure=fingerprint(text))


def observe_surface(sources,ledger,models):
    scan_sources(sources,());files={s.path:s for s in sources};observations=[];unresolved=[];reviewed=[]
    for m in models:
        f=files.get(m['path'])
        try:
            if f is None or f.sha256!=m['sha256']:raise ValueError('FILE_MISSING_OR_DRIFT')
            actual=facts(f.path,f.data,m['language'])
            if actual['symbols']!=tuple(m['symbols']):raise ValueError('WHOLE_FILE_SYMBOL_SET_CHANGED')
            if actual['declarations']!=tuple(m['declarations']) or actual['branches']!=tuple(m['branches']):raise ValueError('WHOLE_FILE_DECLARATION_OR_BRANCH_CHANGED')
            if fingerprint(actual)!=m['facts_sha256']:raise ValueError('WHOLE_FILE_STRUCTURE_CHANGED')
            if not m['role'] or not m['rationale']:raise ValueError('FILE_ROLE_UNREVIEWED')
            selected=[]
            # Individual helper symbols are listed in the model. A file-role
            # fact reviews their exclusion from standalone MCP, not their behavior.
            selected.append(('PYTHON_DECLARATION' if m['language']=='python' else 'NATIVE_OPERATION','file-surface',None))
            selected.extend(tuple(v) for v in m['operations'])
            for kind,entrypoint,selector in selected:
                fields=dict(kind=kind,source_path=f.path,entrypoint=entrypoint,selector=selector)
                o=Observation(observation_identity(**fields),**fields);observations.append(o)
                if not any(c['review_status']=='REVIEWED' and o.id in c['observation_ids'] for c in ledger['capabilities']):
                    raise ValueError('FILE_OPERATION_UNCLASSIFIED')
            reviewed.append(f.path)
        except (ValueError,SyntaxError,UnicodeError) as e:unresolved.append((m['path'],'file-surface',str(e)))
    return Scan(tuple(observations),tuple(unresolved)),tuple(reviewed)
