"""Read-only TOC recognition and explicitly reviewed JSON drafts.

OCR is local and loaded only for pages without useful text.  Recognition is a
draft: page evidence and recognition confidence never replace user confirmation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import tempfile

import pymupdf

from bookmarks_core import BookmarkError, inspect_pdf


@dataclass
class DraftEntry:
    level: int
    title: str
    printed_page: int | None
    pdf_page: int | None = None
    confidence: str = "待确认"
    note: str = ""
    confirmed: bool = False
    source_page: int | None = None
    source_rect: tuple[float, float, float, float] | None = None


@dataclass
class Draft:
    pdf_path: Path
    page_count: int
    entries: list[DraftEntry]
    toc_pages: list[int]
    mapping: dict | None
    method: str
    notes: list[str]
    source_titles: list[str] | None = None


@dataclass
class _Line:
    text: str
    x: float
    y: float
    height: float
    score: float
    numbers: list[tuple[int, float]] = field(default_factory=list)
    column: int = 0
    left: float = 0
    right: float | None = None
    rect: tuple[float, float, float, float] | None = None


_PART = re.compile(r"^(?:第\s*[\d一二三四五六七八九十百零〇]+\s*[篇部卷]|part\s+(?:[\divxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)\b)", re.I)
_CHAPTER = re.compile(r"^(?:第\s*[\d一二三四五六七八九十百零〇]+\s*[章篇部卷]|(?:chapter|part)\s+(?:[\divxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)\b)", re.I)
_FRONT = re.compile(r"^(?:前言|序言|自序|序|致谢|出版说明|preface|foreword|acknowledg)", re.I)
_ROOT = re.compile(r"^(?:附录|参考文献|索引|习题解答|appendix|references|bibliography|index|(?:外国)?(?:数学家)?译名对照表$|关键词索引$|(?:部分)?习题答案(?:和提示)?$|(?:《[^》]+》)?(?:已出版书目|出版书目)$)", re.I)
_LEVEL_ROOT = re.compile(r"^(?:符号表|注释|prologue\b|notes\s+and\s+comments|list\s+of\s+(?:special\s+)?symbols)", re.I)
_PAGE = re.compile(r"^(.*?)(?:\s|[.．·…⋯_—-])+(\d{1,5}|[ivxlcdmIVXLCDM]{1,10})\s*$")
_NUM = re.compile(r"^[\s\-—–·.]*([0-9]{1,5})[\s\-—–·.]*$")
_BARE_SECTION = re.compile(r"[§S]?\s*\d+(?:\s*[.．]\s*\d+)+\s*[.．]?", re.I)
_OCR = None


def _integer(value, label, *, positive=False):
    if type(value) is not int or (positive and value < 1):
        raise BookmarkError(f"{label} 必须是{'正' if positive else ''}整数。")
    return value


def _cancelled(cancel):
    if cancel is not None and cancel.is_set():
        raise BookmarkError("已取消识别；原 PDF 未修改。")


def _mapping(mapping, page_count):
    if not isinstance(mapping, dict) or set(mapping) not in ({"offset"}, {"segments"}):
        raise BookmarkError("页码映射必须且只能包含 offset 或 segments。")
    if "offset" in mapping:
        return {"offset": _integer(mapping["offset"], "offset")}
    segments = mapping["segments"]
    if not isinstance(segments, list) or not segments:
        raise BookmarkError("segments 必须是非空数组。")
    clean = []
    for segment in segments:
        if not isinstance(segment, dict) or set(segment) != {"printed_start", "printed_end", "pdf_start"}:
            raise BookmarkError("每个分段必须提供 printed_start、printed_end 和 pdf_start。")
        item = {key: _integer(value, key, positive=True) for key, value in segment.items()}
        if item["printed_end"] < item["printed_start"]:
            raise BookmarkError("分段的终止印刷页码不能小于起始页码。")
        if item["pdf_start"] + item["printed_end"] - item["printed_start"] > page_count:
            raise BookmarkError("分段映射超出 PDF 页数。")
        clean.append(item)
    clean.sort(key=lambda item: item["printed_start"])
    if any(b["printed_start"] <= a["printed_end"] for a, b in zip(clean, clean[1:])):
        raise BookmarkError("分段的印刷页码范围不能重叠。")
    return {"segments": clean}


def _mapped(printed, mapping):
    if mapping is None:
        return None
    if "offset" in mapping:
        return printed + mapping["offset"]
    for segment in mapping["segments"]:
        if segment["printed_start"] <= printed <= segment["printed_end"]:
            return segment["pdf_start"] + printed - segment["printed_start"]
    return None


def apply_mapping(draft, mapping):
    """Apply an explicit mapping without guessing uncovered or invalid targets."""
    clean = _mapping(mapping, draft.page_count)
    targets = []
    for entry in draft.entries:
        if entry.printed_page is None:
            targets.append(None)
        else:
            printed = _integer(entry.printed_page, "印刷页码", positive=True)
            target = _mapped(printed, clean)
            targets.append(target if target is not None and 1 <= target <= draft.page_count else None)
    draft.mapping = clean
    for entry, target in zip(draft.entries, targets):
        if entry.printed_page is not None:
            entry.pdf_page = target
            entry.confirmed = False
            entry.confidence = "待确认"
            entry.note = "已按指定映射计算，请核对目标页。" if target else "此印刷页码未被映射覆盖或目标超出 PDF；请校正。"


def to_toc(draft):
    """Serialize only confirmed entries into the existing, strict TOC schema."""
    if not draft.entries:
        raise BookmarkError("目录为空，请先识别或添加条目。")
    mapping = _mapping(draft.mapping, draft.page_count) if draft.mapping is not None else None
    roots, parents = [], []
    previous = 0
    for index, entry in enumerate(draft.entries, 1):
        level = _integer(entry.level, f"第 {index} 项层级", positive=True)
        if level > previous + 1:
            raise BookmarkError(f"第 {index} 项层级跳级；首项须为 1，后续最多增加一级。")
        if not isinstance(entry.title, str) or not entry.title.strip() or "\x00" in entry.title:
            raise BookmarkError(f"第 {index} 项标题不能为空或包含空字符。")
        target = _integer(entry.pdf_page, f"第 {index} 项 PDF 页", positive=True)
        if target > draft.page_count:
            raise BookmarkError(f"第 {index} 项目标超出 PDF 的 {draft.page_count} 页。")
        if entry.confirmed is not True:
            raise BookmarkError(f"第 {index} 项“{entry.title}”尚未确认，请校对后确认。")
        printed = entry.printed_page
        if printed is not None:
            _integer(printed, f"第 {index} 项印刷页码", positive=True)
        node = {"title": entry.title.strip()}
        if printed is not None and mapping is not None and _mapped(printed, mapping) == target:
            node["page"] = printed
        else:
            node["pdf_page"] = target
        parents = parents[:level - 1]
        if level == 1:
            roots.append(node)
        else:
            parents[-1].setdefault("children", []).append(node)
        parents.append(node)
        previous = level
    result = {"version": 1, "bookmarks": roots}
    if mapping is not None:
        result["mapping"] = mapping
    return result


def save_toc(draft, path):
    """Validate a temporary JSON, then atomically save it; never write the PDF."""
    path = Path(path).expanduser().absolute()
    if path.suffix.lower() != ".json" or path.name.casefold() == "jasminum-outline.json":
        raise BookmarkError("请选择 .json 目录文件；不能覆盖 PDF 或茉莉花缓存。")
    if path.is_symlink() or path.resolve() == draft.pdf_path.resolve():
        raise BookmarkError("目录输出不能是符号链接或原 PDF。")
    if path.exists() and path.samefile(draft.pdf_path):
        raise BookmarkError("目录输出与原 PDF 指向同一文件。")
    if path.is_file():
        with path.open("rb") as stream:
            if stream.read(1024).lstrip().startswith(b"%PDF-"):
                raise BookmarkError("输出文件实际包含 PDF；不能覆盖，请选择新的 JSON 文件名。")
    data = to_toc(draft)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", prefix=".toc-", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        plan = inspect_pdf(draft.pdf_path, temporary)
        if plan.page_count != draft.page_count:
            raise BookmarkError("PDF 页数已变化，请重新识别。")
        os.replace(temporary, path)
        return path
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_draft(pdf_path, toc_path):
    plan = inspect_pdf(pdf_path, toc_path)
    with Path(toc_path).open(encoding="utf-8-sig") as stream:
        data = json.load(stream)
    entries = [DraftEntry(row["level"], row["title"], row["printed_page"], row["pdf_page"], "已导入", "来自已校验的 JSON。", True) for row in plan.preview]
    return Draft(plan.pdf_path, plan.page_count, entries, [], data.get("mapping"), "导入 JSON", [])


def _engine():
    global _OCR
    if _OCR is None:
        try:
            import rapidocr
            models = Path(rapidocr.__file__).parent / "models"
            files = {"Det": "PP-OCRv6_det_small.onnx", "Cls": "ch_ppocr_mobile_v2.0_cls_mobile.onnx", "Rec": "PP-OCRv6_rec_small.onnx"}
            params = {"Global.log_level": "error", "EngineConfig.onnxruntime.intra_op_num_threads": 2, "EngineConfig.onnxruntime.inter_op_num_threads": 1}
            for task, name in files.items():
                model = models / name
                if not model.is_file():
                    raise BookmarkError(f"本地 OCR 模型缺失：{name}。请使用完整安装包；不会联网下载。")
                params[f"{task}.model_path"] = str(model)
            _OCR = rapidocr.RapidOCR(params=params)
        except BookmarkError:
            raise
        except Exception as error:
            raise BookmarkError(f"无法启动本地 OCR，请检查完整安装包：{error}") from error
    return _OCR


def _group_boxes(boxes, *, column_mode="auto", page_width=None, split=None):
    """Keep independent TOC columns separate before joining baseline boxes."""
    if not boxes:
        return []
    if split is not None:
        return _forced_columns(boxes, page_width, split=split)
    if column_mode == "single":
        return _baseline_lines(boxes)
    if column_mode == "double":
        automatic = _group_boxes(boxes)
        if len({line.column for line in automatic if line.right is not None}) == 2:
            return automatic
        return _forced_columns(boxes, page_width)
    ordinary = _baseline_lines(boxes)
    edges = sorted({edge for box in boxes for edge in (box[0], box[2])})
    extent = edges[-1] - edges[0]
    heights = sorted(max(box[3] - box[1], 1) for box in boxes)
    gap = max(heights[len(heights) // 2] * .6, extent * .012)
    candidates = [(a + b) / 2 for a, b in zip(edges, edges[1:])
                  if b - a >= gap and edges[0] + extent * .2 < (a + b) / 2 < edges[0] + extent * .8]
    best = None
    for boundary in candidates:
        left = _baseline_lines([box for box in boxes if box[2] <= boundary],
                               column=0, left=edges[0], right=boundary)
        right = _baseline_lines([box for box in boxes if box[0] >= boundary],
                                column=1, left=boundary, right=edges[-1])
        # A large title-to-page gap is not a column gutter: both sides must
        # contain independently readable titles with their own terminal pages.
        def entries(lines):
            return [line for line in lines if (parsed := _parse([line]))
                    and _normal(parsed[0][0]) not in {"chapter", "part", "section", "subsection", "sec", "appendix", "附录"}
                    and not re.fullmatch(r"[A-Za-z](?:\s*[\^_]\s*[A-Za-z0-9]+)?", parsed[0][0])]

        left_entries, right_entries = entries(left), entries(right)
        if min(len(left_entries), len(right_entries)) < 2:
            continue
        if min(len(left_entries) / max(len(left), 1), len(right_entries) / max(len(right), 1)) < .5:
            continue
        overlap = min(max(line.y for line in left_entries), max(line.y for line in right_entries)) - max(
            min(line.y for line in left_entries), min(line.y for line in right_entries))
        if overlap < heights[len(heights) // 2]:
            continue
        spanning = _baseline_lines([box for box in boxes if box[0] < boundary < box[2]], column=-1)
        first = min(line.y for line in left_entries + right_entries)
        last = max(line.y for line in left_entries + right_entries)
        # A spanning header above the columns is fine; an actual entry crossing
        # the proposed gutter makes this layout ambiguous, so retain one column.
        if any(first <= line.y <= last and _parse([line]) for line in spanning):
            continue
        score = (len(left_entries) + len(right_entries), min(len(left_entries), len(right_entries)))
        if best is None or score > best[0]:
            best = (score, [line for line in spanning if line.y < first] + left + right
                    + [line for line in spanning if line.y >= first])
    return best[1] if best is not None else ordinary


def _forced_columns(boxes, page_width, *, split=None):
    """Use a geometric gutter for the user's explicit two-column choice."""
    left_edge = 0 if page_width is not None else min(box[0] for box in boxes)
    right_edge = page_width if page_width is not None else max(box[2] for box in boxes)
    middle = (left_edge + right_edge) / 2
    left = [box for box in boxes if box[2] <= middle]
    right = [box for box in boxes if box[0] >= middle]
    body = boxes
    if left and right:
        first = max(min(box[1] for box in left), min(box[1] for box in right))
        last = min(max(box[3] for box in left), max(box[3] for box in right))
        if first <= last:
            # Centered headers/footers must not hide an otherwise clear gutter.
            body = [box for box in boxes if box[3] >= first and box[1] <= last]
    occupied = []
    for start, end in sorted((box[0], box[2]) for box in body):
        if occupied and start <= occupied[-1][1]:
            occupied[-1][1] = max(occupied[-1][1], end)
        else:
            occupied.append([start, end])
    extent = right_edge - left_edge
    gutters = [(end + start) / 2 for (_, end), (start, _) in zip(occupied, occupied[1:])
               if left_edge + extent * .2 < (end + start) / 2 < left_edge + extent * .8]
    boundary = split if split is not None else min(gutters, key=lambda value: abs(value - middle)) if gutters else middle
    if split is not None:
        left_boxes = [box for box in boxes if box[2] <= boundary]
        right_boxes = [box for box in boxes if box[0] >= boundary]
        if _parse(_baseline_lines(left_boxes)) and _parse(_baseline_lines(right_boxes)):
            # Keep the user's gutter, but avoid excessive outer whitespace
            # shrinking the column detector enough to miss entire TOC rows.
            left_edge = max(left_edge, min(box[0] for box in left_boxes) - 5)
            right_edge = min(right_edge, max(box[2] for box in right_boxes) + 5)
    left_lines = _baseline_lines([box for box in boxes if box[2] <= boundary],
                                 column=0, left=left_edge, right=boundary)
    right_lines = _baseline_lines([box for box in boxes if box[0] >= boundary],
                                  column=1, left=boundary, right=right_edge)
    spanning = _baseline_lines([box for box in boxes if box[0] < boundary < box[2]], column=-1)
    first = min((line.y for line in left_lines + right_lines), default=float("inf"))
    return ([line for line in spanning if line.y < first] + left_lines + right_lines
            + [line for line in spanning if line.y >= first])


