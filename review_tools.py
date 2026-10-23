"""Read-only draft review, explicit title edits and local recognition proposals.

These helpers never write a PDF/JSON or modify the supplied draft.  A proposal
is editor-only state, not a change to the published directory JSON schema.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import re

from bookmarks_core import BookmarkError
from toc_generation import (Draft, DraftEntry, _CHAPTER, _FRONT, _LEVEL_ROOT, _PART,
                            _ROOT, _heading_number, _level, _mapped, _mapping,
                            _spaced_generated_title, apply_mapping, section_titles)


@dataclass(frozen=True)
class ReviewIssue:
    index: int | None
    severity: str
    category: str
    code: str
    message: str


@dataclass(frozen=True)
class MappingSample:
    index: int
    title: str
    before: int | None
    after: int | None
    was_confirmed: bool


@dataclass(frozen=True)
class MappingPreview:
    changed: int
    needs_review: int
    uncovered: int
    out_of_range: int
    samples: tuple[MappingSample, ...]


@dataclass(frozen=True)
class TitleChange:
    index: int
    before: str
    after: str


@dataclass(frozen=True)
class RecognitionRecord:
    id: str
    kind: str
    existing_indices: tuple[int, ...]
    candidate_index: int | None
    before: DraftEntry | None
    after: DraftEntry | None
    protected: bool
    source_page: int
    source_rect: tuple[float, float, float, float] | None
    insert_before: int | None = None
    message: str = ""
    parent_id: str | None = None
    source_title: str | None = None


@dataclass(frozen=True)
class RecognitionDiff:
    records: tuple[RecognitionRecord, ...]
    source_page: int
    source_rect: tuple[float, float, float, float] | None
    base_entries: tuple[DraftEntry, ...]
    pdf_path: object
    page_count: int
    mapping: dict | None
    base_source_titles: tuple[str, ...] | None = None


def _positive(value):
    return type(value) is int and value > 0


def hierarchy_issues(entries):
    """Return all structural save blockers, using the serializer's level rule."""
    issues, previous = [], 0
    for index, entry in enumerate(entries):
        if not _positive(entry.level):
            issues.append(ReviewIssue(index, "error", "hierarchy", "invalid_level", "层级必须是正整数。"))
            previous = 0
        else:
            if entry.level > previous + 1:
                issues.append(ReviewIssue(index, "error", "hierarchy", "level_jump",
                    "层级跳级：首项须为 1，后续最多增加一级。"))
            previous = entry.level
    return issues


def _parents(entries):
    stack, parents = [], []
    for index, entry in enumerate(entries):
        if not _positive(entry.level):
            parents.append(None)
            stack.clear()
            continue
        while stack and entries[stack[-1]].level >= entry.level:
            stack.pop()
        parents.append(stack[-1] if stack and entries[stack[-1]].level == entry.level - 1 else None)
        stack.append(index)
    return parents


_SECTION_NUMBER = re.compile(r"^\s*(?:§\s*)?(\d+(?:\s*[.．]\s*\d+)*)(?:\s+|[.．](?!\s*\d)\s*)(\S.*)$")
_SPECIAL_ROOT = re.compile(r"^(?:目录|前言|序言|序|致谢|附录|索引|参考文献|符号表|习题解答|"
                           r"contents\b|preface\b|foreword\b|appendix\b|index\b|references\b)", re.I)


