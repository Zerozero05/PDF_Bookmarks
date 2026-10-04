"""Draft safety, mapping and recognition checks use temporary PDFs only."""

import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import pymupdf

from bookmarks_core import BookmarkError, inspect_pdf
import toc_generation as generation
from toc_generation import Draft, DraftEntry, apply_mapping, generate_toc, load_draft, save_toc, to_toc


class GenerationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="zotero-generation-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.pdf = self.folder / "中文书籍.pdf"
        with pymupdf.open() as document:
            for index in range(8):
                page = document.new_page(width=300, height=400)
                page.insert_text((20, 40), f"Original document page {index + 1}: contents unchanged.")
            document.save(self.pdf)
        self.digest = hashlib.sha256(self.pdf.read_bytes()).hexdigest()

    def draft(self):
        return Draft(self.pdf, 8, [DraftEntry(1, "第一章", 1, 3), DraftEntry(2, "§1.1 基础", 2, 4)], [], {"offset": 2}, "测试", [])

    def confirm(self, draft):
        for entry in draft.entries:
            entry.confirmed = True
        return draft

    def test_unconfirmed_cannot_export(self):
        with self.assertRaisesRegex(BookmarkError, "尚未确认"):
            to_toc(self.draft())

    def test_export_preserves_manual_target_as_direct_page(self):
        draft = self.confirm(self.draft())
        draft.entries[1].pdf_page = 5
        data = to_toc(draft)
        self.assertEqual(data["bookmarks"][0]["page"], 1)
        self.assertEqual(data["bookmarks"][0]["children"][0]["pdf_page"], 5)
        self.assertNotIn("confirmed", str(data))

    def test_mapping_does_not_guess_uncovered_pages_or_change_front_matter(self):
        draft = self.confirm(self.draft())
        draft.entries.insert(0, DraftEntry(1, "前言", None, 1, confirmed=True))
        apply_mapping(draft, {"segments": [{"printed_start": 1, "printed_end": 1, "pdf_start": 3}]})
        self.assertEqual(draft.entries[0].pdf_page, 1)
        self.assertTrue(draft.entries[0].confirmed)
        self.assertEqual(draft.entries[1].pdf_page, 3)
        self.assertFalse(draft.entries[1].confirmed)
        self.assertIsNone(draft.entries[2].pdf_page)

    def test_invalid_segment_mapping_is_rejected_without_partial_mutation(self):
        draft = self.confirm(self.draft())
        with self.assertRaisesRegex(BookmarkError, "重叠"):
            apply_mapping(draft, {"segments": [
                {"printed_start": 1, "printed_end": 2, "pdf_start": 3},
                {"printed_start": 2, "printed_end": 3, "pdf_start": 5},
            ]})
        self.assertEqual(draft.mapping, {"offset": 2})
        self.assertTrue(all(entry.confirmed for entry in draft.entries))

    def test_bad_mapping_types_unknown_keys_and_bounds(self):
        for mapping in ({"offset": True}, {"offset": 2, "extra": 1}, {"segments": []},
                        {"segments": [{"printed_start": 1, "printed_end": 3, "pdf_start": 7}]}):
            with self.subTest(mapping=mapping), self.assertRaises(BookmarkError):
                apply_mapping(self.draft(), mapping)

    def test_out_of_bounds_offset_target_remains_unresolved(self):
        draft = self.draft()
        apply_mapping(draft, {"offset": -1})
        self.assertIsNone(draft.entries[0].pdf_page)
        self.assertEqual(draft.entries[1].pdf_page, 1)

    def test_export_rejects_jumping_levels_and_bad_target(self):
        draft = self.confirm(self.draft())
        draft.entries[1].level = 3
        with self.assertRaisesRegex(BookmarkError, "跳级"):
            to_toc(draft)
        draft.entries[1].level = 2
        draft.entries[1].pdf_page = 0
        with self.assertRaises(BookmarkError):
            to_toc(draft)

    def test_save_roundtrip_is_compatible_and_preserves_pdf_hash(self):
        target = self.folder / "中文书籍.toc.json"
        saved = save_toc(self.confirm(self.draft()), target)
        plan = inspect_pdf(self.pdf, saved)
        self.assertEqual(plan.rows, [[1, "第一章", 3], [2, "§1.1 基础", 4]])
        imported = load_draft(self.pdf, saved)
        self.assertTrue(all(entry.confirmed for entry in imported.entries))
        self.assertEqual(imported.entries[1].printed_page, 2)
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.digest)
        self.assertEqual(list(self.folder.glob(".toc-*")), [])

    def test_save_rejects_pdf_cache_and_same_file_hardlink(self):
        draft = self.confirm(self.draft())
        for target in (self.pdf, self.folder / "jasminum-outline.json", self.folder / "new.txt"):
            with self.subTest(target=target), self.assertRaises(BookmarkError):
                save_toc(draft, target)
        link = self.folder / "same.json"
        import os
        os.link(self.pdf, link)
        with self.assertRaisesRegex(BookmarkError, "同一文件"):
            save_toc(draft, link)
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.digest)

    def test_validation_failure_preserves_existing_json_and_cleans_temp(self):
        target = self.folder / "existing.json"
        target.write_text("ORIGINAL", encoding="utf-8")
        with patch.object(generation, "inspect_pdf", side_effect=BookmarkError("模拟验证失败")):
            with self.assertRaisesRegex(BookmarkError, "模拟验证失败"):
                save_toc(self.confirm(self.draft()), target)
        self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL")
        self.assertEqual(list(self.folder.glob(".toc-*")), [])
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.digest)

    def test_save_rejects_pdf_disguised_as_json(self):
        disguised = self.folder / "renamed.json"
        disguised.write_bytes(self.pdf.read_bytes())
        with self.assertRaisesRegex(BookmarkError, "实际包含 PDF"):
            save_toc(self.confirm(self.draft()), disguised)
        self.assertEqual(hashlib.sha256(disguised.read_bytes()).hexdigest(), self.digest)

    def test_cancel_before_ocr_is_read_only(self):
        cancel = threading.Event()
        cancel.set()
        with patch.object(generation, "_engine") as engine:
            with self.assertRaisesRegex(BookmarkError, "取消"):
                generate_toc(self.pdf, cancel=cancel)
            engine.assert_not_called()
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.digest)

    def test_box_join_handles_separate_page_and_roman_front_page(self):
        lines = generation._group_boxes([
            (15, 10, 200, 30, "Chapter 1 Alpha ......", 0.98),
            (265, 13, 280, 31, "1", 1.0),
            (15, 45, 130, 64, "Preface", 0.99),
            (265, 46, 280, 64, "iv", 1.0),
        ])
        parsed = generation._parse(lines)
        self.assertEqual(parsed[0][:2], ("Chapter 1 Alpha", 1))
        self.assertEqual(parsed[1][:2], ("Preface", None))

    def test_text_pdf_automatic_fixed_mapping_and_no_ocr(self):
        target = self.folder / "text.pdf"
        with pymupdf.open() as document:
            page = document.new_page(width=300, height=400)
            page.insert_text((20, 35), "Contents")
            for y, line in enumerate(("Chapter 1 Alpha ........ 1", "1.1 Beta ........ 2", "Chapter 2 Gamma ........ 3", "2.1 Delta ........ 4")):
                page.insert_text((20, 75 + y * 25), line)
            for index, heading in enumerate(("Chapter 1 Alpha", "1.1 Beta", "Chapter 2 Gamma", "2.1 Delta"), 1):
                page = document.new_page(width=300, height=400)
                page.insert_text((20, 55), heading)
                page.insert_text((20, 100), "This is body text with enough extractable words.")
                page.insert_text((150, 385), str(index))
            document.save(target)
        with patch.object(generation, "_engine", side_effect=AssertionError("unexpected OCR")):
            draft = generate_toc(target, toc_start=1)
        self.assertEqual(draft.toc_pages, [1])
        self.assertEqual(draft.mapping, {"offset": 1})
        self.assertEqual([entry.pdf_page for entry in draft.entries], [1, 2, 3, 4, 5])
        self.assertFalse(any(entry.confirmed for entry in draft.entries))

    def test_prefer_existing_requires_confirmation(self):
        path = self.folder / "outline.pdf"
        with pymupdf.open(self.pdf) as document:
            document.set_toc([[1, "Existing outline", 3]])
            document.save(path)
        draft = generate_toc(path, prefer_existing=True)
        self.assertEqual(draft.entries[0].pdf_page, 3)
        self.assertFalse(draft.entries[0].confirmed)


if __name__ == "__main__":
    unittest.main()
