"""Finite public-header API inventory, separate from implementation/operation review."""
from dataclasses import dataclass

from capability_c_syntax import plain_declarations, public_declaration
from capability_profile import Observation, Scan, scan_sources
from capability_ledger import observation_identity, validate_relative_path


@dataclass(frozen=True)
class PublicHeaderRule:
    path: str
    sha256: str
    names: tuple


def scan_public_headers(sources, rules):
    scan_sources(sources, ())
    files = {f.path: f for f in sources}
    observations, unresolved, seen = [], [], set()
    for rule in rules:
        if not isinstance(rule, PublicHeaderRule):
            raise ValueError('PUBLIC_HEADER_RULE')
        validate_relative_path(rule.path)
        if rule.path in seen or len(set(rule.names)) != len(rule.names):
            raise ValueError('PUBLIC_HEADER_DUPLICATE')
        seen.add(rule.path)
        source = files.get(rule.path)
        # Only explicitly selected inputs are inspected, never fetched here.
        if source is None:
            continue
        if source.sha256 != rule.sha256:
            unresolved.append((rule.path, None, 'PUBLIC_HEADER_REVIEW_DRIFT'))
            continue
        try:
            staged = []
            actual = tuple(d[0] for d in plain_declarations(source.data.decode('utf-8')))
            if actual != rule.names:
                raise ValueError('PUBLIC_DECLARATION_SET_CHANGED')
            for name in rule.names:
                public_declaration(source.data, name)
                fields = dict(kind='C_PUBLIC_DECLARATION', source_path=rule.path,
                              entrypoint=name, selector=None)
                staged.append(Observation(observation_identity(**fields), **fields))
            observations.extend(staged)
        except (ValueError, UnicodeError) as error:
            unresolved.append((rule.path, None, str(error) if isinstance(error, ValueError) else 'PUBLIC_HEADER_UTF8'))
    return Scan(tuple(observations), tuple(unresolved))
