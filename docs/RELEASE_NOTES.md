# v1.13.0

PDF_Bookmarks 是 Windows 10/11 x64 的本地 PDF 书签工具，可单独处理普通 PDF，也适配 Zotero 附件。本次更新重新安排了预览、校对和写入操作，改善切换工作页时的响应。

## 更新内容

1. **目录栏数和标题编号始终可见。** 在「目录工作台 · 生成与编辑」的目录表上方右侧，可以选自动、单栏或双栏，再从 PDF 识别。节标题可选 `1.1 基本概念`、每章从 `1. 基本概念` 开始，或保留识别编号。载入目录和开启专注模式后仍可找到这两个选项。切换编号保留导入的 JSON 和手工修改的标题。
2. **查看和写入各有位置。** 写入页从左到右依次是文件、书签、PDF 原页。底部集中显示写入选项、勾选总数和写入按钮，计入被筛选隐藏的勾选项。两页的查找框都可按 Esc 清除筛选。
3. **连续校对更容易定位。** 载入目录后收起文件来源，需要时可展开。进度显示全书确认数，按 Enter 可确认所选项并跳到下一待核对项。「查看问题…」可定位有问题的条目，「定位」可从目录原页回到所选目标页。翻页在预览上方，缩放和局部识别在下方。
4. **三种主题改善阅读。** 日间、夜间和护眼模式均调整正文、选中行及页码的对比。一级目录加粗，页码右对齐；按钮和下拉框提供按下、展开反馈。目录确认进度随 Windows 的动画效果设置变化。小窗口会给目录表头和可读行预留高度。
5. **减少切页重绘和预览内存占用。** 首次使用时才加载 PDF 引擎和相应主题。已显示的预览图释放压缩数据副本。在同一台 Windows 电脑的合成 PDF 测试中，相比优化前的开发稿，空启动私有内存由约 56 MiB 降至约 25 MiB；具体测量场景见[验证记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.13.0/VALIDATION.md)。

## 兼容与升级

沿用目录 JSON v1、原 CLI 参数、设置位置及 schema 1。自动识别结果仍需人工核对，原路径写入、可选备份、已确认目标页检查、两项独立的写后清理和升级失败回滚继续沿用。

Single 和 Portable 的图形功能相同，均无需安装 Python。v1.5.0 及之后的图形版可在「帮助 → 版本与更新…」检查更新，保存校对工作并关闭工作台内容后，按提示安装。更新保留原有发行类型、入口名称、路径和设置。

## 下载文件

| 文件 | 用途 |
| --- | --- |
| [PDF_Bookmarks_v1.13.0_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.13.0/PDF_Bookmarks_v1.13.0_win_x64.exe) | 单文件图形版。只想留一个可运行文件时，下载这一项。 |
| [PDF_Bookmarks_v1.13.0_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.13.0/PDF_Bookmarks_v1.13.0_win_x64_portable.zip) | 便携图形版。完整解压后，运行 `PDF_Bookmarks\PDF_Bookmarks.exe`。 |
| [PDF_Bookmarks_v1.13.0_win_x64_cli.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.13.0/PDF_Bookmarks_v1.13.0_win_x64_cli.exe) | 命令行版，用于脚本、预览和批量写入。 |
| [PDF_Bookmarks_v1.13.0_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.13.0/PDF_Bookmarks_v1.13.0_win_x64_full.zip) | 含图形版、命令行版、完整源码、测试、示例和许可。 |
| [PDF_Bookmarks_v1.13.0_win_x64_portable.zip.sha256](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.13.0/PDF_Bookmarks_v1.13.0_win_x64_portable.zip.sha256) | 便携 ZIP 的独立 SHA-256 校验值。 |
| [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.13.0/SHA256SUMS.txt) | 程序包和更新清单的 SHA-256 清单。 |
| [update-manifest.json](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.13.0/update-manifest.json) | 供程序检查本版更新。 |

本机源码验证覆盖全部 897 个用例，含单独在 E、D 两卷间补测的便携版更新。Windows 发布流程还会从同一提交构建并核对程序包，检查 Single 和 Portable 的真实升级与回滚。[构建记录](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml) · [完整使用说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.13.0/docs/USAGE.md) · [版本记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.13.0/CHANGELOG.md)

项目采用 GNU AGPL v3。完整包和便携包内含第三方许可。
