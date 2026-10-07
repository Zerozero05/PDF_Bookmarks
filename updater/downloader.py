"""Bounded-memory downloads with partial files, cancellation and hash checks."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import urllib.request
import uuid

from . import UpdateError
from .checker import open_github, trusted_https
from .manifest import assert_safe_path


CHUNK_SIZE = 256 * 1024


class DownloadError(OSError):
    pass


def downloads_root():
    return Path(tempfile.gettempdir()) / "PDF_Bookmarks_Update" / "downloads"


def new_download_directory(app_id):
    root = assert_safe_path(downloads_root())
    root.mkdir(parents=True, exist_ok=True)
    directory = root / uuid.uuid4().hex
    directory.mkdir()
    try:
        (directory / "download.json").write_text(json.dumps({"app_id": app_id, "pid": os.getpid(), "created": time.time()}), encoding="utf-8")
    except OSError:
        (directory / "download.json").unlink(missing_ok=True)
        directory.rmdir()
        raise
    return directory


def remove_download_directory(directory, app_id):
    """Only remove a UUID download directory carrying our own ownership marker."""
    try:
        directory = assert_safe_path(directory)
        root = assert_safe_path(downloads_root())
        if directory.parent != root or not re.fullmatch(r"[0-9a-f]{32}", directory.name):
            return False
        marker_path = assert_safe_path(directory / "download.json")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if not isinstance(marker, dict) or marker.get("app_id") != app_id:
            return False
        files = list(directory.iterdir())
        if any(assert_safe_path(p).is_dir() or p.name not in {"download.json", "package", "package.part"} for p in files):
            return False
        for file in files:
            file.unlink()
        directory.rmdir()
        return True
    except (OSError, ValueError, UpdateError):
        return False


def cleanup_interrupted_downloads(app_id):
    from .processes import process_alive

    root = downloads_root()
    try:
        assert_safe_path(root)
    except (OSError, UpdateError):
        return
    if not root.is_dir():
        return
    try:
        directories = list(root.iterdir())
    except OSError:
        return
    for directory in directories:
        try:
            assert_safe_path(directory)
            marker = json.loads(assert_safe_path(directory / "download.json").read_text(encoding="utf-8"))
            if not isinstance(marker, dict):
                continue
            pid = marker.get("pid")
            if marker.get("app_id") == app_id and type(pid) is int and not process_alive(pid):
                remove_download_directory(directory, app_id)
        except (OSError, ValueError, UpdateError):
            continue


def download_asset(asset, destination, *, progress=None, cancelled=None, opener=None):
    destination = assert_safe_path(destination)
    partial = destination.with_name(destination.name + ".part")
    if not isinstance(asset, dict) or type(asset.get("size")) is not int or not 0 < asset["size"] <= 8 * 1024**3:
        raise DownloadError("更新资产大小无效。")
    if not isinstance(asset.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", asset["sha256"]):
        raise DownloadError("更新资产 SHA-256 无效。")
    expected_size = asset["size"]
    expected_hash = asset["sha256"].lower()
    if destination.exists() or partial.exists() or partial.is_symlink():
        raise DownloadError("下载目标已存在，未覆盖或删除原文件。")
    trusted_https(asset.get("url"))
    if cancelled is not None and cancelled.is_set():
        raise DownloadError("已取消下载，原程序未改变。")
    if shutil.disk_usage(destination.parent).free < expected_size + 16 * 1024**2:
        raise DownloadError("下载临时目录空间不足，原程序未改变。")
    request = urllib.request.Request(trusted_https(asset["url"]), headers={"User-Agent": "PDF_Bookmarks-Updater"})
    opener = opener or open_github
    digest, received = hashlib.sha256(), 0
    created_partial = completed = False
    try:
        with opener(request, timeout=30) as response:
            trusted_https(response.geturl())
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) != expected_size:
                raise DownloadError("下载大小与发行版不一致。")
            stream = partial.open("xb")
            created_partial = True
            with stream:
                while True:
                    if cancelled is not None and cancelled.is_set():
                        raise DownloadError("已取消下载，原程序未改变。")
                    block = response.read(CHUNK_SIZE)
                    if not block:
                        break
                    received += len(block)
                    if received > expected_size:
                        raise DownloadError("下载文件超过已验证的大小。")
                    digest.update(block)
                    stream.write(block)
                    if progress:
                        progress(received, expected_size)
                stream.flush()
                os.fsync(stream.fileno())
        if cancelled is not None and cancelled.is_set():
            raise DownloadError("已取消下载，原程序未改变。")
        if received != expected_size or digest.hexdigest() != expected_hash:
            raise DownloadError("下载未完成或 SHA-256 校验失败，原程序未改变。")
        if destination.exists():
            raise DownloadError("下载目标在下载过程中被创建，未覆盖。")
        os.replace(partial, destination)
        completed = True
        return destination
    except Exception as error:
        if isinstance(error, DownloadError):
            raise
        raise DownloadError(f"下载失败：{error}") from error
    finally:
        if created_partial and not completed:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                # Ownership-marked download directories are retried at startup.
                pass
