"""P1 structural fixtures only; neither an issuer nor an acceptance oracle."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def cases():
    original = json.loads((ROOT / "tests/c/fixtures/intent/source-v1.json").read_bytes())
    yield "synthetic", original, True
    for work in (None, "_existing-id-style"):
        yield "work-" + str(work), {**original, "work_id": work}, True
    yield "paired-unicode-assertion", {**original, "created_by_assertion": "capture-\U0001f600"}, True
    for origin in ("TRUSTED_USER_INPUT", "USER_DESIGNATED_DOCUMENT", "TOOL_OBSERVATION", "EXTERNAL_REFERENCE"):
        value = copy.deepcopy(original)
        value["body"]["origin"] = origin
        yield "unverified-origin-" + origin, value, True
    for path in ((), ("body",), ("body", "designation"), ("body", "designation", "ranges", 0)):
        target = original
        for key in path:
            target = target[key]
        for key in target:
            value = copy.deepcopy(original)
            modified = value
            for part in path:
                modified = modified[part]
            del modified[key]
            yield "missing-" + repr(path) + key, value, False
        value = copy.deepcopy(original)
        modified = value
        for part in path:
            modified = modified[part]
        modified["approve"] = True
        yield "unknown-" + repr(path), value, False
    for field in ("baseline_digest", "issuer", "approved", "signature", "authority_root"):
        yield "root-" + field, {**original, field: "forged"}, False
    for path, values in (
        (("schema",), (None, "golem.intent.source.v2", True)),
        (("project_id",), (None, "", "../other", "a" * 65, "a\0b", "\ud800", "a\n", "a\r")),
        (("work_id",), (False, "a/b", 1)),
        (("created_by_assertion",), (None, "", True, {"approved": True}, "\ud800", "\udfff")),
        (("body", "capture_ref"), ("\ud800",)),
        (("body",), (None, False, [], "not-an-object")),
        (("body", "body_cas"), ("A" * 64, "b" * 63, "b" * 65, 5, "a" * 63 + "\n")),
        (("body", "byte_length"), (None, True, -1, 16777217)),
        (("body", "execution_authority"), (True, 0, None, "false")),
        (("body", "media_type"), ("application/pdf", "image/png", "text/html", None)),
        (("body", "encoding"), ("utf-8", "UTF-16", None)),
        (("body", "origin"), ("USER_APPROVED", None, 0)),
        (("body", "designation", "ranges"), ([], {}, None)),
        (("body", "designation"), (None, False, [], "not-an-object")),
        (("body", "designation", "ranges", 0), (None, False, [], "not-a-range")),
        (("body", "designation", "ranges", 0, "start"), (True, -1, 16777217)),
        (("body", "designation", "ranges", 0, "end"), (True, -1, 16777217)),
        (("body", "designation", "decision_ref"), (None, "model-approved", "B" * 64)),
    ):
        for bad in values:
            value = copy.deepcopy(original)
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = bad
            yield repr(path) + repr(bad), value, False


def native(helper, data, digest=False):
    argv = [str(helper)] + (["--digest"] if digest else [])
    result = subprocess.run(argv, input=data, capture_output=True, timeout=15, check=True)
    status, _, diagnostic = result.stdout.decode().strip().partition(" ")
    return int(status), diagnostic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path)
    parser.add_argument("--schema", action="store_true")
    args = parser.parse_args()
    if not args.native and not args.schema:
        parser.error("select --native and/or --schema")
    validator = None
    if args.schema:
        from jsonschema import Draft202012Validator
        schema = json.loads((ROOT / "samples/intent/source.schema.json").read_bytes())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
    checked = 0
    for label, value, expected in cases():
        if validator:
            assert validator.is_valid(value) == expected, label
        if args.native:
            data = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()
            assert (native(args.native, data)[0] == 0) == expected, label
        checked += 1
    representation_cases = domain_vectors = 0
    if args.native:
        original = next(cases())[1]
        serialized = json.dumps(original, separators=(",", ":"))
        # JSON Schema's mathematical integer type permits 3.0; native's strict
        # wire grammar deliberately requires an integer token, not a float.
        wires = [serialized.replace('"byte_length":3', '"byte_length":3.0'),
                 serialized.replace('"byte_length":3', '"byte_length":3,"byte_length":3'),
                 serialized.replace('"byte_length":3', '"byte_length":3,"\\u0062yte_length":3'),
                 serialized + " {}", serialized.replace('"fixture"', '"bad\\u0000key"')]
        for wire in wires:
            assert native(args.native, wire.encode())[0] != 0
            representation_cases += 1
        # Valid shape alone does not verify raw content or byte ranges.
        for bad in ({"body_cas": "b" * 64}, {"byte_length": 2},
                    {"designation": {**original["body"]["designation"], "ranges": [{"start": 2, "end": 1}]}}):
            value = copy.deepcopy(original)
            value["body"].update(bad)
            if validator:
                assert validator.is_valid(value)
            assert native(args.native, json.dumps(value).encode())[0] != 0
            representation_cases += 1
        domain = b"golem.intent.source.v1\0"
        minimum = b'{"schema":"golem.intent.source.v1"}'
        unicode_value = copy.deepcopy(original)
        unicode_value["created_by_assertion"] = "capture-\U0001f600-\ud55c"
        vectors = [(ROOT / "tests/c/fixtures/intent/source-v1.json").read_bytes(),
                   serialized.encode(), json.dumps(original, sort_keys=True).encode(), minimum,
                   json.dumps(unicode_value, ensure_ascii=False).encode(),
                   json.dumps(unicode_value, ensure_ascii=True).encode()]
        vectors += [minimum + b" " * padding for padding in (1, 7, 8, 255, 262144 - len(minimum))]
        for wire in vectors:
            status, actual = native(args.native, wire, digest=True)
            expected = hashlib.sha256(domain + len(wire).to_bytes(8, "little") + wire).hexdigest()
            assert status == 0 and actual == expected
            assert expected != hashlib.sha256(wire).hexdigest()
            assert expected != hashlib.sha256(domain[:-1] + len(wire).to_bytes(8, "little") + wire).hexdigest()
            assert expected != hashlib.sha256(domain + len(wire).to_bytes(8, "big") + wire).hexdigest()
            domain_vectors += 1
        for name in ("golem.intent.baseline.v1", "golem.intent.object-preparation.v1"):
            for value in ({"schema": name}, {"schema": name, "unverified": "\ud55c\U0001f600"}):
                for ascii_only in (True, False):
                    wire = json.dumps(value, ensure_ascii=ascii_only).encode()
                    status, actual = native(args.native, wire, digest=True)
                    expected = hashlib.sha256(name.encode("ascii") + b"\0" + len(wire).to_bytes(8, "little") + wire).hexdigest()
                    assert status == 0 and actual == expected
                    assert expected != hashlib.sha256(wire).hexdigest()
                    domain_vectors += 1
        for wire in (b'{"schema":"golem.intent.baseline.v2"}',
                     b'{"schema":"golem.intent.object-publication.v1"}', minimum + b" " * 262144):
            assert native(args.native, wire, digest=True)[0] != 0
    print(json.dumps({"scope": "P1_STRUCTURAL_PREPARATION_ONLY", "shape_cases": checked,
                      "native_representation_and_content_cases": representation_cases,
                      "independent_domain_vectors": domain_vectors,
                      "independent_json_schema": bool(validator),
                      "authority_or_semantic_acceptance": False}))


if __name__ == "__main__":
    main()
