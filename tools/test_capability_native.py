import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from capability_files import SourceFile
from capability_native import inspect_native_definitions,NativeDefinitionRule,parameter_digest
from capability_native_registry import NATIVE_DEFINITIONS,WRAPPER_SHA256


def source(path,raw):
    return SourceFile(path,hashlib.sha256(raw).hexdigest(),raw)


class NativeDefinitionLinks(unittest.TestCase):
    def fixture(self,raw=b'int api(int value){return value;}'):
        h=source('include/golem/fixture.h',b'int api(int value);')
        c=source('src/fixture.c',raw)
        rule=NativeDefinitionRule('api',c.path,c.sha256,h.path,h.sha256,None,parameter_digest(('int','value')))
        return (h,c),rule

    def test_actual_344_unique_definition_links_have_no_behavior_claim(self):
        root=Path(__file__).resolve().parents[1]
        paths=sorted({p for r in NATIVE_DEFINITIONS for p in (r.path,r.header_path)}|{'src/common/record_internal.h'})
        files=tuple(source(p,(root/p).read_bytes()) for p in paths)
        values=inspect_native_definitions(files,NATIVE_DEFINITIONS,WRAPPER_SHA256)
        self.assertEqual(len(values),344)
        self.assertFalse([v for v in values if v.blockers])
        self.assertTrue(all(not v.behavior_verified and not v.callback_receiver_verified and not v.execution_verified for v in values))

    def test_direct_definition_signature_and_duplicate_guard(self):
        for raw in (b'int api(int other){return other;}',b'int api(int value);',
                    b'int api(int value){return value;} int api(int value){return 1;}'):
            files,rule=self.fixture(raw)
            result=inspect_native_definitions(files,(rule,),'0'*64)
            self.assertTrue(result[0].blockers)

    def test_definition_and_declaration_missing_or_drifted_block(self):
        files,rule=self.fixture()
        self.assertFalse(inspect_native_definitions(files,(rule,),'0'*64)[0].blockers)
        for selected in (files[:1],files[1:],()):
            self.assertTrue(inspect_native_definitions(selected,(rule,),'0'*64)[0].blockers)
        self.assertTrue(inspect_native_definitions(files,(replace(rule,sha256='0'*64),),'0'*64)[0].blockers)

    def test_implementation_link_cannot_invent_public_header(self):
        files,rule=self.fixture()
        changed=source('src/private.h',files[0].data)
        result=inspect_native_definitions((changed,files[1]),(replace(rule,header_path=changed.path),),'0'*64)
        self.assertIn(('PRIVATE_DECLARATION_NOT_NATIVE_BOUNDARY',changed.path),result[0].blockers)

    def test_rule_duplicates_are_not_dropped(self):
        files,rule=self.fixture()
        with self.assertRaises(ValueError):inspect_native_definitions(files,(rule,rule),'0'*64)
