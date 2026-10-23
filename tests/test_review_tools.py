"""Pure review helpers protect existing sources and require explicit adoption."""

from copy import deepcopy
from pathlib import Path
import unittest

from bookmarks_core import BookmarkError
from review_tools import (diagnose_draft, diff_recognition, hierarchy_issues,
                          merge_recognition, preview_mapping, preview_titles)
from toc_generation import Draft, DraftEntry, apply_mapping, to_toc


def row(title, page=1, *, level=1, y=None, x=.1, confirmed=False, source_page=2):
    return DraftEntry(level, title, page, page, "高", "识别结果", confirmed,
        source_page if y is not None else None,
        (x, y, x + .3, y + .025) if y is not None else None)


def draft(entries=(), mapping=None):
    return Draft(Path("D:/synthetic-review.pdf"), 100, list(entries), [2], mapping, "测试", [])


class ReviewDiagnosticsTests(unittest.TestCase):
    def codes(self, current):
        return {(item.index, item.code) for item in diagnose_draft(current)}

    def test_all_independent_save_blockers_and_no_mutation(self):
        current = draft([row("", 0, level=2), row("有效", 101, level=4),
                         row("含\x00字符", None, level=True)])
        current.entries[1].printed_page = -1
        before = deepcopy(current)
        found = self.codes(current)
        self.assertTrue({(0, "invalid_title"), (0, "invalid_target"), (0, "level_jump"),
                         (1, "level_jump"), (1, "target_out_of_range"), (1, "invalid_printed_page"),
                         (2, "invalid_level"), (2, "unknown_target"), (2, "invalid_title")} <= found)
        issues = diagnose_draft(current)
        self.assertEqual(sum(item.code == "unconfirmed" for item in issues), 3)
        self.assertTrue(all(item.severity == "error" for item in issues))
        self.assertEqual(current, before)

    def test_empty_directory_and_bad_mapping_are_locatable_global_issues(self):
        issues = diagnose_draft(draft(mapping={"offset": True}))
        self.assertEqual({item.code for item in issues}, {"empty_directory", "invalid_mapping"})
        self.assertTrue(all(item.index is None for item in issues))

    def test_confirmation_and_page_reasons_stay_separate(self):
        issues = diagnose_draft(draft([row("标题", None)]))
        self.assertEqual({item.category for item in issues}, {"confirmation", "page"})
        self.assertTrue(all(item.severity == "error" for item in issues))

    def test_same_title_and_page_in_different_chapters_not_duplicate(self):
        current = draft([row("第一章", 1), row("习题", 2, level=2),
                         row("第二章", 2), row("习题", 2, level=2)])
        self.assertNotIn("possible_duplicate", {issue.code for issue in diagnose_draft(current)})
        current.entries.append(row("习题", 2, level=2))
        found = [issue for issue in diagnose_draft(current) if issue.code == "possible_duplicate"]
        self.assertEqual([issue.index for issue in found], [4])
        self.assertEqual(found[0].category, "title")
        self.assertEqual(found[0].severity, "warning")

    def test_distinct_page_or_math_case_is_not_duplicate(self):
        current = draft([row("第一章"), row("A", 2, level=2), row("a", 2, level=2),
                         row("A", 3, level=2)])
        self.assertNotIn("possible_duplicate", {issue.code for issue in diagnose_draft(current)})

    def test_number_gap_only_siblings_with_same_prefix(self):
        current = draft([row("第一章"), row("1.1 概念", 2, level=2),
            row("1.1.1 条件", 2, level=3), row("1.3 方法", 3, level=2),
            row("第二章", 4), row("2.3 首节", 4, level=2)])
        found = [issue for issue in diagnose_draft(current) if issue.code == "number_gap"]
        self.assertEqual([issue.index for issue in found], [3])
        self.assertEqual(found[0].severity, "warning")
        self.assertEqual(found[0].category, "hierarchy")

    def test_chapter_local_numbering_front_matter_and_appendices_not_misdiagnosed(self):
        current = draft([row("前言", 5), row("1. 背景", 2, level=2),
            row("第一章", 1), row("1. 基础", 2, level=2), row("2. 延伸", 3, level=2),
            row("第二章", 1), row("1. 新概念", 1, level=2),
            row("附录 A", 90), row("2. 参考", 50, level=2)])
        self.assertEqual([issue for issue in diagnose_draft(current, numbering_style="section")
                          if issue.severity == "warning"], [])

    def test_unspaced_decimal_math_is_not_a_section_label(self):
        current = draft([row("第一章"), row("3.14159", 2, level=2),
                         row("10.23456", 3, level=2), row("1.1x", 4, level=2)])
        self.assertNotIn("number_gap", {issue.code for issue in diagnose_draft(current)})

    def test_pdf_page_order_not_printed_page_restart(self):
        current = draft([row("第一章", 1), row("1.1 概念", 5, level=2), row("1.2 方法", 6, level=2)])
        current.entries[2].printed_page = 1
        self.assertNotIn("page_reversal", {issue.code for issue in diagnose_draft(current)})
        current.entries[2].pdf_page = 3
        self.assertIn((2, "page_reversal"), self.codes(current))

    def test_valid_confirmed_draft_agrees_with_existing_serializer(self):
        current = draft([row("第一章", 1, confirmed=True), row("1.1 概念", 2, level=2, confirmed=True)])
        self.assertEqual(diagnose_draft(current), [])
        self.assertEqual(to_toc(current)["version"], 1)

    def test_hierarchy_checks_all_errors_and_accepts_returns_to_root(self):
        self.assertEqual(hierarchy_issues([row("章"), row("节", level=2), row("新章")]), [])
        self.assertEqual([issue.index for issue in hierarchy_issues([row("章", level=2), row("节", level=4)])], [0, 1])


