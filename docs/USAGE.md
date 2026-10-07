# PDF_Bookmarks 完整使用说明

本页说明 PDF_Bookmarks 的使用方式及单文件、便携文件夹两种打包形式。当前正式发行版仍是 [v1.4.1](https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v1.4.1)，v1.5.0 为新增自动更新的待试用版本；既有 PDF/目录功能与默认设置保留。源码命令均在仓库根目录执行。项目首页见 [README.md](../README.md)，维护流程见 [MAINTENANCE.md](MAINTENANCE.md)。

当前 Windows 版：**v1.4.1**。新增可选的“写入成功后删除目录 JSON”，默认关闭，并记住上次选择。v1.4 的自动编辑、多选改层级、JSON 保存目录、独立目录工作台，以及原有拖放、预览、写入、批量、备份和茉莉花缓存清理功能保留。

v1.2.1 修复滚动区域背景框遮挡内容的问题：拖入文件后的处理列表、预览后的书签树、目标页图片和处理记录现在能够正常显示和点击。关闭旧程序后换用新版 EXE 即可，原有设置自动保留；PDF 写入、备份、缓存清理和命令行逻辑没有改动。

把 `toc.json` 中的章、节、小节写成 PDF 内部的 Outline / Bookmarks，直接更新原 PDF 路径。普通 PDF 可独立使用，不需要安装 Zotero；处理 Zotero 附件时无需删除旧附件或重新附加新 PDF。中文界面、中文文件名和中文书签均支持。

**写入仍使用 PDF 和目录 JSON。没有 JSON 时，可先从 PDF 提取文字或使用内置的本地 OCR 生成目录，再校对和保存。** 它添加阅读器左侧的书签，不给正文插入目录页，也不修改 PDF 的页面标签。

## 最快开始：Windows 可执行版

选择以下任一种 GUI，无需安装 Python：

| 下载文件 | 打开方式 |
| --- | --- |
| [PDF_Bookmarks_v1.4.1_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.4.1/PDF_Bookmarks_v1.4.1_win_x64.exe) | 单文件版，直接运行；每次启动会临时解包运行库 |
| [PDF_Bookmarks_v1.4.1_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.4.1/PDF_Bookmarks_v1.4.1_win_x64_portable.zip) | 便携文件夹版，完整解压后运行 `ZoteroPDFBookmarks\ZoteroPDFBookmarks.exe` |
| [PDF_Bookmarks_v1.4.1_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.4.1/PDF_Bookmarks_v1.4.1_win_x64_full.zip) | 完整包，含源码、CLI、说明和单文件 GUI；解压后运行 `ZoteroPDFBookmarks\dist\ZoteroPDFBookmarks.exe` |

便携版须让 EXE、`_internal` 与其余文件保留在同一文件夹内；移动时移动整个 `ZoteroPDFBookmarks` 文件夹。它省去每次启动的临时解包，功能与单文件版相同，不承诺每页 OCR 或 PDF 写入提速。完整 Windows ZIP 中的 GUI 仍是单文件版，与便携 ZIP 不同。单文件 GUI、CLI 和完整包使用 `SHA256SUMS.txt` 校验；便携 ZIP 使用 `PDF_Bookmarks_v1.4.1_win_x64_portable.zip.sha256` 校验。此次只调整发布页下载文件名，ZIP 内部文件名、程序窗口名称和设置路径保持原样。

1. 从发布页下载所选程序，按上表打开。程序面向 Windows 10/11 x64。
2. 找到需要添加或更新书签的 PDF，关闭这本 PDF 的阅读窗口。
3. 选择原 PDF 和对应的 `toc.json`；没有 JSON 时，点上方“生成 / 编辑目录…”。
4. 点“1. 预览”，在处理列表中选中一本书，展开目录并点击标题，在右侧核对实际目标页图片。预览不修改 PDF，也不创建备份。
5. 勾选需要处理的 PDF，按需设置备份、目录 JSON 删除等选项，再次预览，点“2. 写入勾选的 PDF”。在 PDF 阅读器中重新打开原文件，查看书签及跳转位置。

处理 Zotero 附件时，先在 Zotero 中右键附件，选择“显示文件”定位原 PDF，再按上述流程处理；完成后重新打开同一附件。若准备清除茉莉花缓存，处理前须完全退出 Zotero。存储附件、链接附件和刷新同步的说明见后文 Zotero 专节。

