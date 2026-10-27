"""Explicit C if/return dispatcher edges. No preprocessing or call execution."""
from dataclasses import dataclass
from capability_profile import scan_sources,_c_region,_close
from capability_source import _tokens,_arguments,c_comparison_values,ExtractionError
from capability_c_syntax import public_declaration,plain_definitions,declaration_tokens

@dataclass(frozen=True)
class CEdgeRule:
    caller_path: str
    caller_sha256: str
    caller: str
    subject: str
    callee_path: str
    callee_sha256: str
    declaration_path: str
    declaration_sha256: str
    callee: str

@dataclass(frozen=True)
class CEdgeObservation:
    caller: str
    callee: str
    conditions: tuple
    selectors: tuple
    blockers: tuple
    execution_verified: bool=False
    transitive_verified: bool=False


def _cli_declaration(source, name):
    # Exact CLI prototype, top level. Ignore surrounding declaration prefixes,
    # not preprocessor semantics; no macro expansion or compile claim.
    _, prefix, parameters = public_declaration(source.encode('utf-8'), name)
    if prefix != ('int',) or _arguments(('(', *parameters, ')'), 0) != (('int','argc'),('char','*','*','argv')):
        raise ExtractionError('CLI_PROTOTYPE_UNSUPPORTED_OR_NONUNIQUE')


def _positive_condition(tokens,subject):
    """Finite CLI predicate grammar, not general C expression/dataflow analysis."""
    import re
    while tokens[:1] == ('(',) and _close(tokens,0) == len(tokens)-1:
        tokens = tokens[1:-1]
    for operator in (('|','|'), ('&','&')):
        pos = 0
        while pos < len(tokens):
            if tokens[pos] in ('(', '[', '{'):
                pos = _close(tokens,pos)+1
            elif tokens[pos:pos+2] == operator:
                left=_positive_condition(tokens[:pos],subject)
                right=_positive_condition(tokens[pos+2:],subject)
                # None is the unrestricted domain for this explicit subject.
                # Every disjunct must restrict it; a mere argc guard cannot
                # establish the advertised route.
                if operator==('|','|'):
                    return None if left is None or right is None else left|right
                return right if left is None else left if right is None else left&right
            else:
                pos += 1
    if re.fullmatch(r'argc(>=|==|>|<=|<)[0-9]+', ''.join(tokens)):
        return None
    call = tokens[1:] if tokens[:1] == ('!',) else tokens
    if call[:2] != ('strcmp','('):
        raise ExtractionError('CONDITION_UNSUPPORTED')
    end = _close(call,1)
    suffix = call[end+1:]
    if (tokens[:1] == ('!',) and suffix) or (tokens[:1] != ('!',) and suffix != ('=','=','0')):
        raise ExtractionError('NONPOSITIVE_SELECTOR_CONDITION')
    args = _arguments(call,1)
    if len(args) != 2:
        raise ExtractionError('CONDITION_UNSUPPORTED')
    # Both argument orders are supported, but only an argv slot and literal text.
    pair = args if args[0][:1] == ('argv',) else tuple(reversed(args))
    if not re.fullmatch(r'argv\[[1-9][0-9]*\]', ''.join(pair[0])):
        raise ExtractionError('CONDITION_UNSUPPORTED')
    values=c_comparison_values(' '.join(call[:end+1]), ' '.join(pair[0]))
    if not values:
        raise ExtractionError('CONDITION_UNSUPPORTED')
    return frozenset(values) if pair[0]==subject else None


def inspect_c_edge(sources,rule):
    scan_sources(sources,())
    if not isinstance(rule,CEdgeRule): raise ValueError('EDGE_RULE')
    files={s.path:s for s in sources}; errors=[]
    for path,pin in ((rule.caller_path,rule.caller_sha256),(rule.callee_path,rule.callee_sha256),
                     (rule.declaration_path,rule.declaration_sha256)):
        if path not in files or files[path].sha256!=pin: errors.append(('SOURCE_MISSING_OR_DRIFT',path))
    if errors: return CEdgeObservation(rule.caller,rule.callee,(),(),tuple(errors))
    try:
        _cli_declaration(files[rule.declaration_path].data.decode(),rule.callee)
        for name in ('strcmp',rule.callee):
            declaration_tokens(files[rule.caller_path].data.decode(),name)
        definitions=[d for d in plain_definitions(files[rule.callee_path].data.decode(),rule.callee) if d[0]==rule.callee]
        if len(definitions)!=1 or definitions[0][1]!=('int',) or _arguments(('(',*definitions[0][2],')'),0)!=(('int','argc'),('char','*','*','argv')):
            raise ExtractionError('CLI_DEFINITION_SIGNATURE_UNSUPPORTED')
        tokens=_tokens(_c_region(files[rule.caller_path].data.decode(),rule.caller,False))
        conditions=[];selectors=[];covered=set()
        # Narrow profile: direct if(condition) return callee(argc,argv); only.
        # Braced, nested or indirect forms remain unmatched, never guessed.
        depth=0
        for i,t in enumerate(tokens):
            if t=='{': depth+=1
            elif t=='}': depth-=1
            if t!='if' or i+1>=len(tokens) or tokens[i+1]!='(': continue
            if depth: continue
            end=_close(tokens,i+1)
            if tuple(tokens[end+1:end+4])!=('return',rule.callee,'('): continue
            call=end+3; finish=_close(tokens,call)
            if _arguments(tokens,call)!=(('argc',),('argv',)) or tokens[finish+1:finish+2]!=(';',):
                errors.append(('ARGUMENT_FORWARDING_UNSUPPORTED',rule.callee));continue
            condition=' '.join(tokens[i+2:end])
            domain=_positive_condition(tokens[i+2:end],_tokens(rule.subject))
            values=c_comparison_values(condition,rule.subject)
            if not values: errors.append(('LITERAL_CONDITION_MISSING',rule.callee));continue
            if domain is None or not domain or domain!=frozenset(values):
                errors.append(('SELECTOR_NOT_REQUIRED_OR_CONTRADICTORY',rule.callee));continue
            if any(v in ('#','switch','?') for v in tokens[i+2:end]):
                errors.append(('CONDITION_UNSUPPORTED',rule.callee));continue
            covered.add(end+2);conditions.append(condition);selectors.extend(values)
        occurrences={i for i,t in enumerate(tokens) if t==rule.callee}
        if not conditions or occurrences!=covered: errors.append(('DIRECT_RETURN_SCOPE_UNRESOLVED',rule.callee))
        return CEdgeObservation(rule.caller,rule.callee,tuple(conditions),tuple(sorted(set(selectors))),tuple(errors))
    except (ValueError,UnicodeError,IndexError) as error:
        return CEdgeObservation(rule.caller,rule.callee,(),(),(('PROFILE_UNSUPPORTED',str(error)),))
