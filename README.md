# Zotero PDF 书签目录工具

在 Zotero 当前使用的 PDF 原文件中添加多级书签，保持附件路径不变，无需重新附加 PDF。支持导入目录 JSON，也可从文字或扫描 PDF 生成目录，经预览与人工校对后写入。

当前版本：**v1.4.1**。面向 Windows 10/11 x64，中文界面，兼容中文文件名和书签。源码、版本历史和文档在本仓库管理；Windows 程序从 Releases 下载。

[下载 v1.4.1 Windows 版](https://github.com/Zerozero05/Zotero_PDF_Bookmarks/releases/tag/v1.4.1) · [完整使用说明](docs/USAGE.md) · [版本记录](CHANGELOG.md) · [维护与清理流程](docs/MAINTENANCE.md) · [自动构建](https://github.com/Zerozero05/Zotero_PDF_Bookmarks/actions/workflows/windows-build.yml)

## 选择下载方式

| 下载 | 运行方式与区别 |
| --- | --- |
| [单文件 GUI EXE](https://github.com/Zerozero05/Zotero_PDF_Bookmarks/releases/download/v1.4.1/ZoteroPDFBookmarks-v1.4.1.exe) | 直接运行，携带方便；每次启动需要将运行库解包到临时目录 |
| [便携文件夹版 ZIP](https://github.com/Zerozero05/Zotero_PDF_Bookmarks/releases/download/v1.4.1/ZoteroPDFBookmarks-Portable-v1.4.1.zip) | 解压后打开 `ZoteroPDFBookmarks\ZoteroPDFBookmarks.exe`；须保留同目录的 `_internal` 和其余文件，省去启动时的临时解包 |
| [完整 Windows ZIP](https://github.com/Zerozero05/Zotero_PDF_Bookmarks/releases/download/v1.4.1/ZoteroPDFBookmarks-Windows-x64-v1.4.1.zip) | 原有 GUI/CLI 单文件 EXE、源码、测试、示例和说明；GUI 位于 `ZoteroPDFBookmarks\dist\ZoteroPDFBookmarks.exe` |

两种 GUI 都面向 Windows 10/11 x64，无需安装 Python，功能和版本均为 v1.4.1。便携版主要减少启动解包，不承诺每页 OCR 或 PDF 写入更快。两者共用 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`，切换时继续沿用设置；“便携”指免安装，设置仍保存在当前电脑。

原单文件 EXE 和完整 ZIP 保留，便携版作为同一发布页的新增下载。原三个程序包的校验值见 `SHA256SUMS.txt`，便携 ZIP 的校验值见同名 `.zip.sha256` 文件。

## 快速使用

1. 按上表选择单文件 GUI 或便携文件夹版；需要 CLI、源码与说明时下载完整 Windows ZIP。便携版解压后运行，不能只复制其中的 EXE。
2. 在 Zotero 中右键 PDF 附件，选择“显示文件”，找到实际原文件。关闭该 PDF 的阅读窗口。
3. 把原 PDF 和对应的 `书名.toc.json` 拖进程序。没有 JSON 时，点“生成 / 编辑目录…”进行识别、校对并保存。
4. 点“1. 预览”，检查书签层级、标题和右侧实际目标页。勾选要处理的 PDF，设置写入选项，点“2. 写入勾选的 PDF”。更改输入或写入选项后须重新预览。
5. 回到 Zotero，重新打开同一个附件查看目录。使用茉莉花缓存清理时，处理前须完全退出 Zotero，处理后再启动。

程序添加 PDF 内部的 Outline / Bookmarks，不插入正文目录页。多本文件按文件名配对，存储附件可递归处理 `storage`，链接附件可直接处理实际链接指向的文件。详细配对、恢复与刷新说明见 [使用说明](docs/USAGE.md)。

## 功能与默认设置

| 功能 | 行为 |
| --- | --- |
| 目录生成与编辑 | 文字提取、本地中英文 OCR；目标页预览、人工确认、自动提交编辑与批量改层级 |
| 页码映射 | 固定偏移、分段映射、单项实际 PDF 页；支持章、节、小节多级书签 |
| 拖放与批量 | 拖入 PDF、JSON 或文件夹；逐本预览、勾选和显示处理结果 |
| 原地写入 | 临时副本写入、校验后原子替换；原 PDF 文件名和路径保持不变 |
| 备份 | 默认开启；留空用各 PDF 旁的 `_backup`，可选择自定义文件夹 |
| 已有书签 | 默认跳过；明确选择替换时覆盖当前整棵书签树 |
| 茉莉花缓存清理 | 默认关闭；成功写入后只清理 PDF 同目录 `jasminum-outline.json` |
| 删除输入目录 JSON | 默认关闭；成功写入后删除本次使用的 JSON，失败/跳过/预览时保留 |
| 便捷设置 | 记住选择；主窗口和目录工作台可同时使用，各自置顶与调整大小 |
| 命令行 | 保留预览、dry-run、单本和批量处理模式 |

自动识别结果需要核对，可信提示不是准确率保证。复杂版式、模糊扫描、罗马页码和缺页可能需要手工校正；目标页不确定时不会直接写入。OCR 在本机运行，不上传 PDF，不需要 API Key。打包版包含模型；首次从源码安装依赖需要联网。

## 源码运行与打包

推荐 Windows x64、Python 3.12，保留 pip 和 Tcl/Tk。在仓库根目录运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe gui_entry.py
```

也可以双击 `setup.cmd` 安装，再用 `launch_gui.cmd` 或 `launch_cli.cmd` 启动。Windows 本地打包使用 `build_exe.cmd`，保留 `dist\ZoteroPDFBookmarks.exe` 和 `dist\ZoteroPDFBookmarks-CLI.exe`，另生成 `dist\portable\ZoteroPDFBookmarks\ZoteroPDFBookmarks.exe` 及其完整运行文件夹。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

固定依赖在 `requirements.txt` 和 `requirements-build.txt`。原 v1.4.1 发布的 151 项本地及云端回归已通过；原完整 ZIP 的源码、EXE、校验值及 Windows 启动也已实际验证。便携版的检查范围和结果见 [VALIDATION.md](VALIDATION.md)，原发布云端记录见 [首次正式构建](https://github.com/Zerozero05/Zotero_PDF_Bookmarks/actions/runs/37211403970)。后续构建以各次运行结果为准。

## 项目结构与版本发布

```text
bookmarks_core.py        PDF 校验、页码映射与原地写入
bookmarks_gui.py         主窗口与批量处理
gui_support.py          设置、配对和页面渲染
toc_generation.py        文字/OCR 识别与目录 JSON
toc_editor.py            目录工作台
gui_entry.py             GUI 入口
bookmarks.py             CLI 入口
tests/  examples/        回归测试与示例目录
docs/                   使用说明与维护流程
licenses/               第三方许可
.github/workflows/      Windows 测试、打包与发布
VERSION                 当前发布版本
```

普通提交、PR 和手工运行生成试用构建产物。新版本先供用户本地试用，确认后再推送与 `VERSION` 一致的版本标签并发布 Release。EXE、完整 ZIP 与便携 ZIP 放在 Releases，源码仓库不保存二进制、虚拟环境、用户 PDF 或私人目录 JSON。

云端管理和打包可以减少本地开发文件的磁盘占用；下载的 EXE 仍占本机磁盘，运行时仍需本机内存。远端验证完整后再按确认的具体路径清理旧版本，发布不会自动删除本地文件。流程见 [MAINTENANCE.md](docs/MAINTENANCE.md)。

## 许可

本项目沿用 **GNU AGPL v3**，完整条款见 [LICENSE.txt](LICENSE.txt)。PyMuPDF/MuPDF 与 OCR、运行库等依赖的许可和来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [licenses](licenses)。
