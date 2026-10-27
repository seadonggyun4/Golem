"""Pinned direct handlers; bounded fallback/delegation profiles are separate."""
from capability_handler import HandlerRule
HANDLERS = (
    HandlerRule(declaration_path='tools/integration_service.py', declaration_sha256='c068fd6f888868e311568f4e82c93b7cf5a6107f68cac75059f520bb58e7a7c5', declaration='SCHEMAS', mapping=True, handler_path='tools/integration_service.py', handler_sha256='c068fd6f888868e311568f4e82c93b7cf5a6107f68cac75059f520bb58e7a7c5', method='Service._call_locked', subject='name'),
    HandlerRule(declaration_path='tools/integration_mutation_contract.py', declaration_sha256='6c3b342b1a7859fa863979dc9ca41585084c716597e5159f17176c6c024f9410', declaration='NAMES', mapping=False, handler_path='tools/integration_mutations.py', handler_sha256='93fbe43fee8d26acde873bd7d41b8edbd099e61dd0e904e58fbc3fa2278731dc', method='Service.call', subject='name'),
)
