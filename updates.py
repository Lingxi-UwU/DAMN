"""Public edition local preferences only; no update service is included."""
import json
import os
from pathlib import Path
import tempfile
import threading

MAX_BYTES = 4096
CHANNELS = frozenset(('stable', 'preview'))
CHECK_MODES = frozenset(('manual', 'startup'))
DEFAULTS = {'channel': 'stable', 'checkMode': 'manual'}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def parse_update_body(raw):
    """Keep these small reserved APIs strict without changing unrelated routes."""
    try:
        if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES:
            raise ValueError('invalid body')
        value = json.loads(raw, object_pairs_hook=_unique_object)
        if type(value) is not dict:
            raise ValueError('invalid body')
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('更新设置请求格式不正确。') from None


def _preferences(value):
    if (type(value) is not dict or set(value) != {'channel', 'checkMode'}
            or not isinstance(value['channel'], str) or value['channel'] not in CHANNELS
            or not isinstance(value['checkMode'], str) or value['checkMode'] not in CHECK_MODES):
        raise ValueError('请选择有效的更新通道和检查方式。')
    return {'channel': value['channel'], 'checkMode': value['checkMode']}


class UpdatePreferencesStore:
    """Own only updates.json; never read AI settings, credentials or remote URLs."""
    def __init__(self, directory, version):
        self.directory = Path(directory)
        self.file = self.directory / 'updates.json'
        self.version = version
        self.lock = threading.RLock()

    def _read(self):
        try:
            if not self.file.exists():
                return dict(DEFAULTS)
            if self.file.stat().st_size > MAX_BYTES:
                raise ValueError('invalid preferences')
            data = json.loads(self.file.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
            if (type(data) is not dict or set(data) != {'schemaVersion', 'channel', 'checkMode'}
                    or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1):
                raise ValueError('invalid preferences')
            return _preferences({'channel': data['channel'], 'checkMode': data['checkMode']})
        except (OSError, ValueError, UnicodeError, RecursionError):
            raise ValueError('更新偏好无法读取，请重新选择并保存。') from None

    def _state(self, preferences):
        return {'schemaVersion': 1, 'currentVersion': self.version, 'serviceConfigured': False,
                'status': 'not_configured', 'preferences': dict(preferences)}

    def public(self):
        with self.lock:
            return self._state(self._read())

    def save_preferences(self, preferences):
        value = _preferences(preferences)
        with self.lock:
            temporary = None
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.directory,
                        prefix='updates-', suffix='.tmp', delete=False) as stream:
                    temporary = Path(stream.name)
                    json.dump({'schemaVersion': 1, **value}, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.file)
            except OSError:
                raise ValueError('更新偏好未能保存，请重试。') from None
            finally:
                if temporary is not None:
                    try:temporary.unlink(missing_ok=True)
                    except OSError:pass
            return self._state(value)

    def check(self, body):
        if type(body) is not dict or body:
            raise ValueError('更新检查请求格式不正确。')
        state = self.public()
        return {**state, 'status': 'unavailable', 'code': 'public_feature_unavailable',
                'message': '公开源码版不包含官方更新或通知服务。'}
