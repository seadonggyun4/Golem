"""Deploy an already-created Conan package without depending on its cache paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def install(conan, reference, prefix, bin_dir):
    prefix = prefix.expanduser().absolute()
    bin_dir = bin_dir.expanduser().absolute()
    link = bin_dir / "golem"
    if prefix.exists() or prefix.is_symlink() or os.path.lexists(link):
        raise ValueError("Refusing to replace an existing installation or golem command")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    # full_deploy copies all dependency packages, preserving licenses and layout.
    # Temporary output is published only after the deployed executable passes.
    with tempfile.TemporaryDirectory(prefix=".golem-install-", dir=prefix.parent) as tmp:
        staging = Path(tmp) / "payload"
        subprocess.run([conan, "install", "--requires=" + reference,
                        "--no-remote", "-o", "golem/*:with_cli=True",
                        "--deployer=full_deploy", "--deployer-folder=" + str(staging),
                        "--output-folder=" + str(Path(tmp) / "generators")], check=True)
        candidates = list((staging / "full_deploy/host/golem").glob("**/bin/golem"))
        if len(candidates) != 1:
            raise ValueError("Expected exactly one deployed Golem executable")
        executable = candidates[0]
        # Standalone CLI installation currently supports static dependency packages.
        shared = [p for pattern in ("*.dylib", "*.so*") for p in staging.rglob(pattern)
                  if p.parent.name in ("lib", "lib64")]
        if shared:
            raise ValueError("Shared dependencies require a run environment; use static dependencies")
        subprocess.run([str(executable), "--version"], check=True)
        package = executable.parent.parent
        for name in ("LICENSE", "NOTICE", "COMMERCIAL-LICENSE.md"):
            if not (package / "licenses" / name).is_file():
                raise ValueError("Missing legal file: " + name)
        relative = executable.relative_to(staging)
        manifest = {"reference": reference, "executable": str(relative),
                    "sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}
        (staging / "installation.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staging.rename(prefix)
        link.symlink_to(prefix / relative)
    print("Installed:", link)
    print("Installation and dependency licenses:", prefix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conan", default="conan")
    parser.add_argument("--reference", default="golem/0.1.0")
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local/bin")
    args = parser.parse_args()
    install(args.conan, args.reference, args.prefix, args.bin_dir)
