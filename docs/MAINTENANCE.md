# 版本维护与本地文件管理

正式源代码以 [Zerozero05/PDF_Bookmarks](https://github.com/Zerozero05/PDF_Bookmarks) 为准，正式 Windows 下载放在 [Releases](https://github.com/Zerozero05/PDF_Bookmarks/releases)。PDF_Bookmarks 可独立处理普通 PDF，也适配 Zotero 附件。当前源码版本为 v1.5.0，增加事务自动更新；正式发行版仍保留 v1.4.1，先试用、确认后再发布新版本。原设置位置、目录 JSON 格式、CLI 参数、PDF 写入与备份默认值继续兼容。

## 后续升级流程

1. 向 Codex 提供仓库链接，说明修改需求及必须保留的功能。开始前读取当前 `VERSION`、`README.md`、`CHANGELOG.md`、`AGENTS.md` 和相关代码，以仓库最新状态为基础修改。
2. 在独立分支完成必要修改，增加相应回归验证，更新版本与说明。先生成可供本地试用的 Windows EXE；可本地打包，也可下载 GitHub Actions 的构建产物。
3. 用户试用、提出调整并确认结果。确认前可以继续修复、测试和准备发布材料，不推送正式版本标签。
4. 用户明确确认发布后，合入经过检查的代码，推送与 `VERSION` 一致的 `v版本号` 标签。发布流程再次测试、构建两种 GUI、CLI 和外部 updater，生成 Portable 清单、更新 manifest 与校验文件；真实冻结更新验收通过后创建草稿 Release，上传并核对全部资产后才转为正式发布。按下方命名规则检查标题、文件名和校验清单，不覆盖已有同名 Release。
5. 核对 Release 的版本、文件清单、下载和校验值后，让用户选择保留或删除本地旧 EXE。删除选择与发布确认分开，发布不会自动删除本地文件。

此前已授权的首次迁移已完成上传和初始化；本次另经用户确认调整仓库名称、介绍和发布文件名。以上确认流程用于后续新版本。不要把“可以升级”理解为所有未来版本均已批准发布。

用户明确授权时，可仅向现有版本追加不同打包形式，应用版本号保持不变；不得移动原标签或替换原程序包。此前 v1.4.1 仅追加便携 ZIP 和它的 `.zip.sha256`，原三个程序包及 `SHA256SUMS.txt` 保留；本次只重命名下载资产并同步校验文件中的名称，不重建程序、不移动标签。未来新版本由自动发布流程生成包含便携版的总校验文件。

## 发布命名与校验清单

仓库名为 `PDF_Bookmarks`。发行版标题只使用版本号，例如 `v1.4.1`，与现有版本标签一致；文件名采用 `PDF_Bookmarks_<版本>_<系统>_<架构>[_类型].<扩展名>`，各部分使用下划线连接。Windows x64 用 `win_x64`；图形界面单文件版省略类型，其他包使用 `cli`、`portable`、`full` 区分。

| 构建或此前发布文件名 | v1.4.1 发布页文件名 |
| --- | --- |
| `ZoteroPDFBookmarks-v1.4.1.exe` | `PDF_Bookmarks_v1.4.1_win_x64.exe` |
| `ZoteroPDFBookmarks-CLI-v1.4.1.exe` | `PDF_Bookmarks_v1.4.1_win_x64_cli.exe` |
| `ZoteroPDFBookmarks-Portable-v1.4.1.zip` | `PDF_Bookmarks_v1.4.1_win_x64_portable.zip` |
| `ZoteroPDFBookmarks-Windows-x64-v1.4.1.zip` | `PDF_Bookmarks_v1.4.1_win_x64_full.zip` |
| `ZoteroPDFBookmarks-Portable-v1.4.1.zip.sha256` | `PDF_Bookmarks_v1.4.1_win_x64_portable.zip.sha256` |
| `SHA256SUMS.txt` | `SHA256SUMS.txt` |

上表记录已保留的 v1.4.1 下载名称。v1.5.0 及后续构建自动采用同一外部命名规则，无需发布后手工改名；内部主入口为 `PDF_Bookmarks.exe`，Portable 根目录为 `PDF_Bookmarks`。旧 Release 内部名称与字节不修改，设置路径仍为 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`。

每个新正式版本至少包含两种 GUI 更新资产及 `update-manifest.json`；本项目另外继续提供 CLI、完整源码 ZIP、`SHA256SUMS.txt` 和 Portable 独立校验文件。例如 v1.5.0 对应 `PDF_Bookmarks_v1.5.0_win_x64.exe` 与 `PDF_Bookmarks_v1.5.0_win_x64_portable.zip`。`update-manifest.json` 的 `assets.single` 与 `assets.portable` 分别包含文件名、完整 SHA-256 和字节数；Portable 包内每个程序文件同样记录大小与 SHA-256。

只重命名 EXE/ZIP 的外部文件名不会改变其字节或 SHA-256。同步更新下载链接、`SHA256SUMS.txt` 与便携 `.zip.sha256` 内容中记录的文件名，保留对应的原校验值；校验文件自身的内容会因此改变。若将来重新打包或修改任何程序包内容，则必须重新计算该文件的校验值，不能沿用本次哈希。上传后按最终文件名下载并检查校验结果。

## GitHub Actions 的用途

工作流为 [windows-build.yml](../.github/workflows/windows-build.yml)。main 提交、PR 和手工运行在 Windows x64、Python 3.12 环境中安装固定版本依赖，先运行 PDF/GUI、更新事务、网络和配置回归，再构建外部 updater、Single/CLI 单文件版与 Portable。随后检查嵌入身份、资源、哈希和真实冻结更新/回滚，生成两种 GUI 资产与 manifest；成功产物保留 30 天，适合试用，不能代替正式 Release。

在仓库的 [Actions](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml) 页面选择一次成功运行，下载对应构建产物。构建失败时查看失败步骤并修复，不把未通过的产物当作正式版本。

冻结更新失败时，另保存 `frozen-update-diagnostics-<run_id>` 诊断产物 14 天，包含 `build/frozen_*.json` 中的测试报告、journal 与错误信息；没有生成诊断文件则不上传。诊断上传不会使失败构建变成通过，也不属于正式发行资产。

正式发布由版本标签触发，标签须与根目录 `VERSION` 一致。构建或任何检查失败均不发布；发布 job 下载经过验证的构建，再核对文件集合、SHA-256、两种 manifest 资产、上传名称和大小，然后将完整草稿发布。已有同名 Release 不覆盖；应用功能修复须递增版本，保留旧版本和历史记录。经明确授权的同版本打包形式追加按上面的规则操作。工作流打包所需模型、运行库和许可文件，不处理用户文献，不访问 Zotero 库。

发布前执行 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)，对应自动验收见 [UPDATE_ACCEPTANCE.md](UPDATE_ACCEPTANCE.md)。每次判断配置字段的结构、类型与语义是否改变；仅新增有默认值的可选设置无需提升 schema。当前 `CONFIG_SCHEMA=1`，生产迁移列表为空。需要结构迁移时逐级增加迁移及样本，验证失败原文件保护和程序/配置同步回滚。版本的唯一人工来源是根目录 `VERSION`，不要分别手改 workflow、About 或 manifest 版本。

`VALIDATION.md` 保留本地验证记录，并记录首次迁移已完成的云端测试与发布包下载验证。GitHub Actions 后续每次运行的结果仍以对应运行页面为准，不能把首次通过当作所有未来版本都已通过。

## 本地开发与验证

需要 Windows x64、Python 3.12，并保留 Python 的 pip 和 Tcl/Tk。以下命令均在仓库根目录运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\build_exe.cmd
```

`build_exe.cmd` 会运行测试，调用 `scripts/build_windows.py` 构建独立 updater、Single（`dist\PDF_Bookmarks.exe`）、CLI（`dist\PDF_Bookmarks_CLI.exe`）和 Portable（`dist\portable\PDF_Bookmarks\PDF_Bookmarks.exe` 及完整运行文件夹）。`scripts/package_release.py` 从已加入 Git 管理的源码生成完整包、便携包、manifest 和校验清单；不要把用户配置或已运行生成的 `.pdf_bookmarks` 放进分发包。PDF 写入、备份、缓存、删除 JSON 和更新回滚测试必须使用临时生成的文件，不使用真实 Zotero 附件或用户配置。已有验证见 [VALIDATION.md](../VALIDATION.md)，本次更新验证见 [UPDATE_ACCEPTANCE.md](UPDATE_ACCEPTANCE.md)。

`scripts/build_windows.py --test-version 1.5.1` 仅用于合成新版更新验收，产物隔离在 `dist\test_v1.5.1`，不能进入当前生产版本的正式资产。该参数不修改 `VERSION`。真实冻结验收必须核对改名后的目标 EXE 内容与 BuildInfo、GUI/config/core 健康回执、受管理文件/配置恢复和事务目录清理，不能以“进程启动了”代替。

## GitHub 与本地占用

GitHub 可以保存正式源码、版本历史和发布包；GitHub Actions 可以在云端打包，减少本机虚拟环境、模型和构建临时文件的占用。

这减少的是**本地磁盘占用**。本机下载的 EXE、解压项目、Python 环境及临时文件仍占磁盘；EXE 运行时仍需本机内存。单文件 EXE 运行时也会解压运行库到临时目录；便携文件夹版直接使用旁边的运行库，须保留整个文件夹，主要省去启动解包，不保证每页 OCR 或 PDF 写入提速。两种 GUI 的设置均保存在 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`。程序关闭后不会因为仓库放到 GitHub 就持续免除全部磁盘占用。

## 清理旧文件

自动更新事务只清理本 APP_ID 创建、状态已完成且归属验证通过的临时内容；不需要用户逐文件处理。Portable 旧文件删除权来自旧 installed-manifest，未知文件保留。这与下述用户自行保存的历史 EXE、开发环境和文献整理范围分开；更新器不清空整个程序目录或共享临时目录。

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
