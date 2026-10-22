# v1.11.0

PDF_Bookmarks 是 Windows 本地 PDF 书签工具，可独立处理普通 PDF，也适配 Zotero 附件。支持文字/扫描目录识别、目录 JSON 导入编辑、预览校对、拖放及批量写入，保持原 PDF 文件名和路径。

本版集中精简菜单与重复页头，补充目录添加/移动快捷键及 F1 内的个人键位设置，并修复帮助窗口长详情的底栏裁切。面向 **Windows 10/11 x64**；Single 与 Portable GUI 功能相同，无需安装 Python。沿用原七项下划线命名附件，历史版本、标签和资产保留。

## 更新内容

1. **三菜单与页面去重**：顶部仅保留“编辑 / 视图 / 帮助”。编辑按当前工作页显示适用命令；视图只保留外观、两页共用的专注模式及恢复本页默认布局。移除主界面重复项目名和目录/更新页头按钮，为内容腾出空间。
2. **原功能仍可找到**：文件选择继续使用页面内浏览、添加和拖放，目录生成/编辑通过工作台标签进入；草稿、校对、展开折叠、写入设置及页码定位保留页面、局部菜单和快捷键入口。“帮助 → 版本与更新…”承接原版本检查、下载及安装，发现新版时显示提示。
3. **添加及移动快捷键**：默认 **Ctrl+N** 添加目录项，**Alt+↑ / Alt+↓** 上移/下移，菜单同步标注。无需 Insert 或 Fn，适合98键等键盘；只在目录列表获得焦点时触发，复用原添加/移动与层级检查，不接管输入框。
4. **F1设置15项常用命令**：按 F1 打开“快捷键表”，选中可修改项，点“修改快捷键…”，按下组合后点“应用”；提供“恢复所选默认”和“全部恢复默认”。涵盖添加、移动、编辑标题、确认、删除、选择、展开折叠、撤销重做、草稿、查找及页码定位，表格和相关菜单显示当前键位。
5. **键位与原操作保护**：拒绝重复、冲突和保留组合，保留 Ctrl+C/V/X、F1、工作页切换、Alt+F4 等固定操作。搜索/编辑框 Enter、鼠标手势和窗口操作不变；无效设置或保存失败保留现有键位，命令仍受原焦点、选择、忙碌、无效编辑及目标页检查约束。
6. **帮助窗口底栏修复**：先为修改、恢复和关闭控件预留空间，再布局标签内容；选中长说明时底栏保持可见，不扩大默认窗口尺寸。帮助继续使用非模态窗口，重复打开复用，Esc关闭。

本轮沿用项目既有 Tk/ttk 与命令实现，没有新增外部设计借鉴、第三方代码或运行依赖。此前设计来源及本轮取舍见[界面设计](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.11.0/docs/UI_DESIGN.md)。

## 兼容性与使用提醒

