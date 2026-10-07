"""Small, independent helpers for desktop settings, file drops and page previews.

GUI settings expose SETTINGS_DEFAULTS keys; invalid values fall back individually.
Saving retains unknown preferences and refuses to overwrite malformed files.
``dropped_pairs`` preserves PDF input order and returns None for missing/ambiguous
JSON matches. It ignores directories; the GUI handles folder discovery separately.
``render_page`` reads one 1-based PDF page and returns a bounded PNG byte string.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pymupdf

from config_manager import (DEFAULT_CONFIG, load_config, sanitize_settings,
                            save_config, settings_path)


SETTINGS_DEFAULTS = DEFAULT_CONFIG


def _settings_path(path=None) -> Path:
    return settings_path(path)


def _clean_settings(settings) -> dict:
    return sanitize_settings(settings)


def load_settings(path=None) -> dict:
    """Load whitelisted settings; a missing, unreadable or malformed file is safe."""
    return load_config(path)


def save_settings(settings, path=None) -> None:
    """Atomically save sanitized settings, optionally to a test-supplied path.

    The default location is LOCALAPPDATA/ZoteroPDFBookmarks/settings.json.
    An unavailable location or failed write raises OSError for the GUI to report.
    """
    save_config(settings, path)


def toc_file_signature(path):
    """Snapshot the previewed JSON; changing or unavailable files are not deleted."""
    path = Path(path)
    try:
        if path.suffix.lower() != ".json" or path.is_symlink() or not path.is_file():
            return None
        before = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        after = path.stat()
        before_key = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        after_key = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        return (*after_key, digest) if before_key == after_key else None
    except OSError:
        return None


def delete_written_toc(path, expected_signature, pdf_paths):
    """Delete only the unchanged input JSON after the caller verifies all writes."""
    path = Path(path)
    try:
        if path.name.lower() == "jasminum-outline.json":
            raise OSError("这是茉莉花缓存，请使用独立的缓存清理选项。")
        if path.suffix.lower() != ".json" or path.is_symlink() or not path.is_file():
            raise OSError("目录 JSON 不存在、不是普通文件或是符号链接。")
        if any(path.resolve() == Path(pdf).resolve() or path.samefile(pdf) for pdf in pdf_paths):
            raise OSError("目录 JSON 与 PDF 指向同一文件。")
        if expected_signature is None or toc_file_signature(path) != expected_signature:
            raise OSError("目录 JSON 在预览后发生变化或无法核对，已保留。")
        path.unlink()
        return {"status": "deleted"}
    except Exception as error:
        return {"status": "retained", "warning": f"PDF 已写入，但目录 JSON 未删除：{path}\n  {error}"}


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _json_stem(path: Path) -> str:
    length = len(".toc.json") if path.name.lower().endswith(".toc.json") else len(".json")
    return os.path.normcase(path.name[:-length])


def dropped_pairs(paths) -> list[tuple[Path, Path | None]]:
    """Pair explicitly dropped PDFs/JSON files without guessing across duplicates.

    One PDF plus one JSON is an explicit pair regardless of their names. Otherwise,
    same-directory basename matches take priority (``.toc.json`` before ``.json``),
    followed by unique basename matches across directories. Only an automatically
    found same-directory ``.toc.json`` can serve as a fallback. Each JSON path is
    assigned at most once; ambiguous cross-directory matches remain unpaired.
    PDFs are deduplicated by their resolved, OS-normalized path, but returned paths
    retain their lexical identity so the writer can still reject a symlink PDF.
    """
    pdfs, jsons, seen = [], [], set()
    for value in paths:
        path = Path(value).expanduser().absolute()
        if path.is_dir() or path.suffix.lower() not in {".pdf", ".json"}:
            continue
        key = _path_key(path)
        if key in seen:
            continue
        seen.add(key)
        (pdfs if path.suffix.lower() == ".pdf" else jsons).append(path)
    if len(pdfs) == len(jsons) == 1:
        return [(pdfs[0], jsons[0])]

    assigned, used = {}, set()
    for index, pdf in enumerate(pdfs):
        candidates = [toc for toc in jsons if _path_key(toc) not in used
                      and _json_stem(toc) == os.path.normcase(pdf.stem)
                      and _path_key(toc.parent) == _path_key(pdf.parent)]
        if candidates:
            toc = min(candidates, key=lambda item: not item.name.lower().endswith(".toc.json"))
            assigned[index] = toc
            used.add(_path_key(toc))

    for index, pdf in enumerate(pdfs):
        if index in assigned:
            continue
        stem = os.path.normcase(pdf.stem)
        remaining = [other for position, other in enumerate(pdfs)
                     if position not in assigned and os.path.normcase(other.stem) == stem]
        candidates = [toc for toc in jsons if _path_key(toc) not in used and _json_stem(toc) == stem]
        if len(remaining) == len(candidates) == 1:
            assigned[index] = candidates[0]
            used.add(_path_key(candidates[0]))

    result = []
    for index, pdf in enumerate(pdfs):
        toc = assigned.get(index)
        if toc is None:
            sidecar = pdf.with_suffix(".toc.json")
            if sidecar.is_file() and _path_key(sidecar) not in used:
                toc = sidecar
                used.add(_path_key(sidecar))
        result.append((pdf, toc))
    return result


def render_page(pdf_path, pdf_page: int, max_width: int = 800, max_height: int = 1000) -> bytes:
    """Return a PNG preview; no document write, OCR or persistent image cache."""
    if type(pdf_page) is not int or pdf_page < 1:
        raise ValueError("PDF 实际页码必须是从 1 开始的整数。")
    if any(type(size) is not int or not 1 <= size <= 8192 for size in (max_width, max_height)):
        raise ValueError("预览尺寸必须是 1–8192 的整数。")
    with pymupdf.open(str(pdf_path)) as document:
        if not document.is_pdf or document.needs_pass:
            raise ValueError("无法预览此 PDF。")
        if pdf_page > document.page_count:
            raise ValueError(f"PDF 只有 {document.page_count} 页。")
        page = document.load_page(pdf_page - 1)
        if page.rect.width <= 0 or page.rect.height <= 0:
            raise ValueError("PDF 页面尺寸无效。")
        scale = min(2.0, (max_width - 0.5) / page.rect.width, (max_height - 0.5) / page.rect.height)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
        return pixmap.tobytes("png")
