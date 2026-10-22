# PDF_Bookmarks

为普通 PDF 添加多级书签，可独立使用，也适配 Zotero 附件。支持导入目录 JSON，或从文字、扫描 PDF 识别目录，经预览与人工校对后写入，保持原 PDF 文件名和路径。

当前稳定版：**v1.11.0**，已通过正式云端门禁并公开核验；下载见下方附件。支持 **Windows 10/11 x64**，中文界面，兼容中文文件名和书签。OCR 在本机运行，不上传 PDF，不需要 API Key。

[下载 Windows 版](https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v1.11.0) · [完整使用说明](docs/USAGE.md) · [查看更新](#更新日志)

## 选择下载方式

| 下载 | 运行方式与区别 |
| --- | --- |
| [单文件 GUI EXE](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64.exe) | 直接运行，便于携带；启动时会临时解包运行库 |
| [便携文件夹版 ZIP](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64_portable.zip) | 完整解压后运行 `PDF_Bookmarks\PDF_Bookmarks.exe`；保留 `_internal`、`package-manifest.json` 和其余文件 |
| [CLI EXE](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64_cli.exe) | 适合脚本与批量处理，参数见 [命令行说明](docs/USAGE.md#命令行) |
| [完整 Windows ZIP](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64_full.zip) | 含 GUI、CLI、源码、测试、示例和说明；GUI 位于 `PDF_Bookmarks\dist\PDF_Bookmarks.exe` |

两种 GUI 功能相同，无需安装 Python，共用 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json` 及本机草稿。便携版主要省去启动解包，不保证 OCR 或 PDF 写入更快；“便携”指免安装，设置与草稿仍保存在当前电脑。

下载以 [Releases 实际附件](https://github.com/Zerozero05/PDF_Bookmarks/releases)为准，校验值见 [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/SHA256SUMS.txt)；便携 ZIP 另附[独立校验文件](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64_portable.zip.sha256)。`update-manifest.json` 供程序检查更新，无需手动运行。

## 快速使用

1. 下载并运行单文件 GUI，或完整解压便携版；找到 PDF 原文件，关闭占用它的阅读窗口。
2. 拖入 PDF 和对应的 `书名.toc.json`。没有 JSON 时，切换“目录工作台 · 生成与编辑”标签，选择实际目录页范围、布局和节编号，识别后逐项校对并保存。
3. 点“1. 预览”，检查层级、标题与实际目标页；勾选要处理的 PDF，设置写入选项。
4. 点“2. 写入勾选的 PDF”。更改输入或写入选项后须重新预览；完成后重新打开原文件检查书签。

程序添加 PDF 内部书签，不插入正文目录页。按 **F1** 查看本机操作说明与快捷键表，可在表内修改常用工作台快捷键；按 Esc 关闭说明。多本配对规则与恢复方法见[完整使用说明](docs/USAGE.md)。

### 在 Zotero 中使用

右键 PDF 附件选择“显示文件”，找到原文件并关闭该 PDF 的阅读窗口，再按上述步骤处理。完成后在 Zotero 重新打开同一个附件，无需重新附加；存储附件可处理 `storage`，链接附件使用其实际文件路径。

如启用茉莉花缓存清理，处理前须完全退出 Zotero，完成后再启动；它与删除输入 JSON 是两个独立选项，默认均关闭。

<a name="v170-校对与界面更新"></a>
<a name="继续保留的目录识别与编号规范"></a>

## 功能与默认设置

| 功能 | 使用方式与保护 |
| --- | --- |
| 目录识别与编辑 | 文字提取、本地中英文 OCR；自动/单栏/双栏布局、逐页区域与栏线、三种节编号、人工确认及批量改层级 |
| 校对与草稿 | 默认 Enter 确认并下一项、Ctrl+F 查找、F2 改标题、Ctrl+L 定位页码；v1.11.0 增加 Ctrl+N 添加及 Alt+↑/↓ 移动，15项常用工作台快捷键可在 F1 中自定义；保留筛选、目录树及80步撤销/重做，草稿与正式 JSON 分开，恢复前核对 PDF 身份 |
| 目标页预览 | 滚轮、按钮及 Ctrl＋滚轮缩放 50%–300%，适合宽度/整页、翻页与原目录行定位；预览只读 |
| 页码映射 | 固定偏移、分段映射或指定实际 PDF 页，支持多级书签 |
| 拖放与批量 | 拖入 PDF、JSON 或文件夹，逐本预览、勾选和查看处理结果 |
| 窗口与主题 | 两标签页共用窗口、置顶及专注状态，支持 Ctrl+Tab 往返；左上视图菜单选择三种外观、恢复默认分栏/列宽，PDF 页面图像保持原色 |
| 帮助与菜单 | F1 打开本机非模态操作说明及分场景快捷键表；v1.11.0 只保留编辑/视图/帮助，文件选择在页面内完成，列表支持右键及键盘菜单 |
| 原地写入 | 临时副本写入并校验后原子替换，保持原文件名与路径 |
| 备份 | 默认开启；默认保存在各 PDF 旁的 `_backup`，可自选目录 |
| 已有书签 | 默认跳过；明确选择替换时覆盖整棵原书签树 |
| 茉莉花缓存清理 | 默认关闭；成功写入后只清理同目录 `jasminum-outline.json` |
| 删除输入 JSON | 默认关闭；仅在相关 PDF 全部成功写入且 JSON 未变化后删除，预览/失败/跳过时保留 |
| 命令行 | 支持预览、dry-run、单本及批量处理 |

自动识别结果仍需人工核对；复杂版式、模糊扫描、罗马页码或缺页可能需要手工修正。目标页未知/越界或标题无效时拒绝确认/写入；Enter 确认和草稿暂存都不会自动导出正式 JSON 或写入 PDF。操作细节见[校对说明](docs/USAGE.md#v170校对与界面完善)。

## 更新日志

按时间倒序列出全部已有更新；每条末尾可查看本次完整记录。

| 版本／记录 | 日期 | 主要变更 |
| --- | --- | --- |
| v1.11.0 | 2026-10-22 | 1、精简三菜单与重复页头，保留各功能的页面和局部入口。<br>2、Ctrl+N 添加、Alt+↑/↓ 移动，F1 可设置15项常用工作台快捷键并恢复默认。<br>3、修复帮助长详情挤出底栏；正式云端门禁及七附件核验通过；已更正程序内更新说明及对应校验值。<br>[本次完整记录](CHANGELOG.md#v1-11-0) |
| 目录快捷键设置（未发布） | 2026-10-22 | 1、目录列表新增 Ctrl+N 添加、Alt+↑/↓ 上移/下移，兼容无 Insert 键的键盘。<br>2、F1 快捷键表可修改15项常用工作台命令，并恢复所选或全部默认键位。<br>3、保存个人键位，拒绝冲突和保留组合，继续保护输入框编辑及原业务流程。<br>[本次完整记录](CHANGELOG.md#keyboard-shortcuts-2026-10-22) |
| 菜单与页头精简（未发布） | 2026-10-22 | 1、顶部仅保留编辑、视图、帮助，按当前页显示适用编辑操作。<br>2、移除重复页头，通过标签页进入目录工作台，“版本与更新”集中到帮助菜单。<br>3、文件选择、草稿、目录校对、预览定位及原快捷键继续可用。<br>[本次完整记录](CHANGELOG.md#compact-menus-2026-10-22) |
| v1.10.0 | 2026-10-22 | 1、统一两页专注状态，记忆并恢复分栏/列宽，精简工具分组与状态显示。<br>2、增加右键菜单、Ctrl+F/F2/Ctrl+L 及工作页切换，保留校对和忙碌保护。<br>3、F1 本机说明和21项快捷键表，采用精修图标 A，整理左上菜单。<br>[本次完整记录](CHANGELOG.md#v1-10-0) |
| 图标与快捷操作（未发布） | 2026-10-22 | 1、采用精修的蓝色文档书签图标 A，统一窗口与 Windows GUI 图标。<br>2、F1 打开操作说明和分场景快捷键表，左上菜单集中草稿、校对及导航入口。<br>3、Ctrl+Tab / Ctrl+Shift+Tab 切换两页，保留忙碌和无效编辑保护。<br>[本次完整记录](CHANGELOG.md#app-icon-2026-10-22) |
| 共享专注与界面精简（未发布） | 2026-10-21 | 1、两页专注模式共用一个状态，视图菜单统一开关。<br>2、整理工具分组、主次操作、书名路径、空状态与选择计数。<br>3、增加恢复本页默认布局及 Ctrl+F、F2、Ctrl+L 快捷操作。<br>[本次完整记录](CHANGELOG.md#shared-focus-polish-2026-10-21) |
| 专注入口调整（未发布） | 2026-10-21 | 1、两页专注模式统一由左上视图菜单控制，移除重复复选框。<br>2、保留两页独立状态记忆、原控件恢复及独立编辑窗口入口。<br>[本次完整记录](CHANGELOG.md#focus-menu-2026-10-21) |
| 本地界面更新（未发布） | 2026-10-21 | 1、两页专注模式扩大目录和预览区，原操作随时恢复。<br>2、记住手动分栏与列宽，两列表支持右键及键盘菜单。<br>3、统一输入边框与标签留白，保留三主题和原快捷键。<br>[本次完整记录](CHANGELOG.md#focus-layout-2026-10-21) |
| v1.9.0 | 2026-10-21 | 1、增强扫描目录补漏与层级保护，勾选统一为清晰勾号。<br>2、新增Delete、Ctrl+A、清除选择和目录树整层展开折叠。<br>3、左上菜单、护眼配色、预览滚动缩放及夜间菜单交互优化。<br>[本次完整记录](CHANGELOG.md#v1-9-0) |
| 文档更新 | 2026-10-20 | 1、合并重复介绍，整理下载、使用和文档入口。<br>2、补齐全部更新摘要、编号及详情链接；程序仍为 v1.8.1。<br>[本次完整记录](CHANGELOG.md#docs-2026-10-20) |
| v1.8.1 | 2026-10-19 | 1、两页共用标题栏置顶按钮，切页保持状态。<br>2、修复开启置顶后无法再次点击取消的问题。<br>[本次完整记录](CHANGELOG.md#v1-8-1) |
| v1.8.0 | 2026-10-18 | 1、修复切页时窗口伸缩、移位，改善拖宽响应。<br>2、整理界面，新增可记忆的夜间模式。<br>3、支持 Enter 多选确认、下一待核对及快速查找。<br>[本次完整记录](CHANGELOG.md#v1-8-0) |
| v1.7.0 | 2026-10-18 | 1、主界面与目录工作台整合为同窗标签页。<br>2、新增本地草稿、撤销重做、查找筛选及目录树。<br>3、增加预览定位、逐页识别区域和人工栏线。<br>[本次完整记录](CHANGELOG.md#v1-7-0) |
| v1.6.0 | 2026-10-17 | 1、增强双栏识别，支持手选单栏/双栏布局。<br>2、提供三种节编号方式，修正重复补号。<br>3、预览支持滚轮、按钮及 Ctrl＋滚轮缩放。<br>[本次完整记录](CHANGELOG.md#v1-6-0) |
| v1.5.1 | 2026-10-11 | 1、减少扫描目录漏项，增强短标题识别。<br>2、规范编号空格、去除数字节号前 § 并补充缺失节号。<br>3、修正索引、答案等独立书末条目的层级。<br>[本次完整记录](CHANGELOG.md#v1-5-1) |
| v1.5.0 | 2026-10-08 | 1、新增“帮助 / 更新”、后台检查及下载进度。<br>2、安装前校验，新版异常时回滚程序与配置。<br>3、统一 Single/Portable 打包及更新清单。<br>[本次完整记录](CHANGELOG.md#v1-5-0) |
| 仓库整理 | 2026-10-06 | 1、统一仓库名称、下载命名及使用说明。<br>2、整理源码、测试、许可、便携打包及自动构建。<br>[本次完整记录](CHANGELOG.md#repository-organization) |
| v1.4.1 | 2026-10-04 | 1、新增成功写入后删除目录 JSON 的可选设置。<br>2、批量任务全部成功后才删除共用 JSON。<br>[本次完整记录](CHANGELOG.md#v1-4-1) |
| v1.4（本地历史） | 2026-10-04 | 1、修复选择操作覆盖确认状态，完善单元格编辑。<br>2、增强层级调整，记住保存位置与工作台设置。<br>[本次完整记录](CHANGELOG.md#v1-4) |
| v1.3.1（本地历史） | 2026-10-04 | 1、生成与编辑合并为目录工作台。<br>2、支持拖入 PDF/JSON，切换时保留修改。<br>[本次完整记录](CHANGELOG.md#v1-3-1) |
| v1.3（本地历史） | 2026-10-04 | 1、新增文字/离线 OCR 识别与页码映射建议。<br>2、增加目录编辑、目标页核对和安全 JSON 导出。<br>[本次完整记录](CHANGELOG.md#v1-3) |
| v1.2.1（本地历史） | 2026-10-04 | 1、修复滚动控件被遮挡、内容无法显示或点击的问题。<br>[本次完整记录](CHANGELOG.md#v1-2-1) |
| v1.2（本地历史） | 2026-10-04 | 1、记住设置，支持拖放、批量勾选及置顶。<br>2、增加树状目录和目标页预览。<br>[本次完整记录](CHANGELOG.md#v1-2) |
| v1.1（本地历史） | 2026-10-04 | 1、新增可选备份及自定义备份目录。<br>2、支持成功写入后清理茉莉花大纲缓存。<br>[本次完整记录](CHANGELOG.md#v1-1) |
| 基础版本（本地历史） | 2026-10-03 | 1、根据 JSON 添加多级书签，支持偏移及分段映射。<br>2、提供 GUI/CLI、预览批量、备份及校验后原地写入。<br>[本次完整记录](CHANGELOG.md#initial-version) |

[查看全部完整更新记录](CHANGELOG.md)。目录快捷键设置及菜单与页头精简两条开发记录汇入拟发布的 v1.11.0，保留其本地阶段状态；本文界面说明包含候选更新，当前稳定下载仍为 v1.10.0。其余四条“未发布”记录保留各轮本地开发时的状态，内容汇入 v1.10.0；最终专注状态由两页共用，取代早期分别记忆的方案。标为“本地历史”的早期条目没有对应 GitHub 发行版；仓库整理属于文档/打包阶段，详细日期范围见对应记录。

## 程序更新

本地优化版从“帮助 → 版本与更新…”检查正式版；v1.5.0 及以后旧版入口为“帮助 / 更新”。最多每 24 小时后台检查一次；下载并校验后，由用户选择“安装并重新启动”。安装前先保存目录、关闭工作台内容并等待处理任务结束。

更新保留发行类型、实际 EXE 名称与位置、设置和用户数据；新版健康检查失败时恢复旧程序与配置。v1.4.1 首次升级、CLI 及源码运行须从发行页手动更新；便携版须完整解压，不能只复制 EXE。机制与故障处理见[自动更新说明](docs/AUTO_UPDATE.md)。

## 源码运行与打包

源码推荐 Windows x64、Python 3.12，并保留 pip 与 Tcl/Tk；打包版已包含 OCR 模型，从源码安装依赖需要联网。运行可使用 `setup.cmd`、`launch_gui.cmd` 或 `launch_cli.cmd`，打包入口为 `build_exe.cmd`。

[安装与运行](docs/USAGE.md#从源码安装与运行) · [打包与验证](docs/USAGE.md#打包与验证) · [项目文件](docs/USAGE.md#项目文件) · [维护与发布流程](docs/MAINTENANCE.md) · [自动构建](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml)

## 文档与来源

| 文档 | 内容 |
| --- | --- |
| [完整使用说明](docs/USAGE.md) | 目录识别、校对、草稿、CLI、Zotero、备份和恢复 |
| [验证记录](VALIDATION.md) | 各阶段实际验证、环境、跳过项与尚未覆盖的场景 |
| [更新验收矩阵](docs/UPDATE_ACCEPTANCE.md) | Single/Portable 更新、健康检查及失败回滚 |
| [当前发行说明](docs/RELEASE_NOTES.md) | 当前版本变化、下载附件、升级与验证局限 |
| [界面设计说明](docs/UI_DESIGN.md) | 界面与窗口交互的借鉴来源、采用内容及验证范围 |
| [文档维护约定](docs/MAINTENANCE.md#更新日志与文档维护) | 更新日志格式、文件分工及本次格式参考 |

双栏识别参考 [PyMuPDF 文字提取说明](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)、[官方多栏示例](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/text-extraction/multi_column.py)的坐标分区思路，以及 [Docling SDK 说明](https://github.com/docling-project/docling/blob/main/docling/.agents/skills/docling/references/python-sdk.md)对阅读顺序与层级的区分。实现沿用本项目解析、OCR 与校验接口，未复制示例代码或引入 Docling、新模型及新依赖。

## 许可

本项目沿用 **GNU AGPL v3**，见 [LICENSE.txt](LICENSE.txt)。PyMuPDF/MuPDF、OCR 与运行库的来源及许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [licenses](licenses)。