def _baseline_lines(boxes, *, column=0, left=0, right=None):
    """Join title fragments and their page only inside one established column."""
    rows = []
    for x0, y0, x1, y1, text, score in sorted(boxes, key=lambda box: ((box[1] + box[3]) / 2, box[0])):
        middle, height = (y0 + y1) / 2, max(y1 - y0, 1)
        match = next((row for row in reversed(rows[-3:]) if abs(row[0] - middle) <= max(row[1], height) * .48), None)
        if match is None:
            rows.append([middle, height, [(x0, text, score, x1, y0, y1)]])
        else:
            match[2].append((x0, text, score, x1, y0, y1))
            match[1] = max(match[1], height)
    return [_Line(" ".join(part[1] for part in sorted(parts)), min(part[0] for part in parts), middle, height, min(part[2] for part in parts), [(int(match.group(1)), part[0]) for part in parts if (match := _NUM.match(part[1]))], column, left, right,
                  (min(part[0] for part in parts), min(part[4] for part in parts),
                   max(part[3] for part in parts), max(part[5] for part in parts))) for middle, height, parts in rows]


def _clean(text):
    text = re.sub(r"[.．·…⋯_](?:\s*[.．·…⋯_])+", " ", text)
    text = re.sub(r"[.．·…⋯_]\s*$", "", text).strip()
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s+", " ", text)


