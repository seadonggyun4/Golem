"""Adversarial declarations: a call or local prototype is not a public API."""
import unittest

from capability_c_closure import public_declaration


class PublicDeclarations(unittest.TestCase):
    def test_casts_and_control_parentheses_are_not_function_pointer_calls(self):
        from capability_c_syntax import call_sites
        sites=call_sites('if(ok) (void)f(); x=(size_t)(n+1); y=(unsigned char)(c);')
        self.assertEqual([s.expression for s in sites],[('f',)])
        for body in ('(*fn)(x);','(*size_t)(x);','(other)(x);','factory()(x);','host->read(x);'):
            self.assertTrue(any(s.indirect for s in call_sites(body)),body)
    def test_direct_file_scope_prototype(self):
        public_declaration(b'#ifndef API_H\n#define API_H\nextern int api(int x);\n#endif\n', 'api')

    def test_call_local_static_typedef_and_initializer_are_not_public(self):
        for raw in (
            b'void f(void) { api(1); }',
            b'void f(void) { int api(int x); }',
            b'static int api(int x);',
            b'typedef int api(int x);',
            b'int x = api(1);',
            b'int (*api)(int x);',
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                public_declaration(raw, 'api')

    def test_macro_or_duplicate_is_not_an_unambiguous_prototype(self):
        for raw in (b'#define api(x) other(x)\nint api(int x);',
                    b'int api(int x);\nint api(int x);'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                public_declaration(raw, 'api')

    def test_guard_directives_do_not_contaminate_first_declaration(self):
        public_declaration(b'#include "types.h"\nint api(void);\n', 'api')
