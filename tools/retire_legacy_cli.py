"""Audit/quarantine a recognized Python prototype launcher, never a native CLI.

No command is executed and no package is uninstalled. Stop concurrent installers
first. Apply requires the exact digest printed by the read-only audit.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat

TEMPLATES = (
    "import sys\nfrom golem.cli import main\nif __name__ == '__main__':\n    sys.exit(main())\n",
    "import re\nimport sys\nfrom golem.cli import main\nif __name__ == '__main__':\n"
    "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n    sys.exit(main())\n",
    "import sys\nfrom golem.cli import main\nif __name__ == '__main__':\n"
    "    if sys.argv[0].endswith('.exe'):\n        sys.argv[0] = sys.argv[0][:-4]\n    sys.exit(main())\n",
)


def recognized(data):
    if not data.startswith(b"#!") or len(data) > 8192:
        return False
    try:
        tree = ast.dump(ast.parse(data.decode("utf-8")))
        return any(tree == ast.dump(ast.parse(template)) for template in TEMPLATES)
    except (UnicodeError, SyntaxError, ValueError):
        return False


def retire(path, expected=None):
    path = Path(path).absolute()
    # The user selects the exact path; do not search and delete PATH entries.
    if path.name != "golem":
        raise ValueError("Expected an explicitly selected golem launcher")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 8192:
            raise ValueError("Not a bounded regular Python launcher")
        data = os.read(fd, 8193)
        if not recognized(data):
            raise ValueError("Unrecognized launcher; native binaries and custom wrappers are untouched")
        digest = hashlib.sha256(data).hexdigest()
        backup = path.with_name("golem-prototype.retired-" + digest)
        result = {"path": str(path), "sha256": digest, "backup": str(backup), "changed": False}
        if expected is None:
            return result
        if expected != digest:
            raise ValueError("Launcher changed since audit")
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("Launcher identity changed")
        # No-overwrite backup publication before removing the original name.
        os.link(path, backup, follow_symlinks=False)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
            current = path.lstat()
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError("Launcher identity changed; backup retained")
            os.lseek(fd, 0, os.SEEK_SET)
            if hashlib.sha256(os.read(fd, 8193)).hexdigest() != digest:
                raise ValueError("Launcher contents changed; backup retained")
            path.unlink()
            os.fsync(directory)
        finally:
            os.close(directory)
        result["changed"] = True
        return result
    finally:
        os.close(fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--apply-sha256", help="explicitly quarantine exactly the audited launcher")
    args = parser.parse_args()
    print(json.dumps(retire(args.path, args.apply_sha256), indent=2))
