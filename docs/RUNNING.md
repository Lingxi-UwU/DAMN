# 从源码运行

## 最少准备

1. 安装 Python 3.11 或更新版本，并允许其加入 PATH。
2. 解压源码目录，确认 server.py、static 和 taxonomy.json 在同一目录层级。
3. Windows 双击 start-DAMN.cmd，或在目录内运行 python -X utf8 server.py。
4. 首次 AI 配置可以选择“稍后，先用本地分析”。
5. 可加载内置虚构示例，或自行导入目录 / ZIP / MRPACK。

本地分析无须 API Key。联网资料和 AI 是独立的可选操作，需要网络及使用者自己的服务设置；它们可能向对应服务提交所选模组元数据或分析上下文。请先核对操作和服务商条件。

## 桌面窗口

Windows 用户可运行 python -m pip install -r requirements-desktop.txt 后双击 start-DAMN-desktop-dev.cmd。需要安装 Microsoft Edge WebView2 Runtime。窗口无系统黑色标题栏、不可最大化，保持桌面应用入口。此包仅提供源码，不含预编译 EXE。

[Python 下载](https://www.python.org/downloads/) · [WebView2 下载](https://developer.microsoft.com/microsoft-edge/webview2/)

## 数据位置

默认数据根目录为 %LOCALAPPDATA%/DAMN-Public，配置子目录为 .damn-public-user。不要把它提交到 GitHub。开发时可运行 python -X utf8 server.py --port 8769 --data-dir 某个临时目录 --no-browser，以独立端口和配置测试。

这套本地 HTTP 接口只监听 127.0.0.1，并使用会话令牌。不要直接改为监听公网 IP；源码包不是赞助激活服务或服务器部署包。

## 常见问题

- 找不到 python：安装 Python 并加入 PATH，再重新打开终端。
- 首次配置没有密钥：选择稍后，不影响本地扫描。
- 官方更新不可用：这是公开版保留的界面与本地偏好，不包含官方服务实现。
- 分类和完整应用不同：公开版采用独立的官方扁平分类快照，不附原分类层级和数字映射。
- 桌面模式打不开：先确认浏览器模式可运行，再检查 Python、pywebview 和 WebView2；公开版数据根目录中会记录 desktop.log。日志仅保留本机，提交问题前自行检查其中信息。