class MappingPreviewTests(unittest.TestCase):
    def test_offset_preview_matches_apply_and_keeps_manual_direct_page(self):
        current = draft([row("前言", None, confirmed=True), row("章", 1, confirmed=True),
                         row("节", 2, level=2)])
        current.entries[0].pdf_page = 1
        before = deepcopy(current)
        result = preview_mapping(current, {"offset": 2})
        expected = deepcopy(current)
        apply_mapping(expected, {"offset": 2})
        self.assertEqual(current, before)
        self.assertEqual((result.changed, result.needs_review, result.uncovered, result.out_of_range), (2, 1, 0, 0))
        self.assertEqual([(sample.index, sample.before, sample.after, sample.was_confirmed) for sample in result.samples],
                         [(1, 1, 3, True), (2, 2, 4, False)])
        self.assertEqual([sample.after for sample in result.samples], [entry.pdf_page for entry in expected.entries[1:]])
        self.assertTrue(expected.entries[0].confirmed)

    def test_unchanged_target_still_loses_confirmation(self):
        current = draft([row("章", 1, confirmed=True)], mapping={"offset": 0})
        result = preview_mapping(current, {"offset": 0})
        self.assertEqual((result.changed, result.needs_review), (0, 1))
        self.assertTrue(current.entries[0].confirmed)

    def test_uncovered_distinguished_from_out_of_range(self):
        current = draft([row("章", 1), row("节", 10, level=2), row("末", 99)])
        partial = preview_mapping(current, {"segments": [{"printed_start": 1, "printed_end": 2, "pdf_start": 5}]})
        offset = preview_mapping(current, {"offset": 2})
        self.assertEqual((partial.uncovered, partial.out_of_range), (2, 0))
        self.assertEqual((offset.uncovered, offset.out_of_range), (0, 1))
        self.assertEqual(offset.samples[-1].after, None)

    def test_invalid_mapping_and_printed_page_preserve_all_state(self):
        current = draft([row("章", 1, confirmed=True)], mapping={"offset": 0})
        for mapping in ({"offset": True}, {"segments": []}, {"segments": [
                {"printed_start": 1, "printed_end": 5, "pdf_start": 99}]}):
            before = deepcopy(current)
            with self.subTest(mapping=mapping), self.assertRaises(BookmarkError):
                preview_mapping(current, mapping)
            self.assertEqual(current, before)
        current.entries[0].printed_page = -1
        before = deepcopy(current)
        with self.assertRaises(BookmarkError):
            preview_mapping(current, {"offset": 1})
        self.assertEqual(current, before)

    def test_sample_limit_and_negative_offset(self):
        current = draft([row("章", 1), row("节", 2, level=2)])
        result = preview_mapping(current, {"offset": -1}, sample_limit=1)
        self.assertEqual(result.out_of_range, 1)
        self.assertEqual(len(result.samples), 1)
        self.assertIsNone(result.samples[0].after)
        self.assertEqual(preview_mapping(current, {"offset": 1}, sample_limit=0).samples, ())


