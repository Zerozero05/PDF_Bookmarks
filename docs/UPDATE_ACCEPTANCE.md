# v1.5.0 更新验收矩阵

本文件逐项映射更新规格 §45 的 Single 16 项、Portable 22 项和配置 12 项。测试仅使用合成程序、临时 PDF/JSON、隔离设置及构建产物，不修改真实文献、Zotero 库或用户配置。

## 当前验证状态与边界

2026-10-07，更新清单/路径、Windows 进程/文件锁、Single/Portable 事务等 **53 项核心自动化测试已通过**，含本机实际 C→D 跨盘移动、目录联接拒绝、文件独占打开、清理受阻及中断后重试。该数字仅对应 `test_update_manifest.py`、`test_update_processes.py`、`test_update_transaction.py`，不能代替完整回归或冻结程序验收。

| 验证层 | 当前记录 |
| --- | --- |
| 全量源码回归（含原 PDF/GUI/OCR 行为） | 2026-10-07 完整回归 303 项通过，26.536 秒；含原有 155 项行为回归及新增更新/配置/清理故障回归 |
| Single / Portable / CLI / 外部 helper 实际构建 | Windows x64 生产四项及隔离 1.5.1 的 helper/Single/Portable 三项实际构建通过；七份源码指纹一致，嵌入身份、OCR/运行库/许可及 GUI 内嵌 helper SHA-256 检查通过 |
| 冻结 CLI 原 PDF 行为 | 实际 EXE 预览只读、原路径写入中文书签、默认备份保留原字节、已有书签默认跳过通过 |
| 真实冻结 Single 成功更新 | 1.5.0→隔离 1.5.1 通过；EXE 改名、中文/空格路径、D→C 跨盘部署，真实 GUI/config/PDF 核心健康回执有效；原设置和用户文件保留 |
| 真实冻结 Single 健康失败回滚 | 新版读取 malformed 配置失败，实际恢复旧 EXE 和配置原始字节并重新启动旧 GUI，通过 |
| 真实冻结 Portable 成功更新 | 文件夹和 EXE 改名、移动至 C 盘通过；更新后 1148 个管理文件、新增/替换资源与旧 DLL 删除核对通过，额外 PDF/txt/UserData/自建目录保留 |
| 真实冻结 Portable 健康失败回滚 | 实际恢复旧 EXE、完整运行库、package/installed manifest 和配置原始字节，旧 GUI 重启通过 |
| GitHub CI / commit / PR | 本页记录本机验收；远端 CI、提交与产物记录列在对应工作分支 PR 的验证说明和 Checks 中。v1.5.0 尚未正式发布 |

冻结程序验收要求读取实际 BuildInfo、核对更名后的 EXE 字节、看到配置/GUI/PDF 核心三项健康回执，再确认 journal 提交、废弃 managed 文件清除、未知文件与设置保留、helper/备份/ZIP 最终清理。失败分支必须核对旧 EXE、旧 manifest 与配置原始字节恢复；“能启动”不算更新成功。

本机上述四个冻结场景全部通过；每项均等待应用自行删除事务目录和外部清理收据，再确认用户文件原字节及安装目录无 `.old`、`.new`、`.part`、`.pdf-update-*` 残留。自动化没有代替应用执行最后清理。另对真实 GitHub v1.4.1 latest 接口和其 309 字节 SHA256SUMS 下载进行了只读校验；尚未发布的 1.5.0 完整资产线上下载不作为已执行结果。

配置保留以旧 GUI 正常关闭后保存的完整配置为基准，逐字节及逐字段核对，包含窗口尺寸。旧窗口可能按既有最小尺寸或屏幕限制调整初始请求；冻结样本使用 640×480 请求来覆盖这一差异，更新不得重置其实际已保存的尺寸。此项保持原程序的窗口保存行为。

冻结脚本通过真实外部 helper 直接发起事务，使用真实 GUI/config/PDF 核心健康流程；更新按钮、安装任务守卫、异步复制与关闭事件由真实 Tk 源码测试覆盖。构建 smoke 核对两个 GUI 所携带 helper 的内容与独立 helper 一致。当前远端正式版本仍为 v1.4.1，1.5.1 是隔离的验收版本，不上传正式发行版。

权限和磁盘不足测试使用故障注入加真实 Windows readonly/file-lock 检查；不为测试填满真实磁盘或更改用户目录 ACL。跨盘测试在具备两个可写磁盘时执行，只有一个磁盘的 CI 明确跳过该项；符号链接测试可能因系统权限跳过，Windows 目录联接测试单独验证。真实断电不能由普通单元测试替代：自动测试用持久 journal 加安装中断模拟，检查恢复逻辑。

## 测试名称约定

