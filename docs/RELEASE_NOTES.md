# v1.6.0

PDF_Bookmarks 是 Windows 本地 PDF 书签工具，可独立处理普通 PDF，也适配 Zotero 附件。支持文字/扫描目录识别、JSON 导入与编辑、预览校对、拖放和批量写入，保持原 PDF 的文件名与路径。

本版增强双栏目录识别，增加手选目录布局、三种节编号方式，以及目录工作台的滚轮滚动和缩放。面向 **Windows 10/11 x64**；Single 与 Portable GUI 功能相同，均无需安装 Python。发行版标题只使用版本号，附件沿用原下划线命名。

## 更新内容

1. **双栏按阅读顺序识别**：完整读取左栏后再读取右栏，分别匹配标题与页码，减少同一水平线上的两栏被拼成一行。自动判断需要两侧独立目录证据，避免把单栏标题与远端页码、附录编号或数学片段误拆成两栏。
2. **加强分栏 OCR 与层级连续性**：确定双栏后按栏补读并与原识别结果合并，保留原完整条目；残缺行从同栏图像重读标题和页码，保护已有章/节号与已读数字。章节上下文跨栏、跨页继续，缩进按所属栏判断；右栏不会仅因横坐标较大就被当作深层目录。跨栏不拼接残缺标题，不借现有书签代替识别或凭顺序猜页码。
3. **可手选目录布局**：“从 PDF 生成”中新增“自动”“单栏”“双栏”。默认自动；自动判断不理想时可手选后重新识别。单栏按整页读取，双栏按左/右栏读取并补充 OCR；只切换选项不改变已有草稿，也不重识别导入 JSON 或复用书签。
4. **节编号方式可选**：新自动目录按所选方式规范，默认“章.节”，例如 `1.1 基本概念`；“每章节号”显示 `1. 基本概念`，每章独立；“保留识别编号”不为无编号节补号。修正原书 `1. 基本概念` 等节号被重复补成 `1.1 1. 基本概念` 的情况，中文/英文节号同样按所选方式处理。继续保留编号与标题间一个空格，省略数字号前的 `§`。切换从原始识别标题计算，保护手工修改、手工新增、导入 JSON 及复用书签；只调整可确定章上下文的直接子节，不改变层级、页码或映射，标题变化后须重新确认。
5. **预览滚动与缩放**：鼠标放在目录工作台右侧预览图片上，滚轮上下滚动；Ctrl＋滚轮缩放，也可点击“放大”“缩小”“100%”。范围 **50%–300%**，100%为原预览大小，尽量保留视图中心；切换 PDF 页从顶部显示。局部滚轮绑定保留左侧列表操作，快速缩放合并渲染并拒绝过期帧，不预先缓存整本书。

继续保留 v1.5.1 的扫描文字方向候选比较、点线分离短标题重读、书末独立条目，以及待校对、目标页确认和写入保护。

## 使用方法

1. 从主窗口打开“生成 / 编辑目录…”，选择或拖入原 PDF。
2. 填写实际 PDF 目录页范围；不知道时可留空自动查找。选择目录布局及节编号方式；要重新识别原书时取消“复用 PDF 已有书签”。
3. 点“自动识别目录”，核对条目顺序、章/节层级、标题和实际目标页。自动判断不理想时，改选单栏或双栏并重新识别；重新识别会替换当前草稿，先保存需要保留的编辑。
4. 点击条目，在右侧滚动或缩放预览核对；必要时手改标题、层级与页码，补充未识别条目。选择节编号方式不会替你确认结果。
5. 逐项确认后保存 JSON，回到主窗口重新预览，再使用“写入勾选的 PDF”完成原路径写入。目录工作台和右侧预览本身不写 PDF。

默认推荐“自动布局＋章.节编号”。已知双栏可直接选“双栏”；希望沿用原书编号时选“保留识别编号”并校对，空格与数字号前§仍按既有规范处理。每章节号适合本章内部阅读，跨章引用时须同时注明章号。

## 兼容性与限制

普通 PDF 无需安装 Zotero。Zotero 附件通过“显示文件”定位原 PDF，关闭阅读窗口后处理，完成后重新打开同一附件，无需重新附加。可选茉莉花缓存清理仍须先完全退出 Zotero，默认关闭。

