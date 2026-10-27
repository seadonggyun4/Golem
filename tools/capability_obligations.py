"""Make residual selected-function obligations inspectable, without discharging them.

Direct call names/arguments are observations, not policy, dataflow, reachability
or execution proofs. No source lookup follows a call; only supplied bytes are
used. An unknown call remains a review obligation even when its name looks safe.
"""
import ast
import re
from dataclasses import dataclass

from capability_profile import _c_region, _recorded_region, scan_sources
from capability_source import _arguments, _tokens
from capability_public import scan_public_headers
from capability_public_registry import PUBLIC_HEADERS


@dataclass(frozen=True)
class ScopeObligation:
    path: str
    entrypoint: str | None
    reason: str
    selectors: tuple
    direct_calls: tuple
    public_api_calls: tuple
    helper_or_external_calls_requiring_review: tuple
    declarations: tuple
    unsupported: tuple
    discharged: bool = False


def _direct_calls(body):
    from capability_c_syntax import call_sites
    tokens = _tokens(body)
    calls, unsupported = [], []
    if '#' in tokens:
        unsupported.append('PREPROCESSOR_BODY')
    for site in call_sites(body):
        if site.indirect:unsupported.append('INDIRECT_CALL')
        else:calls.append((site.expression[0],tuple(' '.join(a) for a in site.arguments)))
    return tuple(calls), tuple(sorted(set(unsupported)))


def residual_obligations(sources, rules, scan):
    scan_sources(sources, ())
    files = {s.path:s for s in sources}
    registered = {(r.path,r.entrypoint):r for r in rules}
    public = scan_public_headers(sources, PUBLIC_HEADERS)
    names = {o.entrypoint for o in public.observations}
    output = []
    for path, entrypoint, reason in scan.unresolved:
        source = files.get(path)
        calls, unsupported, declarations = (), (), ()
        if source is not None:
            try:
                if entrypoint is not None and (path,entrypoint) in registered and path.endswith('.c'):
                    rule = registered[path,entrypoint]
                    if source.sha256 != rule.sha256:
                        raise ValueError('SOURCE_REVIEW_DRIFT')
                    body = (_recorded_region(source.data.decode(),entrypoint,rule.wrapper_macro)
                            if rule.wrapper_definition_sha256 else _c_region(source.data.decode(),entrypoint,False))
                    calls, unsupported = _direct_calls(body)
                elif path.endswith('.py'):
                    tree = ast.parse(source.data.decode())
                    found = []
                    for node in tree.body:
                        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                            found.append(node.name)
                        elif isinstance(node,ast.ClassDef):
                            found.extend(node.name+'.'+child.name for child in node.body
                                         if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)))
                    declarations = tuple(found)
                elif path.endswith('.h'):
                    from capability_c_syntax import plain_declarations
                    declarations = tuple(d[0] for d in plain_declarations(source.data.decode()))
            except (ValueError,UnicodeError) as error:
                unsupported = (str(error),)
        selectors = tuple(sorted({o.selector for o in scan.observations
                                  if (o.source_path,o.entrypoint)==(path,entrypoint) and o.selector is not None}))
        native = tuple(sorted({name for name,_ in calls if name in names}))
        remaining = tuple(sorted({name for name,_ in calls if name not in names}))
        output.append(ScopeObligation(path,entrypoint,reason,selectors,calls,native,remaining,declarations,unsupported))
    return tuple(output)
