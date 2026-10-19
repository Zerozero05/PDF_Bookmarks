# 界面设计与兼容约定

更新日期：2026-10-19。本页记录v1.8.0界面改进及v1.8.1共用置顶；既有历史标签和附件保持原内容。发布是否完成及验证范围以发行页、Actions和验证记录为准。

## 设计方向

围绕“选择PDF → 生成或导入目录 → 校对 → 保存JSON → 预览并写入”组织界面。沿用既有主界面和目录工作台两个标签页，所有原按钮、选项、快捷键、拖放和安全确认继续可用。

- 统一蓝灰背景、清楚的输入边界和表格层次。蓝色只突出预览、保存等主要操作；辅助提示使用较弱但可读的文字颜色。
- 写入设置集中分组，状态独立成行；工作台的搜索与筛选分行，减少横向拥挤。保留系统字体和字号，统一小范围留白。
- 两页顶部共享夜间模式选择，默认浅色；原设置文件保存light/dark，schema仍为1。夜间模式覆盖本程序的控件、编辑区、预览背景及帮助窗口；PDF页面图片保留原像素，Windows文件选择和系统提示框由系统绘制。
- 切页共用当前窗口位置、大小和最大化状态，启动时统一最小1000×760；连续拖宽期间合并内部布局，停止变化约80毫秒后以最终尺寸排版，排版本身仍需额外时间。短暂保持旧内容布局是避免每像素重排的取舍。

- 原有交互优先：目录列表Enter仅确认用户选中的条目并定位下一待核对项，支持多选、撤销和草稿；搜索框Enter查找，编辑框Enter只提交编辑。无效目标页或空标题整批拒绝，外观整理不取消人工确认或自动写入PDF。

## 实际借鉴来源

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

必要检查包括：浅色和深色的主要文字、提示、待核对与选中项对比度；已打开和后创建的下拉菜单；最小1000×760共享窗口和原独立工作台1000×720的控件可见性；切页/缩放/拖动与关闭；草稿、预览、识别、JSON/CLI、更新与PDF写入回归。实际通过、失败、跳过与未验证范围以[验证记录](../VALIDATION.md)为准，不能用设计清单代替执行结果。

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
