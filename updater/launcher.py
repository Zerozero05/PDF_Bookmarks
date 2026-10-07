"""Copy the embedded helper outside the installation before spawning it."""

import os
from pathlib import Path
import subprocess
import sys

from . import UpdateError
from . import journal, processes
from .manifest import assert_safe_path, load_json
from .transaction import Transaction, _copy_atomic, _load_transaction, update_root


def start_updater(transaction):
    directory, data = _load_transaction(transaction.directory if isinstance(transaction, Transaction) else transaction)
    if data.get("state") in ("committed", "rolled_back", "failed"):
        raise UpdateError("此更新事务已经结束。")
    if not getattr(sys, "frozen", False):
        raise UpdateError("源码模式不执行自身更新，请运行正式 Single 或 Portable 程序。")
    helper = directory / "updater.exe"
    if not helper.exists():
        resource = assert_safe_path(Path(sys._MEIPASS) / "updater.exe")
        if not resource.is_file():
            raise UpdateError("当前程序不含更新器，请手动下载新版。")
        _copy_atomic(resource, helper)
    command = [str(helper), "--transaction", str(directory)]
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(command, cwd=directory, close_fds=True, creationflags=creationflags)
    # The helper records its actual application PID (not the PyInstaller
    # bootstrap PID). Writing here could race its first journal mutation.
    return process


def resume_pending_update(build_info, current_exe=None, transaction_root=None):
    if not getattr(sys, "frozen", False):
        return False
    executable = assert_safe_path(current_exe or sys.executable)
    base = assert_safe_path(transaction_root or update_root())
    if not base.exists():
        return False
    for directory in base.glob("tx-*"):
        try:
            assert_safe_path(directory)
            data = load_json(directory / "journal.json")
        except (OSError, UpdateError):
            continue
        if (data.get("app_id") != build_info.app_id
                or os.path.normcase(data.get("target_exe", "")) != os.path.normcase(str(executable))
                or data.get("state") not in ("backing_up", "backup_created", "installing", "files_replaced",
                                             "new_app_started", "verifying_install", "healthcheck_ok", "rollback_started")
                or processes.process_alive(data.get("helper_pid"))):
            continue
        data["parent_pids"] = sorted(set(processes.matching_processes(executable)) | {os.getpid()})
        journal.save(directory, data)
        start_updater(directory)
        return True
    return False
