"""Public declaration to one pinned direct/native-wrapper definition.

Definition presence and exact declared parameter tokens are structural evidence,
not implementation correctness, callback receiver resolution or feature PASS.
No native implementation call graph is followed beyond this reviewed boundary.
"""
from dataclasses import dataclass
import hashlib
import json

from capability_c_syntax import plain_definitions, public_declaration
from capability_profile import scan_sources, _recorded_region, _close
from capability_source import _tokens, _arguments
from capability_wrapper import verify_definition


@dataclass(frozen=True)
class NativeDefinitionRule:
    name: str
    path: str
    sha256: str
    header_path: str
    header_sha256: str
    wrapper: str | None
    parameters_sha256: str


@dataclass(frozen=True)
class NativeDefinitionObservation:
    name: str
    declaration_path: str
    definition_path: str
    wrapper: str | None
    blockers: tuple
    behavior_verified: bool=False
    callback_receiver_verified: bool=False
    execution_verified: bool=False


def parameter_digest(tokens):
    return hashlib.sha256(json.dumps(tuple(tokens),ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def inspect_native_definitions(sources,rules,wrapper_sha256):
    scan_sources(sources,())
    files={s.path:s for s in sources}; parsed={}; output=[];seen=set()
    for rule in rules:
        if not isinstance(rule,NativeDefinitionRule) or rule.name in seen:
            raise ValueError('NATIVE_DEFINITION_RULE_DUPLICATE_OR_INVALID')
        seen.add(rule.name); errors=[]
        for path,pin in ((rule.path,rule.sha256),(rule.header_path,rule.header_sha256)):
            if path not in files or files[path].sha256!=pin: errors.append(('SOURCE_MISSING_OR_DRIFT',path))
        if not rule.header_path.startswith('include/golem/'):
            errors.append(('PRIVATE_DECLARATION_NOT_NATIVE_BOUNDARY',rule.header_path))
        if not errors:
            try:
                public_declaration(files[rule.header_path].data,rule.name)
                source=files[rule.path].data.decode('utf-8')
                if rule.wrapper is None:
                    if rule.path not in parsed: parsed[rule.path]=plain_definitions(source)
                    matches=[d for d in parsed[rule.path] if d[0]==rule.name]
                    if len(matches)!=1: raise ValueError('DIRECT_DEFINITION_NOT_UNIQUE')
                    parameters=matches[0][2]
                else:
                    definition=files.get('src/common/record_internal.h')
                    if definition is None or definition.sha256!=wrapper_sha256:
                        raise ValueError('WRAPPER_DEFINITION_MISSING_OR_DRIFT')
                    verify_definition(definition.data,rule.wrapper)
                    _recorded_region(source,rule.name,rule.wrapper)
                    tokens=_tokens(source); matches=[]
                    for i,t in enumerate(tokens[:-1]):
                        if t==rule.wrapper and tokens[i+1]=='(':
                            args=_arguments(tokens,i+1)
                            if args[0]==(rule.name,): matches.append(args[1][1:-1])
                    if len(matches)!=1: raise ValueError('WRAPPER_NOT_UNIQUE')
                    parameters=matches[0]
                if parameter_digest(parameters)!=rule.parameters_sha256:
                    raise ValueError('DEFINITION_PARAMETERS_CHANGED')
            except (ValueError,UnicodeError) as error:
                errors.append(('NATIVE_DEFINITION_UNSUPPORTED',str(error)))
        output.append(NativeDefinitionObservation(rule.name,rule.header_path,rule.path,rule.wrapper,tuple(errors)))
    return tuple(output)