def _normal(text):
    return re.sub(r"[^\w\u3400-\u9fff]", "", text).casefold()


def _heading_number(text):
    """Read the chapter/section numerals already supported by recognition."""
    if text.isdecimal():
        return int(text)
    digits = dict(zip("零〇一二三四五六七八九", (0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9)))
    if all(char in digits for char in text):
        return int("".join(str(digits[char]) for char in text))
    if all(char in digits or char in "十百" for char in text):
        total, value = 0, 0
        for char in text:
            if char in "十百":
                total += (value or 1) * {"十": 10, "百": 100}[char]
                value = 0
            else:
                value = digits[char]
        return total + value
    words = "one two three four five six seven eight nine ten".split()
    if text.casefold() in words:
        return words.index(text.casefold()) + 1
    if not re.fullmatch(r"[ivxlcdm]+", text, re.I):
        return None
    total, previous = 0, 0
    for char in reversed(text.upper()):
        value = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}[char]
        total += -value if value < previous else value
        previous = max(previous, value)
    return total


_TITLE_NUMERAL = r"[\d一二三四五六七八九十百零〇]+"
_TITLE_PREFIX = re.compile(rf"^(?:第\s*{_TITLE_NUMERAL}\s*(?:小节|章|节|篇|部|卷)|"
                        rf"(?:chapter|part)\s+(?:[\divxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)\b|"
                        rf"(?:section\s+|sec\.\s*)\d+(?:\s*[.．]\s*\d+)*(?![\d.．])|"
                        rf"§?\s*\d+(?:\s*[.．]\s*\d+)+(?![\d.．])|§\s*\d+(?![\d.．])|\d+(?=\s|$)|"
                        rf"[一二三四五六七八九十百]+[、．]|[（(][一二三四五六七八九十百]+[）)])", re.I)


def _spaced_generated_title(title):
    if match := _TITLE_PREFIX.match(title):
        label = match[0].lstrip("§").strip()
        if re.match(r"^(?:chapter|part|section)\b|^sec\.", label, re.I):
            label = re.sub(r"\s+", " ", label)
        else:
            label = re.sub(r"\s+", "", label)
        return (label + " " + title[match.end():].strip()).rstrip()
    return title


def _section_label(title, chapter):
    """Return a reliable direct-section number and its unnumbered title."""
    numbered = re.sub(r"^(?:section\s+|sec\.\s*)", "", title, flags=re.I)
    match = re.match(r"^(\d+(?:[.．]\d+)*)(?:\s+|[.．]\s*|$)(.*)$", numbered)
    if match:
        parts = re.split(r"[.．]", match[1])
        if len(parts) == 1:
            return int(parts[0]), match[2]
        if len(parts) == 2 and int(parts[0]) == chapter:
            return int(parts[1]), match[2]
        return None, None
    match = re.match(rf"^(?:第\s*({_TITLE_NUMERAL})\s*节|([一二三四五六七八九十百]+)[、．])\s*(.*)$", title)
    if match:
        return _heading_number(match[1] or match[2]), match[3]
    return None, None


def section_titles(draft, style="chapter_section", *, source_titles=None):
    """Return automatic-draft title choices without changing its other evidence.

    ``section`` uses a chapter-local ``1. Title``; ``preserve`` keeps the
    recognized labels and only applies the existing spacing/section-sign rule.
    Sources must follow the current entry order; the editor tracks them by entry
    identity so moving, deleting or editing an entry cannot reuse another title.
    Imported/manual drafts have no automatic sources and remain verbatim.
    """
    if style not in ("chapter_section", "section", "preserve"):
        raise BookmarkError("请选择章.节编号、节编号或保持识别编号。")
    sources = draft.source_titles if source_titles is None else source_titles
    if sources is None:
        return [entry.title for entry in draft.entries]
    if len(sources) != len(draft.entries) or any(not isinstance(title, str) for title in sources):
        raise BookmarkError("原始标题与当前目录条目不一致，请重新识别后再选择编号方式。")
    titles = [_spaced_generated_title(title) for title in sources]
    if style == "preserve":
        return titles
    chapter, chapter_level, sequence, reserved = None, 0, 0, set()
    for index, (entry, title) in enumerate(zip(draft.entries, titles)):
        chinese = re.match(rf"^第\s*({_TITLE_NUMERAL})\s*章", title)
        english = _CHAPTER.match(title) if re.match(r"^chapter\b", title, re.I) else None
        if chinese or english:
            chapter = _heading_number(chinese[1] if chinese else english[0].split()[1])
            chapter_level, sequence, reserved = entry.level, 0, set()
            for following, source in zip(draft.entries[index + 1:], titles[index + 1:]):
                if following.level <= chapter_level:
                    break
                if following.level == chapter_level + 1:
                    number, _ = _section_label(source, chapter)
                    if number is not None:
                        reserved.add(number)
        elif entry.level <= chapter_level or _PART.match(title) or _ROOT.match(title) or _FRONT.match(title) or _LEVEL_ROOT.match(title):
            chapter = None
        elif chapter is not None and entry.level == chapter_level + 1:
            number, body = _section_label(title, chapter)
            if number is None:
                # Ambiguous labels and explicit deeper numbering are retained.
                if _TITLE_PREFIX.match(title) or _level(title) != 1:
                    continue
                number, body = sequence + 1, title
                while number in reserved:
                    number += 1
            sequence = max(sequence, number)
            label = f"{chapter}.{number}" if style == "chapter_section" else f"{number}."
            titles[index] = (label + " " + body).rstrip()
    return titles


