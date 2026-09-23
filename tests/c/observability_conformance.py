"""Optional independent consumer test: requires opentelemetry-proto and prov.

Run with the same CLI/source/temp arguments as observability_integration.py.
These packages are development-only, not Golem runtime dependencies.
"""
import json
import unittest
from google.protobuf.json_format import Parse
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from prov.model import ProvDocument
from observability_integration import Observability


class Conformance(Observability):
    def test_independent_consumers(self):
        self.setup_private_case()
        for profile in ("MINIMAL", "LINKABLE"):
            message = Parse(json.dumps(self.mapping("otlp", profile)), ExportLogsServiceRequest(),
                            ignore_unknown_fields=False)
            self.assertEqual(len(message.resource_logs[0].scope_logs[0].log_records), 9)
            clone = ExportLogsServiceRequest.FromString(message.SerializeToString())
            self.assertEqual(clone, message)
            source = self.mapping("prov", profile)
            document = ProvDocument.deserialize(content=json.dumps(source), format="json")
            roundtrip = ProvDocument.deserialize(content=document.serialize(format="json"), format="json")
            self.assertEqual(document, roundtrip)
            self.assertEqual(len(document.get_records()), sum(len(source[key]) for key in
                ("entity", "activity", "used", "wasGeneratedBy", "wasDerivedFrom")))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite([Conformance("test_independent_consumers")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
