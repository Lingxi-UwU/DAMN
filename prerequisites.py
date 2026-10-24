"""Conservative, non-AI prerequisite planning and opt-in installation.

Only exact official file identities and required platform relationships are used.
Plans never write into an instance. Installation stages and validates every selected
file before atomically adding files, without replacing anything already present.
"""
import atexit
import copy
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError, URLError

import research
import scanner

MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_NEW = 200
LOADERS = {'fabric': 'Fabric', 'forge': 'Forge', 'neoforge': 'NeoForge'}
LOADER_KEYS = {'fabric': 'fabricloader', 'forge': 'forge', 'neoforge': 'neoforge'}
CF_CDN_HOSTS = {'edge.forgecdn.net', 'mediafilez.forgecdn.net', 'media.forgecdn.net'}
CDN_HOSTS = {'cdn.modrinth.com'} | CF_CDN_HOSTS
WINDOWS = os.name == 'nt'
MR = 'https://api.modrinth.com/v2'
CF = 'https://api.curseforge.com/v1'


class Cancelled(Exception):
    pass


def _cancel(event):
    if event.is_set():
        raise Cancelled('任务已取消。')


def _linked(path):
    value = path.lstat()
    return stat.S_ISLNK(value.st_mode) or bool(getattr(value, 'st_file_attributes', 0) & 0x400)


def _plain_path(path):
    """Reject reparse points before resolving; resolving first would conceal them."""
    path = Path(os.path.abspath(os.fspath(path)))
    for part in [*reversed(path.parents), path]:
        if part.exists() or part.is_symlink():
            if _linked(part):
                raise ValueError('目录或文件包含符号链接 / junction，不能自动补全。')
    return path


def _directory(directory):
    if not isinstance(directory, str) or not directory.strip() or len(directory) > 4096:
        raise ValueError('请填写本地实例目录或 mods 目录。')
    directory = directory.strip()
    if len(directory) >= 2 and directory.startswith('"') and directory.endswith('"'):
        directory = directory[1:-1].strip()
    path = _plain_path(Path(directory).expanduser())
    if not path.is_dir():
        raise ValueError('前置补全只接受本地目录，不支持 ZIP / MRPACK 文件。')
    root = path.parent if path.name.lower() == 'mods' else path
    mods = root / 'mods'
    _plain_path(root)
    _plain_path(mods)
    if not mods.is_dir():
        raise ValueError('该目录内没有 mods 文件夹。')
    anchors = {str(p): (p.stat().st_dev, p.stat().st_ino) for p in (root, mods)}
    return root, mods, anchors


def _guard(job):
    for value, identity in job['anchors'].items():
        path = _plain_path(value)
        current = path.stat()
        if not path.is_dir() or (current.st_dev, current.st_ino) != identity:
            raise ValueError('实例目录已发生变化，请重新扫描。')


def _jar_paths(mods):
    result = []
    for path in sorted(mods.iterdir()):
        if path.name.lower().endswith(('.jar', '.jar.disabled')):
            _plain_path(path)
            if not path.is_file():
                raise ValueError('模组路径不是普通文件：' + path.name)
            if path.stat().st_size > MAX_FILE:
                raise ValueError('模组超过单文件 512 MiB 上限：' + path.name)
            result.append(path)
    if len(result) > 3000:
        raise ValueError('最多识别 3000 个本地模组文件。')
    return result


def _environment_snapshot(root, event):
    result = {}
    for path in ([root / 'mmc-pack.json'] + sorted(root.glob('*.json')))[:30]:
        if path.exists():
            _plain_path(path)
            if path.is_file() and path.stat().st_size <= 2_000_000:
                result[path.name] = _digests(path, event)['sha256']
    return result


def _digests(path, event):
    hashes = {'sha1': hashlib.sha1(), 'sha256': hashlib.sha256()}
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            _cancel(event)
            for digest in hashes.values():
                digest.update(chunk)
    return {k: v.hexdigest() for k, v in hashes.items()}


def _metadata(path, preferred):
    errors = []
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 30000:
            raise ValueError('JAR 内文件数量超过静态读取上限。')
        components, dependencies, loader, loaders = scanner.read_jar(archive, path.name, preferred, errors)
    if errors or not components:
        raise ValueError('JAR 元数据不完整，无法安全补全：' + (str(errors[0]['message']) if errors else path.name))
    return {'components': components, 'dependencies': dependencies, 'loader': loader, 'loaders': loaders}


def _nested_identities(path, meta, owner, event):
    """Match declared embedded JARs by bytes, never by a project/name guess."""
    paths = set()
    for component in meta['components']:
        if component.get('nested'):
            parts = str(component.get('source') or '').split('!')
            if len(parts) >= 3:
                paths.add(tuple(parts[1:-1]))
    result, budget = [], 64_000_000
    for entries in sorted(paths):
        _cancel(event)
        opened = []
        archive = zipfile.ZipFile(path)
        opened.append(archive)
        try:
            data = None
            for entry in entries:
                info = archive.getinfo(entry)
                if info.file_size > min(32_000_000, budget):
                    raise ValueError('内置 JAR 超出精确识别上限。')
                budget -= info.file_size
                data = archive.read(entry)
                archive = zipfile.ZipFile(io.BytesIO(data))
                opened.append(archive)
            if data is not None:
                result.append({'key': owner['key'] + '!' + '!'.join(entries), 'name': owner['name'] + '（内置）',
                               'sha1': hashlib.sha1(data).hexdigest(), 'path': None, 'active': owner['active'],
                               'enabled': owner['enabled'], 'embeddedOwner': owner['key']})
        finally:
            for value in reversed(opened):
                value.close()
    return result


