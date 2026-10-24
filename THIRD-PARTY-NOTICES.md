# 来源与第三方说明

## DAMN 代码与资源

本包中的 Python、JavaScript、HTML、CSS、测试、构建脚本及 DAMN 视觉资源来自 DAMN 开发过程，并包含 AI 工具编写及修改的内容。未将“由 AI 生成”理解为著作权已确认或能够替所有内容授权。明确文件范围和适用说明记录在 SOURCE-MANIFEST.json。

## 分类数据

taxonomy.json 在此公开版中独立重建：以 [Modrinth 官方分类接口](https://api.modrinth.com/v2/tag/category) 中 project_type=mod 的原始分类名为依据，使用直接中文名称、扁平排列及重新编写的常规关键词规则。快照时间、原始 slug 和说明保留在 JSON 元数据。官方接口说明：[Category list](https://docs.modrinth.com/api/operations/categorylist/)。

原完整项目曾参考用户提供的 PCL2 截图与公开分类映射。此包不附那套父子层级、选择编排或 CurseForge 数字分类映射表。类别名称等平台事实及一般分类思想不被声明为 DAMN 专有表达。平台数据及其使用仍须遵守平台适用条款。

## 设计参考

设置分栏、分类呈现、修改版区分和公开 / 私有边界曾参考 PCL 的产品组织思路；界面还受到 Apple、Microsoft 和 Duolingo 的交互风格启发。这些是来源说明，不表示相应项目参与、认可或为 DAMN 背书，也不以参考为由取得其代码、商标或专属资源的使用权。

公开代码保留了既有开发注释中的设计来源记录。包内未附 PCL 的 VB 源文件或它的许可文本作为 DAMN 的许可证。参考：[PCL 仓库](https://github.com/Meloong-Git/PCL)，[此前规则参考版本](https://github.com/Meloong-Git/PCL/blob/93ede5d9e638c99fcec853a9ba1eecd91ceee7f5/LICENCE)。

## 分别安装的依赖

- 浏览器模式使用 Python 3.11+ 标准库；Python 依其自身许可提供。
- Windows 桌面模式可另行安装 pywebview==6.2.1（BSD 3-Clause）及其依赖，并使用 Microsoft Edge WebView2 Runtime。它们不被 DAMN 的非商业条款重新授权。参考：[pywebview](https://github.com/r0x0r/pywebview)、[WebView2](https://developer.microsoft.com/microsoft-edge/webview2/)。
- Node.js 只用于重建和运行前端测试，未将其运行时打进本包。

本包没有上述运行时、第三方二进制或字体文件。以后如果另行制作 EXE / 安装包，需要按实际打包内容附齐依赖许可证与通知；此说明不能代替二进制分发所需文件。

## 其他品牌及内容

Minecraft、Modrinth、CurseForge 等名称和链接用于说明兼容对象及资料来源。DAMN 非 Mojang / Microsoft 官方产品。扫描得到的模组代码、图片、说明和资料不因被 DAMN 读取而转为本许可内容；使用者应遵守各自权利与条件。
