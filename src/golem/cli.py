from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from golem.adapters.local import LocalNoopAdapter
from golem.core.models import AcceptanceCriterion, AutonomyMode, StageGraph, StageName, WorkCapsule, WorkRun
from golem.evidence.store import EvidenceStore
from golem.runtime.loop import LoopController


def default_capsule() -> WorkCapsule:
    stages = tuple(StageName)
    return WorkCapsule(
        id="sample-work-capsule",
        goal="Exercise the Golem MVP work cycle.",
        scope=("samples/**",),
        permissions={stage: AutonomyMode.AUTO_LOCAL for stage in stages},
        stages=stages,
        acceptance=(AcceptanceCriterion(id="AC-001", text="All stages produce evidence.", required_gates=("audit",)),),
        expected_artifacts=("content-addressed evidence",),
        required_gates=("audit",),
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="golem")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("smoke-run")
    args = parser.parse_args()
    if args.command == "smoke-run":
        evidence_store = EvidenceStore(Path(".golem/evidence"))
        capsule = default_capsule()
        errors = capsule.validate()
        if errors:
            print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
            return 1
        run = WorkRun(id=str(uuid4()), capsule=capsule)
        controller = LoopController(StageGraph(), LocalNoopAdapter("local-noop", evidence_store))
        index: int | None = 0
        while index is not None:
            run = controller.run_once(run, index)
            index = controller.next_stage_index(capsule, run.latest_stage_run())
        print(json.dumps({"status": "PASS", "run_id": run.id, "stage_runs": len(run.stage_runs), "receipts": [ref.digest for ref in run.receipts]}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