def _fingerprint(path, event):
    """CurseForge's whitespace-stripped MurmurHash2, seed 1, with bounded memory."""
    count = 0
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            _cancel(event)
            count += len(chunk.translate(None, b'\x09\x0a\x0d\x20'))
    value, tail, mask = 1 ^ count, b'', 0xffffffff
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            _cancel(event)
            data = tail + chunk.translate(None, b'\x09\x0a\x0d\x20')
            length = len(data) // 4 * 4
            words = memoryview(data)[:length].cast('I') if sys.byteorder == 'little' else (int.from_bytes(data[offset:offset + 4], 'little') for offset in range(0, length, 4))
            for part in words:
                part = (part * 0x5bd1e995) & mask
                part ^= part >> 24
                part = (part * 0x5bd1e995) & mask
                value = ((value * 0x5bd1e995) ^ part) & mask
            tail = data[length:]
    if tail:
        value ^= int.from_bytes(tail, 'little')
        value = (value * 0x5bd1e995) & mask
    value ^= value >> 13
    value = (value * 0x5bd1e995) & mask
    return (value ^ (value >> 15)) & mask


def api_json(url, key=None, payload=None):
    """All API access shares the application's allowlist, cache and throttling."""
    return json.loads(research.fetch(url, key, payload))


def _api(job, url, key=None, payload=None):
    _cancel(job['cancel'])
    if time.monotonic() > job['deadline']:
        raise ValueError('平台核对已达到时间上限，请稍后重新扫描。')
    token = research.FETCH_DEADLINE.set(min(job['deadline'], time.monotonic() + 12))
    try:
        return api_json(url, key, payload)
    finally:
        research.FETCH_DEADLINE.reset(token)


def permitted_download(url):
    try:
        parsed = urlsplit(str(url))
        return (parsed.scheme == 'https' and parsed.hostname in CDN_HOSTS and
                parsed.port in (None, 443) and not parsed.username and not parsed.password and
                not parsed.fragment and '\\' not in str(url))
    except ValueError:
        return False


