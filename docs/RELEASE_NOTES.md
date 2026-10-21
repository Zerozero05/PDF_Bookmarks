# v1.10.0

PDF_Bookmarks 是 Windows 本地 PDF 书签工具，可独立处理普通 PDF，也适配 Zotero 附件。支持文字/扫描目录识别、目录 JSON 导入编辑、预览校对、拖放及批量写入，保持原 PDF 文件名和路径。

本版集中完善共享专注、布局、菜单与键盘操作，并采用用户选定的精修图标 A。面向 **Windows 10/11 x64**；Single 与 Portable GUI 功能相同，无需安装 Python。沿用原七项下划线命名附件，历史版本、标签和资产保留。

## 更新内容

1. **两页共用专注模式**：左上“视图 → 专注模式”统一开启或关闭，切页、新建或重开工作台保持一致；收起辅助区时保留校对、预览、保存及当前处理策略，恢复不重载 PDF 或清除编辑内容。
2. **布局记忆与恢复**：记住手动调整的分栏比例和表格列宽，“视图 → 恢复本页默认布局”只恢复当前页布局，不重置主题、窗口、目录、编号或写入策略。两列表支持右键、Shift+F10及键盘菜单，保留原确认、删除/移除、编辑、定位、勾选和展开折叠操作。
3. **界面更简洁**：整理工具分组和主次按钮，减少重复边框与缩放比例；书名与完整可编辑路径分别呈现，增加路径复制/打开所在文件夹、空状态指引，以及明确区分查看选择、写入勾选和目录确认的计数。功能继续通过原操作区或具名菜单使用。
4. **快捷操作与菜单收纳**：Ctrl+F定位目录查找，目录列表F2编辑标题，Ctrl+L定位PDF预览页码。Ctrl+Tab / Ctrl+Shift+Tab切换两个工作页，处理任务中或编辑无效时保留当前页。文件/编辑/视图/帮助按用途集中草稿、撤销重做、查找、目录校对和页码导航，不增加主面板常驻按钮。
5. **F1操作说明与快捷键表**：F1或“帮助 → 操作说明与快捷键…”打开本机非模态说明，两页共用同一窗口；包括操作流程、按区域分类的21项快捷键及窄窗口完整说明。重复打开复用窗口，Esc只关闭帮助；独立工作台也有F1入口，原“帮助 / 更新”保留。F1本身不联网或改写文件。
6. **精修图标A**：采用蓝色文档、白色书签与折角的透明图标，优化留白和边距；窗口与Single/Portable GUI使用同一资源。源码保留PNG光栅母版和16至256像素的九尺寸ICO，并将ICO加入构建来源和资源检查。

设计方法参考Microsoft布局/命令指南及Sun Valley/ttkbootstrap的轻量视觉层次，在既有Tk/ttk上实现；没有安装组件库、复制第三方实现、迁移框架或新增运行依赖。图标由内置ImageGen生成与精修，PNG不是矢量源。具体来源及取舍见[界面设计](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.10.0/docs/UI_DESIGN.md)。

## 兼容性与使用提醒

- JSON仍为version 1，CLI参数、批量配对、本地OCR、自动/手选单栏双栏、人工区域/栏线、三种节编号，以及编号与标题间空格、去除数字节号前§的规范保留。
- Enter单/多选确认并下一待核对、搜索Enter、Delete、Ctrl+A、目录树加减、撤销重做和预览滚轮/缩放保持各自焦点语义。Ctrl+S仅暂存校对草稿，不正式导出JSON或写入PDF；自动识别仍需逐项核对，未知/越界页或空标题拒绝确认/写入。
- 原路径临时副本写入、校验后原子替换及备份默认开启保持；成功后删除输入JSON和茉莉花缓存仍为独立、默认关闭选项。处理列表移除不会删除磁盘PDF/JSON。
- 设置继续位于`%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`，schema仍为1，无迁移。新增可选界面偏好有默认，旧字段与未知字段保留；统一专注优先读取有效focus_mode，缺失时依次兼容旧主界面值、旧工作台值，保存时同步旧键。
- 日间/夜间/护眼及共享置顶继续保留，PDF图像保持原色；Windows原生菜单、标题栏和文件对话框可能使用系统配色。系统快捷方式或任务栏图标缓存可能延迟显示新图标，本版不修改系统缓存。
- 复杂版式、模糊扫描、罗马页码或缺页仍可能需要手工修正；本次界面更新没有改变OCR或编号算法，不承诺任意文档无识别错误。

