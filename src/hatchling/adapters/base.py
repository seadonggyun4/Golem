from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from hatchling.core.models import ContextPackage, EvidenceRef, FailureType, StageStatus


@dataclass(frozen=True)
class StageResult:
    status: StageStatus
    evidence: tuple[EvidenceRef, ...] = ()
    failure_type: FailureType | None = None
    summary: str = ""


class AgentAdapter(Protocol):
    provider: str

    def run_stage(self, context: ContextPackage) -> StageResult:
        """Run one Hatchling stage and return result evidence."""
