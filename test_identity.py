"""Offline file-attribution tests. Every persistent map lives in a temporary folder."""
import copy
import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import identity


def mod_record(key='m1', data=b'modified test bytes', name='Example Mod', component='example', file='0000456.jar'):
    return {'key': key, 'name': name, 'file': file, 'sha1': hashlib.sha1(data).hexdigest(),
            'sha256': hashlib.sha256(data).hexdigest(), 'version': '1.0.0', 'loader': 'Fabric',
            'components': [{'id': component, 'name': name, 'version': '1.0.0', 'aliases': []}],
            'cfFingerprint': identity.curseforge_fingerprint(data)}


class FakeIdentityAPI:
    def __init__(self):
        self.calls = []
        self.exact = {}
        self.projects = {'original': {'id': 'original', 'title': 'Example Mod', 'description': 'Original project', 'project_type': 'mod', 'loaders': ['fabric']}}
        self.hits = [{'project_id': 'original', 'title': 'Example Mod', 'description': 'Original project', 'project_type': 'mod', 'categories': ['fabric'], 'versions': ['1.21.1']}]
        self.cf_hits = [{'id': 123, 'name': 'CF Example', 'summary': 'CF original', 'slug': 'cf-example', 'gameId': 432, 'classId': 6}]
        self.cf_matches = []
        self.callback = None
        self.fail_hash = False
        self.fail_mr_search = False
        self.fail_cf_search = False

    def fetch(self, url, key=None, payload=None):
        self.calls.append((url, key, copy.deepcopy(payload)))
        parsed = urlsplit(url)
        if parsed.hostname != 'api.curseforge.com' and key:
            raise AssertionError('CF key leaked to another host')
        if self.callback:
            result = self.callback(url, key, payload)
            if result is not None:
                return json.dumps(result)
        if url == identity.MR + '/version_files':
            if self.fail_hash:
                raise ValueError('HTTP 429，请稍后重试')
            return json.dumps({sha: self.exact[sha] for sha in payload['hashes'] if sha in self.exact})
        if url.startswith(identity.MR + '/project/'):
            return json.dumps(self.projects[url.rsplit('/', 1)[-1]])
        if url.startswith(identity.MR + '/search?'):
            if self.fail_mr_search:
                raise ValueError('MR 搜索超时')
            return json.dumps({'hits': self.hits})
        if url == identity.CF + '/fingerprints/432':
            return json.dumps({'data': {'exactMatches': self.cf_matches, 'partialMatches': []}})
        if url.startswith(identity.CF + '/mods/search?'):
            if self.fail_cf_search:
                raise ValueError('CF 搜索超时')
            return json.dumps({'data': self.cf_hits})
        if url.startswith(identity.CF + '/mods/'):
            ident = int(url.rsplit('/', 1)[-1])
            return json.dumps({'data': next(row for row in self.cf_hits if row['id'] == ident)})
        raise AssertionError('Unexpected URL ' + url)


