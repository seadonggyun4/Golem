"""Runtime identity integration in disposable stores; not live-provider evidence."""
import copy
import hashlib
import json
import unittest
import session_integration as fixture


class Profiles(fixture.Session):
    def setup_work(self, *args, **kwargs):
        super().setup_work(*args, **kwargs)
        if not getattr(self, "unenrolled", False):
            self.register_profile()

    def profile(self):
        return json.loads((fixture.fixture.SOURCE / "samples/runtime-profile.json").read_text())

    def register_profile(self, profile=None, key="runtime-1", ok=True):
        return self.cli("profile", "register", self.work,
                        self.write("profile.json", profile or self.profile()), key, ok=ok)

    def object_path(self, digest):
        return self.work / "objects/sha256" / digest[:2] / digest[2:]

    def cas(self, digest):
        return json.loads(self.object_path(digest).read_bytes())

    def test_refresh_pins_attempt_and_resume(self):
        self.setup_session()
        self.claim()
        binding_digest = self.active["runtime_binding"]
        binding = self.cas(binding_digest)
        self.assertEqual(binding["runtime_generation"], 1)
        self.assertEqual(binding["claim_epoch"], self.token["epoch"])
        self.assertIsNone(binding["work_run"])
        profile = self.profile()
        profile["model_reported"] = "next-model"
        self.register_profile(profile, "runtime-2")
        self.assertEqual(self.cli("profile", "current", self.work), profile)
        self.assertEqual(self.request("status")["state"]["active"]["runtime_binding"], binding_digest)
        self.begin()
        self.now += 10000
        resumed = self.request("resume", session_id="new-agent", ttl_ms=10000)
        active = resumed["state"]["active"]
        self.assertEqual(active["runtime_binding"], binding_digest)
        self.assertNotEqual(active["epoch"], binding["claim_epoch"])
        self.token = {k: active[k] for k in ("epoch", "attempt_id", "session_id")}
        evidence = self.cli("evidence", "put", self.work, self.write("recovery.txt", "No effects observed."))["digest"]
        self.request("reconcile", token=self.token, input_digest=active["manifest_digest"],
                     source_snapshot=self.source, resolution="NO_EFFECTS", output=None, evidence=[evidence])
        self.claim("new-agent")
        self.assertEqual(self.cas(self.active["runtime_binding"])["runtime_generation"], 2)

    def test_idempotency_reordering_and_conflict(self):
        self.setup_session()
        before = len(list((self.work / "events").glob("*.evt")))
        expected = self.register_profile()
        profile = dict(reversed(list(self.profile().items())))
        self.assertEqual(self.register_profile(profile), expected)
        self.assertEqual(len(list((self.work / "events").glob("*.evt"))), before)
        profile["config_digest"] = "a" * 64
        self.register_profile(profile, ok=False)
        self.assertEqual(self.cli("profile", "current", self.work), self.profile())

    def test_unknown_legacy_and_late_enrollment(self):
        self.unenrolled = True
        self.setup_session()
        self.assertEqual(self.cli("profile", "current", self.work)["runtime_identity"], "UNKNOWN")
        self.claim()
        self.assertNotIn("runtime_binding", self.active)
        self.register_profile(ok=False)
        self.now += 10000
        self.request("resume", session_id="new-agent", ttl_ms=10000)
        self.register_profile()
        self.claim("new-agent")
        self.assertIn("runtime_binding", self.active)
        self.begin()

    def test_local_availability_and_observation_are_not_descriptor_claims(self):
        self.setup_work()
        profile = self.profile()
        profile["restore_level"] = "LOCAL_ARTIFACTS_AVAILABLE"
        self.register_profile(profile, "missing", ok=False)
        evidence = self.cli("evidence", "put", self.work,
                            self.write("artifact.txt", "Synthetic locally available fixture."))["digest"]
        for key in ("engine_build_digest", "adapter_executable_digest", "adapter_descriptor_digest",
                    "config_digest", "policy_digest"):
            profile[key] = evidence
        profile["tools"] = [{"id": "test-tool", "digest": evidence}]
        profile.update(provider_observed="fixture-provider", model_observed="different-observation",
                       observation_digest="f" * 64)
        self.register_profile(profile, "missing-observation", ok=False)
        profile["observation_digest"] = evidence
        self.register_profile(profile, "available")
        current = self.cli("profile", "current", self.work)
        self.assertNotEqual(current["model_reported"], current["model_observed"])
        self.object_path(evidence).unlink()
        self.cli("profile", "current", self.work, ok=False)

    def test_v2_work_starts_with_profile_and_missing_cas_fails_closed(self):
        self.work = self.root / "initial-work"
        spec = json.loads((fixture.fixture.SOURCE / "samples/documents/work.json").read_text())
        spec.update(schema_version=2, runtime_profile=self.profile())
        self.cli("work", "start", self.work, self.write("initial.json", spec))
        self.assertEqual(self.cli("profile", "current", self.work), self.profile())
        self.assertEqual(len(list((self.work / "events").glob("*.evt"))), 1)
        digest = self.cli("profile", "validate", self.write("profile.json", self.profile()))["profile_digest"]
        self.object_path(digest).unlink()
        self.cli("profile", "current", self.work, ok=False)

    def test_v2_initial_profile_session_and_replay(self):
        original_cli = self.cli
        def initial_cli(*args, **kwargs):
            if args[:2] == ("work", "start"):
                spec = json.loads(args[3].read_text())
                spec.update(schema_version=2, runtime_profile=self.profile())
                args = (*args[:3], self.write("v2-spec.json", spec))
            return original_cli(*args, **kwargs)
        self.cli = initial_cli
        self.unenrolled = True
        self.setup_session()
        self.claim()
        self.assertEqual(self.cas(self.active["runtime_binding"])["runtime_generation"], 1)
        self.begin()
        self.output()
        self.submit()
        self.assertEqual(self.request("status")["runtime_identity"], "ENROLLED_NO_ACTIVE_BINDING")

    def test_explicit_binary_run_bridge_and_checkpoint(self):
        self.setup_session(actual=True)
        self.claim()
        self.begin()
        fixture_path = fixture.fixture.SOURCE / "tests/c/fixtures/journal/v1_default.hex"
        full = bytes.fromhex(fixture_path.read_text())
        frames, offset = [], 0
        for _ in range(2):
            length = 32 + int.from_bytes(full[offset + 12:offset + 16], "little")
            frames.append(full[offset:offset + length])
            offset += length
        journal = b"".join(frames)
        chain = bytes(32)
        for frame in frames:
            chain = hashlib.sha256(b"golem.journal.chain.v1" + chain + hashlib.sha256(frame).digest()).digest()
        path = self.root / "binary.journal"
        path.write_bytes(journal)
        args = ("profile", "link", self.work, self.active["runtime_binding"], path)
        self.cli(*args, "wrong-run", 2, len(journal), chain.hex(), ok=False)
        self.cli(*args, "run-golden", 2, len(journal), "f" * 64, ok=False)
        result = self.cli(*args, "run-golden", 2, len(journal), chain.hex())
        self.assertEqual(self.cli(*args, "run-golden", 2, len(journal), chain.hex()), result)
        receipt = self.cas(result["link_receipt"])
        self.assertEqual(receipt["run_id"], "run-golden")
        self.assertEqual(receipt["stage_sequence"], 1)
        self.assertEqual(receipt["binding_digest"], self.active["runtime_binding"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(self.request("status")["runtime_identity"], "BOUND")
        self.object_path(receipt["journal_digest"]).unlink()
        self.request("status", ok=False)

    def test_canonical_digest_independent_encoding(self):
        profile = self.profile()
        expected = hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(expected, "ef3a9d7485126bc9e4772b50689a4a45b0f38b564eaa13d27bdb70d5e48d4fc9")
        result = self.cli("profile", "validate", self.write("profile.json", profile))
        self.assertEqual(result["profile_digest"], expected)

    def test_secret_fields_versions_and_overflow(self):
        for field in ("api_key", "token", "environment", "authorization", "password"):
            profile = self.profile()
            profile[field] = "synthetic-never-secret"
            self.cli("profile", "validate", self.write("bad.json", profile), ok=False)
        for value in (-1, 0, 2**32, 2**64, 10**100, True, 1.5):
            profile = self.profile()
            profile["engine_abi"] = value
            self.cli("profile", "validate", self.write("bad.json", profile), ok=False)
        profile = self.profile()
        profile["schema_version"] = 2
        self.cli("profile", "validate", self.write("bad.json", profile), ok=False)
        profile["schema_version"] = 1
        profile["model_reported"] = "CaseSensitive/Model"
        first = self.cli("profile", "validate", self.write("good.json", profile))
        profile["model_reported"] = "casesensitive/model"
        self.assertNotEqual(first, self.cli("profile", "validate", self.write("good.json", profile)))

    def test_binding_semantic_corruption_even_with_rehashed_frames(self):
        self.setup_session()
        self.claim()
        path = self.work / "agent-events/00000002.evt"
        original_frame = path.read_bytes()
        event = self.cas(original_frame[48:].hex())
        binding = self.cas(self.active["runtime_binding"])
        mutations = [("work_id", "other-work"), ("claim_epoch", self.token["epoch"] + 1),
                     ("session_id", "different-agent"), ("profile_digest", "f" * 64),
                     ("input_manifest_digest", "f" * 64), ("runtime_generation", 99),
                     ("work_run", {"id": "invented"}), ("generation_digest", "f" * 64)]
        selection = copy.deepcopy(binding["selection"])
        selection["revision"] += 1
        mutations.append(("selection", selection))
        for field, value in mutations:
            with self.subTest(field=field):
                bad = copy.deepcopy(binding)
                bad[field] = value
                blob = json.dumps(bad).encode()
                digest = hashlib.sha256(blob).hexdigest()
                destination = self.object_path(digest)
                destination.parent.mkdir(exist_ok=True)
                destination.write_bytes(blob)
                changed = copy.deepcopy(event)
                changed["data"]["runtime_binding"] = digest
                blob = json.dumps(changed).encode()
                payload = hashlib.sha256(blob).hexdigest()
                destination = self.object_path(payload)
                destination.parent.mkdir(exist_ok=True)
                destination.write_bytes(blob)
                path.chmod(0o600)
                path.write_bytes(original_frame[:48] + bytes.fromhex(payload))
                self.request("status", ok=False)
                path.write_bytes(original_frame)
        self.begin()

    def test_denied_registration(self):
        self.work = self.root / "denied-work"
        spec = json.loads((fixture.fixture.SOURCE / "samples/documents/work.json").read_text())
        spec["permission"] = "DENY"
        self.cli("work", "start", self.work, self.write("denied.json", spec))
        self.register_profile(ok=False)
        self.assertEqual(self.cli("profile", "current", self.work)["runtime_identity"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
