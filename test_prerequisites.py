"""Offline prerequisite planner/installer regression cases; no real network/API key."""
import hashlib
import io
import json
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import prerequisites as pre
REAL_DOWNLOAD = pre.download_file


def jar_bytes(ident, version='1.0.0', depends=None, breaks=None, loader='fabric', aliases=None, nested=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        if loader == 'fabric':
            data = {'schemaVersion': 1, 'id': ident, 'name': '示例 ' + ident, 'version': version,
                    'depends': {'minecraft': '1.21.1', **(depends or {})}, 'breaks': breaks or {}, 'provides': aliases or []}
            if nested:
                data['jars'] = [{'file': 'nested.jar'}]
                archive.writestr('nested.jar', nested)
            archive.writestr('fabric.mod.json', json.dumps(data))
        else:
            descriptor = 'META-INF/neoforge.mods.toml' if loader == 'neoforge' else 'META-INF/mods.toml'
            text = 'modLoader="javafml"\nloaderVersion="*"\nlicense="MIT"\n[[mods]]\nmodId="' + ident + '"\nversion="' + version + '"\ndisplayName="示例 ' + ident + '"\n'
            for target, rule in {'minecraft': '[1.21.1]', **(depends or {})}.items():
                text += '\n[[dependencies.' + ident + ']]\nmodId="' + target + '"\nmandatory=true\nversionRange="' + rule + '"\nside="BOTH"\n'
            archive.writestr(descriptor, text)
    return output.getvalue()


class FakePlatform:
    """Reusable browser-preview fixture: A is local, A -> B -> C required."""
    def __init__(self, root, loader='fabric'):
        self.root = Path(root)
        self.mods = self.root / 'mods'
        self.mods.mkdir(parents=True, exist_ok=True)
        self.loader = loader
        self.calls = []
        self.downloads = []
        self.before_download = None
        self.blobs = {}
        self.versions = {}
        self.projects = {}
        self.by_hash = {}
        self.add('A', 'main_mod', {'lib_b': '*'}, ['B'], local=True)
        self.add('B', 'lib_b', {'lib_c': '*'}, ['C'])
        self.add('C', 'lib_c', {}, [])

    def add(self, project, component, depends=None, dependencies=None, local=False, version='1.0.0', loader=None, suffix='', blob=None):
        data = blob if blob is not None else jar_bytes(component, version, depends, loader=loader or self.loader)
        sha1 = hashlib.sha1(data).hexdigest()
        version_id = project + (suffix or 'Version')
        filename = project + suffix + '.jar'
        url = 'https://cdn.modrinth.com/data/' + project + '/versions/' + version_id + '/' + filename
        value = {'id': version_id, 'project_id': project, 'version_number': version, 'game_versions': ['1.21.1'],
                 'loaders': [loader or self.loader], 'version_type': 'release', 'date_published': '2026-10-20T00:00:00Z',
                 'files': [{'filename': filename, 'url': url, 'primary': True, 'size': len(data),
                            'hashes': {'sha1': sha1, 'sha512': hashlib.sha512(data).hexdigest()}}],
                 'dependencies': [{'project_id': dep, 'dependency_type': 'required'} if isinstance(dep, str) else dep for dep in dependencies or []]}
        self.versions[version_id] = value
        self.projects[project] = {'id': project, 'title': '构造资料 ' + component, 'project_type': 'mod', 'server_side': 'required', 'client_side': 'required'}
        self.blobs[url] = data
        self.by_hash[sha1] = value
        if local:
            (self.mods / filename).write_bytes(data)
        return value

    def api(self, url, key=None, payload=None):
        self.calls.append((url, key, payload))
        parsed = urlsplit(url)
        if url == pre.MR + '/version_files':
            return {value: self.by_hash[value] for value in payload['hashes'] if value in self.by_hash}
        path = parsed.path.removeprefix('/v2/').split('/')
        if path[0] == 'project' and len(path) == 2:
            return self.projects[path[1]]
        if path[0] == 'project' and len(path) == 3 and path[2] == 'version':
            return [value for value in self.versions.values() if value['project_id'] == path[1]]
        if path[0] == 'version':
            return self.versions[path[1]]
        raise ValueError('模拟平台没有这个官方 API：' + url)

    def download(self, url, destination, expected_size, hashes, event, cf_key=None):
        self.downloads.append(url)
        if self.before_download:
            self.before_download(url, destination, event)
        pre._cancel(event)
        Path(destination).write_bytes(self.blobs[url])


def wait(manager, ident, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = manager.status(ident)
        if value['status'] not in ('planning', 'installing'):
            # The public status can finish immediately before finally removes staging.
            thread = manager.jobs[ident].get('thread')
            if thread:
                thread.join(1)
            return manager.status(ident)
        time.sleep(.01)
    raise AssertionError('后台模拟任务超时')


class PrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.platform = FakePlatform(self.root)
        self.api_patch = patch.object(pre, 'api_json', self.platform.api)
        self.download_patch = patch.object(pre, 'download_file', self.platform.download)
        self.api_patch.start()
        self.download_patch.start()
        self.manager = pre.PrerequisiteManager()

    def tearDown(self):
        self.manager.close()
        self.api_patch.stop()
        self.download_patch.stop()
        self.temp.cleanup()

    def plan(self, **kwargs):
        value = self.manager.start_plan(str(self.root), **kwargs)
        return wait(self.manager, value['id'])

    def install(self, state, ids=None):
        self.manager.install(state['id'], ids or ['Modrinth:B'])
        return wait(self.manager, state['id'])

    def test_recursive_plan_and_atomic_install_closure(self):
        state = self.plan()
        self.assertEqual(state['status'], 'ready')
        self.assertEqual({row['id'] for row in state['items']}, {'Modrinth:B', 'Modrinth:C'})
        self.assertEqual(self.platform.downloads, [])
        self.assertEqual([p.name for p in self.platform.mods.iterdir()], ['A.jar'])
        state = self.install(state)
        self.assertEqual(state['status'], 'complete', state['message'])
        self.assertEqual({p.name for p in self.platform.mods.iterdir()}, {'A.jar', 'B.jar', 'C.jar'})
        self.assertEqual({row['status'] for row in state['items']}, {'installed'})
        self.assertEqual(len(self.platform.downloads), 2)

    def test_unknown_environment_needs_input_without_api(self):
        (self.platform.mods / 'A.jar').write_bytes(jar_bytes('main_mod', depends={'minecraft': '>=1.20'}))
        state = self.plan()
        self.assertTrue(state['needsEnvironment'])
        self.assertEqual(state['status'], 'ready')
        self.assertEqual(self.platform.calls, [])

    def test_manual_environment_recovers_mods_directory(self):
        (self.platform.mods / 'A.jar').write_bytes(jar_bytes('main_mod', depends={'minecraft': '>=1.20'}))
        state = self.manager.start_plan(str(self.platform.mods), game_version='1.21.1', loader='Fabric')
        state = wait(self.manager, state['id'])
        self.assertFalse(state['needsEnvironment'])
        self.assertEqual(state['environment'], {'minecraft': '1.21.1', 'loader': 'Fabric', 'loaderVersion': ''})

    def test_exact_fixed_versions_conflict_blocks(self):
        self.platform.versions['AVersion']['dependencies'] = [{'project_id': 'B', 'version_id': 'BVersion', 'dependency_type': 'required'}, {'project_id': 'D', 'dependency_type': 'required'}]
        self.platform.add('D', 'another', dependencies=[{'project_id': 'B', 'version_id': 'BVersion2', 'dependency_type': 'required'}])
        self.platform.add('B', 'lib_b', dependencies=['C'], suffix='Version2')
        state = self.plan()
        self.assertEqual(next(i for i in state['items'] if i['id'] == 'Modrinth:B')['status'], 'blocked')
        with self.assertRaises(ValueError):
            self.manager.install(state['id'], ['Modrinth:D'])

    def test_forge_is_not_neoforge(self):
        self.platform.versions['BVersion']['loaders'] = ['neoforge']
        state = self.plan()
        self.assertEqual(state['items'][0]['status'], 'blocked')
        self.assertIn('加载器', state['items'][0]['reason'])

    def test_wrong_minecraft_blocked(self):
        self.platform.versions['BVersion']['game_versions'] = ['1.20.1']
        self.assertEqual(self.plan()['items'][0]['status'], 'blocked')

    def test_optional_and_embedded_are_not_downloaded(self):
        self.platform.versions['AVersion']['dependencies'] = [{'project_id': 'B', 'dependency_type': 'optional'}, {'project_id': 'C', 'dependency_type': 'embedded'}]
        self.assertEqual(self.plan()['items'], [])

    def test_cycles_terminate(self):
        self.platform.versions['CVersion']['dependencies'] = [{'project_id': 'B', 'dependency_type': 'required'}]
        state = self.plan()
        self.assertEqual(len(state['items']), 2)
        self.assertEqual(self.install(state)['status'], 'complete')

    def test_existing_disabled_project_not_duplicated(self):
        file = self.platform.versions['BVersion']['files'][0]
        (self.platform.mods / 'B.jar.disabled').write_bytes(self.platform.blobs[file['url']])
        state = self.plan()
        item = next(i for i in state['items'] if i['id'] == 'Modrinth:B')
        self.assertEqual(item['status'], 'blocked')
        self.assertIn('停用', item['reason'])

    def test_existing_fixed_version_mismatch_not_overwritten(self):
        old = self.platform.versions['BVersion']
        (self.platform.mods / 'B.jar').write_bytes(self.platform.blobs[old['files'][0]['url']])
        self.platform.versions['AVersion']['dependencies'][0]['version_id'] = 'DifferentVersion'
        state = self.plan()
        self.assertEqual(next(i for i in state['items'] if i['id'] == 'Modrinth:B')['status'], 'blocked')

    def test_platform_incompatible_blocks_both(self):
        self.platform.versions['CVersion']['dependencies'] = [{'project_id': 'B', 'dependency_type': 'incompatible'}]
        state = self.plan()
        self.assertEqual({i['status'] for i in state['items']}, {'blocked'})

    def test_download_hash_mismatch_leaves_directory_untouched(self):
        state = self.plan()
        self.platform.blobs[self.platform.versions['BVersion']['files'][0]['url']] = b'corrupt'
        after = self.install(state)
        self.assertEqual(after['status'], 'failed')
        self.assertEqual({p.name for p in self.platform.mods.iterdir()}, {'A.jar'})

    def test_metadata_id_mismatch_aborts_entire_batch(self):
        self.platform.add('B', 'not_lib_b', {}, [])
        state = self.plan()
        after = self.install(state)
        self.assertEqual(after['status'], 'failed')
        self.assertIn('lib_b', after['message'])
        self.assertEqual({p.name for p in self.platform.mods.iterdir()}, {'A.jar'})

    def test_metadata_unknown_range_does_not_assume_satisfied(self):
        blob = jar_bytes('lib_b', depends={'lib_c': 'unparseable-requirement'})
        self.platform.add('B', 'lib_b', dependencies=['C'], blob=blob)
        state = self.install(self.plan())
        self.assertEqual(state['status'], 'failed')
        self.assertIn('lib_c', state['message'])

    def test_local_version_ranges_are_verified(self):
        blob = jar_bytes('main_mod', depends={'lib_b': '>=2.0.0'})
        self.platform.add('A', 'main_mod', dependencies=['B'], local=True, blob=blob)
        state = self.install(self.plan())
        self.assertEqual(state['status'], 'failed')
        self.assertIn('lib_b', state['message'])

    def test_nested_and_alias_provider_satisfies_metadata(self):
        nested = jar_bytes('nested_library', aliases=['lib_c'])
        self.platform.add('B', 'lib_b', depends={'lib_c': '*'}, dependencies=[], blob=jar_bytes('lib_b', depends={'lib_c': '*'}, nested=nested))
        state = self.install(self.plan())
        self.assertEqual(state['status'], 'complete', state['message'])
        self.assertFalse((self.platform.mods / 'C.jar').exists())

    def test_changed_file_rejects_install(self):
        state = self.plan()
        (self.platform.mods / 'A.jar').write_bytes(b'changed')
        state = self.install(state)
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(self.platform.downloads, [])

    def test_changed_during_download_rejects_install(self):
        state = self.plan()
        self.platform.before_download = lambda *args: (self.platform.mods / 'A.jar').write_bytes(b'changed')
        state = self.install(state)
        self.assertEqual(state['status'], 'failed')
        self.assertFalse((self.platform.mods / 'B.jar').exists())

    def test_same_name_existing_not_overwritten(self):
        state = self.plan()
        (self.platform.mods / 'B.jar').write_bytes(b'keep')
        state = self.install(state)
        self.assertEqual(state['status'], 'failed')
        self.assertEqual((self.platform.mods / 'B.jar').read_bytes(), b'keep')

    def test_filename_and_host_and_missing_hash_block_plan(self):
        for mutate in (lambda f: f.update(filename='../bad.jar'), lambda f: f.update(url='https://evil.example/B.jar'), lambda f: f.update(hashes={})):
            with self.subTest(mutate=mutate):
                original = dict(self.platform.versions['BVersion']['files'][0])
                mutate(self.platform.versions['BVersion']['files'][0])
                state = self.plan()
                self.assertEqual(state['items'][0]['status'], 'blocked')
                self.platform.versions['BVersion']['files'][0] = original

    def test_cancel_download_cleans_staging(self):
        state = self.plan()
        self.platform.before_download = lambda url, dest, event: event.set()
        state = self.install(state)
        self.assertEqual(state['status'], 'cancelled')
        self.assertEqual({p.name for p in self.platform.mods.iterdir()}, {'A.jar'})

    def test_path_only_and_input_validation(self):
        for path in (str(self.platform.mods / 'A.jar'), '', str(self.root / 'missing.zip')):
            with self.assertRaises(ValueError):
                self.manager.start_plan(path)
        with self.assertRaises(ValueError):
            self.manager.start_plan(str(self.root), loader='quilt')
        with self.assertRaises(ValueError):
            self.manager.start_plan(str(self.root), game_version='latest')

    def test_no_url_can_be_supplied_to_install(self):
        state = self.plan()
        with self.assertRaises(ValueError):
            self.manager.install(state['id'], [{'id': 'Modrinth:B', 'url': 'https://evil.example/x'}])
        with self.assertRaises(ValueError):
            self.manager.install(state['id'], ['https://evil.example/x'])

    def test_symlink_or_junction_directory_rejected(self):
        link = self.root / 'alias'
        try:
            link.symlink_to(self.platform.mods, target_is_directory=True)
        except OSError:
            self.skipTest('系统未允许创建测试符号链接')
        with self.assertRaises(ValueError):
            self.manager.start_plan(str(link))

    def test_cf_missing_key_is_explicit_no_ai(self):
        self.platform.by_hash = {}
        state = self.plan()
        self.assertTrue(any('CF API Key' in x for x in state['notes']))
        self.assertTrue(any(x['target'] == 'lib_b' for x in state['unresolved']))
        self.assertEqual(state['items'], [])

    def test_no_sources_jar_or_wrong_side(self):
        self.platform.versions['BVersion']['files'][0]['file_type'] = 'sources-jar'
        self.assertEqual(self.plan()['items'][0]['status'], 'blocked')
        self.platform.versions['BVersion']['files'][0].pop('file_type')
        self.platform.versions['BVersion']['environment'] = 'server'
        self.assertEqual(self.plan()['items'][0]['status'], 'blocked')

    def test_official_cdn_redirect_guard(self):
        for value in ('http://cdn.modrinth.com/a.jar', 'https://cdn.modrinth.com.evil.test/a.jar', 'https://127.0.0.1/a.jar', 'https://cdn.modrinth.com:8443/a.jar', 'https://user@cdn.modrinth.com/a.jar'):
            self.assertFalse(pre.permitted_download(value))
        with self.assertRaises(ValueError):
            pre._DownloadRedirect().redirect_request(None, None, 302, 'Found', {}, 'https://evil.example/a.jar')

    def test_existing_unrelated_incompatibility_is_checked(self):
        (self.platform.mods / 'Unrelated.jar').write_bytes(jar_bytes('unrelated', breaks={'lib_c': '*'}))
        state = self.install(self.plan())
        self.assertEqual(state['status'], 'failed')
        self.assertIn('不兼容', state['message'])
        self.assertFalse((self.platform.mods / 'B.jar').exists())

    def test_addition_must_satisfy_existing_unrelated_version_constraint(self):
        (self.platform.mods / 'Unrelated.jar').write_bytes(jar_bytes('unrelated', depends={'lib_c': '>=9.0.0'}))
        state = self.install(self.plan())
        self.assertEqual(state['status'], 'failed')
        self.assertIn('lib_c', state['message'])

    def test_two_separate_installs_retain_provider_state(self):
        state = self.plan()
        self.manager.install(state['id'], ['Modrinth:C'])
        state = wait(self.manager, state['id'])
        self.assertEqual(state['status'], 'complete')
        state = self.install(state)
        self.assertEqual(state['status'], 'complete', state['message'])
        self.assertEqual(len(self.platform.downloads), 2)
        self.assertFalse(any(row['target'] == 'lib_b' for row in state['unresolved']))

    def test_manual_loader_version_and_quote_wrapped_path(self):
        self.platform.add('B', 'lib_b', dependencies=['C'], blob=jar_bytes('lib_b', depends={'lib_c': '*', 'fabricloader': '>=0.16.0'}))
        value = self.manager.start_plan('"' + str(self.root) + '"', loader_version='0.16.10')
        state = wait(self.manager, value['id'])
        self.assertEqual(state['environment']['loaderVersion'], '0.16.10')
        self.assertEqual(self.install(state)['status'], 'complete')

    def test_manual_environment_conflict_is_explicit(self):
        (self.root / 'mmc-pack.json').write_text(json.dumps({'components': [{'uid': 'net.minecraft', 'version': '1.21.1'}, {'uid': 'net.fabricmc.fabric-loader', 'version': '0.16.10'}]}))
        state = self.plan(loader_version='0.15.0')
        self.assertEqual(state['status'], 'failed')
        self.assertIn('实例配置不符', state['message'])
        self.assertEqual(self.platform.calls, [])

    def test_missing_specific_loader_version_blocks_install(self):
        self.platform.add('B', 'lib_b', dependencies=['C'], blob=jar_bytes('lib_b', depends={'lib_c': '*', 'fabricloader': '>=0.16.0'}))
        state = self.install(self.plan())
        self.assertEqual(state['status'], 'failed')
        self.assertIn('fabricloader', state['message'])

    def test_fingerprint_matches_known_murmur2_vector(self):
        path = self.root / 'hashdata.bin'
        path.write_bytes(b'hello world')
        self.assertEqual(pre._fingerprint(path, threading.Event()), 2824650221)
        path.write_bytes(b'hello\r\n\t world')
        self.assertEqual(pre._fingerprint(path, threading.Event()), 2824650221)

    def test_cf_exact_fingerprint_and_recursive_required_flow(self):
        self.manager.close()
        self.manager = pre.PrerequisiteManager(lambda: 'CF-ONLY-TEST')
        self.platform.by_hash = {}
        files = {}
        for index, name in enumerate(('A', 'B', 'C'), 1):
            mr = self.platform.versions[name + 'Version']
            data = self.platform.blobs[mr['files'][0]['url']]
            url = 'https://edge.forgecdn.net/files/100/' + str(index) + '/' + name + '.jar'
            self.platform.blobs[url] = data
            files[str(index)] = {'id': index * 100, 'modId': index, 'fileName': name + '.jar', 'displayName': '构造 CF ' + name,
                                 'gameVersions': ['1.21.1', 'Fabric'], 'releaseType': 1, 'fileDate': '2026-10-20',
                                 'downloadUrl': url, 'fileLength': len(data), 'hashes': [{'algo': 1, 'value': hashlib.sha1(data).hexdigest()}],
                                 'dependencies': [{'modId': index + 1, 'relationType': 3}] if index < 3 else []}
        files['1']['fileFingerprint'] = pre._fingerprint(self.platform.mods / 'A.jar', threading.Event())
        old_api = self.platform.api

        def cf_api(url, key=None, payload=None):
            if not url.startswith(pre.CF):
                self.assertIsNone(key)
                return old_api(url, key, payload)
            self.assertEqual(key, 'CF-ONLY-TEST')
            if url == pre.CF + '/fingerprints':
                return {'data': {'exactMatches': [{'file': files['1']}], 'partialMatches': []}}
            bits = urlsplit(url).path.removeprefix('/v1/').split('/')
            if len(bits) == 2:
                return {'data': {'id': int(bits[1]), 'name': '构造 CF ' + bits[1], 'gameId': 432, 'classId': 6, 'slug': 'fake-' + bits[1], 'allowModDistribution': True}}
            return {'data': [files[bits[1]]]}

        with patch.object(pre, 'api_json', cf_api):
            state = self.plan()
            self.assertEqual({i['id'] for i in state['items']}, {'CurseForge:2', 'CurseForge:3'})
            # A user can update their key after planning; download must read it fresh.
            self.manager.cf_key_getter = lambda: 'CF-UPDATED-DOWNLOAD-KEY'
            with patch.object(pre, 'download_file', wraps=self.platform.download) as downloads:
                state = self.install(state, ['CurseForge:2'])
            self.assertEqual(downloads.call_count, 2)
            self.assertTrue(all(call.kwargs.get('cf_key') == 'CF-UPDATED-DOWNLOAD-KEY' for call in downloads.call_args_list))
            self.assertNotIn('CF-UPDATED-DOWNLOAD-KEY', json.dumps(state))
            self.assertEqual(state['status'], 'complete', state['message'])

    def test_real_download_stream_hash_and_length_validation(self):
        value = self.platform.versions['BVersion']['files'][0]
        data = self.platform.blobs[value['url']]

        class Response(io.BytesIO):
            headers = {'Content-Length': str(len(data))}

            def geturl(self):
                return value['url']

        class Opener:
            def open(self, request, timeout):
                return Response(data)

        with patch.object(pre, 'build_opener', return_value=Opener()):
            target = self.root / 'staged.jar'
            REAL_DOWNLOAD(value['url'], target, len(data), value['hashes'], threading.Event())
            self.assertEqual(target.read_bytes(), data)
            with self.assertRaises(ValueError):
                REAL_DOWNLOAD(value['url'], self.root / 'bad.jar', len(data), {'sha1': '0' * 40}, threading.Event())

    def test_concurrent_task_is_rejected(self):
        state = self.plan()
        gate = threading.Event()
        entered = threading.Event()
        original = self.platform.api

        def blocked_api(*args, **kwargs):
            entered.set()
            gate.wait(2)
            return original(*args, **kwargs)

        try:
            with patch.object(pre, 'api_json', blocked_api):
                other = self.manager.start_plan(str(self.root))
                self.assertTrue(entered.wait(1))
                with self.assertRaises(ValueError):
                    self.manager.install(state['id'], ['Modrinth:B'])
                self.manager.cancel(other['id'])
                gate.set()
                self.assertEqual(wait(self.manager, other['id'])['status'], 'cancelled')
        finally:
            gate.set()

    def test_declared_nested_file_hash_prevents_duplicate_platform_download(self):
        inner = jar_bytes('lib_b', depends={'lib_c': '*'})
        self.platform.add('B', 'lib_b', dependencies=['C'], blob=inner)
        self.platform.add('A', 'main_mod', dependencies=['B'], local=True,
                          blob=jar_bytes('main_mod', depends={'lib_b': '*'}, nested=inner))
        state = self.plan()
        self.assertEqual([i['id'] for i in state['items']], ['Modrinth:C'])
        state = self.install(state, ['Modrinth:C'])
        self.assertEqual(state['status'], 'complete', state['message'])
        self.assertFalse((self.platform.mods / 'B.jar').exists())

    def test_unresolvable_required_platform_relation_blocks_parent(self):
        self.platform.add('B', 'lib_b', depends={}, dependencies=[{'dependency_type': 'required', 'file_name': 'unknown.jar'}])
        state = self.plan()
        self.assertEqual(state['items'][0]['status'], 'blocked')
        with self.assertRaises(ValueError):
            self.manager.install(state['id'], ['Modrinth:B'])

    def test_unresolvable_fixed_platform_version_blocks_parent(self):
        self.platform.add('B', 'lib_b', depends={}, dependencies=[{'dependency_type': 'required', 'version_id': 'UnknownVersion'}])
        old_api = self.platform.api

        def api(*args, **kwargs):
            if args[0] == pre.MR + '/version/UnknownVersion':
                raise ValueError('版本不可用')
            return old_api(*args, **kwargs)

        with patch.object(pre, 'api_json', api):
            state = self.plan()
            self.assertEqual(state['items'][0]['status'], 'blocked')

    def test_new_item_count_limit_blocks_required_parent(self):
        with patch.object(pre, 'MAX_NEW', 1):
            state = self.plan()
        self.assertEqual(state['items'][0]['status'], 'blocked')

    def test_declared_specific_loader_and_mc_are_checked_before_commit(self):
        self.platform.add('B', 'lib_b', depends={}, dependencies=[], blob=jar_bytes('lib_b', depends={'minecraft': '1.20.1'}))
        state = self.install(self.plan())
        self.assertEqual(state['status'], 'failed')
        self.assertIn('minecraft', state['message'])

    def test_forge_and_neoforge_both_explicitly_supported_is_valid(self):
        job = {'environment': {'minecraft': '1.21.1', 'loader': 'neoforge'}, 'side': 'client'}
        self.assertTrue(self.manager._compatible(job, {'gameVersions': ['1.21.1', 'NeoForge', 'Forge']}, 'CurseForge'))
        self.assertFalse(self.manager._compatible(job, {'gameVersions': ['1.21.1', 'Forge']}, 'CurseForge'))

    def test_modrinth_new_environment_values_are_side_aware(self):
        job = {'environment': {'minecraft': '1.21.1', 'loader': 'forge'}, 'side': 'server'}
        version = {'game_versions': ['1.21.1'], 'loaders': ['forge']}
        for side in ('client_only', 'singleplayer_only', 'unknown', 'future-enum'):
            self.assertFalse(self.manager._compatible(job, {**version, 'environment': side}, 'Modrinth'))
        for side in ('server_only', 'client_and_server', 'dedicated_server_only', 'server_only_client_optional', 'client_only_server_optional', 'client_or_server', 'client_or_server_prefers_both'):
            self.assertTrue(self.manager._compatible(job, {**version, 'environment': side}, 'Modrinth'))
        job['side'] = 'client'
        self.assertFalse(self.manager._compatible(job, {**version, 'environment': 'dedicated_server_only'}, 'Modrinth'))
        for side in ('server_only', 'client_only', 'singleplayer_only'):
            self.assertTrue(self.manager._compatible(job, {**version, 'environment': side}, 'Modrinth'))

    def test_environment_json_changed_after_plan_blocks_install(self):
        state = self.plan()
        (self.root / 'mmc-pack.json').write_text('{"components":[]}')
        state = self.install(state)
        self.assertEqual(state['status'], 'failed')
        self.assertIn('版本配置已变化', state['message'])
        self.assertEqual(self.platform.downloads, [])

    def test_cancel_during_commit_preserves_dependency_first(self):
        state = self.plan()
        original_commit = pre._commit_file

        def commit(source, target):
            original_commit(source, target)
            self.manager.jobs[state['id']]['cancel'].set()

        with patch.object(pre, '_commit_file', commit):
            state = self.install(state)
        self.assertEqual(state['status'], 'cancelled')
        self.assertTrue((self.platform.mods / 'C.jar').exists())
        self.assertFalse((self.platform.mods / 'B.jar').exists())
        self.assertEqual(next(row['status'] for row in state['items'] if row['id'] == 'Modrinth:C'), 'installed')

    def test_cancel_during_cycle_commit_finishes_cycle(self):
        self.platform.versions['CVersion']['dependencies'] = [{'project_id': 'B', 'dependency_type': 'required'}]
        state = self.plan()
        original_commit = pre._commit_file

        def commit(source, target):
            original_commit(source, target)
            self.manager.jobs[state['id']]['cancel'].set()

        with patch.object(pre, '_commit_file', commit):
            state = self.install(state)
        self.assertEqual(state['status'], 'complete')
        self.assertEqual({row['status'] for row in state['items']}, {'installed'})

    def test_windows_install_does_not_require_hardlink_support(self):
        state = self.plan()
        original_rename = pre.os.rename
        with patch.object(pre, 'WINDOWS', True), patch.object(pre.os, 'link', side_effect=OSError(1, 'hard links unsupported')) as link, patch.object(pre.os, 'rename', wraps=original_rename) as rename:
            state = self.install(state)
        self.assertEqual(state['status'], 'complete', state['message'])
        self.assertEqual(link.call_count, 0)
        self.assertEqual(rename.call_count, 2)
        for call in rename.call_args_list:
            source, target = map(Path, call.args)
            self.assertEqual(source.parent.parent, self.platform.mods)
            self.assertEqual(target.parent, self.platform.mods)
        self.assertEqual({p.name for p in self.platform.mods.iterdir()}, {'A.jar', 'B.jar', 'C.jar'})

    @unittest.skipUnless(pre.WINDOWS, 'Windows rename no-clobber semantics')
    def test_windows_atomic_rename_does_not_replace_existing_destination(self):
        source, target = self.root / 'temporary.jar', self.root / 'keep.jar'
        source.write_bytes(b'new validated bytes')
        target.write_bytes(b'existing user file')
        with self.assertRaises(FileExistsError):
            pre._commit_file(source, target)
        self.assertEqual(source.read_bytes(), b'new validated bytes')
        self.assertEqual(target.read_bytes(), b'existing user file')

    def test_destination_created_at_commit_is_never_overwritten(self):
        state = self.plan()
        original_commit = pre._commit_file

        def race(source, target):
            Path(target).write_bytes(b'user file created during download')
            original_commit(source, target)

        with patch.object(pre, '_commit_file', race):
            state = self.install(state)
        self.assertEqual(state['status'], 'failed')
        self.assertEqual((self.platform.mods / 'C.jar').read_bytes(), b'user file created during download')
        self.assertFalse((self.platform.mods / 'B.jar').exists())
        self.assertFalse(any(p.name.startswith('.damn-prerequisites-') for p in self.platform.mods.iterdir()))

    def test_posix_commit_keeps_atomic_link_and_never_uses_rename(self):
        source, target = self.root / 'temporary.jar', self.root / 'final.jar'
        with patch.object(pre, 'WINDOWS', False), patch.object(pre.os, 'link') as link, patch.object(pre.os, 'rename', side_effect=AssertionError('POSIX rename could replace destination')):
            pre._commit_file(source, target)
        link.assert_called_once_with(source, target)

    def test_cf_cdn_download_authenticates_only_with_request_header(self):
        data = b'fixture authenticated download bytes'
        hashes = {'sha1': hashlib.sha1(data).hexdigest()}
        captured = []

        class Response(io.BytesIO):
            headers = {'Content-Length': str(len(data))}

            def __init__(self, url):
                super().__init__(data)
                self.url = url

            def geturl(self):
                return self.url

        class Opener:
            def open(self, request, timeout):
                captured.append(request)
                return Response(request.full_url)

        with patch.object(pre, 'build_opener', return_value=Opener()):
            for index, host in enumerate(sorted(pre.CF_CDN_HOSTS)):
                url = 'https://' + host + '/files/123/456/test.jar'
                REAL_DOWNLOAD(url, self.root / ('authenticated-' + str(index) + '.jar'), len(data), hashes, threading.Event(), cf_key='FAKE-CF-DOWNLOAD-KEY')
        self.assertEqual(len(captured), len(pre.CF_CDN_HOSTS))
        for request in captured:
            self.assertEqual({key.lower(): value for key, value in request.header_items()}['x-api-key'], 'FAKE-CF-DOWNLOAD-KEY')
            self.assertNotIn('FAKE-CF-DOWNLOAD-KEY', request.full_url)
            self.assertNotIn('api-key=', request.full_url)

    def test_modrinth_download_never_receives_supplied_cf_key(self):
        value = self.platform.versions['BVersion']['files'][0]
        data = self.platform.blobs[value['url']]
        captured = []

        class Response(io.BytesIO):
            headers = {'Content-Length': str(len(data))}

            def geturl(self):
                return value['url']

        class Opener:
            def open(self, request, timeout):
                captured.append(request)
                return Response(data)

        with patch.object(pre, 'build_opener', return_value=Opener()):
            REAL_DOWNLOAD(value['url'], self.root / 'modrinth-clean.jar', len(data), value['hashes'], threading.Event(), cf_key='FAKE-CF-PRIVATE-KEY')
        self.assertFalse(any(key.lower() == 'x-api-key' for key, _ in captured[0].header_items()))
        self.assertNotIn('FAKE-CF-PRIVATE-KEY', captured[0].full_url)

    def test_cf_authenticated_redirect_keeps_key_only_inside_cf_cdn(self):
        request = pre.Request('https://edge.forgecdn.net/files/1/2/a.jar', headers={'x-api-key': 'FAKE-CF-KEY'})
        redirect = pre._DownloadRedirect()
        next_request = redirect.redirect_request(request, None, 302, 'Found', {}, 'https://mediafilez.forgecdn.net/files/1/2/a.jar')
        self.assertEqual({key.lower(): value for key, value in next_request.header_items()}['x-api-key'], 'FAKE-CF-KEY')
        for url in ('https://cdn.modrinth.com/data/a.jar', 'https://evil.example/a.jar', 'https://edge.forgecdn.net.evil.example/a.jar', 'http://edge.forgecdn.net/a.jar'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                redirect.redirect_request(request, None, 302, 'Found', {}, url)

    def test_cf_unredirected_auth_header_cannot_leak_on_cross_site_redirect(self):
        request = pre.Request('https://edge.forgecdn.net/files/1/2/a.jar')
        request.add_unredirected_header('X-Api-Key', 'FAKE-CF-KEY')
        with self.assertRaises(ValueError):
            pre._DownloadRedirect().redirect_request(request, None, 302, 'Found', {}, 'https://cdn.modrinth.com/data/a.jar')

    def test_cf_cdn_401_has_actionable_message_without_secret(self):
        url = 'https://edge.forgecdn.net/files/1/2/a.jar'

        class Opener:
            def open(self, request, timeout):
                raise pre.HTTPError(url, 401, 'Unauthorized', {}, None)

        with patch.object(pre, 'build_opener', return_value=Opener()):
            for key in (None, 'FAKE-SECRET-KEY'):
                with self.assertRaisesRegex(ValueError, '独立 CF API Key') as caught:
                    REAL_DOWNLOAD(url, self.root / 'must-not-exist.jar', 1, {'sha1': '0' * 40}, threading.Event(), cf_key=key)
                self.assertIn('HTTP 401', str(caught.exception))
                self.assertNotIn('FAKE-SECRET-KEY', str(caught.exception))
                self.assertFalse((self.root / 'must-not-exist.jar').exists())

    def test_invalid_cf_header_value_is_rejected_without_exposing_key(self):
        with patch.object(pre, 'build_opener') as opener:
            for key in ('FAKE-SECRET\r\nInjected: bad', 'FAKE-SECRET 非ASCII'):
                with self.assertRaisesRegex(ValueError, 'CF API Key 格式无效') as caught:
                    REAL_DOWNLOAD('https://edge.forgecdn.net/files/1/2/a.jar', self.root / 'bad-key.jar', 1, {'sha1': '0' * 40}, threading.Event(), cf_key=key)
                self.assertNotIn('FAKE-SECRET', str(caught.exception))
            opener.assert_not_called()


if __name__ == '__main__':
    unittest.main()
