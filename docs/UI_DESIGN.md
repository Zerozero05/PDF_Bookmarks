# 界面设计与兼容约定

更新日期：2026-10-22。本页记录v1.8.0界面改进、v1.8.1共用置顶、v1.9.0交互优化及v1.10.0共享专注、图标与界面调整；既有历史标签和附件保持原内容。发布是否完成及验证范围以发行页、Actions和验证记录为准。

## 设计方向

围绕“选择PDF → 生成或导入目录 → 校对 → 保存JSON → 预览并写入”组织界面。沿用既有主界面和目录工作台两个标签页，所有原按钮、选项、快捷键、拖放和安全确认继续可用。

- 统一蓝灰背景、清楚的输入边界和表格层次。蓝色只突出预览、保存等主要操作；辅助提示使用较弱但可读的文字颜色。
- 写入设置集中分组，状态独立成行；工作台的搜索与筛选分行，减少横向拥挤。保留系统字体和字号，统一小范围留白。
- 两页共用外观选择，默认浅色；本地优化版在左上“视图 → 外观”统一日间/夜间/护眼，原设置文件保存light/dark/eye_care，schema仍为1。主题覆盖本程序控件、编辑区、预览背景及帮助窗口；PDF页面图片保留原像素，Windows文件选择和系统提示框由系统绘制。
- 切页共用当前窗口位置、大小和最大化状态，启动时统一最小1000×760；连续拖宽期间合并内部布局，停止变化约80毫秒后以最终尺寸排版，排版本身仍需额外时间。短暂保持旧内容布局是避免每像素重排的取舍。

- 原有交互优先：目录列表Enter仅确认用户选中的条目并定位下一待核对项，支持多选、撤销和草稿；搜索框Enter查找，编辑框Enter只提交编辑。无效目标页或空标题整批拒绝，外观整理不取消人工确认或自动写入PDF。

<a name="app-icon-design"></a>

## 图标 A 精修（2026-10-22，纳入v1.10.0）

用户从三款候选中选择 A，并要求继续美化。沿用蓝色文档、白色 V 形书签和右上折角，减少装饰，调整轮廓、留白及书签边距；透明背景不随日间、夜间或护眼主题改色，保持应用身份一致。

资源由本次调用的内置 ImageGen 生成与精修，没有复制第三方图标或引入新的组件库、字体、运行依赖。`assets/PDF_Bookmarks.png` 是光栅母版，不是 SVG 或其他矢量源；`assets/PDF_Bookmarks.ico` 从母版生成16至256像素的九档 Windows 图标。两者用途为应用标识，不能替代勾选、置顶等操作控件的状态反馈。生成提示词保存在本次本地交付目录 `PDF_Bookmarks_图标A精修_20261022` 的 `icon_prompts.md`，原始候选也随本地记录保留，不混入用户 PDF 或程序设置。

窗口图标及 Windows 单文件/便携 GUI 使用同一资源，保持已有标题、入口与命名。资源检查、冻结程序实际显示及尚未覆盖的 Windows 显示条件分别记入[验证记录](../VALIDATION.md)；资源存在或构建成功不能代替实屏检查，Windows 图标缓存与固定快捷方式也可能延迟显示。

<a name="help-menus-design"></a>

### 帮助与键盘导航的收纳（2026-10-22）

F1由用户主动打开非模态说明，不在主面板增设按钮、不抢占数据处理流程。两标签分别放操作说明和按作用区域整理的快捷键表；窄窗口中选中条目可阅读换行详情，保留原字号。帮助按owner复用，Esc或关窗释放；主题跟随现有刷新，外部独立宿主的主题不被重设。原帮助/更新入口保留，F1本身不联网或写文件。

四个顶层菜单保留已有命令，新增项目按文件/编辑/视图/帮助分组，目录校对用一层子菜单收纳。新菜单动作复用既有草稿、校对、查找、历史和预览方法，并按活动页/选择/忙碌状态禁用。Ctrl+Tab和反向组合仅导航工作页；针对程序内Notebook采用类绑定之前的局部绑定，先经过未完成编辑与busy校验，帮助窗口自己的标签不被接管。没有新增组件库、外部代码或运行依赖；延用本页已注明的低干扰分级与命令组织方法。验证层次见[验证记录](../VALIDATION.md)。

<a name="shared-focus-polish-design"></a>

## 共享专注与界面精简（2026-10-21，开发阶段记录，纳入v1.10.0）

视图菜单的专注是整个双标签窗口的一份状态；两个页面共用BooleanVar，显隐不提交用户输入、不改变目录/历史/预览或窗口几何，新建/重开工作台继承。旧双页偏好通过统一focus_mode兼容读取，不建立第二套专注逻辑。独立Toplevel仍保留可恢复菜单。

