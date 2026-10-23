"""Audit observations do not delete evidence, grant access or reserve capacity."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import integration_backend as backend
import integration_contract as c
import integration_service as service
import test_integration_d2 as fixtures


class Capacity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_exact_read_capacity_and_boundaries(self):
        for i in range(255):
            (self.root / f'read-{i}').mkdir()
        report = backend._quota(self.root)
        self.assertEqual(report['remaining']['read_directories'], 1)
        with self.assertRaises(c.IntegrationError) as raised:
            backend._quota(self.root, 3)
        self.assertEqual(raised.exception.code, 'AUDIT_QUOTA')
        self.assertEqual(raised.exception.audit_capacity['reasons'], ['READ_DIRECTORY_HEADROOM'])
        (self.root / 'read-last').mkdir()
        self.assertEqual(backend.audit_capacity(self.root)['reasons'], ['READ_DIRECTORY_LIMIT'])
        self.assertEqual(len(list(self.root.iterdir())), 256)

    def test_bytes_entries_and_no_follow(self):
        p = self.root / 'private-name'
        p.write_bytes(b'1234')
        with patch.dict(backend.AUDIT_LIMITS, bytes=3):
            report = backend.audit_capacity(self.root)
            self.assertEqual(report['reasons'], ['BYTE_LIMIT'])
            self.assertEqual(report['usage']['bytes'], 4)
        with patch.dict(backend.AUDIT_LIMITS, entries=0):
            report = backend.audit_capacity(self.root)
            self.assertFalse(report['inventory_complete'])
            self.assertTrue(all(v is None for v in report['remaining'].values()))
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        report = backend.audit_capacity(self.root)
        self.assertIn('UNSAFE_FILE_TYPE', report['reasons'])
        self.assertNotIn('private-name', str(report))
        self.assertFalse(report['inventory_complete'])
        alias.unlink()
        os.link(p, alias)
        self.assertIn('UNSAFE_HARDLINK', backend.audit_capacity(self.root)['reasons'])
        self.assertEqual(p.read_bytes(), b'1234')

    def test_unreadable_inventory_is_not_free_capacity(self):
        with patch.object(backend.os, 'scandir', side_effect=PermissionError('/secret')):
            report = backend.audit_capacity(self.root)
            self.assertEqual(report['reasons'], ['INVENTORY_UNREADABLE'])
            self.assertFalse(report['inventory_complete'])
            self.assertNotIn('/secret', str(report))
            with self.assertRaises(c.IntegrationError):
                backend._quota(self.root)


class CapacityService(unittest.TestCase):
    for name in ('setUp', 'approve', 'query', 'expect', 'inventory', 'save_policy', 'adapter'):
        locals()[name] = getattr(fixtures.D2, name)

    def test_saturated_listing_is_read_only_and_does_not_admit_work(self):
        api = service.Service(self.adapter())
        for i in range(256):
            (self.registry.root / f'read-{i}').mkdir()
        before = set(self.registry.root.rglob('*'))
        with patch.object(service.records, 'capture', side_effect=AssertionError('no native call')):
            response = api.call('projects_list', {})
            self.assertEqual(response['state'], 'AVAILABLE')
            self.assertEqual(response['audit_capacity']['state'], 'BLOCKED')
            self.expect('AUDIT_QUOTA', lambda: api.call('work_inspect',
                        {'project_id':'p', 'work_id':'a', 'view':'status'}))
        self.assertEqual(before, set(self.registry.root.rglob('*')))

    def test_compound_query_rejects_before_first_read(self):
        api = service.Service(self.adapter())
        for i in range(254):
            (self.registry.root / f'read-{i}').mkdir()
        before = set(self.registry.root.rglob('*'))
        with patch.object(api, '_read', side_effect=AssertionError('no partial audit')):
            self.expect('AUDIT_QUOTA', lambda: api.call('completion_check',
                        {'project_id':'p', 'work_id':'a', 'selection_id':'s'}))
            self.expect('AUDIT_QUOTA', lambda: api.call('context_get',
                        {'project_id':'p', 'work_id':'a', 'selection_id':'s',
                         'source_snapshot':'f'*64, 'target_kind':'planning', 'recipe':'current-v1'}))
        self.assertEqual(before, set(self.registry.root.rglob('*')))

    def test_preflight_does_not_reserve_or_disclose_unapproved_registry(self):
        api = service.Service(self.adapter())
        first = api.call('projects_list', {})['audit_capacity']
        (self.registry.root / 'read-external').mkdir()
        second = api.call('projects_list', {})['audit_capacity']
        self.assertEqual(second['remaining']['read_directories'], first['remaining']['read_directories']-1)
        self.assertFalse(second['reservation_created'])
        self.approve('revoke')
        self.assertNotIn('audit_capacity', api.call('projects_list', {}))

    def test_error_explanation_does_not_infer_nonexistence_or_work_failure(self):
        response = service.blocked(c.IntegrationError('EVIDENCE_NOT_REFERENCED'))
        self.assertIn('Storage existence', response['explanation'])
        self.assertEqual(response['work_outcome'], 'NOT_DETERMINED_BY_THIS_ERROR')
        self.assertIn('NULL_DOES_NOT_PROVE', response['local_evidence_id_semantics'])
        self.assertFalse(response['automatic_retry_allowed'])
