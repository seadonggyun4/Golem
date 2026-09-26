"""Local benchmark collection and fail-closed, environment-matched comparison."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

METRICS = (
    "transition_cycle", "transition_replay", "journal_encode", "journal_decode",
    "journal_append_fsync", "digest_4k", "digest_1m", "json_encode", "json_decode",
    "msgpack_encode", "msgpack_decode",
)
ENV_KEYS = ("compiler", "build_flags", "workload_sha256", "configuration", "sanitized", "openssl", "json_c", "version")
DEFAULT_THRESHOLDS = {name: 0.35 if name == "journal_append_fsync" else 0.20 for name in METRICS}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(text):
    return json.loads(text, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite {value}")))


def positive(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value > 0
    except OverflowError:
        return False


def summary(samples):
    require(isinstance(samples, list) and len(samples) >= 3, "at least three samples required")
    values = []
    for sample in samples:
        require(isinstance(sample, dict) and set(sample) == {"iterations", "elapsed_ns"}, "invalid sample fields")
        require(type(sample["iterations"]) is int and 1 <= sample["iterations"] <= 1000000, "invalid iterations")
        require(type(sample["elapsed_ns"]) is int and 0 < sample["elapsed_ns"] < 10**15, "invalid duration")
        values.append(sample["elapsed_ns"] / sample["iterations"])
    median = statistics.median(values)
    return {"median_ns_per_op": median, "min_ns_per_op": min(values), "max_ns_per_op": max(values),
            "relative_mad": statistics.median(abs(x - median) for x in values) / median}


def validate(report):
    require(isinstance(report, dict) and type(report.get("schema")) is int and report["schema"] == 1
            and type(report.get("workload_version")) is int and report["workload_version"] == 1,
            "unsupported benchmark schema/workload")
    require(report.get("mode") in ("baseline", "smoke"), "invalid mode")
    env = report.get("environment")
    require(isinstance(env, dict), "missing environment")
    for key in (*ENV_KEYS, "system", "release", "architecture", "cpu", "storage_device", "environment_id"):
        require(key in env, f"missing environment field: {key}")
        if key == "sanitized":
            require(type(env[key]) is bool, "invalid sanitizer flag")
        elif key == "cpu" and env[key] is None:
            require(isinstance(env.get("cpu_probe_error"), str) and
                    0 < len(env["cpu_probe_error"]) <= 128, "missing CPU probe failure")
        else:
            require(isinstance(env[key], str) and 0 < len(env[key]) <= 1024, f"invalid {key}")
    require(isinstance(report.get("metrics"), dict) and set(report["metrics"]) == set(METRICS), "metric set mismatch")
    require(isinstance(report.get("settings"), dict), "missing settings")
    require(positive(report["settings"].get("target_ms")) and report["settings"]["target_ms"] <= 1000, "invalid target duration")
    expected_count = report["settings"].get("sample_count")
    require(type(expected_count) is int and 3 <= expected_count <= 31, "invalid sample count")
    for name, data in report["metrics"].items():
        require(isinstance(data, dict), f"invalid metric {name}")
        require(type(data.get("bytes_per_op")) is int and 0 <= data["bytes_per_op"] <= 1048576, "invalid byte count")
        require(type(data.get("events_per_op")) is int and data["events_per_op"] > 0, "invalid event count")
        require(type(data.get("durable")) is bool and data["durable"] == (name == "journal_append_fsync"), "invalid durability")
        summary(data.get("samples"))
        require(len(data["samples"]) == expected_count, "sample count mismatch")
    return report


def read(path):
    require(path.stat().st_size <= 4 * 1024 * 1024, "report exceeds 4 MiB")
    return validate(load(path.read_text()))


def compare(baseline, candidate, thresholds=None, max_noise=0.10):
    validate(baseline); validate(candidate)
    require(positive(max_noise) and max_noise <= 1, "invalid noise limit")
    thresholds = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    require(isinstance(thresholds, dict) and set(thresholds) == set(METRICS), "threshold metric set mismatch")
    require(all(positive(v) and v <= 1 for v in thresholds.values()), "thresholds must be in (0, 1]")
    require(baseline["environment"].get("cpu") is not None and
            candidate["environment"].get("cpu") is not None,
            "CPU metadata unavailable: measurements retained, comparison not qualified")
    require(baseline["environment"] == candidate["environment"], "environment mismatch: do not compare different hosts/toolchains")
    require(baseline["settings"] == candidate["settings"], "measurement settings mismatch")
    for report in (baseline, candidate):
        require(report["mode"] == "baseline" and report["environment"]["configuration"] == "Release"
                and not report["environment"]["sanitized"], "comparison requires unsanitized Release baseline runs")
    rows = []; regression = False; noisy = False
    for name in METRICS:
        old, new = baseline["metrics"][name], candidate["metrics"][name]
        require(all(old[k] == new[k] for k in ("bytes_per_op", "events_per_op", "durable")), f"workload mismatch: {name}")
        require(len(old["samples"]) >= 5 and len(new["samples"]) >= 5, "comparison requires at least five samples")
        a, b = summary(old["samples"]), summary(new["samples"])
        delta = b["median_ns_per_op"] / a["median_ns_per_op"] - 1
        unstable = max(a["relative_mad"], b["relative_mad"]) > max_noise
        status = "inconclusive" if unstable else "regression" if b["median_ns_per_op"] > a["median_ns_per_op"] * (1 + thresholds[name]) else "pass"
        noisy |= unstable; regression |= status == "regression"
        rows.append({"metric": name, "change_fraction": delta, "threshold_fraction": thresholds[name],
                     "baseline": a, "candidate": b, "status": status})
    return {"status": "regression" if regression else "inconclusive" if noisy else "pass", "metrics": rows}


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest():
    root = Path(__file__).resolve().parent.parent
    files = [root / "CMakeLists.txt", root / "CMakePresets.json"]
    for directory in ("src", "include", "bench", "cmake"):
        files.extend(p for p in (root / directory).rglob("*") if p.suffix in (".c", ".h", ".py", ".txt", ".in"))
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def cpu_name():
    if platform.system() == "Darwin":
        return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=5).strip()
    if platform.system() == "Linux":
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    return platform.processor() or platform.machine()


def collect(binary, scratch, environment_id, samples, target_ms, smoke=False):
    require(3 <= samples <= 31 and (smoke or samples >= 5), "sample count must be 5..31 (smoke: 3..31)")
    require(positive(target_ms) and target_ms <= 1000, "target-ms must be in (0, 1000]")
    require(environment_id and len(environment_id) <= 128, "provide a stable, nonprivate environment-id")
    before = file_digest(binary); sources = source_digest()
    try:
        cpu, cpu_error = cpu_name(), None
    except (OSError, subprocess.SubprocessError) as exc:
        cpu, cpu_error = None, type(exc).__name__
    environment = {"system": platform.system(), "release": platform.release(), "architecture": platform.machine(),
                   "cpu": cpu,
                   "storage_device": str(os.stat(scratch).st_dev), "environment_id": environment_id}
    if cpu_error is not None:
        environment["cpu_probe_error"] = cpu_error
    report = {"schema": 1, "workload_version": 1, "mode": "smoke" if smoke else "baseline",
              "created_utc": datetime.now(timezone.utc).isoformat(), "environment": environment,
              "binary_sha256": before, "source_sha256": sources,
              "settings": {"target_ms": target_ms, "sample_count": samples}, "metrics": {}}

    def invoke(metric, iterations, directory):
        completed = subprocess.run([str(binary), metric, str(iterations), directory], text=True,
                                   capture_output=True, check=True, timeout=30)
        row = load(completed.stdout)
        require(row["schema"] == 1 and row["workload_version"] == 1 and row["metric"] == metric
                and row["iterations"] == iterations and positive(row["elapsed_ns"]), "invalid runner output")
        for key in ENV_KEYS:
            if key in environment:
                require(environment[key] == row[key], "runner metadata changed during measurement")
            else:
                environment[key] = row[key]
        require(smoke or (row["configuration"] == "Release" and not row["sanitized"]),
                "baseline requires an unsanitized Release binary; use --smoke for correctness only")
        return row

    with tempfile.TemporaryDirectory(prefix="golem-bench-", dir=scratch) as directory:
        for metric in METRICS:
            loops = 16; limit = 4096 if metric == "journal_append_fsync" else 1000000
            # Independent subprocesses avoid carrying allocator/journal history
            # between samples. Calibration and one warmup per batch are untimed.
            while True:
                row = invoke(metric, loops, directory)
                if row["elapsed_ns"] >= target_ms * 1e6 or loops == limit:
                    break
                loops = min(limit, max(loops + 1, min(loops * 16, math.ceil(loops * target_ms * 1e6 / row["elapsed_ns"])) ))
            data = {key: row[key] for key in ("bytes_per_op", "events_per_op", "durable")}
            data["samples"] = []
            for _ in range(samples):
                row = invoke(metric, loops, directory)
                require(all(row[k] == data[k] for k in ("bytes_per_op", "events_per_op", "durable")), "workload changed")
                data["samples"].append({"iterations": loops, "elapsed_ns": row["elapsed_ns"]})
            report["metrics"][metric] = data
    require(file_digest(binary) == before and source_digest() == sources, "binary/source changed during collection")
    return validate(report)


def write_new(path, report):
    # Never silently replace a reviewed baseline. On failure, a partial report
    # cannot pass schema validation and is left for the caller to inspect.
    with path.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


def projection(report):
    validate(report)
    lines = ["| Metric | ns/op (median) | ops/s | MiB/s | MAD |", "| --- | ---: | ---: | ---: | ---: |"]
    for name, data in report["metrics"].items():
        stats = summary(data["samples"])
        ops = 1e9 / stats["median_ns_per_op"]
        mib = ops * data["bytes_per_op"] / 1048576
        lines.append(f"| {name} | {stats['median_ns_per_op']:.1f} | {ops:.1f} | {mib:.2f} | {stats['relative_mad']:.2%} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--binary", type=Path, required=True)
    run.add_argument("--scratch", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--environment-id", required=True)
    run.add_argument("--samples", type=int, default=7)
    run.add_argument("--target-ms", type=float, default=50)
    run.add_argument("--smoke", action="store_true")
    check = commands.add_parser("compare")
    check.add_argument("baseline", type=Path); check.add_argument("candidate", type=Path)
    check.add_argument("--thresholds", type=Path)
    check.add_argument("--max-noise", type=float, default=0.10)
    show = commands.add_parser("report")
    show.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "run":
            require(not args.output.exists(), "output already exists; baseline overwrite refused")
            report = collect(args.binary.resolve(), args.scratch.resolve(), args.environment_id,
                             args.samples, args.target_ms, args.smoke)
            write_new(args.output, report)
            print(projection(report))
            return 0
        if args.command == "report":
            print(projection(read(args.input)))
            return 0
        thresholds = load(args.thresholds.read_text()) if args.thresholds else None
        result = compare(read(args.baseline), read(args.candidate), thresholds, args.max_noise)
        print(json.dumps(result, indent=2, allow_nan=False))
        return {"pass": 0, "regression": 1, "inconclusive": 2}[result["status"]]
    except (ValueError, OSError, KeyError, TypeError, RecursionError, subprocess.SubprocessError) as error:
        print(f"benchmark: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
