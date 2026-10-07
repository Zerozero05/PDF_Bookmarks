# 自动更新说明

v1.5.0 引入 Windows GUI 完整包更新。当前代码先供试用，正式发布须用户确认；v1.4.1 的标签、Release 和历史资产保留。v1.4.1 不包含此更新器，第一次升级需手动下载新版本。

## 使用方法

1. 主窗口点击“帮助 / 更新”，查看当前版本及 Single/Portable 类型。
2. 点击“检查更新”。默认启动后也会后台检查，同一配置最多每 24 小时一次；可以取消自动检查，手动检查不受间隔限制。
3. 阅读版本、更新内容和下载大小，选择“下载更新”。后台下载不占用 PDF 任务工作队列。
4. 校验成功后进入 READY。先保存目录编辑、关闭工作台并完成写入/识别/保存/预览任务，再点击“安装并重新启动”。
5. 新版完成配置、PDF 核心和主窗口初始化后确认成功；失败会恢复旧程序和旧配置。

Single 自动更新始终得到 Single；Portable 始终得到 Portable。当前实际 EXE 名、根目录、中文/空格路径和整体移动后的地址保持不变。源码 GUI 可手动检查更新；CLI 从发行版页面手动更新。两者都不会执行 GUI 自身替换。

本版不会强制安装或退出正在编辑的程序。直接退出时取消已准备但未获批准的安装；退出时安装、跳过特定版本、Beta UI、数字签名和差分更新属于后续阶段。

## 稳定身份与版本

| 字段 | 当前值及用途 |
| --- | --- |
| `APP_ID` | `com.linzh.PDFBookmarks`，与仓库、EXE 及目录名称解耦 |
| `APP_VERSION` | 从 `VERSION` 读取，当前待试用版本 `1.5.0` |
| `BUILD_VARIANT` | 构建时嵌入 `single` 或 `portable`，不按文件名/目录猜测 |
| `UPDATE_SCHEMA` | `1`，不兼容协议安全停止并提示手动下载 |
| `CONFIG_SCHEMA` | `1`，与应用版本解耦，本次没有结构迁移 |
| `UPDATE_CHANNEL` | `stable`，拒绝草稿、预发行版和其他通道 |
| `BUILD_ENTRYPOINT` | `gui`、`cli` 或 `updater`，仅冻结 GUI 允许自身安装 |

