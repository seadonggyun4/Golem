from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal


class StageName(StrEnum):
    PLANNING = "planning"
    UX = "ux"
    PUBLISHING = "publishing"
    DEVELOPMENT = "development"
    QA = "qa"
    AUDIT = "audit"


class AutonomyMode(StrEnum):
    AUTO_LOCAL = "AUTO_LOCAL"
    ASK_ON_EXTERNAL_EFFECT = "ASK_ON_EXTERNAL_EFFECT"
    ASK_ALWAYS = "ASK_ALWAYS"
    DENY = "DENY"


class StageStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class FailureType(StrEnum):
    PLANNING_GAP = "planning_gap"
    UX_MISMATCH = "ux_mismatch"
    PUBLISHING_GAP = "publishing_gap"
    IMPLEMENTATION_DEFECT = "implementation_defect"
    QA_FLAKE = "qa_flake"
    AUDIT_GAP = "audit_gap"
    POLICY_DENIED = "policy_denied"
    STALE_LEASE = "stale_lease"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvidenceRef:
    digest: str
    kind: str
    uri: str


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    text: str
    required_gates: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkCapsule:
    id: str
    goal: str
    scope: tuple[str, ...]
    permissions: dict[StageName, AutonomyMode]
    stages: tuple[StageName, ...]
    acceptance: tuple[AcceptanceCriterion, ...]
    expected_artifacts: tuple[str, ...]
    required_gates: tuple[str, ...]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.id:
            errors.append("WorkCapsule.id is required.")
        if not self.goal:
            errors.append("WorkCapsule.goal is required.")
        if not self.stages:
            errors.append("WorkCapsule.stages must not be empty.")
        missing_permissions = [stage.value for stage in self.stages if stage not in self.permissions]
        if missing_permissions:
            errors.append("Missing autonomy policy for stages: " + ", ".join(missing_permissions))
        acceptance_gates = {gate for item in self.acceptance for gate in item.required_gates}
        missing_gates = sorted(acceptance_gates - set(self.required_gates))
        if missing_gates:
            errors.append("Acceptance references gates not listed as required: " + ", ".join(missing_gates))
        return errors


@dataclass(frozen=True)
class StageGraph:
    order: tuple[StageName, ...] = (
        StageName.PLANNING,
        StageName.UX,
        StageName.PUBLISHING,
        StageName.DEVELOPMENT,
        StageName.QA,
        StageName.AUDIT,
    )
    rollback: dict[FailureType, StageName] = field(
        default_factory=lambda: {
            FailureType.PLANNING_GAP: StageName.PLANNING,
            FailureType.UX_MISMATCH: StageName.UX,
            FailureType.PUBLISHING_GAP: StageName.PUBLISHING,
            FailureType.IMPLEMENTATION_DEFECT: StageName.DEVELOPMENT,
            FailureType.QA_FLAKE: StageName.QA,
            FailureType.AUDIT_GAP: StageName.AUDIT,
            FailureType.POLICY_DENIED: StageName.PLANNING,
            FailureType.STALE_LEASE: StageName.PLANNING,
            FailureType.BUDGET_EXHAUSTED: StageName.PLANNING,
            FailureType.UNKNOWN: StageName.PLANNING,
        }
    )

    def next_after(self, stage: StageName) -> StageName | None:
        index = self.order.index(stage)
        if index + 1 >= len(self.order):
            return None
        return self.order[index + 1]

    def reentry_for(self, failure_type: FailureType) -> StageName:
        return self.rollback.get(failure_type, StageName.PLANNING)


@dataclass(frozen=True)
class ContextPackage:
    capsule_id: str
    stage: StageName
    predecessor_evidence: tuple[EvidenceRef, ...] = ()
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    status: Literal["ALLOW", "ASK", "DENY"]
    reason: str
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class StageRun:
    id: str
    capsule_id: str
    stage: StageName
    attempt: int
    status: StageStatus
    agent_provider: str
    lease_id: str | None = None
    budget_seconds: int | None = None
    evidence: tuple[EvidenceRef, ...] = ()
    failure_type: FailureType | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None


@dataclass(frozen=True)
class WorkRun:
    id: str
    capsule: WorkCapsule
    stage_runs: tuple[StageRun, ...] = ()
    receipts: tuple[EvidenceRef, ...] = ()

    def latest_stage_run(self) -> StageRun | None:
        return self.stage_runs[-1] if self.stage_runs else None
