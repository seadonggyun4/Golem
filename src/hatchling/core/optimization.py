from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from hatchling.core.models import ContextPackage, Decision, EvidenceRef, StageName


class OptimizationAction(StrEnum):
    NO_OP = "NO_OP"
    ROUTE_PROVIDER = "ROUTE_PROVIDER"
    COMPRESS_CONTEXT = "COMPRESS_CONTEXT"
    USE_CACHE = "USE_CACHE"
    FALLBACK = "FALLBACK"


@dataclass(frozen=True)
class ProviderUsage:
    provider: str
    model: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    tool_cost_micros: int = 0
    billed_cost_micros: int = 0


@dataclass(frozen=True)
class BudgetPolicy:
    stage: StageName
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_reasoning_tokens: int | None = None
    max_tool_cost_micros: int | None = None
    max_retries: int | None = None
    max_billed_cost_micros: int | None = None


@dataclass(frozen=True)
class CostLedgerEntry:
    stage: StageName
    attempt: int
    usage: ProviderUsage
    evidence: EvidenceRef | None = None


@dataclass(frozen=True)
class OptimizationProposal:
    action: OptimizationAction
    decision: Decision
    estimated_savings_micros: int = 0
    estimated_overhead_micros: int = 0
    evidence: tuple[EvidenceRef, ...] = ()


class OptimizationAdvisor(Protocol):
    """Optional boundary for cost optimizers such as Golem.

    Hatchling must remain able to run without an advisor. Advisors propose lower
    cost routes, cache use, compression, or fallback; Hatchling keeps final
    authority through its policy, stage graph, and evidence gates.
    """

    def propose(self, context: ContextPackage, budget: BudgetPolicy | None = None) -> OptimizationProposal:
        """Return a proposed optimization or NO_OP."""
