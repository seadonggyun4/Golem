"""Offline clean-source acceptance gate; never publishes or edits the checkout."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_policy import selected, export_sources


def run(args, cwd, env):
    print("+ " + " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True, timeout=900)


def snapshot(root, destination):
    names = export_sources(root, destination)
    print(f"Clean C source snapshot: {len(names)} files (no Git metadata or local state)", flush=True)


def audit_install(prefix, platform=None):
    """Reject unexpected files in the default static C/CLI installation."""
    required = {"bin/golem", "include/golem/completion.h", "lib/libgolem.a",
                "share/licenses/Golem/LICENSE", "share/licenses/Golem/NOTICE"}
    platform = platform or sys.platform
    if platform == "linux":
        required.add("bin/golem-cgroup-exec")
    found = set()
    for path in prefix.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink in installed package")
        if path.is_dir():
            continue
        name = path.relative_to(prefix).as_posix()
        parts = path.relative_to(prefix).parts
        allowed = name in ("bin/golem", "lib/libgolem.a")
        allowed |= platform == "linux" and name == "bin/golem-cgroup-exec"
        allowed |= len(parts) == 3 and parts[:2] == ("include", "golem") and path.suffix == ".h"
        allowed |= (len(parts) == 4 and parts[:3] == ("lib", "cmake", "Golem") and
                    path.name.startswith("Golem") and path.suffix == ".cmake")
        allowed |= (len(parts) == 4 and parts[:3] == ("share", "licenses", "Golem") and
                    path.name in ("LICENSE", "NOTICE", "COMMERCIAL-LICENSE.md"))
        if not path.is_file() or not allowed:
            raise ValueError("unexpected installed package asset")
        found.add(name)
    if not required <= found:
        raise ValueError("incomplete installed C/CLI package")
    print(f"Installed package inventory: {len(found)} allowlisted files", flush=True)


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
             "-DCMAKE_INSTALL_LIBDIR=lib",
             "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF"], work, env)
        run(["cmake", "--build", build, "--parallel", "2"], work, env)
        run(["ctest", "--test-dir", build, "--parallel", "2",
             "--output-on-failure", "--no-tests=error"], work, env)
        run(["cmake", "--install", build, "--prefix", prefix], work, env)
        audit_install(prefix)
        consumer = work / "consumer"
        run(["cmake", "-S", source / "tests/consumer", "-B", consumer, "-G", "Ninja",
             f"-DCMAKE_PREFIX_PATH={prefix}", "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF"], work, env)
        run(["cmake", "--build", consumer], work, env)
        run(["ctest", "--test-dir", consumer, "--output-on-failure", "--no-tests=error"], work, env)
        # Reuse the behavioral contract against the installed binary, from outside the checkout.
        run([sys.executable, source / "tests/c/cli_integration.py", prefix / "bin/golem", work], work, env)
        # Exercise the shipped executable, not the build-tree binary, through E28.
        compiler = shutil.which("cc")
        if not compiler:
            raise ValueError("C compiler is required for installed conformance")
        run([sys.executable, source / "tests/c/conformance_integration.py",
             prefix / "bin/golem", source, compiler], work, env)
        # Phase31 gates run against the installed CLI, never only the build tree.
        for script in ("execution_bundle_integration.py", "execution_boundary_integration.py",
                       "execution_change_integration.py", "proof_integration.py"):
            run([sys.executable, source / "tests/c" / script,
                 prefix / "bin/golem", source, compiler], work, env)
        run([prefix / "bin/golem", "candidate", "validate",
             source / "samples/candidates/group.json"], work, env)
    print("Public Alpha gate passed: clean build, full tests, installed C API, noop and fixture conformance. "
          "Actual-agent qualification is separate.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Public Alpha gate failed: {error}", file=sys.stderr)
        sys.exit(1)
