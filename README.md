# DAMN

Minecraft 模组依赖网络与整合包静态分析工具。

这是 **0.5.6 部分源码公开版**，用于学习、检查和非商业修改。它是可运行的独立源码目录，不包含完整应用的所有实现。项目代码由 AI 工具参与编写；用户负责需求、取舍、测试反馈与发布决定，不将其表述为纯人工独立编写。

## 能做什么

- 读取本地实例 / mods 目录，以及 ZIP、MRPACK 文件。
- 展示模组清单、文件声明的依赖关系和静态检查结果。
- 查看依赖网络，核对前置候选与文件身份。
- 匹配联网资料，并在自行配置后使用兼容 Chat Completions 的 AI 服务。
- 使用内置的六项虚构示例查看界面；示例不含真实整合包或作者本机路径。

静态分析结果需要结合实际版本、加载器和游戏运行情况核对，不代表已经启动测试。文件名推断、平台资料和 AI 关联与文件声明分开展示。

## 快速运行

需要 Python 3.11 或更新版本。浏览器模式只使用 Python 标准库，无须安装第三方 Python 包。

在此目录打开终端并运行：

```text
python -X utf8 server.py
```

Windows 也可双击 start-DAMN.cmd。启动后打开本机页面；关闭终端即可停止服务。默认使用 8768 端口，端口被其他程序占用时会另选可用端口。只监听 127.0.0.1，不是可直接放到公网的 Web 服务。

可选的 Windows 独立窗口入口：

```text
python -m pip install -r requirements-desktop.txt
python -X utf8 desktop.py
```

桌面入口还需要 Microsoft Edge WebView2 Runtime。此源码包不附 Python、WebView2 或 EXE；系统及依赖安装说明见 [运行说明](docs/RUNNING.md)。

## 设置与数据

公开版默认使用 %LOCALAPPDATA%/DAMN-Public/.damn-public-user，与完整应用的设置分开。可使用 DAMN_PUBLIC_DATA_DIR 环境变量或 --data-dir 指定其他开发数据目录。

源码不包含 API Key。AI 是可选功能，请填写自己的地址、模型和密钥；调用费用由对应服务商计算。保存设置不会自动发起 AI 分析。默认开启扫描后的联网补全；可在“设置 → 联网资料”关闭。开启时会向平台发送模组名称、哈希和平台 ID；配置可用 AI 后，补全流程也可能调用 AI。Windows 下密钥由当前用户的 DPAPI 保护；其他系统仅在本次会话中保留密钥。扫描目录、报告和设置不要上传到仓库。

## 公开范围

保留常规模组分析、联网资料适配、AI 接口、桌面窗口、界面和相关测试。

- 外观固定为默认森林绿色。
- 不含私人主题、解锁条件、彩蛋、赞助激活、设备绑定、签发器或私钥。相应后端占位接口明确返回不可用。
- 不含官方更新 / 通知服务。更新界面只保存本地偏好，检查与安装操作不可用。
- 不含角色资源与交互、历史配置、真实扫描报告、构建缓存或旧发行包。
- 分类数据独立按 Modrinth 官方分类建立扁平类别，不附原有截图派生层级或 CurseForge 数字映射表。

文件范围以 [SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) 为准。来源、参考和权利边界见 [来源说明](THIRD-PARTY-NOTICES.md) 与 [发布状态](PUBLICATION-STATUS.txt)。

## 开发与检查

版本号统一来自 app_info.py。HTML 和启动画面通过 __VERSION__ 占位符取得版本，不要分别写死。

静态资源已提供，可直接运行。修改界面分层源文件后，用 Node.js 18 或更新版本重建：

```text
node tools/assemble.mjs
node tools/assemble.mjs --check
python -B -X utf8 -m unittest discover -s . -p "test_*.py"
node tools/check-frontend.mjs
```

浏览器界面没有 npm 安装步骤。Node.js 用于资源重建和 JavaScript / 分类交叉检查。测试使用临时目录、虚构数据和模拟服务；实际平台响应、付费 AI 与桌面环境需另外验证。

## 使用与分发规则

本项目采用自定义 [DAMN 源码非商业使用与分发许可 1.0](LICENSE.txt)，对明确适用且授权方有权授权的部分生效。允许非商业学习、修改和免费分享；不授予商业使用权。对外发布的衍生软件应提供对应受许可源码，名称以 DAMN 开头、添加修改后缀并标注非官方修改版，主配色固定为本版默认绿色。完整条件以许可原文为准。

这属于“部分源码公开，非商业使用许可”，不是 MIT / GPL，也不作符合 OSI 开源定义的声明。许可不创造原本不存在的著作权，不替代第三方许可。

第一次使用 GitHub，可看 [建仓库与上传指南](docs/GITHUB-FIRST-UPLOAD.md)。
