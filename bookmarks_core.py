"""Read, preview and safely append PDF bookmarks without changing its path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

import pymupdf


class BookmarkError(Exception):
    """A validation or safe-write failure suitable for displaying to the user."""


@dataclass
class Plan:
    pdf_path: Path
    toc_path: Path
    page_count: int
    rows: list[list]
    preview: list[dict]
    existing: list[list]
    source_sha256: str


def _sha256(path: Path, length: int | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        remaining = length
        while remaining is None or remaining > 0:
            block = stream.read(1024 * 1024 if remaining is None else min(1024 * 1024, remaining))
            if not block:
                if remaining:
                    raise BookmarkError("临时 PDF 比原文件短，已停止写入。")
                break
            digest.update(block)
            if remaining is not None:
                remaining -= len(block)
    return digest.hexdigest()


def _integer(value, label: str, positive: bool = False) -> int:
    if type(value) is not int or (positive and value < 1):
        raise BookmarkError(f"{label} 必须是{'正' if positive else ''}整数（不能是布尔值）。")
    return value


def _keys(obj, allowed: set[str], label: str) -> dict:
    if not isinstance(obj, dict):
        raise BookmarkError(f"{label} 必须是 JSON 对象。")
    unknown = set(obj) - allowed
    if unknown:
        raise BookmarkError(f"{label} 包含未知字段：{', '.join(sorted(unknown))}。")
    return obj


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BookmarkError(f"JSON 中字段 {key!r} 重复。")
        result[key] = value
    return result


def _read_toc(path: Path, page_count: int) -> tuple[list[list], list[dict]]:
    with path.open("r", encoding="utf-8-sig") as stream:
        root = json.load(stream, object_pairs_hook=_unique_keys)
    _keys(root, {"version", "mapping", "bookmarks"}, "目录文件")
    if _integer(root.get("version"), "version") != 1:
        raise BookmarkError("目录文件的 version 必须为 1。")
    mapping = _keys(root.get("mapping", {"offset": 0}), {"offset", "segments"}, "mapping")
    if len(mapping) != 1:
        raise BookmarkError("mapping 必须且只能包含 offset 或 segments。")
    segments = []
    if "offset" in mapping:
        offset = _integer(mapping["offset"], "mapping.offset")
    else:
        raw_segments = mapping["segments"]
        if not isinstance(raw_segments, list) or not raw_segments:
            raise BookmarkError("mapping.segments 必须是非空数组。")
        for index, segment in enumerate(raw_segments, 1):
            label = f"mapping.segments[{index}]"
            _keys(segment, {"printed_start", "printed_end", "pdf_start"}, label)
            start = _integer(segment.get("printed_start"), f"{label}.printed_start", True)
            end = _integer(segment.get("printed_end"), f"{label}.printed_end", True)
            pdf_start = _integer(segment.get("pdf_start"), f"{label}.pdf_start", True)
            if end < start:
                raise BookmarkError(f"{label} 的 printed_end 小于 printed_start。")
            if pdf_start + end - start > page_count:
                raise BookmarkError(f"{label} 的映射范围超出 PDF 的 {page_count} 页。")
            segments.append((start, end, pdf_start))
        segments.sort()
        for previous, current in zip(segments, segments[1:]):
            if current[0] <= previous[1]:
                raise BookmarkError("mapping.segments 的印刷页码范围不能重叠。")

    def map_page(printed: int) -> int:
        if "offset" in mapping:
            return printed + offset
        for start, end, pdf_start in segments:
            if start <= printed <= end:
                return pdf_start + printed - start
        raise BookmarkError(f"印刷页码 {printed} 不在任何分段映射范围内。")

    rows, preview = [], []

    def visit(nodes, level: int, label: str) -> None:
        if not isinstance(nodes, list):
            raise BookmarkError(f"{label} 必须是数组。")
        for index, node in enumerate(nodes, 1):
            location = f"{label}[{index}]"
            _keys(node, {"title", "page", "pdf_page", "children"}, location)
            title = node.get("title")
            if not isinstance(title, str) or not title.strip() or "\x00" in title:
                raise BookmarkError(f"{location}.title 必须是非空文本且不能包含空字符。")
            if ("page" in node) == ("pdf_page" in node):
                raise BookmarkError(f"{location} 必须且只能提供 page 或 pdf_page。")
            printed = _integer(node["page"], f"{location}.page", True) if "page" in node else None
            target = map_page(printed) if printed is not None else _integer(node["pdf_page"], f"{location}.pdf_page", True)
            if not 1 <= target <= page_count:
                raise BookmarkError(f"书签“{title}”指向 PDF 第 {target} 页，超出 1–{page_count} 页。")
            rows.append([level, title, target])
            preview.append({"level": level, "title": title, "printed_page": printed, "pdf_page": target})
            if "children" in node:
                visit(node["children"], level + 1, f"{location}.children")

    nodes = root.get("bookmarks")
    if not isinstance(nodes, list) or not nodes:
        raise BookmarkError("bookmarks 必须是非空数组。")
    visit(nodes, 1, "bookmarks")
    return rows, preview


def _check_path(path: Path) -> None:
    if path.is_symlink():
        raise BookmarkError("不处理符号链接 PDF；请使用实际文件路径。")
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise BookmarkError(f"不是可读取的 PDF 文件：{path}")


def _check_document(document) -> None:
    if not document.is_pdf:
        raise BookmarkError("输入文件不是 PDF。")
    if (document.needs_pass or document.is_encrypted
            or document.xref_get_key(-1, "Encrypt")[0] != "null"):
        raise BookmarkError("暂不处理加密或受密码保护的 PDF。")
    if document.is_repaired or not document.can_save_incrementally():
        raise BookmarkError("此 PDF 需要修复或不能增量保存；为保护原文件，已停止处理。")
    if document.get_sigflags() > 0:
        raise BookmarkError("检测到 PDF 签名标志；为保护签名，已停止处理。")
    for page in document:
        for widget in page.widgets() or ():
            if widget.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE:
                raise BookmarkError("检测到 PDF 签名字段；为保护签名，已停止处理。")
    if document.page_count < 1:
        raise BookmarkError("PDF 没有页面。")


def inspect_pdf(pdf_path, toc_path) -> Plan:
    """Validate both inputs and return a read-only preview with actual 1-based pages."""
    pdf_path = Path(pdf_path).absolute()
    toc_path = Path(toc_path).absolute()
    try:
        _check_path(pdf_path)
        original_hash = _sha256(pdf_path)
        with pymupdf.open(str(pdf_path)) as document:
            _check_document(document)
            page_count = document.page_count
            existing = document.get_toc()
            rows, preview = _read_toc(toc_path, page_count)
        if _sha256(pdf_path) != original_hash:
            raise BookmarkError("预览期间 PDF 已被其他程序修改，请重新预览。")
        return Plan(pdf_path, toc_path, page_count, rows, preview, existing, original_hash)
    except BookmarkError:
        raise
    except Exception as error:
        raise BookmarkError(f"无法预览：{error}") from error


def _check_source(plan: Plan) -> None:
    _check_path(plan.pdf_path)
    if _sha256(plan.pdf_path) != plan.source_sha256:
        raise BookmarkError("PDF 在预览后已发生变化，请重新预览后再写入。")


def _make_backup(plan: Plan, directory=None) -> Path:
    directory = (Path(directory).expanduser().absolute() if directory is not None
                 else plan.pdf_path.parent / "_backup")
    if directory.is_symlink():
        raise BookmarkError("备份目录不能是符号链接。")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = directory / f"{plan.pdf_path.stem}.{stamp}.{uuid.uuid4().hex[:8]}.pdf"
    try:
        with plan.pdf_path.open("rb") as source, backup.open("xb") as target:
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        shutil.copystat(plan.pdf_path, backup)
        if _sha256(backup) != plan.source_sha256:
            raise BookmarkError("备份校验失败；原 PDF 未修改。")
    except Exception:
        backup.unlink(missing_ok=True)
        raise
    return backup


def _clear_jasminum_cache(plan: Plan) -> dict:
    cache = plan.pdf_path.parent / "jasminum-outline.json"
    result = {"cache_path": str(cache), "cache_status": "not_found", "warnings": []}
    try:
        if cache.is_symlink():
            raise OSError("缓存是符号链接，已保留。")
        if not cache.exists():
            return result
        if cache.resolve() == plan.toc_path.resolve() or cache.samefile(plan.toc_path):
            raise OSError("缓存文件同时是本次输入的目录 JSON，已保留。")
        cache.unlink()
        result["cache_status"] = "deleted"
    except Exception as error:
        result["cache_status"] = "failed"
        result["warnings"].append(f"PDF 已写入，但未删除茉莉花缓存 {cache}：{error}")
    return result


def write_plan(plan: Plan, existing: str = "skip", *, backup: bool = True,
               backup_dir=None, clear_jasminum_cache: bool = False) -> dict:
    """Write a validated plan with optional backup and post-success cache removal.

    Only ``existing='replace'`` permits replacing the complete existing outline.
    A same-directory incremental copy is verified before the atomic replacement.
    """
    if existing not in {"skip", "replace"}:
        raise BookmarkError("existing 必须为 skip 或 replace。")
    if not backup and backup_dir is not None:
        raise BookmarkError("未启用备份，不能指定备份文件夹。")
    lock_path = plan.pdf_path.with_name(f".{plan.pdf_path.name}.bookmarks.lock")
    temporary = None
    lock_fd = None
    backup_path = None
    try:
        _check_source(plan)
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise BookmarkError(f"此 PDF 已有工具锁：{lock_path}。若上次异常退出，请确认工具已关闭后删除该锁文件。") from error
        os.write(lock_fd, f"pid={os.getpid()}\n".encode("ascii"))
        _check_source(plan)
        with pymupdf.open(str(plan.pdf_path)) as original:
            _check_document(original)
            if original.page_count != plan.page_count:
                raise BookmarkError("PDF 页数已变化，请重新预览。")
            if original.get_toc() and existing == "skip":
                return {"status": "skipped", "message": "已存在书签，按默认策略跳过；原 PDF 未修改。", "backup": None}
            page_xrefs = [page.xref for page in original]
            metadata = original.metadata
        original_size = plan.pdf_path.stat().st_size
        if backup:
            backup_path = _make_backup(plan, backup_dir)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{plan.pdf_path.name}.bookmarks.", suffix=".tmp", dir=plan.pdf_path.parent)
        os.close(fd)
        temporary = Path(temporary_name)
        shutil.copy2(plan.pdf_path, temporary)
        if _sha256(temporary) != plan.source_sha256:
            raise BookmarkError("复制期间原 PDF 已发生变化，已停止写入。")
        with pymupdf.open(str(temporary)) as document:
            _check_document(document)
            document.set_toc(plan.rows)
            document.save(str(temporary), incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP, no_new_id=True)
        with pymupdf.open(str(temporary)) as verified:
            if (verified.is_repaired or verified.page_count != plan.page_count
                    or verified.get_toc() != plan.rows
                    or [page.xref for page in verified] != page_xrefs
                    or verified.metadata != metadata):
                raise BookmarkError("写入结果未通过书签、页数、页面对象或元数据校验；原 PDF 未修改。")
        if _sha256(temporary, original_size) != plan.source_sha256:
            raise BookmarkError("增量保存改变了原始 PDF 字节；原 PDF 未修改。")
        os.utime(temporary, None)
        with temporary.open("r+b") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        _check_source(plan)
        os.replace(temporary, plan.pdf_path)
        temporary = None
        result = {"status": "written", "message": f"已原地写入 {len(plan.rows)} 个书签。",
                  "backup": str(backup_path) if backup_path is not None else None,
                  "cache_status": "not_requested", "warnings": []}
        if clear_jasminum_cache:
            result.update(_clear_jasminum_cache(plan))
        return result
    except BookmarkError as error:
        if backup_path is not None:
            raise BookmarkError(f"{error}；备份保留于 {backup_path}") from error
        raise
    except Exception as error:
        backup_note = f"；备份保留于 {backup_path}" if backup_path is not None else ""
        raise BookmarkError(f"写入失败，原 PDF 未修改：{error}{backup_note}") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # A stale tool temporary must not hide the original failure.
        if lock_fd is not None:
            os.close(lock_fd)
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass  # A stale lock remains visible and blocks the next write.


def discover_pairs(folder, recursive: bool = False, *, exclude_dirs=()) -> list[tuple[Path, Path | None]]:
    """Find PDF + same-stem .toc.json pairs, retaining PDFs with a missing JSON."""
    folder = Path(folder).absolute()
    if not folder.is_dir():
        raise BookmarkError(f"文件夹不存在：{folder}")
    excluded = {"_backup", ".git", ".venv", "__pycache__"}
    custom_excluded = {Path(path).expanduser().resolve() for path in exclude_dirs}
    if any(part.lower() in excluded for part in folder.parts):
        return []
    result = []

    def scan_error(error):
        raise error

    try:
        for current, directories, files in os.walk(folder, followlinks=False, onerror=scan_error):
            directories[:] = sorted(name for name in directories if name.lower() not in excluded
                                    and (Path(current) / name).resolve() not in custom_excluded)
            for name in sorted(files, key=str.casefold):
                if not name.lower().endswith(".pdf") or ".bookmarks." in name.lower():
                    continue
                pdf = Path(current) / name
                toc = pdf.with_suffix(".toc.json")
                result.append((pdf, toc if toc.is_file() else None))
            if not recursive:
                break
    except OSError as error:
        raise BookmarkError(f"无法扫描文件夹：{error}") from error
    return sorted(result, key=lambda pair: str(pair[0]).casefold())
