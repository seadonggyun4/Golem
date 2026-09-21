from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hatchling.adapters.base import StageResult
from hatchling.core.models import (
    AcceptanceCriterion,
    AutonomyMode,
    ContextPackage,
    FailureType,
    StageGraph,
    StageName,
    StageStatus,
    WorkCapsule,
    WorkRun,
)
from hatchling.evidence.store import EvidenceStore
from hatchling.policies.autonomy import ActionRequest, evaluate_action
from hatchling.runtime.lease import Lease
from hatchling.runtime.loop import LoopController


def make_capsule() -> WorkCapsule:
    stages = tuple(StageName)
    return WorkCapsule(
        id="sample-work",
        goal="Complete a headless work cycle.",
        scope=("src/**",),
        permissions={stage: AutonomyMode.AUTO_LOCAL for stage in stages},
        stages=stages,
        acceptance=(AcceptanceCriterion("AC-1", "Audit gate must pass.", ("audit",)),),
        expected_artifacts=("evidence receipt",),
        required_gates=("audit",),
    )


class HatchlingCoreTests(unittest.TestCase):
    def test_work_capsule_validation_accepts_default_shape(self) -> None:
        self.assertEqual(make_capsule().validate(), [])

    def test_stage_graph_routes_failures_to_specific_reentry_stage(self) -> None:
        graph = StageGraph()
        self.assertEqual(graph.next_after(StageName.PLANNING), StageName.UX)
        self.assertEqual(graph.reentry_for(FailureType.UX_MISMATCH), StageName.UX)
        self.assertEqual(graph.reentry_for(FailureType.IMPLEMENTATION_DEFECT), StageName.DEVELOPMENT)
        self.assertEqual(graph.reentry_for(FailureType.UNKNOWN), StageName.PLANNING)

    def test_autonomy_policy_blocks_external_effects_when_required(self) -> None:
        work = make_capsule()
        permissions = dict(work.permissions)
        permissions[StageName.PUBLISHING] = AutonomyMode.ASK_ON_EXTERNAL_EFFECT
        work = WorkCapsule(
            id=work.id,
            goal=work.goal,
            scope=work.scope,
            permissions=permissions,
            stages=work.stages,
            acceptance=work.acceptance,
            expected_artifacts=work.expected_artifacts,
            required_gates=work.required_gates,
        )
        decision = evaluate_action(work, ActionRequest(StageName.PUBLISHING, "publish", external_effect=True))
        self.assertEqual(decision.status, "ASK")

    def test_evidence_store_is_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EvidenceStore(Path(directory))
            ref = store.put("test-result", {"command": "pytest", "result": "PASS"})
            self.assertTrue(ref.digest.startswith("sha256:"))
            self.assertEqual(store.verify(ref), [])

    def test_lease_detects_stale_heartbeat(self) -> None:
        now = datetime.now(timezone.utc)
        lease = Lease(acquired_at=now - timedelta(seconds=10), heartbeat_at=now - timedelta(seconds=10), ttl_seconds=5)
        self.assertTrue(lease.is_stale(now))

    def test_loop_controller_returns_to_failure_specific_stage(self) -> None:
        class FailingAdapter:
            provider = "test"

            def run_stage(self, context: ContextPackage) -> StageResult:
                return StageResult(status=StageStatus.FAILED, failure_type=FailureType.PUBLISHING_GAP)

        work = make_capsule()
        controller = LoopController(StageGraph(), FailingAdapter())
        run = controller.run_once(WorkRun("run-1", work), stage_index=3)
        self.assertEqual(run.latest_stage_run().stage, StageName.DEVELOPMENT)
        self.assertEqual(controller.next_stage_index(work, run.latest_stage_run()), work.stages.index(StageName.PUBLISHING))


if __name__ == "__main__":
    unittest.main()