可以把 PDF、目录 JSON 或文件夹直接拖进已经打开的程序窗口，也可以把多个路径拖到 `.exe` 图标上启动。中文和带空格的路径均支持。

- 单个 PDF 会自动查找旁边的同名 `.toc.json`；也可以同时拖入一个 PDF 和一个 JSON，即使两者不同名。
- 多本书一起拖入时，按文件名配对，如 `书名.pdf` 对应 `书名.toc.json`。明确拖入的同名 `书名.json` 也可配对。不同文件夹中有重名附件时，优先同目录匹配；无法唯一确定的配对需要手工选择。
- 只拖入 JSON 时，可用于当前选中的 PDF。批量文件夹扫描仍要求每个 PDF 旁有同名 `.toc.json`；包含 Zotero storage 子目录时勾选“包含子文件夹”。
- 拖放只准备输入；仍须先预览，再确认原地写入。

默认遇到已有书签时跳过。确实需要更新时，选择“替换已有书签”，重新预览后写入；替换覆盖当前整棵书签树，不合并旧目录。GUI 的写入按钮在预览后才可用，更改输入或策略后必须重新预览。

## 界面中的五项便捷功能

1. **记住上次设置**：正常关闭窗口后，保存备份开关、备份文件夹、清理缓存及删除目录 JSON 选项、子目录选项、已有目录处理策略、最近浏览目录、窗口大小和置顶状态。目录工作台另记住自身大小、独立置顶及 JSON 保存位置。第一次启动仍使用备份开启、缓存清理关闭、目录 JSON 删除关闭的默认值。CLI 不读取 GUI 设置。
2. **窗口内拖放**：支持 PDF、JSON、多个文件及文件夹，按上述规则配对；缺少目录文件会在处理列表中显示，避免漏看。
3. **树状目录和目标页预览**：显示章、节、小节层级及印刷页码到 PDF 实际页码的对应关系。点击标题只读取目标页图片，不改动源 PDF。快速切换目录时以最后一次选择为准。预览图片用于核对，不提供批注编辑。
4. **批量处理列表**：逐本显示目录匹配、校验和写入状态，可勾选参与写入的文件。缺少 JSON 或校验失败的文件不会写入；单本失败不阻止其他已勾选文件。若目录 JSON 放在其他文件夹，先预览文件夹，再拖入对应同名 JSON 补配，重新预览即可。处理详情保留在记录中。
5. **右上角“置顶”开关**：勾选后窗口保持在普通应用窗口上方，切换浏览器或 Zotero 时仍可看到它；取消后恢复普通窗口行为。主窗口与目录工作台分别记住自己的选择。首次升级时工作台沿用旧主窗口的置顶设置，此后可以独立取消或开启。

两种 GUI 共用设置文件 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`，切换打包方式无需迁移设置。便携版也把设置保存在当前电脑，不放进程序文件夹、Zotero storage 或 PDF 文件夹。设置损坏时使用默认值；想恢复默认设置，可以关闭程序后删除这个设置文件。

“写入选项”中提供：

- **写入前备份原 PDF**：第一次启动默认勾选，以后记住上次选择，可以取消。关闭备份后仍会使用临时副本、校验和原子替换，但不会留下本次原文件的备份。
- **备份文件夹**：留空时使用各 PDF 旁的 `_backup`；选择自定义文件夹后，单本或批量的所有备份都存放到该文件夹，文件名包含时间戳和随机标识。关闭备份后，此字段停用。
- **写入成功后删除同目录的茉莉花缓存**：默认不勾选，仅删除 PDF 所在文件夹的 `jasminum-outline.json`，规则见后文。启用前完全退出 Zotero。
- **写入成功后删除目录 JSON**：默认不勾选，勾选后仅删除本次使用的目录描述文件，可位于 PDF 旁或其他文件夹，也可与 PDF 不同名。PDF 原地写入并通过原有校验后才删除；预览、取消、已有书签跳过或写入失败均保留。批量中共用一个 JSON 时，等使用它的所有勾选 PDF 全部写入成功再删除，有跳过或失败则保留。JSON 在预览后被修改、无法核对或无法删除时保留并提示，PDF 仍算写入成功。该选项不扫描其他 JSON，也不清除设置文件或 `jasminum-outline.json`；茉莉花缓存继续由其独立选项控制。若要保留 JSON 以便再次导入，请不要勾选。此新增选项仅在 GUI 中提供，命令行行为保持原样。

## 从源码安装与运行

需要 Windows 和 Python 3.10 或更高版本，安装 Python 时保留 pip 和 Tcl/Tk（桌面 GUI），推荐 Python 3.12 x64。解压项目后：

1. 双击 `setup.cmd`，安装依赖到项目自己的 `.venv`。
2. 双击 `launch_gui.cmd`。也可把一个 PDF 或文件夹拖到这个启动文件上。

在 PowerShell 中手动安装：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe gui_entry.py
```

