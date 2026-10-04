"""Run existing domain scenarios with automatic recording enabled."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--case", nargs="+", action="append", required=True,
                        metavar="OPERATION_AND_COMMAND")
    args = parser.parse_args()
    sys.path.insert(0, str(args.source / "tools"))
    from native_record import check

    environment = {k: v for k, v in os.environ.items() if not k.startswith("GOLEM_RECORD_")}
    for case in args.case:
        if len(case) < 2:
            parser.error("--case requires an operation name and command")
        operation, *command = case
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root, work = base / "records", base / "work"
            root.mkdir(mode=0o700)
            work.mkdir()
            invocation = [str(work) if arg == "@CASE_DIR@" else arg for arg in command]
            completed = subprocess.run(invocation, capture_output=True, timeout=180,
                                       env={**environment, "GOLEM_RECORD_ROOT": str(root)})
            if completed.returncode:
                raise AssertionError(f"{operation}: exit {completed.returncode}\n"
                                     f"{completed.stdout.decode(errors='replace')}\n"
                                     f"{completed.stderr.decode(errors='replace')}")
            records = {p.name: (check(p), json.loads((p / "started.json").read_bytes()))
                       for p in root.iterdir()}
            successes = [r for r, s in records.values() if s["operation"] == operation
                         and r["result"]["operation_status"] == 0]
            if not successes:
                raise AssertionError(f"{operation}: no successful automatic observation")
            for record, _ in records.values():
                if record["parent"] and record["parent"] not in records:
                    raise AssertionError(f"{operation}: missing parent observation")
                if record["result"]["recording_status"] != 0:
                    raise AssertionError(f"{operation}: recording failed")
            print(f"{operation}: verified {len(records)} records")


if __name__ == "__main__":
    main()