## 下载文件与区别

| 文件 | 用途 |
| --- | --- |
| [PDF_Bookmarks_v1.10.0_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.10.0/PDF_Bookmarks_v1.10.0_win_x64.exe) | Single单文件GUI，直接运行；启动时临时解包运行库 |
| [PDF_Bookmarks_v1.10.0_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.10.0/PDF_Bookmarks_v1.10.0_win_x64_portable.zip) | Portable文件夹GUI，完整解压后运行PDF_Bookmarks\PDF_Bookmarks.exe；保留_internal和package-manifest.json |
| [PDF_Bookmarks_v1.10.0_win_x64_cli.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.10.0/PDF_Bookmarks_v1.10.0_win_x64_cli.exe) | CLI命令行程序，用于脚本和批量处理 |
| [PDF_Bookmarks_v1.10.0_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.10.0/PDF_Bookmarks_v1.10.0_win_x64_full.zip) | GUI、CLI、完整源码、测试、示例及许可；GUI位于PDF_Bookmarks\dist\PDF_Bookmarks.exe |
| [PDF_Bookmarks_v1.10.0_win_x64_portable.zip.sha256](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.10.0/PDF_Bookmarks_v1.10.0_win_x64_portable.zip.sha256) | Portable ZIP独立校验 |
| [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.10.0/SHA256SUMS.txt) | 附件SHA-256清单 |
| [update-manifest.json](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.10.0/update-manifest.json) | 程序更新清单，无需手动运行 |

两种GUI功能一致；“便携”指免安装，两者共用本机设置和草稿。Portable主要省去启动解包，不保证OCR或PDF写入更快。

## 升级与验证

- v1.5.0及后续Single/Portable GUI从“帮助 / 更新”检查正式版，校验下载后由用户选择安装并重启；保留发行类型、实际名称、位置和设置。先保存目录、关闭工作台内容并等待任务结束。v1.4.1、CLI和源码手动下载，Portable须完整解压。
- 发布前已验收的本地试用沿用1.9.0身份：完整源码682项，681通过、1跨盘环境跳过、0失败；实际EXE内嵌11模块由宿主Python/Tk执行319项通过，另核对31项运行文件/ICO指纹、身份、资源、helper及九档PE图标。这些结果不冒充正式1.10.0附件验证。
- 实际Single试用检查覆盖新图标、F1操作说明及快捷键表、Esc关闭、菜单分组、两页快捷切换与内容保持；前轮实屏检查覆盖共享专注、Ctrl+F/F2/Ctrl+L和分栏恢复。真实全书OCR、跨屏DPI、固定快捷方式缓存、全部旧快捷键及忙碌/无效编辑的冻结鼠标组合未在最后一轮重做，相关源码/包内及未变模块既有证据分开记录。
- 正式发布门禁以1.10.0身份重新测试并构建Single/Portable/CLI/helper，执行真实冻结升级、健康检查和失败回滚四场景；全部成功并核对七项草稿资产后才公开，失败不发布。实际运行与发布结果以[Actions](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml)、发行页及[验证记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.10.0/VALIDATION.md)为准。

[完整使用说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.10.0/docs/USAGE.md) · [全部更新记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.10.0/CHANGELOG.md) · [维护流程](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.10.0/docs/MAINTENANCE.md)

沿用GNU AGPL v3，第三方许可随完整包和便携包提供；无签名或准确率保证的新增宣称。