依赖固定为 PyMuPDF 1.28.2、tkinterdnd2 0.6.3、RapidOCR 3.9.2、ONNX Runtime 1.22.1、NumPy 2.2.6、OpenCV 4.11.0.86；打包依赖为 PyInstaller 6.22.3。源码也可在安装 PyMuPDF 的其他系统使用原命令行；Windows 可执行包只能在 Windows 运行。

## 从 PDF 生成目录与校对

主窗口顶部只有一个“生成 / 编辑目录…”入口，作用于当前选中的一本书。目录工作台的“从 PDF 生成”和“编辑已有 JSON”两个标签共用下方的目录表格、编辑区、页码映射和目标页预览；切换标签保留当前修改，不会自行开始识别。工作台是独立窗口，打开它时仍可操作主窗口；右上角保留最小化、最大化、关闭按钮，界面另有独立的置顶开关。PDF 操作继续在同一个工作线程中依次执行。

1. 点“生成 / 编辑目录…”，直接把原 PDF 拖进目录工作台，或使用浏览按钮。可以只添加 PDF，暂时不提供 JSON；主界面已有选中的 PDF 时会自动带入。
2. 在“从 PDF 生成”标签中点“自动识别目录”。目录页起止范围留空时，程序检查 PDF 前 25 页并读取找到的连续目录页；已知目录位置时填写实际 PDF 页，例如起页 10、止页 12，避免扫描无关页面。文字版优先提取文本，扫描版使用本地 OCR，进度会显示在窗口中，可以取消识别。
3. 查看生成的层级、标题、印刷页、实际 PDF 页和可信提示。程序根据中英文篇、章、节、小节编号、上下文及缩进推断层级；例如英文 Chapter 后的无编号标题归为其子项，跨目录页继续保留章节上下文。缩进判断会给出核对提示。程序根据印刷页码与标题等证据建议页码映射；无法确定的目标页留空，不会猜一个数字并写入。
4. 点击条目核对右侧目标页。在下方编辑标题、层级和页码后会自动更新草稿，也可按 Enter 立即应用；切换条目时提交当前有效修改，不必逐项点击“更新选中项”。双击单元格可直接编辑，原更新按钮继续保留。尚未填完或无效的内容须先改正，避免切换时丢失修改。前言的罗马页码或重复印刷页码应直接指定 PDF 实际页码。
5. 固定偏移例如 `+12` 表示印刷第 1 页对应 PDF 第 13 页。遇到缺页、插页时，可使用分段映射：每行填写“印刷起页, 印刷止页, PDF 起页”，例如 `1,100,13` 和 `101,200,114`。每段范围包含两端。
6. 核对后勾选“已核对目标页”，确认状态立即更新到表格。确认所有条目时仍会提醒先检查结果；没有有效目标页的条目不能确认或保存。修改条目或重新应用映射后，相关条目需要重新确认。
7. 在工作台底部选择 JSON 的保存位置：默认使用原目录文件所在位置（新生成时使用 PDF 旁的同名 `书名.toc.json`），也可以选择自定义文件夹。自定义路径会记住，下次无需重新浏览。点“保存 JSON 并返回”直接使用该位置，已有文件仍需确认覆盖；需要临时改文件名或路径时使用“另存为…”。工作台只保存 JSON，不写 PDF，也不删除插件缓存。保存后回到原处理列表并进行只读预览；如果主窗口正在处理，会等待结束后载入，仍须使用原“写入勾选的 PDF”完成写入。

批量改层级：在目录表中用 Ctrl 或 Shift 多选，保持表格获得焦点后按数字键 1–9，设置选中项的层级；也可以按住选中行的层级列横向拖动，向右增加层级数字、向左减少，每移动约 30 像素调整一级，松开时应用。拖动修改层级，不重排条目。操作会检查完整层级序列，第一项须为一级，后项不能跳过尚未出现的上级；不合法时保留原结果并提示需要调整哪些选中项。标题或页码输入框中的数字仍作为输入文字。