def diagnose_draft(draft, *, numbering_style=None):
    """List blockers separately from conservative, non-correcting warnings.

    Number gaps are compared only between siblings with the same number prefix.
    Each chapter starts a new sequence; special front/back matter is excluded
    from numbering/page-order hints.  No missing title or number is invented.
    """
    if numbering_style not in (None, "chapter_section", "section", "preserve"):
        raise BookmarkError("请选择章.节编号、节编号或保持识别编号。")
    issues = hierarchy_issues(draft.entries)
    if not draft.entries:
        issues.append(ReviewIssue(None, "error", "hierarchy", "empty_directory", "目录为空，请先识别或添加条目。"))
    # Reuse validation rather than maintaining a second segment-map contract.
    if draft.mapping is not None:
        try:
            _mapping(draft.mapping, draft.page_count)
        except BookmarkError as error:
            issues.append(ReviewIssue(None, "error", "page", "invalid_mapping", str(error)))
    parents = _parents(draft.entries)
    duplicate, sequence = {}, {}
    root, previous_page = None, None
    special = False
    for index, entry in enumerate(draft.entries):
        title_valid = isinstance(entry.title, str) and bool(entry.title.strip()) and "\x00" not in entry.title
        if not title_valid:
            issues.append(ReviewIssue(index, "error", "title", "invalid_title", "标题不能为空或包含空字符。"))
        if entry.pdf_page is None:
            issues.append(ReviewIssue(index, "error", "page", "unknown_target", "目标 PDF 页未知，请校正。"))
        elif not _positive(entry.pdf_page):
            issues.append(ReviewIssue(index, "error", "page", "invalid_target", "目标 PDF 页必须是正整数。"))
        elif entry.pdf_page > draft.page_count:
            issues.append(ReviewIssue(index, "error", "page", "target_out_of_range",
                f"目标超出 PDF 的 {draft.page_count} 页。"))
        if entry.printed_page is not None and not _positive(entry.printed_page):
            issues.append(ReviewIssue(index, "error", "page", "invalid_printed_page", "印刷页码必须是正整数或留空。"))
        if entry.confirmed is not True:
            issues.append(ReviewIssue(index, "error", "confirmation", "unconfirmed", "尚未人工确认，请校对后确认。"))
        if entry.level == 1:
            root, previous_page = index, None
            special = bool(title_valid and _SPECIAL_ROOT.match(entry.title.strip()))
        if not title_valid:
            continue
        page_key = ("pdf", entry.pdf_page) if _positive(entry.pdf_page) else ("printed", entry.printed_page)
        if _positive(page_key[1]):
            key = (parents[index], entry.title.strip(), page_key)
            if key in duplicate:
                issues.append(ReviewIssue(index, "warning", "title", "possible_duplicate",
                    f"与第 {duplicate[key] + 1} 项同属一个父项、同标题且同页，请核对是否重复。"))
            else:
                duplicate[key] = index
        if not special and root is not None and _positive(entry.pdf_page):
            if previous_page is not None and entry.pdf_page < previous_page[1]:
                issues.append(ReviewIssue(index, "warning", "page", "page_reversal",
                    f"同章目标页比第 {previous_page[0] + 1} 项靠前；可能是映射、排序或正文重新起算，请人工核对。"))
            previous_page = (index, entry.pdf_page)
        if special or not _positive(entry.level) or entry.level == 1:
            continue
        match = _SECTION_NUMBER.match(entry.title)
        if not match:
            continue
        number = tuple(int(part) for part in re.split(r"\s*[.．]\s*", match[1]))
        # A chapter-local '1. Title' is legitimate even after chapter N.
        if numbering_style == "section" and entry.level == 2 and len(number) != 1:
            continue
        key = (parents[index], number[:-1])
        previous = sequence.get(key)
        if previous is not None and number[-1] > previous[1] + 1:
            issues.append(ReviewIssue(index, "warning", "hierarchy", "number_gap",
                f"编号从第 {previous[0] + 1} 项跳到当前项，可能漏节；不会自动补造条目。"))
        sequence[key] = (index, number[-1])
    return issues


def preview_mapping(draft, mapping, *, sample_limit=5):
    """Preview exactly what apply_mapping does; never alter the source draft.

    ``needs_review`` counts previously confirmed entries which lose confirmation,
    including unchanged targets. Entries without a printed page remain intact.
    """
    if type(sample_limit) is not int or sample_limit < 0:
        raise ValueError("样例数量必须是非负整数。")
    mapped = deepcopy(draft)
    apply_mapping(mapped, mapping)
    changed = needs_review = uncovered = out_of_range = 0
    samples = []
    for index, (before, after) in enumerate(zip(draft.entries, mapped.entries)):
        if before.printed_page is None:
            continue
        raw = _mapped(before.printed_page, mapped.mapping)
        changed += before.pdf_page != after.pdf_page
        needs_review += before.confirmed is True
        uncovered += raw is None
        out_of_range += raw is not None and not 1 <= raw <= draft.page_count
        if len(samples) < sample_limit:
            samples.append(MappingSample(index, before.title, before.pdf_page, after.pdf_page, before.confirmed is True))
    return MappingPreview(changed, needs_review, uncovered, out_of_range, tuple(samples))


