"""Pinned direct handlers; bounded fallback/delegation profiles are separate."""
from capability_handler import HandlerRule
HANDLERS = (
    HandlerRule(declaration_path='tools/integration_service.py', declaration_sha256='c15b4d00b839872c99c45b1bbbc97409868fc0bac3b18445e61c653a119a8b22', declaration='SCHEMAS', mapping=True, handler_path='tools/integration_service.py', handler_sha256='c15b4d00b839872c99c45b1bbbc97409868fc0bac3b18445e61c653a119a8b22', method='Service._call_locked', subject='name'),
    HandlerRule(declaration_path='tools/integration_mutation_contract.py', declaration_sha256='0edf3888cdeadaf5fae9ed99af83f122ece23146dffea0ae381ae1b054969020', declaration='NAMES', mapping=False, handler_path='tools/integration_mutations.py', handler_sha256='e69ba630714b2c545cc165c3fcce91e54473fe8cb9ca3baae3d5bdb1cc2be565', method='Service.call', subject='name'),
)