- JSON仍为version 1，CLI参数、批量配对、本地OCR、自动/手选单栏双栏、人工区域/栏线、三种节编号，以及编号与标题间空格、去除数字节号前§的规范保留；本版不修改OCR或编号算法。
- 未设置个人键位时沿用默认 Enter确认并下一待核对、Delete删除、Ctrl+A全选、加减展开折叠及Ctrl+Z/Y/S等。自定义后以F1表的当前键位为准；处理列表和输入框保持各自原作用范围。Ctrl+S默认仅暂存草稿，不正式导出JSON或写入PDF。
- 自动识别仍需人工校对；未知/越界页或空标题拒绝确认/写入。原路径临时副本写入、校验后原子替换和备份默认开启保持；成功后删除输入JSON和茉莉花缓存仍为独立、默认关闭选项。处理列表移除不会删除磁盘文件。
- 设置继续位于 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`，新增可选 `editor_shortcuts`，schema仍为1，无迁移；缺字段使用默认键位，旧偏好和未知字段保留。查看F1说明不写用户资料；应用或恢复键位才保存对应设置，没有关联程序设置的帮助窗口只供查看。
- 日间/夜间/护眼、共享专注、共用置顶、布局记忆、图标A及预览滚轮/缩放继续保留；PDF图像保持原色。Windows原生菜单、标题栏及系统对话框可能使用系统配色。
- 复杂版式、模糊扫描、罗马页码或缺页仍可能需要手工修正，不承诺任意文档无识别错误。

## 下载文件与区别

七项附件的用途如下；Single 与 Portable GUI 按使用方式择一下载。

| 文件 | 用途 |
| --- | --- |
| [PDF_Bookmarks_v1.11.0_win_x64.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64.exe) | Single单文件GUI，直接运行；启动时临时解包运行库 |
| [PDF_Bookmarks_v1.11.0_win_x64_portable.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64_portable.zip) | Portable文件夹GUI，完整解压后运行PDF_Bookmarks\PDF_Bookmarks.exe；保留_internal和package-manifest.json |
| [PDF_Bookmarks_v1.11.0_win_x64_cli.exe](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64_cli.exe) | CLI命令行程序，用于脚本和批量处理 |
| [PDF_Bookmarks_v1.11.0_win_x64_full.zip](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64_full.zip) | GUI、CLI、完整源码、测试、示例及许可；GUI位于PDF_Bookmarks\dist\PDF_Bookmarks.exe |
| [PDF_Bookmarks_v1.11.0_win_x64_portable.zip.sha256](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/PDF_Bookmarks_v1.11.0_win_x64_portable.zip.sha256) | Portable ZIP独立校验 |
| [SHA256SUMS.txt](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/SHA256SUMS.txt) | 附件SHA-256清单 |
| [update-manifest.json](https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.11.0/update-manifest.json) | 程序更新清单，无需手动运行 |

两种GUI功能一致；“便携”指免安装，两者共用本机设置和草稿。Portable主要省去启动解包，不保证OCR或PDF写入更快。

## 升级与验证

- v1.5.0及后续Single/Portable GUI可从旧“帮助 / 更新”检查已公开正式版；新版入口为“帮助 → 版本与更新…”。下载校验后由用户选择安装并重启，保留发行类型、实际名称、位置和设置。先保存目录、关闭工作台内容并等待任务结束。v1.4.1、CLI和源码手动下载，Portable须完整解压。
- 本机1.11.0正式身份源码728项：727通过、1跨盘环境跳过、0失败/错误；171文件隔离快照完成Single/Portable/CLI/helper四构建及身份、资源和helper核验。实际Single内12个应用模块由宿主Python/Tk执行390项全部通过，32项运行指纹前后稳定；这些本机结果不代替云端重建、公开附件校验或390项冻结鼠标/键盘场景。
- 沿用1.10.0身份的实际冻结试用已检查Ctrl+N添加、Alt+↑/↓移动及撤销恢复原6条目录；最终帮助布局修复版看到对应默认键位，长详情后修改/恢复/关闭控件完整，实际关闭成功。真实冻结自定义组合录入/应用尚未验收：工具输入会激活所有者窗口，未完成Ctrl+M录入，不能用源码或宿主测试替代此项观察。
- 正式发布须以1.11.0身份重新测试并构建Single/Portable/CLI/helper，执行真实冻结升级、健康检查和失败回滚四场景，核对七项草稿资产后才公开；失败不发布。真实全书OCR、所有DPI/多屏等未覆盖范围继续如实记录。实际结果以[Actions](https://github.com/Zerozero05/PDF_Bookmarks/actions/workflows/windows-build.yml)、发行页及[验证记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.11.0/VALIDATION.md)为准。

[完整使用说明](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.11.0/docs/USAGE.md) · [全部更新记录](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.11.0/CHANGELOG.md) · [维护流程](https://github.com/Zerozero05/PDF_Bookmarks/blob/v1.11.0/docs/MAINTENANCE.md)

沿用GNU AGPL v3，第三方许可随完整包和便携包提供；无签名或准确率保证的新增宣称。
