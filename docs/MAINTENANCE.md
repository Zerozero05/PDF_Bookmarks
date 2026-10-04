# 版本维护与本地文件管理

正式源代码以 [Zerozero05/Zotero_PDF_Bookmarks](https://github.com/Zerozero05/Zotero_PDF_Bookmarks) 为准，正式 Windows 下载放在 [Releases](https://github.com/Zerozero05/Zotero_PDF_Bookmarks/releases)。本次迁移保留 v1.4.1 的应用代码、设置格式、目录 JSON 格式和已有功能，只整理仓库、文档和自动构建流程。

## 后续升级流程

1. 向 Codex 提供仓库链接，说明修改需求及必须保留的功能。开始前读取当前 `VERSION`、`README.md`、`CHANGELOG.md`、`AGENTS.md` 和相关代码，以仓库最新状态为基础修改。
2. 在独立分支完成必要修改，增加相应回归验证，更新版本与说明。先生成可供本地试用的 Windows EXE；可本地打包，也可下载 GitHub Actions 的构建产物。
3. 用户试用、提出调整并确认结果。确认前可以继续修复、测试和准备发布材料，不推送正式版本标签。
4. 用户明确确认发布后，合入经过检查的代码，推送与 `VERSION` 一致的 `v版本号` 标签。发布流程再次测试和打包，创建 GitHub Release，上传 GUI、CLI、完整 ZIP 和 `SHA256SUMS.txt`。
5. 核对 Release 的版本、文件清单、下载和校验值后，让用户选择保留或删除本地旧 EXE。删除选择与发布确认分开，发布不会自动删除本地文件。

本次已明确授权的首次迁移可以按迁移任务完成上传和初始化；以上确认流程用于后续新版本。不要把“可以升级”理解为所有未来版本均已批准发布。

## GitHub Actions 的用途

工作流为 [windows-build.yml](../.github/workflows/windows-build.yml)。普通提交、PR 和手工运行会在 Windows x64、Python 3.12 环境中安装固定版本依赖，运行测试，再构建 GUI 与 CLI。成功产物保留 30 天，适合试用，不能代替正式 Release。

在仓库的 [Actions](https://github.com/Zerozero05/Zotero_PDF_Bookmarks/actions/workflows/windows-build.yml) 页面选择一次成功运行，下载对应构建产物。构建失败时查看失败步骤并修复，不把未通过的产物当作正式版本。

正式发布由版本标签触发，标签须与根目录 `VERSION` 一致。已有同名 Release 不覆盖；需要修复已发布版本时递增版本，保留旧版本和历史记录。工作流打包所需模型、运行库和许可文件，不处理用户文献，不访问 Zotero 库。

`VALIDATION.md` 保留迁移前的本地验证记录。GitHub Actions 每次运行的结果以对应运行页面为准；加入工作流本身不代表云端已验证通过。

## 本地开发与验证

需要 Windows x64、Python 3.12，并保留 Python 的 pip 和 Tcl/Tk。以下命令均在仓库根目录运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\build_exe.cmd
```

`build_exe.cmd` 会运行测试并构建两个 EXE，输出到 `dist`。PDF 写入、备份、缓存及删除 JSON 的测试必须使用临时生成的文件，不使用真实 Zotero 附件。按涉及的功能进行预览、写入和界面检查，具体已有验证边界见 [VALIDATION.md](../VALIDATION.md)。

## GitHub 与本地占用

GitHub 可以保存正式源码、版本历史和发布包；GitHub Actions 可以在云端打包，减少本机虚拟环境、模型和构建临时文件的占用。

这减少的是**本地磁盘占用**。本机下载的 EXE、解压项目、Python 环境及临时文件仍占磁盘；EXE 运行时仍需本机内存。单文件 EXE 运行时也会解压运行库到临时目录。程序关闭后不会因为仓库放到 GitHub 就持续免除全部磁盘占用。

## 清理旧文件

先确认远端源码已上传，正式 Release 可下载，完整 ZIP 和校验值可核对，再整理本地副本。建议保留一个当前常用 EXE，其余选择取决于是否需要本地开发或回退。

| 本地内容 | 可选择的处理方式 |
| --- | --- |
| 旧版本 EXE、旧发布 ZIP | 远端版本完整并能下载后，可按版本逐个删除，也可保留用于回退 |
| 项目 `.venv`、`build`、PyInstaller 中间文件 | 不再本地开发或打包时可删除；需要时重新安装或构建 |
| 已验证上传的重复源码副本 | 保留仓库工作副本或远端版本后，按确认的路径删除重复副本 |
| 当前常用 EXE | 通常保留一份；删除后可从 Releases 重新下载 |
| `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json` | 保留即可记住设置；删除会重置设置 |
| Zotero 原 PDF、数据库、批注、PDF 备份及仍需使用的目录 JSON | 不属于项目迁移清理范围 |

执行清理前列出具体绝对路径、用途和总大小，由用户确认删除范围；不要搜索所有 `.json`、`.pdf` 或聊天目录后批量删除。清理项目临时文件不能扩大到 Zotero `storage`、用户文献目录、其他项目或 Codex 的共享数据。

只有明确授权的路径可以删除。本地文件整理不能删除远端历史版本；发布流程也不执行本地清理。
