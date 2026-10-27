"""Reviewed, hash-bound lexical profiles. Internal values, never a coverage gate.

Only consumes SourceFile values from the bounded reader. No source execution,
filesystem discovery, ledger mutation or authority. Uninspected scope is explicit.
"""
from dataclasses import dataclass
import hashlib
import re

from capability_files import SourceFile, FILE_BYTES_MAX, TOTAL_BYTES_MAX, FILE_COUNT_MAX
from capability_ledger import observation_identity, validate_relative_path
from capability_source import ExtractionError, _arguments, _tokens, c_comparison_values, python_literal_names


@dataclass(frozen=True)
class Rule:
    path: str
    sha256: str
    kind: str
    entrypoint: str
    subject: str | None = None
    wrapper_definition_sha256: str | None = None
    wrapper_macro: str = "GOLEM_RECORDED_API"


@dataclass(frozen=True)
class Observation:
    id: str
    kind: str
    source_path: str
    entrypoint: str
    selector: str | None


@dataclass(frozen=True)
class Scan:
    observations: tuple
    unresolved: tuple

    @property
    def coverage_complete(self):
        # Evidence sufficiency and repository universe are not approved yet.
        return False


def _close(tokens, start):
    pairs = {'(': ')', '[': ']', '{': '}'}
    stack = []
    for pos in range(start, len(tokens)):
        token = tokens[pos]
        if token in pairs:
            stack.append(pairs[token])
        elif token in (')', ']', '}'):
            if not stack or stack.pop() != token:
                raise ExtractionError('UNBALANCED_C')
            if not stack:
                return pos
    raise ExtractionError('UNTERMINATED_C')


def _c_region(source, name, declaration):
    tokens = _tokens(source)
    found = []
    pos, boundary = 0, 0
    # Only direct file-scope declarators; macro-wrapped APIs are unresolved.
    while pos < len(tokens):
        token = tokens[pos]
        if token == name and pos + 1 < len(tokens) and tokens[pos + 1] == '(':
            end = _close(tokens, pos + 1)
            after = tokens[end + 1] if end + 1 < len(tokens) else None
            prefix = tokens[boundary:pos]
            plain_type = bool(prefix) and all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', t) or t == '*' for t in prefix)
            if declaration and after == ';' and plain_type and not set(prefix).intersection({'typedef', 'static'}):
                found.append(None)
            elif not declaration and after == '{':
                last = _close(tokens, end + 1)
                found.append(' '.join(tokens[end + 2:last]))
        if token in ('(', '[', '{'):
            pos = _close(tokens, pos) + 1
        else:
            pos += 1
        if token in (';', '{', '}'):
            boundary = pos
    if len(found) != 1:
        raise ExtractionError('ENTRYPOINT_NOT_UNIQUE_OR_UNSUPPORTED')
    return found[0]


WRAPPER_SEMANTICS = {
    'GOLEM_RECORDED_API': ('status', 'stop_on_record_begin_failure'),
    'GOLEM_RECORDED_REQUIRED_API': ('status', 'body_despite_record_begin_failure'),
    'GOLEM_RECORDED_RELEASE_API': ('void', 'release_despite_record_begin_failure'),
}


