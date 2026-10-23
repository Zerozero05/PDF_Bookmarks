"""A one-page recognition pass never loses the surrounding chapter contract."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import unittest

from bookmarks_core import BookmarkError
from review_tools import contextualize_candidates, diff_recognition, merge_recognition
from toc_generation import Draft, DraftEntry


def entry(title, printed, *, level=2, source=3, y=.2, confirmed=False, confidence="高"):
    return DraftEntry(level, title, printed, printed + 5 if printed is not None else None,
                      confidence, "原识别证据", confirmed, source, (.1, y, .85, y + .025))


def book():
    entries = [entry("目录", None, level=1, source=2, y=.05, confirmed=True),
               entry("第一章 基础", 1, level=1, source=2, y=.1, confirmed=True),
               entry("1.1 已核对概念", 1, source=2, y=.2, confirmed=True),
               entry("1.2 已核对方法", 2, y=.1, confirmed=True),
               entry("1.3 手工标题 x²", 3, y=.2, confidence="手工校正"),
               entry("1.4 需要修正", 4, y=.3),
               entry("1.6 另一个节", 6, y=.5),
               entry("第二章 应用", 10, level=1, source=4, y=.1, confirmed=True),
               entry("2.1 已核对应用", 10, source=4, y=.2, confirmed=True)]
    entries[0].pdf_page = 2
    result = Draft(Path("D:/synthetic-cross-page.pdf"), 100, entries, [2, 3, 4],
                   {"offset": 5}, "跨页原始草稿", ["原备注"])
    result.source_titles = [e.title for e in entries]
    return result


def one_page(rows):
    # The real single-page generator prepends a synthetic directory node and
    # can clamp its first true section to level 1 without the previous chapter.
    synthetic = DraftEntry(1, "目录", None, 3)
    result = Draft(Path("D:/synthetic-cross-page.pdf"), 100, [synthetic] + list(rows), [3],
                   {"offset": 17}, "局部 OCR", ["局部备注"])
    result.source_titles = [e.title for e in result.entries]
    return result


class PartialRecognitionContractTests(unittest.TestCase):
    def test_unique_old_rows_restore_levels_mapping_and_canonical_titles(self):
        current = book()
        current.source_titles[3] = "§1.2已核对方法"
        candidates = one_page([entry("§1.2已核对方法", 2, level=1, y=.1),
                               entry("1.4 正确标题", 4, level=2, y=.3)])
        before, raw_before = deepcopy(current), deepcopy(candidates)
        localized = contextualize_candidates(current, candidates, source_page=3)
        self.assertEqual([e.level for e in localized.entries], [2, 2])
        self.assertEqual([e.title for e in localized.entries], ["1.2 已核对方法", "1.4 正确标题"])
        self.assertEqual([e.pdf_page for e in localized.entries], [7, 9])
        self.assertEqual(localized.mapping, {"offset": 5})
        self.assertTrue(all(not e.confirmed for e in localized.entries))
        self.assertEqual(current, before)
        self.assertEqual(candidates, raw_before)

    def test_change_only_page_three_keeps_all_protected_and_outside_fields(self):
        current = book()
        candidates = one_page([entry("1.2 已核对方法", 2, level=1, y=.1),
                               entry("1.3 OCR想覆盖手工标题", 3, y=.2),
                               entry("1.4 正确标题", 4, y=.3)])
        before = deepcopy(current)
        localized = contextualize_candidates(current, candidates, source_page=3)
        proposal = diff_recognition(current, localized, source_page=3)
        chosen = [r.id for r in proposal.records if r.kind == "change" and not r.protected]
        merged = merge_recognition(current, proposal, chosen)
        self.assertEqual(merged.entries[5].title, "1.4 正确标题")
        for index in (0, 1, 2, 3, 4, 6, 7, 8):
            with self.subTest(index=index):
                self.assertEqual(asdict(merged.entries[index]), asdict(before.entries[index]))
        self.assertEqual((merged.method, merged.notes, merged.mapping, merged.toc_pages),
                         (before.method, before.notes, before.mapping, before.toc_pages))
        self.assertEqual(current, before)
        protected = [r.id for r in proposal.records if r.kind == "change" and r.protected]
        self.assertEqual(len(protected), 1)
        with self.assertRaisesRegex(BookmarkError, "保护"):
            merge_recognition(current, proposal, protected)

    def test_cross_page_new_section_uses_whole_chapter_reserved_numbers(self):
        current = book()
        candidates = one_page([entry("1.4 需要修正", 4, level=1, y=.3),
                               entry("补回的节", 5, level=1, y=.4),
                               entry("1.6 另一个节", 6, level=1, y=.5)])
        localized = contextualize_candidates(current, candidates, source_page=3)
        self.assertEqual([e.level for e in localized.entries], [2, 2, 2])
        self.assertEqual([e.title for e in localized.entries],
                         ["1.4 需要修正", "1.5 补回的节", "1.6 另一个节"])
        proposal = diff_recognition(current, localized, source_page=3)
        new = [r for r in proposal.records if r.kind == "new"]
        self.assertEqual(len(new), 1)
        merged = merge_recognition(current, proposal, [new[0].id])
        chapter_one = [e.title.split()[0] for e in merged.entries if e.level == 2 and e.source_page in (2, 3)]
        self.assertEqual(chapter_one, ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6"])
        self.assertEqual(merged.source_titles[6], "补回的节")

    def test_chapter_local_style_restarts_only_at_real_chapter_boundary(self):
        current = book()
        for index in (2, 3, 4, 5, 6):
            number, body = current.entries[index].title.split(" ", 1)
            current.entries[index].title = number.split(".")[1] + ". " + body
        current.entries[8].title = "1. 已核对应用"
        candidates = one_page([entry("1.4 需要修正", 4, level=1, y=.3),
                               entry("补回的节", 5, level=1, y=.4),
                               entry("1.6 另一个节", 6, level=1, y=.5)])
        localized = contextualize_candidates(current, candidates, source_page=3, numbering_style="section")
        self.assertEqual([e.title for e in localized.entries],
                         ["4. 需要修正", "5. 补回的节", "6. 另一个节"])
        self.assertEqual(current.entries[8].title, "1. 已核对应用")

    def test_unlabeled_new_row_with_conflicting_offsets_is_not_auto_matchable(self):
        current = book()
        # A page includes the end of chapter 1 followed by another chapter.
        current.entries[7].source_page = 3
        current.entries[7].source_rect = (.1, .8, .85, .825)
        candidates = one_page([entry("1.6 另一个节", 6, level=1, y=.5),
                               entry("无编号且位置不明", 7, level=1, y=.6),
                               entry("第二章 应用", 10, level=1, y=.8)])
        localized = contextualize_candidates(current, candidates, source_page=3)
        self.assertIsNone(localized.entries[1].source_rect)
        self.assertIn("待人工定位", localized.entries[1].note)
        proposal = diff_recognition(current, localized, source_page=3)
        self.assertEqual(proposal.records[1].kind, "ambiguous")
        with self.assertRaises(BookmarkError):
            merge_recognition(current, proposal, [proposal.records[1].id])

    def test_unknown_parent_number_is_not_inserted_into_previous_chapter(self):
        current = book()
        candidates = one_page([entry("1.4 需要修正", 4, level=1, y=.3),
                               entry("2.5 缺少上级新章", 5, y=.4),
                               entry("1.6 另一个节", 6, y=.5)])
        localized = contextualize_candidates(current, candidates, source_page=3)
        self.assertIsNone(localized.entries[1].source_rect)
        self.assertIn("章节不一致", localized.entries[1].note)

    def test_region_filter_does_not_adopt_other_page_or_outside_crop(self):
        current = book()
        candidates = one_page([entry("1.2 改", 2, y=.1), entry("1.4 改", 4, y=.3),
                               entry("1.6 改", 6, y=.5), entry("别页", 10, source=4, y=.3)])
        localized = contextualize_candidates(current, candidates, source_page=3, source_rect=(0, .25, 1, .4))
        self.assertEqual([e.title for e in localized.entries], ["1.4 改"])
        self.assertEqual(localized.entries[0].source_page, 3)

    def test_no_original_mapping_does_not_adopt_single_page_offset_guess(self):
        current = book()
        current.mapping = None
        current.entries[5].pdf_page = 20
        candidates = one_page([entry("1.4 改", 4, level=1, y=.3), entry("1.5 新", 5, y=.4),
                               entry("1.6 另一个节", 6, y=.5)])
        localized = contextualize_candidates(current, candidates, source_page=3)
        self.assertIsNone(localized.mapping)
        self.assertEqual(localized.entries[0].pdf_page, 20)
        self.assertIsNone(localized.entries[1].pdf_page)

    def test_raw_ocr_remains_visible_after_manual_title_edit_in_every_numbering_style(self):
        for style in ("chapter_section", "section", "preserve"):
            current = book()
            original = "4. 需要修正" if style == "section" else "1.4 需要修正"
            current.entries[5].title = original + " TEST"
            current.entries[5].confidence = "手工校正"
            current.entries[5].confirmed = False
            candidates = one_page([entry("1.4 需要修正", 4, level=1, y=.3)])
            before = deepcopy(current)
            localized = contextualize_candidates(current, candidates, source_page=3, numbering_style=style)
            proposal = diff_recognition(current, localized, source_page=3)
            target = next(record for record in proposal.records if record.existing_indices == (5,))
            with self.subTest(style=style):
                self.assertEqual(target.kind, "change")
                self.assertTrue(target.protected)
                self.assertEqual(target.before.title, original + " TEST")
                self.assertEqual(target.after.title, original)
                with self.assertRaisesRegex(BookmarkError, "保护"):
                    merge_recognition(current, proposal, [target.id])
                adopted = merge_recognition(current, proposal, [target.id], allow_protected=[target.id])
                self.assertEqual(adopted.entries[5].title, original)
                self.assertFalse(adopted.entries[5].confirmed)
                self.assertEqual(current, before)


if __name__ == "__main__":
    unittest.main()
