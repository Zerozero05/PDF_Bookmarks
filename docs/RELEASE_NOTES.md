# v1.8.1

PDF_Bookmarks 是 Windows 本地 PDF 书签工具，可独立处理普通 PDF，也适配 Zotero 附件。支持文字/扫描目录识别、JSON 导入编辑、预览校对、拖放和批量写入，保持原 PDF 文件名与路径。

本版将两个标签页的置顶操作统一到标题栏，并修复开启后无法再次点击取消的问题。面向 **Windows 10/11 x64**；Single 与 Portable GUI 功能相同，均无需安装 Python。标题只写版本号，七项附件沿用原下划线命名；历史发行版及附件保留。

## 更新内容

1. **两个界面共用一个置顶按钮**：位于窗口右上角、系统最小化按钮左侧。点击“置顶”开启后显示“取消置顶”，再次点击即可关闭，允许反复开关。主界面和目录工作台切换、保存返回或关闭重开工作台，都沿用同一状态；移除两页内容区的重复入口。
2. **修复置顶后按钮无法再次点击**：试用中主窗口进入置顶层，而附属按钮仍在普通窗口层，导致按钮被主窗口挡住。本版在窗口状态回调处理结束后同步按钮的置顶层级，重新获得焦点时也核对，保持按钮可点击。开启和取消均有原生窗口层级及实际鼠标验证。
3. **保留系统窗口操作与编辑状态**：继续使用原生标题栏、拖动、边框缩放及最小化/最大化/关闭。置顶按钮不新增任务栏或 Alt+Tab 项，不抢编辑焦点；主窗口被确认提示等模态窗口禁用时，不允许通过按钮改变它。关闭时释放相关回调。原生扩展初始化不可用时，在标签栏右侧保留唯一入口。
4. **沿用设置兼容性**：启动使用原主界面的置顶选择，关闭后记住统一状态；保留 `topmost`、`editor_topmost` 旧字段、原设置位置和配置 schema 1。源码接口 `open_editor()` 的独立工作台仍保留自己的置顶开关。

本版相对 v1.8.0 仅更新上述置顶入口和状态同步，未修改 PDF/OCR/目录识别算法、JSON/CLI、安全写入和更新事务实现。使用现有 Tk/ttk 和 Python 标准库，参考微软官方窗口接口及 Tk 8.6.12 窗口行为；没有复制第三方实现或新增依赖。具体来源及采用范围见[界面设计说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.8.1/docs/UI_DESIGN.md)。

## 继续保留的功能和规范