下面 `T` 表示 `tests/test_update_transaction.py` 的 `TransactionTests`，`P` 表示 `tests/test_update_processes.py` 的 `ProcessTests`，`M` 表示 `tests/test_update_manifest.py` 的 `ManifestTests`，`N` 表示 `tests/test_update_network.py`，`C` 表示 `tests/test_config_compatibility.py` 的 `ConfigCompatibilityTests`。表中的方法名都是实际测试，不以预期功能代替验证。

运行完整源码验证：

```powershell
python -m unittest discover -s tests -v
```

## Single：16 项

| 编号 | 场景 | 对应自动测试 |
| --- | --- | --- |
| S01 | 原始文件名更新 | T.`test_original_name_single_and_other_single_not_managed`；T.`test_single_name_move_path_matrix` 的 original 子例 |
| S02 | EXE 改名后更新 | T.`test_single_name_move_path_matrix` 的 renamed 子例 |
| S03 | EXE 移动目录后更新 | T.`test_single_name_move_path_matrix` 的 moved 子例 |
| S04 | 改名 + 移动 | T.`test_single_name_move_path_matrix` 的 renamed_moved 子例；冻结 Single 成功场景 |
| S05 | 中文路径 | T.`test_single_renamed_moved_chinese_space_path_success`；T.`test_single_name_move_path_matrix` 中文子例 |
| S06 | 空格路径 | T.`test_single_name_move_path_matrix` 的 directory with spaces 子例 |
| S07 | 无写权限 | T.`test_no_write_permission_preflight`；T.`test_windows_readonly_target_prevents_install` |
| S08 | 磁盘不足 | T.`test_disk_space_failure`；N.`DownloadTests.test_disk_space_failure_stops_before_network_and_creating_partial` |
| S09 | 下载中断 | N.`DownloadTests.test_network_disconnect_progress_error_and_interruption_remove_partial`；N.`DownloadTests.test_early_midstream_and_eof_cancellation_leave_no_download` |
| S10 | SHA-256 错误 | T.`test_hash_error_never_modifies_program`；N.`DownloadTests.test_bad_hash_short_oversized_or_wrong_declared_size_remove_partial` |
| S11 | manifest APP_ID 错误 | M.`test_identity_variant_schema_version_and_hash` 的 app_id 子例；N.`UpdateCheckTests.test_mismatched_manifest_app_variant_protocol_version_or_hash_is_rejected` |
| S12 | variant 错误 | M.`test_identity_variant_schema_version_and_hash` 的 variant 子例；N.`UpdateCheckTests.test_stable_release_selects_only_the_current_build_variant` |
| S13 | 主程序/其他实例未退出 | P.`test_main_or_other_instance_prevents_install`；T.`test_other_instance_and_lock_stop_before_backup` |
| S14 | 新版健康检查失败 | T.`test_health_failure_rolls_back_program_and_migrated_configuration`；T.`test_missing_health_receipt_times_out_and_rolls_back`；冻结 Single 失败场景 |
| S15 | 回滚 | T.`test_persistent_journal_recovers_interrupted_replace`；T.`test_health_failure_rolls_back_program_and_migrated_configuration` |
| S16 | 成功无残留 | T.`test_single_renamed_moved_chinese_space_path_success`；T.`test_cleanup_failure_after_commit_does_not_rollback`；冻结 Single 成功场景 |

## Portable：22 项