已有 JSON 时，将对应 PDF 和 JSON 一起拖入工作台，会自动切到“编辑已有 JSON”并载入；也可先后拖入，两者齐全后自动载入。只拖入 JSON 时优先使用当前 PDF，没有当前 PDF 则尝试同目录同名 PDF。只拖入 PDF 时会查找同目录同名 `.toc.json`，找到则进入编辑，否则进入生成。不同文件夹中的 PDF / JSON 也可一起拖入，单本明确配对不要求同名。标题、列表、输入框或预览区均可接收拖放。

“编辑已有 JSON”标签也提供浏览与“载入 JSON”按钮。原位置模式默认沿用已载入 JSON 的文件夹和文件名；重新识别生成新目录后默认使用 `书名.toc.json`。工作台一次编辑一本书，多本书或文件夹请拖入主窗口的批量列表；切换标签不会丢弃当前目录，但重新识别、载入另一个 JSON 或更换 PDF 会替换当前编辑内容。工作台只支持 PDF 与 JSON，不把其他文件解释成目录。若拖放不响应，使用普通权限启动程序，保持与文件资源管理器相同的运行权限。

“复用已有书签”可以将 PDF 当前的书签载入编辑，但旧目录可能并不完整。自动提取的条目默认都需要校对，可信提示是识别与页码证据的提示，不是准确率保证。中英混排、数学符号、双栏/双页目录、模糊扫描、缺页等可能需要手工补全。识别出的目录不等于已遍历全书验证每个标题，保存前请抽查章首与末尾目标页。

Windows EXE 包含中文/英文 OCR 模型和 CPU 运行库，识别不上传 PDF、不调用在线服务、不要求 API Key，也不需要另装 OCR 软件。内置模型使新版文件比旧版大。源码安装需要下载依赖，打包版运行时从包内加载本地模型；模型文件缺失会报错，不会改为在线下载。

## 准备目录文件

`examples\toc.json` 是固定偏移示例，`examples\toc.segmented.json` 是插页造成偏移变化的分段示例。**这些只是格式示例，标题、页码和偏移须按你的书核对，不是某本书经过校验的完整目录。** 单个 PDF 可以选择任意 JSON 文件名；批量模式必须同名：

```text
书名.pdf
书名.toc.json
```

最小可用格式：

```json
{
  "version": 1,
  "mapping": { "offset": 10 },
  "bookmarks": [
    {
      "title": "第1章 基本概念",
      "page": 1,
      "children": [
        {
          "title": "1.1 定义",
          "page": 2,
          "children": [
            { "title": "1.1.1 例子", "page": 3 }
          ]
        }
      ]
    }
  ]
}
```

所有 **PDF 实际页码均从 1 开始**：封面是 PDF 第 1 页。不要用阅读器显示的印刷页标签来当 PDF 实际页码。

| 字段 | 含义 |
| --- | --- |
| `version` | 必填，当前为整数 `1` |
| `mapping.offset` | `PDF 实际页码 = 印刷页码 + offset`，允许正、零、负整数；省略 `mapping` 时偏移为 0 |
| `bookmarks` | 必填，非空数组，数组顺序就是书签顺序 |
| `title` | 必填，非空标题，支持中文 |
| `page` | 正整数印刷页码，经过 mapping 得到实际 PDF 页码 |
| `pdf_page` | 直接指定实际 PDF 页码；与 `page` 二选一 |
| `children` | 可选，子书签数组；嵌套表达章、节、小节等层级 |

例：印刷第 1 页是 PDF 第 11 页，则 `offset=10`。确认下一章也具有相同偏移后再用固定偏移。

分段映射已经实现：

```json
"mapping": {
  "segments": [
    { "printed_start": 1, "printed_end": 100, "pdf_start": 11 },
    { "printed_start": 101, "printed_end": 200, "pdf_start": 113 }
  ]
}
```

每段两端都包含在范围内，公式为 `pdf_start + page - printed_start`。上例印刷第 100 页跳到 PDF 第 110 页，印刷第 101 页跳到 PDF 第 113 页。整个示例要求 PDF 至少 212 页。

`offset` 和 `segments` 不能同时存在；印刷页码区间不可重叠；段内映射范围也不能越过 PDF 总页数。印刷页码未被任何段覆盖时会报错，不猜测偏移。某一处缺页或插页需拆成新的段。前言的罗马页码、同一本书中重复的印刷页码、无法用单个区间标识的部分，用 `pdf_page` 直接指定。