def _indices(indices, count):
    result = list(indices)
    if any(type(index) is not int or not 0 <= index < count for index in result):
        raise BookmarkError("选择的条目已变化，请重新选择。")
    return sorted(set(result))


def preview_titles(draft, indices, *, find=None, replace="", prefix="", suffix="",
                   remove_prefix="", remove_suffix="", strip=False, collapse_spaces=False):
    """Preview literal edits for explicit selections only, returning changes.

    Order: remove prefix/suffix, literal replacement, whitespace options, then
    add prefix/suffix. No regex substitution, numbering or symbol normalization.
    """
    for value in (replace, prefix, suffix, remove_prefix, remove_suffix):
        if not isinstance(value, str) or "\x00" in value:
            raise BookmarkError("标题编辑内容必须是不含空字符的文字。")
    if find is not None and (not isinstance(find, str) or not find or "\x00" in find):
        raise BookmarkError("查找文字不能为空；不替换时请留为 None。")
    if type(strip) is not bool or type(collapse_spaces) is not bool:
        raise BookmarkError("空白处理选项必须为布尔值。")
    result = []
    for index in _indices(indices, len(draft.entries)):
        before = draft.entries[index].title
        if not isinstance(before, str):
            raise BookmarkError(f"第 {index + 1} 项标题不是文字。")
        after = before
        if remove_prefix and after.startswith(remove_prefix):
            after = after[len(remove_prefix):]
        if remove_suffix and after.endswith(remove_suffix):
            after = after[:-len(remove_suffix)]
        if find is not None:
            after = after.replace(find, replace)
        if strip:
            after = after.strip()
        if collapse_spaces:
            after = re.sub(r"\s+", " ", after)
        after = prefix + after + suffix
        if after != before:
            result.append(TitleChange(index, before, after))
    return result


def _rect(value):
    if value is None:
        return None
    if (not isinstance(value, (tuple, list)) or len(value) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)
            or not 0 <= value[0] < value[2] <= 1 or not 0 <= value[1] < value[3] <= 1):
        raise BookmarkError("来源区域必须是 0–1 范围的有效矩形。")
    return tuple(value)


def _in_region(entry, page, region):
    if entry.source_page != page:
        return False
    rect = _rect(entry.source_rect)
    if rect is None:
        return False
    if region is None:
        return True
    x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    return region[0] <= x <= region[2] and region[1] <= y <= region[3]


def _same_row(left, right):
    """Compare physical rows, keeping left/right columns independent."""
    if left is None or right is None:
        return False
    vertical = max(0, min(left[3], right[3]) - max(left[1], right[1]))
    horizontal = max(0, min(left[2], right[2]) - max(left[0], right[0]))
    return (vertical >= min(left[3] - left[1], right[3] - right[1]) * .5
            and horizontal >= min(left[2] - left[0], right[2] - right[0]) * .3)


def _content(entry):
    return entry.level, entry.title, entry.printed_page, entry.pdf_page


def _manual(entry):
    return entry.confirmed is True or any(word in (entry.confidence + entry.note) for word in ("手工", "人工修改"))