| 编号 | 场景 | 对应自动测试 |
| --- | --- | --- |
| P01 | 原目录名更新 | T.`test_portable_rename_move_matrix` 的 PDF_Bookmarks 子例 |
| P02 | 文件夹改名 | T.`test_portable_rename_move_matrix` 的 RenamedFolder 子例 |
| P03 | 移到其他磁盘 | T.`test_portable_moved_to_another_drive`，本机 C→D 已通过；单盘环境跳过 |
| P04 | 主 EXE 改名 | T.`test_portable_first_use_manifest_maps_renamed_entrypoint`；T.`test_portable_rename_move_matrix` 的 PDF_BookmarksRenamedEntry 子例 |
| P05 | 文件夹 + EXE 同时改名 | T.`test_portable_rename_move_matrix` 的 FolderAndEntryRenamed 子例；冻结 Portable 成功场景 |
| P06 | 中文路径 | T.`test_portable_rename_move_matrix` 的中文子例 |
| P07 | 空格路径 | T.`test_portable_rename_move_matrix` 的 folder with spaces 子例 |
| P08 | 额外 PDF 保留 | T.`test_portable_replaces_managed_only_and_removes_obsolete_runtime` 的论文.pdf 断言 |
| P09 | 自定义 txt 保留 | 同一测试的 custom.txt 断言 |
| P10 | 自定义文件夹保留 | 同一测试的我的文件夹/a.json 断言 |
| P11 | 删除旧 DLL | 同一测试的 _internal/old.dll 缺失断言；冻结 Portable 成功场景 |
| P12 | 增加 DLL | 同一测试的 _internal/new.dll 内容断言 |
| P13 | 修改资源 | 同一测试的 resources/readme.txt 内容断言 |
| P14 | config 保留 | 同一测试的 config.json 原字节断言；T.`test_configuration_target_cannot_be_managed_program_file` |
| P15 | UserData 保留 | 同一测试的 UserData/history 原字节断言 |
| P16 | installed-manifest 更新 | 同一测试的 version/entrypoint 断言；T.`test_portable_rename_move_matrix` |
| P17 | 更新中断 | T.`test_portable_interrupted_install_recovers`；T.`test_portable_replace_fault_rolls_back` |
| P18 | 文件锁定 | T.`test_portable_runtime_file_lock_stops_before_changing_any_file`；P.`test_locked_file_rejected_before_replace`（真实 Windows CreateFile） |
| P19 | 无写权限 | T.`test_portable_readonly_managed_runtime_stops_before_install`；T.`test_no_write_permission_preflight` |
| P20 | 健康检查失败 | T.`test_portable_health_failure_restores_manifest_runtime_and_configuration`；冻结 Portable 失败场景 |
| P21 | rollback | T.`test_portable_replace_fault_rolls_back`；T.`test_portable_interrupted_install_recovers` |
| P22 | 成功无废弃文件残留 | T.`test_portable_replaces_managed_only_and_removes_obsolete_runtime` 清理断言；冻结 Portable 成功场景 |

Portable 还额外验证：未知文件同名冲突拒绝（T.`test_unknown_filename_collision_rejected`）、ZIP 穿越/重复 case/链接/额外条目拒绝（T.`test_invalid_zip_entries_and_tampered_member_never_installed`）、文件记录哈希错误拒绝（T.`test_wrong_package_hash_record_is_rejected`）、Windows junction 拒绝（T.`test_windows_junction_program_root_is_rejected`）及其他应用/未完成事务保护（T.`test_cleanup_retains_unfinished_transactions_and_other_app`）。

## 配置：12 项

| 编号 | 场景 | 对应自动测试 |
| --- | --- | --- |
| C01 | 当前 schema 完整配置 | C.`test_current_full_fixture_retains_custom_values` |
| C02 | 当前 schema 缺可选字段 | C.`test_minimal_fixture_fills_defaults_and_legacy_editor_topmost` |
| C03 | 旧 schema | C.`test_unversioned_legacy_is_schema_1_without_rewriting_bytes`；C.`test_old_intermediate_schema_fixture_migrates_to_latest_injected_schema` |
| C04 | 多版本逐级迁移 | C.`test_multi_level_migration_preserves_user_values_and_unknown_fields`（测试注入 1→2→3） |
| C05 | 未知字段 | C.`test_unknown_fields_survive_gui_save_and_partial_update` |
| C06 | 默认值 | C.`test_invalid_optional_values_fall_back_individually`；C.`test_missing_config_uses_defaults_without_creating_file` |
| C07 | malformed 配置 | C.`test_malformed_files_use_gui_defaults_but_are_not_overwritten`；C.`test_non_json_constants_are_rejected_without_saving_defaults` |
| C08 | migration 中断 | C.`test_migration_exception_and_interruption_leave_original_bytes`；C.`test_interruption_after_replace_restores_original` |
| C09 | migration 异常 | C.`test_migration_exception_and_interruption_leave_original_bytes`；C.`test_failed_atomic_replace_keeps_old_file_and_cleans_temporary` |
| C10 | migration 后 schema 校验 | C.`test_missing_migration_and_invalid_output_leave_original_bytes`；C.`test_schema_specific_validation_failure_preserves_original` |
| C11 | 程序回滚 + 配置恢复 | C.`test_program_rollback_restores_config_after_successful_migration`；T.`test_portable_health_failure_restores_manifest_runtime_and_configuration`；冻结两种形态失败场景 |
| C12 | 自定义设置保持 | C.`test_current_full_fixture_retains_custom_values`；C.`test_parallel_gui_save_and_timestamp_updates_keep_both_settings`；冻结两种形态成功场景 |

配置 schema 与应用版本独立；生产 `CONFIG_SCHEMA=1` 且迁移列表为空。schema 2/3 测试样本专用于迁移框架验证，不意味着正式程序会把 schema 1 迁到 3。当前生产升级保持 schema 1；未来结构变化必须另加真实迁移与样本。

## GUI、检查、状态机及发布补充验收

