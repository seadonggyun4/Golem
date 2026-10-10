"""Private, unsigned command observations. Never an authorization or replay engine."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import signal
import stat
import subprocess
import time
import uuid

LIMIT = 32 * 1024 * 1024
SCHEMA = "golem.execution-observation.v1"


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2).encode() + b"\n"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def private_directory(path):
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("symlink output path")
    path.mkdir(mode=0o700)
    return path


def save(path, data, *, durable=True):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        if durable:
            stream.flush()
            os.fsync(stream.fileno())
    if durable:
        fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def git(source, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", str(source), *args], check=True,
                          capture_output=True, timeout=30, env=env).stdout


def source_identity(source):
    """Non-atomic Git worktree identity; excludes ignored files and rejects submodules."""
    entries = git(source, "ls-files", "--stage", "-z").split(b"\0")
    if any(row.startswith(b"160000 ") for row in entries):
        raise ValueError("submodules are not supported by source identity v1")
    names = git(source, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    files = {}
    for raw in sorted(set(names.split(b"\0")) - {b""}):
        name = os.fsdecode(raw)
        path = source / name
        if path.is_symlink():
            files[name] = {"kind": "symlink", "sha256": hashlib.sha256(
                os.fsencode(os.readlink(path))).hexdigest()}
        elif path.is_file():
            files[name] = {"kind": "file", "sha256": digest(path),
                           "executable": bool(path.stat().st_mode & 0o111)}
        elif not path.exists():
            files[name] = {"kind": "deleted"}
        else:
            raise ValueError("unsupported source file kind: " + name)
    status = git(source, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    return {"commit": git(source, "rev-parse", "HEAD").decode().strip(),
            "dirty": bool(status), "status_sha256": hashlib.sha256(status).hexdigest(),
            "diff_sha256": hashlib.sha256(git(source, "diff", "HEAD", "--binary", "--no-ext-diff",
                                               "--no-textconv")).hexdigest(),
            "tree_sha256": hashlib.sha256(encoded(files)).hexdigest(), "files": files}


def source_observation(source, destination):
    phase = "SOURCE_ROOT_UNAVAILABLE"
    try:
        root = Path(os.fsdecode(git(source, "rev-parse", "--show-toplevel")).strip()).resolve()
        if destination == root or root in destination.parents:
            phase = "OUTPUT_IN_SOURCE_NOT_IGNORED"
            git(root, "check-ignore", "--", destination.relative_to(root).as_posix() + "/")
        phase = "SOURCE_IDENTITY_UNAVAILABLE"
        return {"status": "OBSERVED", "root": str(root), **source_identity(root)}
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {"status": "UNAVAILABLE", "requested": str(source),
                "error_type": type(error).__name__, "diagnostic": phase}


def executable_identity(argv, cwd, env):
    name = argv[0]
    path = (Path(name) if Path(name).is_absolute() else cwd / name) if "/" in name else None
    if path is None:
        # PATH entries are interpreted relative to the child's cwd.
        search = os.pathsep.join(str(Path(p) if Path(p).is_absolute() else cwd / p)
                                 for p in env.get("PATH", os.defpath).split(os.pathsep))
        found = shutil.which(name, path=search)
        path = Path(found) if found else None
    try:
        if path is None:
            raise FileNotFoundError(name)
        path = path.resolve(strict=True)
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("executable is not a regular file")
        return {"status": "OBSERVED", "path": str(path), "sha256": digest(path)}
    except (OSError, ValueError) as error:
        return {"status": "UNAVAILABLE", "error_type": type(error).__name__}


def metadata(path):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("record must be a regular file")
    return {"sha256": digest(path), "bytes": path.stat().st_size}


def run_private(argv, *, destination, timeout, env=None, cwd=None, source=None,
                capture_output=False, output_limit=8192):
    """Metadata-only interactive child: never persist prompt-bearing argv or streams."""
    command = list(map(str, argv))
    if not command or any("\0" in s for s in command) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid private process parameters")
    if type(capture_output) is not bool or type(output_limit) is not int or not 0 < output_limit <= LIMIT:
        raise ValueError("invalid private output parameters")
    directory = private_directory(destination)
    cwd = Path(cwd or Path.cwd()).resolve()
    environment = dict(os.environ if env is None else env)
    before = source_observation(Path(source or cwd), directory)
    save(directory / "source-before.json", encoded(before))
    identity = executable_identity(command, cwd, environment)
    save(directory / "started.json", encoded({"schema": "golem.private-process-observation.v1",
        "executable": identity, "timeout_seconds": timeout, "argv_redacted": True,
        "streams_recorded": False, "environment_recorded": False,
        "producer_sha256": digest(Path(__file__)), "started_at": datetime.now(timezone.utc).isoformat()}))
    child, reason = None, "LAUNCH_ERROR"
    started = time.monotonic()
    try:
        child = subprocess.Popen(command, cwd=cwd, env=environment, start_new_session=True,
            stdin=subprocess.DEVNULL if capture_output else None,
            stdout=subprocess.PIPE if capture_output else None, stderr=subprocess.PIPE if capture_output else None)
        reason = "EXIT"
        try:
            if capture_output:
                # Secret streams never touch disk or inherited terminal output.
                buffers, size = {"stdout": bytearray(), "stderr": bytearray()}, 0
                with selectors.DefaultSelector() as selector:
                    for name in buffers:
                        stream = getattr(child, name)
                        os.set_blocking(stream.fileno(), False)
                        selector.register(stream, selectors.EVENT_READ, name)
                    while selector.get_map():
                        if time.monotonic() - started >= timeout:
                            raise subprocess.TimeoutExpired("<redacted>", timeout)
                        for key, _ in selector.select(min(.1, timeout)):
                            data = os.read(key.fileobj.fileno(), 4096)
                            if not data:
                                selector.unregister(key.fileobj)
                                continue
                            size += len(data)
                            if size > output_limit:
                                reason = "OUTPUT_LIMIT"
                                raise ValueError("private output limit exceeded")
                            buffers[key.data].extend(data)
                returncode = child.wait(timeout=max(.001, timeout - (time.monotonic() - started)))
                return subprocess.CompletedProcess([], returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"]))
            return subprocess.CompletedProcess([], child.wait(timeout=timeout))
        except subprocess.TimeoutExpired:
            reason = "TIMEOUT"
            raise subprocess.TimeoutExpired("<redacted>", timeout) from None
    except BaseException:
        if reason == "EXIT":
            reason = "INTERRUPTED"
        raise
    finally:
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                reason = "CLEANUP_DENIED"
                if child.poll() is None:
                    child.kill()
            child.wait()
            if capture_output:
                child.stdout.close()
                child.stderr.close()
        after = source_observation(Path(source or cwd), directory)
        save(directory / "source-after.json", encoded(after))
        save(directory / "result.json", encoded({"schema": "golem.private-process-result.v1",
            "returncode": child.returncode if child else None, "reason": reason,
            "elapsed_seconds": time.monotonic() - started,
            "source_unchanged": before == after if before["status"] == after["status"] == "OBSERVED" else None,
            "executable_unchanged": executable_identity(command, cwd, environment) == identity}))


def _private_existing(path):
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError("symlink output path")
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("output directory must be private and owned by this user")


def _extra_logs(names):
    if not isinstance(names, (tuple, list)):
        raise ValueError("additional logs must be a list")
    names = tuple(names)
    if (any(not isinstance(n, str) or
            not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}\.log", n) or
            n in ("stdout.log", "stderr.log") for n in names) or len(set(names)) != len(names)):
        raise ValueError("invalid additional log names")
    return names


def _over_limit(paths, limit):
    for path in paths:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("capture log is not a regular file")
        if info.st_size > limit:
            return True
    return False


def capture(argv, destination, timeout, cwd=None, *, source=None, env=None, limit=LIMIT,
            extra_logs=()):
    """Record once before launch and once after reaping; never retry effects."""
    command = list(map(str, argv))
    if not command or any("\0" in s for s in command) or not math.isfinite(timeout) or timeout <= 0 or limit < 1:
        raise ValueError("invalid capture parameters")
    cwd = Path(cwd or Path.cwd()).resolve()
    destination = Path(destination).absolute()
    _private_existing(destination)
    extra_logs = _extra_logs(extra_logs)
    if any((destination / name).exists() or (destination / name).is_symlink()
           for name in ("stdout.log", "stderr.log", *extra_logs)):
        raise FileExistsError("capture logs already exist")
    record_dir = private_directory(destination / "execution")
    environment = dict(env) if env is not None else {
        k: v for k, v in os.environ.items()
        if not k.startswith("GIT_") and k not in ("PYTHONPATH", "PYTHONHOME")}
    source = Path(source).resolve() if source is not None else cwd
    before = source_observation(source, destination)
    save(record_dir / "source-before.json", encoded(before))
    binary = executable_identity(command, cwd, environment)
    start = {"schema": SCHEMA, "invocation_id": uuid.uuid4().hex,
             "started_at": datetime.now(timezone.utc).isoformat(), "argv": command,
             "cwd": str(cwd), "timeout_seconds": timeout, "output_limit_bytes": limit,
             "extra_logs": list(extra_logs),
             "executable": binary, "source_status": before["status"],
             "producer_sha256": digest(Path(__file__)),
             "python": platform.python_version(), "system": platform.system(),
             "environment_recorded": False, "state": "STARTED", "product_acceptance": False}
    save(record_dir / "started.json", encoded(start))
    native = private_directory(destination / "native")
    environment["GOLEM_RECORD_ROOT"] = str(native)
    environment["GOLEM_RECORD_SOURCE_MANIFEST"] = str(record_dir / "source-before.json")
    paths = [destination / name for name in ("stdout.log", "stderr.log", *extra_logs)]
    process, error, returncode = None, None, None
    reason = "EXIT"
    started = time.monotonic()
    try:
        for path in paths[2:]:
            save(path, b"")
        with paths[0].open("xb") as out, paths[1].open("xb") as err:
            os.chmod(paths[0], 0o600)
            os.chmod(paths[1], 0o600)
            process = subprocess.Popen(command, cwd=cwd, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    if time.monotonic() - started > timeout:
                        reason = "TIMEOUT"
                        break
                    if _over_limit(paths, limit):
                        reason = "OUTPUT_LIMIT"
                        break
                    time.sleep(0.01)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    reason = "CLEANUP_DENIED"
                    if process.poll() is None:
                        process.kill()
                returncode = process.wait(timeout=5)
            out.flush(); err.flush()
            os.fsync(out.fileno()); os.fsync(err.fileno())
        for path in paths[2:]:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise ValueError("capture log is not a regular file")
                os.fsync(fd)
            finally:
                os.close(fd)
        if reason != "CLEANUP_DENIED" and _over_limit(paths, limit):
            reason = "OUTPUT_LIMIT"
    except BaseException as exc:
        error = exc
        reason = "LAUNCH_ERROR" if process is None else "CAPTURE_INTERRUPTED"
    elapsed = round(time.monotonic() - started, 6)
    result = {"returncode": returncode, "reason": reason, "elapsed_seconds": elapsed,
              "logs": {}, "recording": "INCOMPLETE", "record_path": str(record_dir)}
    try:
        result["logs"] = {p.name: metadata(p)["sha256"] for p in paths if p.exists() or p.is_symlink()}
        after = source_observation(source, destination)
        save(record_dir / "source-after.json", encoded(after))
        binary_after = executable_identity(command, cwd, environment)
        native_files, native_complete = native_inventory(native)
        result["native_recording"] = ("NOT_OBSERVED" if not native_files else
                                      "RECORDED" if native_complete else "INCOMPLETE")
        result["recording"] = "RECORDED"
        finish = {"schema": SCHEMA, "invocation_id": start["invocation_id"],
                  "finished_at": datetime.now(timezone.utc).isoformat(), "state": "FINISHED",
                  "process": dict(result), "executable_after": binary_after,
                  "executable_unchanged": binary == binary_after if binary["status"] == "OBSERVED" else None,
                  "source_unchanged": before == after if before["status"] == after["status"] == "OBSERVED" else None,
                  "producer_unchanged": digest(Path(__file__)) == start["producer_sha256"],
                  "error_type": type(error).__name__ if error else None,
                  "errno": getattr(error, "errno", None), "product_acceptance": False}
        save(record_dir / "result.json", encoded(finish))
        files = {p.name: metadata(p) for p in record_dir.iterdir() if p.is_file()}
        logs = {p.name: metadata(p) for p in paths if p.is_file()}
        save(record_dir / "manifest.json", encoded({"schema": "golem.execution-manifest.v1",
             "files": files, "logs": logs, "native_files": native_files}))
    except (OSError, ValueError) as exc:
        result.update(recording="INCOMPLETE", reason="RECORDING_ERROR", process_reason=reason,
                      recording_error=type(exc).__name__)
    if error is not None:
        raise error
    return result


def native_inventory(root):
    """Bind observed native files, including incomplete scopes, without claiming coverage."""
    _private_existing(root)
    inventory, complete = {}, True
    for scope in root.iterdir():
        if len(scope.name) != 32 or any(c not in "0123456789abcdef" for c in scope.name):
            raise ValueError("invalid native record id")
        _private_existing(scope)
        inventory[scope.name + "/"] = {"kind": "directory"}
        names = {p.name for p in scope.iterdir()}
        complete = complete and {"started.json", "result.json", "manifest.json"} <= names
        for p in scope.iterdir():
            if p.name not in {"started.json", "result.json", "manifest.json", ".pending", "stdout.log", "stderr.log"}:
                raise ValueError("unexpected native artifact")
            inventory[p.relative_to(root).as_posix()] = metadata(p)
        if {"started.json", "result.json", "manifest.json"} <= names:
            try:
                manifest = json.loads((scope / "manifest.json").read_bytes())
                result = json.loads((scope / "result.json").read_bytes())
                valid = (isinstance(manifest, dict) and set(manifest) == names - {"manifest.json"}
                         and result.get("state") == "FINISHED" and result.get("recording_status") == 0
                         and all(inventory[scope.name + "/" + name]["sha256"] == value
                                 for name, value in manifest.items()))
                complete = complete and valid
            except (ValueError, KeyError, TypeError, AttributeError):
                complete = False
    return inventory, complete


def check(destination):
    """Verify a fixed inventory; never accept a missing finish/manifest as success."""
    destination = Path(destination).absolute()
    _private_existing(destination)
    record = destination / "execution"
    _private_existing(record)
    expected = {"started.json", "source-before.json", "source-after.json", "result.json"}
    def load(name):
        path = record / name
        metadata(path)
        if path.stat().st_size > LIMIT:
            raise ValueError("record too large")
        return json.loads(path.read_bytes())
    manifest = load("manifest.json")
    start = load("started.json")
    extra_logs = _extra_logs(start.get("extra_logs", []))
    if (manifest.get("schema") != "golem.execution-manifest.v1" or
            set(manifest.get("files", {})) != expected or
            set(manifest.get("logs", {})) - {"stdout.log", "stderr.log", *extra_logs} or
            set(extra_logs) - manifest.get("logs", {}).keys() or
            {p.name for p in record.iterdir()} != expected | {"manifest.json"}):
        raise ValueError("invalid record inventory")
    for name, meta in manifest["files"].items():
        if metadata(record / name) != meta:
            raise ValueError("record digest mismatch")
    for name, meta in manifest["logs"].items():
        if metadata(destination / name) != meta:
            raise ValueError("log digest mismatch")
    if "native_files" in manifest:
        native_files, _ = native_inventory(destination / "native")
        if native_files != manifest["native_files"]:
            raise ValueError("native record digest mismatch")
    elif (destination / "native").exists():
        raise ValueError("unbound native records")
    start, finish = load("started.json"), load("result.json")
    if (start.get("schema") != SCHEMA or finish.get("schema") != SCHEMA or
            start.get("state") != "STARTED" or finish.get("state") != "FINISHED" or
            not start.get("invocation_id") or start["invocation_id"] != finish.get("invocation_id")):
        raise ValueError("invalid execution lifecycle")
    return {"integrity": "PASS", "process": finish["process"],
            "source_unchanged": finish["source_unchanged"],
            "source_before_status": start["source_status"],
            "executable_unchanged": finish["executable_unchanged"],
            "authenticity_verified": False, "product_acceptance": False}


def run(argv, *, destination, timeout=30, cwd=None, source=None, env=None, check=True):
    """Checked subprocess.run adapter. Caller chooses a new durable directory."""
    destination = private_directory(destination)
    result = capture(argv, destination, timeout, cwd, source=source, env=env)
    if result["reason"] != "EXIT":
        raise subprocess.SubprocessError("recorded command incomplete: " + result["reason"] + "; " + str(destination))
    stdout = (destination / "stdout.log").read_bytes()
    stderr = (destination / "stderr.log").read_bytes()
    if check and result["returncode"]:
        raise subprocess.CalledProcessError(result["returncode"], list(map(str, argv)), stdout, stderr)
    completed = subprocess.CompletedProcess(list(map(str, argv)), result["returncode"], stdout, stderr)
    completed.observation = result
    return completed


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Verify private command records without executing commands.")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.destination), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"integrity": "FAIL", "error_type": type(exc).__name__,
                          "product_acceptance": False}), file=sys.stderr)
        sys.exit(1)