文件编码为 UTF-8，兼容 UTF-8 BOM；JSON 不支持注释或末尾多余逗号。页码不得是字符串、小数或布尔值。程序拒绝未知字段、重复字段、空目录和越界目标，避免把拼写错误默默忽略。

## 命令行

源码入口：`launch_cli.cmd`；本地构建或完整包中的可执行入口：`dist\ZoteroPDFBookmarks-CLI.exe`；发布页单独下载的 CLI 文件名为 `PDF_Bookmarks_v1.4.1_win_x64_cli.exe`。下面的命令在项目文件夹中运行，也可把 `launch_cli.cmd` 替换为所用 CLI 的实际路径。

```powershell
# 预览同名目录文件
.\launch_cli.cmd preview "D:\文献\书名.pdf"

# 预览指定 JSON
.\launch_cli.cmd preview "D:\文献\书名.pdf" --toc "D:\目录\toc.json"

# 备份并原地写入；已有书签则默认跳过
.\launch_cli.cmd write "D:\文献\书名.pdf" --toc "D:\目录\toc.json"

# 更新已有目录（覆盖全部旧书签）
.\launch_cli.cmd write "D:\文献\书名.pdf" --existing replace

# 不创建 PDF 备份，仍先校验临时副本再原子替换
.\launch_cli.cmd write "D:\文献\书名.pdf" --no-backup

# 将备份放入自定义文件夹
.\launch_cli.cmd write "D:\文献\书名.pdf" --backup-dir "E:\PDF备份"

# 成功写入后清除同目录的茉莉花旧缓存；请先完全退出 Zotero
.\launch_cli.cmd write "D:\文献\书名.pdf" --existing replace --clear-jasminum-cache

# 正式命令也支持强制 dry-run
.\launch_cli.cmd write "D:\文献\书名.pdf" --dry-run

# 批量预览，含子文件夹；此命令不写入
.\launch_cli.cmd batch "D:\文献" --recursive

# 批量写入，只有带同名 .toc.json 的 PDF 才参与
.\launch_cli.cmd batch "D:\文献" --recursive --write

# 批量使用统一备份目录，并在各 PDF 成功写入后清除同目录的缓存
.\launch_cli.cmd batch "D:\文献" --recursive --write --backup-dir "E:\PDF备份" --clear-jasminum-cache

# JSON 处理报告；可以自行重定向保存
.\launch_cli.cmd batch "D:\文献" --recursive --json
```

`preview`、`write` 和 `batch` 均接受 `--no-backup`、`--backup-dir`、`--clear-jasminum-cache`。`--no-backup` 与 `--backup-dir` 互斥，同时提供是参数错误；不提供时默认备份到 PDF 旁的 `_backup`。这些选项在预览或 dry-run 中只展示设置，不创建备份或删除缓存。

`batch` 默认预览，必须加 `--write` 才写入；`--dry-run` 优先于 `--write`。缺少 JSON 的文件只报告并跳过，单本失败不阻止其他文件。递归扫描排除 `_backup`、`.venv`、`.git`、`__pycache__` 和本工具临时文件；自定义备份文件夹是待处理文件夹的子文件夹时也会排除。不跟随子目录的符号链接；遇到无权限子目录会报告错误。自定义备份文件夹可以与待处理文件夹相同，这种情况不会跳过整个输入文件夹；后续扫描可能把其中备份报告为缺少同名 JSON 并跳过。

进程退出码：0 表示操作完成（包括默认跳过或缺少同名 JSON）；1 表示存在读取、校验或 PDF 写入失败；2 表示命令参数错误。PDF 已成功写入、但缓存删除失败时给出提示，单独出现该提示仍返回 0。

JSON 报告区分 `preview`、`written`、`skipped`、`missing_toc`、`error`，其中 `action` 是正式模式的预期动作。`backup_enabled`、`backup_directory`、`clear_jasminum_cache` 记录所选设置；实际备份路径见 `backup`，未创建时为 `null`。成功写入的记录另有 `cache_status`（`not_requested`、`not_found`、`deleted` 或 `failed`）和 `warnings`，用来区分 PDF 写入结果与缓存清理结果。

## Zotero 默认 storage 附件

以“显示文件”得到的真实路径为准，不要求改动 Zotero 的存储结构，例如：

```text
C:\Users\你的用户名\Zotero\storage\AB12CD34\书名.pdf
```