def _format_generated_titles(draft):
    """Format automatic titles after page evidence, leaving imported titles alone."""
    numeral, prefix = _TITLE_NUMERAL, _TITLE_PREFIX
    if draft.source_titles is None:
        draft.source_titles = [entry.title for entry in draft.entries]

    def section_number(title, chapter):
        numbered = re.sub(r"^(?:section\s+|sec\.\s*)", "", title, flags=re.I)
        match = re.match(r"^(\d+)(?:[.．](\d+))?(?=\s|$)", numbered)
        if match:
            return int(match[2]) if match[2] and int(match[1]) == chapter else (int(match[1]) if not match[2] else None)
        match = re.match(rf"^(?:第\s*({numeral})\s*节|([一二三四五六七八九十百]+)[、．])", title)
        return _heading_number(match[1] or match[2]) if match else None

    for entry in draft.entries:
        entry.title = _spaced_generated_title(entry.title)

    chapter, chapter_level, sequence, reserved = None, 0, 0, set()
    for index, entry in enumerate(draft.entries):
        match = re.match(rf"^第\s*({numeral})\s*章", entry.title)
        english = _CHAPTER.match(entry.title) if re.match(r"^chapter\b", entry.title, re.I) else None
        if match or english:
            chapter = _heading_number(match[1] if match else english[0].split()[1])
            chapter_level, sequence, reserved = entry.level, 0, set()
            # Reserve existing numbers even when they appear after a missing one.
            for following in draft.entries[index + 1:]:
                if following.level <= chapter_level:
                    break
                if following.level == chapter_level + 1:
                    number = section_number(following.title, chapter)
                    if number is not None:
                        reserved.add(number)
        elif entry.level <= chapter_level or _PART.match(entry.title) or _ROOT.match(entry.title) or _FRONT.match(entry.title) or _LEVEL_ROOT.match(entry.title):
            chapter = None
        elif chapter is not None and entry.level == chapter_level + 1:
            number = section_number(entry.title, chapter)
            if number is not None:
                sequence = max(sequence, number)
            elif not prefix.match(entry.title) and _level(entry.title) == 1:
                sequence += 1
                while sequence in reserved:
                    sequence += 1
                entry.title = f"{chapter}.{sequence} {entry.title}"
                entry.note += " 根据章内顺序补充节编号，请核对。"
    return draft


def _level(title):
    if _CHAPTER.match(title) or _FRONT.match(title) or _ROOT.match(title) or _LEVEL_ROOT.match(title):
        return 1
    if re.match(r"^(?:subsection\b|subsec\.|第\s*[\d一二三四五六七八九十百]+\s*小节|[（(][一二三四五六七八九十百]+[）)])", title, re.I):
        return 3
    numbered = re.match(r"^(?:[§S]|section\s+|sec\.\s*)?\s*(\d+(?:\s*[.．]\s*\d+)+)", title, re.I)
    if numbered:
        return min(len(re.split(r"[.．]", numbered.group(1))), 5)
    appendix_number = re.match(r"^[A-Z]((?:[.．]\s*\d+)+)(?:\s|[.．、:]|$)", title)
    if appendix_number:
        return min(appendix_number.group(1).count(".") + appendix_number.group(1).count("．") + 1, 5)
    if re.match(r"^(?:§\s*\d+|第\s*[\d一二三四五六七八九十百]+\s*节|section\b|sec\.|[一二三四五六七八九十百]+[、．])", title, re.I):
        return 2
    return 1


def _hierarchy(parts, layout):
    """Use heading roles across pages; indentation is only a reviewable hint."""
    # Compare indentation only within one page/column and chapter; the semantic
    # chapter context still continues across columns and directory page breaks.
    groups, bases, anchor = [], {}, 0
    for (title, _, _, _), (page, x) in zip(parts, layout):
        if _CHAPTER.match(title) or _FRONT.match(title) or _ROOT.match(title) or _LEVEL_ROOT.match(title):
            anchor += 1
        key = (page, anchor)
        groups.append(key)
        if not (_CHAPTER.match(title) or _FRONT.match(title) or _ROOT.match(title) or _LEVEL_ROOT.match(title)):
            bases[key] = min(bases.get(key, x), x)
    result, previous, part, parent = [], 0, False, None
    for (title, _, _, _), (_, x), group in zip(parts, layout, groups):
        local, note = _level(title), ""
        if _PART.match(title):
            level, part, parent = 1, True, None
        elif _CHAPTER.match(title):
            level = 2 if part else 1
            parent = level
        elif _FRONT.match(title) or _ROOT.match(title) or _LEVEL_ROOT.match(title):
            level, part = 1, False
            parent = 1 if re.match(r"^(?:附录|appendix\b)", title, re.I) else None
        elif local > 1:
            level = local + (parent - 1 if parent is not None else int(part))
        elif parent is not None:
            level = parent + 1
            note = "根据最近的章/附录推断为子目录，请核对层级。"
            if x - bases.get(group, x) >= .035:
                level += 1
                note = "根据章内较深缩进推断为小节，请核对层级。"
        elif part:
            level = 2
            note = "根据最近的篇/部推断为子目录，请核对层级。"
        else:
            level = 1
        level = min(level, 5)
        if level > previous + 1:
            level = previous + 1
            note = "未识别到完整上级标题，已避免层级跳级；请核对层级。"
        result.append((level, note))
        previous = level
    return result


def _parse(lines, *, layout=None, sources=None):
    parsed = []
    pending = ""
    pending_x = None
    pending_rect = None
    pending_line = None
    column = None
    for line in lines:
        if line.column != column:
            pending, pending_x, pending_rect, column = "", None, None, line.column
        if pending_line is not None and line.y - pending_line.y > max(line.height, pending_line.height) * 2:
            pending = ""
        raw = line.text.strip()
        # A detected label alone is not a title followed by a terminal page.
        if _BARE_SECTION.fullmatch(raw):
            pending, pending_x, pending_rect, pending_line = _clean(raw), line.x, line.rect, line
            continue
        heading = _CHAPTER.match(raw)
        if heading and not raw[heading.end():].strip():
            pending, pending_x = _clean(raw), line.x
            pending_rect = line.rect
            pending_line = line
            continue
        match = _PAGE.match(raw)
        if not match:
            if ((_CHAPTER.match(raw) or re.match(r"^[§S]?\s*\d+[.．]\d+", raw))
                    and not re.search(r"[.．·…⋯_](?:\s*[.．·…⋯_]){2}", raw)):
                pending = _clean(raw)
                pending_x = line.x
                pending_rect = line.rect
                pending_line = line
            else:
                pending = ""
            continue
        title = _clean(match.group(1))
        if not title or _normal(title) in {"目录", "contents", "tableofcontents"} or _NUM.match(title) or _BARE_SECTION.fullmatch(title):
            continue
        x = line.x
        rect = line.rect
        label_only = _CHAPTER.fullmatch(pending) or _BARE_SECTION.fullmatch(pending)
        independent = not label_only and (_ROOT.fullmatch(title) or _FRONT.fullmatch(title)
                                           or _LEVEL_ROOT.fullmatch(title))
        if pending and not (_CHAPTER.match(title) or independent or re.match(r"^[§S]?\s*\d+[.．]\d+", title)):
            title = pending + " " + title
            x = pending_x
            rect = (tuple(pymupdf.Rect(pending_rect) | pymupdf.Rect(rect))
                    if pending_rect is not None and rect is not None else None)
        pending = ""
        page_text = match.group(2)
        printed = int(page_text) if page_text.isdecimal() and int(page_text) > 0 else None
        parsed.append((title, printed, line.score, page_text))
        if layout is not None:
            layout.append((line.column, x, line.left, line.right))
        if sources is not None:
            sources.append(rect)
    return parsed


