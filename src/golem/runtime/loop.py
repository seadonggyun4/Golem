from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from golem.adapters.base import AgentAdapter
from golem.core.models import ContextPackage, FailureType, StageGraph, StageRun, StageStatus, WorkCapsule, WorkRun
from golem.policies.autonomy import ActionRequest, evaluate_action
from golem.runtime.lease import Lease


@dataclass
class LoopController:
    graph: StageGraph
    adapter: AgentAdapter
    max_attempts_per_stage: int = 3

    def run_once(self, run: WorkRun, stage_index: int = 0) -> WorkRun:
        stage = run.capsule.stages[stage_index]
        decision = evaluate_action(run.capsule, ActionRequest(stage=stage, description=f"run {stage.value}"))
        if decision.status != "ALLOW":
            stage_run = StageRun(
                id=str(uuid4()),
                capsule_id=run.capsule.id,
                stage=stage,
                attempt=self._attempt(run, stage),
                status=StageStatus.BLOCKED,
                agent_provider=self.adapter.provider,
                failure_type=FailureType.POLICY_DENIED,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            return WorkRun(id=run.id, capsule=run.capsule, stage_runs=run.stage_runs + (stage_run,), receipts=run.receipts)
        lease = Lease(holder=self.adapter.provider)
        context = ContextPackage(
            capsule_id=run.capsule.id,
            stage=stage,
            predecessor_evidence=tuple(ref for item in run.stage_runs for ref in item.evidence),
        )
        result = self.adapter.run_stage(context)
        stage_run = StageRun(
            id=str(uuid4()),
            capsule_id=run.capsule.id,
            stage=stage,
            attempt=self._attempt(run, stage),
            status=result.status,
            agent_provider=self.adapter.provider,
            lease_id=lease.id,
            evidence=result.evidence,
            failure_type=result.failure_type,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        return WorkRun(id=run.id, capsule=run.capsule, stage_runs=run.stage_runs + (stage_run,), receipts=run.receipts + result.evidence)

    def next_stage_index(self, capsule: WorkCapsule, stage_run: StageRun) -> int | None:
        if stage_run.status == StageStatus.PASSED:
            next_stage = self.graph.next_after(stage_run.stage)
        else:
            next_stage = self.graph.reentry_for(stage_run.failure_type or FailureType.UNKNOWN)
        if next_stage is None:
            return None
        return capsule.stages.index(next_stage)

    def _attempt(self, run: WorkRun, stage) -> int:
        return sum(1 for item in run.stage_runs if item.stage == stage) + 1
