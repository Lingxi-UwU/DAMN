"""Interactive local setup for the user's own CurseForge API key."""
import getpass
import sys
from server import data_directory
from app_info import USER_DATA_SUBDIRECTORY
from settings import SettingsStore


def configure_curseforge(store, prompt=None, output=print):
    prompt = prompt or getpass.getpass
    output('录入 CurseForge 官方 API Key。输入不会显示；直接回车取消。')
    try:
        key = prompt('CurseForge API Key: ').strip()
    except (EOFError, KeyboardInterrupt):
        output('已取消，未修改配置。')
        return False
    if not key:
        output('已取消，未修改配置。')
        return False
    if len(key) > 4000:
        output('密钥内容过长，未保存。')
        return False
    try:
        store.save({'platformOnly': True, 'curseForgeKey': key})
    except (ValueError, OSError):
        output('密钥未保存，请检查本机目录权限和 Windows 用户账户。')
        return False
    output('已由当前 Windows 用户加密保存。返回 DAMN 重新核对来源即可；没有发送测试请求。')
    return True


def main():
    if sys.platform != 'win32' or not sys.stdin.isatty():
        print('请在 Windows 的交互式命令窗口中运行本机配置工具。')
        return 1
    store = SettingsStore(data_directory() / USER_DATA_SUBDIRECTORY)
    return 0 if configure_curseforge(store) else 1


if __name__ == '__main__':
    raise SystemExit(main())
