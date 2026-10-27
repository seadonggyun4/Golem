"""Exact selected-file comparison, not schema, integrity or execution acceptance.

Expected names must come from a separately reviewed format adapter. Native
references remain unresolved here; this helper cannot certify child records.
"""
from dataclasses import dataclass
from capability_ledger import validate_relative_path
from capability_record_input import decode_record_inputs, FILES_MAX, require


@dataclass(frozen=True)
class InventoryComparison:
    missing: tuple
    extra: tuple
    unresolved_native: tuple

    @property
    def file_set_matches(self):
        return not self.missing and not self.extra

    @property
    def blocked(self):
        return not self.file_set_matches or bool(self.unresolved_native)


def _names(names):
    require(type(names) in (list, tuple) and len(names) <= FILES_MAX, 'INVENTORY_NAMES_LIMIT_OR_TYPE')
    seen = set()
    for name in names:
        validate_relative_path(name)
        require(name not in seen, 'INVENTORY_DUPLICATE_NAME')
        seen.add(name)
    return seen


def _no_file_ancestor(names):
    for name in names:
        parts = name.split('/')
        require(not any('/'.join(parts[:i]) in names for i in range(1, len(parts))),
                'INVENTORY_FILE_PATH_COLLISION')


def compare_file_inventory(files, required, referenced, *, unresolved_native=()):
    """Compare names without resolving paths or altering bytes.

    Required/manifest overlap is normal; duplicates within either list are not.
    Empty native refs are only absence of a blocker, never full integrity PASS.
    """
    decode_record_inputs(files, [])
    required_set, referenced_set = _names(required), _names(referenced)
    native = _names(unresolved_native)
    expected = required_set | referenced_set
    require(len(expected) <= FILES_MAX, 'INVENTORY_NAMES_LIMIT_OR_TYPE')
    _no_file_ancestor(set(files) | expected)
    return InventoryComparison(tuple(sorted(expected - files.keys())),
                               tuple(sorted(files.keys() - expected)),
                               tuple(name for name in unresolved_native if name in native))
