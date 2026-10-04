"""Architecture tripwire for Work record writers, not arbitrary-C static proof."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]) / "src"
# Remaining byte publications are projections or effect/authorization markers,
# not independently authored copies of assessment/status/journal records.
allowed = {
    "document/storage.c": 2,  # Primitive definition and Markdown projection.
    "document/record.c": 1,
    "execution/store.c": 1,  # Approved execution-policy marker.
    "execution/runner.c": 2,  # Dispatch and attempt-start intent hashes, not CAS keys.
    "execution/proof_store.c": 1,  # Explicit proof export.
    "reentry/store.c": 1,  # Explicit report projection.
    "completion/report.c": 1,  # Required completion projection.
    "workspace/lifecycle.c": 2,  # Ownership markers, not event streams.
}
observed = {}
for path in root.rglob("*.c"):
    count = len(re.findall(r"\bdw_publish\s*\(", path.read_text()))
    if count:
        observed[path.relative_to(root).as_posix()] = count
if observed != allowed:
    raise AssertionError(f"Unreviewed record publication path: {observed!r}")
events = {
    "document/registry.c": 2, "policy/approval_store.c": 1,
    "research/store.c": 1, "completion/store.c": 1, "workflow/role_store.c": 1,
    "reentry/store.c": 1, "runtime/profile_link.c": 1, "runtime/profile_store.c": 1,
    "daemon/admission_work.c": 1,
}
for name, count in events.items():
    source = (root / name).read_text()
    assert len(re.findall(r"\bdw_event_write(?:_guarded)?\s*\(", source)) == count, name
    assert len(re.findall(r"\bdw_record_prepare\s*\(", source)) == count, name
for name in ("agent_session/storage.c", "workspace/store.c", "candidate/store.c"):
    assert "dw_record_prepare(" in (root / name).read_text(), name
for name in ("document/storage.c", "agent_session/storage.c", "agent_session/history.c"):
    source = (root / name).read_text()
    assert "dw_record_read(" in source, name
    assert "dw_record_frame(" not in source, name
for name in ("document/storage.c", "agent_session/storage.c"):
    assert "dw_record_scan(" in (root / name).read_text(), name
for path in root.rglob("*.c"):
    if path.relative_to(root).as_posix() != "document/record.c":
        assert not re.search(r'"GW(?:DOC|AGN)001"', path.read_text()), path
print("Work record writer/reader inventory matches")