def contextualize_candidates(draft, candidates, *, source_page, source_rect=None,
                             numbering_style="chapter_section"):
    """Restore one-page OCR proposals in the complete draft's chapter context.

    The generator's synthetic directory root is excluded. Unique physical rows
    retain their old levels; new unlabeled rows require a unique neighboring
    level offset. Ambiguous rows lose their source rectangle and cannot be
    accepted automatically. Only candidate titles are formatted; all original
    entries and their original mapping remain untouched.
    """
    if not isinstance(candidates, Draft):
        raise BookmarkError("局部识别候选须为包含原始标题的草稿。")
    if not _positive(source_page) or source_page > draft.page_count:
        raise BookmarkError("请选择有效的目录 PDF 页。")
    if draft.pdf_path != candidates.pdf_path or draft.page_count != candidates.page_count:
        raise BookmarkError("PDF 身份或页数已变化，请重新加载后再生成局部候选。")
    region = _rect(source_rect)
    if (draft.source_titles is not None
            and (len(draft.source_titles) != len(draft.entries)
                 or any(not isinstance(title, str) for title in draft.source_titles))):
        raise BookmarkError("原始标题与当前目录条目不一致，请先恢复草稿来源。")
    if (candidates.source_titles is not None
            and (len(candidates.source_titles) != len(candidates.entries)
                 or any(not isinstance(title, str) for title in candidates.source_titles))):
        raise BookmarkError("候选原始标题与条目不一致。")
    result = deepcopy(candidates)
    retained = [i for i, entry in enumerate(result.entries) if entry.source_page == source_page
                and (entry.source_rect is None or _in_region(entry, source_page, region))]
    result.entries = [result.entries[i] for i in retained]
    result.source_titles = [candidates.source_titles[i] if candidates.source_titles is not None
                            else candidates.entries[i].title for i in retained]
    result.mapping = deepcopy(draft.mapping)
    raw_levels = [entry.level for entry in result.entries]
    scope = [i for i, entry in enumerate(draft.entries) if _in_region(entry, source_page, region)]
    options = {ci: [i for i in scope if _same_row(entry.source_rect, draft.entries[i].source_rect)]
               for ci, entry in enumerate(result.entries)}
    claims = {}
    for ci, matches in options.items():
        if len(matches) == 1:
            claims.setdefault(matches[0], []).append(ci)
    matches = {ci: indices[0] for ci, indices in options.items()
               if len(indices) == 1 and len(claims[indices[0]]) == 1}
    parents = _parents(draft.entries)

    def chapter_at(index):
        while index is not None:
            entry = draft.entries[index]
            title = entry.title.strip()
            chinese = re.match(r"^第\s*([\d一二三四五六七八九十百零〇]+)\s*章", title)
            english = re.match(r"^chapter\s+(\w+)", title, re.I)
            if chinese or english:
                return entry.level, _heading_number((chinese or english)[1])
            index = parents[index]
        return None

    def uncertain(entry, reason):
        entry.source_rect = None
        entry.note += " 局部层级待人工定位：" + reason

    for ci, (entry, raw) in enumerate(zip(result.entries, result.source_titles)):
        if ci in matches:
            entry.level = draft.entries[matches[ci]].level
            continue
        if options[ci]:
            uncertain(entry, "来源行不能唯一匹配。")
            continue
        anchors = sorted(matches, key=lambda other: (abs(other - ci), other))
        contexts = [chapter_at(matches[other]) for other in anchors[:2]]
        contexts = [context for context in contexts if context is not None]
        context = contexts[0] if contexts and len(set(contexts)) == 1 else None
        if _PART.match(raw) or _FRONT.match(raw) or _ROOT.match(raw) or _LEVEL_ROOT.match(raw):
            entry.level = 1
        elif _CHAPTER.match(raw):
            entry.level = context[0] if context else 1
        elif (intrinsic := _level(raw)) > 1 or _SECTION_NUMBER.match(raw):
            number = _SECTION_NUMBER.match(raw)
            parts = tuple(int(part) for part in re.split(r"\s*[.．]\s*", number[1])) if number else ()
            if context and len(parts) > 1 and parts[0] != context[1]:
                uncertain(entry, "节编号与相邻已知章节不一致。")
            elif context:
                entry.level = (intrinsic if intrinsic > 1 else 2) + context[0] - 1
            elif intrinsic > 1:
                entry.level = intrinsic
            else:
                uncertain(entry, "单个节号缺少明确上级章节。")
        else:
            offsets = {draft.entries[matches[other]].level - raw_levels[other]
                       for other in anchors if raw_levels[other] == raw_levels[ci]}
            if len(offsets) == 1 and _positive(raw_levels[ci] + next(iter(offsets))):
                entry.level = raw_levels[ci] + next(iter(offsets))
            else:
                uncertain(entry, "无编号条目缺少一致的相邻层级锚点。")
    if draft.mapping is not None:
        evidence = [(entry.confidence, entry.note) for entry in result.entries]
        apply_mapping(result, draft.mapping)
        for entry, (confidence, note) in zip(result.entries, evidence):
            entry.confidence = confidence if entry.pdf_page is not None else "待确认"
            entry.note = note + " 已按原草稿映射核对候选目标；仍须人工确认。"
    else:
        for ci, entry in enumerate(result.entries):
            old = draft.entries[matches[ci]] if ci in matches else None
            entry.pdf_page = old.pdf_page if old is not None and old.printed_page == entry.printed_page else None
    for entry in result.entries:
        entry.confirmed = False
    # A temporary complete context reserves old explicit numbers, including
    # chapters on other TOC pages. It is never returned as the current draft.
    proposal = diff_recognition(draft, result, source_page=source_page, source_rect=region)
    working = deepcopy(draft)
    sources = {id(entry): source for entry, source in zip(working.entries,
        draft.source_titles if draft.source_titles is not None else [entry.title for entry in draft.entries])}
    additions = {}
    unchanged = {}
    prior_formatted = section_titles(draft, numbering_style,
        source_titles=draft.source_titles if draft.source_titles is not None else [entry.title for entry in draft.entries])
    for record in proposal.records:
        if record.candidate_index is None:
            continue
        ci = record.candidate_index
        entry = result.entries[ci]
        if record.kind in ("existing", "change"):
            index = record.existing_indices[0]
            old = draft.entries[index]
            raw_old = draft.source_titles[index] if draft.source_titles is not None else old.title
            if (_spaced_generated_title(raw_old) == _spaced_generated_title(result.source_titles[ci])
                    and (old.level, old.printed_page, old.pdf_page) == (entry.level, entry.printed_page, entry.pdf_page)
                    and old.title == prior_formatted[index]):
                # Keep equivalent generated formatting, never a later manual
                # rename: protection is an adoption rule, not replacement of
                # the actual OCR text shown in the comparison.
                unchanged[ci] = old.title
            working.entries[index] = entry
        elif record.kind == "new":
            additions.setdefault(record.insert_before, []).append((ci, entry))
        else:
            continue
        sources[id(entry)] = result.source_titles[ci]
    assembled = []
    for index in range(len(working.entries) + 1):
        assembled.extend(entry for _, entry in sorted(additions.get(index, ())))
        if index < len(working.entries):
            assembled.append(working.entries[index])
    working.entries = assembled
    titles = section_titles(working, numbering_style, source_titles=[sources[id(entry)] for entry in assembled])
    candidate_ids = {id(entry): ci for ci, entry in enumerate(result.entries)}
    for entry, title in zip(assembled, titles):
        ci = candidate_ids.get(id(entry))
        if ci is not None:
            entry.title = unchanged.get(ci, title)
    return result