class TitlePreviewTests(unittest.TestCase):
    def test_empty_selection_means_none_and_default_does_nothing(self):
        current = draft([row("第一章"), row("§1.1 x² + y²", 2, level=2)])
        self.assertEqual(preview_titles(current, [], prefix="新"), [])
        self.assertEqual(preview_titles(current, [0, 1]), [])

    def test_literal_replace_does_not_treat_math_as_regex(self):
        current = draft([row("x+y + x+y"), row("x+y", 2)])
        before = deepcopy(current)
        result = preview_titles(current, [0, 0], find="x+y", replace="u.v")
        self.assertEqual([(r.index, r.before, r.after) for r in result], [(0, "x+y + x+y", "u.v + u.v")])
        self.assertEqual(current, before)

    def test_prefix_suffix_and_explicit_whitespace_rules(self):
        current = draft([row("OLD  1.1  数学  END")])
        result = preview_titles(current, [0], remove_prefix="OLD", remove_suffix="END", strip=True,
                                collapse_spaces=True, prefix="[", suffix="]")
        self.assertEqual(result[0].after, "[1.1 数学]")

    def test_suffix_prefix_remove_only_at_edges_and_only_once(self):
        current = draft([row("AA body AA AA")])
        self.assertEqual(preview_titles(current, [0], remove_prefix="AA", remove_suffix="AA")[0].after,
                         " body AA ")

    def test_replacement_can_preview_empty_title_for_user_to_fix(self):
        self.assertEqual(preview_titles(draft([row("all")]), [0], find="all")[0].after, "")

    def test_invalid_selection_and_empty_search_do_not_mutate(self):
        current = draft([row("原标题")])
        before = deepcopy(current)
        for indices in ([1], [-1], [True], [0, "1"]):
            with self.subTest(indices=indices), self.assertRaises(BookmarkError):
                preview_titles(current, indices, prefix="新")
        for options in ({"find": ""}, {"find": 1}, {"replace": "\x00"}, {"strip": "yes"}):
            with self.subTest(options=options), self.assertRaises(BookmarkError):
                preview_titles(current, [0], **options)
        self.assertEqual(current, before)


