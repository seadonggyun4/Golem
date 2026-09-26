import unittest
from classify_failures import classify, BY_TEST


class ClassificationTests(unittest.TestCase):
    def test_all_reported_failures_retained(self):
        self.assertEqual(len(BY_TEST), 50)
        xml = "<testsuite>" + "".join(f'<testcase name="{name}"><failure/></testcase>'
                                      for name in BY_TEST) + "</testsuite>"
        report = classify({"schema": "golem.environment.v1", "status": "UNSUPPORTED_ENVIRONMENT"}, xml)
        self.assertEqual(len(report["failures"]), 50)
        self.assertFalse(report["causality_proven"])
        self.assertTrue(all(f["cause"] == "UNDETERMINED" for f in report["failures"]))

    def test_skip_unknown_and_duplicates(self):
        env = {"schema": "golem.environment.v1", "status": "PASS"}
        result = classify(env, '<testsuite><testcase name="new"><error/></testcase><testcase name="s"><skipped/></testcase></testsuite>')
        self.assertEqual(result["status"], "REQUIRES_REVIEW")
        self.assertEqual(result["failures"][0]["group"], "unclassified")
        self.assertEqual(result["skipped"], ["s"])
        for xml in ('<testsuite/>', '<testsuite><testcase name="a"/><testcase name="a"/></testsuite>',
                    '<testsuite failures="1"><testcase name="a"/></testsuite>'):
            with self.assertRaises(ValueError):
                classify(env, xml)


if __name__ == "__main__":
    unittest.main()
