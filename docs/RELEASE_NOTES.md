# v1.12.0

PDF_Bookmarks 是 Windows 本地 PDF 书签工具，可独立处理普通 PDF，也适配 Zotero 附件。支持文字/扫描目录识别、目录 JSON 导入编辑、预览校对、拖放及批量写入，保持原 PDF 文件名和路径。

本版集中优化均衡清爽界面、连续校对和局部重识别。面向 **Windows 10/11 x64**；Single 与 Portable GUI 功能相同，无需安装 Python。保留双标签、三菜单、三主题、共享专注/置顶及原七项附件命名。

## 更新内容

1. **界面字号与布局**：“视图 → 外观 → 界面字号”提供100% / 110% / 125%，两页、日志和F1同步，独立于PDF缩放。统一主次操作和错误反馈；小窗口的映射/编辑辅助区可滚动，Tab可将隐藏字段带入视口，底部保存操作保留。修复切页后字段未重映射、分段文本原滚轮失效，以及重复加载默认ICO造成的原生图标句柄累计。
2. **连续目录校对**：刷新保留目录树折叠、选中和视口；查找时临时展开祖先，清空后恢复。确认优先局部更新，减少整表重建。原Enter确认并跳下一待核对、Delete删除、Ctrl+A、加减展开折叠及自定义键位保持。
3. **问题清单与映射预览**：“草稿 / 设置 → 目录问题清单…”区分保存阻塞和复核提示，可定位筛选外的问题。字段显示具体错误且保留中间输入；“页码映射 / 高级 → 预览影响”只读显示改页、重核、未覆盖、越界及样例，再按原规则应用。
4. **原目录行与目标页对照**：“定位 → 同时对照原目录行”按需展开来源裁图与目标页。较高裁图可用滚轮/滚动条查看完整内容，保留图像像素、目标页独立缩放；没有可靠来源时不猜位置。
5. **所选标题批量处理**：“目录操作 → 批量修改所选标题…”先预览文字替换、添加/移除前后缀及空白处理，再明确应用。仅选中项改变，变化需重新核对，整次可一次撤销；空标题或过期预览拒绝应用，编号与数学内容保护保持。
6. **主列表筛选和单本详情**：按书名/状态筛选，保留文件顺序、配对和写入勾选。隐藏勾选仍计入写入总数；Ctrl+A先清除筛选再选中全列表。双击状态或右键“单本处理详情…”分别查看预览/写入、完整错误、备份和清理结果。
7. **局部重识别与明确采纳**：查看目录页后，在“识别工具”选择“重识别当前页 / 区域并比较…”或“强制本地 OCR 并比较…”，复用该页区域、栏线及布局。候选默认不选，只明确采纳所选新增/变化；缺失不删、歧义不强配、手工/已确认项默认保护。结合完整章节和原映射，只给接受子集按最终上下文补号；变化仍待确认，整次一次撤销。修复手工标题被错误沿用为OCR候选、导致真实差异消失的问题。
8. **帮助和响应**：F1按操作名、关键词和当前键位检索，帮助内Ctrl+F只定位帮助检索，保留15项自定义、冲突检查及恢复默认。减少重复历史序列化，保留80状态撤销。识别/目标页/来源裁图共享64MiB会话缓存数据预算，按PDF身份和参数隔离，文档变化失效、关闭释放；最多8图一批补读并在批间取消，保持单PDF线程。“最近识别与缓存诊断…”显示当前会话计时。

## 兼容性与使用提醒

