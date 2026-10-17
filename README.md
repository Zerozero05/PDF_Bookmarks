# PDF_Bookmarks

为普通 PDF 添加多级书签，可独立使用。支持导入目录 JSON，也可从文字或扫描 PDF 生成目录，经预览与人工校对后写入，保持原 PDF 的文件名和路径不变。

同时适配 Zotero 附件：直接处理 Zotero 当前使用的 PDF 原文件，无需重新附加 PDF。具体操作见下方“在 Zotero 中使用”。

当前源码版本：**v1.7.0**，将主界面和目录工作台整合为同窗标签页，增加本地草稿恢复、撤销/重做、查找筛选与目录树，以及识别区域、分栏线和原目录行定位。面向 Windows 10/11 x64，中文界面，兼容中文文件名和书签。下载是否可用以 [Releases](https://github.com/Zerozero05/PDF_Bookmarks/releases) 的实际附件为准；[v1.6.0 历史发行版](https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v1.6.0)与更早版本继续保留。源码、版本历史和文档在本仓库管理，Windows 程序从 Releases 下载。

[下载 v1.7.0 Windows 版](https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v1.7.0) · [完整使用说明](docs/USAGE.md) · [版本记录](CHANGELOG.md) · [维护与清理流程](docs/MAINTENANCE.md) · [自动构建](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml)

两个标签页间切换会保留未完成输入、撤销历史与预览；“保存 JSON 并返回”后回主界面自动预览，PDF 写入仍需原有确认。草稿独立保存在本机，与正式 JSON 分开，恢复前核对原 PDF 身份。v1.6.0 的单/双栏选择、三种节编号、滚轮/Ctrl＋滚轮缩放及安全写入继续保留。操作见 [校对与界面说明](docs/USAGE.md#v170校对与界面完善)，各阶段验证见 [验证记录](VALIDATION.md)。

## 选择下载方式

| 下载 | 运行方式与区别 |
| --- | --- |
| [单文件 GUI EXE](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.7.0/PDF_Bookmarks_v1.7.0_win_x64.exe) | 直接运行，携带方便；每次启动需要将运行库解包到临时目录 |
| [便携文件夹版 ZIP](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.7.0/PDF_Bookmarks_v1.7.0_win_x64_portable.zip) | 解压后打开 `PDF_Bookmarks\PDF_Bookmarks.exe`；须保留同目录的 `_internal`、`package-manifest.json` 和其余文件，省去启动时的临时解包 |
| [CLI EXE](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.7.0/PDF_Bookmarks_v1.7.0_win_x64_cli.exe) | 命令行程序，适合脚本和批量处理；参数见 [使用说明](docs/USAGE.md) |
| [完整 Windows ZIP](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.7.0/PDF_Bookmarks_v1.7.0_win_x64_full.zip) | GUI/CLI 单文件 EXE、源码、测试、示例和说明；GUI 位于 `PDF_Bookmarks\dist\PDF_Bookmarks.exe` |

两种 GUI 都面向 Windows 10/11 x64，无需安装 Python，功能和版本均为 v1.7.0。便携版主要减少启动解包，不承诺每页 OCR 或 PDF 写入更快。两者共用 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`，切换时继续沿用设置；“便携”指免安装，设置和本地草稿仍保存在当前电脑。

发布页下载文件统一采用 `PDF_Bookmarks_<版本>_<系统>_<架构>[_类型].<扩展名>`，各部分用下划线分隔。下载文件的校验值见 [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.7.0/SHA256SUMS.txt)，便携 ZIP 另附 [同名 .zip.sha256 文件](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.7.0/PDF_Bookmarks_v1.7.0_win_x64_portable.zip.sha256)。`update-manifest.json` 供程序检查更新使用，无需手动运行。

历史 [v1.4.1 发行版](https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v1.4.1)及其文件保持不变，旧 ZIP 内部名称仍为 `ZoteroPDFBookmarks`。v1.5.0 及后续包内采用 `PDF_Bookmarks.exe`，继续沿用原设置路径。

## v1.7.0 校对与界面更新

- **同一窗口两个标签页**：普通切换保留当前编辑、撤销历史和预览；关闭工作台后回主界面，顶部标签可重开。保存 JSON 成功后回主界面自动预览，识别、载入、保存与主界面处理任务互锁。
- **本地未完成草稿**：约1200毫秒停顿后自动暂存，也可手动暂存/恢复；草稿保留未确认条目和未完成输入，PDF 路径、大小或修改时间不符时拒绝恢复。正式 JSON 仍须确认后导出。
- **校对工具**：最多80步撤销/重做，标题查找、待确认/低可信/未知页码筛选、下一待核对和目录树；不改变原目录顺序、层级及页码。
- **预览与人工辅助识别**：增加原目录行定位、适合宽度/整页、翻页和折叠映射；可逐页框选目录区域、设置栏线后重新识别，修复人工分栏时宽白边造成的漏行。
- **资源释放**：合并过期渲染，关闭时释放预览图片、排队结果、历史和自有回调，修复快速关闭与取消读取后的界面生命周期问题；不承诺固定内存降幅。

### 继续保留的目录识别与编号规范

- **双栏目录**：按完整左栏、再完整右栏读取，减少同一行两栏标题/页码混在一起；按栏补充 OCR，章节上下文跨栏、跨页继续，栏位置不直接作为层级。
- **手选布局**：识别前可选“自动”“单栏”“双栏”。自动判断不理想时，手选布局并重新识别；页码范围仍填写实际 PDF 页。
- **节编号**：新自动目录按所选方式规范，默认 `1.1 基本概念`，可选每章独立的 `1. 基本概念` 或“保留识别编号”；修正已有节号重复补号。继续使用编号与标题间一个空格、去除数字前 `§` 的规则；切换保护手工标题，不改变层级和页码。
- **预览交互**：目录工作台右侧支持滚轮上下滚动，新增“放大”“缩小”“100%”及 Ctrl＋滚轮缩放，范围50%–300%。
- 保留 v1.5.1 的文字方向比较、短标题重读、书末独立条目和人工确认保护；JSON/CLI、原设置位置和 PDF 安全写入机制继续兼容。新选项只用于当前工作台，不新增持久设置。

详细变化见 [版本记录](CHANGELOG.md)，验证范围与局限见 [验证记录](VALIDATION.md)。

## 程序更新

v1.5.0 的 Single 与 Portable GUI 增加“帮助 / 更新”：显示当前版本、发行类型、更新内容和下载大小。启动后最多每 24 小时后台检查一次，也可立即手动检查；下载后须由用户选择“安装并重新启动”，不强制退出正在处理 PDF 的程序。请先保存目录编辑、关闭目录工作台并等待写入、识别和预览任务完成。

更新保持当前发行类型、实际 EXE 文件名和文件夹位置；改名、中文/空格路径、移动整个便携文件夹均支持。Portable 仅更新清单中受管理的程序文件，清除废弃运行库，保留用户 PDF、配置和未知文件。新版完成配置、PDF 核心和主窗口健康检查后才提交；失败时同步恢复旧程序与旧配置。

**v1.4.1 没有更新器，第一次升级须手动下载 v1.7.0。** 关闭旧程序后从发行版页面下载：Single 运行新 EXE 即可；Portable 须完整解压新文件夹，保留 `_internal` 与 `package-manifest.json`。两者设置仍在 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`，无需重新设置。源码运行和 CLI 不执行 GUI 自身更新。

机制与故障处理见 [自动更新说明](docs/AUTO_UPDATE.md)，逐项验证记录见 [更新验收矩阵](docs/UPDATE_ACCEPTANCE.md)。

## 快速使用

1. 按上表选择单文件 GUI 或便携文件夹版；需要 CLI、源码与说明时下载完整 Windows ZIP。便携版解压后运行，不能只复制其中的 EXE。
2. 找到要处理的 PDF 原文件，关闭占用该文件的阅读窗口。
3. 把原 PDF 和对应的 `书名.toc.json` 拖进程序。没有 JSON 时，点“生成 / 编辑目录…”，选择目录页范围、目录布局与节编号，再识别、校对并保存；默认使用自动布局和章.节编号。
4. 点“1. 预览”，检查书签层级、标题和右侧实际目标页。勾选要处理的 PDF，设置写入选项，点“2. 写入勾选的 PDF”。更改输入或写入选项后须重新预览。
5. 用 PDF 阅读器重新打开原文件，查看新增书签。

程序添加 PDF 内部的 Outline / Bookmarks，不插入正文目录页。多本文件按文件名配对，详细配对、恢复与刷新说明见 [使用说明](docs/USAGE.md)。

### 在 Zotero 中使用

在 Zotero 中右键 PDF 附件，选择“显示文件”，找到实际原文件并关闭该 PDF 的阅读窗口，再按上述步骤处理。完成后回到 Zotero，重新打开同一个附件即可查看书签，无需重新附加 PDF。存储附件可递归处理 `storage`，链接附件可直接处理实际链接指向的文件。

使用可选的茉莉花缓存清理时，处理前须完全退出 Zotero，处理后再启动。该选项默认关闭，与删除输入目录 JSON 是两个独立选项。

## 功能与默认设置

| 功能 | 行为 |
| --- | --- |
| 目录生成与编辑 | 文字提取、本地中英文 OCR；自动/单栏/双栏、逐页区域/栏线、三种节编号、人工确认与批量改层级 |
| 校对与草稿 | 查找筛选、目录树、最多80步撤销/重做、本机未完成草稿与身份核验恢复 |
| 目标页预览 | 滚轮、按钮及 Ctrl＋滚轮缩放50%–300%，适合宽度/整页、翻页与原目录行定位，只读核对 |
| 页码映射 | 固定偏移、分段映射、单项实际 PDF 页；支持章、节、小节多级书签 |
| 拖放与批量 | 拖入 PDF、JSON 或文件夹；逐本预览、勾选和显示处理结果 |
| 原地写入 | 临时副本写入、校验后原子替换；原 PDF 文件名和路径保持不变 |
| 备份 | 默认开启；留空用各 PDF 旁的 `_backup`，可选择自定义文件夹 |
| 已有书签 | 默认跳过；明确选择替换时覆盖当前整棵书签树 |
| 茉莉花缓存清理 | 默认关闭；成功写入后只清理 PDF 同目录 `jasminum-outline.json` |
| 删除输入目录 JSON | 默认关闭；成功写入后删除本次使用的 JSON，失败/跳过/预览时保留 |
| 便捷设置 | 同窗两标签保留当前状态，两页分别记住大小与置顶；处理任务互锁 |
| 命令行 | 保留预览、dry-run、单本和批量处理模式 |

自动识别结果需要核对，可信提示不是准确率保证。复杂版式、模糊扫描、罗马页码和缺页可能需要手工校正；目标页不确定时不会直接写入。OCR 在本机运行，不上传 PDF，不需要 API Key。打包版包含模型；首次从源码安装依赖需要联网。

## 源码运行与打包

推荐 Windows x64、Python 3.12，保留 pip 和 Tcl/Tk。在仓库根目录运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe gui_entry.py
```

也可以双击 `setup.cmd` 安装，再用 `launch_gui.cmd` 或 `launch_cli.cmd` 启动。Windows 本地打包使用 `build_exe.cmd`，生成 `dist\PDF_Bookmarks.exe`、`dist\PDF_Bookmarks_CLI.exe` 和 `dist\portable\PDF_Bookmarks\PDF_Bookmarks.exe` 及其完整运行文件夹；外部更新器由构建脚本先构建并嵌入两种 GUI。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

本次候选源码477项回归中476通过、1项跨盘环境测试跳过；正式1.7.0四种构建身份/资源与237项包内模块检查通过。真实冻结1.7.0→隔离合成1.7.1的Single/Portable成功升级和健康失败回滚共4场景通过，冻结CLI预览、原路径写入、原字节备份和默认跳过通过。同功能1.6.0本地试用的合成PDF实际窗口切页、校对、保存返回和最小尺寸检查通过；正式构建与前试用的26项运行源码仅VERSION变化。上一阶段实书自动/人工栏线各147项、20章、偏移+8，原PDF不变；数学符号及3项无页码前置内容仍须校对。包内模块使用宿主依赖，完整冻结GUI实书OCR和PDF写入交互未逐项实操。云端与公开附件结果以对应 [Actions](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml)、[验证记录](VALIDATION.md)和[本次发行说明](docs/RELEASE_NOTES.md)为准，本地结果不代替云端验收。

固定依赖在 `requirements.txt` 和 `requirements-build.txt`。v1.5.0 本机完整回归 303 项通过，真实冻结 Single/Portable 的成功升级和失败回滚共四个场景通过；[云端验证](https://github.com/Zerozero05/PDF_Bookmarks/actions/runs/37604195474)通过，其中一项跨盘测试因单盘环境跳过，本机已实际通过。详细结果与边界见 [UPDATE_ACCEPTANCE.md](docs/UPDATE_ACCEPTANCE.md)。原 v1.4.1 的历史验证保留在 [VALIDATION.md](VALIDATION.md)。

## 项目结构与版本发布

```text
bookmarks_core.py        PDF 校验、页码映射与原地写入
bookmarks_gui.py         主窗口与批量处理
gui_support.py          设置、配对和页面渲染
toc_generation.py        文字/OCR 识别与目录 JSON
toc_editor.py            目录工作台
editor_session.py        本地未完成草稿与有界撤销/重做
gui_entry.py             GUI 入口
bookmarks.py             CLI 入口
build_info.py            构建身份、协议与配置 schema
config_manager.py        原设置兼容、原子保存与逐级迁移
updater/                 检查、下载、清单、事务、回滚与清理
update_dialog.py          主窗口的帮助与更新入口
updater_entry.py          外部更新器入口
tests/  examples/        回归测试与示例目录
docs/                   使用说明与维护流程
licenses/               第三方许可
.github/workflows/      Windows 测试、打包与发布
VERSION                 当前发布版本
```

普通提交、PR 和手工运行生成试用构建产物。新版本先供用户本地试用，确认后再推送与 `VERSION` 一致的版本标签并发布 Release。EXE、完整 ZIP 与便携 ZIP 放在 Releases，源码仓库不保存二进制、虚拟环境、用户 PDF 或私人目录 JSON。

云端管理和打包可以减少本地开发文件的磁盘占用；下载的 EXE 仍占本机磁盘，运行时仍需本机内存。只有收到本次清理要求才执行清理；已同时要求“发布后清理”时，远端核验通过后按展示的固定路径清单执行，无需逐项重复确认。默认保留 Git 工作副本、用户 PDF/设置、共享依赖及唯一资料。流程见 [MAINTENANCE.md](docs/MAINTENANCE.md)。

## 许可

双栏识别的方法参考 [PyMuPDF 官方文字提取说明](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)与[官方多栏示例](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/text-extraction/multi_column.py)的坐标分区思路，并参考 [Docling SDK 说明](https://github.com/docling-project/docling/blob/main/docling/.agents/skills/docling/references/python-sdk.md)将布局阅读顺序和目录层级分别处理。实现根据本项目既有解析、OCR与校验接口独立编写，没有复制这些示例代码，也未引入Docling框架、新模型或新依赖。

本项目沿用 **GNU AGPL v3**，完整条款见 [LICENSE.txt](LICENSE.txt)。PyMuPDF/MuPDF 与 OCR、运行库等依赖的许可和来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [licenses](licenses)。