class _DownloadRedirect(HTTPRedirectHandler):
    max_redirections = 5
    max_repeats = 2

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not permitted_download(newurl):
            raise ValueError('文件跳转到了非官方 HTTPS CDN，已停止。')
        authenticated = req is not None and any(name.lower() == 'x-api-key' for name in {**req.headers, **req.unredirected_hdrs})
        if authenticated and urlsplit(newurl).hostname not in CF_CDN_HOSTS:
            raise ValueError('已阻止 CurseForge 下载认证随跳转发送到其他来源。')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_file(url, destination, expected_size, hashes, event, cf_key=None):
    if not permitted_download(url):
        raise ValueError('下载地址不是受支持的官方 HTTPS CDN。')
    if not hashes:
        raise ValueError('来源没有提供校验哈希，不能自动下载。')
    expected_size = int(expected_size)
    if not 0 < expected_size <= MAX_FILE:
        raise ValueError('文件大小未知或超过单文件 512 MiB 上限。')
    digests = {name: hashlib.new(name) for name in hashes}
    deadline = time.monotonic() + 180
    request = Request(url, headers={'User-Agent': 'DAMN/prerequisites', 'Accept-Encoding': 'identity'})
    if cf_key and urlsplit(url).hostname in CF_CDN_HOSTS:
        if not isinstance(cf_key, str) or len(cf_key) > 2048 or not cf_key.isascii() or any(ord(char) <= 32 or ord(char) == 127 for char in cf_key):
            raise ValueError('独立 CF API Key 格式无效，请检查设置；密钥不能包含空格、换行或非 ASCII 字符。')
        request.add_header('x-api-key', cf_key)
    try:
        with build_opener(_DownloadRedirect()).open(request, timeout=8) as response:
            if not permitted_download(response.geturl()):
                raise ValueError('文件来源发生变化，已停止。')
            length = response.headers.get('Content-Length')
            if length and (not length.isdigit() or int(length) != expected_size):
                raise ValueError('下载长度与平台声明不一致。')
            size = 0
            with Path(destination).open('xb') as stream:
                while True:
                    _cancel(event)
                    if time.monotonic() > deadline:
                        raise ValueError('文件下载超时，请稍后重试。')
                    chunk = response.read(128 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > expected_size or size > MAX_FILE:
                        raise ValueError('下载文件超过平台声明大小。')
                    stream.write(chunk)
                    for digest in digests.values():
                        digest.update(chunk)
                stream.flush()
                os.fsync(stream.fileno())
        if size != expected_size or any(digests[name].hexdigest().lower() != value.lower() for name, value in hashes.items()):
            raise ValueError('文件哈希或大小校验失败，未安装。')
        _cancel(event)
    except HTTPError as error:
        if error.code == 401 and urlsplit(error.url or url).hostname in CF_CDN_HOSTS:
            raise ValueError('CurseForge 文件下载认证失败（HTTP 401）。请在设置中填写或更新独立 CF API Key（不是 AI 密钥），然后重新尝试补全。') from None
        if error.code == 429:
            raise ValueError('下载源限流（HTTP 429），本次已停止，请稍后重试。') from None
        raise ValueError('下载源返回 HTTP ' + str(error.code) + '，未安装。') from None
    except (URLError, TimeoutError, OSError) as error:
        raise ValueError('文件下载或暂存失败：' + str(error)[:180]) from None


def _safe_name(name):
    return (isinstance(name, str) and 0 < len(name) <= 180 and name.lower().endswith('.jar') and
            name == Path(name).name and not re.search(r'[\\/:*?"<>|\x00-\x1f]', name) and
            name.rstrip(' .') == name and not re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', name))


def _hashes(file, site):
    if site == 'Modrinth':
        raw = file.get('hashes') or {}
    else:
        raw = {('sha1' if h.get('algo') == 1 else 'md5' if h.get('algo') == 2 else ''): h.get('value')
               for h in file.get('hashes') or [] if isinstance(h, dict)}
    result = {}
    for algorithm, length in [('sha512', 128), ('sha1', 40)]:
        value = raw.get(algorithm)
        if isinstance(value, str) and re.fullmatch(r'[a-fA-F0-9]{' + str(length) + '}', value):
            result[algorithm] = value.lower()
    return result


def _version_id(version, site):
    return str(version.get('id') or '')


def _required(version, site):
    result = []
    for dependency in version.get('dependencies') or []:
        if not isinstance(dependency, dict):
            continue
        kind = dependency.get('dependency_type') if site == 'Modrinth' else dependency.get('relationType')
        if kind not in ('required', 'incompatible', 3, 5):
            continue
        result.append({'project': str(dependency.get('project_id' if site == 'Modrinth' else 'modId') or ''),
                       'version': str(dependency.get('version_id') or ''),
                       'kind': 'incompatible' if kind in ('incompatible', 5) else 'required'})
    return result


def _commit_groups(selected, graph):
    """Dependency-first strongly connected groups; cancellation stays outside cycles."""
    selected = set(selected)
    indices, low, stack, active, result = {}, {}, [], set(), []

    def visit(ref):
        indices[ref] = low[ref] = len(indices)
        stack.append(ref)
        active.add(ref)
        for child in sorted(graph.get(ref, set()) & selected):
            if child not in indices:
                visit(child)
                low[ref] = min(low[ref], low[child])
            elif child in active:
                low[ref] = min(low[ref], indices[child])
        if low[ref] == indices[ref]:
            group = []
            while True:
                child = stack.pop()
                active.remove(child)
                group.append(child)
                if child == ref:
                    break
            result.append(group)
    for ref in sorted(selected):
        if ref not in indices:
            visit(ref)
    return result


def _commit_file(source, target):
    """Atomic no-clobber addition on the same staging/instance volume.

    Windows rename fails when a destination exists, and also works on volumes
    such as exFAT which do not support hard links. POSIX rename can overwrite,
    so it must continue to use link instead. Never fall back to a direct copy.
    """
    if WINDOWS:
        os.rename(source, target)
    else:
        os.link(source, target)


class PrerequisiteManager:
    def __init__(self, cf_key_getter=lambda: ''):
        self.cf_key_getter = cf_key_getter
        self.lock = threading.RLock()
        self.jobs = {}
        self.closed = False
        atexit.register(self.close)

    def _public(self, job):
        return copy.deepcopy(job['state'])

    def _update(self, job, **values):
        with self.lock:
            job['state'].update(values)

    def _note(self, job, text):
        with self.lock:
            if text not in job['state']['notes']:
                job['state']['notes'].append(text)

    def _unresolved(self, job, target, required_by, reason):
        value = {'target': str(target)[:200], 'requiredBy': list(dict.fromkeys(required_by)), 'reason': str(reason)[:500]}
        with self.lock:
            if value not in job['state']['unresolved']:
                job['state']['unresolved'].append(value)

    def _relationship_failure(self, job, parent, parent_name, target, reason):
        self._unresolved(job, target, [parent_name], reason)
        if parent in job['items']:
            job['items'][parent]['public'].update(status='blocked', reason='必需 / 不兼容关系不能完整核对：' + str(reason)[:350])

    def _launch(self, job, function, *args):
        def run():
            try:
                function(job, *args)
            except Cancelled:
                self._update(job, status='cancelled', phase='cancelled', message='任务已取消；已安装的文件保留。')
            except Exception as error:
                self._update(job, status='failed', phase='failed', message=str(error)[:500])
            finally:
                with self.lock:
                    staging = job.get('staging')
                    job['staging'] = None
                if staging:
                    try:
                        _plain_path(staging)
                        current = Path(staging).stat()
                        if (current.st_dev, current.st_ino) != job.get('staging_identity'):
                            raise ValueError('临时目录身份已变化，保留供人工检查。')
                        shutil.rmtree(staging)
                    except (OSError, ValueError):
                        self._note(job, '临时文件清理失败：' + str(staging))
        thread = threading.Thread(target=run, name='DAMN-prerequisites', daemon=True)
        job['thread'] = thread
        thread.start()

    def start_plan(self, directory, side='client', game_version='', loader='', loader_version=''):
        root, mods, anchors = _directory(directory)
        if side not in ('client', 'server'):
            raise ValueError('运行侧必须是 client 或 server。')
        game_version = str(game_version or '').strip()
        loader = str(loader or '').strip().lower()
        loader_version = str(loader_version or '').strip()
        if game_version and not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', game_version):
            raise ValueError('请填写准确的 Minecraft 版本，例如 1.21.1。')
        if loader and loader not in LOADERS:
            raise ValueError('当前仅支持 Fabric、Forge 和 NeoForge，三者不能混用。')
        if loader_version and not re.fullmatch(r'\d+(?:\.\d+){1,4}(?:[-+][A-Za-z0-9.-]+)?', loader_version):
            raise ValueError('请填写准确的加载器版本，例如 0.16.10 或 21.1.172。')
        with self.lock:
            if self.closed:
                raise ValueError('前置补全服务已关闭。')
            if any(j['state']['status'] in ('planning', 'installing') for j in self.jobs.values()):
                raise ValueError('已有前置任务正在处理，请先等待或取消。')
            ident = uuid.uuid4().hex
            job = {'cancel': threading.Event(), 'anchors': anchors, 'root': root, 'mods': mods,
                   'side': side, 'manual': (game_version, loader, loader_version), 'deadline': time.monotonic() + 240,
                   'items': {}, 'graph': defaultdict(set), 'parents': defaultdict(set),
                   'existing': {}, 'local': [], 'nested': [], 'snapshot': {}, 'staging': None,
                   'state': {'id': ident, 'status': 'planning', 'phase': 'scanning', 'message': '正在静态读取本地模组。',
                             'root': str(root), 'modsDir': str(mods), 'environment': {'minecraft': '', 'loader': '', 'loaderVersion': ''},
                             'progress': {'done': 0, 'total': 0}, 'items': [], 'notes': [], 'unresolved': [],
                             'needsEnvironment': False}}
            self.jobs[ident] = job
            # Bound retained completed plans; paths and download choices stay server-side.
            for old in list(self.jobs):
                if len(self.jobs) <= 16:
                    break
                if old != ident and self.jobs[old]['state']['status'] not in ('planning', 'installing'):
                    del self.jobs[old]
            result = self._public(job)
            self._launch(job, self._plan)
            return result

    def status(self, ident):
        with self.lock:
            if ident not in self.jobs:
                raise ValueError('前置任务不存在或已过期，请重新扫描。')
            return self._public(self.jobs[ident])

    def cancel(self, ident):
        with self.lock:
            if ident not in self.jobs:
                raise ValueError('前置任务不存在。')
            job = self.jobs[ident]
            job['cancel'].set()
            if job['state']['status'] not in ('planning', 'installing'):
                job['state'].update(status='cancelled', phase='cancelled', message='任务已取消。')
            else:
                job['state']['message'] = '正在停止任务并清理临时文件。'
            return self._public(job)

    def close(self):
        with self.lock:
            self.closed = True
            jobs = list(self.jobs.values())
            for job in jobs:
                job['cancel'].set()
        deadline = time.monotonic() + 10
        for job in jobs:
            thread = job.get('thread')
            if thread and thread is not threading.current_thread():
                thread.join(max(0, deadline - time.monotonic()))

    def _local(self, job):
        _guard(job)
        job['environment_snapshot'] = _environment_snapshot(job['root'], job['cancel'])
        env = scanner.instance_environment(job['root'])
        if job['environment_snapshot'] != _environment_snapshot(job['root'], job['cancel']):
            raise ValueError('读取期间实例版本配置发生变化，请重新扫描。')
        # scanner skips symlinks, but a supplemental override is not safe to ignore.
        if (job['root'] / 'config/fabric_loader_dependencies.json').exists():
            raise ValueError('发现 Fabric 依赖覆盖文件，当前不能自动应用覆盖规则，请先人工核对。')
        game, loader, manual_loader_version = job['manual']
        declared = [name for name, key in LOADER_KEYS.items() if env.get(key)]
        if game and env.get('minecraft') and game != env['minecraft']:
            raise ValueError('手填 Minecraft 版本与实例配置不符，请核对后重新扫描。')
        if loader and declared and declared != [loader]:
            raise ValueError('手填加载器与实例配置不符，请核对后重新扫描。')
        if not loader:
            loader = declared[0] if len(declared) == 1 else ''
        preferred = LOADERS.get(loader)
        paths = _jar_paths(job['mods'])
        self._update(job, progress={'done': 0, 'total': len(paths)})
        for index, path in enumerate(paths):
            _cancel(job['cancel'])
            before = path.stat()
            hashes = _digests(path, job['cancel'])
            try:
                meta = _metadata(path, preferred)
            except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as error:
                self._unresolved(job, path.name, [], str(error))
                meta = {'components': [], 'dependencies': [], 'loader': '未知', 'loaders': []}
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError('读取期间模组发生变化，请重新扫描：' + path.name)
            enabled = not path.name.lower().endswith('.disabled')
            top = [c for c in meta['components'] if not c.get('nested')]
            active = enabled and not (meta['loader'] == 'Fabric' and top and all(c.get('environment') == ('client' if job['side'] == 'server' else 'server') for c in top))
            local = {**meta, **hashes, 'path': path, 'file': path.name, 'key': 'local:' + path.name,
                     'name': ' / '.join(c.get('name', c['id']) for c in top) or path.name, 'active': active, 'enabled': enabled}
            job['local'].append(local)
            try:
                job['nested'].extend(_nested_identities(path, meta, local, job['cancel']))
            except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
                self._note(job, '内置依赖平台身份未能核对：' + str(error))
            job['snapshot'][path.name] = hashes['sha256']
            self._update(job, progress={'done': index + 1, 'total': len(paths)})
        if not loader:
            choices = {m['loader'].lower() for m in job['local'] if m['active'] and m['loader'].lower() in LOADERS}
            loader = next(iter(choices)) if len(choices) == 1 else ''
        game = game or env.get('minecraft', '')
        if not game:
            exact = set()
            for mod in job['local']:
                if not mod['active']:
                    continue
                for dep in mod['dependencies']:
                    rule = str(dep.get('range') or '')
                    if dep['target'] == 'minecraft' and dep['type'] == 'required':
                        value = rule[1:-1] if rule.startswith('[') and rule.endswith(']') and ',' not in rule else rule.lstrip('=')
                        if re.fullmatch(r'\d+\.\d+(?:\.\d+)?', value):
                            exact.add(value)
            game = next(iter(exact)) if len(exact) == 1 else ''
        auto_loader_version = str(env.get(LOADER_KEYS.get(loader, ''), ''))
        if loader == 'forge' and game and auto_loader_version.startswith(game + '-'):
            auto_loader_version = auto_loader_version[len(game) + 1:]
        if manual_loader_version and auto_loader_version and manual_loader_version != auto_loader_version:
            raise ValueError('手填加载器版本与实例配置不符，请核对后重新扫描。')
        loader_version = auto_loader_version or manual_loader_version
        job['environment'] = {**env, 'minecraft': game, 'loader': loader}
        if loader and loader_version:
            job['environment'][LOADER_KEYS[loader]] = loader_version
        self._update(job, environment={'minecraft': game, 'loader': LOADERS.get(loader, ''), 'loaderVersion': loader_version})
        if not game or not loader:
            self._unresolved(job, '运行环境', [], '不能可靠确定 Minecraft 版本或加载器，请补填后重新扫描。')
            self._update(job, needsEnvironment=True, status='ready', phase='ready', message='请补填准确的 Minecraft 版本和加载器，再重新扫描。')
            return False
        for mod in job['local']:
            if mod['active'] and mod['loaders'] and LOADERS[loader] not in mod['loaders']:
                raise ValueError('启用文件的加载器与所选环境不同：' + mod['name'] + '；请先整理目录，不会混装 Forge / NeoForge / Fabric。')
        return True

    def _identify(self, job):
        local = job['local'] + job['nested']
        self._update(job, phase='identifying', message='正在通过官方文件哈希匹配平台版本。', progress={'done': 0, 'total': len(local)})
        for offset in range(0, len(local), 80):
            batch = local[offset:offset + 80]
            try:
                data = _api(job, MR + '/version_files', payload={'hashes': [m['sha1'] for m in batch], 'algorithm': 'sha1'})
                for mod in batch:
                    version = data.get(mod['sha1']) if isinstance(data, dict) else None
                    if isinstance(version, dict) and version.get('project_id') and any((_hashes(f, 'Modrinth').get('sha1') == mod['sha1']) for f in version.get('files') or []):
                        mod['platform'] = ('Modrinth', str(version['project_id']), version)
            except ValueError as error:
                self._note(job, 'Modrinth 哈希匹配：' + str(error))
            self._update(job, progress={'done': min(offset + len(batch), len(local)), 'total': len(local)})
        key = self.cf_key_getter() or ''
        job['cf_key'] = key
        unmatched = [m for m in local if not m.get('platform')]
        if unmatched and not key:
            self._note(job, '部分文件未匹配 Modrinth；CurseForge 精确匹配需要设置中的独立 CF API Key，不使用 AI 密钥。')
        if key:
            fingerprintable = [m for m in unmatched if m.get('path')]
            for offset in range(0, len(fingerprintable), 60):
                batch = fingerprintable[offset:offset + 60]
                fingerprints = defaultdict(list)
                for mod in batch:
                    self._update(job, message='正在核对 CurseForge 精确文件指纹：' + mod['name'])
                    fingerprints[_fingerprint(mod['path'], job['cancel'])].append(mod)
                try:
                    data = _api(job, CF + '/fingerprints', key, {'fingerprints': list(fingerprints)}).get('data') or {}
                    for match in data.get('exactMatches') or []:
                        version = match.get('file') or {}
                        for mod in fingerprints.get(version.get('fileFingerprint'), []):
                            if _hashes(version, 'CurseForge').get('sha1') == mod['sha1'] and version.get('modId'):
                                mod['platform'] = ('CurseForge', str(version['modId']), version)
                except ValueError as error:
                    self._note(job, 'CurseForge 指纹匹配：' + str(error))
        for mod in local:
            if mod.get('platform'):
                site, project, version = mod['platform']
                ref = site + ':' + project
                if ref in job['existing'] and _version_id(job['existing'][ref]['platform'][2], site) != _version_id(version, site):
                    self._unresolved(job, mod['name'], [], '同一平台项目存在多个本地版本，请先整理。')
                job['existing'][ref] = mod

    def _compatible(self, job, version, site):
        env = job['environment']
        if site == 'Modrinth':
            side = version.get('environment')
            if side in ('client', 'server') and side != job['side']:
                return False
            if side:
                known = {'client', 'server', 'client_only', 'server_only', 'client_and_server', 'dedicated_server_only',
                         'singleplayer_only', 'server_only_client_optional', 'client_only_server_optional',
                         'client_or_server', 'client_or_server_prefers_both'}
                if not isinstance(side, str) or side not in known:
                    return False
                if job['side'] == 'server' and side in ('client_only', 'singleplayer_only'):
                    return False
                if job['side'] == 'client' and side == 'dedicated_server_only':
                    return False
            return env['minecraft'] in (version.get('game_versions') or []) and env['loader'] in (version.get('loaders') or [])
        names = set(version.get('gameVersions') or [])
        expected = LOADERS[env['loader']]
        return env['minecraft'] in names and expected in names

    def _candidate(self, job, site, project, fixed):
        encoded = quote(project, safe='')
        if site == 'Modrinth':
            info = _api(job, MR + '/project/' + encoded)
            if str(info.get('id')) != project or info.get('project_type', 'mod') != 'mod':
                raise ValueError('平台项目身份不符或不是模组。')
            support = info.get('server_side' if job['side'] == 'server' else 'client_side')
            if support == 'unsupported':
                raise ValueError('平台项目不支持当前运行侧。')
            if fixed:
                versions = [_api(job, MR + '/version/' + quote(fixed, safe=''))]
            else:
                versions = _api(job, MR + '/project/' + encoded + '/version?' + urlencode({'game_versions': json.dumps([job['environment']['minecraft']]), 'loaders': json.dumps([job['environment']['loader']]), 'include_changelog': 'false'}))
            versions = [v for v in versions if isinstance(v, dict) and str(v.get('project_id')) == project and self._compatible(job, v, site) and (not fixed or str(v.get('id')) == fixed)]
            versions.sort(key=lambda v: (v.get('version_type') == 'release', str(v.get('date_published', ''))), reverse=True)
            if not versions:
                raise ValueError('没有同时匹配 Minecraft、加载器及固定版本要求的文件。')
            version = versions[0]
            files = [f for f in version.get('files') or [] if isinstance(f, dict) and _safe_name(f.get('filename')) and not f.get('file_type') and not re.search(r'(?i)[.-](sources|dev|javadoc)\.jar$', f['filename'])]
            primary = [f for f in files if f.get('primary')]
            file = primary[0] if len(primary) == 1 else files[0] if len(files) == 1 else None
            if not file:
                raise ValueError('平台版本没有唯一的主 JAR 文件。')
            return info, version, file, 'https://modrinth.com/mod/' + encoded
        key = job['cf_key']
        if not key:
            raise ValueError('CurseForge 缺少独立 CF API Key。')
        info = _api(job, CF + '/mods/' + encoded, key).get('data') or {}
        if str(info.get('id')) != project or info.get('gameId') != 432 or info.get('classId') != 6:
            raise ValueError('CurseForge 项目身份不符或不是 Minecraft 模组。')
        if info.get('allowModDistribution') is False:
            raise ValueError('作者未允许第三方分发，不能自动下载。')
        if fixed:
            versions = [(_api(job, CF + '/mods/' + encoded + '/files/' + quote(fixed, safe=''), key).get('data') or {})]
        else:
            query = urlencode({'gameVersion': job['environment']['minecraft'], 'modLoaderType': {'forge': 1, 'fabric': 4, 'neoforge': 6}[job['environment']['loader']], 'pageSize': 50})
            versions = (_api(job, CF + '/mods/' + encoded + '/files?' + query, key).get('data') or [])
        versions = [v for v in versions if isinstance(v, dict) and str(v.get('modId')) == project and self._compatible(job, v, site) and (not fixed or str(v.get('id')) == fixed)]
        versions.sort(key=lambda v: (v.get('releaseType') == 1, str(v.get('fileDate', ''))), reverse=True)
        if not versions:
            raise ValueError('没有同时匹配 Minecraft、加载器及固定版本要求的文件。')
        version = versions[0]
        return info, version, version, 'https://www.curseforge.com/minecraft/mc-mods/' + quote(str(info.get('slug') or project), safe='')

    def _publish(self, job):
        self._update(job, items=[copy.deepcopy(item['public']) for item in job['items'].values()])

    def _plan(self, job):
        if not self._local(job):
            return
        self._identify(job)
        queue = deque()
        for mod in job['local']:
            if mod['active'] and mod.get('platform'):
                site, _, version = mod['platform']
                for dependency in _required(version, site):
                    queue.append((mod['key'], mod['name'], site, dependency))
        seen = set()
        fixed_by = defaultdict(set)
        incompatible = []
        expanded_existing = set()
        self._update(job, phase='resolving', message='正在核对必需前置及递归依赖。')
        while queue:
            _cancel(job['cancel'])
            parent, parent_name, site, dependency = queue.popleft()
            project, fixed = dependency['project'], dependency['version']
            if not project and fixed and site == 'Modrinth':
                try:
                    project = str(_api(job, MR + '/version/' + quote(fixed, safe='')).get('project_id') or '')
                except ValueError as error:
                    self._relationship_failure(job, parent, parent_name, fixed, str(error))
                    continue
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}' if site == 'Modrinth' else r'\d{1,15}', project):
                self._relationship_failure(job, parent, parent_name, project or fixed or '未命名依赖', '平台没有提供可核对的项目 ID。')
                continue
            ref = site + ':' + project
            if dependency['kind'] == 'incompatible':
                incompatible.append((parent, parent_name, ref, fixed))
                continue
            marker = (parent, ref, fixed)
            if marker in seen:
                continue
            seen.add(marker)
            job['graph'][parent].add(ref)
            job['parents'][ref].add(parent)
            if fixed:
                fixed_by[ref].add(fixed)
            existing = job['existing'].get(ref)
            if existing:
                if not existing['active']:
                    self._unresolved(job, existing['name'], [parent_name], '对应文件处于停用状态，不能自动启用或重复安装。')
                    self._blocked(job, ref, parent_name, site, '对应模组已存在但停用；请人工处理。', existing['name'])
                elif fixed and _version_id(existing['platform'][2], site) != fixed:
                    self._blocked(job, ref, parent_name, site, '本地版本与必需的固定平台版本不符；不会覆盖。', existing['name'])
                elif not self._compatible(job, existing['platform'][2], site):
                    self._blocked(job, ref, parent_name, site, '本地平台版本不支持所选 Minecraft / 加载器 / 运行侧，不会替换。', existing['name'])
                elif ref not in expanded_existing:
                    expanded_existing.add(ref)
                    job['parents'][existing['key']].add(parent)
                    for child in _required(existing['platform'][2], site):
                        queue.append((existing['key'], existing['name'], site, child))
                continue
            if ref in job['items']:
                item = job['items'][ref]
                if parent_name not in item['public']['requiredBy']:
                    item['public']['requiredBy'].append(parent_name)
                if len(fixed_by[ref]) > 1 or (fixed and item.get('version') and _version_id(item['version'], site) != fixed):
                    item['public'].update(status='blocked', reason='多个必需关系要求不同固定版本，需人工处理。')
                continue
            if len(job['items']) >= MAX_NEW:
                self._relationship_failure(job, parent, parent_name, project, '缺失前置超过 200 项上限，停止继续扩展。')
                continue
            try:
                info, version, file, source = self._candidate(job, site, project, fixed)
                hashes = _hashes(file, site)
                name = file.get('filename' if site == 'Modrinth' else 'fileName')
                url = file.get('url' if site == 'Modrinth' else 'downloadUrl')
                size = file.get('size' if site == 'Modrinth' else 'fileLength')
                if not _safe_name(name):
                    raise ValueError('平台文件名不安全或不是 JAR。')
                if not permitted_download(url):
                    raise ValueError('没有受支持的官方 CDN 下载地址；不会自行拼接地址。')
                if not hashes:
                    raise ValueError('平台未提供 SHA1 / SHA512 校验哈希。')
                if not isinstance(size, int) or not 0 < size <= MAX_FILE:
                    raise ValueError('文件大小未知或超过单文件 512 MiB 上限。')
                total = sum(i['public']['bytes'] for i in job['items'].values()) + size
                if total > MAX_TOTAL:
                    raise ValueError('待补全文件总量超过 2 GiB 上限。')
                public = {'id': ref, 'name': str(info.get('title' if site == 'Modrinth' else 'name') or project)[:200],
                          'version': str(version.get('version_number' if site == 'Modrinth' else 'displayName') or version.get('id'))[:160],
                          'fileName': name, 'sourceSite': site, 'sourceUrl': source, 'requiredBy': [parent_name],
                          'status': 'ready', 'reason': '官方必需关系；安装前还会校验 JAR 元数据。', 'bytes': size}
                job['items'][ref] = {'public': public, 'version': version, 'url': url, 'hashes': hashes}
                for child in _required(version, site):
                    queue.append((ref, public['name'], site, child))
            except (ValueError, KeyError, TypeError) as error:
                self._blocked(job, ref, parent_name, site, str(error), project)
            self._publish(job)
            self._update(job, progress={'done': len(seen), 'total': len(seen) + len(queue)})
        # Incompatibilities are platform-version scoped; absence of a version means all.
        for parent, parent_name, ref, fixed in incompatible:
            candidate = job['items'].get(ref)
            existing = job['existing'].get(ref)
            version = candidate.get('version') if candidate else (existing['platform'][2] if existing and existing['active'] else None)
            if version and (not fixed or _version_id(version, ref.split(':', 1)[0]) == fixed):
                for blocked in (parent, ref):
                    if blocked in job['items']:
                        job['items'][blocked]['public'].update(status='blocked', reason='平台声明与当前或待安装文件不兼容。')
                self._unresolved(job, ref, [parent_name], '平台声明不兼容。')
        changed = True
        while changed:
            changed = False
            for ref, item in job['items'].items():
                if item['public']['status'] != 'ready':
                    continue
                if any(child in job['items'] and job['items'][child]['public']['status'] == 'blocked' for child in job['graph'][ref]):
                    item['public'].update(status='blocked', reason='该项目仍有不能安全补全的必需前置。')
                    changed = True
        active_ids = {ident for mod in job['local'] if mod['active'] for c in mod['components'] for ident in [c['id']] + list(c.get('aliases') or [])}
        for mod in job['local']:
            if not mod['active']:
                continue
            for dependency in mod['dependencies']:
                if dependency['type'] != 'required' or dependency['side'] not in ('BOTH', job['side'].upper()) or dependency['target'] in scanner.BASE_IDS or dependency['target'] in active_ids:
                    continue
                children = job['graph'].get(mod['key'], set())
                reason = '缺少文件声明的组件；将于安装前验证平台前置是否提供该组件。' if children else '缺少文件声明的组件，且没有精确平台必需关系可安全定位。'
                self._unresolved(job, dependency['target'], [mod['name']], reason)
        self._publish(job)
        ready = sum(i['public']['status'] == 'ready' for i in job['items'].values())
        self._update(job, status='ready', phase='ready', message=('找到 ' + str(ready) + ' 个可核对并补全的必需前置。') if ready else '没有可安全自动补全的缺失前置，请查看核对结果。', progress={'done': len(seen), 'total': len(seen)})

    def _blocked(self, job, ref, parent_name, site, reason, name):
        job['items'][ref] = {'public': {'id': ref, 'name': str(name)[:200], 'version': '', 'fileName': '',
                                      'sourceSite': site, 'sourceUrl': '', 'requiredBy': [parent_name],
                                      'status': 'blocked', 'reason': str(reason)[:500], 'bytes': 0}}
        self._unresolved(job, name, [parent_name], reason)

    def install(self, ident, item_ids):
        with self.lock:
            if self.closed or ident not in self.jobs:
                raise ValueError('任务不存在或服务已关闭。')
            job = self.jobs[ident]
            if any(other is not job and other['state']['status'] in ('planning', 'installing') for other in self.jobs.values()):
                raise ValueError('另一个前置任务正在处理，请等待或取消后再安装。')
            if job['state']['status'] not in ('ready', 'complete') or job['state']['needsEnvironment']:
                raise ValueError('请先完成前置规划及环境核对。')
            if not isinstance(item_ids, list) or not item_ids or len(item_ids) > MAX_NEW or any(not isinstance(x, str) for x in item_ids):
                raise ValueError('请选择需要补全的前置项目。')
            selected = set(item_ids)
            queue = list(selected)
            while queue:
                ref = queue.pop()
                if ref not in job['items'] or job['items'][ref]['public']['status'] not in ('ready', 'installed'):
                    raise ValueError('所选前置不存在或尚不能安全安装。')
                for dependency in job['graph'][ref]:
                    if dependency in job['existing'] and job['existing'][dependency]['active'] and dependency not in job['items']:
                        continue
                    if dependency not in selected:
                        selected.add(dependency)
                        queue.append(dependency)
            selected = {ref for ref in selected if job['items'][ref]['public']['status'] == 'ready'}
            if not selected:
                raise ValueError('所选项目已经全部安装。')
            names = [job['items'][ref]['public']['fileName'].casefold() for ref in selected]
            if len(names) != len(set(names)):
                raise ValueError('待补全项目存在同名文件，不能自动安装。')
            job['cancel'].clear()
            self._update(job, status='installing', phase='downloading', message='正在下载并校验所选前置及必需闭包。', progress={'done': 0, 'total': len(selected)})
            result = self._public(job)
            self._launch(job, self._install, sorted(selected))
            return result

    def _unchanged(self, job):
        _guard(job)
        if _environment_snapshot(job['root'], job['cancel']) != job['environment_snapshot']:
            raise ValueError('实例版本配置已变化，请重新扫描后再补全。')
        paths = _jar_paths(job['mods'])
        if {p.name for p in paths} != set(job['snapshot']):
            raise ValueError('mods 中的文件已变化，请重新扫描后再补全。')
        for path in paths:
            if _digests(path, job['cancel'])['sha256'] != job['snapshot'][path.name]:
                raise ValueError('模组文件已变化，请重新扫描：' + path.name)

    def _validate(self, job, staged, selected):
        env = job['environment']
        preferred = LOADERS[env['loader']]
        new = []
        for ref in selected:
            item = job['items'][ref]
            meta = _metadata(staged[ref], preferred)
            if preferred not in meta['loaders']:
                raise ValueError('下载文件元数据不支持 ' + preferred + '：' + item['public']['name'])
            top = [c for c in meta['components'] if not c.get('nested')]
            if top and all(c.get('environment') == ('client' if job['side'] == 'server' else 'server') for c in top):
                raise ValueError('下载文件元数据不支持当前运行侧。')
            new.append({**meta, 'key': ref, 'name': item['public']['name'], 'active': True})
        providers = defaultdict(list)
        disabled = set()
        for mod in job['local'] + new:
            for component in mod['components']:
                ids = [component['id']] + list(component.get('aliases') or [])
                if not mod['active']:
                    disabled.update(ids)
                    continue
                if component.get('environment') == ('client' if job['side'] == 'server' else 'server'):
                    continue
                for target in ids:
                    providers[target].append((mod, component))
        for mod in new:
            for component in mod['components']:
                if component['id'] in disabled:
                    raise ValueError('待安装组件已有停用文件，不能重复安装：' + component['id'])
                if len({m['key'] for m, _ in providers[component['id']]}) > 1:
                    raise ValueError('组件重复，不能自动安装：' + component['id'])
        # Validate originals which require the selected projects, and each new JAR.
        origins, queue = set(), list(selected)
        while queue:
            for parent in job['parents'].get(queue.pop(), set()):
                if parent in job['items'] and parent not in selected:
                    continue
                if parent not in origins:
                    origins.add(parent)
                    queue.append(parent)
        new_ids = {ident for mod in new for c in mod['components'] for ident in [c['id']] + list(c.get('aliases') or [])}
        for mod in new + [m for m in job['local'] if m['active']]:
            for dep in mod['dependencies']:
                if dep['side'] not in ('BOTH', job['side'].upper()) or dep['type'] not in ('required', 'incompatible'):
                    continue
                target, rule = dep['target'], dep['range']
                # Unrelated pre-existing missing dependencies must not block a useful
                # addition, but every existing incompatibility/new-provider range does.
                if mod['key'] not in selected and mod['key'] not in origins and not (target in new_ids):
                    continue
                if target in scanner.BASE_IDS:
                    if target == 'java':
                        continue  # Java runtime is chosen at launch; never install it here.
                    version = env.get(target)
                    if target in {'forge', 'neoforge', 'fabricloader'} and target != LOADER_KEYS[env['loader']]:
                        result = False
                    else:
                        result = scanner.matches(version, rule, dep['loader']) if version else (True if str(rule) in ('', '*') else None)
                    if dep['type'] == 'required' and result is not True:
                        raise ValueError('基础环境版本无法确认或不满足：' + target + ' ' + str(rule))
                    if dep['type'] == 'incompatible' and result is not False:
                        raise ValueError('基础环境存在不兼容声明：' + target)
                    continue
                values = [scanner.matches(c['version'], rule, dep['loader']) for _, c in providers.get(target, [])]
                if dep['type'] == 'required' and True not in values:
                    raise ValueError('JAR 核对仍缺少匹配的必需组件：' + target + ' ' + str(rule))
                if dep['type'] == 'incompatible' and values and (True in values or None in values):
                    raise ValueError('JAR 声明不兼容的组件：' + target)
        return new

    def _install(self, job, selected):
        self._unchanged(job)
        for ref in selected:
            target = job['mods'] / job['items'][ref]['public']['fileName']
            if target.exists() or target.is_symlink():
                raise ValueError('目标文件已存在，不会覆盖：' + target.name)
        # The staging directory stays on the same volume for atomic no-clobber commits.
        staging = Path(tempfile.mkdtemp(prefix='.damn-prerequisites-', dir=job['mods']))
        job['staging'] = staging
        _plain_path(staging)
        staging_identity = (staging.stat().st_dev, staging.stat().st_ino)
        job['staging_identity'] = staging_identity
        staged = {}
        staged_hashes = {}
        for index, ref in enumerate(selected):
            _cancel(job['cancel'])
            _guard(job)
            item = job['items'][ref]
            path = staging / (str(index) + '.jar')
            if item['public']['sourceSite'] == 'CurseForge':
                download_file(item['url'], path, item['public']['bytes'], item['hashes'], job['cancel'], cf_key=self.cf_key_getter() or '')
            else:
                download_file(item['url'], path, item['public']['bytes'], item['hashes'], job['cancel'])
            # The downloader is independently rechecked before metadata parsing/commit.
            if path.stat().st_size != item['public']['bytes']:
                raise ValueError('暂存文件大小与平台不一致。')
            with path.open('rb') as stream:
                digests = {name: hashlib.new(name) for name in item['hashes']}
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    _cancel(job['cancel'])
                    for digest in digests.values():
                        digest.update(chunk)
            if any(digests[name].hexdigest() != value for name, value in item['hashes'].items()):
                raise ValueError('暂存文件哈希与平台不一致。')
            staged[ref] = path
            staged_hashes[ref] = _digests(path, job['cancel'])['sha256']
            self._update(job, progress={'done': index + 1, 'total': len(selected)})
        self._update(job, phase='validating', message='正在核对 JAR 组件、版本范围与完整必需关系。')
        validated = self._validate(job, staged, selected)
        self._unchanged(job)
        self._update(job, phase='installing', message='校验通过，正在添加到 mods 目录。', progress={'done': 0, 'total': len(selected)})
        completed = 0
        for group in _commit_groups(selected, job['graph']):
            _cancel(job['cancel'])
            preflight = {}
            for ref in group:
                path = _plain_path(staged[ref])
                before = path.stat()
                if _digests(path, job['cancel'])['sha256'] != staged_hashes[ref]:
                    raise ValueError('已核对的暂存文件发生变化，已停止安装。')
                after = path.stat()
                identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                if identity != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns):
                    raise ValueError('核对期间暂存文件发生变化，已停止安装。')
                preflight[ref] = identity
            _cancel(job['cancel'])
            # A cycle is committed as a short group without cancellation between
            # members. Disk/path failures still stop immediately and are reported.
            for ref in group:
                _guard(job)
                _plain_path(staging)
                if (staging.stat().st_dev, staging.stat().st_ino) != staging_identity:
                    raise ValueError('临时目录发生变化，已停止安装。')
                path = staged[ref]
                target = job['mods'] / job['items'][ref]['public']['fileName']
                _plain_path(path)
                current = path.stat()
                if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != preflight[ref]:
                    raise ValueError('已核对的暂存文件发生变化，已停止安装。')
                # Both platform branches fail if a destination already exists.
                _commit_file(path, target)
                # Do not check cancellation between adding the file and recording it.
                job['snapshot'][target.name] = staged_hashes[ref]
                local = next(m for m in validated if m['key'] == ref)
                local.update(path=target, file=target.name, enabled=True)
                job['local'].append(local)
                job['items'][ref]['public'].update(status='installed', reason='已通过来源哈希和 JAR 元数据核对，添加到 mods。')
                completed += 1
                self._publish(job)
                self._update(job, progress={'done': completed, 'total': len(selected)})
        resolved_ids = {ident for mod in job['local'] if mod['active'] for c in mod['components'] for ident in [c['id']] + list(c.get('aliases') or [])}
        self._update(job, unresolved=[row for row in job['state']['unresolved'] if row['target'] not in resolved_ids])
        self._update(job, status='complete', phase='complete', message='所选前置及其必需关系已补全；请通过启动游戏确认运行结果。')
