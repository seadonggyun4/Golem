"""Repeated CLI acceptance paths, separate from broad unit/fixture counts.

Uses the existing canonical fixtures rather than a second, drifting protocol.
Every CLI call starts a fresh process. Both paths use current-agent sessions;
the repair path includes observed C QA failure and classified document revision.
"""
import sys
import unittest
from completion_integration import Completion


class SessionRepair(Completion):
    def setup_failure(self, mode="real", sessions=True):
        super().setup_failure(mode=mode, sessions=True)

    def call(self, op, ok=True, **fields):
        # QA after the revised development submission requires a fresh claim.
        if op == "run" and ok and self.sessions and self.token is None:
            self.begin_claim()
        return super().call(op, ok=ok, **fields)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    for _ in range(3):
        suite.addTest(Completion("test_complete_recover_and_idempotency"))
        suite.addTest(SessionRepair("test_failure_repair_reaches_completion"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