def _looks_toc(lines, parsed):
    header = any(_normal(line.text) in {"目录", "目", "contents", "tableofcontents"} for line in lines)
    numbered = sum(bool(_CHAPTER.match(title) or re.match(r"^[§S]?\s*\d+[.．]\d+", title)) for title, _, _, _ in parsed)
    return (header and len(parsed) >= 2) or (len(parsed) >= 5 and numbered >= 3)


def _title_crop(image, line):
    """Find a repeated pixel dot leader without guessing the title width."""
    import cv2

    height = line.height
    crop = image[max(0, int(line.y - height / 2) - 5):int(line.y + height / 2) + 5,
                 max(0, int(line.x) - 5):int(line.right) if line.right is not None else image.shape[1]]
    if not crop.size:
        return None
    _, ink = cv2.threshold(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY), 0, 255,
                          cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    _, _, stats, centers = cv2.connectedComponentsWithStats(ink, 8)
    dots = sorted([(stat, center) for stat, center in zip(stats[1:], centers[1:])
                   if stat[2] <= height * .2 and stat[3] <= height * .2
                   and 2 <= stat[4] <= height * height * .04], key=lambda item: item[0][0])
    runs, run = [], []
    for dot in dots:
        if run and not (abs(dot[1][1] - run[-1][1][1]) < height * .15
                        and 0 < dot[1][0] - run[-1][1][0] < height * .7):
            if len(run) >= 6:
                runs.append(run)
            run = []
        run.append(dot)
    if len(run) >= 6:
        runs.append(run)
    end = int(max(runs, key=len)[0][0][0]) - 1 if runs else 0
    return crop[:, :end] if end > height else None


def _ocr_label(text):
    match = _CHAPTER.match(text) or re.match(
        r"^(?:[§S]?\s*\d+(?:\s*[.．]\s*\d+)*|"
        r"第\s*[\d一二三四五六七八九十百零〇]+\s*(?:小节|节)|"
        r"(?:section|subsection|sec\.)\s*\d+(?:\s*[.．]\s*\d+)*|"
        r"[一二三四五六七八九十百]+[、．]|[（(][一二三四五六七八九十百]+[）)])", text, re.I)
    if match:
        return re.sub(r"^[§S](?=\s*\d)|\s+", "", match[0]).replace("．", ".").casefold()


def _refine_ocr_titles(pix, lines, engine, cancel):
    """Re-read image-backed short titles, retaining the original page numbers."""
    from difflib import SequenceMatcher
    import numpy as np

    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    candidates = []
    for line in lines:
        _cancelled(cancel)
        parsed = _parse([line])
        if parsed and (crop := _title_crop(image, line)) is not None:
            candidates.append((line, parsed[0][0], _PAGE.match(line.text)[2], crop))
    if not candidates:
        return
    _cancelled(cancel)
    crops, _ = engine.cls_and_rotate([item[3] for item in candidates])
    _cancelled(cancel)
    result = engine.recognize_txt(crops)
    _cancelled(cancel)
    if result.txts is None or result.scores is None:
        return
    for (line, old_title, page, _), text, score in zip(candidates, result.txts, result.scores):
        title = _clean(text)
        old_key, key = _normal(old_title), _normal(title)
        old_label = _ocr_label(old_title)
        if old_label is not None and _ocr_label(title) != old_label:
            continue
        if (title and not _NUM.match(title) and len(key) >= len(old_key)
                and score >= max(.92, line.score) and SequenceMatcher(None, old_key, key).ratio() >= .7):
            line.text = f"{title} {page}"


def _same_ocr_entry(original, candidate):
    """An extra OCR pass must agree with existing text, labels, and page ink."""
    from difflib import SequenceMatcher

    parsed = _parse([candidate])
    number = _NUM.match(re.sub(r"[.．·…⋯_]", " ", original.text))
    if number:
        return bool(parsed) and parsed[0][1] == int(number[1])
    label = _ocr_label(original.text)
    if label is not None and _ocr_label(candidate.text) != label:
        return False
    old = _normal(_clean(original.text))
    new = _normal(parsed[0][0] if parsed else _clean(candidate.text))
    return bool(old and new) and (SequenceMatcher(None, old, new).ratio() >= .7 or old in new or new in old)


def _merge_ocr_lines(original, additional):
    """Keep complete original rows; add independently detected missing rows."""
    result = list(original)
    for line in additional:
        match = min((old for old in result if abs(old.y - line.y) <= max(old.height, line.height) * .6),
                    key=lambda old: abs(old.y - line.y), default=None)
        if match is None:
            result.append(line)
        elif (not _parse([match]) and _same_ocr_entry(match, line)
              and (_parse([line]) or len(_normal(line.text)) > len(_normal(match.text)))):
            line.score = min(match.score, line.score)
            result[result.index(match)] = line
    return sorted(result, key=lambda line: line.y)


def _recover_ocr_rows(image, lines, engine, cancel):
    """Retry incomplete column rows without inventing a page or changing labels."""
    import cv2

    missing = [line for line in lines if line.right is not None and not _parse([line])]
    crops = [image[max(0, int(line.y - line.height * .8)):int(line.y + line.height * .8),
                   max(0, int(line.left) - 5):int(line.right)] for line in missing]
    if not crops:
        return
    _cancelled(cancel)
    result = engine.recognize_txt(crops)
    _cancelled(cancel)
    if result.txts is None or result.scores is None:
        return
    for line, crop, text, score in zip(missing, crops, result.txts, result.scores):
        _cancelled(cancel)
        candidate = _Line(str(text), line.x, line.y, line.height, float(score),
                          column=line.column, left=line.left, right=line.right)
        if not _parse([candidate]) or score < .7 or not _same_ocr_entry(line, candidate):
            continue
        # A number-only detection has no title position. Recover its ink start
        # from this same row, otherwise it would look like a deeply nested item.
        _, ink = cv2.threshold(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY), 0, 255,
                              cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        _, _, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
        starts = [stat[0] for stat in stats[1:] if stat[3] >= line.height * .25 and stat[4] >= 3]
        if starts:
            candidate.x = float(max(0, int(line.left) - 5) + min(starts))
        candidate.score = min(line.score, candidate.score)
        candidate.rect = (candidate.x, max(0, line.y - line.height * .8),
                          min(image.shape[1], line.right), min(image.shape[0], line.y + line.height * .8))
        lines[lines.index(line)] = candidate


