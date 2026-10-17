"""Local, unfinished editor drafts and bounded in-memory undo/redo states."""

from dataclasses import MISSING, asdict, fields
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from bookmarks_core import BookmarkError
from toc_generation import Draft, DraftEntry, _mapping


def _absolute(path):
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _path_key(path):
    return os.path.normcase(str(_absolute(path)))


def _json_copy(value):
    def check_keys(item):
        if isinstance(item, dict):
            if any(type(key) is not str for key in item):
                raise ValueError("草稿对象的键必须是字符串。")
            for child in item.values():
                check_keys(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                check_keys(child)
    try:
        check_keys(value)
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, OverflowError, RecursionError, ValueError) as exc:
        raise ValueError(f"草稿包含无效或非有限的 JSON 数据：{exc}") from None


def _integer(value, label, *, maximum=None):
    if type(value) is not int or value < 1 or (maximum is not None and value > maximum):
        raise ValueError(f"{label}必须是有效范围内的正整数。")


def _fields(data, kind):
    if not isinstance(data, dict):
        raise ValueError("草稿结构须为对象。")
    declared = {item.name: item for item in fields(kind)}
    required = {name for name, item in declared.items()
                if item.default is MISSING and item.default_factory is MISSING}
    if set(data) - set(declared) or not required <= set(data):
        raise ValueError("草稿字段缺失或不受支持。")


def _validated_state(state):
    clean = _json_copy(state)
    if (not isinstance(clean, dict) or set(clean) != {"schema_version", "draft", "numbering_sources", "options"}
            or type(clean["schema_version"]) is not int or clean["schema_version"] != 1):
        raise ValueError("不支持的编辑草稿格式；需要 schema_version=1。")
    data = clean["draft"]
    _fields(data, Draft)
    if not isinstance(data["pdf_path"], str) or not Path(data["pdf_path"]).is_absolute():
        raise ValueError("草稿必须记录 PDF 的绝对路径。")
    count = data["page_count"]
    _integer(count, "PDF页数")
    if not isinstance(data["entries"], list):
        raise ValueError("草稿条目须为数组。")
    for entry in data["entries"]:
        _fields(entry, DraftEntry)
        _integer(entry["level"], "层级", maximum=20)
        if not isinstance(entry["title"], str) or "\x00" in entry["title"]:
            raise ValueError("条目标题须为不含空字符的文字。")
        for name in ("printed_page", "pdf_page", "source_page"):
            page = entry.get(name)
            if page is not None:
                _integer(page, name, maximum=count if name != "printed_page" else None)
        for name in ("confidence", "note"):
            if name in entry and not isinstance(entry[name], str):
                raise ValueError(f"{name}须为文字。")
        confirmed = entry.get("confirmed", False)
        if type(confirmed) is not bool:
            raise ValueError("确认状态须为布尔值。")
        if confirmed and (entry.get("pdf_page") is None or not entry["title"].strip()):
            raise ValueError("目标页未知或标题为空的条目不能标为已确认。")
        rect = entry.get("source_rect")
        if rect is not None:
            if (not isinstance(rect, list) or len(rect) != 4
                    or any(type(value) not in (int, float) for value in rect)
                    or rect[0] < 0 or rect[1] < 0 or rect[2] > 1 or rect[3] > 1
                    or rect[2] <= rect[0] or rect[3] <= rect[1]):
                raise ValueError("来源区域须为四个 0–1 有限数字组成的有效矩形。")
    if (not isinstance(data["toc_pages"], list) or not isinstance(data["method"], str)
            or not isinstance(data["notes"], list) or any(not isinstance(note, str) for note in data["notes"])):
        raise ValueError("草稿目录页、识别方法或备注格式无效。")
    for page in data["toc_pages"]:
        _integer(page, "目录PDF页", maximum=count)
    titles = data.get("source_titles")
    if titles is not None and (not isinstance(titles, list) or any(not isinstance(title, str) for title in titles)):
        raise ValueError("原始标题须为文字数组或留空。")
    if data["mapping"] is not None:
        try:
            _mapping(data["mapping"], count)
        except BookmarkError as exc:
            raise ValueError(f"草稿页码映射无效：{exc}") from None
    sources = clean["numbering_sources"]
    if (not isinstance(sources, list) or len(sources) != len(data["entries"])
            or any(source is not None and not isinstance(source, str) for source in sources)):
        raise ValueError("编号来源须按条目顺序提供等长的文字或空值数组。")
    if not isinstance(clean["options"], dict):
        raise ValueError("编辑选项须为对象。")
    return clean


def snapshot_state(draft, *, numbering_sources=None, options=None):
    """Copy all dataclass fields without confirming or mapping any entry."""
    data = asdict(draft)
    data["pdf_path"] = str(_absolute(draft.pdf_path))
    return _validated_state({"schema_version": 1, "draft": data,
        "numbering_sources": [None] * len(draft.entries) if numbering_sources is None else numbering_sources,
        "options": {} if options is None else options})


def restore_state(state):
    """Restore an independent Draft and its position-based editor metadata."""
    clean = _validated_state(state)
    data = clean["draft"]
    data["pdf_path"] = Path(data["pdf_path"])
    entries = []
    for entry in data["entries"]:
        if entry.get("source_rect") is not None:
            entry["source_rect"] = tuple(entry["source_rect"])
        entries.append(DraftEntry(**entry))
    data["entries"] = entries
    return Draft(**data), clean["numbering_sources"], clean["options"]