单本：选择该 PDF 和目录 JSON即可。批量：在各 PDF 旁放好同名 `书名.toc.json`，选择 Zotero 的 `storage` 文件夹，勾选“包含子文件夹”。没有对应 JSON 的附件会跳过。也可在命令行使用：

```powershell
.\launch_cli.cmd batch "C:\Users\你的用户名\Zotero\storage" --recursive
.\launch_cli.cmd batch "C:\Users\你的用户名\Zotero\storage" --recursive --write
```

原 PDF 文件名、路径、附件条目和父条目关系保持不变。工具不读写 `zotero.sqlite`，不调用 Zotero API，不迁移存储目录。PDF 内的现有页面、页面顺序和页面对象保持不变。Zotero 自身批注存储在数据库中，本工具不编辑它；已嵌入 PDF 的批注也不主动修改。仍应以你的书为样本检查书签跳转和原有批注显示。

## Zotero 链接附件

同样通过“显示文件”定位链接指向的真实 PDF，例如 `D:\文献库\书籍\书名.pdf`。选择该路径原地处理，或按同名 JSON 规则处理这个文件夹。不需要转换为存储附件。这里的“链接附件”是 Zotero 附件类型；操作系统中的符号链接 PDF 暂不支持。

Zotero 对存储附件和链接附件的同步方式不同：存储附件可通过 Zotero/WebDAV 文件同步，链接附件本身不由 Zotero 文件同步上传。链接附件若由其他云盘同步，应避免云盘和工具同时修改同一文件。

## 写入保护、备份和恢复

每次实际写入自动执行：

1. 核验 PDF 与预览时的 SHA-256 一致，建立该 PDF 的工具锁。
2. 如果启用备份，创建所选备份目录（留空则是同目录 `_backup`），以时间戳加随机标识备份原文件；校验备份与原文件字节一致，不覆盖已有备份。关闭备份时跳过此步骤。
3. 在原 PDF 旁建立临时副本，只对临时副本增量写入书签，保留原 PDF 的字节前缀和文件标识。
4. 重开临时 PDF，核验书签标题/层级/目标页、总页数、页面对象、元数据和原字节前缀，刷新文件修改时间并刷写磁盘。
5. 再核对原文件未变化，用同目录原子替换更新原路径，清理本次临时文件和锁。
6. 如果启用茉莉花缓存清理，在 PDF 成功替换后删除同目录的 `jasminum-outline.json`。

不会原地打开原文件直接写入；备份失败、目标页错误、校验失败或替换被 Windows 拒绝时，工具停止该文件。成功的其他批量文件不会回滚。普通文件系统上的同目录原子替换避免半写入原文件；这不等于断电、磁盘故障、网络文件系统或其他软件并发覆盖的绝对保证。处理时关闭该 PDF 的阅读窗口，暂停会写该文件的同步/编辑操作，工具锁只能协调本工具的其他实例。

备份示例：

```text
书名.pdf
书名.toc.json
_backup\书名.20261003-143015-123456.a1b2c3d4.pdf
```

恢复方法：关闭该 PDF，从 `_backup` 或所选自定义备份文件夹选择要恢复的版本，复制到原目录并改回 **原 PDF 文件名**，覆盖当前文件，再在阅读器中重开；Zotero 用户重新打开同一附件即可。先保留当前版本可方便撤销恢复。备份是每次写入前的文件，不一定都是首次处理前的版本；按时间选择。关闭备份的写入不会生成可供本工具恢复的原 PDF。需要完整 Zotero 库恢复时，还应单独备份 Zotero 数据目录，因为这些备份只包含 PDF。

异常关闭后可能留下 `.书名.pdf.bookmarks.lock` 或 `.书名.pdf.bookmarks.*.tmp`。先确认工具及其其他实例已结束，再删除这本书对应的残留锁/临时文件即可重试；不要删除原 PDF 或 `_backup`。增量替换只更新最新逻辑目录，旧目录对象仍可能留在 PDF 历史字节中，重复更新会略增文件体积。

程序会拒绝加密/密码保护 PDF、检测到签名标志或签名字段的 PDF、需要修复或不支持增量保存的 PDF，不自动解密、去签名或重写整个文档。

## 茉莉花旧大纲缓存

