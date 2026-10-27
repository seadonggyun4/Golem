"""Shared finite C declaration observations, without preprocessing.

Only plain file-scope prototypes (including literal extern "C" groups) are
supported. Bodies, typedefs, initializers and function pointers are not APIs.
Conditional branches remain lexical alternatives; this is not an ABI checker.
"""
import re
from dataclasses import dataclass

from capability_source import ExtractionError, _tokens
from capability_profile import _close
from capability_source import _arguments

CAST_TYPES = frozenset(('void','char','short','int','long','signed','unsigned','float','double','bool',
    'size_t','ssize_t','int8_t','int16_t','int32_t','int64_t','uint8_t','uint16_t','uint32_t','uint64_t',
    'lookup','golem_document_freshness'))
CONTROL_WORDS = frozenset(('if','for','while','switch','sizeof','_Alignof','return','do','case'))


@dataclass(frozen=True)
class CCall:
    expression: tuple
    arguments: tuple
    position: int
    indirect: bool


def call_sites(body,cast_types=CAST_TYPES):
    """Direct/member calls and unresolved computed calls; casts are not calls.

    Only the finite registered cast spelling is supported. No typedef inference,
    pointer target resolution or macro expansion is performed.
    """
    t=_tokens(body); stack=[]; opening={};out=[]
    for i,v in enumerate(t):
        if v in ('(','[','{'):stack.append(i)
        elif v in (')',']','}'):
            if not stack: raise ExtractionError('UNBALANCED_C')
            opening[i]=stack.pop()
    if stack: raise ExtractionError('UNBALANCED_C')
    for i,v in enumerate(t[:-1]):
        if t[i+1]!='(':continue
        if re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',v):
            if v in CONTROL_WORDS or v in ('void','char','short','int','long','signed','unsigned','float','double','_Bool'):
                continue
            start=i
            while start>=2:
                if t[start-1]=='.' and re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',t[start-2]):start-=2
                elif start>=3 and t[start-2:start]==('-','>') and re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',t[start-3]):start-=3
                else:break
            out.append(CCall(t[start:i+1],_arguments(t,i+1),i,start!=i))
        elif v in (')',']'):
            start=opening[i];inside=t[start+1:i]
            if start and t[start-1] in CONTROL_WORDS:continue
            qualifiers=('const','volatile','restrict')
            base=[x for x in inside if x not in ('*',*qualifiers)]
            first=next((x for x in inside if x not in qualifiers),None)
            star=inside.index('*') if '*' in inside else len(inside)
            if (v==')' and first in cast_types and base and all(x in cast_types for x in base) and
                    all(x in ('*',*qualifiers) for x in inside[star:])):continue
            out.append(CCall(t[start:i+1],_arguments(t,i+1),i,True))
    return tuple(out)


def declaration_tokens(source, target=None):
    # Remove comments before recognizing line directives, preserving newlines.
    # Quoted strings/chars are consumed first so comment markers in them survive.
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*'
    def uncomment(match):
        text = match.group()
        return ''.join('\n' if c == '\n' else ' ' for c in text) if text.startswith(('/',)) else text
    source = re.sub(pattern, uncomment, source, flags=re.S)
    lines, directive = [], ''
    for line in source.splitlines():
        if directive or line.lstrip().startswith('#'):
            directive += line + '\n'
            if not line.rstrip().endswith('\\'):
                if target is not None and _tokens(directive)[:2]==('#','define') and target in _tokens(directive):
                    raise ExtractionError('MACRO_DECLARATION')
                directive = ''
            lines.append('')
        else:
            lines.append(line)
    if directive:
        raise ExtractionError('UNTERMINATED_DIRECTIVE')
    return _tokens('\n'.join(lines))


def plain_declarations(source, target=None):
    tokens = declaration_tokens(source, target)
    def declarations(tokens):
        found, pos, boundary = [], 0, 0
        while pos < len(tokens):
            if tokens[pos:pos+3] == ('extern', '"C"', '{'):
                end = _close(tokens, pos+2)
                found.extend(declarations(tokens[pos+3:end]))
                pos = boundary = end+1
                continue
            if (re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', tokens[pos]) and
                    tokens[pos+1:pos+2] == ('(',)):
                end = _close(tokens, pos+1)
                prefix = tokens[boundary:pos]
                plain = bool(prefix) and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', t) or t == '*' for t in prefix)
                if plain and not set(prefix) & {'static', 'typedef', 'return'} and tokens[end+1:end+2] == (';',):
                    found.append((tokens[pos], prefix, tokens[pos+2:end]))
            token = tokens[pos]
            if token in ('(', '[', '{'):
                pos = _close(tokens, pos)+1
            else:
                pos += 1
            if token == ';':
                boundary = pos
            # A function body is a complete top-level unit. Struct/enum suffixes
            # are left attached until ';', so they cannot become prototypes.
            elif token == '{' and tokens[boundary:pos].count('typedef') == 0:
                boundary = pos
        return found
    return tuple(declarations(tokens))


def public_declaration(raw, name):
    declarations = [d for d in plain_declarations(raw.decode('utf-8'), name) if d[0] == name]
    if len(declarations) != 1:
        raise ExtractionError('PUBLIC_DECLARATION_NOT_UNIQUE_OR_UNSUPPORTED')
    return declarations[0]


def plain_definitions(source, target=None):
    """Direct file-scope definitions only; named recorder wrappers are separate."""
    tokens=declaration_tokens(source,target)
    found=[]; pos=boundary=0
    while pos<len(tokens):
        if re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',tokens[pos]) and tokens[pos+1:pos+2]==('(',):
            end=_close(tokens,pos+1)
            prefix=tokens[boundary:pos]
            plain=bool(prefix) and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',t) or t=='*' for t in prefix)
            if plain and 'typedef' not in prefix and tokens[end+1:end+2]==('{',):
                last=_close(tokens,end+1)
                found.append((tokens[pos],prefix,tokens[pos+2:end],tokens[end+2:last]))
        token=tokens[pos]
        if token in ('(','[','{'): pos=_close(tokens,pos)+1
        else: pos+=1
        if token in (';','{'): boundary=pos
    return tuple(found)
