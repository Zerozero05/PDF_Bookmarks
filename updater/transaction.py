"""Prepare, install and recover a complete, journaled update transaction."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

from . import UpdateError
from . import journal, processes
from .manifest import (assert_safe_path, load_json, relative_path, sha256_file, target_path,
                       validate_package_manifest, validate_release_manifest, verify_records)

INSTALLED = ".pdf_bookmarks/installed-manifest.json"
PACKAGE = "package-manifest.json"
TERMINAL = {"committed", "rolled_back", "failed"}


@dataclass
class Transaction:
    directory: Path
    journal: dict


def update_root():
    return Path(tempfile.gettempdir()) / "PDF_Bookmarks_Update"


def _copy_atomic(source, destination, temporary_path=None):
    destination = assert_safe_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if temporary_path is None:
        descriptor, temporary = tempfile.mkstemp(prefix=".pdf-update-", dir=destination.parent)
    else:
        temporary = str(assert_safe_path(temporary_path))
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output, Path(source).open("rb") as input_file:
            shutil.copyfileobj(input_file, output, 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        journal.replace_file(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _mapped(manifest, launcher_name):
    result = dict(manifest)
    result["entrypoint"] = relative_path(launcher_name)
    result["launcher_name"] = launcher_name
    result["managed_files"] = [dict(item, path=launcher_name if item["path"] == manifest["entrypoint"] else item["path"])
                               for item in manifest["managed_files"]]
    return validate_package_manifest(result)


def ensure_installed_manifest(current_exe, build_info):
    if build_info.variant != "portable":
        return None
    executable = assert_safe_path(current_exe)
    root = executable.parent
    installed = target_path(root, INSTALLED)
    if installed.exists():
        result = validate_package_manifest(load_json(installed), build_info, build_info.version)
        return _mapped(result, executable.name)
    package = validate_package_manifest(load_json(target_path(root, PACKAGE)), build_info, build_info.version)
    verify_records(root, package, executable.name)
    result = _mapped(package, executable.name)
    journal.atomic_json(installed, result)
    return result


def _space_check(directory, required):
    directory = assert_safe_path(directory)
    while not directory.exists():
        directory = directory.parent
    if shutil.disk_usage(directory).free < required + 8 * 1024 * 1024:
        raise UpdateError("磁盘空间不足；尚未修改当前程序。")


def _writable_directory(directory):
    directory = assert_safe_path(directory)
    while not directory.exists():
        directory = directory.parent
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".pdf-permission-", dir=directory)
        os.close(descriptor)
        Path(temporary).unlink()
    except OSError as exc:
        raise UpdateError(f"程序目录不可写，请移动到可写位置或以管理员权限运行：{directory}") from exc


def _preflight(directory, data, check_locks=False):
    root = assert_safe_path(data["target_root"])
    assert_safe_path(data["target_exe"])
    backup_size = 0
    install_size = 0
    checked_parents = set()
    for operation in data["operations"]:
        target = target_path(root, operation["path"])
        if os.path.normcase(str(target)) == os.path.normcase(data.get("config_path", "")):
            raise UpdateError("程序包不得覆盖用户配置文件。")
        if target.exists():
            if not target.is_file():
                raise UpdateError(f"目标文件与用户目录冲突：{operation['path']}")
            if not operation["old_exists"]:
                raise UpdateError(f"新程序文件与用户未知文件冲突：{operation['path']}")
            if getattr(target.stat(), "st_file_attributes", 0) & 1:
                raise UpdateError(f"程序文件为只读：{operation['path']}")
            backup_size += target.stat().st_size
            if check_locks:
                processes.check_file_unlocked(target)
        elif operation["old_exists"]:
            raise UpdateError(f"受管理文件在准备后已消失：{operation['path']}")
        if target.parent not in checked_parents:
            _writable_directory(target.parent)
            checked_parents.add(target.parent)
        if operation.get("new_source"):
            source = target_path(directory, operation["new_source"])
            if not source.is_file() or sha256_file(source) != operation["new_hash"]:
                raise UpdateError("已验证的新程序文件被修改。")
            install_size += source.stat().st_size
    config = data.get("config_path")
    if config:
        _writable_directory(assert_safe_path(config).parent)
        if Path(config).is_file():
            backup_size += Path(config).stat().st_size
            if check_locks:
                processes.check_file_unlocked(config)
    _space_check(directory, backup_size + install_size)
    _space_check(root, install_size)


def _extract_portable(package_path, destination, build_info, version):
    with zipfile.ZipFile(package_path) as archive:
        infos = archive.infolist()
        if len(infos) > 100000:
            raise UpdateError("Portable ZIP 条目过多。")
        seen = set()
        files = {}
        for entry in infos:
            name = relative_path(entry.filename.rstrip("/"))
            folded = name.casefold()
            if folded in seen:
                raise UpdateError("ZIP 包含大小写重复路径。")
            seen.add(folded)
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise UpdateError("ZIP 含链接或非普通文件。")
            if entry.flag_bits & 1:
                raise UpdateError("不能使用加密的 Portable 程序包。")
            if not entry.is_dir():
                files[name] = entry
        manifests = [name for name in files if name == PACKAGE or name.endswith("/" + PACKAGE)]
        if len(manifests) != 1:
            raise UpdateError("Portable ZIP 必须且只能有一个 package-manifest.json。")
        manifest_name = manifests[0]
        prefix = manifest_name[:-len(PACKAGE)]
        if prefix.count("/") > 1:
            raise UpdateError("Portable ZIP 根目录层级无效。")
        if files[manifest_name].file_size > 8 * 1024 * 1024:
            raise UpdateError("Portable 清单过大。")
        try:
            manifest = validate_package_manifest(json.loads(archive.read(files[manifest_name])), build_info, version)
        except (ValueError, UnicodeError) as exc:
            raise UpdateError("Portable 清单不是有效 JSON。") from exc
        expected = {prefix + item["path"] for item in manifest["managed_files"]} | {manifest_name}
        if set(files) != expected:
            raise UpdateError("ZIP 文件与受管理清单不一致。")
        total = sum(item["size"] for item in manifest["managed_files"])
        if total > 4 * 1024 * 1024 * 1024:
            raise UpdateError("Portable 包解压大小超过支持上限。")
        _space_check(destination.parent, total * 2)
        destination.mkdir(parents=True, exist_ok=True)
        for item in manifest["managed_files"]:
            entry = files[prefix + item["path"]]
            if entry.file_size != item["size"]:
                raise UpdateError("Portable 文件大小与清单不一致。")
            output = target_path(destination, item["path"])
            output.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as input_file, output.open("xb") as output_file:
                shutil.copyfileobj(input_file, output_file, 1024 * 1024)
            if sha256_file(output) != item["sha256"].lower():
                raise UpdateError(f"Portable 文件 SHA-256 错误：{item['path']}")
        journal.atomic_json(destination / PACKAGE, manifest)
        return manifest


def prepare_transaction(package_path, release_manifest, build_info, current_exe=None,
                        config_path=None, transaction_root=None):
    from config_manager import settings_path
    validate_release_manifest(release_manifest, build_info)
    package_path = assert_safe_path(package_path)
    asset = release_manifest["assets"][build_info.variant]
    if not package_path.is_file() or sha256_file(package_path) != asset["sha256"].lower():
        raise UpdateError("下载文件 SHA-256 校验失败。")
    if "size" in asset and package_path.stat().st_size != asset["size"]:
        raise UpdateError("下载文件大小不正确。")
    executable = assert_safe_path(current_exe or sys.executable)
    if not executable.is_file():
        raise UpdateError("找不到当前实际运行程序。")
    base = assert_safe_path(transaction_root or update_root())
    if base.is_relative_to(executable.parent):
        raise UpdateError("临时 updater 必须位于程序目录之外。")
    _writable_directory(base)
    _space_check(base, package_path.stat().st_size * 2)
    base.mkdir(parents=True, exist_ok=True)
    directory = base / ("tx-" + uuid.uuid4().hex)
    directory.mkdir()
    data = {"schema": 1, "transaction": directory.name, "app_id": build_info.app_id,
            "variant": build_info.variant, "from_version": build_info.version,
            "to_version": release_manifest["version"], "target_root": str(executable.parent),
            "target_exe": str(executable), "config_path": str(assert_safe_path(settings_path(config_path))),
            "state": "created", "parent_pids": sorted(set(processes.matching_processes(executable)) | {os.getpid()}),
            "health_token": secrets.token_hex(32), "health_pid": None, "helper_pid": None,
            "operations": [], "config_snapshot": None, "asset": asset["file"]}
    journal.save(directory, data)
    journal.log(directory, f"{data['app_id']} {data['variant']} {data['from_version']} -> {data['to_version']} target={executable} asset={asset['file']}")
    try:
        package_copy = directory / ("package.exe" if build_info.variant == "single" else "package.zip")
        _copy_atomic(package_path, package_copy)
        if sha256_file(package_copy) != asset["sha256"].lower():
            raise UpdateError("事务包复制后校验失败。")
        sources = {}
        old_names = set()
        if build_info.variant == "single":
            with package_copy.open("rb") as handle:
                if handle.read(2) != b"MZ":
                    raise UpdateError("Single 更新包不是 Windows EXE。")
            old_names.add(executable.name)
            sources[executable.name] = "package.exe"
        else:
            old = ensure_installed_manifest(executable, build_info)
            new = _extract_portable(package_copy, directory / "new", build_info, data["to_version"])
            mapped = _mapped(new, executable.name)
            old_names = {item["path"] for item in old["managed_files"]}
            for item in new["managed_files"]:
                destination = executable.name if item["path"] == new["entrypoint"] else item["path"]
                sources[destination] = "new/" + item["path"]
            journal.atomic_json(directory / "installed-manifest.json", mapped)
            sources[INSTALLED] = "installed-manifest.json"
            sources[PACKAGE] = "new/" + PACKAGE
            old_names.add(INSTALLED)
            if target_path(executable.parent, PACKAGE).is_file():
                old_names.add(PACKAGE)
        ownership = {name.casefold() for name in old_names}
        names = sorted(old_names | set(sources), key=str.casefold)
        if len({name.casefold() for name in names}) != len(names):
            raise UpdateError("更新路径发生大小写冲突。")
        for index, name in enumerate(names):
            target = target_path(executable.parent, name)
            existing = target.exists()
            if existing and name.casefold() not in ownership:
                raise UpdateError(f"新文件与用户未知文件冲突，拒绝覆盖：{name}")
            source = sources.get(name)
            data["operations"].append({"path": name, "old_exists": existing,
                                       "old_hash": sha256_file(target) if existing and target.is_file() else None,
                                       "backup": f"backup/program/{index}", "backed_up": False,
                                       "new_source": source, "new_hash": sha256_file(directory / source) if source else None,
                                       "temporary": str(target.with_name(".pdf-update-" + directory.name + f"-{index}.new")),
                                       "started": False, "completed": False})
        journal.save(directory, data, "verified")
        _preflight(directory, data)
        return Transaction(directory, data)
    except BaseException as exc:
        data["error"] = str(exc)
        journal.save(directory, data, "failed")
        journal.log(directory, f"Preparation failed: {exc}")
        from .cleanup import cleanup_transaction
        try:
            cleanup_transaction(directory, data["app_id"])
        except (OSError, UpdateError) as cleanup_error:
            if directory.exists():
                journal.log(directory, f"Preparation cleanup deferred: {cleanup_error}")
        raise


def _load_transaction(directory):
    directory = assert_safe_path(directory)
    data = load_json(directory / "journal.json")
    if (data.get("schema") != 1 or data.get("transaction") != directory.name
            or data.get("variant") not in ("single", "portable") or not isinstance(data.get("operations"), list)):
        raise UpdateError("更新事务记录无效。")
    root = assert_safe_path(data["target_root"])
    executable = assert_safe_path(data["target_exe"])
    if executable.parent != root or directory.is_relative_to(root):
        raise UpdateError("更新事务的目标路径无效。")
    names = set()
    for operation in data["operations"]:
        name = relative_path(operation["path"])
        if name.casefold() in names:
            raise UpdateError("更新事务中存在重复目标文件。")
        names.add(name.casefold())
        target_path(root, name)
        target_path(directory, operation["backup"])
        if not operation["backup"].startswith("backup/program/"):
            raise UpdateError("事务备份不在备份目录。")
        if operation.get("new_source"):
            target_path(directory, operation["new_source"])
        temporary = assert_safe_path(operation["temporary"])
        if temporary.parent != target_path(root, name).parent or not temporary.name.startswith(".pdf-update-" + directory.name + "-"):
            raise UpdateError("事务临时替换文件路径无效。")
    snapshot = data.get("config_snapshot")
    if snapshot:
        if os.path.normcase(snapshot.get("path", "")) != os.path.normcase(data["config_path"]):
            raise UpdateError("配置快照路径与事务不一致。")
        if snapshot.get("backup") and not assert_safe_path(snapshot["backup"]).is_relative_to(directory / "backup/config"):
            raise UpdateError("配置快照不在事务备份目录内。")
    return directory, data


def _backup(directory, data):
    from config_manager import snapshot_config
    data["config_snapshot"] = snapshot_config(data["config_path"], directory / "backup/config")
    journal.save(directory, data, "backing_up")
    for operation in data["operations"]:
        if operation["old_exists"]:
            source = target_path(data["target_root"], operation["path"])
            if sha256_file(source) != operation["old_hash"]:
                raise UpdateError("准备更新后旧程序被修改，请重新检查更新。")
            backup = target_path(directory, operation["backup"])
            _copy_atomic(source, backup)
            if sha256_file(backup) != operation["old_hash"]:
                raise UpdateError("旧程序备份校验失败。")
        operation["backed_up"] = True
        journal.save(directory, data)
    journal.save(directory, data, "backup_created")


def _install(directory, data, fault_hook=None):
    root = data["target_root"]
    journal.save(directory, data, "installing")
    for operation in data["operations"]:
        target = target_path(root, operation["path"])
        operation["started"] = True
        journal.save(directory, data)
        if operation["new_source"]:
            _copy_atomic(target_path(directory, operation["new_source"]), target, operation["temporary"])
        elif operation["old_exists"]:
            target.unlink()
        operation["completed"] = True
        journal.save(directory, data)
        journal.log(directory, f"Installed managed path {operation['path']}")
        if fault_hook is not None:
            fault_hook(operation)
    journal.save(directory, data, "files_replaced")


def rollback_transaction(directory, *, restart=False):
    from config_manager import restore_config
    directory, data = _load_transaction(directory)
    if data["state"] == "committed":
        raise UpdateError("已经提交的更新不能回滚。")
    journal.save(directory, data, "rollback_started")
    for operation in reversed(data["operations"]):
        temporary = assert_safe_path(operation["temporary"])
        if temporary.exists():
            temporary.unlink()
        if not operation.get("started"):
            continue
        target = target_path(data["target_root"], operation["path"])
        if operation["old_exists"]:
            backup = target_path(directory, operation["backup"])
            if not operation.get("backed_up") or not backup.is_file() or sha256_file(backup) != operation["old_hash"]:
                raise UpdateError("回滚备份不完整，已保留事务供恢复。")
            _copy_atomic(backup, target)
        elif target.exists():
            if not target.is_file() or sha256_file(target) != operation["new_hash"]:
                raise UpdateError("新增程序文件在事务中被外部修改，拒绝删除。")
            target.unlink()
        operation["started"] = False
        operation["completed"] = False
        journal.save(directory, data)
    if data.get("config_snapshot"):
        restore_config(data["config_snapshot"])
    journal.save(directory, data, "rolled_back")
    journal.log(directory, "Rolled back program and configuration")
    _remove_empty_managed_dirs(data)
    if restart:
        _launch_old(data)
    return "rolled_back"


def _remove_empty_managed_dirs(data):
    root = Path(data["target_root"])
    parents = set()
    for operation in data["operations"]:
        target = target_path(root, operation["path"])
        for parent in target.parents:
            if parent == root:
                break
            if parent.is_relative_to(root):
                parents.add(parent)
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        try:
            assert_safe_path(parent).rmdir()
        except OSError:
            pass


def _launch_old(data):
    try:
        subprocess.Popen([data["target_exe"]], cwd=data["target_root"], close_fds=True)
    except OSError as exc:
        raise UpdateError(f"旧版本已恢复，但不能自动启动：{exc}") from exc


def run_transaction(directory, wait_timeout=60, health_timeout=90, *, launch=None, fault_hook=None):
    """Helper process only; never called to overwrite the running main EXE."""
    directory, data = _load_transaction(directory)
    from build_info import APP_ID
    if data["app_id"] != APP_ID:
        raise UpdateError("事务不属于本应用。")
    launched = None
    with processes.installation_lock(data["target_exe"], directory.parent):
        if data["state"] in TERMINAL:
            return data["state"]
        data["helper_pid"] = os.getpid()
        journal.save(directory, data)
        try:
            processes.wait_for_release(data["target_exe"], data["parent_pids"], wait_timeout)
            if data["state"] != "verified":
                return rollback_transaction(directory, restart=launch is None)
            _preflight(directory, data, check_locks=True)
            _backup(directory, data)
            _install(directory, data, fault_hook)
            journal.save(directory, data, "new_app_started")
            command = [data["target_exe"], "--update-transaction", str(directory), "--update-token", data["health_token"]]
            launched = (launch or subprocess.Popen)(command, cwd=data["target_root"], close_fds=True)
            data["launched_pid"] = launched.pid
            journal.save(directory, data, "verifying_install")
            deadline = time.monotonic() + health_timeout
            while time.monotonic() < deadline:
                if launched.poll() is not None:
                    raise UpdateError("新版在完成健康检查前退出。")
                receipt = directory / "health.json"
                if receipt.exists():
                    health = load_json(receipt)
                    if (health.get("token") == data["health_token"] and health.get("app_id") == data["app_id"]
                            and health.get("version") == data["to_version"] and health.get("variant") == data["variant"]
                            and all(health.get(item) is True for item in ("config_ready", "gui_ready", "core_ready"))
                            and processes.process_alive(health.get("pid"))
                            and health.get("pid") in processes.matching_processes(data["target_exe"])):
                        journal.save(directory, data, "healthcheck_ok")
                        journal.save(directory, data, "committed")
                        journal.log(directory, "Committed after configuration, core and GUI health receipt")
                        _remove_empty_managed_dirs(data)
                        from .cleanup import cleanup_transaction
                        cleanup_transaction(directory, data["app_id"], allow_current_helper=True)
                        return "committed"
                    raise UpdateError("新版健康回执无效。")
                time.sleep(0.1)
            raise UpdateError("新版健康检查超时。")
        except Exception as exc:
            # rollback_transaction may already have persisted many restored
            # files before raising. Its durable progress is authoritative;
            # never overwrite it with the installer's stale in-memory copy.
            directory, data = _load_transaction(directory)
            if data["state"] == "committed":
                journal.log(directory, f"Committed; cleanup deferred: {exc}")
                return "committed"
            data["error"] = str(exc)
            journal.save(directory, data)
            journal.log(directory, f"Update failed: {exc}")
            if launched is not None:
                processes.terminate_tree(launched)
                processes.wait_for_release(data["target_exe"], timeout=15)
            if any(item.get("started") for item in data["operations"]) or data.get("config_snapshot"):
                try:
                    return rollback_transaction(directory, restart=launch is None)
                except Exception as rollback_error:
                    directory, data = _load_transaction(directory)
                    restored = data["state"] == "rolled_back"
                    data["restart_error" if restored else "rollback_error"] = str(rollback_error)
                    journal.save(directory, data, None if restored else "rollback_started")
                    journal.log(directory, f"Rollback deferred: {rollback_error}")
                    return data["state"]
            journal.save(directory, data, "failed")
            if launch is None:
                _launch_old(data)
            return "failed"


def recover_transaction(directory):
    directory, data = _load_transaction(directory)
    if data["state"] in TERMINAL:
        return data["state"]
    if processes.process_alive(data.get("helper_pid")):
        return "active"
    with processes.installation_lock(data["target_exe"], directory.parent):
        if any(item.get("started") for item in data["operations"]) or data.get("config_snapshot"):
            processes.wait_for_release(data["target_exe"], timeout=0)
            return rollback_transaction(directory)
        journal.save(directory, data, "failed")
        return "failed"


def discard_prepared_transaction(transaction):
    directory, data = _load_transaction(transaction.directory if isinstance(transaction, Transaction) else transaction)
    if (data["state"] not in ("created", "verified") or data.get("helper_pid")
            or data.get("config_snapshot") or any(item.get("started") for item in data["operations"])):
        raise UpdateError("已经开始安装的事务不能直接丢弃。")
    journal.save(directory, data, "failed")
    from .cleanup import cleanup_transaction
    return cleanup_transaction(directory, data["app_id"])
