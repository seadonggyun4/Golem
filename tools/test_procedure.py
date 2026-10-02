"""Exhaustive finite routing policy, separate from native workflow gates."""
import copy
import itertools
from pathlib import Path
import tempfile
import unittest

import agent_io as io


def intent(activities=None):
    return {"schema": "golem.procedure-intent.v1", "activities": activities or ["docs"],
            "scope": {"document_id": "scope", "revision": 1, "digest": "a" * 64}}


class Procedure(unittest.TestCase):
    def test_every_nonempty_combination_and_order(self):
        for count in range(1, 4):
            for activities in itertools.permutations(io.PROCEDURE_ORDER, count):
                with self.subTest(activities=activities):
                    route = io.select_procedure(intent(list(activities)))
                    expected = max(activities, key=io.PROCEDURE_ORDER.index)
                    self.assertEqual(route["task"], expected)
                    self.assertEqual(route["mode"], "documents" if expected == "docs" else "development")
                    self.assertFalse(route["execution_authorized"])
                    self.assertFalse(route["acceptance_verified"])
                    self.assertIn("completion", route["required_checks"])
                    self.assertIn("review", route["required_checks"])
                    if expected == "deploy":
                        self.assertIn("scoped_host_approval", route["required_checks"])

    def test_invalid_intents_fail_closed(self):
        invalid = [None, {}, {**intent(), "schema": "v2"}, {**intent(), "override": "docs"}]
        invalid += [{**intent(), "activities": a} for a in ([], ["unknown"], ["docs", "docs"], [True], "docs", [{}])]
        for key, value in (("revision", True), ("revision", 0), ("revision", 4097),
                           ("digest", "x" * 64), ("document_id", "../scope")):
            item = intent()
            item["scope"][key] = value
            invalid.append(item)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(io.ObservationError):
                io.select_procedure(value)

    def test_no_mutation_or_shared_result_alias(self):
        original = intent(["deploy", "docs"])
        before = copy.deepcopy(original)
        first = io.select_procedure(original)
        first["scope"]["digest"] = "b" * 64
        first["required_checks"].clear()
        self.assertEqual(original, before)
        self.assertTrue(io.select_procedure(original)["required_checks"])

    def test_plan_only_executes_native_query_and_pins_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = intent(["docs", "deploy"])
            plan = io.procedure_plan(Path("/bin/golem"), Path("/work with spaces"), request, root)
            io.validate_plan(plan)
            self.assertEqual(len(plan["commands"]), 1)
            self.assertEqual(plan["commands"][0]["argv"], ["/bin/golem", "--output-mode", "full",
                             "workflow", "select", "/work with spaces", "scope", "1", "development"])
            self.assertEqual(io.read_json(root / "procedure-intent.json"), request)
            self.assertEqual(io.read_json(root / "procedure-route.json"), io.select_procedure(request))


if __name__ == "__main__":
    unittest.main()
