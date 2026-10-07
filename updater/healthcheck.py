"""Acknowledge actual configuration, PDF-core and GUI initialization."""

import os
from pathlib import Path
import sys
import threading
import time

from . import UpdateError
from .journal import atomic_json
from .manifest import assert_safe_path, load_json


def validate_health_start(transaction_dir, token, build_info):
    from .transaction import _load_transaction
    directory, data = _load_transaction(transaction_dir)
    if (not isinstance(token, str) or token != data.get("health_token")
            or data.get("app_id") != build_info.app_id or data.get("to_version") != build_info.version
            or data.get("variant") != build_info.variant
            or data.get("state") not in ("new_app_started", "verifying_install")):
        raise UpdateError("更新健康检查身份或事务状态不一致。")
    if os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(data["target_exe"]):
        raise UpdateError("健康回执来自错误程序路径。")
    assert_safe_path(data["config_path"])
    return data


def ack_health(transaction_dir, token, build_info, *, config_ready, gui_ready, core_ready):
    directory = assert_safe_path(transaction_dir)
    data = validate_health_start(directory, token, build_info)
    if not all(value is True for value in (config_ready, gui_ready, core_ready)):
        raise UpdateError("配置、PDF 核心及 GUI 必须全部初始化成功。")
    atomic_json(directory / "health.json", {"token": token, "app_id": build_info.app_id,
                "version": build_info.version, "variant": build_info.variant, "pid": os.getpid(),
                "config_ready": True, "gui_ready": True, "core_ready": True})

    def clean_after_helper():
        from .cleanup import cleanup_transaction
        for _ in range(120):
            time.sleep(1)
            try:
                # Cleanup owns terminal-state and APP_ID validation, including
                # a receipt when the final journal->rmdir step was interrupted.
                if cleanup_transaction(directory, build_info.app_id):
                    return
                if not directory.exists():
                    return
                state = load_json(directory / "journal.json").get("state")
                if state in ("rolled_back", "rollback_started", "failed"):
                    return
            except (OSError, UpdateError):
                continue

    threading.Thread(target=clean_after_helper, name="update-cleanup", daemon=True).start()
    return True
