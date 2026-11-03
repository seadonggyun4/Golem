"""Pinned direct handlers; bounded fallback/delegation profiles are separate."""
from capability_handler import HandlerRule
HANDLERS = (
    HandlerRule(declaration_path='tools/integration_service.py', declaration_sha256='a2ec4a339ab4169aaf0cc01c75aad1cd14eb0a183dd85f7380de24e00a8a82f3', declaration='SCHEMAS', mapping=True, handler_path='tools/integration_service.py', handler_sha256='a2ec4a339ab4169aaf0cc01c75aad1cd14eb0a183dd85f7380de24e00a8a82f3', method='Service._call_locked', subject='name'),
    HandlerRule(declaration_path='tools/integration_mutation_contract.py', declaration_sha256='301d7a013ddd90aafbb0c36a17c7aea9f5e8f24ae96c26af2f28eef57d2abc98', declaration='NAMES', mapping=False, handler_path='tools/integration_mutations.py', handler_sha256='b41150e05b293e0f35c48a213b7c1ba350740ae14b1c18b82728487e426ad536', method='Service.call', subject='name'),
)
