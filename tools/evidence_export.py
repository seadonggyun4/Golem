"""Explicit private evidence closure; never a Work permission or backup engine."""
import argparse
from collections import deque
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

import evidence_contract as contract
from execution_record import encoded, private_directory, save

SCHEMA = "golem.evidence-export.v1"
CATALOG = "golem.evidence-export-catalog.v1"
LINKS = "golem.evidence-links.v1"
ADAPTERS = {"opaque.v1", "links.v1", "verification.v1", "research-digests.v1", "observation-manifest.v1"}
REASONS = {"SECRET", "PRIVACY", "OUT_OF_SCOPE", "OPERATOR_EXCLUDED"}
MAX_NODES = 1024
MAX_EDGES = 8192
MAX_DEPTH = 64
MAX_OBJECT = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_METADATA = 2 * 1024 * 1024
CLAIMS = {"scope": "DECLARED_TYPED_REFERENCES_ONLY", "content_truth": "NOT_ESTABLISHED",
          "authenticity": "NOT_VERIFIED", "acceptance_authorized": False,
          "remote_latest_verified": False, "privacy": "PRIVATE_REVIEW_REQUIRED",
          "secret_detection": "NOT_PERFORMED"}


def require(condition, message):
    if not condition:
        raise ValueError("EVIDENCE_EXPORT: " + message)


def is_digest(value):
    return isinstance(value, str) and contract.HEX.fullmatch(value) is not None


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("EVIDENCE_EXPORT: non-finite JSON number")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("EVIDENCE_EXPORT: invalid JSON encoding/depth") from error


def relative_path(name):
    require(isinstance(name, str), "unsafe source path")
    relative = PurePosixPath(name)
    require(name and len(name) <= 4096 and relative.parts and not relative.is_absolute()
            and relative.as_posix() == name and ".." not in relative.parts
            and "\\" not in name and not any(ord(c) < 32 for c in name), "unsafe source path")
    return relative


def safe_read(root, name, limit):
    """Descriptor-relative traversal rejects symlinks, FIFOs and parent escapes."""
    relative = relative_path(name)
    root = Path(root).absolute()
    require(".." not in root.parts, "unsafe source root")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root.anchor, flags)
    try:
        for part in (*root.parts[1:], *relative.parts[:-1]):
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(child, "rb") as stream:
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "regular file required")
            require(os.fstat(stream.fileno()).st_size <= limit, "file size limit")
            data = stream.read(limit + 1)
            require(len(data) <= limit, "file size limit")
            return data
    finally:
        os.close(fd)


def reference(value):
    require(isinstance(value, dict), "invalid reference")
    if set(value) == {"sha256"}:
        require(is_digest(value["sha256"]), "invalid reference digest")
        return value
    require(set(value) == {"external"} and isinstance(value["external"], str)
            and 0 < len(value["external"]) <= 4096, "invalid external reference")
    # The locator remains in reviewed raw bytes, never in diagnostic metadata.
    return {"external_sha256": contract.sha256(value["external"].encode())}


