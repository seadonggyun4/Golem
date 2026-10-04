"""Read-only native observation verifier. Integrity is not acceptance or authenticity."""
import hashlib
import json
from pathlib import Path
import re
import stat
import os


def check(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError("symlink record path")
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("record must be private")

    def read(name):
        p = path / name
        info = p.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024 * 1024:
            raise ValueError("invalid artifact")
        return p.read_bytes()

    manifest = json.loads(read("manifest.json"))
    if (not isinstance(manifest, dict) or not {"started.json", "result.json"} <= manifest.keys()
            or manifest.keys() - {"started.json", "result.json", "stdout.log", "stderr.log"}
            or {p.name for p in path.iterdir()} != manifest.keys() | {"manifest.json"}):
        raise ValueError("invalid inventory")
    for name, digest in manifest.items():
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid digest")
        if hashlib.sha256(read(name)).hexdigest() != digest:
            raise ValueError("digest mismatch")
    start, result = (json.loads(read(n)) for n in ("started.json", "result.json"))
    if (not isinstance(start, dict) or not isinstance(result, dict)
            or start.get("schema") != "golem.native-record.v1" or result.get("schema") != start["schema"]
            or start.get("id") != path.name or result.get("id") != path.name
            or not re.fullmatch(r"[0-9a-f]{32}", path.name)
            or start.get("state") != "STARTED" or result.get("state") not in ("FINISHED", "RECORDING_FAILED")):
        raise ValueError("invalid lifecycle")
    if (not isinstance(start.get("parent"), str)
            or (start["parent"] and not re.fullmatch(r"[0-9a-f]{32}", start["parent"]))
            or not isinstance(start.get("kind"), str)
            or start.get("descendant_coverage") != "GOLEM_SUPERVISOR_ONLY"
            or any(type(result.get(key)) is not int for key in
                   ("operation_status", "recording_status", "exit_code", "signal_number", "elapsed_ns"))
            or any(type(result.get(key)) is not bool for key in
                   ("spawned", "reaped", "timed_out", "stdout_eof", "stderr_eof", "product_acceptance"))
            or result["product_acceptance"]
            or (result["state"] == "FINISHED") != (result["recording_status"] == 0)):
        raise ValueError("invalid outcome")
    for stream in ("stdout", "stderr"):
        if stream + ".log" in manifest:
            if (result.get(stream + "_sha256") != manifest[stream + ".log"]
                    or result.get(stream + "_bytes") != (path / (stream + ".log")).stat().st_size):
                raise ValueError("invalid stream receipt")
    return {"integrity": "PASS", "id": start["id"], "parent": start["parent"],
            "kind": start["kind"], "result": result, "product_acceptance": False,
            "authenticity_verified": False, "descendant_coverage": start["descendant_coverage"]}


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.record), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"integrity": "FAIL", "error_type": type(error).__name__}), file=sys.stderr)
        sys.exit(1)