def _recover_leader_rows(pix, lines, engine, cancel):
    """Read title/page ink separately where a long dotted leader joins them.

    Dot components locate actual rows, including rows missed by text detection.
    Existing column boundaries and complete readings are retained; no page or
    heading is supplied from numbering order or another row.
    """
    import cv2
    import numpy as np
    from difflib import SequenceMatcher

    _cancelled(cancel)
    if not lines:
        return lines
    heights = sorted(line.height for line in lines)
    height = heights[len(heights) // 2]
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    _, ink = cv2.threshold(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), 0, 255,
                          cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    dots = [index for index, box in enumerate(stats[1:], 1)
            if box[2] <= height * .25 and box[3] <= height * .25 and 2 <= box[4] <= height * height * .06]
    if not dots:
        return lines
    mask = np.isin(labels, dots).astype(np.uint8) * 255
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                             np.ones((max(1, int(height * .12)), max(3, int(height * .7))), np.uint8))
    _, _, runs, _ = cv2.connectedComponentsWithStats(closed, 8)
    runs = [box for box in runs[1:] if box[2] >= height * 3 and box[3] < height * .5]
    bounds = sorted({(line.column, line.left, line.right) for line in lines if line.right is not None})
    if not bounds:
        bounds = [(0, 0, pix.width)]
    candidates, crops = [], []

    def trim(x0, y0, x1, y1):
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(pix.width, int(x1)), min(pix.height, int(y1))
        _, _, components, _ = cv2.connectedComponentsWithStats(ink[y0:y1, x0:x1], 8)
        glyphs = [box for box in components[1:]
                  if (box[3] >= height * .25 or box[2] >= height * .35) and box[4] >= 3]
        if not glyphs:
            return None
        a, b = min(box[0] for box in glyphs), min(box[1] for box in glyphs)
        c, d = max(box[0] + box[2] for box in glyphs), max(box[1] + box[3] for box in glyphs)
        pad = max(2, int(height * .12))
        rect = (max(x0, x0 + a - pad), max(y0, y0 + b - pad),
                min(x1, x0 + c + pad), min(y1, y0 + d + pad))
        return image[rect[1]:rect[3], rect[0]:rect[2]], rect

    for column, left, right in bounds:
        column_runs = [box for box in runs if left <= box[0] and box[0] + box[2] <= right]
        # Two independent leaders on one baseline need established columns.
        column_runs = sorted((box for box in column_runs if not any(
            other is not box and abs(float(other[1]) - float(box[1])) < height * .5
            for other in column_runs)), key=lambda box: box[1])
        for index, box in enumerate(column_runs):
            _cancelled(cancel)
            x, y, width, run_height = map(int, box[:4])
            center = y + run_height / 2
            y0 = max(center - height, (float(column_runs[index - 1][1]) + center) / 2 if index else center - height * .8)
            y1 = min(center + height, (float(column_runs[index + 1][1]) + center) / 2 if index + 1 < len(column_runs) else center + height * .8)
            title = trim(left, y0, x + height * .35, y1)
            page = trim(x + width - height * .15, y0, right, y1)
            if title is not None and page is not None:
                candidates.append((column, left, right, title[1], page[1]))
                crops.extend((title[0], page[0]))
    if not crops:
        return lines
    _cancelled(cancel)
    result = engine.recognize_txt(crops)
    _cancelled(cancel)
    if result.txts is None or result.scores is None:
        return lines
    recovered = []
    pairs = zip(candidates, zip(result.txts[::2], result.txts[1::2]),
                zip(result.scores[::2], result.scores[1::2]))
    for (column, left, right, title_rect, page_rect), texts, scores in pairs:
        title, page = (_clean(str(text)) for text in texts)
        score = min(map(float, scores))
        if score < .8 or not re.fullmatch(r"\d{1,5}|[ivxlcdmIVXLCDM]{1,10}", page):
            continue
        rect = tuple(pymupdf.Rect(title_rect) | pymupdf.Rect(page_rect))
        line = _Line(f"{title} {page}", title_rect[0], (rect[1] + rect[3]) / 2,
                     rect[3] - rect[1], score, column=column, left=left, right=right, rect=rect)
        if _parse([line]):
            recovered.append(line)
    if not recovered:
        return lines
    combined = []
    for column, _, _ in bounds:
        original = [line for line in lines if line.column == column]
        additional = [line for line in recovered if line.column == column]
        for line in additional:
            old = min((row for row in original if abs(row.y - line.y) <= max(row.height, line.height) * .6),
                      key=lambda row: abs(row.y - line.y), default=None)
            parsed = _parse([old]) if old is not None else []
            current = _parse([line])[0]
            old_key = _normal(parsed[0][0]) if parsed else ""
            key = _normal(current[0])
            # A reliable same-image reread can repair a low-score full row,
            # but must agree on its label and page, retaining the confidence cap.
            if (parsed and old.score < .8 and line.score >= .92 and parsed[0][1] == current[1]
                    and _ocr_label(parsed[0][0]) == _ocr_label(current[0])
                    and not (key != old_key and key in old_key)
                    and SequenceMatcher(None, old_key, key).ratio() >= .85):
                line.score = min(old.score, line.score)
                line.x, line.y, line.height, line.rect = old.x, old.y, old.height, old.rect
                original[original.index(old)] = line
        combined.extend(_merge_ocr_lines(original, additional))
    columns = {column for column, _, _ in bounds}
    spanning = [line for line in lines if line.column not in columns]
    first = min(line.y for line in combined)
    return ([line for line in spanning if line.y < first] + combined
            + [line for line in spanning if line.y >= first])


def _ocr_lines(pix, cancel=None, *, column_mode="auto", split=None):
    """Compare TOC orientations; long leaders can fool the angle classifier."""
    engine = _engine()
    original_cls = engine.use_cls
    image = pix.tobytes("png")

    def recognize(use_cls, crop=None, *, start=0, column=0, left=0, right=None):
        _cancelled(cancel)
        output = engine(image if crop is None else crop, use_cls=use_cls)
        if output.boxes is None or output.txts is None:
            return []
        boxes = [
            (float(min(box[:, 0])) + start, float(min(box[:, 1])), float(max(box[:, 0])) + start,
             float(max(box[:, 1])), str(text), float(score))
            for box, text, score in zip(output.boxes, output.txts, output.scores)
        ]
        if crop is None:
            return (_group_boxes(boxes) if column_mode == "auto" and split is None else
                    _group_boxes(boxes, column_mode=column_mode, page_width=pix.width, split=split))
        return _baseline_lines(boxes, column=column, left=left, right=right)

    def quality(lines):
        parsed = _parse(lines)
        return len(parsed), sum(score for _, _, score, _ in parsed)

    try:
        lines = recognize(True)
        leaders = sum(bool(re.search(r"[.．·…⋯](?:\s*[.．·…⋯]){3}", line.text)) for line in lines)
        if column_mode == "double" or split is not None or _looks_toc(lines, _parse(lines)) or leaders >= 2:
            upright = recognize(False)
            if quality(upright) > quality(lines):
                lines = upright
            bounds = sorted({(line.column, line.left, line.right) for line in lines if line.right is not None})
            if (column_mode == "double" or split is not None) and len(bounds) != 2:
                boundary = split if split is not None else pix.width / 2
                bounds = [(0, 0, boundary), (1, boundary, pix.width)]
            if len(bounds) == 2:
                import numpy as np
                pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                columns = []
                for column, left, right in bounds:
                    margin = 0 if split is not None else 5
                    start = max(0, int(left) - margin)
                    crop = pixels[:, start:min(pix.width, int(right) + margin)]
                    variants = [recognize(use_cls, crop, start=start, column=column, left=left, right=right)
                                for use_cls in (True, False)]
                    columns.extend(_merge_ocr_lines([line for line in lines if line.column == column],
                                                    max(variants, key=quality)))
                _recover_ocr_rows(pixels, columns, engine, cancel)
                if columns:
                    first = min(line.y for line in columns)
                    spanning = [line for line in lines if line.right is None]
                    if split is not None:
                        # Two independently recovered rows supersede an old OCR
                        # box that merged both sides of the user's separator.
                        spanning = [line for line in spanning if not all(any(
                            row.column == column and abs(row.y - line.y) <= max(row.height, line.height) * .6
                            and _parse([row]) for row in columns) for column in (0, 1))]
                    lines = ([line for line in spanning if line.y < first] + columns
                             + [line for line in spanning if line.y >= first])
            _refine_ocr_titles(pix, lines, engine, cancel)
            lines = _recover_leader_rows(pix, lines, engine, cancel)
        return lines
    finally:
        # RapidOCR call options persist on its singleton; keep later pages safe.
        engine.use_cls = original_cls