def references(adapter, data):
    require(adapter in ADAPTERS, "unsupported adapter")
    if adapter == "opaque.v1":
        return []
    value = strict_json(data)
    require(isinstance(value, dict), "JSON object required")
    refs = []
    if adapter == "links.v1":
        require(set(value) == {"schema", "references"} and value["schema"] == LINKS
                and isinstance(value["references"], list), "invalid links envelope")
        require(len(value["references"]) <= MAX_EDGES, "edge limit")
        refs = [reference(row) for row in value["references"]]
    elif adapter == "observation-manifest.v1":
        require(set(value) == {"schema", "files"}
                and value["schema"] == "golem.agent-observation-manifest.v1"
                and isinstance(value["files"], dict) and len(value["files"]) <= MAX_NODES
                and "record.json" in value["files"] and "manifest.json" not in value["files"]
                and all(is_digest(d) for d in value["files"].values()), "invalid observation manifest")
        for name in value["files"]:
            relative_path(name)
        refs = [{"sha256": digest} for digest in value["files"].values()]
    elif adapter == "verification.v1":
        contract.validate(value)
        refs = [{"sha256": value["subject"]["sha256"]}]
        refs += [{"sha256": digest} for row in value["checks"].values()
                 for digest in row["evidence_refs"]]
    else:
        # Same typed field convention as native research bundle.c, but transitive.
        # This adapter validates references, not native research acceptance rules.
        require(type(value.get("schema_version")) is int and value["schema_version"] == 1,
                "research schema_version 1 required")
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            require(depth <= MAX_DEPTH, "JSON depth limit")
            if isinstance(item, dict):
                for key, child in item.items():
                    if key in {"digest", "qa_receipt", "supersedes"} or key.endswith("_digest"):
                        if child is not None:
                            require(is_digest(child), "invalid typed research digest")
                            refs.append({"sha256": child})
                    else:
                        pending.append((child, depth + 1))
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
            require(len(refs) <= MAX_EDGES, "edge limit")
    return sorted({json.dumps(ref, sort_keys=True): ref for ref in refs}.values(),
                  key=lambda ref: json.dumps(ref, sort_keys=True))


def catalog_validate(value):
    require(isinstance(value, dict) and set(value) == {"schema", "roots", "objects"}
            and value["schema"] == CATALOG, "invalid catalog")
    roots = value["roots"]
    require(isinstance(roots, list) and 0 < len(roots) <= MAX_NODES
            and all(is_digest(d) for d in roots) and len(set(roots)) == len(roots), "invalid roots")
    objects = value["objects"]
    require(isinstance(objects, dict) and len(objects) <= MAX_NODES, "catalog object limit")
    for digest, row in objects.items():
        require(is_digest(digest) and isinstance(row, dict), "invalid catalog object")
        if row.get("disposition") == "INCLUDE":
            require(set(row) == {"disposition", "adapter", "path", "review"}
                    and isinstance(row["adapter"], str) and row["adapter"] in ADAPTERS
                    and isinstance(row["path"], str)
                    and row["review"] == "PRIVATE_EXPORT_APPROVED", "raw export approval required")
            relative_path(row["path"])
        else:
            require(set(row) == {"disposition", "reason"} and row["disposition"] == "EXCLUDE"
                    and isinstance(row["reason"], str) and row["reason"] in REASONS,
                    "invalid exclusion")
    return value


def walk(roots, resolve):
    queue = deque((digest, 0) for digest in sorted(roots))
    nodes, payloads = {}, {}
    total = edges = 0
    while queue:
        digest, depth = queue.popleft()
        if digest in nodes:
            continue
        require(depth <= MAX_DEPTH and len(nodes) < MAX_NODES, "graph depth/node limit")
        row, data = resolve(digest)
        nodes[digest] = row
        if data is not None:
            total += len(data)
            require(total <= MAX_TOTAL, "total byte limit")
            payloads[digest] = data
        edges += len(row["references"])
        require(edges <= MAX_EDGES, "graph edge limit")
        for ref in row["references"]:
            if "sha256" in ref:
                queue.append((ref["sha256"], depth + 1))
    return nodes, payloads


def node(state, adapter=None, reason=None, data=None):
    return {"state": state, "adapter": adapter, "reason": reason,
            "bytes": len(data) if data is not None else None,
            "references": references(adapter, data) if data is not None else []}


def summary(nodes):
    incomplete = any(row["state"] != "INCLUDED" or any("external_sha256" in ref
                     for ref in row["references"]) for row in nodes.values())
    return "INCOMPLETE" if incomplete else "COMPLETE_DECLARED_SCOPE"


