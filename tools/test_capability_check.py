"""CLI regression: a successful sample must not return repository success."""
import contextlib
import io
import unittest
from unittest.mock import patch

from capability_check import main


class CheckCommand(unittest.TestCase):
    def test_successful_selected_sample_with_repository_gap_returns_two(self):
        report={'selected_inventory_complete':True,'repository':{'blockers':[('PUBLIC_API_NOT_LISTED','api')]}}
        output=io.StringIO()
        with patch('capability_check.reconcile',return_value=(report,'incomplete\n')) as reconcile,contextlib.redirect_stdout(output):
            code=main(['--root','/explicit/root','--repository-sources','--format','markdown'])
        self.assertEqual(code,2)
        self.assertEqual(output.getvalue(),'incomplete\n')
        reconcile.assert_called_once_with('/explicit/root',public_headers=False,repository_sources=True)

    def test_input_failure_does_not_echo_arbitrary_source_or_private_path(self):
        output=io.StringIO()
        with patch('capability_check.reconcile',side_effect=ValueError('private material must not echo')),contextlib.redirect_stderr(output):
            code=main(['--root','/explicit/root'])
        self.assertEqual(code,1)
        self.assertNotIn('private material',output.getvalue())
        self.assertIn('INVALID_INPUT',output.getvalue())
