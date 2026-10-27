"""Reviewed whole-file interface roles for selected implementation dependencies.

A role records a manual scope review, never certifies behavior from a hash. All
declared symbols, explicit CLI choices, and required connection profiles must
still match. Private forward declarations are not new public/native boundaries.
Caller/helper and repository-wide obligations remain independent.
"""
import ast
from dataclasses import dataclass

from capability_c_syntax import plain_declarations
from capability_ledger import observation_identity
from capability_profile import Observation, Scan, scan_sources
from capability_wrapper import verify_definition
from capability_source import _tokens


@dataclass(frozen=True)
class SourceRoleRule:
    path: str
    sha256: str
    language: str
    symbols: tuple
    cli_argument: str | None
    cli_names: tuple
    required_profiles: tuple
    rationale: str


@dataclass(frozen=True)
class SourceRoleObservation:
    path: str
    symbols: tuple
    cli_names: tuple
    blockers: tuple
    rationale: str
    file_surface_reviewed: bool
    execution_verified: bool = False


def python_symbols(raw):
    tree=ast.parse(raw.decode('utf-8'))
    found=[]
    def walk(nodes,prefix=''):
        for node in nodes:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                name=prefix+node.name
                found.append((type(node).__name__,name))
                walk(node.body,name+'.')
    walk(tree.body)
    if len(found)!=len(set(found)):
        raise ValueError('DUPLICATE_SOURCE_SYMBOL')
    return tuple(found)


def literal_cli_choices(raw,argument):
    tree=ast.parse(raw.decode('utf-8'))
    mains=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main']
    if len(mains)!=1: raise ValueError('CLI_MAIN_NOT_UNIQUE')
    matches=[]
    for node in ast.walk(mains[0]):
        if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and
                node.func.attr=='add_argument' and node.args and
                isinstance(node.args[0],ast.Constant) and node.args[0].value==argument):
            choices=[k.value for k in node.keywords if k.arg=='choices']
            if len(choices)!=1 or not isinstance(choices[0],(ast.Tuple,ast.List)):
                raise ValueError('CLI_CHOICES_NOT_LITERAL')
            if any(not isinstance(v,ast.Constant) or type(v.value) is not str for v in choices[0].elts):
                raise ValueError('CLI_CHOICES_NOT_LITERAL')
            names=tuple(v.value for v in choices[0].elts)
            if len(set(names))!=len(names): raise ValueError('CLI_CHOICES_DUPLICATE')
            matches.append(names)
    if len(matches)!=1: raise ValueError('CLI_CHOICES_NOT_UNIQUE')
    return matches[0]


def private_header_symbols(raw):
    # These three small private dependency headers were reviewed in full. Keep
    # all non-comment tokens as well as the parsed prototypes, so a new macro,
    # typedef/callback field or directive cannot hide behind a repinned file.
    # This is an exact reviewed model, never arbitrary macro expansion.
    return (*plain_declarations(raw.decode('utf-8')),('REVIEWED_HEADER_TOKENS',_tokens(raw.decode('utf-8'))))


def observe_source_roles(sources,rules,profiles=None,ledger=None):
    scan_sources(sources,())
    files={s.path:s for s in sources}
    out=[]; profiles=profiles or {}
    for rule in rules:
        source=files.get(rule.path)
        if source is None: continue
        blockers=[]; symbols=(); names=()
        if source.sha256!=rule.sha256:
            blockers.append(('SOURCE_REVIEW_DRIFT',rule.path))
        else:
            try:
                if rule.language=='python':
                    symbols=python_symbols(source.data)
                    if rule.cli_argument is not None:
                        names=literal_cli_choices(source.data,rule.cli_argument)
                elif rule.language=='c_header':
                    symbols=private_header_symbols(source.data)
                    if rule.path=='src/common/record_internal.h':
                        for macro in ('GOLEM_RECORDED_API','GOLEM_RECORDED_REQUIRED_API','GOLEM_RECORDED_RELEASE_API'):
                            verify_definition(source.data,macro)
                else:
                    raise ValueError('SOURCE_ROLE_LANGUAGE_UNSUPPORTED')
                if symbols!=rule.symbols: blockers.append(('SOURCE_SYMBOL_SET_CHANGED',rule.path))
                if names!=rule.cli_names: blockers.append(('SOURCE_CLI_SET_CHANGED',rule.path))
            except (ValueError,UnicodeError) as error:
                blockers.append(('SOURCE_ROLE_UNSUPPORTED',str(error)))
        for required in rule.required_profiles:
            proof=profiles.get(required)
            if proof is None or proof.get('blockers'):
                blockers.append(('REQUIRED_CONNECTION_PROFILE_UNVERIFIED',required))
        for name in rule.cli_names:
            observed=[o for o in (ledger or {}).get('observations',()) if
                      (o['kind'],o['source_path'],o['entrypoint'],o['selector'])==('CLI_ROUTE',rule.path,'main',name)]
            classified=[c for c in (ledger or {}).get('capabilities',()) if c['review_status']=='REVIEWED' and
                        any(o['id'] in c['observation_ids'] for o in observed)]
            if len(observed)!=1 or not classified:
                blockers.append(('SOURCE_CLI_CLASSIFICATION_MISSING',name))
        out.append(SourceRoleObservation(rule.path,symbols,names,tuple(blockers),rule.rationale,not blockers))
    return tuple(out)


def source_role_cli_scan(sources,rules):
    # Only facts are extracted here. Profile preconditions and scope review are
    # enforced later by connect_inventory; this cannot discharge a source role.
    scan_sources(sources,())
    files={s.path:s for s in sources}; observations=[]; problems=[]
    for rule in rules:
        if rule.cli_argument is None or rule.path not in files: continue
        source=files[rule.path]
        try:
            if source.sha256!=rule.sha256: raise ValueError('SOURCE_REVIEW_DRIFT')
            names=literal_cli_choices(source.data,rule.cli_argument)
            if names!=rule.cli_names: raise ValueError('SOURCE_CLI_SET_CHANGED')
            for name in names:
                fields=dict(kind='CLI_ROUTE',source_path=rule.path,entrypoint='main',selector=name)
                observations.append(Observation(observation_identity(**fields),**fields))
        except (ValueError,UnicodeError) as error:
            problems.append((rule.path,'main',str(error)))
    return Scan(tuple(observations),tuple(problems))