| 要求 | 实际测试入口 |
| --- | --- |
| 自动最多 24h、手动立即检查 | `ControllerTests.test_automatic_check_obeys_toggle_and_24_hour_interval`、`test_manual_check_forces_check_despite_disabled_automatic_or_recent_timestamp` |
| 后台更新与 PDF 工作分离 | `ControllerTests.test_update_executor_does_not_block_or_reuse_pdf_worker` |
| 写入/编辑/保存/预览阻挡安装 | `UpdateGuiTests.test_install_guard_covers_write_editor_save_and_render`、`test_busy_install_never_starts_updater_or_exits_main_window` |
| READY 不改变程序，取消/关闭清理 | `ControllerTests.test_download_reaches_ready_and_keeps_current_program_until_install`、`test_close_ready_discards_transaction_without_touching_current_program`、`test_cancel_ready_discards_transaction_and_allows_new_check` |
| 下载/准备取消竞态 | `ControllerTests.test_close_while_preparing_discards_new_transaction_without_ready_event`、`test_cancel_during_download_cleans_partial_directory_and_keeps_program` |
| Tk 只在主线程应用事件 | `UpdateGuiTests.test_offer_progress_ready_are_applied_only_by_tk_poll` |
| 稳定发布拒绝 draft/prerelease | `UpdateCheckTests.test_stable_rejects_drafts_prereleases_and_invalid_tags` |
| HTTPS 和重定向可信主机 | `UpdateCheckTests.test_url_trust_requires_https_and_approved_github_hosts`、`test_redirect_policy_rejects_destination_before_sending_request` |
| 不替换源码/CLI | `ControllerTests.test_source_and_cli_identity_cannot_download_or_install_gui_update` |
| 包清单与所有实际文件完整哈希 | `UpdatePackagingTests.test_manifest_hashes_all_payload_files`、`test_release_manifest_uses_version_and_exact_asset_digests` |
| 版本/源码漂移拒绝发布 | `UpdatePackagingTests.test_tag_must_match_version`、`test_stale_other_version_asset_refuses_publication`、`test_build_source_drift_cannot_be_packaged_as_current_release` |
| installed 状态/私人资料不进包 | `UpdatePackagingTests.test_installed_user_state_never_packaged`、`test_configuration_fixtures_allowed_but_private_json_rejected` |
| helper 解包中不取消已批准安装 | `UpdateSafetyReviewTests.test_startup_cleanup_retains_verified_transaction_during_helper_bootstrap` |
| 清理文件占用、并发和末尾删除中断 | T.`test_cleanup_keeps_journal_when_helper_file_is_temporarily_locked`、`test_concurrent_completed_cleanup_is_idempotent`、`test_final_rmdir_failure_keeps_external_ownership_for_startup_retry` |
| 清理收据归属及未知文件保护 | T.`test_cleanup_receipt_rejects_foreign_identity_pending_state_and_malformed_data`、`test_cleanup_retains_unknown_top_level_file_and_ownership`；`UpdateSafetyReviewTests.test_external_cleanup_receipt_retains_foreign_and_unfinished_transactions` |

`ControllerTests` 位于 `tests/test_update_controller.py`，GUI 类位于 `tests/test_update_gui.py`，网络类位于 `tests/test_update_network.py`，打包类位于 `tests/test_update_packaging.py`，独立安全复核类位于 `tests/test_update_safety_review.py`。

## 规格 §51 的 17 项交付定位

| 交付事项 | 查阅位置 |
| --- | --- |
| 1 修改文件、2 新模块 | Git diff / PR 文件列表；[AUTO_UPDATE.md](AUTO_UPDATE.md#模块与构建) |
| 3 Actions 变更 | `.github/workflows/windows-build.yml`；[MAINTENANCE.md](MAINTENANCE.md#github-actions-的用途) |
| 4 Single、5 Portable 流程 | [AUTO_UPDATE.md](AUTO_UPDATE.md#single-文件替换)、[Portable 文件管理](AUTO_UPDATE.md#portable-文件管理) |
| 6 配置策略、7 schema、8 migrations | [配置兼容与迁移](AUTO_UPDATE.md#配置兼容与迁移)，当前 1 / 空列表 |
| 9 自动测试、10 实际构建 | 本页“当前验证状态与边界”中的实际结果 |
| 11 EXE 改名、12 文件夹改名、13 移动 | S02–S06、P02–P07 及冻结验证实际结果 |
| 14 配置升级、15 失败回滚 | C03–C12、S14–S15、P17/P20/P21 |
| 16 无旧程序残留 | S16、P11/P22 及真实冻结清理结果 |
| 17 GitHub commit / PR / Release | 对应工作分支 PR 的验证记录与 Checks；旧 v1.4.1 Release 保留，新标签待试用确认 |

完整源码、冻结更新与远端构建的实际结果全部核对前，不把设计、单元测试或待执行项写成已验收完成。
