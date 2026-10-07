"""Release/package validation. Paths use Windows rules even in CI."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

from . import UpdateError

_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
_HASH = re.compile(r"^[0-9a-fA-F]{64}$")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_USER_NAMES = {"config.json", "settings.json", "userdata", "presets", "templates", "history", ".pdf_bookmarks"}


def version_key(value):
    match = _VERSION.fullmatch(str(value))
    if not match:
        raise UpdateError("版本号不符合语义版本格式。")
    pre = match.group(4)
    if pre:
        parts = pre.split(".")
        if any(not p or (p.isdigit() and len(p) > 1 and p[0] == "0") for p in parts):
            raise UpdateError("无效的预发行版本号。")
        prerelease = tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts)
    else:
        prerelease = ()
    return tuple(int(match.group(i)) for i in range(1, 4)), pre is None, prerelease


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise UpdateError("程序包包含无效路径。")
    path = PurePosixPath(value)
    parts = value.split("/")
    if path.is_absolute() or any(p in ("", ".", "..") for p in parts):
        raise UpdateError("程序包路径越界。")
    for part in parts:
        if part.endswith((".", " ")) or any(ord(c) < 32 or c in '<>"|?*' for c in part):
            raise UpdateError("程序包包含 Windows 不支持的路径。")
        if part.split(".", 1)[0].upper() in _RESERVED:
            raise UpdateError("程序包使用了 Windows 保留文件名。")
    return value


def assert_safe_path(path):
    """Reject links and Windows reparse points anywhere in an existing path."""
    path = Path(os.path.abspath(path))
    for current in (path, *path.parents):
        try:
            status = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(status.st_mode) or getattr(status, "st_file_attributes", 0) & 0x400:
            raise UpdateError(f"更新路径含符号链接或目录联接：{current}")
    return path


def target_path(root, name):
    root = assert_safe_path(root)
    candidate = assert_safe_path(root.joinpath(*relative_path(name).split("/")))
    if not candidate.is_relative_to(root):
        raise UpdateError("文件不在程序目录内。")
    return candidate


def load_json(path):
    try:
        if Path(path).stat().st_size > 8 * 1024 * 1024:
            raise UpdateError("清单文件过大。")
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise UpdateError(f"不能读取有效清单：{exc}") from exc


def validate_release_manifest(data, build_info):
    if not isinstance(data, dict):
        raise UpdateError("更新清单必须为 JSON 对象。")
    if data.get("schema") != 1 or type(data.get("schema")) is not int:
        raise UpdateError("更新协议不兼容，请手动下载。")
    if data.get("app_id") != build_info.app_id:
        raise UpdateError("更新程序身份不一致。")
    minimum = data.get("minimum_updater_schema", 1)
    if type(minimum) is not int or minimum < 1 or minimum > build_info.update_schema:
        raise UpdateError("新版需要更高的更新协议，请手动更新。")
    version = data.get("version")
    if version_key(version) <= version_key(build_info.version):
        raise UpdateError("更新版本必须高于当前版本。")
    if data.get("channel", "stable") != build_info.channel:
        raise UpdateError("更新通道不一致。")
    if build_info.channel == "stable" and _VERSION.fullmatch(version).group(4):
        raise UpdateError("Stable 不安装预发行版本。")
    assets = data.get("assets")
    if not isinstance(assets, dict) or build_info.variant not in ("single", "portable"):
        raise UpdateError("更新发行类型无效。")
    asset = assets.get(build_info.variant)
    if not isinstance(asset, dict) or asset.get("variant", build_info.variant) != build_info.variant:
        raise UpdateError("更新发行类型不一致。")
    name = relative_path(asset.get("file"))
    if "/" in name or not name.lower().endswith(".exe" if build_info.variant == "single" else ".zip"):
        raise UpdateError("更新资产类型不正确。")
    if not isinstance(asset.get("sha256"), str) or not _HASH.fullmatch(asset["sha256"]):
        raise UpdateError("更新资产缺少有效 SHA-256。")
    if "size" in asset and (type(asset["size"]) is not int or asset["size"] < 1):
        raise UpdateError("更新资产大小无效。")
    return data


def validate_package_manifest(data, build_info=None, expected_version=None):
    if not isinstance(data, dict) or data.get("schema") != 1 or type(data.get("schema")) is not int:
        raise UpdateError("Portable 清单协议不兼容。")
    if data.get("variant") != "portable" or not isinstance(data.get("app_id"), str):
        raise UpdateError("Portable 程序身份/类型无效。")
    if build_info is not None and data["app_id"] != build_info.app_id:
        raise UpdateError("Portable 程序身份不一致。")
    version_key(data.get("version"))
    if expected_version is not None and data["version"] != expected_version:
        raise UpdateError("程序包版本与更新清单不一致。")
    entrypoint = relative_path(data.get("entrypoint"))
    if "/" in entrypoint or not entrypoint.lower().endswith(".exe"):
        raise UpdateError("Portable 主入口必须位于根目录。")
    files = data.get("managed_files")
    if not isinstance(files, list) or not files or len(files) > 100000:
        raise UpdateError("Portable 程序文件清单无效。")
    names = set()
    for item in files:
        if not isinstance(item, dict):
            raise UpdateError("Portable 文件清单必须包含路径、大小和 SHA-256。")
        name = relative_path(item.get("path"))
        lower = name.casefold()
        if lower in names or lower == "package-manifest.json" or name.split("/")[0].casefold() in _USER_NAMES:
            raise UpdateError("程序清单含重复文件、元数据或用户数据路径。")
        names.add(lower)
        if type(item.get("size")) is not int or item["size"] < 0 or not isinstance(item.get("sha256"), str) or not _HASH.fullmatch(item["sha256"]):
            raise UpdateError("Portable 文件大小或 SHA-256 无效。")
    if entrypoint.casefold() not in names:
        raise UpdateError("Portable 清单缺少主入口。")
    for name in names:
        if any(parent in names for parent in (str(p) for p in PurePosixPath(name).parents) if parent != "."):
            raise UpdateError("Portable 清单中目录与文件相互冲突。")
    return data


def verify_records(root, manifest, launcher_name=None):
    for record in manifest["managed_files"]:
        name = launcher_name if launcher_name and record["path"] == manifest["entrypoint"] else record["path"]
        file = target_path(root, name)
        if not file.is_file() or file.stat().st_size != record["size"] or sha256_file(file) != record["sha256"].lower():
            raise UpdateError(f"Portable 文件校验失败：{name}")
