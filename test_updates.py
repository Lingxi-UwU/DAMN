import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from scanner import VERSION
from server import create_local_server, close_local_server
from updates import UpdatePreferencesStore, parse_update_body


class UpdatePreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = UpdatePreferencesStore(self.root / '.damn-public-user', 'fixture-version')

    def test_default_and_check_are_truthful_and_do_not_create_files(self):
        with patch('urllib.request.build_opener', side_effect=AssertionError('no outbound updates')):
            state = self.store.public()
            self.assertEqual(state, {'schemaVersion': 1, 'currentVersion': 'fixture-version',
                'serviceConfigured': False, 'status': 'not_configured',
                'preferences': {'channel': 'stable', 'checkMode': 'manual'}})
            self.assertEqual(self.store.check({})['status'], 'unavailable')
            self.assertEqual(self.store.check({})['code'], 'public_feature_unavailable')
        self.assertFalse(self.store.directory.exists())
        state['preferences']['channel'] = 'preview'
        self.assertEqual(self.store.public()['preferences']['channel'], 'stable')

    def test_save_and_restart_are_isolated_from_ai_settings(self):
        self.store.directory.mkdir()
        settings = self.store.directory / 'settings.json'
        sentinel = b'{"fixture":"do not read or rewrite","apiKey":"test-only"}'
        settings.write_bytes(sentinel)
        with patch('settings.SettingsStore.read', side_effect=AssertionError('no AI settings')):
            saved = self.store.save_preferences({'channel': 'preview', 'checkMode': 'startup'})
            fresh = UpdatePreferencesStore(self.store.directory, 'new-version').public()
            self.assertEqual(fresh['preferences'], saved['preferences'])
            self.assertEqual(fresh['currentVersion'], 'new-version')
            self.assertFalse(fresh['serviceConfigured'])
            self.assertEqual(fresh['status'], 'not_configured')
            self.assertEqual(self.store.check({})['preferences'], saved['preferences'])
            self.assertEqual(self.store.check({})['status'], 'unavailable')
        self.assertEqual(settings.read_bytes(), sentinel)
        self.assertEqual({p.name for p in self.store.directory.iterdir()}, {'settings.json', 'updates.json'})
        self.assertEqual(json.loads(self.store.file.read_text(encoding='utf8')),
            {'schemaVersion': 1, 'channel': 'preview', 'checkMode': 'startup'})

    def test_invalid_preferences_and_nonempty_checks_do_not_write(self):
        bad = [None, [], {}, {'channel': 'stable'}, {'channel': 'stable', 'checkMode': 'manual', 'url': 'https://example.invalid'},
            {'channel': 'latest', 'checkMode': 'manual'}, {'channel': [], 'checkMode': 'manual'},
            {'channel': True, 'checkMode': 'manual'}, {'channel': 'stable', 'checkMode': False},
            {'channel': 'stable', 'checkMode': 'hourly'}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):self.store.save_preferences(value)
        for value in (None, [], {'channel': 'stable'}, {'url': 'https://example.invalid'}):
            with self.subTest(value=value), self.assertRaises(ValueError):self.store.check(value)
        self.assertFalse(self.store.directory.exists())

    def test_failed_atomic_write_preserves_previous_preferences(self):
        previous = self.store.save_preferences({'channel': 'stable', 'checkMode': 'manual'})
        raw = self.store.file.read_bytes()
        with patch('updates.os.replace', side_effect=OSError('sensitive internal path')):
            with self.assertRaisesRegex(ValueError, '^更新偏好未能保存，请重试。$'):
                self.store.save_preferences({'channel': 'preview', 'checkMode': 'startup'})
        self.assertEqual(self.store.file.read_bytes(), raw)
        self.assertEqual(self.store.public(), previous)
        self.assertEqual({p.name for p in self.store.directory.iterdir()}, {'updates.json'})

    def test_corrupt_files_are_explicit_and_can_be_repaired_by_save(self):
        self.store.directory.mkdir()
        values = ['broken', '[]', '{"schemaVersion":true,"channel":"stable","checkMode":"manual"}',
            '{"schemaVersion":1,"channel":"unknown","checkMode":"manual"}',
            '{"schemaVersion":1,"channel":"stable","channel":"preview","checkMode":"manual"}', 'x' * 4097]
        for raw in values:
            with self.subTest(raw=raw[:80]):
                self.store.file.write_text(raw, encoding='utf8')
                with self.assertRaisesRegex(ValueError, '^更新偏好无法读取，请重新选择并保存。$'):self.store.public()
                self.assertEqual(self.store.file.read_text(encoding='utf8'), raw)
                self.store.save_preferences({'channel': 'preview', 'checkMode': 'manual'})
                self.assertEqual(self.store.public()['preferences'], {'channel': 'preview', 'checkMode': 'manual'})

    def test_concurrent_saves_always_leave_one_complete_valid_document(self):
        values = [{'channel': 'stable', 'checkMode': 'manual'}, {'channel': 'preview', 'checkMode': 'startup'}] * 10
        with ThreadPoolExecutor(max_workers=4) as pool:
            states = list(pool.map(self.store.save_preferences, values))
        self.assertTrue(all(s['preferences'] in values for s in states))
        self.assertIn(self.store.public()['preferences'], values)
        self.assertEqual({p.name for p in self.store.directory.iterdir()}, {'updates.json'})

    def test_request_parser_rejects_duplicate_deep_and_oversized_bodies(self):
        self.assertEqual(parse_update_body(b'{}'), {})
        for raw in (b'', b'[]', b'null', b'{"channel":"stable","channel":"preview"}',
                    b'[' * 1600 + b']' * 1600, b' ' * 4097, b'\xff'):
            with self.subTest(raw=raw[:50]), self.assertRaisesRegex(ValueError, '^更新设置请求格式不正确。$'):
                parse_update_body(raw)


class UpdateAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / '.damn-public-user'
        self.profile.mkdir()
        self.settings = self.profile / 'settings.json'
        self.sentinel = b'{"fixture":"do not read","apiKey":"test-only"}'
        self.settings.write_bytes(self.sentinel)
        self.server = create_local_server(0, self.root)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.worker.join(3)
        close_local_server(self.server)

    def request(self, method, path, data=None, *, token=True, headers=None):
        merged = {'X-DAMN-Token': self.server.token} if token else {}
        if headers:merged.update(headers)
        raw = data if isinstance(data, bytes) else json.dumps(data).encode('utf8') if data is not None else None
        if raw is not None:merged['Content-Type'] = 'application/json'
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=raw, headers=merged)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:connection.close()

    def test_read_save_and_check_contract_is_local_and_survives_new_store(self):
        with patch('server.build_opener', side_effect=AssertionError('no outbound update request')), \
             patch('server.ai_request', side_effect=AssertionError('no AI call')), \
             patch('settings.SettingsStore.read', side_effect=AssertionError('no AI settings')):
            status, initial = self.request('GET', '/api/updates')
            self.assertEqual(status, 200)
            self.assertEqual(initial['currentVersion'], VERSION)
            self.assertEqual(initial['preferences'], {'channel': 'stable', 'checkMode': 'manual'})
            self.assertFalse((self.profile / 'updates.json').exists())
            preferences = {'channel': 'preview', 'checkMode': 'startup'}
            status, saved = self.request('POST', '/api/updates/preferences', preferences)
            self.assertEqual(status, 200)
            self.assertEqual(saved['preferences'], preferences)
            check_status, checked = self.request('POST', '/api/updates/check', {})
            self.assertEqual(check_status, 501)
            self.assertEqual(checked['status'], 'unavailable')
            self.assertEqual(checked['code'], 'public_feature_unavailable')
            self.assertEqual(checked['preferences'], saved['preferences'])
            self.assertEqual(self.request('GET', '/api/updates'), (200, saved))
        fresh = UpdatePreferencesStore(self.profile, VERSION).public()
        self.assertEqual(saved, fresh)
        self.assertEqual(set(saved), {'schemaVersion', 'currentVersion', 'serviceConfigured', 'status', 'preferences'})
        self.assertIs(saved['serviceConfigured'], False)
        self.assertEqual(saved['status'], 'not_configured')
        self.assertEqual(self.settings.read_bytes(), self.sentinel)

    def test_session_and_origin_protection_apply_to_all_update_routes(self):
        cases = [('GET', '/api/updates', None), ('POST', '/api/updates/check', {}),
                 ('POST', '/api/updates/preferences', {'channel': 'stable', 'checkMode': 'manual'})]
        for method, path, body in cases:
            with self.subTest(path=path):
                self.assertEqual(self.request(method, path, body, token=False)[0], 403)
                self.assertEqual(self.request(method, path, body, headers={'Origin': 'https://example.invalid'})[0], 403)
        self.assertFalse((self.profile / 'updates.json').exists())

    def test_invalid_api_inputs_cannot_write_or_trigger_update_checks(self):
        for value in ({}, [], {'channel': 'stable', 'checkMode': 'manual', 'apiKey': 'test-only'},
                      {'channel': [], 'checkMode': 'manual'}, {'channel': 'stable', 'checkMode': 'automatic'}):
            with self.subTest(value=value):
                self.assertEqual(self.request('POST', '/api/updates/preferences', value)[0], 400)
        for raw in (b'{"channel":"stable","channel":"preview","checkMode":"manual"}',
                    b'[' * 1600 + b']' * 1600):
            self.assertEqual(self.request('POST', '/api/updates/preferences', raw)[0], 400)
        self.assertEqual(self.request('POST', '/api/updates/preferences', b' ' * 4097)[0], 413)
        self.assertEqual(self.request('POST', '/api/updates/check', {'url': 'https://example.invalid'})[0], 400)
        self.assertFalse((self.profile / 'updates.json').exists())
        self.assertEqual(self.settings.read_bytes(), self.sentinel)

    def test_read_and_save_errors_remain_failures_without_internal_paths(self):
        with patch.object(self.server.updates, '_read', side_effect=ValueError('更新偏好无法读取，请重新选择并保存。')):
            self.assertEqual(self.request('GET', '/api/updates'), (400, {'error': '更新偏好无法读取，请重新选择并保存。'}))
        with patch('updates.os.replace', side_effect=OSError('/private/test-path')):
            self.assertEqual(self.request('POST', '/api/updates/preferences', {'channel': 'stable', 'checkMode': 'manual'}),
                (400, {'error': '更新偏好未能保存，请重试。'}))
        self.assertFalse((self.profile / 'updates.json').exists())


if __name__ == '__main__':
    unittest.main()
