# 界面设计与兼容约定

更新日期：2026-10-18。本页记录v1.8.0的界面改进；v1.7.0及更早历史标签和附件保持原内容。发布是否完成及验证范围以发行页、Actions和验证记录为准。

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
