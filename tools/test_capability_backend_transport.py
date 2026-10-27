import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from capability_files import SourceFile
from capability_sample_registry import SOURCES
from capability_backend import inspect_backend, PINS as BACKEND_PINS
from capability_transport import inspect_transport, PINS as TRANSPORT_PINS


class StaticAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.files=tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in SOURCES)

    def mutate(self,path,before,after,pins):
        changed=[]; pins=dict(pins)
        for f in self.files:
            if f.path==path:
                self.assertIn(before,f.data)
                raw=f.data.replace(before,after)
                f=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest());pins[path]=f.sha256
            changed.append(f)
        return tuple(changed),pins

    def test_backend_four_routes_only(self):
        result=inspect_backend(self.files)
        self.assertFalse(result.blockers)
        self.assertEqual(dict(result.operation_routes)['history'],('work','history'))
        self.assertEqual(dict(result.operation_routes)['status'],('session','call'))
        self.assertFalse(result.native_read_only_verified)
        self.assertFalse(result.authority_verified)

    def test_wrong_backend_native_route_or_argument_blocks_after_repin(self):
        for before,after in ((b'command = ["work", operation]',b'command = ["approval", operation]'),
                             (b'"--output-mode", "full"',b'"--output-mode", "compact"'),
                             (b'validate("read", request)',b'validate("project", request)'),
                             (b'*command, work["path"]',b'*command, project["root"]'),
                             (b'capture(argv, destination',b'capture(other, destination')):
            files,pins=self.mutate('tools/integration_backend.py',before,after,BACKEND_PINS)
            self.assertTrue(inspect_backend(files,pins).blockers)

    def test_backend_subject_escape_blocks(self):
        files,pins=self.mutate('tools/integration_backend.py',b'    argv = [project',b'    command.append(operation)\n    argv = [project',BACKEND_PINS)
        self.assertTrue(inspect_backend(files,pins).blockers)

    def test_backend_domain_or_reject_guard_change_blocks(self):
        for before,after in ((b'enum("status", "next", "record", "history")',b'enum("status", "next", "record", "history", "approve")'),
                             (b'if not condition:\n        raise IntegrationError(code)',b'if not condition:\n        return')):
            files,pins=self.mutate('tools/integration_contract.py',before,after,BACKEND_PINS)
            self.assertTrue(inspect_backend(files,pins).blockers)

    def test_transport_closed_declared_names_are_not_client_delivery(self):
        result=inspect_transport(self.files)
        self.assertFalse(result.blockers)
        self.assertEqual(len(result.declared_tool_names),80)
        self.assertIn('golem_workflow_read',result.declared_tool_names)
        self.assertIn('golem_action_prepare',result.declared_tool_names)
        self.assertFalse(result.client_delivery_verified)
        self.assertFalse(result.runtime_receiver_verified)

    def test_transport_prefix_slice_dynamic_receiver_or_binding_blocks(self):
        for before,after in ((b'params.name[6:]',b'params.name[5:]'),
                             (b'"golem_" + name',b'"other_" + name'),
                             (b'run_sync(service.call,',b'run_sync(other.call,'),
                             (b'on_call_tool=call_tool',b'on_call_tool=list_tools'),
                             (b'run(mutations.Service(policy, resources, helpers, parallel_hosts))',b'run(other.Service(policy, resources, helpers, parallel_hosts))')):
            files,pins=self.mutate('tools/integration_mutation_mcp.py',before,after,TRANSPORT_PINS)
            self.assertTrue(inspect_transport(files,pins).blockers)

    def test_transport_alias_and_attribute_assignment_block(self):
        for inserted in (b'            alias = service\n',b'            params.name = "golem_work_inspect"\n'):
            files,pins=self.mutate('tools/integration_mutation_mcp.py',b'            c.require(params.name.startswith',inserted+b'            c.require(params.name.startswith',TRANSPORT_PINS)
            self.assertTrue(inspect_transport(files,pins).blockers)

    def test_missing_or_drifted_inputs_do_not_fall_back(self):
        for inspect in (inspect_backend,inspect_transport):
            self.assertTrue(inspect(()).blockers)

    def test_tool_metadata_wait_cannot_retry_actions_or_other_errors_after_repin(self):
        for before,after in ((b'run_sync(service.tools)',b'run_sync(service.call)'),
                             (b"error.code != 'REGISTRY_BUSY'",b"error.code != 'COMMIT_UNKNOWN'"),
                             (b'time.monotonic() + 5',b'time.monotonic() + 500'),
                             (b'except c.IntegrationError as error:',b'except Exception as error:')):
            files,pins=self.mutate('tools/integration_mcp.py',before,after,TRANSPORT_PINS)
            self.assertTrue(inspect_transport(files,pins).blockers)
