"""Pinned direct handlers; bounded fallback/delegation profiles are separate."""
from capability_handler import HandlerRule
HANDLERS = (
    HandlerRule(declaration_path='tools/integration_service.py', declaration_sha256='f82d9963a2152e14c10eeb2805c66eaa82beea9b1c50805b6333a51500102a44', declaration='SCHEMAS', mapping=True, handler_path='tools/integration_service.py', handler_sha256='f82d9963a2152e14c10eeb2805c66eaa82beea9b1c50805b6333a51500102a44', method='Service._call_locked', subject='name'),
    HandlerRule(declaration_path='tools/integration_mutation_contract.py', declaration_sha256='586501b124e655e328861dccd821c752743ccface1fbe1396514fb066cde3335', declaration='NAMES', mapping=False, handler_path='tools/integration_mutations.py', handler_sha256='e9232924c824bf5eaef8be7683bdd480c74ba338d04b8a7fd26ac25f96987cb8', method='Service.call', subject='name'),
)
