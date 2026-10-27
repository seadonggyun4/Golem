"""Detect repository index omissions separately from selected-source extraction.

The tracked-path inventory is metadata, not permission to open any listed file.
Every new/deleted path requires scope review, including docs and build inputs.
"""
from dataclasses import dataclass
import os
from capability_ledger import validate_relative_path
from capability_files import _git_query, _repository, _open_root


@dataclass(frozen=True)
class ScopeDifference:
    added: tuple
    removed: tuple

    @property
    def matches(self):
        return not self.added and not self.removed


def compare_scope(reviewed, current):
    for names in (reviewed, current):
        if not isinstance(names, (tuple, list)) or len(names) > 4096:
            raise ValueError('SCOPE_LIMIT_OR_TYPE')
        for name in names:
            validate_relative_path(name)
        if len(set(names)) != len(names):
            raise ValueError('SCOPE_DUPLICATE')
    return ScopeDifference(tuple(sorted(set(current)-set(reviewed))), tuple(sorted(set(reviewed)-set(current))))


def _scope_names(root,arguments):
    """Fixed read-only index query; no imports, file discovery or content reads."""
    descriptor = _open_root(root)
    try:
        original = os.fstat(descriptor)
        _repository(root)
        raw = _git_query(root, arguments, 4096 * 4097)
        again = _open_root(root)
        try:
            current = os.fstat(again)
            if (original.st_dev, original.st_ino) != (current.st_dev, current.st_ino):
                raise ValueError('SCOPE_ROOT_CHANGED')
        finally:
            os.close(again)
    finally:
        os.close(descriptor)
    if raw and not raw.endswith(b'\0'):
        raise ValueError('SCOPE_FRAMING')
    names = tuple(raw[:-1].decode('utf-8', errors='strict').split('\0')) if raw else ()
    compare_scope(names, names)
    return names


def tracked_scope(root):
    """Fixed index metadata only; never opens a listed path."""
    return _scope_names(root,['ls-files','--cached','--full-name','-z'])


def untracked_scope(root):
    """Fixed non-ignored untracked names only, within the selected repository."""
    return _scope_names(root,['ls-files','--others','--exclude-standard','--full-name','-z'])
