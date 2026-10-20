"""Explicit qualification against a retained older CLI, on synthetic Work only.

Usage: script NEW_CLI SOURCE AGENT_CLIENT CC OLD_CLI NEW_EVIDENCE_DIRECTORY
The older executable is supplied by the maintainer; normal tests never download
or rebuild an arbitrary historical engine, or use an installed product Work.
"""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import rejected_output_integration as fixture

sys.path.insert(0, str(fixture.sessions.fixture.SOURCE / "tools"))
import execution_record as records


def verify(old, output):
    output = records.private_directory(output)
    case = fixture.Rejection()
    case.setUp()
    commands = []

    def run(name, *args):
        result = subprocess.run([str(old), "--output-mode", "full", *map(str, args)],
                                env=fixture.sessions.fixture.ENV, capture_output=True, timeout=90)
        records.save(output / f"{name}.stdout", result.stdout)
        records.save(output / f"{name}.stderr", result.stderr)
        commands.append(dict(id=name, exit_code=result.returncode, argv=list(map(str, args))))
        return result

    try:
        query = case.write("status.json", dict(schema_version=1, operation="status", work_id="example-work"))
        assert run("old-session-before", "session", "call", case.work, query).returncode == 0
        receipt = case.reject()
        records.save(output / "new-rejection.json", records.encoded(receipt))
        prefix = case.work_bytes()
        assert run("old-session-after", "session", "call", case.work, query).returncode != 0
        assert run("old-historical-document", "document", "inspect", case.work,
                   case.ref["document_id"], case.ref["revision"]).returncode == 0
        view = run("old-workflow-view", "workflow", "next", case.work, "selection")
        assert view.returncode == 0 and json.loads(view.stdout).get("acceptance_verified") is not True
        claim = case.write("old-claim.json", dict(schema_version=1, operation="claim", work_id="example-work",
            key="old-claim", expected_sequence=case.seq, session_id="old-owner", expected_generation=case.generation,
            source_snapshot=case.source, byte_budget=1048576, ttl_ms=10000))
        assert run("old-claim", "session", "call", case.work, claim).returncode != 0
        resume = case.write("old-completion-resume.json", dict(schema_version=1, operation="resume", selection_id="selection"))
        assert run("old-completion-resume", "completion", "call", case.work, resume).returncode != 0
        finalize = case.write("old-finalize.json", dict(schema_version=2, operation="finalize", selection_id="selection",
            key="old-finalize", expected_generation=case.generation, issues=[]))
        assert run("old-finalize", "completion", "call", case.work, finalize).returncode != 0
        assert prefix == case.work_bytes(), "Read/blocked authority calls changed fixture bytes"

        # A legacy trusted registration API is NOT a current acceptance API. Test
        # this separately rather than claiming all old SDK writes are fenced.
        metadata = case.metadata("planning")
        metadata["producer_attempt"] = case.active["attempt_id"]
        result = run("old-raw-registration", "document", "submit", case.work,
            case.write("legacy-metadata.json", metadata), case.write("legacy-body.md", case.body("planning", [])),
            "unsupported-mixed-writer")
        assert result.returncode == 0, result.stderr.decode()
        assert json.loads(result.stdout).get("acceptance_verified") is not True
        for name, raw in prefix.items():
            assert (case.work / name).read_bytes() == raw
        after = case.work_bytes()
        blocked = case.request("status", ok=False)
        records.save(output / "new-reader-after-mixed-write.stderr", blocked.stderr)
        assert after == case.work_bytes()
        report = dict(schema="golem.rejection-compatibility.v1", platform=platform.platform(),
            old_binary_sha256=hashlib.sha256(old.read_bytes()).hexdigest(),
            new_binary_sha256=hashlib.sha256(fixture.sessions.fixture.CLI.read_bytes()).hexdigest(),
            old_historical_read=True, old_session_claim_and_completion_blocked=True,
            old_raw_registration_still_possible=True, mixed_version_writers_supported=False,
            new_reader_blocks_extra_attributed_output=True, preserved_original_prefix=True, commands=commands)
        records.save(output / "compatibility.json", records.encoded(report))
        print(json.dumps({k: v for k, v in report.items() if k != "commands"}))
    finally:
        case.tearDown()


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