- JSON仍为version 1，CLI参数、设置schema1及未知字段保留，无配置迁移；新增ui_scale是可选界面偏好。设置仍位于 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`。
- 保留自动/手选单栏双栏、区域/栏线、三种节编号、章名空格及去除数字节号前§的规范；导入JSON和手工标题不因自动识别规范被擅改。
- 自动识别仍是待核对草稿，OCR分数、诊断和候选不替代人工确认。未知/越界页或空标题仍拒绝确认/写入。原路径临时副本写入、校验后原子替换、可选备份及更新事务保持；删除目录JSON与茉莉花缓存仍为独立选项。
- Ctrl+S默认只暂存草稿，列表移除不会删除磁盘PDF；原快捷键、滚轮/缩放、拖放、批量配对及自动更新入口保持。
- 64MiB是缓存数据预算，不是总内存上限。大目录确认/检索实测改善，但部分首次建表测量变慢；不承诺全面提速、固定内存降幅或即时中断底层单次OCR。可见区域裁剪已评估，本版保留有界整页渲染。
- 多屏DPI及所有扫描书籍未穷举。110%字号/较高来源图滚动有真实Tk离屏矩阵验证，冻结实屏覆盖100%/125%、三主题与主要交互；工具注入组合曾额外捕获Alt，不能当作精确物理键全覆盖。

本轮沿用项目已有Tk/ttk、OCR模型和设计参考，没有新增外部组件实现或运行依赖。来源及取舍见[界面设计](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.12.0/docs/UI_DESIGN.md)。

## 下载文件与区别

| 文件 | 用途 |
| --- | --- |
| [PDF_Bookmarks_v1.12.0_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.12.0/PDF_Bookmarks_v1.12.0_win_x64.exe) | Single单文件GUI，直接运行；启动时临时解包运行库 |
| [PDF_Bookmarks_v1.12.0_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.12.0/PDF_Bookmarks_v1.12.0_win_x64_portable.zip) | 完整解压整个文件夹后运行PDF_Bookmarks\PDF_Bookmarks.exe；保留_internal与package-manifest.json |
| [PDF_Bookmarks_v1.12.0_win_x64_cli.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.12.0/PDF_Bookmarks_v1.12.0_win_x64_cli.exe) | CLI命令行程序，适合脚本与批量处理 |
| [PDF_Bookmarks_v1.12.0_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.12.0/PDF_Bookmarks_v1.12.0_win_x64_full.zip) | GUI、CLI、完整源码、测试、示例与许可；GUI在PDF_Bookmarks\dist\PDF_Bookmarks.exe |
| [PDF_Bookmarks_v1.12.0_win_x64_portable.zip.sha256](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.12.0/PDF_Bookmarks_v1.12.0_win_x64_portable.zip.sha256) | Portable ZIP独立校验值 |
| [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.12.0/SHA256SUMS.txt) | 附件SHA-256清单 |
| [update-manifest.json](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.12.0/update-manifest.json) | 程序更新清单，无需手动运行 |

两种GUI功能相同，按使用方式择一；“便携”指免安装，两者仍共用本机设置和草稿。Portable主要省去启动解包，不保证每次OCR或写入更快。

## 升级与验证

v1.5.0及后续Single/Portable GUI可在“帮助 → 版本与更新…”检查正式版，下载校验后由用户选择安装并重启；保留发行类型、实际名称、路径和设置。先保存目录、关闭工作台内容并等待任务结束。CLI、源码及v1.4.1手动下载，Portable须完整解压。

本批已验收试用源码共881项：880通过、1跨盘环境跳过、0失败/错误，四构建同源/资源和冻结CLI核验通过。实屏复验局部候选默认保护、明确接受一条及一次撤销，其余八条全部字段保持；独立草稿比较15项与12项通过。正式版本身份验证另记[验证记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.12.0/VALIDATION.md)，不把试用或源码测试冒充所有冻结鼠标场景。

正式发布工作流依次运行源码回归、四构建、资源/打包检查，以及Single/Portable成功升级和健康失败回滚四场景；门禁失败不公开。最终结果见[Actions](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml)，下载以[发行页](https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v1.12.0)为准。

[完整使用说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.12.0/docs/USAGE.md) · [全部更新记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.12.0/CHANGELOG.md)

沿用GNU AGPL v3，第三方许可随完整包和便携包提供；保留历史版本、标签及附件。