def diff_recognition(draft, candidates, *, source_page, source_rect=None, protected_indices=()):
    """Compare a local OCR pass without replacing existing or missing entries.

    A unique physical row is the primary match; exact title plus target/printed
    page breaks geometric ties only when unique on both sides. No fuzzy title
    match is used. Unknown sources and uncertain insertion parents are explicit
    ambiguous records, which cannot be accepted by merge_recognition.
    """
    if not _positive(source_page) or source_page > draft.page_count:
        raise BookmarkError("请选择有效的目录 PDF 页。")
    region = _rect(source_rect)
    protected = set(_indices(protected_indices, len(draft.entries)))
    candidate_sources = candidates.source_titles if isinstance(candidates, Draft) else None
    candidates = list(candidates.entries if isinstance(candidates, Draft) else candidates)
    if candidate_sources is not None and len(candidate_sources) != len(candidates):
        raise BookmarkError("候选原始标题与条目数量不一致，请重新识别。")
    if candidate_sources is not None and any(not isinstance(title, str) for title in candidate_sources):
        raise BookmarkError("候选原始标题必须是文字。")
    scope = [i for i, entry in enumerate(draft.entries) if _in_region(entry, source_page, region)]
    possibilities = {}
    for ci, candidate in enumerate(candidates):
        if not _in_region(candidate, source_page, region):
            possibilities[ci] = None
            continue
        options = [i for i in scope if _same_row(draft.entries[i].source_rect, candidate.source_rect)]
        if len(options) > 1:
            exact = [i for i in options if draft.entries[i].title == candidate.title
                     and (draft.entries[i].pdf_page == candidate.pdf_page if candidate.pdf_page is not None
                          else draft.entries[i].printed_page == candidate.printed_page
                          and candidate.printed_page is not None)]
            if len(exact) == 1:
                options = exact
        possibilities[ci] = options
    claims = {}
    for ci, options in possibilities.items():
        if options is not None and len(options) == 1:
            claims.setdefault(options[0], []).append(ci)
    matches = {ci: options[0] for ci, options in possibilities.items()
               if options is not None and len(options) == 1 and len(claims[options[0]]) == 1}
    used = set(matches.values())
    parents = _parents(draft.entries)
    candidate_parents = _parents(candidates)
    records = []
    for ci, candidate in enumerate(candidates):
        options = possibilities[ci]
        existing = matches.get(ci)
        before = draft.entries[existing] if existing is not None else None
        locked = existing is not None and (existing in protected or _manual(before))
        kind = "existing" if before is not None and _content(before) == _content(candidate) else "change" if before is not None else "new"
        insert_before, message, parent_id = None, "", None
        if existing is None and options:
            kind, message = "ambiguous", "多个来源行或多个候选争用同一行，不能自动匹配。"
        elif options is None:
            kind = "ambiguous"
            message = candidate.note if "局部层级待人工定位" in candidate.note else "来源未知或不在本次区域内，请手工定位。"
        elif existing is None:
            # Candidate order already reflects recognition's single/two-column
            # reading order; do not resort the page merely by its Y coordinate.
            earlier = [(c, i) for c, i in matches.items() if c < ci]
            later = [(c, i) for c, i in matches.items() if c > ci]
            left = max(earlier, default=None)
            right = min(later, default=None)
            if left is not None and right is not None and left[1] >= right[1]:
                kind, message = "ambiguous", "相邻来源的目录顺序冲突，请先人工校正。"
            elif right is not None:
                insert_before = right[1]
            elif left is not None:
                insert_before = left[1] + 1
            elif not draft.entries:
                insert_before = 0
            else:
                kind, message = "ambiguous", "没有可唯一定位的相邻来源行，请使用添加操作。"
            parent = candidate_parents[ci]
            if kind == "new" and candidate.level > 1:
                if parent is not None:
                    parent_id = f"candidate:{parent}"
                    if parent in matches:
                        # The insertion must stay inside its recognized parent.
                        expected = matches[parent]
                        at = insert_before
                        ancestry = []
                        while at is not None and at > 0:
                            at = at - 1 if not ancestry else parents[at]
                            if at is None:
                                break
                            ancestry.append(at)
                            if draft.entries[at].level < candidate.level:
                                break
                        if expected not in ancestry and insert_before != expected + 1:
                            kind, message = "ambiguous", "候选插入位置与父章节不一致。"
                else:
                    # A cropped page can start in the middle of a chapter. Two
                    # neighboring anchors must agree about that parent.
                    inferred = []
                    for anchor in (left, right):
                        if anchor is None:
                            continue
                        at = anchor[1]
                        while at is not None and draft.entries[at].level >= candidate.level:
                            at = parents[at]
                        if at is not None and draft.entries[at].level == candidate.level - 1:
                            inferred.append(at)
                    if len(set(inferred)) == 1:
                        parent_id = f"existing:{inferred[0]}"
                    else:
                        kind, message = "ambiguous", "无法唯一确定新增条目的父章节，请手工添加。"
        records.append(RecognitionRecord(f"candidate:{ci}", kind,
            (existing,) if existing is not None else tuple(options or ()), ci,
            deepcopy(before), deepcopy(candidate), bool(locked), source_page,
            _rect(candidate.source_rect), insert_before, message, parent_id,
            candidate_sources[ci] if candidate_sources is not None else candidate.title))
    for index in scope:
        if index not in used:
            entry = draft.entries[index]
            records.append(RecognitionRecord(f"missing:{index}", "missing", (index,), None,
                deepcopy(entry), None, index in protected or _manual(entry), source_page,
                _rect(entry.source_rect), message="本次未识别到，原条目保留，不会自动删除。"))
    return RecognitionDiff(tuple(records), source_page, region, tuple(deepcopy(draft.entries)),
                           draft.pdf_path, draft.page_count, deepcopy(draft.mapping),
                           tuple(draft.source_titles) if draft.source_titles is not None else None)