若使用茉莉花（Jasminum）插件后仍显示旧大纲，可以勾选“写入成功后删除同目录的茉莉花缓存”，或加命令行参数 `--clear-jasminum-cache`。**操作前须完全退出 Zotero，包括仍在运行的后台进程**；只关闭 PDF 标签页不够，否则 Zotero 或插件内存中的旧大纲可能再次写回缓存。处理结束后重新启动 Zotero、打开同一附件查看目录。

工具只处理当前 PDF 所在文件夹中的 **`jasminum-outline.json`**。存储附件通常可在 PDF 所在的 `storage\附件键` 文件夹找到该文件。链接附件的插件缓存可能位于 Zotero 自己的 `storage\附件键` 中，而不在链接 PDF 旁；本工具不定位或删除这些其他位置的缓存，不保证覆盖链接附件的插件缓存。

只在对应 PDF 成功写入后删除缓存；预览、dry-run、默认跳过已有书签和写入失败都保留缓存。缓存不存在时无需删除。若删除失败，PDF 仍算成功写入，并在界面或命令行显示提示，JSON 中为 `status: "written"`、`cache_status: "failed"`；不会为缓存清理失败回滚已经写入的 PDF。缓存是符号链接或同时是本次输入的目录 JSON 时也会保留并提示。

缓存清理默认关闭，清理的是插件旧大纲文件，不删除 PDF 或 Zotero 数据库中的批注。PDF 备份也不包含该缓存；如需保留旧插件大纲，可在启用清理前单独复制这个 JSON。

## Zotero 刷新与同步注意事项

- 写入后关闭 PDF 阅读标签页，再从同一个附件重新打开，查看左侧目录；若仍是旧内容，重启 Zotero。
- 启用茉莉花缓存清理时，先完全退出 Zotero再处理，完成后重新启动；不要在 Zotero 仍运行时清缓存。
- 不要导入备份或重新附加处理后的 PDF，原附件已经指向更新后的路径。
- 文件修改时间会更新，但本工具不操控 Zotero 的同步状态。需要多设备使用时，在 Zotero 发起同步，并在另一设备核对；本项目未实测你的 Zotero/WebDAV/云盘环境，不承诺立即检测或上传外部修改。
- 若同步出现冲突，先核对时间和备份再选择版本。不要把“重置同步历史”当作常规刷新手段。

## 程序自动更新（v1.5.0 及以后）

在主窗口点“帮助 / 更新”查看版本、Single/Portable 类型和正式发行版页面。启动后后台检查最多每 24 小时一次，可取消自动检查；手动“检查更新”不受间隔限制。

发现新版后先阅读更新内容及下载大小，点“下载更新”。下载在后台运行，可以继续处理 PDF；校验通过后才出现可用的“安装并重新启动”。安装前保存目录编辑并关闭目录工作台，等待 PDF 写入、目录识别、JSON 保存和页面预览结束，再点击安装。存在占用时程序会提示，保留当前窗口与任务。

更新继续使用原程序路径和 EXE 名：Single 保持单个主 EXE，Portable 保持完整文件夹，不相互转换。Portable 根目录和主 EXE 均可改名，也可整体移至其他磁盘；须保留完整运行文件和 `package-manifest.json`。程序只清理已安装清单确定属于旧程序的文件，个人 PDF、文本、配置和自建文件夹保留；若新版文件与未知用户文件同名，则停止安装并提示处理冲突。

程序更新不会重置设置。两种 GUI 仍共用 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`；新版默认补齐新增设置、保留未知字段，配置需要迁移时先备份并验证。新版初始化失败将恢复旧程序与旧配置；成功后删除旧程序备份和更新临时文件，仍被运行中的 helper 占用的内容由后台重试或下次启动继续清理。

**从 v1.4.1 升级时须先手动下载新版本**，旧版没有更新入口。当前 v1.5.0 尚待用户试用确认，先从本地构建或 Actions 产物试用。源码运行及 CLI 使用发行版页面手动下载；程序不会覆盖 Python 解释器或把 CLI 替换为 GUI。未点击安装而直接退出时，已准备的更新会被取消；“退出时安装”和“跳过此版本”列入后续阶段。

权限不足时先关闭程序并移动到可写目录重试，或明确选择以管理员权限运行；不在替换一半后请求提权。更新失败诊断保存在本程序临时更新目录的 `diagnostics`，机制与恢复说明见 [AUTO_UPDATE.md](AUTO_UPDATE.md)，验证边界见 [UPDATE_ACCEPTANCE.md](UPDATE_ACCEPTANCE.md)。

## 打包与验证

在 Windows 上双击 `build_exe.cmd`：安装打包依赖、运行测试，先构建独立 updater，再生成 GUI/CLI 单文件 EXE 和 GUI 便携文件夹版。输出在 `dist`，便携版输出到 `dist\portable\PDF_Bookmarks`，构建中间文件在 `build`。命令行等效步骤：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/build_windows.py
.\.venv\Scripts\python.exe scripts/smoke_binaries.py
.\.venv\Scripts\python.exe scripts/package_release.py
```

