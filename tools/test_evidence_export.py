"""Independent verification, bounded closure and explicit privacy failures."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import agent_io
import evidence_contract as ec
import evidence_export as ex


class Export(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        self.output = self.base / "export"
        self.catalog = {"schema": ex.CATALOG, "roots": [], "objects": {}}

    def add(self, data, adapter="opaque.v1"):
        digest = ec.sha256(data)
        (self.source / digest).write_bytes(data)
        self.catalog["objects"][digest] = {"disposition": "INCLUDE", "adapter": adapter,
                                         "path": digest, "review": "PRIVATE_EXPORT_APPROVED"}
        return digest

    def links(self, *refs):
        return self.add(ex.encoded({"schema": ex.LINKS, "references": list(refs)}), "links.v1")

    def run_export(self, *roots):
        self.catalog["roots"] = list(roots)
        path = self.source / "catalog.json"
        path.write_bytes(ex.encoded(self.catalog))
        return ex.export(path, self.output)

    def rewrite(self, change):
        path = self.output / "manifest.json"
        manifest = json.loads(path.read_bytes())
        change(manifest)
        path.write_bytes(ex.encoded(manifest))

    def test_transitive_dedup_and_no_unrelated_copy(self):
        leaf = self.add(b"required bytes")
        unused = self.add(b"not in selected scope")
        child = self.links({"sha256": leaf})
        root = self.links({"sha256": child}, {"sha256": leaf}, {"sha256": leaf})
        result = self.run_export(root)
        self.assertEqual(result["objects"], 3)
        self.assertEqual(result["completeness"], "COMPLETE_DECLARED_SCOPE")
        self.assertFalse((self.output / "data" / unused).exists())
        self.assertEqual((self.output / "data" / leaf).read_bytes(), b"required bytes")

    def test_verify_after_original_removed_and_bundle_moved(self):
        leaf = self.add(b"standalone")
        root = self.links({"sha256": leaf})
        result = self.run_export(root)
        shutil.rmtree(self.source)
        moved = self.base / "moved"
        self.output.rename(moved)
        self.assertEqual(ex.verify(moved, result["manifest_sha256"])["integrity"], "MATCH")

    def test_excluded_secret_is_not_opened_or_copied(self):
        secret = ec.sha256(b"TOKEN=secret")
        (self.source / secret).symlink_to("/not/allowed")
        self.catalog["objects"][secret] = {"disposition": "EXCLUDE", "reason": "SECRET"}
        root = self.links({"sha256": secret})
        result = self.run_export(root)
        self.assertEqual(result["completeness"], "INCOMPLETE")
        self.assertNotIn(b"TOKEN", (self.output / "manifest.json").read_bytes())
        self.assertFalse((self.output / "data" / secret).exists())

    def test_missing_unresolved_and_external_are_separate(self):
        missing = self.add(b"missing")
        (self.source / missing).unlink()
        unknown = "a" * 64
        root = self.links({"sha256": missing}, {"sha256": unknown},
                          {"external": "https://example.invalid/?credential=secret"})
        result = self.run_export(root)
        self.assertEqual(result["unavailable"], 2)
        manifest = json.loads((self.output / "manifest.json").read_bytes())
        self.assertEqual(manifest["nodes"][missing]["state"], "MISSING")
        self.assertEqual(manifest["nodes"][unknown]["state"], "UNRESOLVED")
        self.assertNotIn("credential", json.dumps(manifest))
        self.assertFalse(result["remote_latest_verified"])

    def test_missing_root_is_not_a_complete_empty_bundle(self):
        result = self.run_export("a" * 64)
        self.assertEqual(result["completeness"], "INCOMPLETE")
        self.assertEqual(result["objects"], 0)

    def test_raw_export_requires_per_object_approval(self):
        root = self.add(b"private")
        del self.catalog["objects"][root]["review"]
        with self.assertRaisesRegex(ValueError, "approval"):
            self.run_export(root)
        self.assertFalse(self.output.exists())

    def test_hash_corruption_aborts_before_publication(self):
        root = self.add(b"original")
        (self.source / root).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.run_export(root)
        self.assertFalse(self.output.exists())

    def test_source_symlink_rejected(self):
        root = self.add(b"bytes")
        (self.source / root).unlink()
        (self.source / root).symlink_to(self.base / "outside")
        with self.assertRaises(OSError):
            self.run_export(root)

    def test_parent_symlink_rejected(self):
        root = self.add(b"bytes")
        (self.source / "alias").symlink_to(self.source, target_is_directory=True)
        self.catalog["objects"][root]["path"] = "alias/" + root
        with self.assertRaises(OSError):
            self.run_export(root)

    def test_traversal_absolute_and_noncanonical_paths_rejected(self):
        for name in ("../outside", "/etc/passwd", "./inside", "a//b", "a\\b", "a\x00b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ex.safe_read(self.source, name, 1024)

    def test_fifo_rejected_without_blocking(self):
        os.mkfifo(self.source / "fifo")
        with self.assertRaisesRegex(ValueError, "regular"):
            ex.safe_read(self.source, "fifo", 1024)

    def test_unknown_adapter_rejected(self):
        root = self.add(b"bytes", "future.v2")
        with self.assertRaises(ValueError):
            self.run_export(root)

    def test_tampered_payload_or_pin_rejected(self):
        root = self.add(b"bytes")
        self.run_export(root)
        with self.assertRaisesRegex(ValueError, "pin mismatch"):
            ex.verify(self.output, "a" * 64)
        (self.output / "data" / root).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            ex.verify(self.output)

    def test_dropped_edge_cannot_be_hidden_by_rehashed_manifest(self):
        leaf = self.add(b"bytes")
        root = self.links({"sha256": leaf})
        self.run_export(root)
        self.rewrite(lambda m: m["nodes"][root].update(references=[]))
        with self.assertRaisesRegex(ValueError, "references/size"):
            ex.verify(self.output)

    def test_unreported_reference_rejected(self):
        leaf = self.add(b"bytes")
        root = self.links({"sha256": leaf})
        self.run_export(root)
        self.rewrite(lambda m: m["nodes"].pop(leaf))
        with self.assertRaisesRegex(ValueError, "unreported"):
            ex.verify(self.output)

    def test_unreachable_node_rejected(self):
        root = self.add(b"bytes")
        self.run_export(root)
        self.rewrite(lambda m: m["nodes"].update({"a" * 64: ex.node("UNRESOLVED", reason="NOT_IN_CATALOG")}))
        with self.assertRaisesRegex(ValueError, "unreachable"):
            ex.verify(self.output)

    def test_false_completeness_rejected(self):
        self.run_export("a" * 64)
        self.rewrite(lambda m: m.update(completeness="COMPLETE_DECLARED_SCOPE"))
        with self.assertRaisesRegex(ValueError, "false completeness"):
            ex.verify(self.output)

    def test_extra_payload_and_extra_directory_rejected(self):
        root = self.add(b"bytes")
        self.run_export(root)
        (self.output / "data" / "extra").mkdir()
        with self.assertRaisesRegex(ValueError, "inventory"):
            ex.verify(self.output)
        (self.output / "data" / "extra").rmdir()
        (self.output / "extra").mkdir()
        with self.assertRaisesRegex(ValueError, "unexpected"):
            ex.verify(self.output)

    def test_missing_and_symlink_payload_rejected(self):
        root = self.add(b"bytes")
        self.run_export(root)
        path = self.output / "data" / root
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            ex.verify(self.output)
        path.symlink_to(self.source / root)
        with self.assertRaises(OSError):
            ex.verify(self.output)

    def test_no_overwrite_and_private_modes(self):
        root = self.add(b"bytes")
        self.run_export(root)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.output / "data" / root).stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            self.run_export(root)

    def test_interruption_leaves_no_final_manifest(self):
        root = self.add(b"bytes")
        with patch.object(ex, "save", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                self.run_export(root)
        self.assertFalse((self.output / "manifest.json").exists())
        with self.assertRaises(FileNotFoundError):
            ex.verify(self.output)

    def test_limits_fail_without_silently_truncating(self):
        leaf = self.add(b"bytes")
        root = self.links({"sha256": leaf})
        for name, limit in (("MAX_NODES", 1), ("MAX_DEPTH", 0), ("MAX_TOTAL", 1), ("MAX_OBJECT", 1), ("MAX_EDGES", 0)):
            with self.subTest(name=name), patch.object(ex, name, limit), self.assertRaises(ValueError):
                self.run_export(root)
        self.assertFalse(self.output.exists())

    def test_graph_cycle_terminates_at_resolver_layer(self):
        def resolve(d):
            other = "b" if d == "a" else "a"
            row = ex.node("INCLUDED", "opaque.v1", data=b"bytes")
            row["references"] = [{"sha256": other}]
            return row, b"bytes"
        nodes, _ = ex.walk(["a"], resolve)
        self.assertEqual(set(nodes), {"a", "b"})

    def test_duplicate_json_keys_and_nan_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff'):
            with self.assertRaises(ValueError):
                ex.strict_json(raw)

    def test_catalog_pin_rejects_modified_approval(self):
        root = self.add(b"bytes")
        self.catalog["roots"] = [root]
        path = self.source / "catalog.json"
        path.write_bytes(ex.encoded(self.catalog))
        with self.assertRaisesRegex(ValueError, "catalog pin"):
            ex.export(path, self.output, "a" * 64)
        self.assertFalse(self.output.exists())

    def test_known_json_adapter_does_not_fall_back_to_opaque(self):
        root = self.add(b"not JSON", "links.v1")
        with self.assertRaises(ValueError):
            self.run_export(root)
        self.assertFalse(self.output.exists())

    def test_manifest_claim_types_cannot_upgrade_authority(self):
        root = self.add(b"bytes")
        self.run_export(root)
        self.rewrite(lambda m: m.update(acceptance_authorized=0))
        with self.assertRaisesRegex(ValueError, "claims"):
            ex.verify(self.output)

    def test_observation_reference_paths_cannot_escape(self):
        raw = ex.encoded({"schema": "golem.agent-observation-manifest.v1",
                          "files": {"record.json": "a" * 64, "../secret": "b" * 64}})
        with self.assertRaisesRegex(ValueError, "unsafe source path"):
            ex.references("observation-manifest.v1", raw)

    def test_output_inside_staging_rejected(self):
        self.output = self.source / "export"
        with self.assertRaisesRegex(ValueError, "outside"):
            self.run_export(self.add(b"bytes"))

    def test_output_parent_alias_cannot_bypass_staging_boundary(self):
        (self.base / "other").mkdir()
        self.output = self.base / "other" / ".." / "source" / "export"
        with self.assertRaisesRegex(ValueError, "unsafe output"):
            self.run_export(self.add(b"bytes"))

    def test_real_cli_export_and_standalone_verify(self):
        root = self.add(b"raw CLI evidence")
        self.catalog["roots"] = [root]
        path = self.source / "catalog.json"
        path.write_bytes(ex.encoded(self.catalog))
        result = subprocess.run([sys.executable, ex.__file__, "export", str(path), str(self.output),
                                 "--expect-catalog", ec.sha256(path.read_bytes())],
                                check=True, capture_output=True, timeout=10)
        report = json.loads(result.stdout)
        shutil.rmtree(self.source)
        verified = subprocess.run([sys.executable, ex.__file__, "verify", str(self.output),
                                   "--expect-manifest", report["manifest_sha256"]],
                                  check=True, capture_output=True, timeout=10)
        self.assertEqual(json.loads(verified.stdout)["integrity"], "MATCH")

    def test_manifest_size_limit_prevents_publication(self):
        with patch.object(ex, "MAX_METADATA", 1024), patch.object(ex, "encoded", return_value=b"x" * 1025):
            # Create the catalog normally; patch only the manifest serialization.
            root = self.add(b"bytes")
            self.catalog["roots"] = [root]
            path = self.source / "catalog.json"
            path.write_bytes(json.dumps(self.catalog).encode())
            with self.assertRaisesRegex(ValueError, "manifest size"):
                ex.export(path, self.output)
        self.assertFalse(self.output.exists())

    def test_research_adapter_ignores_prose_hashes_but_expands_typed_refs(self):
        leaf = self.add(b"bytes")
        root = self.add(ex.encoded({"schema_version": 1, "case_digest": leaf,
                                   "observations": [{"evidence_digest": leaf}],
                                   "hypothesis": "a" * 64}), "research-digests.v1")
        result = self.run_export(root)
        self.assertEqual(result["objects"], 2)
        self.assertEqual(result["unavailable"], 0)

    def test_verification_contract_transitive_subject(self):
        leaf = self.add(b"bytes")
        record = ec.assessment(leaf, "ARTIFACT")
        root = self.add(ex.encoded(record), "verification.v1")
        result = self.run_export(root)
        self.assertEqual(result["objects"], 2)
        self.assertFalse(result["acceptance_authorized"])
        self.assertEqual(result["content_truth"], "NOT_ESTABLISHED")

    def test_real_observation_survives_source_removal(self):
        bundle = self.source / "observation"
        bundle.mkdir()
        repository = self.base / "repository"
        repository.mkdir()
        subprocess.run(["git", "init", "-q", str(repository)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repository), "-c", "user.name=Test", "-c",
                        "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture"],
                       check=True, capture_output=True)
        plan = {"schema": agent_io.PLAN_SCHEMA, "task": "code",
                "commands": [{"id": "check", "argv": [sys.executable, "-c", "print('evidence')"], "timeout": 5}]}
        observation = agent_io.run(plan, repository, bundle, None)
        self.assertEqual(observation["steps"][0]["status"], "EXIT_OK")
        pin = ec.sha256((bundle / "record.json").read_bytes())
        catalog_path = self.source / "catalog.json"
        ex.observation_catalog(bundle, catalog_path, pin, approved=True)
        result = ex.export(catalog_path, self.output)
        original_manifest = (bundle / "manifest.json").read_bytes()
        shutil.rmtree(self.source)
        shutil.rmtree(repository)
        self.assertEqual(ex.verify(self.output, result["manifest_sha256"])["integrity"], "MATCH")
        self.assertEqual((self.output / "data" / ec.sha256(original_manifest)).read_bytes(), original_manifest)

    def test_observation_catalog_requires_pin_and_explicit_approval(self):
        for pin, approved in ((None, True), ("a" * 64, False)):
            with self.assertRaisesRegex(ValueError, "approval"):
                ex.observation_catalog(self.source / "missing", self.source / "catalog", pin, approved)

    def test_cli_exit_distinguishes_incomplete_from_integrity_failure(self):
        self.run_export("a" * 64)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ex.main(["verify", str(self.output)]), 2)
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(ex.main(["verify", str(self.output), "--expect-manifest", "b" * 64]), 1)
        self.assertEqual(json.loads(stderr.getvalue())["code"], "EVIDENCE_EXPORT_FAILED")


if __name__ == "__main__":
    unittest.main()
