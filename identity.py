"""Official file identity and explicitly confirmed project attribution, without AI.

User attribution is keyed by SHA256 and metadata signature. It is never an exact
file/version identity and must not be used as permission for prerequisite installs.
"""
import atexit
import concurrent.futures
import copy
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from app_info import USER_DATA_SUBDIRECTORY
from urllib.parse import quote, urlencode, urlsplit

import research

MR = 'https://api.modrinth.com/v2'
CF = 'https://api.curseforge.com/v1'
MCIM_MR = 'https://mod.mcimirror.top/modrinth/v2'
MCIM_CF = 'https://mod.mcimirror.top/curseforge/v1'
MAX_MODS = 3000
MAX_CANDIDATES = 6
MAX_ENTRIES = 5000
STORE_LOCK = threading.Lock()
STORE_LOCKS = {}


def curseforge_fingerprint(data: bytes):
    """CurseForge's whitespace-stripped MurmurHash2 with seed 1."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('指纹输入必须为 bytes / bytearray。')
    data = data.translate(None, b'\x09\x0a\x0d\x20')
    value, mask = 1 ^ len(data), 0xffffffff
    limit = len(data) // 4 * 4
    words = memoryview(data)[:limit].cast('I') if sys.byteorder == 'little' else (int.from_bytes(data[offset:offset + 4], 'little') for offset in range(0, limit, 4))
    for part in words:
        part = part * 0x5bd1e995 & mask
        part ^= part >> 24
        part = part * 0x5bd1e995 & mask
        value = ((value * 0x5bd1e995) ^ part) & mask
    if data[limit:]:
        value ^= int.from_bytes(data[limit:], 'little')
        value = value * 0x5bd1e995 & mask
    value ^= value >> 13
    value = value * 0x5bd1e995 & mask
    return (value ^ (value >> 15)) & mask


def _text(value, maximum=200):
    return re.sub(r'[\x00-\x1f\x7f]', ' ', str(value or '')).strip()[:maximum]


def _signature(mod):
    values = []
    for item in mod.get('components') or []:
        if isinstance(item, dict):
            values.append({'id': _text(item.get('id'), 128), 'version': _text(item.get('version'), 128),
                           'nested': bool(item.get('nested')), 'aliases': sorted(_text(x, 128) for x in item.get('aliases') or [] if isinstance(x, str))})
    return hashlib.sha256(json.dumps(sorted(values, key=lambda x: (x['id'], x['version'], x['nested'])), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _plain(path):
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('来源映射路径包含链接，不能读写。')
    return path


def _project_id(value, site):
    value = str(value or '')
    return value if re.fullmatch(r'[A-Za-z0-9_-]{1,100}' if site == 'Modrinth' else r'\d{1,15}', value) else ''


def _project(site, data):
    if not isinstance(data, dict):
        return None
    ident = _project_id(data.get('id') or data.get('project_id'), site)
    if not ident:
        return None
    if site == 'Modrinth':
        if data.get('project_type', 'mod') != 'mod':
            return None
        loaders = set(data.get('loaders') or []) | (set(data.get('categories') or []) & {'fabric', 'forge', 'neoforge', 'quilt'})
        versions = [str(v) for v in data.get('versions') or [] if isinstance(v, str) and re.fullmatch(r'\d+\.\d+(?:\.\d+)?', v)]
        name = data.get('title')
        summary = data.get('description')
        url = 'https://modrinth.com/mod/' + quote(ident, safe='')
    else:
        if data.get('gameId') != 432 or data.get('classId') != 6:
            return None
        indexes = data.get('latestFilesIndexes') or []
        loader_names = {1: 'forge', 4: 'fabric', 5: 'quilt', 6: 'neoforge'}
        loaders = {loader_names[x['modLoader']] for x in indexes if isinstance(x, dict) and x.get('modLoader') in loader_names}
        versions = [str(x['gameVersion']) for x in indexes if isinstance(x, dict) and x.get('gameVersion')]
        slug = str(data.get('slug') or '')
        url = 'https://www.curseforge.com/minecraft/mc-mods/' + quote(slug, safe='') if re.fullmatch(r'[A-Za-z0-9_-]{1,150}', slug) else 'https://www.curseforge.com/projects/' + ident
        name, summary = data.get('name'), data.get('summary')
    return {'site': site, 'projectId': ident, 'name': _text(name or ident), 'url': url,
            'summary': _text(summary, 500), 'loaders': sorted(_text(x, 40) for x in loaders if isinstance(x, str)),
            'versionHint': '适用 MC：' + '、'.join(list(dict.fromkeys(versions))[-5:]) if versions else ''}


def _search_hints(mod):
    """Bounded search clues from top-level metadata; none verifies file identity."""
    components = [value for value in mod.get('components') or [] if isinstance(value, dict) and not value.get('nested')]
    hints, seen = [], set()

    def add(value, source):
        value = _text(value, 500 if _project_target(value) else 120)
        normalized = re.sub(r'\s+', ' ', value).casefold()
        if len(value) >= 2 and not re.fullmatch(r'[\d\W_]+|[0-9a-f]{24,}', value, re.I) and normalized not in seen:
            seen.add(normalized)
            hints.append({'query': value, 'source': source})

    for component in components:
        add(component.get('id'), '本地组件 ID')
    add(research.query_for(mod), '本地显示名称')
    for component in components:
        add(component.get('name'), '本地组件名称')
    for component in components:
        for url in component.get('projectUrls') or []:
            if not isinstance(url, str):
                continue
            target = _project_target(url)
            if target:
                add(url, '文件声明的项目链接')
            else:
                try:
                    parsed = urlsplit(url)
                    parts = parsed.path.strip('/').split('/')
                    if parsed.scheme == 'https' and parsed.hostname in ('github.com', 'www.github.com', 'gitlab.com') and len(parts) >= 2:
                        add(re.sub(r'[-_]+', ' ', parts[1].removesuffix('.git')), '文件声明的源码仓库名')
                except ValueError:
                    pass
    for component in components:
        ident = str(component.get('id') or '')
        if re.search(r'[_-]', ident):
            add(re.sub(r'[_-]+', ' ', ident), '本地组件 ID 分词')
    return hints[:8]


def _queries(mod):
    return [hint['query'] for hint in _search_hints(mod)][:4]


def _local_metadata(mod):
    components = [value for value in mod.get('components') or [] if isinstance(value, dict) and not value.get('nested')]
    def values(field):
        result = []
        for component in components:
            items = [component.get(field)] if field == 'id' else component.get(field) or []
            for value in items if isinstance(items, list) else []:
                if isinstance(value, str) and value and value not in result:
                    result.append(_text(value, 500 if field == 'projectUrls' else 128))
        return result[:20]
    return {'componentIds': values('id'), 'authors': values('authors'), 'projectUrls': values('projectUrls')}


def _project_target(value):
    """Parse known project pages, never follow arbitrary URLs from a JAR/user."""
    try:
        parsed = urlsplit(str(value))
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        if parsed.hostname in ('modrinth.com', 'www.modrinth.com'):
            match = re.fullmatch(r'/mod/([A-Za-z0-9_-]{1,100})/?', parsed.path)
            return ('Modrinth', match[1], 'id') if match else None
        if parsed.hostname in ('curseforge.com', 'www.curseforge.com'):
            match = re.fullmatch(r'/projects/(\d{1,15})/?', parsed.path)
            if match:
                return ('CurseForge', match[1], 'id')
            match = re.fullmatch(r'/minecraft/mc-mods/([A-Za-z0-9_-]{1,150})/?', parsed.path)
            return ('CurseForge', match[1], 'slug') if match else None
    except ValueError:
        pass
    return None


class _Cancelled(Exception):
    pass


class IdentityManager:
    def __init__(self, directory, cf_key_getter=lambda: ''):
        self.directory = _plain(directory)
        if not self.directory.is_dir():
            raise ValueError('来源映射基目录不存在。')
        self.store = self.directory / USER_DATA_SUBDIRECTORY / 'identity-map.json'
        self.cf_key_getter = cf_key_getter
        self.lock = threading.RLock()
        with STORE_LOCK:
            self.store_lock = STORE_LOCKS.setdefault(str(self.store).casefold(), threading.Lock())
        self.jobs, self.closed = {}, False
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix='DAMN-identity')
        self.records, self.store_note = {}, ''
        try:
            self.records = self._read_store()
        except (OSError, ValueError, TypeError) as error:
            self.store_note = '来源映射无法读取，原文件保留：' + _text(error, 250)
        atexit.register(self.close)

    def _read_store(self):
        _plain(self.store)
        if not self.store.exists():
            return {}
        if self.store.stat().st_size > 4_000_000:
            raise ValueError('来源映射文件过大。')
        data = json.loads(self.store.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('entries'), dict):
            raise ValueError('来源映射格式不支持。')
        result = {}
        for sha, value in data['entries'].items():
            if not re.fullmatch(r'[a-f0-9]{64}', sha) or not isinstance(value, dict):
                continue
            site = value.get('site')
            if site not in ('Modrinth', 'CurseForge') or not _project_id(value.get('projectId'), site):
                continue
            if not re.fullmatch(r'[a-f0-9]{64}', str(value.get('componentsSignature', ''))):
                continue
            # Rebuild URLs from validated project IDs; a local map cannot inject URLs.
            ident = _project_id(value['projectId'], site)
            url = 'https://modrinth.com/mod/' + ident if site == 'Modrinth' else 'https://www.curseforge.com/projects/' + ident
            result[sha] = {'sha256': sha, 'site': site, 'projectId': ident, 'name': _text(value.get('name') or ident),
                           'url': url, 'componentsSignature': value['componentsSignature'],
                           'userConfirmedAt': _text(value.get('userConfirmedAt'), 60)}
            if value.get('provider') == 'MCIM':
                result[sha]['provider'] = 'MCIM'
        return result

    def _persist(self, sha, value):
        with self.store_lock:
            data = self._read_store()
            if value is None:
                data.pop(sha, None)
            else:
                data[sha] = value
            if len(data) > MAX_ENTRIES:
                data = dict(sorted(data.items(), key=lambda x: x[1].get('userConfirmedAt', ''), reverse=True)[:MAX_ENTRIES])
            folder = _plain(self.store.parent)
            folder.mkdir(exist_ok=True)
            _plain(self.store)
            temp = None
            try:
                descriptor, temp = tempfile.mkstemp(prefix='identity-', suffix='.tmp', dir=folder)
                with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                    json.dump({'schema': 1, 'entries': data}, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                _plain(self.store)
                os.replace(temp, self.store)
                self.records = data
            finally:
                if temp and Path(temp).exists():
                    Path(temp).unlink()

    def _check(self, job):
        if self.closed or job['cancel'].is_set():
            raise _Cancelled()
        if time.monotonic() > job['deadline']:
            raise ValueError('本次来源检索达到时间上限，尚未完成的项目可稍后重试。')

    def _api(self, job, url, key=None, payload=None):
        self._check(job)
        token = research.FETCH_DEADLINE.set(min(job['deadline'], time.monotonic() + 12))
        try:
            result = json.loads(research.fetch(url, key, payload))
            self._check(job)
            return result
        finally:
            research.FETCH_DEADLINE.reset(token)

    def _public(self, job):
        return copy.deepcopy(job['state'])

    def _sync(self, job):
        state = job['state']
        if job['cancel'].is_set():
            state.update(status='cancelled', phase='cancelled', message='来源核对已取消。')
            for item in state['items']:
                item['searching'] = False
                if item['status'] == 'checking':
                    item.update(status='error', label='查询已取消 · 来源待确认')
        elif job['auto_active'] or job['searches']:
            state.update(status='running', phase='searching' if job['searches'] else 'hash_lookup', message='正在搜索官方项目候选。' if job['searches'] else '正在核对官方文件来源。')
        else:
            state.update(status='complete', phase='complete', message='来源核对已完成；候选项目需由你确认。')

    def _submit(self, job, function, *args):
        future = self.pool.submit(function, job, *args)
        job['futures'].add(future)
        future.add_done_callback(lambda f: job['futures'].discard(f))

    def _item(self, job, key):
        if key not in job['mods']:
            raise ValueError('该模组不在本次来源核对中。')
        return next(item for item in job['state']['items'] if item['key'] == key)

    def _job(self, ident):
        if self.closed or ident not in self.jobs:
            raise ValueError('来源核对不存在或已过期，请重新核对。')
        return self.jobs[ident]

    def start(self, mods):
        if not isinstance(mods, list) or not mods or len(mods) > MAX_MODS:
            raise ValueError('每次来源核对需要 1–3000 个模组。')
        selected, keys = [], set()
        for mod in mods:
            if not isinstance(mod, dict):
                raise ValueError('模组资料格式错误。')
            if mod.get('kind') == 'manifest' or not str(mod.get('file', '')).lower().endswith(('.jar', '.jar.disabled')):
                continue
            if not re.fullmatch(r'[a-fA-F0-9]{40}', str(mod.get('sha1', ''))) or not re.fullmatch(r'[a-fA-F0-9]{64}', str(mod.get('sha256', ''))):
                continue
            key = mod.get('key')
            if not isinstance(key, str) or not 0 < len(key) <= 200 or key in keys:
                raise ValueError('模组标识缺失或重复。')
            if not isinstance(mod.get('components') or [], list) or len(mod.get('components') or []) > 500:
                raise ValueError('模组组件数量超出上限。')
            keys.add(key)
            normalized = {name: copy.deepcopy(mod.get(name)) for name in ('key', 'name', 'file', 'sha1', 'sha256', 'version', 'loader', 'components', 'cfFingerprint')}
            normalized.update(sha1=mod['sha1'].lower(), sha256=mod['sha256'].lower(), name=_text(mod.get('name') or mod['file']), file=_text(mod['file'], 500))
            selected.append(normalized)
        with self.lock:
            if self.closed:
                raise ValueError('来源核对服务已关闭。')
            for previous in self.jobs.values():
                if previous['state']['status'] == 'running':
                    previous['cancel'].set()
                    self._sync(previous)
            ident = secrets.token_hex(16)
            job = {'cancel': threading.Event(), 'deadline': time.monotonic() + 1200, 'epochs': defaultdict_int(),
                   'auto_epochs': {mod['key']: 0 for mod in selected},
                   'mods': {mod['key']: mod for mod in selected}, 'candidates': {}, 'searches': set(), 'futures': set(), 'auto_active': bool(selected),
                   'state': {'id': ident, 'status': 'running' if selected else 'complete', 'phase': 'hash_lookup' if selected else 'complete',
                             'message': '正在核对官方文件来源。' if selected else '没有可读取哈希的实际 JAR；下载清单项已跳过。',
                             'progress': {'done': 0, 'total': len(selected)}, 'items': [], 'notes': [self.store_note] if self.store_note else [], 'aiCalls': 0}}
            for mod in selected:
                confirmation = self.records.get(mod['sha256'])
                if confirmation and confirmation['componentsSignature'] != _signature(mod):
                    confirmation = None
                job['state']['items'].append({'key': mod['key'], 'name': mod['name'], 'file': mod['file'], 'sha256': mod['sha256'],
                                             'status': 'confirmed' if confirmation else 'checking', 'label': '已确认原项目' if confirmation else '正在核对',
                                             'notes': ['此项目归属由用户确认，不代表官方原版文件或精确版本，也不用于自动补全前置。'] if confirmation else [],
                                             'checks': {}, 'exact': None, 'confirmation': self._confirmation(confirmation),
                                             'candidates': [], 'searching': False, 'query': (_queries(mod) or [''])[0],
                                             'searchHints': _search_hints(mod), 'searchChecks': [], 'localMetadata': _local_metadata(mod)})
            self.jobs[ident] = job
            while len(self.jobs) > 8:
                old = next(key for key in self.jobs if key != ident)
                self.jobs[old]['cancel'].set()
                del self.jobs[old]
            result = self._public(job)
            if selected:
                self._submit(job, self._run)
            return result

    def status(self, ident):
        with self.lock:
            return self._public(self._job(ident))

    @staticmethod
    def _confirmation(record):
        return {key: record[key] for key in ('site', 'projectId', 'name', 'url', 'userConfirmedAt', 'provider') if key in record} if record else None

    def _exact(self, job, site, version):
        project_id = _project_id(version.get('project_id' if site == 'Modrinth' else 'modId'), site)
        if not project_id:
            raise ValueError('平台没有返回有效项目 ID。')
        key = None if site == 'Modrinth' else self.cf_key_getter() or ''
        data = self._api(job, MR + '/project/' + project_id) if site == 'Modrinth' else (self._api(job, CF + '/mods/' + project_id, key).get('data') or {})
        project = _project(site, data)
        if not project or project['projectId'] != project_id:
            raise ValueError('平台项目身份无法核对。')
        return {**project, 'versionId': _text(version.get('id'), 100),
                'version': _text(version.get('version_number' if site == 'Modrinth' else 'displayName'), 200), 'verifiedBy': 'sha1'}

    def _run(self, job):
        try:
            with self.lock:
                epochs = job['auto_epochs']
                pending = [mod for mod in job['mods'].values() if not self._item(job, mod['key'])['confirmation']]
            versions, checks = {}, {mod['key']: {} for mod in pending}
            for offset in range(0, len(pending), 80):
                batch = pending[offset:offset + 80]
                try:
                    values = self._api(job, MR + '/version_files', payload={'hashes': [m['sha1'] for m in batch], 'algorithm': 'sha1'})
                    requested = {m['sha1'] for m in batch}
                    if not isinstance(values, dict) or any(not isinstance(sha, str) or sha not in requested for sha in values):
                        raise ValueError('平台文件匹配响应格式错误。')
                    for mod in batch:
                        version = values.get(mod['sha1'])
                        if mod['sha1'] in values and (not isinstance(version, dict) or not _project_id(version.get('project_id'), 'Modrinth') or not version.get('id') or not isinstance(version.get('files'), list)):
                            checks[mod['key']]['Modrinth'] = {'status': 'error', 'message': '平台返回的版本结构不完整，不能判断文件是否收录。'}
                            continue
                        matched = isinstance(version, dict) and any(str((file.get('hashes') or {}).get('sha1', '')).lower() == mod['sha1'] for file in version.get('files') or [] if isinstance(file, dict))
                        if mod['sha1'] in values and not matched:
                            checks[mod['key']]['Modrinth'] = {'status': 'error', 'message': '平台返回的文件 SHA1 与查询不符，未作为来源证据。'}
                            continue
                        checks[mod['key']]['Modrinth'] = {'status': 'matched' if matched else 'not_found', 'message': '文件 SHA1 精确匹配。' if matched else '没有查到相同 SHA1；可能未收录、重新打包或修改过。'}
                        if matched:
                            versions[mod['key']] = ('Modrinth', version)
                except ValueError as error:
                    for mod in batch:
                        checks[mod['key']]['Modrinth'] = {'status': 'error', 'message': '文件匹配未完成：' + _text(error, 200)}
            key = self.cf_key_getter() or ''
            remaining = [mod for mod in pending if mod['key'] not in versions]
            fingerprintable = []
            for mod in remaining:
                fp = mod.get('cfFingerprint')
                if not key:
                    checks[mod['key']]['CurseForge'] = {'status': 'skipped', 'message': 'CurseForge 官方文件查询服务未配置，本次未核对该平台。'}
                elif isinstance(fp, int) and not isinstance(fp, bool) and 0 <= fp <= 0xffffffff:
                    fingerprintable.append(mod)
                else:
                    checks[mod['key']]['CurseForge'] = {'status': 'skipped', 'message': '未提供 CF 文件指纹，未核对该站文件；大文件可能跳过指纹计算。'}
            for offset in range(0, len(fingerprintable), 60):
                batch = fingerprintable[offset:offset + 60]
                try:
                    response = self._api(job, CF + '/fingerprints/432', key, {'fingerprints': list({m['cfFingerprint'] for m in batch})})
                    if not isinstance(response, dict) or not isinstance(response.get('data'), dict) or not isinstance(response['data'].get('exactMatches'), list):
                        raise ValueError('平台指纹响应格式错误，无法核对文件。')
                    values = response['data']
                    for mod in batch:
                        found = None
                        for match in values.get('exactMatches') or []:
                            file = match.get('file') or {}
                            sha1 = next((str(h.get('value', '')).lower() for h in file.get('hashes') or [] if isinstance(h, dict) and h.get('algo') == 1), '')
                            if file.get('fileFingerprint') == mod['cfFingerprint'] and sha1 == mod['sha1'] and (not match.get('id') or str(match['id']) == str(file.get('modId'))):
                                found = file
                                break
                        checks[mod['key']]['CurseForge'] = {'status': 'matched' if found else 'not_found', 'message': '精确指纹及 SHA1 均匹配。' if found else '没有查到指纹及 SHA1 均相符的官方文件。'}
                        if found:
                            versions[mod['key']] = ('CurseForge', found)
                except ValueError as error:
                    for mod in batch:
                        checks[mod['key']]['CurseForge'] = {'status': 'error', 'message': '文件匹配未完成：' + _text(error, 200)}
            for index, mod in enumerate(job['mods'].values()):
                self._check(job)
                key = mod['key']
                with self.lock:
                    epoch = epochs[key]
                    item = self._item(job, key)
                    already_confirmed = bool(item['confirmation']) or job['epochs'][key] != epoch
                if not already_confirmed:
                    exact, notes, candidates, search_checks = None, [], [], []
                    item_checks = checks.get(key, {})
                    if key in versions:
                        try:
                            exact = self._exact(job, *versions[key])
                        except ValueError as error:
                            notes.append('文件已匹配，但项目资料未能核对：' + _text(error, 200))
                    if not exact:
                        for query in _queries(mod):
                            values, extra, checked = self._find(job, query, 'all')
                            candidates.extend(values)
                            notes.extend(extra)
                            search_checks.extend(checked)
                            if len(candidates) >= MAX_CANDIDATES:
                                break
                    with self.lock:
                        if job['epochs'][key] == epoch and not job['cancel'].is_set() and not self._item(job, key)['confirmation']:
                            item = self._item(job, key)
                            item.update(checks=item_checks, exact=exact, notes=list(dict.fromkeys(notes)), searchChecks=search_checks)
                            self._candidates(job, key, candidates)
                            self._derive(item)
                with self.lock:
                    job['state']['progress']['done'] = index + 1
        except _Cancelled:
            pass
        except Exception as error:
            with self.lock:
                job['state']['notes'].append('部分来源未查完：' + _text(error, 300))
                for item in job['state']['items']:
                    if item['status'] == 'checking':
                        item.update(status='error', label='查询未完成 · 可重试')
        finally:
            with self.lock:
                job['auto_active'] = False
                self._sync(job)

    def _find(self, job, query, site):
        candidates, notes, checks = [], [], []
        target = _project_target(query)
        mirrored = site == 'mcim'
        platforms = ['Modrinth', 'CurseForge'] if site in ('all', 'mcim') else ['Modrinth' if site == 'modrinth' else 'CurseForge']
        if target:
            platforms = [value for value in platforms if value == target[0]]
        for platform in platforms:
            key = None if platform == 'Modrinth' or mirrored else self.cf_key_getter() or ''
            check = {'site': platform, 'query': query, 'provider': 'MCIM' if mirrored else platform}
            if platform == 'CurseForge' and not mirrored and not key:
                message = 'CurseForge 官方查询服务未配置，本次未搜索该平台；不能据此判断项目不存在。'
                notes.append(message)
                checks.append({**check, 'status': 'skipped', 'message': message})
                continue
            base = (MCIM_MR if mirrored else MR) if platform == 'Modrinth' else (MCIM_CF if mirrored else CF)
            try:
                if target and target[2] == 'id':
                    endpoint = '/project/' if platform == 'Modrinth' else '/mods/'
                    response = self._api(job, base + endpoint + quote(target[1], safe=''), key)
                    values = [response if platform == 'Modrinth' else response.get('data') if isinstance(response, dict) else None]
                    if not isinstance(response, dict) or not values[0]:
                        raise ValueError('平台项目响应格式错误。')
                elif platform == 'Modrinth':
                    response = self._api(job, base + '/search?' + urlencode({'query': query, 'limit': MAX_CANDIDATES, 'facets': json.dumps([['project_type:mod']])}))
                    if not isinstance(response, dict) or not isinstance(response.get('hits'), list):
                        raise ValueError('平台搜索响应格式错误。')
                    values = response['hits']
                else:
                    response = self._api(job, base + '/mods/search?' + urlencode({'gameId': 432, 'classId': 6, 'searchFilter': target[1] if target else query, 'pageSize': MAX_CANDIDATES}), key)
                    if not isinstance(response, dict) or not isinstance(response.get('data'), list):
                        raise ValueError('平台搜索响应格式错误。')
                    values = response['data']
                found = []
                for value in values:
                    project = _project(platform, value)
                    if project and target and target[2] == 'id' and project['projectId'] != target[1] and (platform != 'Modrinth' or str(value.get('slug', '')).casefold() != target[1].casefold()):
                        raise ValueError('平台返回的项目与链接不符，未作为候选。')
                    if project and (not target or target[2] != 'slug' or str(value.get('slug', '')).casefold() == target[1].casefold()):
                        if mirrored:
                            project['provider'] = 'MCIM'
                        found.append(project)
                candidates.extend(found)
                message = ('返回 ' + str(len(found)) + ' 个项目候选，仍需核对后确认。') if found else '查询成功，未返回项目候选；只代表该平台本次检索结果。'
                checks.append({**check, 'status': 'matched' if found else 'not_found', 'message': message})
            except ValueError as error:
                message = ('MCIM 镜像 · ' if mirrored else '') + platform + ' 项目查询未完成：' + _text(error, 200)
                notes.append(message)
                checks.append({**check, 'status': 'error', 'message': message})
        return candidates, notes, checks

    def _candidates(self, job, key, values):
        saved, projects, rows = {}, set(), []
        grouped = {'Modrinth': [], 'CurseForge': []}
        for value in values:
            ref = (value['site'], value['projectId'])
            if ref in projects:
                continue
            projects.add(ref)
            grouped[value['site']].append(value)
        # Preserve each site's official ordering while keeping both visible.
        ordered = []
        for index in range(MAX_CANDIDATES):
            for site in ('Modrinth', 'CurseForge'):
                if index < len(grouped[site]):
                    ordered.append(grouped[site][index])
        for value in ordered[:MAX_CANDIDATES]:
            ident = secrets.token_urlsafe(18)
            saved[ident] = copy.deepcopy(value)
            rows.append({'id': ident, **value})
        job['candidates'][key] = saved
        self._item(job, key)['candidates'] = rows

    def _derive(self, item):
        if item['exact']:
            item.update(status='exact', label='官方文件 · 精确匹配')
        elif item['confirmation']:
            item.update(status='confirmed', label='已确认原项目')
        elif item['candidates']:
            checks = list((item.get('checks') or {}).values())
            # One site's miss is not evidence against files hosted elsewhere.
            # A skipped, failed, or pending source leaves hash coverage incomplete.
            all_hash_sources_missed = bool(checks) and all(check.get('status') == 'not_found' for check in checks)
            item.update(status='suspect', label='疑似魔改 · 待确认' if all_hash_sources_missed else '候选来源 · 待确认')
            disclaimer = '候选不证明文件来自该项目；未匹配也可能是未收录或重新打包，不一定修改过。'
            if disclaimer not in item['notes']:
                item['notes'].append(disclaimer)
        else:
            error = any(check.get('status') == 'error' for check in item['checks'].values()) or any('未完成' in note for note in item['notes'])
            item.update(status='error' if error else 'unmatched', label='查询未完成 · 可重试' if error else '来源待确认')

    def search(self, ident, key, query, site='all'):
        site = str(site).lower()
        if not isinstance(query, str):
            raise ValueError('请输入项目名称。')
        query = query.strip()
        target = _project_target(query)
        if site not in ('all', 'modrinth', 'curseforge', 'mcim') or not 2 <= len(query) <= (500 if target else 120) or re.search(r'[\x00-\x1f]', query):
            raise ValueError('请输入 2–120 字的项目名称或支持的官方项目链接，并选择查询来源。')
        if query.lower().startswith(('http://', 'https://')) and not target:
            raise ValueError('项目链接仅支持 HTTPS 的 Modrinth /mod/项目 或 CurseForge 项目页面。')
        if target and site not in ('all', 'mcim', target[0].lower()):
            raise ValueError('项目链接与所选平台不符，请选择对应平台或全部平台。')
        with self.lock:
            job = self._job(ident)
            self._check(job)
            item = self._item(job, key)
            if item['exact']:
                raise ValueError('该文件已有精确官方来源，无需猜测其他项目。')
            job['epochs'][key] += 1
            epoch = job['epochs'][key]
            job['candidates'][key] = {}
            item.update(searching=True, query=query, candidates=[], searchChecks=[])
            job['searches'].add((key, epoch))
            self._sync(job)
            self._submit(job, self._search, key, epoch, query, site)
            return self._public(job)

    def _search(self, job, key, epoch, query, site):
        try:
            values, notes, checked = self._find(job, query, site)
            with self.lock:
                if job['epochs'][key] == epoch and not job['cancel'].is_set():
                    item = self._item(job, key)
                    item['notes'] = list(dict.fromkeys(notes))
                    item['searchChecks'] = checked
                    self._candidates(job, key, values)
                    self._derive(item)
        except _Cancelled:
            pass
        except Exception as error:
            with self.lock:
                if job['epochs'][key] == epoch:
                    self._item(job, key).update(status='error', label='查询未完成 · 可重试', notes=[_text(error, 300)])
        finally:
            with self.lock:
                job['searches'].discard((key, epoch))
                if job['epochs'][key] == epoch:
                    self._item(job, key)['searching'] = False
                self._sync(job)

    def confirm(self, ident, key, candidate_id):
        with self.lock:
            job = self._job(ident)
            self._check(job)
            item = self._item(job, key)
            value = job['candidates'].get(key, {}).get(candidate_id) if isinstance(candidate_id, str) else None
            if item['exact'] or not value:
                raise ValueError('候选不存在或已过期，请重新搜索后选择。')
            if value.get('provider') == 'MCIM':
                base = MCIM_MR if value['site'] == 'Modrinth' else MCIM_CF
                endpoint = '/project/' if value['site'] == 'Modrinth' else '/mods/'
                response = self._api(job, base + endpoint + value['projectId'])
                project = _project(value['site'], response if value['site'] == 'Modrinth' else response.get('data') if isinstance(response, dict) else None)
                if not project or project['projectId'] != value['projectId']:
                    raise ValueError('镜像返回的项目 ID 不符，尚未确认原项目，请重新搜索。')
                value = {**project, 'provider': 'MCIM'}
            mod = job['mods'][key]
            record = {**{name: value[name] for name in ('site', 'projectId', 'name', 'url')}, 'sha256': mod['sha256'],
                      'componentsSignature': _signature(mod), 'userConfirmedAt': datetime.now(timezone.utc).isoformat()}
            if value.get('provider') == 'MCIM':
                record['provider'] = 'MCIM'
            self._persist(mod['sha256'], record)
            for other in job['state']['items']:
                if other['sha256'] == mod['sha256'] and _signature(job['mods'][other['key']]) == record['componentsSignature'] and not other['exact']:
                    job['epochs'][other['key']] += 1
                    job['searches'] = {entry for entry in job['searches'] if entry[0] != other['key']}
                    other.update(confirmation=self._confirmation(record), searching=False,
                                 notes=['此项目归属由用户确认，不代表官方原版文件或精确版本，也不用于自动补全前置。'])
                    self._derive(other)
            self._sync(job)
            return self._public(job)

    def clear(self, ident, key):
        with self.lock:
            job = self._job(ident)
            item = self._item(job, key)
            sha = job['mods'][key]['sha256']
            self._persist(sha, None)
            for other in job['state']['items']:
                if other['sha256'] == sha:
                    job['epochs'][other['key']] += 1
                    job['searches'] = {entry for entry in job['searches'] if entry[0] != other['key']}
                    other.update(confirmation=None, searching=False, notes=[])
                    self._derive(other)
            self._sync(job)
            return self._public(job)

    def cancel(self, ident):
        with self.lock:
            job = self._job(ident)
            job['cancel'].set()
            for item in job['state']['items']:
                item['searching'] = False
                if item['status'] == 'checking':
                    item.update(status='error', label='查询已取消 · 来源待确认')
            self._sync(job)
            return self._public(job)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            for job in self.jobs.values():
                job['cancel'].set()
        self.pool.shutdown(wait=True, cancel_futures=True)


def defaultdict_int():
    from collections import defaultdict
    return defaultdict(int)
