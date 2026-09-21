from __future__ import annotations

from dataclasses import dataclass

from hatchling.adapters.base import StageResult
from hatchling.core.models import ContextPackage, StageStatus
from hatchling.evidence.store import EvidenceStore


@dataclass(frozen=True)
class LocalNoopAdapter:
    provider: str
    evidence_store: EvidenceStore

    def run_stage(self, context: ContextPackage) -> StageResult:
        evidence = self.evidence_store.put(
            "stage-log",
            {
                "capsule_id": context.capsule_id,
                "stage": context.stage.value,
                "provider": self.provider,
                "inputs": context.inputs,
                "predecessor_evidence": [item.digest for item in context.predecessor_evidence],
                "result": "noop stage completed",
            },
        )
        return StageResult(status=StageStatus.PASSED, evidence=(evidence,), summary="noop stage completed")