class LocalRecognitionTests(unittest.TestCase):
    def original(self):
        return draft([row("第一章", 1, y=.1), row("1.1 概念", 2, level=2, y=.2),
                      row("1.3 推广", 4, level=2, y=.4), row("第二章", 10, y=.6),
                      row("2.1 方法", 11, level=2, y=.7)])

    def test_unique_physical_row_matches_changed_ocr_title_and_page(self):
        current = self.original()
        before = deepcopy(current)
        candidate = row("1.1 正确概念", 3, level=2, y=.2)
        proposal = diff_recognition(current, [candidate], source_page=2)
        record = proposal.records[0]
        self.assertEqual((record.kind, record.existing_indices), ("change", (1,)))
        result = merge_recognition(current, proposal, [record.id])
        self.assertEqual(result.entries[1].title, "1.1 正确概念")
        self.assertEqual(result.entries[1].pdf_page, 3)
        self.assertFalse(result.entries[1].confirmed)
        self.assertEqual(current, before)
        self.assertEqual(result.entries[0], current.entries[0])
        self.assertEqual(len(result.entries), len(current.entries))

    def test_identical_result_is_noop_even_when_confirmed(self):
        current = self.original()
        current.entries[1].confirmed = True
        proposal = diff_recognition(current, [deepcopy(current.entries[1])], source_page=2)
        self.assertEqual(proposal.records[0].kind, "existing")
        self.assertEqual(merge_recognition(current, proposal, [proposal.records[0].id]), current)

    def test_missing_rows_are_not_removed(self):
        current = self.original()
        proposal = diff_recognition(current, [], source_page=2)
        self.assertTrue(all(record.kind == "missing" for record in proposal.records))
        self.assertEqual(merge_recognition(current, proposal, []), current)
        with self.assertRaisesRegex(BookmarkError, "不能自动合并"):
            merge_recognition(current, proposal, [proposal.records[0].id])

    def test_protected_confirmed_manual_and_explicit_indices_require_override(self):
        for mode in ("confirmed", "manual", "index"):
            current = self.original()
            if mode == "confirmed":
                current.entries[1].confirmed = True
            elif mode == "manual":
                current.entries[1].confidence = "手工校正"
            proposal = diff_recognition(current, [row("1.1 新", 2, level=2, y=.2)], source_page=2,
                                        protected_indices=[1] if mode == "index" else [])
            record = proposal.records[0]
            self.assertTrue(record.protected)
            with self.subTest(mode=mode), self.assertRaisesRegex(BookmarkError, "保护"):
                merge_recognition(current, proposal, [record.id])
            result = merge_recognition(current, proposal, [record.id], allow_protected=[record.id])
            self.assertFalse(result.entries[1].confirmed)

    def test_region_and_page_boundaries_preserve_outside_and_unknown_sources(self):
        current = self.original()
        current.entries.append(row("无来源", 20))
        proposal = diff_recognition(current, [row("1.1 修改", 2, level=2, y=.2)], source_page=2,
                                    source_rect=(0, .15, .8, .3))
        self.assertEqual(len(proposal.records), 1)
        result = merge_recognition(current, proposal, [proposal.records[0].id])
        for index in (0, 2, 3, 4, 5):
            self.assertEqual(result.entries[index], current.entries[index])

    def test_unknown_candidate_source_cannot_be_adopted(self):
        current = self.original()
        for candidate in (row("新标题", 2), row("页外标题", 2, y=.2, source_page=3)):
            proposal = diff_recognition(current, [candidate], source_page=2)
            self.assertEqual(proposal.records[0].kind, "ambiguous")
            with self.assertRaises(BookmarkError):
                merge_recognition(current, proposal, [proposal.records[0].id])

    def test_duplicate_physical_candidates_are_ambiguous(self):
        current = self.original()
        proposal = diff_recognition(current, [row("甲", 2, level=2, y=.2), row("乙", 2, level=2, y=.2)], source_page=2)
        self.assertEqual([r.kind for r in proposal.records[:2]], ["ambiguous", "ambiguous"])
        with self.assertRaises(BookmarkError):
            merge_recognition(current, proposal, [proposal.records[0].id])

    def test_two_columns_at_same_height_remain_independent(self):
        current = draft([row("左章", 1, y=.2, x=.1), row("右章", 50, y=.2, x=.6)])
        proposal = diff_recognition(current, [row("右章改", 51, y=.2, x=.6)], source_page=2)
        self.assertEqual(proposal.records[0].existing_indices, (1,))
        result = merge_recognition(current, proposal, [proposal.records[0].id])
        self.assertEqual(result.entries[0], current.entries[0])

    def test_new_section_between_anchors_retains_parent_and_existing_order(self):
        current = self.original()
        candidates = [deepcopy(current.entries[1]), row("1.2 补回", 3, level=2, y=.3),
                      deepcopy(current.entries[2])]
        proposal = diff_recognition(current, candidates, source_page=2)
        record = proposal.records[1]
        self.assertEqual((record.kind, record.insert_before, record.parent_id), ("new", 2, "existing:0"))
        result = merge_recognition(current, proposal, [record.id])
        self.assertEqual([entry.title for entry in result.entries],
                         ["第一章", "1.1 概念", "1.2 补回", "1.3 推广", "第二章", "2.1 方法"])
        self.assertFalse(result.entries[2].confirmed)

    def test_new_root_and_child_require_explicit_parent_acceptance(self):
        current = draft()
        proposal = diff_recognition(current, [row("新章", 1, y=.1), row("新节", 2, level=2, y=.2)], source_page=2)
        self.assertEqual([r.kind for r in proposal.records], ["new", "new"])
        with self.assertRaisesRegex(BookmarkError, "父章节"):
            merge_recognition(current, proposal, [proposal.records[1].id])
        result = merge_recognition(current, proposal, [r.id for r in proposal.records])
        self.assertEqual([e.level for e in result.entries], [1, 2])

    def test_no_anchor_with_existing_draft_does_not_guess_new_chapter(self):
        current = self.original()
        proposal = diff_recognition(current, [row("新章", 20, y=.9)], source_page=2)
        self.assertEqual(proposal.records[0].kind, "ambiguous")

    def test_insertion_cannot_silently_reparent_existing_children(self):
        current = self.original()
        proposal = diff_recognition(current, [deepcopy(current.entries[1]), row("新章", 3, y=.3)], source_page=2)
        with self.assertRaisesRegex(BookmarkError, "父章节"):
            merge_recognition(current, proposal, [proposal.records[1].id])

    def test_hierarchy_regression_rejected_without_mutation(self):
        current = self.original()
        before = deepcopy(current)
        proposal = diff_recognition(current, [row("跳级", 2, level=4, y=.2)], source_page=2)
        with self.assertRaisesRegex(BookmarkError, "层级"):
            merge_recognition(current, proposal, [proposal.records[0].id])
        self.assertEqual(current, before)

    def test_explicit_level_correction_can_change_only_accepted_rows_parent(self):
        current = draft([row("章", 1, y=.1), row("节", 2, level=2, y=.2),
                         row("错识别为同级", 3, level=2, y=.3)])
        candidate = deepcopy(current.entries[2])
        candidate.level = 3
        proposal = diff_recognition(current, [candidate], source_page=2)
        result = merge_recognition(current, proposal, [proposal.records[0].id])
        self.assertEqual([entry.level for entry in result.entries], [1, 2, 3])
        self.assertEqual(result.entries[:2], current.entries[:2])
        self.assertFalse(result.entries[2].confirmed)

    def test_stale_diff_rejected_after_title_mapping_or_confirmation_changes(self):
        for field in ("title", "mapping", "confirmed", "sources"):
            current = self.original()
            proposal = diff_recognition(current, [row("1.1 新", 2, level=2, y=.2)], source_page=2)
            if field == "mapping":
                current.mapping = {"offset": 1}
            elif field == "confirmed":
                current.entries[1].confirmed = True
            elif field == "sources":
                current.source_titles = [entry.title for entry in current.entries]
            else:
                current.entries[1].title = "用户刚改的标题"
            with self.subTest(field=field), self.assertRaisesRegex(BookmarkError, "已变化"):
                merge_recognition(current, proposal, [proposal.records[0].id])

    def test_original_numbering_sources_preserved_and_changes_get_new_source(self):
        current = self.original()
        current.source_titles = [e.title for e in current.entries]
        proposal = diff_recognition(current, [row("1.1 新", 2, level=2, y=.2)], source_page=2)
        result = merge_recognition(current, proposal, [proposal.records[0].id])
        self.assertEqual(result.source_titles, ["第一章", "1.1 新", "1.3 推广", "第二章", "2.1 方法"])
        self.assertEqual(current.source_titles[1], "1.1 概念")

    def test_original_numbering_sources_follow_insertions_and_candidate_raw_titles(self):
        current = self.original()
        current.source_titles = ["原始" + e.title for e in current.entries]
        recognized = draft([deepcopy(current.entries[1]), row("1.2 补回", 3, level=2, y=.3),
                            deepcopy(current.entries[2])])
        recognized.source_titles = ["§1.1概念", "§1.2补回", "§1.3推广"]
        proposal = diff_recognition(current, recognized, source_page=2)
        result = merge_recognition(current, proposal, [proposal.records[1].id])
        self.assertEqual(result.source_titles, ["原始第一章", "原始1.1 概念", "§1.2补回", "原始1.3 推广",
                                                "原始第二章", "原始2.1 方法"])
        self.assertEqual(len(result.source_titles), len(result.entries))
        self.assertEqual(merge_recognition(current, proposal, []), current)

    def test_invalid_region_or_selection_is_not_silently_accepted(self):
        current = self.original()
        for rect in ((0, 0, 2, 1), (0, 0, float("nan"), 1), (.5, .5, .2, .8)):
            with self.subTest(rect=rect), self.assertRaises(BookmarkError):
                diff_recognition(current, [], source_page=2, source_rect=rect)
        proposal = diff_recognition(current, [], source_page=2)
        with self.assertRaises(BookmarkError):
            merge_recognition(current, proposal, ["unknown"])


if __name__ == "__main__":
    unittest.main()