def _page_regions(value, count):
    """Validate page-local display coordinates without changing caller data."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise BookmarkError("目录识别区域须按实际 PDF 页码指定。")
    result = {}
    for number, options in value.items():
        if type(number) is not int or not 1 <= number <= count:
            raise BookmarkError(f"识别区域页码必须在 PDF 的 1–{count} 页之间。")
        if not isinstance(options, dict) or set(options) - {"rect", "split", "mode"}:
            raise BookmarkError("识别区域仅支持 rect、split 和 mode。")
        mode = options.get("mode")
        if "mode" in options and mode not in ("auto", "single", "double"):
            raise BookmarkError("目录栏数须选择自动、单栏或双栏。")
        rect = options.get("rect", (0, 0, 1, 1))
        if (not isinstance(rect, (list, tuple)) or len(rect) != 4
                or any(type(v) not in (int, float) or not 0 <= v <= 1 for v in rect)
                or not (rect[0] < rect[2] and rect[1] < rect[3])):
            raise BookmarkError("识别区域须为 0–1 范围内的有效矩形 [左, 上, 右, 下]。")
        split = options.get("split")
        if "split" in options and (type(split) not in (int, float) or not rect[0] < split < rect[2]):
            raise BookmarkError("人工分栏线须位于识别区域内部，按整页宽度的 0–1 比例指定。")
        result[number] = dict(options)
        if "rect" in options:
            result[number]["rect"] = tuple(rect)
    return result


def _normalized_source(rect, page_rect):
    if rect is None:
        return None
    clipped = pymupdf.Rect(rect) & page_rect
    if clipped.is_empty:
        return None
    return ((clipped.x0 - page_rect.x0) / page_rect.width,
            (clipped.y0 - page_rect.y0) / page_rect.height,
            (clipped.x1 - page_rect.x0) / page_rect.width,
            (clipped.y1 - page_rect.y0) / page_rect.height)


def generate_toc(pdf_path, *, toc_start=None, toc_end=None, offset=None, prefer_existing=False, progress=None, cancel=None, column_mode="auto", page_regions=None):
    """Recognize a reviewable draft without changing the PDF or its caches.

    ``page_regions`` maps actual PDF pages to optional normalized display
    ``rect``, ``split`` and per-page ``mode``. A separator overrides automatic
    layout, but regions never restrict the independent body-page evidence.
    Observed source locations stay in the draft and are not exported to JSON.
    """
    if column_mode not in ("auto", "single", "double"):
        raise BookmarkError("目录栏数须选择自动、单栏或双栏。")
    path = Path(pdf_path).expanduser().absolute()
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise BookmarkError("请选择可读取的 PDF 文件。")
    report = progress if progress is not None else lambda message: None
    _cancelled(cancel)
    with pymupdf.open(path) as doc:
        if not doc.is_pdf or doc.needs_pass or doc.page_count < 1:
            raise BookmarkError("PDF 为空、无法读取或需要密码。")
        count = doc.page_count
        regions = _page_regions(page_regions, count)
        for value, name in ((toc_start, "目录起始页"), (toc_end, "目录结束页")):
            if value is not None and not 1 <= _integer(value, name, positive=True) <= count:
                raise BookmarkError(f"{name} 必须在 PDF 的 1–{count} 页之间。")
        if toc_end is not None and toc_start is None:
            raise BookmarkError("指定目录结束页时须同时指定起始页。")
        if toc_start is not None and toc_end is not None and toc_end < toc_start:
            raise BookmarkError("目录结束页不能早于起始页。")
        if offset is not None:
            _integer(offset, "固定偏移")
        if prefer_existing:
            outline = doc.get_toc()
            if outline:
                entries = [DraftEntry(level, title, None, page if 1 <= page <= count else None, "待确认", "来自已有 PDF 书签，请检查完整性。") for level, title, page in outline]
                return Draft(path, count, entries, [], None, "已有 PDF 书签", ["复用了已有书签；可能不完整，仍需确认。"])

        cache, methods = {}, set()

        def read(number, *, directory=True):
            _cancelled(cancel)
            region = regions.get(number) if directory else None
            key = (number, bool(region))
            if key not in cache:
                report(f"读取 PDF 第 {number}/{count} 页……")
                page = doc[number - 1]
                words = page.get_text("words")
                clip = page.rect
                mode = region.get("mode", column_mode) if region else column_mode
                split = None
                if region:
                    x0, y0, x1, y1 = region.get("rect", (0, 0, 1, 1))
                    clip = pymupdf.Rect(x0 * page.rect.width, y0 * page.rect.height,
                                        x1 * page.rect.width, y1 * page.rect.height)
                    selected = []
                    for a, b, c, d, text, *_ in words:
                        bounds = pymupdf.Rect(a, b, c, d) * page.rotation_matrix
                        if clip.contains(bounds):
                            selected.append((bounds.x0 - clip.x0, bounds.y0 - clip.y0,
                                             bounds.x1 - clip.x0, bounds.y1 - clip.y0, text))
                    words = selected
                    if "split" in region:
                        split = region["split"] * page.rect.width - clip.x0
                useful = "".join(str(word[4]) for word in words)
                if len(useful) >= 8 and useful.count("�") < len(useful) * .1 and not (region and page.rotation):
                    boxes = [(a, b, c, d, str(text), 1.0) for a, b, c, d, text, *_ in words]
                    lines = (_group_boxes(boxes) if mode == "auto" and split is None else
                             _group_boxes(boxes, column_mode=mode, page_width=clip.width, split=split))
                    width, height = page.rect.width, page.rect.height
                    for line in lines:
                        if region:
                            line.x += clip.x0
                            line.y += clip.y0
                            line.left += clip.x0
                            line.numbers = [(number, x + clip.x0) for number, x in line.numbers]
                            if line.right is not None:
                                line.right += clip.x0
                            bounds = (pymupdf.Rect(line.rect) + (clip.x0, clip.y0, clip.x0, clip.y0)
                                      if line.rect is not None else None)
                        else:
                            bounds = pymupdf.Rect(line.rect) * page.rotation_matrix if line.rect is not None else None
                        line.rect = _normalized_source(bounds, page.rect)
                    methods.add("文字提取")
                else:
                    report(f"本地 OCR：PDF 第 {number}/{count} 页……")
                    scale = min(4.0, 1900 / max(page.rect.width, page.rect.height))
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False,
                                          **({"clip": clip} if region else {}))
                    if pix.width < 1 or pix.height < 1:
                        raise BookmarkError("识别区域过小，请扩大后再试。")
                    split_pixels = region["split"] * page.rect.width * scale - pix.x if split is not None else None
                    lines = (_ocr_lines(pix, cancel) if mode == "auto" and split_pixels is None else
                             _ocr_lines(pix, cancel, column_mode=mode, **({"split": split_pixels} if split_pixels is not None else {})))
                    width, height = pix.width, pix.height
                    for line in lines:
                        bounds = (tuple((value + (pix.x if index % 2 == 0 else pix.y)) / scale
                                        for index, value in enumerate(line.rect)) if line.rect is not None else None)
                        line.rect = _normalized_source(bounds, page.rect)
                        if region:
                            line.x, line.y = (line.x + pix.x) / scale, (line.y + pix.y) / scale
                            line.height /= scale
                            line.left = (line.left + pix.x) / scale
                            line.numbers = [(number, (x + pix.x) / scale) for number, x in line.numbers]
                            if line.right is not None:
                                line.right = (line.right + pix.x) / scale
                    if region:
                        width, height = page.rect.width, page.rect.height
                    methods.add("本地 OCR")
                _cancelled(cancel)
                cache[key] = (lines, width, height)
            return cache[key]

        toc_pages, parts, layout, locations = [], [], [], []
        first = toc_start
        if first is None:
            for number in range(1, min(count, 25) + 1):
                lines, _, _ = read(number)
                parsed = _parse(lines)
                if _looks_toc(lines, parsed):
                    first = number
                    break
        if first is None:
            raise BookmarkError("前 25 页未找到可识别目录。请指定目录起止 PDF 页后再试，或导入已有 toc.json。")
        end = toc_end if toc_end is not None else min(count, first + 14)
        for number in range(first, end + 1):
            lines, width, _ = read(number)
            page_layout, source_rects = [], []
            parsed = _parse(lines, layout=page_layout, sources=source_rects)
            numbered = sum(bool(_CHAPTER.match(title) or re.match(r"^[§S]?\s*\d+[.．]\d+", title)) for title, _, _, _ in parsed)
            continuation = parsed and (numbered >= 2 or any(_ROOT.match(title) for title, _, _, _ in parsed) or _looks_toc(lines, parsed))
            if toc_end is None and number > first and not continuation:
                break
            toc_pages.append(number)
            parts.extend(parsed)
            locations.extend((number, rect) for rect in source_rects)
            layout.extend(((number, column), (x - left) / (right - left) if right is not None else x / width)
                          for column, x, left, right in page_layout)
        if not parts:
            raise BookmarkError("指定页未识别出标题和页码，请检查目录页范围或使用手工编辑。")
        entries = [DraftEntry(1, "目录", None, first, "高", "目录起始 PDF 页。")]
        seen, notes = set(), ["自动识别结果均未确认；请检查标题、层级与目标页后再导出或写入。"]
        for (title, printed, score, page_text), (level, hierarchy_note), (number, source_rect) in zip(parts, _hierarchy(parts, layout), locations):
            key = (title, printed)
            if key in seen:
                continue
            seen.add(key)
            entry = DraftEntry(level, title, printed, confidence="中" if score >= .92 else "低", note="文字提取标题，需检查。" if score == 1.0 else f"OCR 标题分数 {score:.2f}，需检查错字。")
            if source_rect is not None:
                entry.source_page, entry.source_rect = number, source_rect
            if hierarchy_note:
                entry.note += " " + hierarchy_note
            if printed is None:
                entry.note += f" 非阿拉伯或无效印刷页码 {page_text!r}，请指定实际 PDF 页。"
            if _FRONT.match(title):
                entry.printed_page = None
                entry.note += f" 前置部分的 {page_text} 可能另起页码，不套用正文偏移。"
                target = next((number for number in range(1, first) if any(_normal(line.text) == _normal(title) for line in read(number, directory=False)[0])), None)
                entry.pdf_page = target
            entries.append(entry)
        draft = Draft(path, count, entries, toc_pages, None, " + ".join(sorted(methods)), notes)

        def generated_mapping(mapping):
            evidence = [(entry.confidence, entry.note) for entry in entries]
            apply_mapping(draft, mapping)
            for entry, (confidence, note) in zip(entries, evidence):
                if entry.printed_page is not None:
                    entry.confidence = confidence if entry.pdf_page is not None else "待确认"
                    entry.note = note + " " + entry.note

        if offset is not None:
            generated_mapping({"offset": offset})
            notes.append("使用用户指定固定偏移；仍须检查中途缺页或插页。")
            return _format_generated_titles(draft)

        def footer(number):
            lines, width, height = read(number, directory=False)
            numbers = []
            for line in lines:
                if line.y < height * .12 or line.y > height * .88:
                    if match := _NUM.match(line.text):
                        numbers.append(int(match.group(1)))
                    else:
                        numbers.extend(value for value, x in line.numbers if x < width * .2 or x > width * .7)
            return list(dict.fromkeys(numbers))

        votes = []
        for number in range(toc_pages[-1] + 1, min(count, toc_pages[-1] + 7) + 1):
            values = footer(number)
            if len(values) == 1:
                votes.append(number - values[0])
        counts = Counter(votes)
        candidates = counts.most_common()
        if not candidates or candidates[0][1] < 2 or (len(candidates) > 1 and candidates[1][1] == candidates[0][1]):
            notes.append("未找到至少两页一致的正文页码证据，请输入固定偏移或分段映射。")
            return _format_generated_titles(draft)
        suggested = candidates[0][0]
        printed_entries = [entry for entry in entries if entry.printed_page is not None]
        if not printed_entries:
            notes.append("目录未包含可用于正文映射的阿拉伯页码，请逐项指定实际 PDF 页。")
            return _format_generated_titles(draft)
        sample_indices = sorted({round(index * (len(printed_entries) - 1) / 5) for index in range(6)})
        verified, conflicts = [], []
        for index in sample_indices:
            entry = printed_entries[index]
            target = entry.printed_page + suggested
            if not 1 <= target <= count:
                conflicts.append(f"{entry.title} 推算目标超出范围")
                continue
            lines = read(target, directory=False)[0]
            numbers = footer(target)
            title_key = _normal(entry.title)
            heading = any(title_key and (title_key in _normal(line.text) or _normal(line.text) in title_key and len(_normal(line.text)) >= 5) for line in lines[:12])
            if entry.printed_page in numbers or heading:
                verified.append((entry, target))
            elif numbers and entry.printed_page not in numbers:
                conflicts.append(f"印刷 {entry.printed_page} 页的预计 PDF {target} 页，页眉/脚为 {numbers}")
        if conflicts:
            notes.append("发现页码不一致，可能有缺页、插页或页码重启；请使用分段映射。" + "；".join(conflicts))
            for entry, target in verified:
                entry.pdf_page = target
                entry.note += " 此目标有页码或标题证据，整体映射仍待校正。"
            return _format_generated_titles(draft)
        generated_mapping({"offset": suggested})
        for entry, target in verified:
            if entry.confidence != "低":
                entry.confidence = "高"
            entry.note += " 目标页有独立页码或标题证据；标题仍需校对。"
        notes.append(f"建议固定偏移 {suggested:+d}：正文开头 {counts[suggested]} 页一致，跨目录抽样 {len(verified)} 项有支持证据。未检查每一页。")
        draft.method = " + ".join(sorted(methods))
        return _format_generated_titles(draft)