便携版的入口是 `dist\portable\PDF_Bookmarks\PDF_Bookmarks.exe`，必须连同 `_internal`、`package-manifest.json` 和运行文件夹一起分发；发布 ZIP 随附本项目及第三方许可。两种 GUI 使用相同源码、依赖和 OCR 模型，构建类型在打包时嵌入。打包前新增源码应已加入 Git 索引，因为完整包只收录 Git 管理的文件。发布文件与 manifest 自动生成，规则见 [MAINTENANCE.md](MAINTENANCE.md#发布命名与校验清单)。

打包须在目标系统上进行，迁移前的 v1.4.1 二进制在 Windows x64、Python 3.12.14 上构建；GitHub 自动构建使用 Windows x64、Python 3.12，具体环境见对应运行日志。未进行 Windows ARM64、32 位系统或所有 Windows 版本兼容性实测。写入测试只使用自动生成的临时 PDF，覆盖中文路径、多层目录、偏移映射、已有书签、内容/批注保持、备份和失败保护，以及备份设置和缓存清理规则；真实书籍仅用于只读目录识别，未修改真实 Zotero 附件或缓存。迁移前已完成验证见 [VALIDATION.md](../VALIDATION.md)，云端测试结果以 Actions 页面为准。

## 项目文件

| 文件 | 用途 |
| --- | --- |
| `bookmarks_core.py` | JSON 校验、映射、可选备份、增量写入、原子替换与成功后缓存清理 |
| `bookmarks_gui.py` / `gui_entry.py` | 中文界面、文件拖放、批量列表、目录与目标页预览 |
| `gui_support.py` | 用户设置、拖入文件配对与只读页面渲染 |
| `build_info.py` / `config_manager.py` | 稳定构建身份、原设置兼容、schema 与迁移事务 |
| `updater/` / `updater_entry.py` / `update_dialog.py` | 更新检查、下载、清单、外部事务、健康确认、回滚与 GUI 入口 |
| `toc_generation.py` | 文字/OCR 目录识别、页码建议、确认校验与 JSON 保存 |
| `toc_editor.py` | 目录识别、映射、编辑和目标页校对窗口 |
| `bookmarks.py` | 命令行入口 |
| `setup.cmd` / `launch_gui.cmd` / `launch_cli.cmd` | 源码安装与启动 |
| `build_exe.cmd` / `hook-tkinterdnd2.py` / `hook-rapidocr.py` | Windows 打包、拖放组件与离线 OCR 模型收集 |
| `examples` | 固定偏移和分段目录示例 |
| `tests` | 安全写入及界面功能回归测试 |

## 官方参考与第三方许可

- [PyMuPDF Document API](https://pymupdf.readthedocs.io/en/latest/document.html)：`get_toc`、`set_toc`、增量保存和 `no_new_id`。
- [Zotero 存储附件与链接附件](https://www.zotero.org/support/attaching_files)：两种附件的路径和同步差异。
- [Zotero 批注存储方式](https://www.zotero.org/support/kb/annotations_in_database)：内置阅读器批注位于数据库。
- [Zotero 同步设置](https://www.zotero.org/support/preferences/sync)：附件文件同步。
- [PyInstaller 使用说明](https://pyinstaller.org/en/stable/usage.html)：`--onefile`、`--windowed` 打包。
- [TkinterDnD2 官方说明](https://github.com/Eliav2/tkinterdnd2)：原生文件拖放与 PyInstaller 打包。
- [RapidOCR 官方文档](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/install/)：OCR 模型与本地推理依赖。

本项目以 AGPL v3 提供，完整条款见 [LICENSE.txt](../LICENSE.txt)。PyMuPDF/MuPDF 使用 AGPL 或商业许可，随附程序包含其开源版本；完整项目源码与依赖版本同时提供。重新分发或用于其他项目时，按 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) 和 [licenses](../licenses) 中的许可办理。
