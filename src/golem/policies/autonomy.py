from __future__ import annotations

from dataclasses import dataclass

from golem.core.models import AutonomyMode, Decision, StageName, WorkCapsule


@dataclass(frozen=True)
class ActionRequest:
    stage: StageName
    description: str
    external_effect: bool = False
    destructive: bool = False


def evaluate_action(capsule: WorkCapsule, request: ActionRequest) -> Decision:
    mode = capsule.permissions.get(request.stage, AutonomyMode.DENY)
    if request.destructive or mode == AutonomyMode.DENY:
        return Decision(status="DENY", reason=f"{request.stage.value} is not allowed for this action.")
    if mode == AutonomyMode.ASK_ALWAYS:
        return Decision(status="ASK", reason=f"{request.stage.value} requires explicit approval.")
    if mode == AutonomyMode.ASK_ON_EXTERNAL_EFFECT and request.external_effect:
        return Decision(status="ASK", reason=f"{request.stage.value} has an external effect.")
    return Decision(status="ALLOW", reason=f"{request.stage.value} may run locally.")
