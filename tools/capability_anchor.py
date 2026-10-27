"""Conservative explicit-anchor Markdown profile; not a Markdown renderer.

Only standalone empty <a id="…"></a>/<a name="…"></a> elements are verified.
Unsupported HTML/container contexts fail closed instead of guessing rendering.
"""
import re

_ANCHOR = re.compile(r' {0,3}<a (?:id|name)="([^"&<>\s]+)"></a>[ \t]*')
_FENCE = re.compile(r' {0,3}(`{3,}|~{3,})(.*)')


def markdown_anchor(raw, anchor):
    if anchor is None:
        return None, 'ANCHOR_UNSPECIFIED'
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeError:
        return None, 'MARKDOWN_NOT_UTF8'
    if not anchor or any(c.isspace() or c in '&<>"' for c in anchor):
        return None, 'ANCHOR_UNSUPPORTED'
    matches, fence, comment, unsupported = [], None, False, False
    for number, line in enumerate(text.splitlines(), 1):
        if fence is not None:
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(fence[1]) + r',}[ \t]*', line):
                fence = None
            continue
        # Comments are masked without changing surrounding indentation.
        visible, pos = '', 0
        while pos < len(line):
            if comment:
                end = line.find('-->', pos)
                if end < 0:
                    visible += ' ' * (len(line) - pos)
                    break
                visible += ' ' * (end + 3 - pos)
                pos, comment = end + 3, False
            else:
                start = line.find('<!--', pos)
                if start < 0:
                    visible += line[pos:]
                    break
                visible += line[pos:start]
                pos, comment = start + 4, True
                visible += ' ' * 4
        opening = _FENCE.fullmatch(visible)
        if opening:
            run, info = opening.groups()
            if run[0] == '`' and '`' in info:
                unsupported = True
            else:
                fence = (run[0], len(run))
            continue
        if visible.startswith(('    ', '\t')):
            # Indentation alone is not proof of a code block (e.g. paragraph
            # continuation). Do not silently discard a possible duplicate.
            if '<' in visible:
                unsupported = True
            continue
        candidate = _ANCHOR.fullmatch(visible)
        if candidate:
            if candidate[1] == anchor:
                matches.append(number)
            continue
        # Ignore complete inline code spans; unmatched/multiline spans stay
        # unresolved, as do HTML blocks, escaped anchors and nested containers.
        cursor, outside = 0, ''
        while cursor < len(visible):
            if visible[cursor] != '`':
                outside += visible[cursor]
                cursor += 1
                continue
            end = cursor
            while end < len(visible) and visible[end] == '`':
                end += 1
            marker = visible[cursor:end]
            closing = re.search(r'(?<!`)'+re.escape(marker)+r'(?!`)', visible[end:])
            if closing is None:
                unsupported = True
                break
            cursor = end + closing.end()
        if '<' in outside or re.match(r' {0,3}(?:>|[-+*] |[0-9]+[.)] )', outside):
            unsupported = True
    if comment or fence is not None or unsupported:
        return None, 'MARKDOWN_CONTEXT_UNSUPPORTED'
    if len(matches) != 1:
        return None, 'ANCHOR_NOT_UNIQUE_OR_ABSENT'
    return matches[0], None
