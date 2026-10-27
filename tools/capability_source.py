"""Pure M0 extraction primitives, not a capability ledger or authority source.

No imports of inspected programs, filesystem scans, subprocesses or MCP changes.
C observations are lexical across preprocessor branches, not compiled semantics.
Callers select a reviewed subject; absence is never proof of complete dispatch.
The ledger schema, source scope and production scan bounds remain separate decisions.
"""
import ast
import json
import re


class ExtractionError(ValueError):
    pass


def _tokens(source):
    """Tokenize enough C to separate identifiers, literals and comments safely.

    Not a C parser: unsupported literals are rejected when used as selectors.
    Unterminated comments/strings fail rather than returning a partial result.
    """
    result, i = [], 0
    while i < len(source):
        if source[i].isspace():
            i += 1
        elif source.startswith('//', i):
            end = source.find('\n', i + 2)
            i = len(source) if end < 0 else end + 1
        elif source.startswith('/*', i):
            end = source.find('*/', i + 2)
            if end < 0:
                raise ExtractionError('UNTERMINATED_COMMENT')
            i = end + 2
        elif source[i] in ('"', "'"):
            start, quote = i, source[i]
            i += 1
            while i < len(source) and source[i] != quote:
                if source[i] == '\n':
                    raise ExtractionError('UNTERMINATED_LITERAL')
                if source[i] == '\\':
                    i += 1
                i += 1
            if i >= len(source):
                raise ExtractionError('UNTERMINATED_LITERAL')
            i += 1
            result.append(source[start:i])
        elif source[i].isascii() and (source[i].isalpha() or source[i] == '_'):
            end = i + 1
            while end < len(source) and source[end].isascii() and (source[end].isalnum() or source[end] == '_'):
                end += 1
            result.append(source[i:end])
            i = end
        else:
            result.append(source[i])
            i += 1
    return tuple(result)


def _arguments(tokens, start):
    arguments, current, stack = [], [], []
    pairs = {')': '(', ']': '[', '}': '{'}
    for pos in range(start + 1, len(tokens)):
        token = tokens[pos]
        if token == ')' and not stack:
            return (*arguments, tuple(current))
        if token == ',' and not stack:
            arguments.append(tuple(current))
            current = []
            continue
        if token in ('(', '[', '{'):
            stack.append(token)
        elif token in pairs:
            if not stack or stack.pop() != pairs[token]:
                raise ExtractionError('UNBALANCED_COMPARISON')
        current.append(token)
    raise ExtractionError('UNTERMINATED_COMPARISON')


def c_comparison_values(source, subject):
    """Literal strcmp values for one explicit expression, in deterministic order.

    Supports either argument order, comments, whitespace and adjacent ordinary
    string literals. JSON-compatible C escapes only. Macros, casts, aliases,
    switch/enum dispatch and preprocessing are outside this primitive's scope.
    A computed strcmp comparand or strncmp on this subject blocks extraction.
    """
    tokens, selected = _tokens(source), _tokens(subject)
    if not selected:
        raise ExtractionError('EMPTY_SUBJECT')
    values = set()
    for pos, token in enumerate(tokens[:-1]):
        if token not in ('strcmp', 'strncmp') or tokens[pos + 1] != '(':
            continue
        args = _arguments(tokens, pos + 1)
        if selected not in args:
            continue
        if token != 'strcmp' or len(args) != 2 or args.count(selected) != 1:
            raise ExtractionError('UNSUPPORTED_COMPARISON')
        other = args[1] if args[0] == selected else args[0]
        if not other or any(not t.startswith('"') for t in other):
            raise ExtractionError('NON_LITERAL_COMPARAND')
        try:
            value = ''.join(json.loads(t) for t in other)
        except (ValueError, TypeError) as error:
            raise ExtractionError('UNSUPPORTED_C_ESCAPE') from error
        if not value or not value.isascii() or not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
            raise ExtractionError('UNSUPPORTED_SELECTOR')
        values.add(value)
    return tuple(sorted(values))


def python_literal_names(source, assignment, *, mapping):
    """Read explicit top-level mapping keys or tuple/list names without execution.

    A mapping's values may be arbitrary AST expressions and are never evaluated.
    Duplicate keys/names, unpacking and nonliteral/computed names are rejected.
    Later dynamic mutations are not analyzed: this is declaration observation,
    not a claim about tools/list or runtime behavior.
    """
    try:
        module = ast.parse(source)
    except SyntaxError as error:
        raise ExtractionError('PYTHON_SYNTAX') from error
    matches = []
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == assignment for t in node.targets):
            matches.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == assignment:
            matches.append(node.value)
    if len(matches) != 1:
        raise ExtractionError('ASSIGNMENT_NOT_UNIQUE')
    value = matches[0]
    if mapping and isinstance(value, ast.Dict):
        nodes = value.keys
    elif not mapping and isinstance(value, (ast.Tuple, ast.List)):
        nodes = value.elts
    else:
        raise ExtractionError('UNSUPPORTED_DECLARATION')
    names = []
    for node in nodes:
        if not isinstance(node, ast.Constant) or type(node.value) is not str:
            raise ExtractionError('NON_LITERAL_NAME')
        if not re.fullmatch(r'[a-z][a-z0-9_]*', node.value):
            raise ExtractionError('UNSUPPORTED_NAME')
        names.append(node.value)
    if len(set(names)) != len(names):
        raise ExtractionError('DUPLICATE_NAME')
    return tuple(sorted(names))


def observation_difference(expected, observed):
    """Compare names only; an empty difference is not reviewed feature coverage.

    No defaults, wildcard exclusions or automatic reclassification. Duplicates
    fail, so a lossy set conversion cannot hide a broken upstream extraction.
    """
    for names in (expected, observed):
        if not isinstance(names, (tuple, list)) or any(type(n) is not str or not n for n in names):
            raise ExtractionError('INVALID_NAMES')
        if len(names) != len(set(names)):
            raise ExtractionError('DUPLICATE_OBSERVATION')
    return tuple(sorted(set(observed) - set(expected))), tuple(sorted(set(expected) - set(observed)))