- 同一窗口两个标签页，共用稳定窗口尺寸、位置及最大化状态；夜间模式、Enter 单/多选确认和下一待核对、Enter 查找，原编辑框 Enter 用途保持。
- 自动/单栏/双栏目录，逐页识别区域与人工栏线，双栏先左后右并延续章节上下文；三种节编号、编号与标题间一个空格、去除数字编号前 `§`，手工标题和原有可靠编号保护。
- 本地未完成草稿、身份核验恢复、撤销/重做、查找筛选和目录树；滚轮、Ctrl＋滚轮及按钮缩放、适合宽度/整页、翻页与原目录行定位。
- 自动识别结果仍是待核对草稿；人工确认、目标页校验、正式 JSON `version: 1`、原有 CLI 参数和批量配对规则保持。未知/越界页或无效标题继续拒绝确认/写入。
- 预览只读，原路径临时副本写入、校验后原子替换；备份默认开启，删除目录 JSON 与茉莉花缓存仍为独立且默认关闭的成功后操作。
- 原 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`、未知配置字段、Single/Portable 下载校验、健康检查及程序/配置同步回滚继续保留。

## 下载文件与区别

| 文件 | 用途与运行方式 |
| --- | --- |
| [PDF_Bookmarks_v1.8.1_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.8.1/PDF_Bookmarks_v1.8.1_win_x64.exe) | Single 单文件 GUI，直接运行；启动时临时解包运行库 |
| [PDF_Bookmarks_v1.8.1_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.8.1/PDF_Bookmarks_v1.8.1_win_x64_portable.zip) | Portable 文件夹 GUI，完整解压后运行 `PDF_Bookmarks\PDF_Bookmarks.exe`；保留 `_internal`、`package-manifest.json` 和其余文件 |
| [PDF_Bookmarks_v1.8.1_win_x64_cli.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.8.1/PDF_Bookmarks_v1.8.1_win_x64_cli.exe) | CLI 命令行程序，用于脚本与批量处理 |
| [PDF_Bookmarks_v1.8.1_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.8.1/PDF_Bookmarks_v1.8.1_win_x64_full.zip) | Single GUI、CLI、源码、测试、示例和许可；GUI 位于 `PDF_Bookmarks\dist\PDF_Bookmarks.exe` |
| [PDF_Bookmarks_v1.8.1_win_x64_portable.zip.sha256](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.8.1/PDF_Bookmarks_v1.8.1_win_x64_portable.zip.sha256) | 便携 ZIP 独立 SHA-256 校验文件 |
| [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.8.1/SHA256SUMS.txt) | 正式附件 SHA-256 校验清单 |
| [update-manifest.json](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.8.1/update-manifest.json) | 程序检查及验证更新所用清单，无需手动运行 |

两种 GUI 功能一致。“便携”指免安装，两者共用原设置及本机草稿目录；Portable 主要省去启动解包，不保证 OCR 或 PDF 写入更快。下载是否可用以发行页实际附件为准。

## 使用与升级

- 置顶开启时按钮显示“取消置顶”；再次点击即可恢复普通窗口。无需到另一个标签页重复设置。
- v1.5.0 及后续 Single/Portable GUI 可从“帮助 / 更新”检查正式版，下载校验后由用户选择安装并重启；保留发行类型、实际入口名称与原设置。安装前保存目录、关闭工作台内容并等待任务结束，仅切回主界面不算关闭工作台。
- v1.4.1 无更新入口，首次须手动下载。Single 运行新 EXE；Portable 完整解压新文件夹，不能只复制主 EXE。CLI/源码从发行页手动更新。用户 PDF、目录 JSON、备份、设置和未完成草稿继续保留。

## 验证与限制

- **本轮源码回归**：517 项，516 通过、1 项跨盘环境测试跳过、0 失败。涵盖共享置顶、实际原生窗口层级与按钮中心命中，以及原有标签页、主题、快捷校对、PDF、OCR、JSON/CLI、配置及更新回归。
- **修正后的本地试用**：146 项实际 PYZ 内嵌模块检查通过，28 项运行源码指纹、身份/资源/helper 核验通过。试用包身份仍为 1.8.0，与正式 v1.8.0 公开包不同；模块检查使用宿主 Python/Tk，不代替冻结程序交互。
- **真实试用 EXE 鼠标检查**：4 次点击完成两轮开启/取消，覆盖主界面与工作台、明暗主题、最小化恢复；核对统一状态、稳定窗口及正常退出后的设置保存。使用空白界面和隔离配置，未操作真实 PDF 或用户设置。
- **正式构建门禁**：本版由原 Windows Actions 重新构建 Single/Portable/CLI/helper，验证生产身份、资源、清单和真实冻结更新/失败回滚四场景；仅在成功并核对七项草稿附件后公开。实际结果见 [Actions](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml) 与[验证记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.8.1/VALIDATION.md)，不以旧试用字节代替正式附件。
- 实际跨显示器 DPI、贴边和最大化手势，以及完整真实 PDF 业务未在本轮鼠标阶段逐项覆盖。自动目录仍需核对标题、层级和实际页码；有限测试不能保证所有 Windows 环境或文档均无缺陷。

[使用说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.8.1/docs/USAGE.md) · [版本记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.8.1/CHANGELOG.md) · [维护流程](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.8.1/docs/MAINTENANCE.md)

沿用 GNU AGPL v3，第三方许可随完整包及便携包提供。发布后的本地清理按本次用户授权执行：先核验远端恢复、保存交接并展示固定清单，再删除确认不用的可恢复副本；当前 Git、私人资料、用户设置/草稿和共享依赖保留。
