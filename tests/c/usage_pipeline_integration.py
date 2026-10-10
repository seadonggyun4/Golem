"""Python hosted delivery -> actual native finish-time ledger import."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from test_usage_pipeline import PipelineTests
from test_codex_hosted import OwnedTests


def main():
    owned = OwnedTests(); owned.setUp()
    try:
        owned.mapping["run_id"] = "cost-run"
        assert owned.run_owned()["native_delivery"] == "PUBLISHED"
        subprocess.run([sys.argv[1], "inbox-observed", str(owned.inbox)], check=True)
        path = next(owned.inbox.glob("*.json"))
        value = json.loads(path.read_bytes())
        report = value["reports"][0]
        for invalid in ({**report, "schema": "golem.native-cost-report.v1"},
                        {**report, "nano_cost": "1"},
                        {**report, "usage_known": "false"},
                        {**report, "run_id": "cost-run\0hidden"},
                        {**report, "request_id": "call\0hidden"},
                        {**report, "extra": True}):
            path.write_text(json.dumps({**value, "reports": [invalid]}))
            subprocess.run([sys.argv[1], "inbox-blocked", str(owned.inbox)], check=True)
    finally:
        owned.doCleanups()
    case = PipelineTests()
    case.setUp()
    try:
        case.observed()
        case.p.close()
        subprocess.run([sys.argv[1], "inbox-file", str(case.inbox)], check=True)
        subprocess.run([sys.argv[1], "inbox-cancel", str(case.inbox)], check=True)
        subprocess.run([sys.argv[1], "inbox-unbilled", str(case.inbox)], check=True)
        path = next(case.inbox.iterdir())
        value = json.loads(path.read_bytes())
        for corrupt in ({**value, "sealed": False}, {**value, "run_id": "wrong"},
                        {**value, "reports": []}, {**value, "sequence": "2"},
                        {**value, "run_id": "cost-run\0hidden"}):
            path.write_text(json.dumps(corrupt))
            subprocess.run([sys.argv[1], "inbox-blocked", str(case.inbox)], check=True)
        path.unlink()
        subprocess.run([sys.argv[1], "inbox-blocked", str(case.inbox)], check=True)
    finally:
        case.doCleanups()
    billed = PipelineTests(); billed.setUp()
    try:
        billed.test_signed_billing_automatically_routes_verified_cost()
        subprocess.run([sys.argv[1], "inbox-billed", str(billed.inbox)], check=True)
    finally:
        billed.doCleanups()


if __name__ == "__main__":
    main()