JSON 格式、CLI 参数、页码映射、确认/保存、备份、校验后原子替换及更新机制保持兼容。设置仍使用 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`，`CONFIG_SCHEMA=1`；新增目录选项只用于当前工作台，不增加持久设置或配置迁移。没有新增外部框架、在线 OCR、模型下载或运行依赖。

自动结果都是待校对草稿，可信提示不是准确率保证。跨栏长标题、同页混合单/双栏、重叠或模糊扫描、数学符号、上标、缺页及未标印刷页码的条目仍需手动处理。双栏与布局选择不能保证任意 PDF 层级准确，也不等于已逐页验证正文。保存前请核对章首、跨栏衔接与末尾目标页。

## 下载文件与区别

以下七项沿用既有命名；可下载状态以本发行页实际附件为准。

| 文件 | 用途与运行方式 |
| --- | --- |
| [PDF_Bookmarks_v1.6.0_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/PDF_Bookmarks_v1.6.0_win_x64.exe) | Single单文件 GUI，直接运行；启动时临时解包运行库 |
| [PDF_Bookmarks_v1.6.0_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/PDF_Bookmarks_v1.6.0_win_x64_portable.zip) | Portable文件夹 GUI，完整解压后运行 `PDF_Bookmarks\PDF_Bookmarks.exe`；保留 `_internal`、`package-manifest.json` 与全部运行文件 |
| [PDF_Bookmarks_v1.6.0_win_x64_cli.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/PDF_Bookmarks_v1.6.0_win_x64_cli.exe) | 命令行程序，适合脚本和批量处理 |
| [PDF_Bookmarks_v1.6.0_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/PDF_Bookmarks_v1.6.0_win_x64_full.zip) | Single GUI、CLI、源码、测试、示例和许可；GUI入口 `PDF_Bookmarks\dist\PDF_Bookmarks.exe` |
| [PDF_Bookmarks_v1.6.0_win_x64_portable.zip.sha256](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/PDF_Bookmarks_v1.6.0_win_x64_portable.zip.sha256) | 便携 ZIP 的独立 SHA-256 校验文件 |
| [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/SHA256SUMS.txt) | 正式附件的 SHA-256 校验清单 |
| [update-manifest.json](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/update-manifest.json) | 程序检查/验证 Single 和 Portable 更新所用的清单，无需手动运行 |

两种 GUI 功能相同，Portable主要省去启动解包，不保证每页 OCR 或写入更快；移动时保留整个文件夹。两者共用原设置路径，“便携”指免安装，设置仍保存在当前电脑。文件名统一为 `PDF_Bookmarks_<版本>_<系统>_<架构>[_类型].<扩展名>`，不改用连字符或加入额外试用后缀。

## 从旧版升级

v1.5.0 及后续 Single/Portable GUI 可通过“帮助 / 更新”检查已经公开的正式版本，下载校验后由用户选择安装并重启；保留发行类型、用户改名后的入口和现有设置。安装前先保存目录编辑、关闭工作台并等待识别、预览或写入结束。CLI/源码从发行页手动更新。

v1.4.1 无自动更新入口，须手动下载本版。Single运行新EXE；Portable完整解压新文件夹，不能只复制主EXE。旧程序目录中自行保存的 PDF、目录 JSON 和其他资料保留。历史 Release、标签与附件不覆盖。

## 验证与证据范围

- **源码回归**：本机393项完整回归通过，覆盖 PDF/JSON 安全、CLI、目录识别、节编号、真实 Tk 预览事件和工作台、配置与更新事务；包含首次生成默认编号的三类原书节号回归。
- **上一试用包**：127项包内模块检查通过；该结果针对此前同功能试用 EXE，不能替代新正式版本的冻结构建检查，也不能表述为完整生产 EXE 界面交互通过。
- **本地正式包**：四种生产身份与资源核验通过；正式Single内嵌模块128项相关检查通过。真实冻结1.6.0→隔离合成1.6.1的Single/Portable成功升级和健康失败回滚共4场景通过，冻结CLI以临时PDF验证预览、原路径写入、原字节备份和默认跳过。合成版本不发布。包内模块测试使用宿主依赖，不等同于完整冻结GUI实书交互。
- **真实双栏样例**：只读识别《实分析与复分析》实际 PDF 第7–8页，自动和手选双栏均从旧版60项提升到147项（含“目录”入口），恢复20章。层级和目标 PDF 页与独立参照一致，源 PDF 哈希不变；原有书签仅作独立核对，没有用来生成识别结果。识别结果全部未确认。
- **仍需人工核对**：数学符号、上标和 OCR 错字；样例中未在目录标印刷页码的译者序、关于作者、前言需手动补录。这一实例不保证其他 PDF 的准确率，也不表示已逐页核对全书正文。
- **正式包与云端检查**：每次版本标签由 [Windows Actions](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml) 执行完整回归、四种构建身份/资源/许可、包校验及真实冻结更新/回滚验收，失败不发布。具体执行结果以对应运行和 [VALIDATION.md](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.6.0/VALIDATION.md) 为准，不以历史通过代替本次结果。完整冻结 GUI 的真实书籍 OCR 界面交互尚未验证。

[完整使用说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.6.0/docs/USAGE.md) · [版本记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.6.0/CHANGELOG.md) · [维护流程](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.6.0/docs/MAINTENANCE.md)

沿用 GNU AGPL v3，第三方许可随完整包和便携包提供。本地文件仅按当次明确授权清理：先核验远端可恢复并保存交接、展示固定路径清单，再执行；发布本身不自动删除用户资料或共享依赖。
