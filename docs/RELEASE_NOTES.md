# v1.14.0

PDF_Bookmarks 是 Windows 10/11 x64 本地 PDF 书签工具，可独立处理普通 PDF，也适配 Zotero 附件。本版改善长目录连续校对、扫描页浏览和三种外观的可读性。

## 更新内容

1. **连续校对。** 在“待确认”筛选中按 Enter，可确认选中条目并前进。有待核对子项的父章继续显示。原目录行用双线定位，方便在目录与原页间对照。
2. **原页浏览。** 两条书签指向同一页时，保留当前阅读位置。两页均支持以指针为中心缩放，缩放按钮以视口中心为基准。
3. **批量写入。** 写入按钮显示实际勾选且可写的本数。选择文件用于查看，文件勾号决定写入范围。目录栏数和标题编号在小窗口与专注模式下也可操作。
4. **日间、夜间与护眼模式。** 暖纸白、石墨灰和灰绿背景搭配海青色选中标记。多选及焦点离开列表后，行首细线仍然可见。夜间主按钮使用浅底深字。草稿暂存失败时显示原因，成功后恢复常规提示。
5. **减少长目录内存和重绘。** 撤销历史压缩存放，最多保留 80 个状态。选中标记由控件复用，未选中行跳过标记绘制。本机最终试用 EXE 各切页 50 次，两轮首次可见反馈 P95 为 48.72 和 47.82 毫秒。1000 项目录连续确认 50 项的 P95 为 42.17 毫秒。

## 兼容与升级

沿用目录 JSON v1、原 CLI 参数、设置位置及 schema 1。自动识别结果仍需人工核对，原路径写入、可选备份、已确认目标页检查、两项独立的写后清理和升级失败回滚继续沿用。

Single 和 Portable 的图形功能相同，均无需安装 Python。v1.5.0 及之后的图形版可在「帮助 → 版本与更新…」检查更新，保存校对工作并关闭工作台内容后，按提示安装。更新保留原有发行类型、入口名称、路径和设置。

## 下载文件

| 文件 | 用途 |
| --- | --- |
| [PDF_Bookmarks_v1.14.0_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.14.0/PDF_Bookmarks_v1.14.0_win_x64.exe) | 单文件图形版。只想留一个可运行文件时，下载这一项。 |
| [PDF_Bookmarks_v1.14.0_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.14.0/PDF_Bookmarks_v1.14.0_win_x64_portable.zip) | 便携图形版。完整解压后，运行 `PDF_Bookmarks\PDF_Bookmarks.exe`。 |
| [PDF_Bookmarks_v1.14.0_win_x64_cli.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.14.0/PDF_Bookmarks_v1.14.0_win_x64_cli.exe) | 命令行版，用于脚本、预览和批量写入。 |
| [PDF_Bookmarks_v1.14.0_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.14.0/PDF_Bookmarks_v1.14.0_win_x64_full.zip) | 含图形版、命令行版、完整源码、测试、示例和许可。 |
| [PDF_Bookmarks_v1.14.0_win_x64_portable.zip.sha256](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.14.0/PDF_Bookmarks_v1.14.0_win_x64_portable.zip.sha256) | 便携 ZIP 的独立 SHA-256 校验值。 |
| [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.14.0/SHA256SUMS.txt) | 程序包和更新清单的 SHA-256 清单。 |
| [update-manifest.json](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.14.0/update-manifest.json) | 供程序检查本版更新。 |

用于试用的源码回归 901 项通过，1 项便携版跨盘移动在该测试环境跳过。双栏扫描样本经校对写入的 17 条书签已逐项核对标题、层级和目标页。正式发行流程从对应标签重建各发行形式，验证实际升级与回滚。[构建记录](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml) · [完整使用说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.14.0/docs/USAGE.md) · [版本记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.14.0/CHANGELOG.md)

项目采用 GNU AGPL v3。完整包和便携包内含第三方许可。
