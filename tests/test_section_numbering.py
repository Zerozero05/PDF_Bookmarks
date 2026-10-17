"""Section naming changes titles only, using the original automatic draft."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import pymupdf

from bookmarks_core import BookmarkError
import toc_generation as generation
from toc_generation import Draft, DraftEntry, generate_toc, load_draft, save_toc


class SectionNumberingTests(unittest.TestCase):
    def draft(self, rows):
        entries = [DraftEntry(level, title, index + 1, index + 2,
                              "低", "识别证据。", index % 2 == 0)
                   for index, (level, title) in enumerate(rows)]
        result = Draft(Path("temporary.pdf"), 100, entries, [1, 2],
                       {"offset": 1}, "文字提取", ["请校对。"])
        # The generator keeps these raw titles before its default formatting.
        result.source_titles = [entry.title for entry in result.entries]
        return result

    def titles(self, draft, style="chapter_section", **options):
        return generation.section_titles(draft, style, **options)

    def test_two_styles_and_preserve_use_original_titles(self):
        draft = self.draft([(1, "目录"), (1, "第一章基础"), (2, "基本概念"),
                            (2, "§1.2拓展"), (1, "第二章应用"), (2, "应用方法")])
        self.assertEqual(self.titles(draft), ["目录", "第一章 基础", "1.1 基本概念",
                                             "1.2 拓展", "第二章 应用", "2.1 应用方法"])
        self.assertEqual(self.titles(draft, "section"), ["目录", "第一章 基础", "1. 基本概念",
                                                        "2. 拓展", "第二章 应用", "1. 应用方法"])
        self.assertEqual(self.titles(draft, "preserve"), ["目录", "第一章 基础", "基本概念",
                                                         "1.2 拓展", "第二章 应用", "应用方法"])

    def test_conversion_never_mutates_draft_or_confirmation(self):
        draft = self.draft([(1, "第一章基础"), (2, "§1.1概念"), (2, "方法")])
        before = deepcopy(draft)
        for style in ("chapter_section", "section", "preserve"):
            self.titles(draft, style)
            self.assertEqual(draft, before)

    def test_switching_repeatedly_does_not_stack_or_lose_numbers(self):
        draft = self.draft([(1, "第一章基础"), (2, "基本概念"), (2, "方法")])
        for style in ("section", "chapter_section", "section", "preserve") * 2:
            result = self.titles(draft, style)
            for entry, title in zip(draft.entries, result):
                entry.title = title
        self.assertEqual([entry.title for entry in draft.entries], ["第一章 基础", "基本概念", "方法"])
        self.assertEqual(self.titles(draft), ["第一章 基础", "1.1 基本概念", "1.2 方法"])

    def test_existing_numbers_reserved_and_missing_numbers_continue(self):
        draft = self.draft([(1, "第十章基础"), (2, "缺号"), (2, "10.1 首节"),
                            (2, "10.4 第四节"), (2, "后续")])
        self.assertEqual(self.titles(draft), ["第十章 基础", "10.2 缺号", "10.1 首节",
                                             "10.4 第四节", "10.5 后续"])
        self.assertEqual(self.titles(draft, "section"), ["第十章 基础", "2. 缺号", "1. 首节",
                                                        "4. 第四节", "5. 后续"])

    def test_chinese_english_and_bare_section_labels_convert(self):
        draft = self.draft([(1, "Chapter IV Foundations"), (2, "第一节基本概念"),
                            (2, "Section 2 Methods"), (2, "三、推广"),
                            (2, "Sec. 4 Examples"), (2, "5. More"), (2, "6．补充")])
        self.assertEqual(self.titles(draft), ["Chapter IV Foundations", "4.1 基本概念", "4.2 Methods",
                                             "4.3 推广", "4.4 Examples", "4.5 More", "4.6 补充"])
        self.assertEqual(self.titles(draft, "section"), ["Chapter IV Foundations", "1. 基本概念", "2. Methods",
                                                        "3. 推广", "4. Examples", "5. More", "6. 补充"])

    def test_explicit_subsection_numbers_and_unlabelled_deeper_levels_stay(self):
        draft = self.draft([(1, "第一章基础"), (2, "1.2方法"), (3, "§1.2.1局部"),
                            (3, "进一步说明"), (2, "1.2.3错误层级仍保留编号"),
                            (2, "后续")])
        self.assertEqual(self.titles(draft, "section"), ["第一章 基础", "2. 方法", "1.2.1 局部",
                                                        "进一步说明", "1.2.3 错误层级仍保留编号", "3. 后续"])
        self.assertEqual([entry.level for entry in draft.entries], [1, 2, 3, 3, 2, 2])

    def test_parts_front_matter_appendices_and_root_titles_do_not_number(self):
        draft = self.draft([(1, "前言"), (1, "第一篇基础"), (2, "第3章理论"),
                            (3, "概念"), (1, "附录A公式"), (2, "补充材料"),
                            (1, "参考文献"), (1, "索引")])
        self.assertEqual(self.titles(draft, "section"), ["前言", "第一篇 基础", "第3章 理论",
                                                        "1. 概念", "附录A公式", "补充材料", "参考文献", "索引"])

    def test_numeric_title_content_is_preserved(self):
        draft = self.draft([(1, "第一章基础"), (2, "3D动力系统"),
                            (2, "2020年的研究"), (2, "100%概率"), (2, "L2空间")])
        self.assertEqual(self.titles(draft, "section"), ["第一章 基础", "1. 3D动力系统",
                                                        "2. 2020年的研究", "3. 100%概率", "4. L2空间"])

    def test_unknown_or_conflicting_chapter_labels_are_not_guessed(self):
        draft = self.draft([(1, "Chapter I2 Foundations"), (2, "Iteration"),
                            (1, "第一章基础"), (2, "2.3 别章的编号"), (2, "后续")])
        self.assertEqual(self.titles(draft, "section"), ["Chapter I2 Foundations", "Iteration",
                                                        "第一章 基础", "2.3 别章的编号", "1. 后续"])

    def test_explicit_source_titles_support_identity_aligned_editor_order(self):
        draft = self.draft([(1, "第一章基础"), (2, "概念"), (2, "方法")])
        draft.entries[1], draft.entries[2] = draft.entries[2], draft.entries[1]
        result = self.titles(draft, "section", source_titles=["第一章基础", "方法", "概念"])
        self.assertEqual(result, ["第一章 基础", "1. 方法", "2. 概念"])
        self.assertEqual(draft.source_titles, ["第一章基础", "概念", "方法"])

    def test_manual_and_imported_drafts_without_generated_sources_stay_verbatim(self):
        draft = Draft(Path("manual.pdf"), 10,
                      [DraftEntry(1, "第一章基础", None, 1), DraftEntry(2, "§1.1我的手工标题", None, 2)],
                      [], None, "导入 JSON", [])
        for style in ("chapter_section", "section", "preserve"):
            self.assertEqual(self.titles(draft, style), ["第一章基础", "§1.1我的手工标题"])

    def test_invalid_style_or_misaligned_sources_are_rejected(self):
        draft = self.draft([(1, "第一章基础"), (2, "概念")])
        for style in ("", "renumber_everything", None):
            with self.assertRaises(BookmarkError):
                self.titles(draft, style)
        with self.assertRaises(BookmarkError):
            self.titles(draft, source_titles=["第一章基础"])

    def test_sections_without_readable_chapter_do_not_get_a_global_sequence(self):
        draft = self.draft([(1, "Overview"), (2, "Basic concepts"),
                            (1, "第1十章基础"), (2, "未识别章号的节"),
                            (1, "第十二章基础"), (2, "有效章的节")])
        self.assertEqual(self.titles(draft, "section"), ["Overview", "Basic concepts",
                                                        "第1十章 基础", "未识别章号的节",
                                                        "第十二章 基础", "1. 有效章的节"])

    def test_title_body_punctuation_and_numbers_remain_verbatim(self):
        draft = self.draft([(1, "第一章基础"), (2, "§1.2 Fourier 3D, L2 和 100%"),
                            (2, "3. “定义”：2020 年 (修订)")])
        self.assertEqual(self.titles(draft, "section"), ["第一章 基础", "2. Fourier 3D, L2 和 100%",
                                                        "3. “定义”：2020 年 (修订)"])

    def test_preserve_does_not_translate_existing_label_kinds(self):
        draft = self.draft([(1, "第一章基础"), (2, "第一节基本"), (2, "三、推广"),
                            (2, "Section 4 Examples"), (2, "§5未限定符号")])
        self.assertEqual(self.titles(draft, "preserve"), ["第一章 基础", "第一节 基本", "三、 推广",
                                                         "Section 4 Examples", "5 未限定符号"])

    def test_invalid_sources_do_not_modify_evidence(self):
        draft = self.draft([(1, "第一章基础"), (2, "概念")])
        before = deepcopy(draft)
        with self.assertRaises(BookmarkError):
            self.titles(draft, "section", source_titles=["第一章基础", None])
        self.assertEqual(draft, before)

    def test_generation_keeps_raw_titles_and_default_api_and_json_schema(self):
        with tempfile.TemporaryDirectory(prefix="section-naming-") as folder:
            pdf, target = Path(folder) / "source.pdf", Path(folder) / "source.toc.json"
            with pymupdf.open() as document:
                page = document.new_page()
                page.insert_text((30, 40), "Contents")
                page.insert_text((30, 80), "Chapter 1 Foundations .... 1")
                page.insert_text((60, 110), "Basic concepts .... 2")
                for _ in range(3):
                    document.new_page().insert_text((30, 50), "Body text")
                document.save(pdf)
            before = pdf.read_bytes()
            draft = generate_toc(pdf, toc_start=1, toc_end=1, offset=1)
            self.assertEqual(draft.source_titles, ["目录", "Chapter 1 Foundations", "Basic concepts"])
            self.assertEqual([entry.title for entry in draft.entries], ["目录", "Chapter 1 Foundations", "1.1 Basic concepts"])
            self.assertEqual(self.titles(draft, "section"), ["目录", "Chapter 1 Foundations", "1. Basic concepts"])
            self.assertFalse(any(entry.confirmed for entry in draft.entries))
            for entry in draft.entries:
                entry.confirmed = True
            save_toc(draft, target)
            imported = load_draft(pdf, target)
            self.assertIsNone(imported.source_titles)
            self.assertNotIn("source_titles", target.read_text(encoding="utf-8"))
            self.assertEqual(pdf.read_bytes(), before)
            with pymupdf.open(pdf) as document:
                document.set_toc([[1, "Chapter 1 Foundations", 2], [2, "§1.1Basic concepts", 3]])
                outlined = Path(folder) / "outlined.pdf"
                document.save(outlined)
            reused = generate_toc(outlined, prefer_existing=True)
            self.assertIsNone(reused.source_titles)
            self.assertEqual(self.titles(reused, "section"), ["Chapter 1 Foundations", "§1.1Basic concepts"])


if __name__ == "__main__":
    unittest.main()
