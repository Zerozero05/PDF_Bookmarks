"""TOC hierarchy regressions exercise recognition against temporary PDFs."""

from pathlib import Path
import tempfile
import unittest

import pymupdf

from toc_generation import generate_toc


class HierarchyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="zotero-hierarchy-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def recognize(self, pages):
        pdf = self.folder / "hierarchy.pdf"
        with pymupdf.open() as document:
            for rows in pages:
                page = document.new_page(width=600, height=800)
                page.insert_text((30, 35), "Contents")
                for index, (title, x) in enumerate(rows, 1):
                    font = "china-s" if any(ord(letter) > 127 for letter in title) else "helv"
                    page.insert_text((x, 60 + index * 30), title + " .... " + str(index), fontname=font, fontsize=11)
            for _ in range(25):
                page = document.new_page(width=600, height=800)
                page.insert_text((30, 50), "Readable original document body; do not modify.")
            document.save(pdf)
        original = pdf.read_bytes()
        draft = generate_toc(pdf, toc_start=1, toc_end=len(pages), offset=len(pages))
        self.assertEqual(pdf.read_bytes(), original)
        self.assertFalse(any(entry.confirmed for entry in draft.entries))
        return draft

    def levels(self, draft):
        return [entry.level for entry in draft.entries[1:]]

    def test_rudin_chapters_contain_unnumbered_sections_and_exercises(self):
        draft = self.recognize([[ (title, 40) for title in (
            "Chapter 1 Abstract Integration", "Set-theoretic notations and terminology",
            "The concept of measurability", "Simple functions", "Exercises",
            "Chapter 2 Positive Borel Measures", "Vector spaces", "Exercises",
            "Bibliography", "Index",
        )]])
        self.assertEqual(self.levels(draft), [1, 2, 2, 2, 2, 1, 2, 2, 1, 1])

    def test_parts_chapters_explicit_sections_and_numbered_subsections(self):
        draft = self.recognize([[ (title, 40) for title in (
            "Part I Foundations", "Chapter 1 Measures", "Section 1 Measurability",
            "Subsection 1.1 Simple functions", "Chapter 2 Integration", "2.1 Basic integrals",
            "2.1.1 Approximations", "Part II Complex analysis", "Chapter 3 Holomorphic functions",
            "3.1 Derivatives", "Appendix A Facts", "A.1 Lemma",
        )]])
        self.assertEqual(self.levels(draft), [1, 2, 3, 4, 2, 3, 4, 1, 2, 3, 1, 2])

    def test_chinese_sections_subsections_and_common_outline_numbers(self):
        draft = self.recognize([[ (title, 40) for title in (
            "第一章 动力系统", "第一节 基本概念", "第一小节 流的定义",
            "第二章 微分方程", "一、准备知识", "（一）记号", "§2 解的存在性",
            "2.1 局部解", "2.1.1 唯一性", "参考文献",
        )]])
        self.assertEqual(self.levels(draft), [1, 2, 3, 1, 2, 3, 2, 2, 3, 1])

    def test_chinese_parts_nest_chapters(self):
        draft = self.recognize([[ (title, 40) for title in (
            "第一篇 基础", "第一章 基本概念", "第一节 流", "1.1.1 例子",
            "第二章 稳定性", "§1 线性化", "第二篇 应用", "第三章 分岔", "习题",
        )]])
        self.assertEqual(self.levels(draft), [1, 2, 3, 4, 2, 3, 1, 2, 3])

    def test_context_survives_toc_page_breaks_and_margin_changes(self):
        draft = self.recognize([
            [("Chapter 1 Alpha", 35), ("First section", 90)],
            [("Continuation section", 55), ("Chapter 2 Beta", 30), ("Next section", 55)],
        ])
        self.assertEqual(self.levels(draft), [1, 2, 2, 1, 2])

    def test_deeper_indent_is_hint_for_unnumbered_subsection(self):
        draft = self.recognize([[
            ("Chapter 1 Alpha", 30), ("Section 1 Foundations", 60),
            ("A nested example", 90), ("A sibling section", 60),
        ]])
        self.assertEqual(self.levels(draft), [1, 2, 3, 2])
        self.assertIn("缩进", draft.entries[3].note)

    def test_unanchored_titles_remain_flat_and_first_numbered_level_is_safe(self):
        flat = self.recognize([[("Alpha", 30), ("Beta", 80), ("Gamma", 30)]])
        self.assertEqual(self.levels(flat), [1, 1, 1])
        numbered = self.recognize([[("1.1 First visible section", 30), ("1.1.1 Detail", 30)]])
        self.assertEqual(self.levels(numbered), [1, 2])
        self.assertTrue(all(entry.level <= previous.level + 1
                            for previous, entry in zip(numbered.entries, numbered.entries[1:])))

    def test_appendix_children_and_end_matter_do_not_attach_to_last_chapter(self):
        draft = self.recognize([[ (title, 40) for title in (
            "Chapter 1 Alpha", "A section", "Appendix A Auxiliary facts", "A.1 A lemma",
            "Notes and Comments", "Bibliography", "List of Special Symbols", "Index",
        )]])
        self.assertEqual(self.levels(draft), [1, 2, 1, 2, 1, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()