def merge_recognition(draft, diff, accepted_ids, *, allow_protected=()):
    """Return a new draft after explicit adoption; reject stale/ambiguous edits.

    Missing rows are always retained. Every changed/new row becomes unconfirmed.
    The caller records the returned draft as one normal undoable transaction.
    """
    if (tuple(draft.entries) != diff.base_entries or draft.pdf_path != diff.pdf_path
            or draft.page_count != diff.page_count or draft.mapping != diff.mapping
            or (tuple(draft.source_titles) if draft.source_titles is not None else None) != diff.base_source_titles):
        raise BookmarkError("草稿已变化，请重新生成重识别对照后再应用。")
    selected = set(accepted_ids)
    overrides = set(allow_protected)
    records = {record.id: record for record in diff.records}
    if selected - records.keys() or overrides - selected:
        raise BookmarkError("候选选择无效，请重新选择。")
    result = deepcopy(draft)
    additions = {}
    changed_indices = set()
    if (result.source_titles is not None
            and (len(result.source_titles) != len(result.entries)
                 or any(not isinstance(title, str) for title in result.source_titles))):
        raise BookmarkError("原始标题与当前目录条目不一致，请先恢复草稿来源。")
    source_by_entry = ({id(entry): source for entry, source in zip(result.entries, result.source_titles)}
                       if result.source_titles is not None else None)
    for record in diff.records:
        if record.id not in selected:
            continue
        if record.kind in ("ambiguous", "missing"):
            raise BookmarkError("歧义候选或本次缺失的条目不能自动合并；请手工校对。")
        if record.kind == "existing":
            continue
        if record.protected and record.id not in overrides:
            raise BookmarkError("已确认或手工修改的条目受到保护；须明确允许替换。")
        if record.parent_id and record.parent_id.startswith("candidate:"):
            parent = records[record.parent_id]
            if parent.kind == "ambiguous" or (parent.kind == "new" and parent.id not in selected):
                raise BookmarkError("请同时接受新增父章节，或手工校对父章节后再合并。")
        entry = deepcopy(record.after)
        if not isinstance(entry.title, str) or not entry.title.strip() or "\x00" in entry.title:
            raise BookmarkError("候选标题为空或无效，不能合并。")
        entry.confirmed = False
        entry.note = (entry.note + " 局部重识别结果，请重新核对标题、层级与目标页。").strip()
        if record.kind == "change":
            index = record.existing_indices[0]
            result.entries[index] = entry
            changed_indices.add(index)
        elif record.kind == "new":
            additions.setdefault(record.insert_before, []).append((record.candidate_index, record.id, entry))
        if source_by_entry is not None:
            source_by_entry[id(entry)] = record.source_title
    merged = []
    for index in range(len(result.entries) + 1):
        merged.extend(entry for _, _, entry in sorted(additions.get(index, [])))
        if index < len(result.entries):
            merged.append(result.entries[index])
    errors = hierarchy_issues(merged)
    if errors:
        raise BookmarkError(f"合并会造成目录层级错误：第 {errors[0].index + 1} 项，{errors[0].message}")
    # Catch a structurally valid but wrong parent when a subset of proposed
    # chapter headings was declined. Entry identity survives our local copy.
    merged_parents = _parents(merged)
    positions = {id(entry): index for index, entry in enumerate(merged)}
    original_parents = _parents(draft.entries)
    for index, entry in enumerate(result.entries):
        if index in changed_indices:
            # A reviewed level change may deliberately correct this row's
            # parent. It must not silently reparent a different untouched row.
            continue
        if original_parents[index] is None:
            expected = None
        else:
            expected = positions[id(result.entries[original_parents[index]])]
        if merged_parents[positions[id(entry)]] != expected:
            raise BookmarkError("合并会改变原条目的父章节；请先手工调整层级后再重识别。")
    candidate_entries = {record.id: result.entries[record.existing_indices[0]]
                         for record in diff.records if record.existing_indices and record.kind in ("existing", "change")}
    for additions_at in additions.values():
        for _, record_id, entry in additions_at:
            candidate_entries[record_id] = entry
    for additions_at in additions.values():
        for _, record_id, entry in additions_at:
            parent_id = records[record_id].parent_id
            if parent_id is None:
                continue
            expected = result.entries[int(parent_id.split(":")[1])] if parent_id.startswith("existing:") else candidate_entries[parent_id]
            if merged_parents[positions[id(entry)]] != positions[id(expected)]:
                raise BookmarkError("新增条目的父章节不一致，请手工校对后再合并。")
    result.entries = merged
    if source_by_entry is not None:
        result.source_titles = [source_by_entry[id(entry)] for entry in merged]
    return result
