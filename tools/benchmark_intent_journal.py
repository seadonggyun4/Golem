"""Disposable layout experiment, NOT a native intent store or durability proof."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import struct
import tempfile
import time


def payload(sequence, size):
    value = {"schema_version": 1, "sequence": sequence,
             "previous_event_digest": "0" * 64,
             "operation_id": f"experiment-{sequence}", "request_digest": "1" * 64,
             "expected_generation": sequence - 1, "constraint_epoch": 1,
             "type": "EXPERIMENT_ONLY", "object_digest": "2" * 64,
             "padding": ""}
    raw = json.dumps(value, separators=(",", ":")).encode()
    if len(raw) > size:
        raise ValueError("payload size too small")
    value["padding"] = "x" * (size - len(raw))
    return json.dumps(value, separators=(",", ":")).encode()


def publish(path, data, sync):
    pending = path.with_suffix(".pending")
    with pending.open("xb") as stream:
        stream.write(data)
        stream.flush()
        if sync:
            os.fsync(stream.fileno())
    os.link(pending, path)
    pending.unlink()
    if sync:
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def replay(root, count):
    previous = bytes(32)
    for sequence in range(1, count + 1):
        frame = (root / f"{sequence:08}.evt").read_bytes()
        if len(frame) != 80 or frame[:8] != b"EXPER001":
            raise ValueError("frame shape")
        if struct.unpack("<Q", frame[8:16])[0] != sequence or frame[16:48] != previous:
            raise ValueError("sequence/chain")
        raw = (root / frame[48:].hex()).read_bytes()
        if hashlib.sha256(raw).digest() != frame[48:]:
            raise ValueError("payload digest")
        if json.loads(raw)["sequence"] != sequence:
            raise ValueError("payload sequence")
        previous = hashlib.sha256(frame).digest()
    return previous.hex()


def measure(parent, count, size, sync, repeats):
    with tempfile.TemporaryDirectory(prefix="intent-capacity-", dir=parent) as temp:
        root = Path(temp)
        previous = bytes(32)
        started = time.perf_counter()
        for sequence in range(1, count + 1):
            raw = payload(sequence, size)
            digest = hashlib.sha256(raw).digest()
            publish(root / digest.hex(), raw, sync)
            frame = b"EXPER001" + struct.pack("<Q", sequence) + previous + digest
            publish(root / f"{sequence:08}.evt", frame, sync)
            previous = hashlib.sha256(frame).digest()
        write_seconds = time.perf_counter() - started
        stats = [p.stat() for p in root.iterdir()]
        replay_times = []
        for _ in range(repeats):
            started = time.perf_counter()
            head = replay(root, count)
            replay_times.append(time.perf_counter() - started)
            if head != previous.hex():
                raise ValueError("head mismatch")
        return {"events": count, "payload_bytes": size, "sync": sync,
                "files": len(stats), "logical_bytes": sum(s.st_size for s in stats),
                "allocated_file_bytes": sum(s.st_blocks * 512 for s in stats),
                "write_seconds": write_seconds, "warm_replay_seconds": replay_times,
                "warm_replay_median": statistics.median(replay_times), "head": head}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--counts", type=int, nargs="+", default=[256, 1024, 4096])
    parser.add_argument("--sizes", type=int, nargs="+", default=[1024, 16384])
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()
    if any(n < 1 or n > 65536 for n in args.counts):
        parser.error("experiment count must be 1..65536")
    if any(s < 1024 or s > 262144 for s in args.sizes):
        parser.error("experiment payload must be 1024..262144")
    if max(args.counts) * max(args.sizes) > 256 * 1024**2:
        parser.error("experiment logical payload budget is 256 MiB per case")
    result = {"schema": "golem.experiment.intent-capacity.v1",
              "implementation": "python synthetic 80-byte frame + raw CAS model",
              "not_validated": ["native reducer", "cold replay", "power loss", "ENOSPC",
                                "rollover", "authority lock", "physical directory overhead"],
              "platform": platform.platform(), "python": platform.python_version(),
              "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cases": [measure(args.parent, n, s, args.sync, 3)
                        for s in args.sizes for n in args.counts]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