def observation_catalog(bundle, destination, expected_record, approved=False):
    """Bridge an already captured observation, never discover a live Work/CAS."""
    import agent_io
    require(approved is True and is_digest(expected_record), "private raw approval and record pin required")
    bundle, destination = Path(bundle).absolute(), Path(destination).absolute()
    require(destination.parent == bundle.parent, "catalog must be a sibling of observation bundle")
    manifest = safe_read(bundle, "manifest.json", MAX_METADATA)
    inventory = strict_json(manifest)
    references("observation-manifest.v1", manifest)
    _, record_digest = agent_io.load_bundle(bundle)
    require(record_digest == expected_record, "observation record pin mismatch")
    root = contract.sha256(manifest)
    objects = {root: {"disposition": "INCLUDE", "adapter": "observation-manifest.v1",
                     "path": bundle.name + "/manifest.json", "review": "PRIVATE_EXPORT_APPROVED"}}
    for name, digest in sorted(inventory["files"].items()):
        require(digest != root, "observation manifest aliases a payload")
        objects.setdefault(digest, {"disposition": "INCLUDE", "adapter": "opaque.v1",
                                   "path": bundle.name + "/" + name, "review": "PRIVATE_EXPORT_APPROVED"})
    catalog = catalog_validate({"schema": CATALOG, "roots": [root], "objects": objects})
    data = encoded(catalog)
    require(len(data) <= MAX_METADATA, "catalog size limit")
    save(destination, data)
    return {"schema": CATALOG, "sha256": contract.sha256(data), "objects": len(objects),
            "privacy": "PRIVATE_REVIEW_REQUIRED"}


def export(catalog_path, output, expected_catalog=None):
    catalog_path, output = Path(catalog_path).absolute(), Path(output).absolute()
    require(".." not in output.parts, "unsafe output path")
    raw = safe_read(catalog_path.parent, catalog_path.name, MAX_METADATA)
    require(expected_catalog is None or is_digest(expected_catalog)
            and contract.sha256(raw) == expected_catalog, "catalog pin mismatch")
    catalog = catalog_validate(strict_json(raw))
    require(output != catalog_path.parent and catalog_path.parent not in output.parents,
            "output must be outside source staging directory")

    def resolve(digest):
        row = catalog["objects"].get(digest)
        if row is None:
            return node("UNRESOLVED", reason="NOT_IN_CATALOG"), None
        if row["disposition"] == "EXCLUDE":
            return node("EXCLUDED", reason=row["reason"]), None
        try:
            data = safe_read(catalog_path.parent, row["path"], MAX_OBJECT)
        except FileNotFoundError:
            return node("MISSING", adapter=row["adapter"], reason="SOURCE_NOT_FOUND"), None
        require(contract.sha256(data) == digest, "source digest mismatch")
        return node("INCLUDED", adapter=row["adapter"], data=data), data

    nodes, payloads = walk(catalog["roots"], resolve)
    manifest = {"schema": SCHEMA, "roots": sorted(catalog["roots"]), "nodes": nodes,
                "completeness": summary(nodes), **CLAIMS}
    manifest_bytes = encoded(manifest)
    require(len(manifest_bytes) <= MAX_METADATA, "manifest size limit")
    private_directory(output)
    private_directory(output / "data")
    for digest, data in sorted(payloads.items()):
        save(output / "data" / digest, data)
    # Final manifest is the publication boundary; partial directories stay private.
    save(output / "manifest.json", manifest_bytes)
    return verify(output, contract.sha256(manifest_bytes))