def wait(manager, ident, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = manager.status(ident)
        if value['status'] != 'running' and not any(row['searching'] for row in value['items']):
            return value
        time.sleep(.005)
    raise AssertionError('Identity test task timed out')


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fake = FakeIdentityAPI()
        self.patch = patch.object(identity.research, 'fetch', self.fake.fetch)
        self.patch.start()
        self.manager = identity.IdentityManager(self.root)

    def tearDown(self):
        self.manager.close()
        self.patch.stop()
        self.temp.cleanup()

    def check(self, mods=None):
        job = self.manager.start(mods or [mod_record()])
        return wait(self.manager, job['id'])

    def confirmed(self):
        state = self.check()
        row = state['items'][0]
        return self.manager.confirm(state['id'], row['key'], row['candidates'][0]['id'])

    def test_one_hash_miss_and_skipped_source_is_candidate_not_suspect_modification(self):
        state = self.check()
        row = state['items'][0]
        self.assertEqual(row['status'], 'suspect')
        self.assertEqual(row['label'], '候选来源 · 待确认')
        self.assertIsNone(row['exact'])
        self.assertIsNone(row['confirmation'])
        self.assertEqual(state['aiCalls'], 0)
        self.assertFalse((self.root / '.damn-public-user').exists())

    def test_mr_exact_hash_verifies_file_and_project(self):
        mod = mod_record()
        self.fake.exact[mod['sha1']] = {'id': 'exact-version', 'project_id': 'original', 'version_number': '1.0.0', 'files': [{'hashes': {'sha1': mod['sha1']}}]}
        state = self.check([mod])
        row = state['items'][0]
        self.assertEqual(row['status'], 'exact')
        self.assertEqual(row['exact']['versionId'], 'exact-version')
        self.assertEqual(row['candidates'], [])
        self.assertFalse(any('/search?' in call[0] for call in self.fake.calls))

    def test_mr_hash_response_without_same_file_digest_is_not_exact(self):
        mod = mod_record()
        self.fake.exact[mod['sha1']] = {'id': 'wrong', 'project_id': 'original', 'files': [{'hashes': {'sha1': '0' * 40}}]}
        self.assertEqual(self.check([mod])['items'][0]['status'], 'suspect')

    def test_cf_exact_requires_fingerprint_and_sha1(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'CF-ONLY-KEY')
        mod = mod_record()
        file = {'id': 456, 'modId': 123, 'fileFingerprint': mod['cfFingerprint'], 'hashes': [{'algo': 1, 'value': mod['sha1']}], 'displayName': 'Official file'}
        self.fake.cf_matches = [{'id': 123, 'file': file}]
        row = self.check([mod])['items'][0]
        self.assertEqual(row['status'], 'exact')
        self.assertEqual(row['exact']['site'], 'CurseForge')
        self.assertEqual(row['exact']['versionId'], '456')
        self.assertTrue(all(not key or urlsplit(url).hostname == 'api.curseforge.com' for url, key, _ in self.fake.calls))

    def test_cf_same_fingerprint_wrong_sha1_is_not_exact(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'CF-ONLY-KEY')
        mod = mod_record()
        self.fake.cf_matches = [{'id': 123, 'file': {'id': 456, 'modId': 123, 'fileFingerprint': mod['cfFingerprint'], 'hashes': [{'algo': 1, 'value': '0' * 40}]}}]
        self.assertEqual(self.check([mod])['items'][0]['status'], 'suspect')

    def test_network_error_is_not_proof_of_modification(self):
        self.fake.fail_hash = True
        row = self.check()['items'][0]
        self.assertEqual(row['status'], 'suspect')
        self.assertEqual(row['label'], '候选来源 · 待确认')
        self.assertEqual(row['checks']['Modrinth']['status'], 'error')
        self.assertEqual(row['checks']['CurseForge']['status'], 'skipped')

    def test_no_candidates_and_network_error_is_unfinished(self):
        self.fake.fail_hash = True
        self.fake.hits = []
        self.assertEqual(self.check()['items'][0]['status'], 'error')

    def test_no_candidates_is_unmatched_and_missing_cf_key_explained(self):
        self.fake.hits = []
        row = self.check()['items'][0]
        self.assertEqual(row['status'], 'unmatched')
        self.assertEqual(row['label'], '来源待确认')
        self.assertIn('查询服务未配置', row['checks']['CurseForge']['message'])

    def test_cf_failure_does_not_remove_mr_candidates(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'CF-ONLY-KEY')
        self.fake.fail_cf_search = True
        row = self.check()['items'][0]
        self.assertEqual(len(row['candidates']), 1)
        self.assertTrue(any('CurseForge 项目查询未完成' in note for note in row['notes']))

    def test_mr_failure_does_not_remove_cf_candidates(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'CF-ONLY-KEY')
        self.fake.fail_mr_search = True
        row = self.check()['items'][0]
        self.assertEqual(row['candidates'][0]['site'], 'CurseForge')

    def test_confirmation_is_hash_bound_not_exact_or_versioned(self):
        source = mod_record()
        original = copy.deepcopy(source)
        state = self.check([source])
        row = state['items'][0]
        confirmed = self.manager.confirm(state['id'], row['key'], row['candidates'][0]['id'])['items'][0]
        self.assertEqual(confirmed['status'], 'confirmed')
        self.assertIsNone(confirmed['exact'])
        self.assertNotIn('versionId', confirmed['confirmation'])
        self.assertEqual(source, original)
        entries = json.loads((self.root / '.damn-public-user/identity-map.json').read_text(encoding='utf-8'))['entries']
        self.assertIn(source['sha256'], entries)
        self.assertNotIn('exact', entries[source['sha256']])
        self.assertNotIn('versionId', entries[source['sha256']])
        self.assertNotIn('KEY', json.dumps(entries))

    def test_same_hash_with_new_filename_reuses_confirmation_without_network(self):
        self.confirmed()
        self.fake.calls.clear()
        mod = mod_record(file='改了编号与文件名.jar')
        row = self.check([mod])['items'][0]
        self.assertEqual(row['status'], 'confirmed')
        self.assertEqual(self.fake.calls, [])

    def test_hash_change_does_not_reuse_confirmation(self):
        self.confirmed()
        row = self.check([mod_record(data=b'changed again')])['items'][0]
        self.assertEqual(row['status'], 'suspect')
        self.assertIsNone(row['confirmation'])

    def test_components_signature_change_does_not_reuse_confirmation(self):
        self.confirmed()
        row = self.check([mod_record(component='different_metadata')])['items'][0]
        self.assertIsNone(row['confirmation'])

    def test_confirmation_survives_new_manager_instance(self):
        self.confirmed()
        self.manager.close()
        self.manager = identity.IdentityManager(self.root)
        self.fake.calls.clear()
        row = self.check()['items'][0]
        self.assertEqual(row['status'], 'confirmed')
        self.assertEqual(self.fake.calls, [])

    def test_clear_deletes_mapping_and_reenables_selection(self):
        state = self.confirmed()
        state = self.manager.clear(state['id'], 'm1')
        self.assertEqual(state['items'][0]['status'], 'suspect')
        self.assertIsNone(state['items'][0]['confirmation'])
        self.assertEqual(json.loads((self.root / '.damn-public-user/identity-map.json').read_text(encoding='utf-8'))['entries'], {})

    def test_candidate_id_cannot_be_forged_or_cross_item(self):
        state = self.check([mod_record(), mod_record('m2', data=b'another')])
        with self.assertRaises(ValueError):
            self.manager.confirm(state['id'], 'm1', 'https://evil.example/fake')
        with self.assertRaises(ValueError):
            self.manager.confirm(state['id'], 'm2', state['items'][0]['candidates'][0]['id'])
        with self.assertRaises(ValueError):
            self.manager.confirm(state['id'], 'm1', {'id': 'original', 'exact': True})

    def test_query_url_is_encoded_and_platform_hosts_are_fixed(self):
        state = self.check()
        query = '名称 & x-api-key=SECRET https://evil.example/?x=1'
        self.manager.search(state['id'], 'm1', query, 'Modrinth')
        wait(self.manager, state['id'])
        call = self.fake.calls[-1]
        self.assertEqual(urlsplit(call[0]).hostname, 'api.modrinth.com')
        self.assertEqual(parse_qs(urlsplit(call[0]).query)['query'], [query])
        self.assertIsNone(call[1])

    def test_candidates_deduplicate_by_project_and_cap_six(self):
        self.fake.hits = self.fake.hits * 3 + [{'project_id': 'p' + str(n), 'title': 'Candidate ' + str(n), 'project_type': 'mod'} for n in range(10)]
        values = self.check()['items'][0]['candidates']
        self.assertEqual(len(values), 6)
        self.assertEqual(len({(row['site'], row['projectId']) for row in values}), 6)

    def test_manifest_nonjar_and_bad_hash_are_not_queried(self):
        values = [dict(mod_record(), kind='manifest'), mod_record(file='not-a-jar.zip'), dict(mod_record(), sha256='not-a-hash')]
        state = self.manager.start(values)
        self.assertEqual(state['items'], [])
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(self.fake.calls, [])

    def test_component_id_used_when_filename_is_numeric(self):
        value = mod_record(name='000000001234', component='recognizable_id')
        self.check([value])
        searches = [parse_qs(urlsplit(url).query).get('query', [''])[0] for url, _, _ in self.fake.calls if '/search?' in url]
        self.assertIn('recognizable_id', searches)

    def test_partial_or_invalid_cf_fingerprint_is_explicitly_skipped(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'CF-ONLY-KEY')
        row = self.check([dict(mod_record(), cfFingerprint=None)])['items'][0]
        self.assertEqual(row['checks']['CurseForge']['status'], 'skipped')
        self.assertFalse(any('/fingerprints/' in url for url, _, _ in self.fake.calls))

    def test_old_job_cap_and_cancel(self):
        ids = [self.check()['id'] for _ in range(10)]
        self.assertLessEqual(len(self.manager.jobs), 8)
        with self.assertRaises(ValueError):
            self.manager.status(ids[0])
        self.assertEqual(self.manager.cancel(ids[-1])['status'], 'cancelled')

    def test_manual_search_stale_result_cannot_replace_latest(self):
        state = self.check()
        entered, release = threading.Event(), threading.Event()

        def callback(url, key, payload):
            if '/search?' in url:
                query = parse_qs(urlsplit(url).query)['query'][0]
                if query == 'old query':
                    entered.set()
                    release.wait(2)
                    return {'hits': [{'project_id': 'old', 'title': 'Old'}]}
                if query == 'new query':
                    return {'hits': [{'project_id': 'new', 'title': 'New'}]}

        self.fake.callback = callback
        try:
            self.manager.search(state['id'], 'm1', 'old query', 'modrinth')
            self.assertTrue(entered.wait(1))
            self.manager.search(state['id'], 'm1', 'new query', 'modrinth')
            release.set()
            state = wait(self.manager, state['id'])
            self.assertEqual(state['items'][0]['candidates'][0]['projectId'], 'new')
        finally:
            release.set()

    def test_manual_search_during_hash_lookup_wins_over_auto(self):
        entered, release = threading.Event(), threading.Event()

        def callback(url, key, payload):
            if url.endswith('/version_files'):
                entered.set()
                release.wait(2)
            if '/search?' in url and parse_qs(urlsplit(url).query)['query'][0] == 'manual choice':
                return {'hits': [{'project_id': 'manual', 'title': 'Manual'}]}

        self.fake.callback = callback
        try:
            state = self.manager.start([mod_record()])
            self.assertTrue(entered.wait(1))
            self.manager.search(state['id'], 'm1', 'manual choice', 'modrinth')
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and self.manager.status(state['id'])['items'][0]['searching']:
                time.sleep(.005)
            release.set()
            row = wait(self.manager, state['id'])['items'][0]
            self.assertEqual(row['candidates'][0]['projectId'], 'manual')
        finally:
            release.set()

    def test_cancel_inflight_lookup_does_not_publish_candidates(self):
        entered, release = threading.Event(), threading.Event()

        def callback(url, key, payload):
            if url.endswith('/version_files'):
                entered.set()
                release.wait(2)

        self.fake.callback = callback
        try:
            state = self.manager.start([mod_record()])
            self.assertTrue(entered.wait(1))
            self.manager.cancel(state['id'])
            release.set()
            state = self.manager.status(state['id'])
            self.assertEqual(state['status'], 'cancelled')
            self.assertEqual(state['items'][0]['candidates'], [])
        finally:
            release.set()

    def test_corrupt_map_is_not_silently_replaced(self):
        self.manager.close()
        directory = self.root / '.damn-public-user'
        directory.mkdir()
        target = directory / 'identity-map.json'
        target.write_bytes(b'corrupt original map')
        self.manager = identity.IdentityManager(self.root)
        state = self.check()
        self.assertTrue(state['notes'])
        with self.assertRaises(ValueError):
            self.manager.confirm(state['id'], 'm1', state['items'][0]['candidates'][0]['id'])
        self.assertEqual(target.read_bytes(), b'corrupt original map')

    def test_fingerprint_bytes_and_bytearray_match_known_vector(self):
        self.assertEqual(identity.curseforge_fingerprint(b'hello world'), 2824650221)
        self.assertEqual(identity.curseforge_fingerprint(bytearray(b'hello\r\n\t world')), 2824650221)
        with self.assertRaises(TypeError):
            identity.curseforge_fingerprint('hello')

    def test_new_search_invalidates_old_candidate_immediately(self):
        state = self.check()
        old = state['items'][0]['candidates'][0]['id']
        entered, release = threading.Event(), threading.Event()

        def callback(url, key, payload):
            if '/search?' in url:
                entered.set()
                release.wait(2)

        self.fake.callback = callback
        try:
            self.manager.search(state['id'], 'm1', 'new lookup', 'Modrinth')
            self.assertTrue(entered.wait(1))
            with self.assertRaises(ValueError):
                self.manager.confirm(state['id'], 'm1', old)
        finally:
            release.set()

    def test_version_response_error_object_is_not_a_hash_miss(self):
        self.fake.callback = lambda url, key, payload: {'error': 'rate_limited'} if url.endswith('/version_files') else None
        row = self.check()['items'][0]
        self.assertEqual(row['checks']['Modrinth']['status'], 'error')
        self.assertEqual(row['label'], '候选来源 · 待确认')

    def test_invalid_version_value_is_not_a_hash_miss(self):
        mod = mod_record()
        self.fake.exact[mod['sha1']] = []
        row = self.check([mod])['items'][0]
        self.assertEqual(row['checks']['Modrinth']['status'], 'error')
        self.assertEqual(row['label'], '候选来源 · 待确认')

    def test_persistent_mapping_cannot_forge_exact_or_inject_external_url(self):
        self.confirmed()
        self.manager.close()
        path = self.root / '.damn-public-user/identity-map.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        entry = next(iter(data['entries'].values()))
        entry.update(url='https://evil.example/', exact=True, versionId='forged')
        path.write_text(json.dumps(data), encoding='utf-8')
        self.manager = identity.IdentityManager(self.root)
        row = self.check()['items'][0]
        self.assertEqual(row['status'], 'confirmed')
        self.assertIsNone(row['exact'])
        self.assertEqual(row['confirmation']['url'], 'https://modrinth.com/mod/original')
        self.assertNotIn('versionId', row['confirmation'])

    def test_mapping_directory_link_is_not_followed(self):
        self.manager.close()
        outside = self.root / 'another-data'
        outside.mkdir()
        secret = outside / 'identity-map.json'
        secret.write_bytes(b'do not read or replace')
        try:
            (self.root / '.damn-public-user').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('系统不允许创建测试符号链接')
        self.manager = identity.IdentityManager(self.root)
        state = self.check()
        self.assertTrue(state['notes'])
        with self.assertRaises(ValueError):
            self.manager.confirm(state['id'], 'm1', state['items'][0]['candidates'][0]['id'])
        self.assertEqual(secret.read_bytes(), b'do not read or replace')

    def test_hash_queries_are_batched_and_input_limit_is_explicit(self):
        mods = [mod_record('m' + str(n), data=str(n).encode()) for n in range(81)]
        self.check(mods)
        calls = [payload for url, _, payload in self.fake.calls if url.endswith('/version_files')]
        self.assertEqual([len(payload['hashes']) for payload in calls], [80, 1])
        with self.assertRaises(ValueError):
            self.manager.start([{}] * 3001)

    def test_returned_job_is_a_detached_snapshot(self):
        state = self.check()
        state['items'][0]['candidates'][0]['url'] = 'https://evil.example/'
        current = self.manager.status(state['id'])
        self.assertEqual(current['items'][0]['candidates'][0]['url'], 'https://modrinth.com/mod/original')

    def test_queued_automatic_worker_cannot_overwrite_earlier_manual_action(self):
        worker_release, hash_release, hash_entered = threading.Event(), threading.Event(), threading.Event()
        worker_entered = [threading.Event() for _ in range(3)]

        def hold(marker):
            marker.set()
            worker_release.wait(2)

        def callback(url, key, payload):
            if url.endswith('/version_files'):
                hash_entered.set()
                hash_release.wait(2)
            if '/search?' in url and parse_qs(urlsplit(url).query)['query'][0] == 'queued manual':
                return {'hits': [{'project_id': 'manual', 'title': 'Manual'}]}

        self.fake.callback = callback
        try:
            for marker in worker_entered:
                self.manager.pool.submit(hold, marker)
            self.assertTrue(all(marker.wait(1) for marker in worker_entered))
            state = self.manager.start([mod_record()])
            self.manager.search(state['id'], 'm1', 'queued manual', 'Modrinth')
            worker_release.set()
            self.assertTrue(hash_entered.wait(1))
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and self.manager.status(state['id'])['items'][0]['searching']:
                time.sleep(.005)
            hash_release.set()
            self.assertEqual(wait(self.manager, state['id'])['items'][0]['candidates'][0]['projectId'], 'manual')
        finally:
            worker_release.set()
            hash_release.set()

    def test_all_site_candidate_limit_preserves_both_sites(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'CF-ONLY-KEY')
        self.fake.hits = [{'project_id': 'mr' + str(n), 'title': 'MR ' + str(n)} for n in range(6)]
        self.fake.cf_hits = [{'id': n + 10, 'name': 'CF ' + str(n), 'gameId': 432, 'classId': 6} for n in range(6)]
        rows = self.check()['items'][0]['candidates']
        self.assertEqual(len(rows), 6)
        self.assertEqual({row['site'] for row in rows}, {'Modrinth', 'CurseForge'})


    def test_renamed_title_keeps_component_and_repository_search_clues(self):
        mod = mod_record(name='My translated title', component='independent_feature')
        mod['components'][0].update(authors=['A developer'], projectUrls=['https://github.com/a-developer/independent-feature-mod/issues'])
        row = self.check([mod])['items'][0]
        self.assertEqual(row['query'], 'independent_feature')
        self.assertIn({'query': 'independent feature mod', 'source': '文件声明的源码仓库名'}, row['searchHints'])
        self.assertEqual(row['localMetadata']['authors'], ['A developer'])
        self.assertEqual(row['localMetadata']['componentIds'], ['independent_feature'])
        self.assertIsNone(row['exact'])
        self.assertIsNone(row['confirmation'])

    def test_nested_components_do_not_become_parent_identity_hints(self):
        mod = mod_record()
        mod['components'].append({'id': 'nested_other', 'name': 'Different bundled library', 'nested': True,
                                  'authors': ['Other author'], 'projectUrls': ['https://modrinth.com/mod/other']})
        row = self.check([mod])['items'][0]
        self.assertNotIn('nested_other', row['localMetadata']['componentIds'])
        self.assertFalse(any('other' in value['query'].lower() for value in row['searchHints']))

    def test_queries_split_generic_component_ids_without_name_lookup_table(self):
        self.fake.hits = []
        row = self.check([mod_record(name='Translated display', component='alpha_beta_tools')])['items'][0]
        queries = [value['query'] for value in row['searchChecks'] if value['site'] == 'Modrinth']
        self.assertIn('alpha_beta_tools', queries)
        self.assertIn('alpha beta tools', queries)
        self.assertLessEqual(len(queries), 4)
        self.assertEqual({value['status'] for value in row['searchChecks'] if value['site'] == 'Modrinth'}, {'not_found'})

    def test_search_diagnostics_distinguish_empty_search_from_unavailable_provider(self):
        self.fake.hits = []
        row = self.check()['items'][0]
        self.assertTrue(all(value['status'] == 'not_found' for value in row['searchChecks'] if value['site'] == 'Modrinth'))
        self.assertTrue(all(value['status'] == 'skipped' for value in row['searchChecks'] if value['site'] == 'CurseForge'))
        self.assertTrue(all(value['query'] for value in row['searchChecks']))
        self.assertFalse(any('API Key' in value['message'] for value in row['searchChecks']))

    def test_search_diagnostics_retain_provider_error(self):
        self.fake.fail_mr_search = True
        row = self.check()['items'][0]
        checks = [value for value in row['searchChecks'] if value['site'] == 'Modrinth']
        self.assertTrue(checks)
        self.assertTrue(all(value['status'] == 'error' and '超时' in value['message'] for value in checks))
        self.assertEqual(row['status'], 'error')

    def test_declared_modrinth_url_is_candidate_lookup_not_exact_file(self):
        mod = mod_record()
        mod['components'][0]['projectUrls'] = ['https://modrinth.com/mod/original']
        self.fake.hits = []
        row = self.check([mod])['items'][0]
        self.assertTrue(any(url == identity.MR + '/project/original' for url, _, _ in self.fake.calls))
        self.assertEqual(row['candidates'][0]['projectId'], 'original')
        self.assertIsNone(row['exact'])
        self.assertIsNone(row['confirmation'])

    def test_manual_official_url_fetches_project_not_literal_url_search(self):
        state = self.check()
        self.fake.calls.clear()
        self.manager.search(state['id'], 'm1', 'https://modrinth.com/mod/original', 'Modrinth')
        row = wait(self.manager, state['id'])['items'][0]
        self.assertEqual(self.fake.calls[0][0], identity.MR + '/project/original')
        self.assertEqual(row['candidates'][0]['projectId'], 'original')
        self.assertEqual(row['searchChecks'][0]['status'], 'matched')

    def test_project_urls_do_not_allow_arbitrary_fetch_or_wrong_platform(self):
        state = self.check()
        for query, platform in [('https://evil.example/mod/original', 'all'),
                                ('https://modrinth.com.evil.example/mod/original', 'all'),
                                ('https://user:password@modrinth.com/mod/original', 'all'),
                                ('https://modrinth.com:444/mod/original', 'all'),
                                ('https://modrinth.com/mod/original', 'CurseForge')]:
            with self.assertRaises(ValueError):
                self.manager.search(state['id'], 'm1', query, platform)

    def test_cf_project_link_without_service_is_explicitly_unqueried(self):
        state = self.check()
        self.fake.calls.clear()
        self.manager.search(state['id'], 'm1', 'https://www.curseforge.com/minecraft/mc-mods/example-project', 'all')
        row = wait(self.manager, state['id'])['items'][0]
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(row['searchChecks'][0]['status'], 'skipped')
        self.assertEqual(row['candidates'], [])

    def mirror_api(self, url, key, payload):
        if url.startswith('https://mod.mcimirror.top/'):
            self.assertIsNone(key)
            self.assertIsNone(payload)
            if '/modrinth/v2/search?' in url:
                return {'hits': self.fake.hits}
            if '/modrinth/v2/project/' in url:
                return self.fake.projects['original']
            if '/curseforge/v1/mods/search?' in url:
                return {'data': self.fake.cf_hits}
            if '/curseforge/v1/mods/' in url:
                return {'data': self.fake.cf_hits[0]}
            self.fail('Unexpected mirror endpoint')

    def test_mcim_is_explicit_only_and_never_receives_official_key(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'OFFICIAL-ONLY')
        state = self.check()
        self.assertFalse(any('mcimirror' in url for url, _, _ in self.fake.calls))
        self.fake.callback = self.mirror_api
        self.fake.calls.clear()
        self.manager.search(state['id'], 'm1', 'Example Mod', 'MCIM')
        row = wait(self.manager, state['id'])['items'][0]
        self.assertEqual({value['site'] for value in row['candidates']}, {'Modrinth', 'CurseForge'})
        self.assertTrue(all(value['provider'] == 'MCIM' for value in row['candidates']))
        self.assertTrue(all(key is None for _, key, _ in self.fake.calls))
        self.assertTrue(all(value['provider'] == 'MCIM' for value in row['searchChecks']))
        self.assertIsNone(row['exact'])

    def test_mcim_confirmation_refetches_project_and_remains_user_attribution(self):
        state = self.check()
        self.fake.callback = self.mirror_api
        self.manager.search(state['id'], 'm1', 'Example Mod', 'MCIM')
        row = wait(self.manager, state['id'])['items'][0]
        self.fake.calls.clear()
        row = self.manager.confirm(state['id'], 'm1', row['candidates'][0]['id'])['items'][0]
        self.assertEqual(self.fake.calls[0][0], identity.MCIM_MR + '/project/original')
        self.assertEqual(row['status'], 'confirmed')
        self.assertEqual(row['confirmation']['provider'], 'MCIM')
        self.assertIsNone(row['exact'])
        self.assertNotIn('versionId', row['confirmation'])
        self.manager.close()
        self.manager = identity.IdentityManager(self.root)
        self.assertEqual(self.check()['items'][0]['confirmation']['provider'], 'MCIM')

    def test_mcim_confirmation_rejects_different_project_id(self):
        state = self.check()
        self.fake.callback = self.mirror_api
        self.manager.search(state['id'], 'm1', 'Example Mod', 'MCIM')
        row = wait(self.manager, state['id'])['items'][0]
        self.fake.projects['original'] = {'id': 'different', 'title': 'Another project', 'project_type': 'mod'}
        with self.assertRaisesRegex(ValueError, '项目 ID 不符'):
            self.manager.confirm(state['id'], 'm1', row['candidates'][0]['id'])
        self.assertIsNone(self.manager.status(state['id'])['items'][0]['confirmation'])
        self.assertFalse((self.root / '.damn-public-user').exists())

    def test_mcim_actual_failure_is_shown_without_fabricated_candidates(self):
        state = self.check()
        def unavailable(url, key, payload):
            if 'mcimirror' in url:
                raise ValueError('站点返回 HTTP 503，资料暂不可用。')
        self.fake.callback = unavailable
        self.manager.search(state['id'], 'm1', 'Example Mod', 'MCIM')
        row = wait(self.manager, state['id'])['items'][0]
        self.assertEqual(row['candidates'], [])
        self.assertEqual(row['status'], 'error')
        self.assertEqual(len(row['searchChecks']), 2)
        self.assertTrue(all(value['status'] == 'error' and '503' in value['message'] for value in row['searchChecks']))

    def test_cf_slug_link_matches_exact_slug_in_search_results(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'OFFICIAL-ONLY')
        state = self.check()
        self.fake.cf_hits.append({'id': 999, 'name': 'Wrong project', 'slug': 'wrong-slug', 'gameId': 432, 'classId': 6})
        self.manager.search(state['id'], 'm1', 'https://www.curseforge.com/minecraft/mc-mods/cf-example', 'CurseForge')
        row = wait(self.manager, state['id'])['items'][0]
        self.assertEqual([value['projectId'] for value in row['candidates']], ['123'])



    def test_direct_project_response_cannot_substitute_other_identity(self):
        state = self.check()
        self.fake.projects['original'] = {'id': 'different', 'title': 'Another project', 'project_type': 'mod'}
        self.manager.search(state['id'], 'm1', 'https://modrinth.com/mod/original', 'modrinth')
        row = wait(self.manager, state['id'])['items'][0]
        self.assertEqual(row['candidates'], [])
        self.assertEqual(row['searchChecks'][0]['status'], 'error')
        self.assertIn('项目与链接不符', row['searchChecks'][0]['message'])

    def test_modrinth_slug_response_resolves_real_project_id(self):
        state = self.check()
        self.fake.projects['readable-slug'] = {'id': 'actual-id', 'slug': 'readable-slug', 'title': 'Real project', 'project_type': 'mod'}
        self.manager.search(state['id'], 'm1', 'https://modrinth.com/mod/readable-slug', 'modrinth')
        row = wait(self.manager, state['id'])['items'][0]
        self.assertEqual(row['candidates'][0]['projectId'], 'actual-id')
        self.assertIsNone(row['exact'])



    def test_all_hash_sources_miss_with_candidates_can_be_suspect(self):
        self.manager.close()
        self.manager = identity.IdentityManager(self.root, lambda: 'CF-ONLY-KEY')
        row = self.check()['items'][0]
        self.assertEqual({check['status'] for check in row['checks'].values()}, {'not_found'})
        self.assertEqual(row['label'], '疑似魔改 · 待确认')
        self.assertIsNone(row['exact'])
        self.assertIsNone(row['confirmation'])

    def test_incomplete_hash_source_never_claims_suspect_modification(self):
        for status in ('skipped', 'error', 'checking', 'matched'):
            with self.subTest(status=status):
                item = {'checks': {'source-a': {'status': 'not_found'}, 'source-b': {'status': status}},
                        'candidates': [{'id': 'a-candidate'}], 'exact': None, 'confirmation': None, 'notes': []}
                self.manager._derive(item)
                self.assertEqual(item['label'], '候选来源 · 待确认')

    def test_candidate_without_finished_hash_checks_does_not_claim_modification(self):
        item = {'checks': {}, 'candidates': [{'id': 'a-candidate'}], 'exact': None, 'confirmation': None, 'notes': []}
        self.manager._derive(item)
        self.assertEqual(item['label'], '候选来源 · 待确认')

    def test_exact_match_still_wins_over_incomplete_other_source(self):
        item = {'checks': {'source-a': {'status': 'matched'}, 'source-b': {'status': 'skipped'}},
                'candidates': [], 'exact': {'projectId': 'a-real-project'}, 'confirmation': None, 'notes': []}
        self.manager._derive(item)
        self.assertEqual(item['status'], 'exact')
        self.assertEqual(item['label'], '官方文件 · 精确匹配')


if __name__ == '__main__':
    unittest.main()
