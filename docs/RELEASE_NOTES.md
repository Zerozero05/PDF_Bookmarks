# v1.9.0

PDF_Bookmarks 是 Windows 本地 PDF 书签工具，可独立处理普通 PDF，也适配 Zotero 附件。支持文字/扫描目录识别、目录 JSON 导入编辑、预览校对、拖放及批量写入，保持原 PDF 文件名和路径。

本版汇总目录识别、快捷操作及界面优化。面向 **Windows 10/11 x64**；Single 与 Portable GUI 功能相同，无需安装 Python。沿用原七项下划线命名附件，历史版本和资产保留。

## 更新内容

1. **增强扫描目录补漏**：在已确定的栏内，按连续点线定位目录行，分别重读同一行标题和页码，减少漏项及远端页码错配；不凭序号虚构内容，不跨栏拼接。拒绝纯编号误当页码、无页码残缺行误接后文，书目等独立内容保持根层级。真实单栏样例由旧131条恢复为227条、13章；这只是已核验样例结果，识别后仍需人工校对。
2. **勾选状态更清楚**：主界面、文件夹“包含子文件夹”和工作台的选中状态统一为清晰勾号，保留原点击、空格、焦点和设置含义。
3. **目录快捷操作**：列表中Delete删除所选目录项，支持多选、撤销/重做；多项删除默认询问，可在“草稿 / 设置”关闭。Ctrl+A全选当前筛选匹配项，Esc清除选择；目录树+/-展开折叠所选节点，未选择时作用于全部显示层级。输入框保持原文字编辑用途，未选子项不自动删除，非法层级仍拒绝。
4. **界面更集中**：左上“文件 / 编辑 / 视图 / 帮助”统一全局入口；收起低频写入设置并始终显示当前策略摘要，目录草稿、移动、定位和适应进入具名菜单。保留全部原功能，增加少量悬停/焦点提示，成功反馈集中到状态与记录，原写入确认/错误保护保留。
5. **主列表与预览**：处理列表支持Ctrl+A、Ctrl/Shift多选、清除选择和Delete移除；高亮选择与写入勾号分开，移除不删除磁盘PDF/JSON。主只读预览增加滚轮上下滚动、Ctrl+滚轮和按钮缩放，范围50%–300%，连续缩放合并请求。
6. **三种外观与菜单交互**：日间/夜间/护眼共用并记忆，护眼采用加深米绿分层，PDF图片保持原色。Windows原生菜单使用系统色，改善禁用文字和快捷键重影；其余控件和下拉列表继续跟随主题。增加悬停/焦点边框及箭头反馈，减少子控件焦点引发的置顶重排，保留共享置顶与取消。

没有新增运行依赖、模型或在线OCR；沿用已有RapidOCR、OpenCV、PyMuPDF与Tk/ttk。菜单/层级方法核对官方Tk和Microsoft资料，原有设计来源与采用范围见[界面设计](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.9.0/docs/UI_DESIGN.md)。

## 兼容性与使用提醒

- 正式JSON仍为version 1，CLI参数、批量配对、三种节编号、单/双栏和人工区域/栏线、编号与标题间空格及§规范保留。
- 原Enter单/多选确认和下一待核对、搜索Enter、撤销/重做、本地草稿及身份校验保留。自动识别不是已核对结果；未知/越界页或空标题仍拒绝确认/写入。
- 原路径临时副本写入、校验后原子替换、备份默认开启、成功后可选删除JSON和茉莉花缓存规则保留；后两项仍独立且默认关闭。
- 设置继续位于`%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`，schema仍为1；新增可选删除询问与eye_care值有默认，旧字段及未知字段保留，无迁移。
- Windows原生菜单/标题栏及文件对话框可能使用系统浅色；正文PDF不反色。复杂版式、模糊扫描、罗马页码或缺页仍可能需手工修正，不保证任意文档无识别错误。

## 下载文件与区别

| 文件 | 用途 |
| --- | --- |
| [PDF_Bookmarks_v1.9.0_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.9.0/PDF_Bookmarks_v1.9.0_win_x64.exe) | Single单文件GUI，直接运行；启动时临时解包运行库 |
| [PDF_Bookmarks_v1.9.0_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.9.0/PDF_Bookmarks_v1.9.0_win_x64_portable.zip) | Portable文件夹GUI，完整解压后运行PDF_Bookmarks\PDF_Bookmarks.exe；保留_internal和package-manifest.json |
| [PDF_Bookmarks_v1.9.0_win_x64_cli.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.9.0/PDF_Bookmarks_v1.9.0_win_x64_cli.exe) | CLI命令行程序，用于脚本和批量处理 |
| [PDF_Bookmarks_v1.9.0_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.9.0/PDF_Bookmarks_v1.9.0_win_x64_full.zip) | GUI、CLI、完整源码、测试、示例及许可；GUI位于PDF_Bookmarks\dist\PDF_Bookmarks.exe |
| [PDF_Bookmarks_v1.9.0_win_x64_portable.zip.sha256](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.9.0/PDF_Bookmarks_v1.9.0_win_x64_portable.zip.sha256) | Portable ZIP独立校验 |
| [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.9.0/SHA256SUMS.txt) | 附件SHA-256清单 |
| [update-manifest.json](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.9.0/update-manifest.json) | 程序更新清单，无需手动运行 |

两种GUI功能一致；“便携”指免安装，两者共用本机设置和草稿。Portable主要省去启动解包，不保证OCR或PDF写入更快。

## 升级与验证

- v1.5.0及后续Single/Portable GUI从“帮助 / 更新”检查正式版，校验下载后由用户选择安装并重启；保留发行类型、实际名称、位置和设置。先保存目录、关闭工作台内容并等待任务结束。v1.4.1、CLI和源码手动下载，Portable须完整解压。
- 已验收试用的完整源码600项：599通过、1跨盘环境跳过、0失败；实际EXE内嵌9模块以宿主Python/Tk执行237项通过，另核对28运行源码指纹、身份/资源/helper。
- 实际试用鼠标检查覆盖两页、护眼/夜间往返、菜单清晰绘制、重复单击/Esc、置顶开启/取消、三本合成PDF预览和6项三层目录保持。源码/包内合成事件不冒充冻结鼠标验证；实际Ctrl+滚轮、多选Delete、最小化恢复/跨屏DPI及全部菜单切换路径未在最后一轮逐项重做。
- 正式版本由原Windows Actions以1.9.0身份重新测试、构建Single/Portable/CLI/helper，并完成真实冻结升级/健康检查/失败回滚四场景；所有门禁成功、七项草稿资产核验后才公开。试用字节不代替正式附件，运行结果见[Actions](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml)及[验证记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.9.0/VALIDATION.md)。

[完整使用说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.9.0/docs/USAGE.md) · [全部更新记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.9.0/CHANGELOG.md) · [维护流程](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.9.0/docs/MAINTENANCE.md)

沿用GNU AGPL v3，第三方许可随完整包和便携包提供；无签名或准确率保证的新增宣称。