def _identity(pdf):
    path = _absolute(pdf)
    try:
        stat = path.stat()
        if not path.is_file():
            raise ValueError("PDF 路径不是文件。")
    except OSError as exc:
        raise ValueError(f"无法核对草稿对应的 PDF：{exc}") from None
    return {"path": _path_key(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _ordinary_store(path):
    for item in (path, *path.parents):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError("编辑草稿目录和文件不能是符号链接或目录联接。")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"恢复草稿包含重复字段：{key}")
        result[key] = value
    return result


class DraftStore:
    """Explicit local recovery directory; never write to the PDF/TOC JSON."""

    def __init__(self, root_dir):
        self.root_dir = _absolute(root_dir)
        if str(self.root_dir).startswith("\\\\"):
            raise ValueError("编辑草稿须保存在本机目录。")
        self._archives = {}

    def path_for(self, pdf):
        key = hashlib.sha256(_path_key(pdf).encode("utf8")).hexdigest()
        return self.root_dir / f"{key}.json"

    def exists(self, pdf):
        target = self.path_for(pdf)
        _ordinary_store(target)
        return target.is_file()

    def archive(self, pdf):
        """Explicitly preserve the canonical bytes without moving/deleting them."""
        target = self.path_for(pdf)
        _ordinary_store(target)
        if not target.is_file():
            raise ValueError("没有可保留副本的恢复草稿。")
        content = target.read_bytes()
        stamp = time.time_ns()
        while True:
            backup = target.with_name(f"{target.stem}_{stamp}.backup.json")
            _ordinary_store(backup)
            try:
                with backup.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                break
            except FileExistsError:
                stamp = max(time.time_ns(), stamp + 1)
        _ordinary_store(target)
        if target.read_bytes() != content:
            raise ValueError("保留副本期间草稿已变化；副本仍保留，请重新核对。")
        self._archives[target] = (backup, hashlib.sha256(content).hexdigest())
        return backup

    def _archived_invalid(self, target):
        archive = self._archives.get(target)
        if archive is None:
            raise ValueError("须先明确保留原草稿副本，才能替换无效恢复文件。")
        backup, expected = archive
        _ordinary_store(backup)
        try:
            hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (target, backup)]
        except OSError as exc:
            raise ValueError(f"无法核验原草稿副本，恢复文件未改动：{exc}") from None
        if any(value != expected for value in hashes):
            raise ValueError("原草稿或保留副本已变化，不能覆盖恢复文件。")

    def save(self, pdf, state, *, replace_invalid=False):
        if type(replace_invalid) is not bool:
            raise ValueError("替换无效草稿的选项须为布尔值。")
        clean = _validated_state(state)
        identity = _identity(pdf)
        if _path_key(clean["draft"]["pdf_path"]) != identity["path"]:
            raise ValueError("草稿的 PDF 路径与保存对象不一致。")
        target = self.path_for(pdf)
        _ordinary_store(target)
        if target.exists():
            try:
                self.load(pdf)
            except ValueError:
                if not replace_invalid:
                    raise
                self._archived_invalid(target)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        envelope = {"schema_version": 1, "pdf": identity, "state": clean}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf8", dir=self.root_dir,
                    prefix=f".{target.stem}.", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(envelope, stream, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if _identity(pdf) != identity:
                raise ValueError("保存期间 PDF 已变化，原恢复草稿保持不变。")
            _ordinary_store(target)
            os.replace(temporary, target)
            self._archives.pop(target, None)
            return target
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def load(self, pdf):
        target = self.path_for(pdf)
        _ordinary_store(target)
        identity = _identity(pdf)
        try:
            envelope = json.loads(target.read_text(encoding="utf8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f"无法读取恢复草稿，原文件未改动：{exc}") from None
        if (not isinstance(envelope, dict) or set(envelope) != {"schema_version", "pdf", "state"}
                or type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1):
            raise ValueError("恢复草稿格式损坏或版本不受支持，原文件未改动。")
        saved_identity = envelope["pdf"]
        if (not isinstance(saved_identity, dict) or set(saved_identity) != {"path", "size", "mtime_ns"}
                or not isinstance(saved_identity["path"], str)
                or type(saved_identity["size"]) is not int or saved_identity["size"] < 0
                or type(saved_identity["mtime_ns"]) is not int):
            raise ValueError("恢复草稿的 PDF 标识损坏，原文件未改动。")
        if saved_identity != identity or _identity(pdf) != identity:
            raise ValueError("PDF 已变化，不能自动恢复旧草稿；原恢复文件未改动。")
        clean = _validated_state(envelope["state"])
        if _path_key(clean["draft"]["pdf_path"]) != identity["path"]:
            raise ValueError("恢复草稿对应其他 PDF，原文件未改动。")
        return clean


class UndoHistory:
    """Bounded JSON states; no filesystem operations or shared mutable values."""

    def __init__(self, limit=80):
        if type(limit) is not int or limit < 1:
            raise ValueError("历史记录上限须为正整数。")
        self.limit = limit
        self._states = []
        self._cursor = -1

    @property
    def can_undo(self):
        return self._cursor > 0

    @property
    def can_redo(self):
        return self._cursor + 1 < len(self._states)

    def reset(self, state):
        self._states = [_json_copy(state)]
        self._cursor = 0

    def record(self, state):
        clean = _json_copy(state)
        if self._cursor >= 0 and json.dumps(clean, sort_keys=True) == json.dumps(self._states[self._cursor], sort_keys=True):
            return False
        self._states = self._states[:self._cursor + 1] + [clean]
        self._states = self._states[-self.limit:]
        self._cursor = len(self._states) - 1
        return True

    def undo(self):
        if not self.can_undo:
            return None
        self._cursor -= 1
        return _json_copy(self._states[self._cursor])

    def redo(self):
        if not self.can_redo:
            return None
        self._cursor += 1
        return _json_copy(self._states[self._cursor])
