"""Remove only verified, completed transactions belonging to this application."""

import os
from contextlib import nullcontext
from pathlib import Path
import re
import shutil
import threading

from . import UpdateError
from . import journal, processes
from .manifest import assert_safe_path, load_json
from .processes import process_alive

_TRANSACTION = re.compile(r"^tx-[0-9a-f]{32}$")
_CLEANUP_RECEIPT = re.compile(r"^cleanup_(tx-[0-9a-f]{32})\.json$")
_CLEANUP_LOCK = threading.RLock()
_PRODUCTS = {"journal.json", "update.log", "health.json", "health-failure.json", "installed-manifest.json",
             "updater.exe", "package.exe", "package.zip", "new", "backup"}


def _no_links(directory):
    assert_safe_path(directory)
    for root, directories, files in os.walk(directory, followlinks=False):
        for name in directories + files:
            assert_safe_path(Path(root) / name)


def _receipt_path(directory):
    return assert_safe_path(directory.parent / ("cleanup_" + directory.name + ".json"))


def _cleanup_data(directory, app_id):
    directory = assert_safe_path(directory)
    if not _TRANSACTION.fullmatch(directory.name):
        raise UpdateError("拒绝清理非更新事务目录。")
    source = directory / "journal.json"
    receipt = _receipt_path(directory)
    if not source.is_file():
        source = receipt
    data = load_json(assert_safe_path(source))
    if (not isinstance(data, dict) or data.get("app_id") != app_id or data.get("transaction") != directory.name
            or type(data.get("schema")) is not int or data["schema"] != 1):
        raise UpdateError("拒绝清理其他应用或无效事务。")
    operations = data.get("operations")
    if not isinstance(operations, list) or any(not isinstance(item, dict) for item in operations):
        raise UpdateError("清理归属记录中的文件操作无效。")
    if data.get("state") not in ("committed", "rolled_back", "failed"):
        return None
    if data.get("state") == "failed" and any(item.get("started") for item in data.get("operations", ())):
        return None
    if not isinstance(data.get("target_root"), str) or not isinstance(data.get("target_exe"), str):
        raise UpdateError("清理归属记录中的目标路径无效。")
    target = assert_safe_path(data["target_root"])
    if assert_safe_path(data["target_exe"]).parent != target:
        raise UpdateError("清理归属记录的主程序不在目标目录。")
    if directory.is_relative_to(target) or target.is_relative_to(directory):
        raise UpdateError("临时事务与实际程序目录相互包含。")
    return data


def cleanup_transaction(directory, app_id, *, allow_current_helper=False):
    # startup cleanup and health cleanup share this process lock; the existing
    # OS installation lock serializes cleanup with other application instances.
    with _CLEANUP_LOCK:
        return _cleanup_transaction(directory, app_id, allow_current_helper=allow_current_helper)


def _cleanup_transaction(directory, app_id, *, allow_current_helper=False):
    directory = assert_safe_path(directory)
    receipt = _receipt_path(directory)
    if not directory.exists() and not receipt.exists():
        return True
    data = _cleanup_data(directory, app_id)
    if data is None:
        return False
    if not directory.exists():
        receipt.unlink(missing_ok=True)
        return True
    helper = data.get("helper_pid")
    active = process_alive(helper) or bool(processes.matching_processes(directory / "updater.exe"))
    if active and not (allow_current_helper and helper == os.getpid()):
        return False
    context = nullcontext() if active else processes.installation_lock(data["target_exe"], directory.parent)
    with context:
        if not directory.exists():
            receipt.unlink(missing_ok=True)
            return True
        # Revalidate after obtaining the OS lock: another process may have
        # completed cleanup while this instance was examining its journal.
        data = _cleanup_data(directory, app_id)
        if data is None:
            return False
        return _cleanup_contents(directory, receipt, data, active)


def _cleanup_contents(directory, receipt, data, active):
    _no_links(directory)
    for path in directory.iterdir():
        if path.name not in _PRODUCTS and not path.name.startswith(".journal-"):
            raise UpdateError(f"事务中存在未知文件，已保留：{path.name}")
    if data.get("state") != "committed":
        # Keep the diagnostic journal and log, never old program/config bytes.
        diagnostics = assert_safe_path(directory.parent / "diagnostics")
        diagnostics.mkdir(exist_ok=True)
        for name in ("journal.json", "update.log"):
            source = directory / name
            if source.is_file():
                shutil.copy2(source, diagnostics / (directory.name + "_" + name))
        records = sorted(diagnostics.glob("tx-*_journal.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in records[10:]:
            old.unlink()
            old.with_name(old.name.replace("_journal.json", "_update.log")).unlink(missing_ok=True)
    if active:
        # The running Windows helper cannot unlink itself. The acknowledged
        # main process retries after helper exit, or the next startup does so.
        for name in ("new", "backup", "package.exe", "package.zip", "installed-manifest.json"):
            path = directory / name
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        return False
    # Keep the authoritative journal until all possibly locked program/
    # helper files have gone. A failed unlink can be retried safely.
    for path in directory.iterdir():
        if path.name == "journal.json":
            continue
        assert_safe_path(path)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    # The external receipt closes the crash window between deleting the
    # last journal and removing its empty directory. It uses the same
    # APP_ID/path/terminal validation, and is removed on normal completion.
    journal.atomic_json(receipt, data)
    (directory / "journal.json").unlink(missing_ok=True)
    directory.rmdir()
    receipt.unlink(missing_ok=True)
    return True


def cleanup_stale_update_transactions(app_id, transaction_root=None):
    from .transaction import update_root
    base = assert_safe_path(transaction_root or update_root())
    results = {}
    if not base.exists():
        return results
    for receipt in list(base.iterdir()):
        match = _CLEANUP_RECEIPT.fullmatch(receipt.name)
        if not match:
            continue
        directory = base / match.group(1)
        try:
            results[str(directory)] = "cleaned" if cleanup_transaction(directory, app_id) else "active"
        except (OSError, UpdateError) as exc:
            results[str(directory)] = f"retained: {exc}"
    for directory in base.iterdir():
        if not directory.is_dir() or not _TRANSACTION.fullmatch(directory.name):
            continue
        try:
            if not (directory / "journal.json").is_file() and _receipt_path(directory).is_file():
                continue
            data = load_json(assert_safe_path(directory / "journal.json"))
            if not isinstance(data, dict):
                raise UpdateError("无效的清理归属记录。")
            if data.get("app_id") != app_id:
                continue
            if data.get("state") in ("committed", "rolled_back", "failed"):
                results[str(directory)] = "cleaned" if cleanup_transaction(directory, app_id) else "active"
            elif (data.get("state") in ("created", "verified") and not process_alive(data.get("helper_pid"))
                  and not data.get("config_snapshot") and not any(item.get("started") for item in data.get("operations", ()))
                  and not any(process_alive(pid) for pid in data.get("parent_pids", ()))
                  and not processes.matching_processes(directory / "updater.exe")):
                from .journal import save
                save(directory, data, "failed")
                results[str(directory)] = "cleaned" if cleanup_transaction(directory, app_id) else "active"
            else:
                results[str(directory)] = "pending"
        except (OSError, UpdateError) as exc:
            results[str(directory)] = f"retained: {exc}"
    return results
