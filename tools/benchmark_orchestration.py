"""Read-only CLI latency samples: includes process startup and journal replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

from benchmark_runtime import summarize
from verify_agent import digest, private_directory, save, strict_json


def commands(cli, work, history, admission, candidates, group, candidate):
    return {
        "history": [cli, "work", "history", work, history],
        "events": [cli, "events", admission, "--jsonl"],
        "diff": [cli, "candidate", "diff", candidates, group, candidate],
        "template": [cli, "workflow", "template", "show", "feature"],
    }


def sample(argv, kind):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    started = time.perf_counter_ns()
    process = subprocess.run(list(map(str, argv)), stdin=subprocess.DEVNULL,
                             capture_output=True, env=env, timeout=30, check=True)
    elapsed = time.perf_counter_ns() - started
    if kind == "events":
        rows = [strict_json(line) for line in process.stdout.splitlines()]
        if not rows or rows[0].get("count") != len(rows) - 1:
            raise ValueError("incomplete event response")
    elif not isinstance(strict_json(process.stdout), dict):
        raise ValueError("invalid projection response")
    return {"elapsed_ns": elapsed, "bytes": len(process.stdout),
            "sha256": hashlib.sha256(process.stdout).hexdigest()}


def collect(command_map, output, repeats=30, seed=32):
    if type(repeats) is not int or not 5 <= repeats <= 100:
        raise ValueError("repeats must be 5..100")
    if set(command_map) != {"history", "events", "diff", "template"}:
        raise ValueError("all four workloads required")
    inputs = {Path(arg).resolve() for argv in command_map.values() for arg in argv
              if Path(arg).is_file()}
    inputs.update(Path(__file__).with_name(name).resolve()
                  for name in ("benchmark_orchestration.py", "benchmark_runtime.py", "verify_agent.py"))
    cache = Path(command_map["template"][0]).resolve().parent / "CMakeCache.txt"
    if cache.is_file():
        inputs.add(cache)
    hashes = {str(path): digest(path) for path in sorted(inputs)}
    identity = {"host": platform.platform(), "machine": platform.machine(),
                "cli_sha256": digest(Path(command_map["template"][0])),
                "collector_sha256": digest(Path(__file__)), "scope": "CLI wall-clock ns"}
    output = private_directory(output)
    warm = {name: sample(argv, name) for name, argv in command_map.items()}
    save(output / "warmup.json", json.dumps(warm, indent=2).encode())
    rng, raw = random.Random(seed), []
    for index in range(repeats):
        order = list(command_map)
        rng.shuffle(order)
        row = {name: sample(command_map[name], name) for name in order}
        save(output / f"sample-{index:03d}.json", json.dumps(row, indent=2).encode())
        if any(row[name]["sha256"] != warm[name]["sha256"] for name in row):
            raise ValueError("projection changed during measurement; samples retained")
        raw.append(row)
    if any(not Path(path).is_file() or digest(Path(path)) != value for path, value in hashes.items()):
        raise ValueError("benchmark inputs changed during measurement")
    report = {"schema": "golem.orchestration-benchmark.v1", "authority": "DERIVED_ONLY",
              "environment": identity, "input_files": hashes, "repeats": repeats, "seed": seed,
              "commands_sha256": hashlib.sha256(json.dumps(
                  {k: list(map(str, v)) for k, v in command_map.items()}, sort_keys=True).encode()).hexdigest(),
              "metrics": {name: summarize([row[name]["elapsed_ns"] for row in raw]) for name in warm},
              "performance_gate": "NOT_EVALUATED", "actual_agent_verified": False,
              "limitations": ["No stable-runner baseline comparison; not an SLO or speedup claim.",
                              "Small samples do not establish reliable tail latency.",
                              "Workload is an existing pinned projection, not a concurrent live Work."]}
    save(output / "report.json", json.dumps(report, indent=2).encode())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cli", "work", "history-request", "admission", "candidates", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--repeats", type=int, default=30)
    args = parser.parse_args()
    try:
        collect(commands(args.cli.resolve(), args.work, args.history_request, args.admission,
                         args.candidates, args.group, args.candidate), args.output, args.repeats)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