def _wrapper_parameter_name(parameter):
    """Finite declarator spelling only; never resolves a callback receiver."""
    if parameter[-2:] == ('[',']'):
        parameter=parameter[:-2]
    if '(' in parameter:
        start=parameter.index('(')
        prefix=parameter[:start]
        if (not prefix or not all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',t) or t=='*' for t in prefix) or
                parameter[start:start+2]!=('(','*') or parameter[start+3:start+5]!=(')','(') or
                not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',parameter[start+2]) or
                _close(parameter,start+4)!=len(parameter)-1):
            raise ExtractionError('WRAPPER_PARAMETERS_UNSUPPORTED')
        # Callback parameter types are opaque declarations; nested declarators,
        # attributes and evaluated array dimensions are outside this profile.
        if any(t not in (',','*') and not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',t)
               for t in parameter[start+5:-1]):
            raise ExtractionError('WRAPPER_PARAMETERS_UNSUPPORTED')
        return parameter[start+2]
    if (len(parameter)<2 or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',parameter[-1]) or
            any(not (re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',t) or t=='*') for t in parameter)):
        raise ExtractionError('WRAPPER_PARAMETERS_UNSUPPORTED')
    return parameter[-1]


def _recorded_region(source, name, macro='GOLEM_RECORDED_API'):
    if macro not in WRAPPER_SEMANTICS: raise ExtractionError('WRAPPER_UNSUPPORTED')
    count = 4 if macro == 'GOLEM_RECORDED_API' else 3
    tokens, found, pos = _tokens(source), [], 0
    while pos < len(tokens):
        if tokens[pos] == macro and pos + 1 < len(tokens) and tokens[pos+1] == '(':
            end = _close(tokens, pos+1)
            args = _arguments(tokens, pos+1)
            if args and args[0] == (name,):
                if len(args) != count or any(not a or a[0] != '(' or _close(a, 0) != len(a)-1 for a in args[1:3]):
                    raise ExtractionError('WRAPPER_ARGUMENTS_UNSUPPORTED')
                if count == 4 and (len(args[3]) != 1 or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', args[3][0])):
                    raise ExtractionError('WRAPPER_ARGUMENTS_UNSUPPORTED')
                parameters = _arguments(args[1], 0)
                arguments = _arguments(args[2], 0)
                if parameters == (('void',),):
                    expected = ((),)
                else:
                    expected = tuple((_wrapper_parameter_name(p),) for p in parameters)
                if arguments != expected or len(set(expected)) != len(expected):
                    raise ExtractionError('WRAPPER_FORWARDING_UNSUPPORTED')
                if end+1 >= len(tokens) or tokens[end+1] != '{':
                    raise ExtractionError('WRAPPER_BODY_MISSING')
                last = _close(tokens, end+1)
                found.append(' '.join(tokens[end+2:last]))
        if tokens[pos] in ('(', '[', '{'):
            pos = _close(tokens, pos)+1
        else:
            pos += 1
    if len(found) != 1:
        raise ExtractionError('WRAPPER_NOT_UNIQUE_OR_ABSENT')
    return found[0]


def _extract(source, rule):
    if rule.kind == 'C_PUBLIC_DECLARATION':
        if rule.wrapper_definition_sha256:
            _recorded_region(source, rule.entrypoint, rule.wrapper_macro)
        else:
            _c_region(source, rule.entrypoint, True)
        return (None,)
    if rule.kind in ('CLI_ROUTE', 'NATIVE_OPERATION'):
        region = (_recorded_region(source, rule.entrypoint, rule.wrapper_macro) if rule.wrapper_definition_sha256
                  else _c_region(source, rule.entrypoint, False))
        # Other constructs may still be unsupported: every C scan retains a
        # residual-scope blocker, even when these known hazards are absent.
        if any(t in ('switch', 'enum', '#') for t in _tokens(region)):
            raise ExtractionError('UNSUPPORTED_DISPATCH')
        values = c_comparison_values(region, rule.subject)
        if not values:
            raise ExtractionError('NO_LITERAL_DISPATCH')
        return values
    return python_literal_names(source, rule.entrypoint, mapping=rule.subject == 'mapping')


def scan_sources(sources, rules):
    """Extract exact registered declarations; all residual scope stays blocked.

    A rule hash is an explicit review pin, never generated here. Drift produces
    no observations for that rule. Callers cannot promote this to runtime PASS.
    """
    if not isinstance(sources, (tuple, list)) or len(sources) > FILE_COUNT_MAX:
        raise ExtractionError('SOURCE_LIMIT')
    if not isinstance(rules, (tuple, list)) or len(rules) > 16384:
        raise ExtractionError('RULE_LIMIT')
    files, total = {}, 0
    for item in sources:
        if not isinstance(item, SourceFile):
            raise ExtractionError('INVALID_SOURCE')
        validate_relative_path(item.path)
        if item.path in files or type(item.data) is not bytes:
            raise ExtractionError('INVALID_SOURCE')
        total += len(item.data)
        if len(item.data) > FILE_BYTES_MAX or total > TOTAL_BYTES_MAX:
            raise ExtractionError('SOURCE_LIMIT')
        if hashlib.sha256(item.data).hexdigest() != item.sha256:
            raise ExtractionError('SOURCE_DIGEST_MISMATCH')
        files[item.path] = item
    seen, observations, unresolved, registered = set(), [], [], set()
    for rule in rules:
        if not isinstance(rule, Rule):
            raise ExtractionError('INVALID_RULE')
        validate_relative_path(rule.path)
        if not isinstance(rule.sha256, str) or not re.fullmatch('[0-9a-f]{64}', rule.sha256):
            raise ExtractionError('INVALID_RULE_HASH')
        if not isinstance(rule.entrypoint, str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', rule.entrypoint):
            raise ExtractionError('INVALID_ENTRYPOINT')
        if rule.kind == 'C_PUBLIC_DECLARATION':
            valid = rule.subject is None
        elif rule.kind in ('CLI_ROUTE', 'NATIVE_OPERATION'):
            valid = isinstance(rule.subject, str) and 0 < len(rule.subject.encode('utf-8')) <= 4096
        elif rule.kind in ('PYTHON_DECLARATION', 'MCP_TOOL_DECLARATION'):
            valid = rule.subject in ('mapping', 'sequence')
        else:
            valid = False
        if not valid or rule in seen:
            raise ExtractionError('INVALID_OR_DUPLICATE_RULE')
        if rule.wrapper_macro not in WRAPPER_SEMANTICS or (rule.wrapper_macro != 'GOLEM_RECORDED_API' and not rule.wrapper_definition_sha256):
            raise ExtractionError('WRAPPER_RULE_INVALID')
        if rule.wrapper_definition_sha256 is not None:
            if rule.kind not in ('NATIVE_OPERATION','C_PUBLIC_DECLARATION') or not isinstance(rule.wrapper_definition_sha256, str) or not re.fullmatch('[0-9a-f]{64}', rule.wrapper_definition_sha256):
                raise ExtractionError('WRAPPER_RULE_INVALID')
        seen.add(rule)
        registered.add(rule.path)
        key = (rule.path, rule.entrypoint)
        item = files.get(rule.path)
        if item is None:
            unresolved.append((*key, 'SOURCE_NOT_SELECTED'))
            continue
        if item.sha256 != rule.sha256:
            unresolved.append((*key, 'SOURCE_REVIEW_DRIFT'))
            continue
        if rule.wrapper_definition_sha256:
            definition = files.get('src/common/record_internal.h')
            if definition is None or definition.sha256 != rule.wrapper_definition_sha256:
                unresolved.append((*key, 'WRAPPER_DEFINITION_MISSING_OR_DRIFT'))
                continue
            from capability_wrapper import verify_definition
            try:
                verify_definition(definition.data, rule.wrapper_macro)
            except (UnicodeError, ExtractionError):
                unresolved.append((*key, 'WRAPPER_DEFINITION_UNSUPPORTED'))
                continue
        try:
            source = item.data.decode('utf-8', errors='strict')
            values = _extract(source, rule)
        except (UnicodeError, ExtractionError) as error:
            reason = str(error) if isinstance(error, ExtractionError) else 'SOURCE_NOT_UTF8'
            unresolved.append((*key, reason))
            continue
        if len(observations) + len(values) > 16384:
            raise ExtractionError('OBSERVATION_LIMIT')
        for selector in values:
            fields = dict(kind=rule.kind, source_path=rule.path, entrypoint=rule.entrypoint, selector=selector)
            observations.append(Observation(observation_identity(**fields), **fields))
        unresolved.append((*key, 'DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED' if rule.kind in
                           ('PYTHON_DECLARATION', 'MCP_TOOL_DECLARATION') else 'C_RESIDUAL_SCOPE_UNVERIFIED'))
    for path in files:
        if path not in registered:
            unresolved.append((path, None, 'UNREGISTERED_SOURCE'))
    ids = [item.id for item in observations]
    if len(ids) != len(set(ids)):
        raise ExtractionError('DUPLICATE_OBSERVATION')
    return Scan(tuple(observations), tuple(unresolved))
