"""Finite reviewed C call closure ending at public API/capability boundaries."""
import re
from dataclasses import dataclass
from capability_profile import scan_sources,_c_region,_close
from capability_source import _tokens,c_comparison_values
from capability_c_syntax import public_declaration,declaration_tokens,call_sites

# Named external boundaries require an explicit library/header review. This is
# not symbol resolution, runtime receiver identity or a safety/success claim.
EXTERNAL_C_BOUNDARIES = {
    'strcmp': ('ISO_C','string.h'), 'strlen': ('ISO_C','string.h'),
    'malloc': ('ISO_C','stdlib.h'), 'free': ('ISO_C','stdlib.h'),
    'fwrite': ('ISO_C','stdio.h'), 'fflush': ('ISO_C','stdio.h'),
    'fprintf': ('ISO_C','stdio.h'),
}

@dataclass(frozen=True)
class NativeBoundary:
    name: str
    path: str
    sha256: str
    capability: str

@dataclass(frozen=True)
class ScopeRule:
    path: str
    sha256: str
    function: str
    subject: str | None
    selectors: tuple
    calls: tuple
    external: tuple
    native: tuple
    helpers: tuple

@dataclass(frozen=True)
class Closure:
    function: str
    calls: tuple
    native: tuple
    external: tuple
    blockers: tuple
    execution_verified: bool=False


def inspect_closure(sources,ledger,rule,stack=()):
    scan_sources(sources,())
    files={s.path:s for s in sources}; blockers=[]
    key=(rule.path,rule.function)
    if key in stack: return Closure(rule.function,(),(),(),(('HELPER_CYCLE',key),))
    source=files.get(rule.path)
    if source is None or source.sha256!=rule.sha256:
        return Closure(rule.function,(),(),(),(('SOURCE_MISSING_OR_DRIFT',rule.path),))
    try:
        body=_c_region(source.data.decode(),rule.function,False);tokens=_tokens(body)
        if '#' in tokens: raise ValueError('PREPROCESSOR_BODY')
        sites=call_sites(body)
        if any(s.indirect for s in sites):raise ValueError('INDIRECT_CALL')
        calls=[s.expression[0] for s in sites]
        actual=tuple(sorted(set(calls)))
        if actual!=tuple(sorted(rule.calls)):blockers.append(('CALL_SET_CHANGED',actual))
        if rule.subject and c_comparison_values(body,rule.subject)!=tuple(sorted(rule.selectors)):
            blockers.append(('SELECTOR_SET_CHANGED',rule.function))
        covered=set(rule.external)|{n.name for n in rule.native}|{h.function for h in rule.helpers}
        if covered!=set(rule.calls):blockers.append(('BOUNDARY_SET_MISMATCH',rule.function))
        categories=[set(rule.external),{n.name for n in rule.native},{h.function for h in rule.helpers}]
        if any(a&b for i,a in enumerate(categories) for b in categories[i+1:]):
            blockers.append(('BOUNDARY_CATEGORY_OVERLAP',rule.function))
        for name in rule.external:
            if name not in EXTERNAL_C_BOUNDARIES:
                blockers.append(('EXTERNAL_BOUNDARY_UNREGISTERED',name))
        for name in rule.calls:
            declaration_tokens(source.data.decode(),name)
        for native in rule.native:
            if not native.path.startswith('include/golem/'):
                blockers.append(('PRIVATE_DECLARATION_NOT_NATIVE_BOUNDARY',native.path));continue
            f=files.get(native.path)
            if f is None or f.sha256!=native.sha256:
                blockers.append(('PUBLIC_SOURCE_MISSING_OR_DRIFT',native.path));continue
            public_declaration(f.data,native.name)
            obs=[o for o in ledger['observations'] if o['kind']=='C_PUBLIC_DECLARATION' and o['source_path']==native.path and o['entrypoint']==native.name]
            caps=[c for c in ledger['capabilities'] if c['id']==native.capability and c['review_status']=='REVIEWED' and c['implementation']=='IMPLEMENTED']
            if len(obs)!=1 or len(caps)!=1 or obs[0]['id'] not in caps[0]['observation_ids']:
                blockers.append(('PUBLIC_CAPABILITY_UNBOUND',native.name))
        for helper in rule.helpers:
            child=inspect_closure(sources,ledger,helper,(*stack,key))
            blockers.extend(('HELPER_UNRESOLVED',(helper.function,b)) for b in child.blockers)
        return Closure(rule.function,actual,tuple(n.name for n in rule.native),rule.external,tuple(blockers))
    except (ValueError,UnicodeError,IndexError) as error:
        return Closure(rule.function,(),(),(),(('CLOSURE_UNSUPPORTED',str(error)),))
