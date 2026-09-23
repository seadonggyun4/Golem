"""Paired event-ring microbenchmark. Not an end-to-end runtime SLO measurement."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
from verify_agent import digest, private_directory, save, strict_json


def summarize(values):
    ordered = sorted(values)
    median = statistics.median(ordered)
    return {"median": median, "p95": ordered[math.ceil(.95 * len(ordered)) - 1],
            "p99": ordered[math.ceil(.99 * len(ordered)) - 1],
            "relative_mad": statistics.median(abs(v - median) for v in ordered) / median}


def sample(binary, observers):
    result = subprocess.run([str(binary), str(observers)], capture_output=True,
                            check=True, timeout=30)
    value = strict_json(result.stdout)
    fields = {"schema", "observers", "iterations", "elapsed_ns", "rss_bytes", "checksum"}
    if (not isinstance(value, dict) or set(value) != fields or
            any(type(value[key]) is not int for key in fields) or
            value.get("schema") != 1 or value.get("observers") != observers or
            value.get("iterations") != 100000 or
            type(value.get("elapsed_ns")) is not int or value["elapsed_ns"] <= 0 or
            type(value.get("rss_bytes")) is not int or value["rss_bytes"] <= 0 or
            value.get("checksum") != observers * 16 * 6250 * 6251 // 2):
        raise ValueError("invalid benchmark sample")
    return value


def collect(binary, profile, output, pairs, seed):
    cache = binary.parent.parent / "CMakeCache.txt"
    if not cache.is_file():
        raise ValueError("benchmark must be in its configured build/bench directory")
    output = private_directory(output)
    identity = {"system": platform.platform(), "machine": platform.machine(),
                "binary_sha256": digest(binary), "profile_file_sha256": digest(profile),
                "collector_sha256": digest(Path(__file__)), "cmake_cache_sha256": digest(cache)}
    environment_digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    # Warmup is separate and never included in the statistics.
    for mode in (0, 1, 32):
        sample(binary, mode)
    rng, raw = random.Random(seed), []
    for pair in range(pairs):
        order = [0, 1, 32]
        rng.shuffle(order)
        samples = [sample(binary, mode) for mode in order]
        row = {"pair": pair, "order": order, "samples": samples}
        raw.append(row)
        save(output / f"pair-{pair:03d}.json", json.dumps(row, indent=2).encode())
    metrics = {}
    for mode in (0, 1, 32):
        values = [next(s for s in row["samples"] if s["observers"] == mode) for row in raw]
        metrics[str(mode)] = {"ns_per_append": summarize([s["elapsed_ns"] / s["iterations"] for s in values]),
                              "rss_high_water_bytes": max(s["rss_bytes"] for s in values)}
    ratios = {}
    for mode in (1, 32):
        values = []
        for row in raw:
            times = {s["observers"]: s["elapsed_ns"] for s in row["samples"]}
            values.append(times[mode] / times[0])
        ratios[str(mode)] = summarize(values)
    if (digest(binary) != identity["binary_sha256"] or
            digest(profile) != identity["profile_file_sha256"] or
            digest(cache) != identity["cmake_cache_sha256"]):
        raise ValueError("benchmark inputs changed during collection; raw samples retained")
    report = {"schema": "golem.runtime-benchmark.v1", "authority": "DERIVED_ONLY",
              "scope": "event-ring append plus synchronous pulls every 16 events",
              "environment": identity, "environment_digest": environment_digest,
              "seed": seed, "pairs": pairs, "metrics": metrics, "paired_ratios": ratios,
              "performance_gate": "NOT_EVALUATED", "actual_agent_verified": False,
              "limitations": ["Not daemon latency, CPU utilization or network performance.",
                               "30 samples do not establish a confident tail-latency estimate.",
                               "The runtime profile is a pinned input, not host attestation.",
                               "End-to-end 5% overhead threshold is inapplicable to a ring-only workload."]}
    save(output / "report.json", json.dumps(report, indent=2).encode())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=30)
    args = parser.parse_args()
    if not 30 <= args.pairs <= 100:
        parser.error("pairs must be 30..100")
    try:
        collect(args.binary.resolve(), args.profile.resolve(), args.output, args.pairs, args.seed)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