def verify(directory, expected_manifest=None):
    directory = Path(directory).absolute()
    raw = safe_read(directory, "manifest.json", MAX_METADATA)
    digest = contract.sha256(raw)
    require(expected_manifest is None or is_digest(expected_manifest)
            and expected_manifest == digest, "manifest pin mismatch")
    manifest = strict_json(raw)
    require(isinstance(manifest, dict) and set(manifest) == {
        "schema", "roots", "nodes", "completeness", *CLAIMS}
        and manifest["schema"] == SCHEMA
        and all(type(manifest[key]) is type(value) and manifest[key] == value
                for key, value in CLAIMS.items()), "invalid manifest claims")
    roots, nodes = manifest["roots"], manifest["nodes"]
    require(isinstance(roots, list) and 0 < len(roots) <= MAX_NODES
            and all(is_digest(d) for d in roots) and roots == sorted(set(roots)), "invalid roots")
    require(isinstance(nodes, dict) and 0 < len(nodes) <= MAX_NODES
            and all(is_digest(d) for d in nodes), "invalid nodes")

    def resolve(key):
        require(key in nodes, "unreported reference")
        row = nodes[key]
        require(isinstance(row, dict) and set(row) == {
            "state", "adapter", "reason", "bytes", "references"}, "invalid node")
        state = row["state"]
        if state == "INCLUDED":
            require(isinstance(row["adapter"], str) and row["adapter"] in ADAPTERS,
                    "unsupported adapter")
            data = safe_read(directory, "data/" + key, MAX_OBJECT)
            require(contract.sha256(data) == key, "payload digest mismatch")
            require(type(row["bytes"]) is int and row == node("INCLUDED", row["adapter"], data=data),
                    "payload references/size mismatch")
            return row, data
        expected = (node("EXCLUDED", reason=row["reason"]) if state == "EXCLUDED"
                    and isinstance(row["reason"], str) and row["reason"] in REASONS else
                    node("MISSING", adapter=row["adapter"], reason="SOURCE_NOT_FOUND")
                    if state == "MISSING" and isinstance(row["adapter"], str)
                    and row["adapter"] in ADAPTERS else
                    node("UNRESOLVED", reason="NOT_IN_CATALOG") if state == "UNRESOLVED" else None)
        require(expected is not None and row == expected, "invalid unavailable node")
        return row, None

    visited, payloads = walk(roots, resolve)
    require(set(visited) == set(nodes), "unreachable evidence in manifest")
    require(manifest["completeness"] == summary(nodes), "false completeness claim")
    # Fixed layout, no path-bearing manifest entries or implicit extra evidence.
    require(directory_entries(directory, 2) == {"manifest.json", "data"}, "unexpected bundle entry")
    require(not (directory / "data").is_symlink() and (directory / "data").is_dir(), "unsafe data directory")
    require(directory_entries(directory / "data", MAX_NODES) == set(payloads), "payload inventory mismatch")
    return {"schema": "golem.evidence-export-verification.v1", "integrity": "MATCH",
            "completeness": manifest["completeness"], "manifest_sha256": digest,
            "manifest_pin": "MATCH" if expected_manifest else "NOT_PROVIDED",
            "objects": len(payloads), "unavailable": len(nodes) - len(payloads), **CLAIMS}


def directory_entries(directory, limit):
    names = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            names.add(entry.name)
            require(len(names) <= limit, "unexpected bundle entry limit")
    return names


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("export")
    create.add_argument("catalog", type=Path)
    create.add_argument("output", type=Path)
    create.add_argument("--expect-catalog")
    check = commands.add_parser("verify")
    check.add_argument("directory", type=Path)
    check.add_argument("--expect-manifest")
    prepare = commands.add_parser("catalog-observation")
    prepare.add_argument("bundle", type=Path)
    prepare.add_argument("destination", type=Path)
    prepare.add_argument("--expect-record", required=True)
    prepare.add_argument("--approve-private-raw", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog-observation":
            result = observation_catalog(args.bundle, args.destination, args.expect_record,
                                         args.approve_private_raw)
        else:
            result = export(args.catalog, args.output, args.expect_catalog) if args.command == "export" else verify(
                args.directory, args.expect_manifest)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("completeness", "COMPLETE_DECLARED_SCOPE") == "COMPLETE_DECLARED_SCOPE" else 2
    except (ValueError, OSError) as error:
        # Paths, exception messages and raw locators may contain credentials.
        diagnostic = str(error) if isinstance(error, ValueError) and str(error).startswith("EVIDENCE_EXPORT:") else None
        print(json.dumps({"code": "EVIDENCE_EXPORT_FAILED", "diagnostic": diagnostic,
                          "error_type": type(error).__name__, "errno": getattr(error, "errno", None),
                          "recovery": "CHECK_CATALOG_HASHES_POLICY_AND_PRIVATE_PATHS"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