程序安装位置由当前 `sys.executable` 确定，工作目录不是安装目录。`sys._MEIPASS` 仅用于定位已嵌入的 helper 资源，不用于判断发行类型。相关运行时含义见 [PyInstaller 官方文档](https://pyinstaller.org/en/stable/runtime-information.html)。

## 下载与验证

从本仓库公开 GitHub Release 获取更新信息，无需秘密 Token。发布名继续使用 `PDF_Bookmarks_<版本>_win_x64[_类型]`；`update-manifest.json` 关联两种 GUI 资产，记录 APP_ID、版本、协议、通道、文件名、完整 SHA-256 与大小。

检查器核对 Release 标签和 manifest 版本一致、版本确实高于当前、发行类型及协议相容；下载只访问允许的 GitHub HTTPS 主机，并在发出重定向请求前验证新目标。完整下载先存 `.part`，限制大小、流式校验 SHA-256；任何失败不修改安装。GitHub 公开发布接口参考 [官方 Releases REST 文档](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)。

Portable ZIP 内的 `package-manifest.json` 列出所有受管理程序文件的路径、大小与 SHA-256。解压前拒绝绝对路径、路径穿越、Windows 特殊文件名、大小写重复、链接和清单之外的文件；逐文件验证哈希，检查 ZIP 条目集合与清单完全一致。manifest 本身不递归包含自己的哈希。

所有目标、事务和配置路径检查符号链接及 Windows 目录联接，防止更新越界。未知用户文件与新程序文件碰撞时拒绝覆盖，要求用户先保留并移走冲突文件。

## 外部事务与断电恢复

`updater.exe` 是小型独立 Single helper，构建时嵌入 GUI；运行时复制到程序目录之外：

```text
%TEMP%\PDF_Bookmarks_Update\tx-<随机标识>\
    updater.exe
    package.exe / package.zip
    new\
    backup\program\
    backup\config\
    journal.json
    health.json
    update.log
```

主程序保存设置并启动 helper 后安全退出。helper 等待同路径所有进程（包含 PyInstaller 启动进程）释放目标；不强杀仍在工作的其他窗口。独占安装锁阻止两个 updater 同时更新同一目标。修改前检查目录权限、程序/配置文件锁和下载、解压、备份、替换所需空间；权限不足安全停止，用户可移动到可写目录或明确以管理员权限运行。Windows 共享与锁定规则参考 [CreateFileW 官方文档](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)。

持久 journal 按原子替换与 fsync 保存，包含原/新版本、类型、实际目标、文件操作、旧文件哈希、配置快照和状态。每个替换先记录操作即将开始，再用目标目录内临时文件原子替换；在开始安装前完成所有旧文件备份。旧版不会在下载和验证前被删除。

```text
PREPARE → VERIFY → BACKUP → INSTALL → HEALTHCHECK → COMMIT
                                 任一失败 → ROLLBACK
```

健康回执同时核对事务随机 token、APP_ID、目标版本、发行类型、实际运行 EXE/PID，以及配置读取/迁移、PDF 核心和 GUI 初始化成功。进程启动本身不算成功。只有收到有效回执才能提交和删除备份。

中断后下次启动发现已开始而未完成的事务，会调用外部 helper 等待当前进程退出并恢复旧程序/配置，再启动旧程序。尚未获批准的 READY 下载不会因重开程序自动安装。已提交事务只继续清理，不再回滚；清理遇到运行中的 helper 会延后重试。

## Single 文件替换

记录当前 EXE 的实际绝对路径及名称，备份旧 EXE 和配置，再把下载的完整新 EXE 原子替换到原路径。官方资产名与用户入口名无关。例如 `E:\科研工具\我的 PDF.exe` 更新后仍是同一路径。新版未确认健康就失败时恢复旧 EXE，并按快照恢复旧配置字节。

成功提交后不在安装目录保留旧 EXE、`.old` 或 `.new`；下载和备份位于本 APP_ID 的临时事务目录并最终清理。

## Portable 文件管理

初次准备更新时，完整验证当前 `package-manifest.json` 和文件哈希，允许将清单的官方入口映射到用户改名后的实际 EXE，生成 `.pdf_bookmarks/installed-manifest.json`。后续更新比较旧已安装清单和新包清单：

| 文件类别 | 行为 |
| --- | --- |
| 旧清单证明属于程序的文件 | 可替换；新版废弃项删除；修改前备份 |
| 用户配置、UserData、预设等 | 不作为程序文件删除；配置迁移另走快照事务 |
| 用户 PDF、txt、自建目录等未知文件 | 保留；与新包路径碰撞时拒绝覆盖 |

主 EXE 映射到当前用户名称；根目录随当前 EXE 动态确定。不整目录覆盖，也不按“新版 ZIP 没有”删除所有旧文件。更新同时替换 package-manifest 和 installed-manifest；失败时与程序文件一同恢复。只有受管理文件造成的空目录才尝试删除，含用户文件的目录保留。

Portable 分发请保留完整文件夹、`_internal`、`package-manifest.json` 与运行文件。`.pdf_bookmarks` 是本机已安装状态，不进入发布 ZIP；用户无需自行编辑它。

## 配置兼容与迁移

继续使用 `%LOCALAPPDATA%\ZoteroPDFBookmarks\settings.json`。未标 schema 的原设置按 schema 1 读取，新增自动检查选项通过默认值补齐；原设置值和未知字段保留，应用更新不会重置目录/备份/置顶等选择。

**当前 `CONFIG_SCHEMA=1`，生产 `MIGRATIONS={}`，无需迁移。** 测试通过注入 schema 1→2→3 迁移验证框架，不代表生产配置现在采用 schema 3。malformed 或未来 schema 不在保存时被默认值覆盖；更新健康检查采用严格读取，不能读取则回滚。

未来若字段结构、类型、名称或语义发生不兼容变化，才提高配置 schema，逐级注册迁移。先保存原始字节快照，在副本执行迁移和 schema 校验，用临时文件原子替换正式配置；迁移失败原配置不变。更新事务的配置快照与程序备份一起保留，回滚时二者一致恢复。

## 清理、日志与故障处理

成功提交后删除程序/配置事务备份、下载包、解压目录和临时文件。helper 运行时无法删除自身：新主进程收到成功健康确认后后台重试，启动清理也会再次处理本 APP_ID 的已完成事务。未完成且仍需恢复的备份保留，不清理其他应用或整个共享临时目录。

清理期间保留归属 journal，先删除负载和已退出的 helper。最后删除 journal 与空目录前保存同 APP_ID、同事务且已终结的临时清理收据，关闭最后一步受阻或中断的恢复窗口；成功后收据一并删除。线程和安装锁协调并发清理；未知条目会保留并停止清理。helper 尚在解包时也不会被启动清理误判为失效事务。

失败诊断保存到 `%TEMP%\PDF_Bookmarks_Update\diagnostics`，最多保留最近 10 组 journal/log，不写入 Token 或密码。终端事务归属核验后清理原事务目录；回滚未完成时保留原始状态供继续恢复。日志可能包含程序和配置路径。

遇到提示时关闭占用窗口、检查可写目录/空间，保留原 PDF 与个人文件再重试。备份校验错误或无法回滚时保留事务日志和备份，停止覆盖；不要自行删除仍待恢复的 `backup`。正式发布前按 [发布检查清单](RELEASE_CHECKLIST.md) 和 [验收矩阵](UPDATE_ACCEPTANCE.md) 核对实际结果。

## 模块与构建

| 模块 | 责任 |
| --- | --- |
| `build_info.py` | 永久身份、单一版本源、嵌入 variant/入口 |
| `config_manager.py` | 默认值、未知字段保留、逐级迁移、快照/恢复 |
| `updater/checker.py`、`downloader.py` | GitHub 正式版本检查、可信 HTTPS、进度/校验 |
| `updater/manifest.py` | 协议、版本、路径及完整文件清单验证 |
| `updater/journal.py`、`transaction.py` | 原子持久记录、备份/安装/同步回滚 |
| `updater/processes.py`、`launcher.py` | 进程与文件释放检查、外部 helper 与恢复启动 |
| `updater/healthcheck.py`、`cleanup.py` | 实际初始化健康回执、归属与终态清理 |
| `updater/controller.py`、`update_dialog.py` | 更新状态机、单独后台队列、Tk 主线程界面 |
| `updater_entry.py` | helper 可执行入口 |
| `scripts/build_windows.py`、`package_release.py` | 两种 GUI 同源构建、清单/哈希/许可打包 |

SHA-256 和下载使用分块读取；更新队列与 PDF 队列分开且限制进度事件积累。helper 不重复打包 GUI、PDF/OCR 模型等大依赖。原 OCR 按需初始化保留；本版没有宣称运行内存的固定节省值。
