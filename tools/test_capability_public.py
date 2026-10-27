import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from capability_files import SourceFile
from capability_public import PublicHeaderRule, scan_public_headers
from capability_public_registry import PUBLIC_HEADERS


def file(path, raw):
    return SourceFile(path, hashlib.sha256(raw).hexdigest(), raw)


class PublicInventory(unittest.TestCase):
    def test_all_current_headers_have_exact_finite_declarations(self):
        root = Path(__file__).resolve().parents[1]
        sources = tuple(file(r.path, (root/r.path).read_bytes()) for r in PUBLIC_HEADERS)
        scan = scan_public_headers(sources, PUBLIC_HEADERS)
        self.assertFalse(scan.unresolved)
        self.assertEqual(len(sources), 48)
        self.assertEqual(len(scan.observations), 344)
        self.assertEqual(len({o.id for o in scan.observations}), 344)

    def test_no_inputs_are_implicitly_selected(self):
        self.assertEqual(scan_public_headers((), PUBLIC_HEADERS).observations, ())

    def test_drift_and_new_api_with_repin_require_reviewed_name_set(self):
        f = file('include/golem/fixture.h', b'int api(void);')
        rule = PublicHeaderRule(f.path, f.sha256, ('api',))
        changed = file(f.path, f.data+b'int new_api(void);')
        for r in (rule, replace(rule, sha256=changed.sha256)):
            scan = scan_public_headers((changed,), (r,))
            self.assertTrue(scan.unresolved)
            self.assertFalse(scan.observations)

    def test_duplicates_and_local_prototypes_do_not_hide_missing_api(self):
        for raw in (b'int api(void); int api(void);', b'void f(void) { int api(void); }'):
            f = file('include/golem/fixture.h', raw)
            scan = scan_public_headers((f,), (PublicHeaderRule(f.path, f.sha256, ('api',)),))
            self.assertTrue(scan.unresolved)
