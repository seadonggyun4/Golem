"""Interactive, disposable 31G observation; never launches a model or repairs code.

Not a CI test or identity attestation. Interruptions retain evidence but cannot
be automatically retried: use a new output directory for a new observation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from verify_agent import private_directory, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cc", type=Path, required=True)
    parser.add_argument("--workspace-helper", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("requires an interactive current-agent/operator session")
    os.umask(0o077)
    root = private_directory(args.output).resolve()
    source = args.source.resolve(strict=True)
    # Reuse the reviewed synthetic setup, not a second implementation of Work.
    sys.path.insert(0, str(source / "tests/c"))
    sys.argv = [sys.argv[0], str(args.cli.resolve()), str(source), str(args.cc.resolve())]
    from reentry_integration import Reentry
    from completion_integration import Completion

    class Observation(Reentry):
        completion = Completion.completion
        finalize = Completion.finalize
        project = Completion.project
        note = ""

        def body(self, kind, parents):
            body = super().body(kind, parents)
            return body.replace("## Work\n", "## Work\n\n" + self.note + "\n") if kind == "development-plan" else body

        def begin_claim(self, ttl=300000):
            return super().begin_claim(ttl)

    f = Observation()
    f.root = root
    f.a = json.loads((source / "samples/discovery/assessment.json").read_text())
    f.setup_execution(sessions=True)
    main_repo = f.repo
    original = (main_repo / "user.txt").read_bytes()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "WS_"))}
    base = subprocess.check_output(["git", "-C", str(main_repo), "rev-parse", "HEAD"], env=env).decode().strip()
    workspace_root = root / "worktrees"
    workspace_root.mkdir()
    output = subprocess.check_output([str(args.workspace_helper.resolve()), str(f.work),
        str(main_repo), str(workspace_root), "candidate", "1", base, "-"], env=env, timeout=90).decode().splitlines()
    f.repo = Path(output[1])
    initial_code = (f.repo / "logic.c").read_bytes()
    workspace_receipt = output[2]
    repo = f.contract["snapshot_plan"]["repositories"][0]
    repo["root"] = str(f.repo)
    f.contract["schema_version"] = 4
    f.contract["snapshot_plan"]["schema_version"] = 2
    f.contract["log_retention"] = {"mode": "REDACTED_CAPTURE", "max_bytes": 16384,
        "redactor": "mask-bytes-v1", "require_complete": True}
    repo["change_policy"] = {"schema_version": 1,
        "protected": [{"kind": "EXACT", "pattern": p} for p in ("test.c", "runner.py", "user.txt")],
        "excluded": [{"kind": "EXACT", "pattern": p} for p in ("invoked", "test-bin")],
        "limit": {"mode": "BOUNDED", "max_changed_paths": 1}}
    f.contract["gates"][0]["execution"] = {"kind": "DIRECT",
        "executable_digest": hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()}
    f.approval = f.raw("execution", "validate", f.write("contract.json", f.contract)).strip()
    f.prepare()
    f.finish()
    f.begin_claim()
    f.failure = f.call("run", checkpoint=f.cp["receipt_digest"], attempt_id="observed-failure")
    f.assertEqual(f.failure["record"]["status"], "FAIL")
    f.result("qa-result", f.failure)
    historical = (f.work / "documents/qa-result/r0001.md").read_bytes()
    decision = f.decide()
    f.raw("reentry", "report", f.work, 1)
    print(f"Read {f.work}/failures/r0001.md and candidate {f.repo}.\n"
          f"Write plain paragraphs (no headings) to {root}/revision.md; do NOT edit code yet.", flush=True)
    if input("Type PLAN to register the revision: ").strip() != "PLAN":
        raise ValueError("observation interrupted")
    if (f.repo / "logic.c").read_bytes() != initial_code:
        raise ValueError("candidate edited before the revised development plan was registered")
    note = root / "revision.md"
    if note.is_symlink() or not note.is_file() or not 20 <= note.stat().st_size <= 16384:
        raise ValueError("bounded regular revision note required")
    f.note = note.read_text()
    if any(line.lstrip().startswith("#") for line in f.note.splitlines()):
        raise ValueError("revision note must contain paragraphs, not additional schema headings")
    f.managed("development-plan")
    f.reprepare()
    print(f"Revision registered. Edit ONLY {f.repo}/logic.c using the current agent.", flush=True)
    if input("Type VERIFY to execute QA: ").strip() != "VERIFY":
        raise ValueError("observation interrupted")
    f.finish()
    f.begin_claim()
    passed = f.call("run", checkpoint=f.cp["receipt_digest"], attempt_id="observed-repair")
    f.assertEqual(passed["record"]["status"], "PASS")
    f.result("qa-result", passed)
    f.managed("completion")
    f.finalize()
    f.project()
    f.assertEqual(f.completion()["action"], "DONE")
    f.assertEqual((main_repo / "user.txt").read_bytes(), original)
    f.assertEqual((f.work / "documents/qa-result/r0001.md").read_bytes(), historical)
    request = f.write("proof-request.json", {"schema_version": 1, "renderer_version": 1,
        "qa_receipts": [f.failure["receipt_digest"], passed["receipt_digest"]],
        "redaction": {"schema_version": 1, "profile": "MINIMAL", "acknowledge_linkability": False}})
    pack = f.write("proof.json", f.raw("proof", "render", f.work, request))
    f.raw("proof", "verify", f.work, request, pack)
    export = root / "proof-export"
    export.mkdir()
    publication = f.cli("proof", "publish", pack, export)
    f.cli("proof", "verify-dir", export, publication["manifest_sha256"])
    report = {"schema": "golem.isolation-observation.v1", "authority": "DERIVED_ONLY",
        "status": "PASS", "actual_agent_verified": False, "provider_invoked": False,
        "mode": "INTERACTIVE_SYNTHETIC_TASK", "workspace_receipt": workspace_receipt,
        "failure_receipt": f.failure["receipt_digest"], "pass_receipt": passed["receipt_digest"],
        "decision_digest": decision["decision_digest"], "proof_sha256": hashlib.sha256(pack.read_bytes()).hexdigest(),
        "publication_manifest": publication["manifest_sha256"],
        "limitations": ["identity is not externally attested", "fixture host authorizes only disposable worktree",
                        "synthetic discovery scaffolding, not independent project research", "not a production sandbox"]}
    save(root / "observation.json", (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
