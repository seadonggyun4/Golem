"""Offline clean-source acceptance gate; never publishes or edits the checkout."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SOURCE_DIRS = {"cmake", "include", "src", "tests", "fuzz", "samples"}
SOURCE_FILES = {"CMakeLists.txt", "CMakePresets.json"}


def selected(name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe source path")
    return name in SOURCE_FILES or bool(path.parts and path.parts[0] in SOURCE_DIRS)


def run(args, cwd, env):
    print("+ " + " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True, timeout=900)


def snapshot(root, destination):
    # Include pending source changes for local validation, but never ignored files.
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
    ).decode("utf-8").split("\0")
    ignored = set(subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--ignored", "--exclude-standard"], cwd=root
    ).decode("utf-8").split("\0"))
    count = 0
    for name in sorted(set(names) - ignored - {""}):
        if not selected(name):
            continue
        source = root / name
        if source.is_symlink() or any(p.is_symlink() for p in source.parents if p != root.parent):
            raise ValueError("symlink source is not supported: " + name)
        if not source.exists():
            continue  # Preserve pending tracked deletions in the clean snapshot.
        if not source.is_file():
            raise ValueError("non-file source: " + name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        count += 1
    print(f"Clean C source snapshot: {count} files (no Git metadata or local state)", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.source.resolve(strict=True)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("CMAKE_PREFIX_PATH", None)
    with tempfile.TemporaryDirectory(prefix="golem-alpha-") as tmp:
        # Resolve macOS /var aliases: the CLI deliberately rejects symlink parents.
        work = Path(tmp).resolve()
        source = work / "source"
        source.mkdir()
        snapshot(root, source)
        build, prefix = work / "build", work / "install"
        run(["cmake", "-S", source, "-B", build, "-G", "Ninja",
             "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=ON",
             "-DGOLEM_WARNINGS_AS_ERRORS=ON", "-DGOLEM_BUILD_CLI=ON",
             "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF"], work, env)
        run(["cmake", "--build", build, "--parallel", "2"], work, env)
        run(["ctest", "--test-dir", build, "--output-on-failure", "--no-tests=error"], work, env)
        run(["cmake", "--install", build, "--prefix", prefix], work, env)
        consumer = work / "consumer"
        run(["cmake", "-S", source / "tests/consumer", "-B", consumer, "-G", "Ninja",
             f"-DCMAKE_PREFIX_PATH={prefix}", "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF"], work, env)
        run(["cmake", "--build", consumer], work, env)
        run(["ctest", "--test-dir", consumer, "--output-on-failure", "--no-tests=error"], work, env)
        # Reuse the behavioral contract against the installed binary, from outside the checkout.
        run([sys.executable, source / "tests/c/cli_integration.py", prefix / "bin/golem", work], work, env)
    print("Public Alpha gate passed: clean build, full tests, installed C API and noop CLI.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Public Alpha gate failed: {error}", file=sys.stderr)
        sys.exit(1)