工具按任务分组对齐，减少外层装饰边框，使用主要/辅助按钮和小标题形成层次；预览页码/翻页、缩放与识别工具清楚组织，比例显示去重。书名与可编辑真实路径分开，辅助操作保留完整路径；空态提示只在无内容时出现，选择/勾选/确认的语义保持。布局恢复只影响pane/column记忆，不能重置业务数据或设置。

来源与采用内容：[Microsoft布局间距](https://learn.microsoft.com/en-us/windows/apps/design/basics/content-basics)用于一致留白/分组，[命令设计](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics)用于主要操作与菜单组织；[Sun Valley ttk theme](https://github.com/rdbende/Sun-Valley-ttk-theme)与[ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap)用于参考轻量控件轮廓、主次视觉状态和扁平层次。实现为本项目原有Tk/ttk代码，不复制库实现、不安装依赖、不替换树表/菜单/勾号或三主题。不采用CustomTkinter迁移路线；此次没有新增外部代码许可义务或资源打包要求。

新增快捷操作限制到活动工作台及适用焦点，F2复用原标题编辑，Ctrl+F/Ctrl+L只改变焦点；原快捷键和保存/确认保护保留。三主题、最小窗口、布局恢复、未完成输入、busy、关闭回调等需与原回归一起验证；真实冻结界面与源码/包内证据分别记录。

<a name="focus-menu-design"></a>

## 专注入口集中（2026-10-21，开发阶段记录，纳入v1.10.0）

两页专注模式只保留左上视图菜单入口；当时按活动页更新勾选和分别记忆；后续按用户要求改为上文的全局共享状态，v1.10.0以共享状态为准。移除重复页面复选框，独立Toplevel提供自己的视图菜单，恢复辅助区不再依赖已移除控件的pack锚点。默认值、数据处理及原控件保留。

方法参考[Microsoft命令设计](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics)与[布局间距](https://learn.microsoft.com/en-us/windows/apps/design/basics/content-basics)，只采用集中低频视图命令、减少重复入口的原则。另只读比较[Sun Valley ttk theme](https://github.com/rdbende/Sun-Valley-ttk-theme)、[ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap)、[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)，用于后续方案讨论；没有复制库代码、引入依赖、变更三主题或迁移框架。

<a name="focus-layout-design"></a>

## 首批界面升级（2026-10-21，开发阶段记录，纳入v1.10.0）

在原两页与菜单上增量加入专注布局、手动分栏/列宽记忆和局部右键。专注是原控件的可逆显示状态，不是第二套业务界面；常显退出入口，默认完整，不在选中行时自动反复展开/收起。操作位置稳定，切换不改窗口几何、数据、未完成输入或撤销/草稿。高级设置仍可找到。本段是首批实现记录；后续共享专注覆盖分别保存状态，v1.10.0以共享状态为准。

右键与原按钮调用同一方法；已选行保留多选，未选行须先通过现有编辑校验。菜单键只绑定列表，不截获输入框；忙碌、无目录或无选择时按真实上下文禁用。原生菜单保留Windows系统色与真disabled状态，不为外观重新实现菜单框架。

布局记忆只记录用户改变的分隔条和表头分隔线，自动stretch不回写；首次默认0/空映射保持原布局。恢复使用当前尺寸与相对比例，忽略隐藏页，关闭取消自有回调。字体/字号/三主题色值与勾号算法不动，统一单层边界和Tab留白；不采用装饰动画或额外侧边栏。

设计方法沿用已采用的[Microsoft导航原则](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics)：减少常驻低频入口，保持常用目的地明确；并沿用[可访问性设计](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/designing-inclusive-software)的标准控件、系统字体和焦点可见要求。实际实现是本项目Tk/ttk代码，无第三方代码复制、新依赖、安装或框架迁移。

<a name="本地简化与提示分级2026-10-21未发布"></a>

## 本地简化与提示分级（v1.9.0，2026-10-21）

主界面保留输入、预览、写入和生成目录入口，将详细写入选项收起，同时始终显示策略/备份/清理摘要。工作台保留高频操作，低频操作进入四个有文字标签的菜单；不是移除功能，也不改变用户选择。目录列表增加 Delete 与目录树 + / -，输入框键盘语义和原 Enter、数字改层级、鼠标拖动、撤销及草稿保留。

本轮按用户提出的 tooltip、toast、alert、popconfirm、modal 分级要求取舍，复用 Tk/ttk，不增加新依赖或通用弹窗框架：

| 需要 | 本程序采用方式 |
| --- | --- |
| 不熟悉的低频菜单或快捷操作 | 少量延迟出现的悬停/焦点提示，不抢焦点，离开/点击/隐藏/关闭即消失。 |
| 删除、暂存或写入完成 | 界面内状态摘要；写入完整说明保留在处理记录，减少重复成功弹窗。 |
| 需要用户解决的问题 | 保留原就地校验提示，以及实际失败/警告消息；不把错误仅放在会自动消失的提示里。 |
| 多项删除 | 默认简短确认，可由用户关闭；可撤销、取消不删除。 |
| 写入 PDF、覆盖文件、未保存资料或安装更新 | 保留原需要决定的确认及任务互锁，不能因简化跳过保护。 |

具体实现依据是本项目原流程和用户明确要求。未恢复到的外部聊天解说、未读取的视频或未核实的第三方设计，不当作已采用来源。主界面设置展开状态仅作用于本次窗口，删除询问选择使用原设置文件并兼容 schema 1。

<a name="全局入口与选择语义2026-10-21未发布"></a>

## 全局入口与选择语义（v1.9.0，2026-10-21）

按用户示例采用左上文字菜单，集中全局外观、低频文件和上下文编辑入口；高频按钮保留，菜单操作尊重当前列表焦点，输入框保持原文字快捷键。日间、夜间和暖色护眼共用同一偏好；不是改变PDF像素或医学效果承诺。

目录选择只影响当前筛选匹配行；灰色上下文祖先不自动加入全选，避免删除用户未筛出的条目。清除选择后，树加减号递归所有显示层级；选中时保留原节点操作。主处理列表把高亮选择和写入勾号明确分开，移除只改变会话列表，不删磁盘文件；保留原写入确认和后续安全检查。

主预览补上与工作台一致的滚轮/缩放习惯，限定在图像区域，不全局绑定。请求防抖、排队取消和token拒绝旧结果复用原线程结构。本次没有新增外部借鉴、依赖或框架；用户截图只作为菜单位置示例。

## 实际借鉴来源

<a name="菜单清晰度与悬停反馈修复2026-10-21本地未发布"></a>

### 菜单清晰度与悬停反馈修复（v1.9.0，2026-10-21）

Windows Tk 8.6.12 在非XP主题平台对禁用文字及快捷键绘制系统白色偏移高光；暗色菜单使双层文字明显。本地菜单修复版对原生菜单使用系统菜单色，保持真实disabled、原生命令和键盘语义，不伪造为可用项，不更换运行框架。其余控件、Combobox弹层和PDF周边仍跟随日间/夜间/护眼主题；PDF像素保持。

置顶附属按钮同步使用NOOWNERZORDER，且忽略经根窗口传播的子控件FocusIn，保留真正根激活和变量变更同步，以减少下拉期间的窗口重排。按钮/菜单按钮/下拉框增加悬停和焦点边框反馈，不改尺寸或再绑重复post。护眼改为更深的米绿分层底色，并检验辅助文字可读性。

首帧菜单透出在修后也可能出现，稳定后消失，不能仅据这一现象断言置顶遮挡；Windows淡入动画不在本程序修改范围。实际稳定画面、重复点击与置顶取消分别验证，不能用主题参数读取代替鼠标检查。

| 核对来源 | 实际采用内容 |
| --- | --- |
| [Tk 8.6.12 Windows菜单绘制](https://raw.githubusercontent.com/tcltk/tk/core-8-6-12/win/tkWinMenu.c) | 核对DrawMenuEntryLabel及DrawMenuEntryAccelerator禁用高光；按系统菜单色改善可读性，无代码复制。 |
| [Microsoft SetWindowPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos) | 核对SWP_NOOWNERZORDER语义，保持owner层次和原按钮晋降，不改变系统设置。 |
| [Tk 8.6.12 控件状态](https://raw.githubusercontent.com/tcltk/tk/core-8-6-12/generic/ttk/ttkWidget.c) | 核对Combobox进入/离开时使用原生hover状态，直接设置样式映射，不增加重复鼠标绑定。 |

本轮没有下载、安装或新增依赖；原有其他来源继续保留。

这里只借鉴设计方法，主题与布局代码由本项目自行实现，未复制第三方实现、安装新技能或增加运行依赖。现有GNU AGPL v3及第三方许可文件继续保留。参考文本不覆盖用户要求、当前项目接口和数据保护约定。

| 来源与固定版本 | 实际阅读范围与许可核验 | 本次采用 |
| --- | --- | --- |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/56ea9cf174ed86786187daa9de0e6247cb0747e4) | README相关章节、[完整SKILL.md](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/56ea9cf174ed86786187daa9de0e6247cb0747e4/.claude/skills/ui-ux-pro-max/SKILL.md)、[MIT许可](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/56ea9cf174ed86786187daa9de0e6247cb0747e4/LICENSE) | 可访问性优先；统一语义颜色；紧凑布局保持文字完整、焦点与结果稳定。 |
| [Anthropic frontend-design](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design) | [完整SKILL.md](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/SKILL.md)、[该技能Apache-2.0许可](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/LICENSE.txt) | 围绕PDF校对任务建立层级；减少装饰；动作名称直观，并用实际窗口复查。 |
| Microsoft Windows设计 | [布局与间距](https://learn.microsoft.com/en-us/windows/apps/design/basics/content-basics)、[Windows 11字体](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography)、[设计原则](https://learn.microsoft.com/en-us/windows/apps/design/design-principles) | 清楚的分组、留白和左对齐；保留熟悉的系统字体、窗口与键盘习惯。 |
| Microsoft官方检查方法 | [可访问性清单](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessibility-checklist)、[文字对比度](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessible-text-requirements)、[测试方法](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessibility-testing) | 检查主要文字、提示、选中和禁用状态；状态仍有文字说明，不能只靠颜色；自动回归与实际窗口检查结合。 |

skills.sh排行榜只作为发现入口，动态排名不是适用性或安全保证。“interaction design”“ui checker”并未唯一指定某个仓库，这里采用上表明确来源的交互与检查方法。未阅读上述仓库的全部脚本、数据和引用文件，不将这次参考阅读称为完整代码或安全审计。没有安装或运行Accessibility Insights、AccChecker或其他新检查工具。

未采用网页Hero、网页动画、玻璃特效、在线字体、React/Tailwind或框架迁移。Windows风格主要体现在配色、层次和操作一致性，当前仍使用项目已有Tk/ttk。

## 交付检查

必要检查包括：日间、夜间及护眼的主要文字、提示、待核对与选中项对比度；已打开和后创建的下拉菜单；最小1000×760共享窗口和原独立工作台1000×720的控件可见性；切页/缩放/拖动与关闭；草稿、预览、识别、JSON/CLI、更新与PDF写入回归。Windows标题栏、原生菜单栏和系统文件选择区域可能由系统外观绘制，不保证与Tk主题完全一致。实际通过、失败、跳过与未验证范围以[验证记录](../VALIDATION.md)为准，不能用设计清单代替执行结果。

## 共用置顶的增量设计（v1.8.1，2026-10-19）

只将两个内容区置顶开关合并到窗口级入口。两个标签使用同一BooleanVar，启动以旧主窗口topmost为准；保留旧配置字段和独立工作台默认接口，不改变其他默认选项及业务处理。

保留系统标题栏，不接管系统边框或窗口过程。使用现有Tk/ttk和Python标准库ctypes，让一个无独立任务栏/Alt+Tab入口、不激活的附属按钮依照系统报告的最小化按钮位置显示在其左侧。坐标来自当前窗口而非固定屏幕偏移；支持程序化移动、缩放、最大化和恢复检查，未验证的跨显示器DPI条件另行注明。主窗口被模态窗口禁用时拒绝置顶，关闭时释放自有回调。只有初始化不可用时才采用标签栏右侧单一入口，不复制到两个页面。

本次新增参考如下，仅核对接口和框架行为，没有复制第三方实现、安装技能或新增依赖；此前设计来源继续适用。

用户试用进一步暴露了置顶后的命中缺陷：Tk将主窗口置顶后，原生附属按钮仍在非置顶组，按钮被主窗口遮住，button.invoke检查无法发现。修正时显式用SetWindowPos同步按钮的TOPMOST/NOTOPMOST，保持不激活/不移动/不改尺寸；同一轮变量回调和激活处理结束后再合并同步，避免owner后执行的排列再次覆盖按钮，主窗口重新获得焦点时也同步。关闭取消待执行同步。按钮显示“置顶 / 取消置顶”。补验原生置顶组和按钮中心WindowFromPoint命中，并另行验证真实鼠标反复点击。本次修复沿用以下既有接口与来源，没有新增外部借鉴或依赖。

| 来源 | 实际采用内容 |
| --- | --- |
| Microsoft：[WM_GETTITLEBARINFOEX](https://learn.microsoft.com/en-us/windows/win32/menurc/wm-gettitlebarinfoex)、[TITLEBARINFOEX](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-titlebarinfoex) | 分配正确结构，读取最小化按钮的屏幕坐标，保留原生系统按钮。 |
| Microsoft：[窗口归属](https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#owned-windows)、[扩展样式](https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles)、[SetWindowPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowpos) | 附属窗口跟随主窗口、TOOLWINDOW/NOACTIVATE、移动时不改变激活和排列层次。 |
| [Tk 8.6.12 Windows窗口管理源码](https://github.com/tcltk/tk/blob/core-8-6-12/win/tkWinWm.c) | 只核对UpdateWrapper/TkpWmSetState相关行为：隐藏窗口首次映射才创建原生外层，override-redirect配合transient会成为裁剪子窗口。自有实现以不可见初始化取得真实外层并设置原生owner，不改Tk或复制其代码。 |
