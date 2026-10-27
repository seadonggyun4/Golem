"""Selected reference-file observations, not test execution or evidence acceptance.

Uses the existing bounded source reader unchanged. No automatic selection,
runtime import, approval or ledger writes. Explicit Markdown anchors and Python
declarations are syntactic observations only. Python selectors
identify direct declarations only, never collected or executed tests.
"""
import ast
import keyword
from dataclasses import dataclass

from capability_anchor import markdown_anchor
from capability_files import read_sources, SourceReadError
from capability_ledger import validate_metadata_fields, _decoded_limits


@dataclass(frozen=True)
class ReferenceObservation:
    capability_id: str
    kind: str
    path: str
    locator: str | None
    file_bytes_verified: bool
    observed_sha256: str | None
    byte_length: int | None
    diagnostic: str | None
    locator_unverified: bool = True
    execution_unverified: bool = True
    sufficiency_unverified: bool = True
    declaration_line: int | None = None
    locator_diagnostic: str | None = None


def python_declaration(raw, selector):
    """Return (line, diagnostic) without imports, evaluation or normalization."""
    if selector is None:
        return None, 'SELECTOR_UNSPECIFIED'
    parts = selector.split('.')
    if len(parts) not in (1, 2) or any(not p.isidentifier() or keyword.iskeyword(p) for p in parts):
        return None, 'SELECTOR_UNSUPPORTED'
    try:
        tree = ast.parse(raw.decode('utf-8', errors='strict'))
    except (UnicodeError, SyntaxError, ValueError, RecursionError):
        return None, 'PYTHON_SOURCE_UNPARSEABLE'
    scope = tree.body
    if len(parts) == 2:
        classes = [n for n in scope if isinstance(n, ast.ClassDef) and n.name == parts[0]]
        if len(classes) != 1:
            return None, 'CLASS_NOT_UNIQUE_OR_ABSENT'
        scope = classes[0].body
    matches = [n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == parts[-1]]
    if len(matches) != 1:
        return None, 'DECLARATION_NOT_UNIQUE_OR_ABSENT'
    return matches[0].lineno, None


def inspect_references(ledger, root, selected_paths, *, reviewed_new=(),
                       reviewed_fixtures=(), protected_paths=()):
    """Read one explicit batch; reader failure exposes no partial file success.

    SHA is an observation of selected bytes, not a trusted prior digest. Missing
    paths, exclusion and drift retain the reader's diagnostic. An empty result
    says only that the ledger has no references; it never means coverage PASS.
    """
    validate_metadata_fields(ledger)
    _decoded_limits(ledger)
    # Validate the entire selection through the shared boundary, even when a
    # selected file is not referenced. Never expand it from ledger input.
    try:
        files = {item.path: item for item in read_sources(root, selected_paths,
            reviewed_new=reviewed_new, reviewed_fixtures=reviewed_fixtures,
            protected_paths=protected_paths)}
        failure = None
    except SourceReadError as error:
        files, failure = {}, error.code
    selected = set(selected_paths) if isinstance(selected_paths, (list, tuple)) and all(
        isinstance(p, str) for p in selected_paths) else set()
    observations = []
    for capability in ledger['capabilities']:
        for field, locator in (('test_refs', 'selector'), ('doc_refs', 'anchor')):
            for ref in capability[field]:
                item = files.get(ref['path'])
                reason = None if item is not None else (
                    'REFERENCE_NOT_SELECTED' if ref['path'] not in selected else failure)
                line, locator_reason = None, 'REFERENCE_FILE_UNVERIFIED'
                if item is not None:
                    if field == 'doc_refs':
                        if ref['path'].endswith('.md'):
                            line, locator_reason = markdown_anchor(item.data, ref[locator])
                        else:
                            locator_reason = 'ANCHOR_LANGUAGE_UNSUPPORTED'
                    elif not ref['path'].endswith('.py'):
                        locator_reason = 'SELECTOR_LANGUAGE_UNSUPPORTED'
                    else:
                        line, locator_reason = python_declaration(item.data, ref[locator])
                observations.append(ReferenceObservation(
                    capability['id'], field, ref['path'], ref[locator], item is not None,
                    item.sha256 if item is not None else None,
                    len(item.data) if item is not None else None,
                    reason or (None if item is not None else 'REFERENCE_UNVERIFIED'),
                    locator_unverified=line is None, declaration_line=line,
                    locator_diagnostic=locator_reason))
    return tuple(observations)
