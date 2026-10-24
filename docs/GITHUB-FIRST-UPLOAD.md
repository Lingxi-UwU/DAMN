# 第一次建 GitHub 仓库与上传

仓库是项目的文件夹和修改记录。首次可以只用网页，不必先学习命令。建议先设为私有，确认内容后再公开。

## 一、建立空仓库

1. 登录 GitHub，打开 https://github.com/new 。
2. Owner 选择你自己的账号。
3. Repository name 填 DAMN；若已占用，可以填 DAMN-source。
4. Description 可填：Minecraft 模组依赖网络与整合包静态分析工具。
5. Visibility 选择 Private（私有）。这不妨碍以后改成公开。
6. 不勾选自动生成 README；.gitignore 和 License 都选 None。源码包已经准备这些文件，许可证也不是 MIT / GPL。
7. 点击 Create repository。

## 二、上传解压后的文件

不要只上传 ZIP；先把它解压。进入 DAMN-public-0.5.6 目录，上传里面的内容，让 README.md 和 server.py 直接处在仓库根目录。不要把整个 DAMN-public-0.5.6 外层文件夹再套进去。

GitHub 网页单次最多 100 个文件，每个文件最多 25 MiB。本包超过 100 个文件，分三次上传即可：

1. 首次点击 uploading an existing file（或 Add file → Upload files），拖入根目录的各个文件，包括 .gitignore / .gitattributes，但暂时不选子文件夹。提交说明写“添加 DAMN 公开源码”。点击 Commit changes。
2. 再次 Add file → Upload files，拖入整个 static 文件夹，保留其目录结构。提交说明写“添加界面资源”。
3. 再上传 docs、tools 和 desktop-assets 文件夹。提交说明写“添加说明、工具和桌面资源”。

上传时使用本包，别选择 outputs/DAMN 完整开发目录。若网页显示超过 100 个文件，就分成更小批次，不要删必需文件。每一批等待上传完成再提交。

## 三、检查仓库内容

- 首页能直接显示 README。
- server.py、taxonomy.json、LICENSE.txt、SOURCE-MANIFEST.json 在根目录。
- static/index.html、tools/assemble.mjs 和 docs/RUNNING.md 都能找到。
- 没有 .damn-user、.damn-public-user、密钥、扫描报告或开发日志。

完成后可以把仓库链接给协作者检查。只有你确认公开时，再到 Settings → General → Danger Zone → Change repository visibility 改为 Public。公开仓库的内容可能被下载或派生；以后改回私有不能收回别人已经取得的副本。

## 四、以后更新

小改动仍可通过网页上传同路径文件。改动多时，建议使用 GitHub Desktop：克隆自己的仓库，将新版本源码替换进去，检查 Changes，然后 Commit 与 Push。始终从公开源码目录更新，避免把私有功能或本机配置带入。

不要勾选任何付费选项，本流程不要求开通付费套餐。

## 官方说明

- 建仓库：https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- 网页上传与数量限制：https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- 公开 / 私有切换：https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility
