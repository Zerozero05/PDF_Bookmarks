"""Backward-compatible settings and atomic configuration update transactions.

Existing settings without ``schema`` are schema 1. Application releases do not
change that schema unless the settings structure actually changes. GUI reads
remain tolerant; update health checks use ``read_config`` to reject corrupt data.
"""

from __future__ import annotations

import copy
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid


CONFIG_SCHEMA = 1
MIGRATIONS = {}
_CONFIG_LOCK = threading.RLock()
DEFAULT_CONFIG = {
    "backup": True,
    "backup_dir": "",
    "clear_cache": False,
    "delete_toc": False,
    "recursive": False,
    "existing": "skip",
    "last_dir": "",
    "topmost": False,
    "geometry": "1100x860",
    "editor_geometry": "1240x900",
    "editor_topmost": False,
    "toc_save_mode": "source",
    "toc_save_dir": "",
    "auto_check_update": True,
    "last_update_check": 0.0,
}


class ConfigError(OSError):
    """An unreadable configuration must not be silently replaced with defaults."""


def _locked(function):
    @wraps(function)
    def serialized(*args, **kwargs):
        with _CONFIG_LOCK:
            return function(*args, **kwargs)
    return serialized


def settings_path(path=None) -> Path:
    if path is not None:
        return Path(path)
    appdata = os.environ.get("LOCALAPPDATA")
    if not appdata:
        raise OSError("无法定位 LOCALAPPDATA，未保存设置。")
    return Path(appdata) / "ZoteroPDFBookmarks" / "settings.json"


def _valid_timestamp(value) -> bool:
    try:
        return type(value) in {int, float} and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def sanitize_settings(settings) -> dict:
    """Keep the original whitelist, defaults and legacy editor inheritance."""
    result = DEFAULT_CONFIG.copy()
    if not isinstance(settings, dict):
        return result
    for name, default in DEFAULT_CONFIG.items():
        value = settings.get(name, default)
        if name == "last_update_check":
            if _valid_timestamp(value):
                result[name] = value
            continue
        if type(value) is not type(default):
            continue
        if name == "existing" and value not in {"skip", "replace"}:
            continue
        if name == "toc_save_mode" and value not in {"source", "custom"}:
            continue
        if name in {"geometry", "editor_geometry"}:
            match = re.fullmatch(r"(\d{1,4})x(\d{1,4})(?:[+-]\d{1,6}[+-]\d{1,6})?", value)
            if not match or not all(200 <= int(size) <= 8192 for size in match.group(1, 2)):
                continue
        result[name] = value
    if "editor_topmost" not in settings:
        result["editor_topmost"] = result["topmost"]
    return result


def validate_config(document, expected_schema=None, *, strict_values=False) -> int:
    if not isinstance(document, dict):
        raise ConfigError("设置文件必须是 JSON 对象，已保留原文件。")
    schema = document.get("schema", 1)
    if type(schema) is not int or schema < 1:
        raise ConfigError("设置 schema 无效，已保留原文件。")
    if expected_schema is not None and schema != expected_schema:
        raise ConfigError(f"设置 schema {schema} 与要求的 {expected_schema} 不一致。")
    if strict_values:
        sanitized = sanitize_settings(document)
        for name, default in DEFAULT_CONFIG.items():
            if name == "last_update_check":
                if name in document and not _valid_timestamp(document[name]):
                    raise ConfigError(f"迁移后的设置字段无效：{name}")
                continue
            if name in document and (type(document[name]) is not type(default)
                                     or sanitized[name] != document[name]):
                raise ConfigError(f"迁移后的设置字段无效：{name}")
    return schema


def _invalid_json_constant(value):
    raise ConfigError(f"设置文件含非 JSON 数值：{value}")


def _read_document(path: Path) -> dict:
    try:
        document = json.loads(path.read_bytes().decode("utf-8-sig"), parse_constant=_invalid_json_constant)
        validate_config(document)
        return document
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError, RecursionError) as error:
        raise ConfigError(f"设置文件无法读取，已保留：{path}；{error}") from error


def read_config(path=None, *, strict=True) -> dict:
    """Read defaults plus unknown fields; strict is required by health checks.

    Optional fields retain the old individual fallback behavior. Strictness
    concerns malformed JSON, unreadable files and unsupported configuration
    schemas, rather than unknown fields or a missing optional preference.
    """
    try:
        document = _read_document(settings_path(path))
        if validate_config(document) > CONFIG_SCHEMA:
            raise ConfigError("设置来自更新版本，当前程序不能安全写入该 schema。")
        return dict(document, **sanitize_settings(document), schema=validate_config(document))
    except (OSError, ValueError, TypeError, RecursionError):
        if strict:
            raise
        return dict(DEFAULT_CONFIG, schema=CONFIG_SCHEMA)


def load_config(path=None) -> dict:
    """GUI compatibility API: ignore unknown fields and fall back safely."""
    return sanitize_settings(read_config(path, strict=False))


def _atomic_bytes(path: Path, payload: bytes, validator=None) -> None:
    if path.is_symlink():
        raise ConfigError(f"设置文件是符号链接，未覆盖：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(prefix=".settings.", suffix=".tmp", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if validator is not None:
            validator(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def save_config(settings, path=None) -> None:
    """Atomically save preferences without losing existing unknown fields.

    A malformed existing file is deliberately left untouched. The GUI reports
    this OSError and the user can repair or explicitly remove that file.
    """
    with _CONFIG_LOCK:
        target = settings_path(path)
        document = _read_document(target)
        schema = validate_config(document)
        if schema > CONFIG_SCHEMA:
            raise ConfigError("设置来自更新版本，已保留原文件。")
        if isinstance(settings, dict):
            document.update({name: value for name, value in settings.items() if name != "schema"})
        output = dict(document, **sanitize_settings(document), schema=CONFIG_SCHEMA)
        _atomic_bytes(target, _json_bytes(output),
                      lambda temporary: validate_config(_read_document(temporary), CONFIG_SCHEMA))


def update_config(updates, path=None) -> dict:
    """Update only supplied preferences, including background check timestamps."""
    if not isinstance(updates, dict):
        raise ConfigError("设置更新必须是对象。")
    with _CONFIG_LOCK:
        save_config(updates, path)
        return read_config(path)


@_locked
def snapshot_config(config_path, backup_dir) -> dict:
    """Save exact bytes, including malformed JSON, for program rollback."""
    target = settings_path(config_path).absolute()
    if target.is_symlink():
        raise ConfigError(f"设置文件是符号链接，更新未开始：{target}")
    snapshot = {"path": str(target), "existed": target.exists(), "backup": None, "sha256": None}
    if not snapshot["existed"]:
        return snapshot
    payload = target.read_bytes()
    backup = Path(backup_dir).absolute() / f"settings_{uuid.uuid4().hex}.backup"
    digest = hashlib.sha256(payload).hexdigest()
    _atomic_bytes(backup, payload)
    if hashlib.sha256(backup.read_bytes()).hexdigest() != digest:
        raise ConfigError("旧配置备份校验失败，更新未开始。")
    snapshot.update(backup=str(backup), sha256=digest)
    return snapshot


@_locked
def restore_config(snapshot) -> None:
    """Restore an exact pre-update configuration or its original absence."""
    target = Path(snapshot["path"])
    if not target.is_absolute() or type(snapshot.get("existed")) is not bool:
        raise ConfigError("配置回滚记录无效。")
    if target.is_symlink():
        raise ConfigError("配置回滚目标是符号链接，未覆盖。")
    if not snapshot["existed"]:
        target.unlink(missing_ok=True)
        return
    backup = Path(snapshot["backup"])
    if not backup.is_absolute() or backup.is_symlink():
        raise ConfigError("配置备份路径无效。")
    payload = backup.read_bytes()
    if hashlib.sha256(payload).hexdigest() != snapshot["sha256"]:
        raise ConfigError("配置备份已改变，未覆盖现有配置。")
    _atomic_bytes(target, payload)
    if target.read_bytes() != payload:
        raise ConfigError("配置恢复后的文件校验失败。")


@_locked
def migrate_config(path=None, target_schema=CONFIG_SCHEMA, migrations=None, *,
                   backup_dir=None, validators=None) -> dict:
    """Apply each schema step to a copy, then validate and atomically replace.

    ``migrations`` maps source schema numbers to functions returning the next
    document. Production schema remains 1 and therefore needs no migrations.
    Transaction callers provide ``backup_dir`` and retain its backups until
    health checks commit; standalone migrations clean their temporary backup.
    """
    if type(target_schema) is not int or target_schema < 1:
        raise ConfigError("目标设置 schema 无效。")
    target = settings_path(path)
    original = _read_document(target)
    schema = validate_config(original)
    if schema > target_schema:
        raise ConfigError("不支持把新版配置降级，已保留原文件。")
    if schema == target_schema:
        return dict(original, **sanitize_settings(original), schema=schema)
    migrations = MIGRATIONS if migrations is None else migrations
    validators = {} if validators is None else validators
    # Keep backup and target on the same volume for the standalone transaction.
    temporary_backup = None
    if backup_dir is None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_backup = tempfile.TemporaryDirectory(prefix=".settings.migration.", dir=target.parent)
        backup_dir = temporary_backup.name
    snapshot = None
    try:
        snapshot = snapshot_config(target, backup_dir)
        migrated = copy.deepcopy(original)
        while schema < target_schema:
            if schema not in migrations:
                raise ConfigError(f"缺少设置迁移：schema {schema} -> {schema + 1}")
            migrated = migrations[schema](copy.deepcopy(migrated))
            schema += 1
            validate_config(migrated, schema, strict_values=True)
            if schema in validators:
                validators[schema](migrated)
        payload = _json_bytes(migrated)

        def validate_temporary(temporary):
            result = _read_document(temporary)
            validate_config(result, target_schema, strict_values=True)
            if target_schema in validators:
                validators[target_schema](result)

        _atomic_bytes(target, payload, validate_temporary)
        validate_temporary(target)
        return dict(migrated, **sanitize_settings(migrated), schema=target_schema)
    except BaseException:
        # Cover interruption immediately after os.replace, before Python can
        # record completion; an unchanged original needs no further writes.
        if snapshot is not None:
            original_backup = Path(snapshot["backup"]).read_bytes() if snapshot["existed"] else None
            try:
                current = target.read_bytes()
            except FileNotFoundError:
                current = None
            if current != original_backup:
                restore_config(snapshot)
        raise
    finally:
        if temporary_backup is not None:
            temporary_backup.cleanup()
