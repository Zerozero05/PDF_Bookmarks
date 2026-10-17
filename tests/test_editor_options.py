"""Directory choices preserve manual titles, hierarchy and target-page evidence."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

import pymupdf

import toc_editor
from toc_generation import Draft, DraftEntry, _format_generated_titles


class EditorOptionsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-editor-options-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "目录选项.pdf"
        with pymupdf.open() as doc:
            for _ in range(6):
                doc.new_page()
            doc.save(self.pdf)
        self.original = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.root = tk.Tk()
        self.root.withdraw()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.editor = toc_editor.open_editor(self.root, self.executor, self.pdf)
        self.editor.window.geometry("1000x720+32000+32000")
        self.editor.window.attributes("-topmost", False)
        self.errors = []
        self.dialogs = patch.object(toc_editor.messagebox, "showerror", side_effect=lambda *args, **kw: self.errors.append(args))
        self.dialogs.start()
        self.root.update()

    def tearDown(self):
        self.editor.close()
        self.executor.shutdown(wait=True)
        self.root.update_idletasks()
        self.root.destroy()
        self.dialogs.stop()
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.original)
        self.assertEqual(self.errors, [])
        self.temporary.cleanup()

    def spin(self, condition):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("目录选项操作未完成。")

    def generated(self):
        entries = [DraftEntry(1, "目录", None, 1), DraftEntry(1, "第一章基础", 1, 2),
                   DraftEntry(2, "§1.1基本概念", 1, 2), DraftEntry(2, "更多概念", 2, 3),
                   DraftEntry(1, "第二章极限", 3, 4), DraftEntry(2, "定义", 3, 4)]
        return _format_generated_titles(Draft(self.pdf, 6, entries, [1], {"offset": 1}, "测试识别", []))

    def load_auto(self):
        with patch.object(toc_editor, "generate_toc", return_value=self.generated()) as generate:
            self.editor.generate()
            self.spin(lambda: self.editor.draft is not None and not self.editor.busy)
        return generate

    def choose(self, style):
        label = next(label for label, value in toc_editor.SECTION_STYLES.items() if value == style)
        self.editor.section_style.set(label)
        self.editor._section_style_changed()
        self.root.update()

    def titles(self):
        return [entry.title for entry in self.editor.draft.entries]

    def test_generation_uses_layout_and_selected_numbering_and_readonly_controls(self):
        self.editor.column_mode.set("双栏")
        self.choose("section")
        generate = self.load_auto()
        self.assertEqual(generate.call_args.kwargs["column_mode"], "double")
        self.assertEqual(self.titles()[2:4], ["1. 基本概念", "2. 更多概念"])
        self.assertEqual(self.titles()[-1], "1. 定义")
        self.assertFalse(any(entry.confirmed for entry in self.editor.draft.entries))
        for control in self.editor._controls:
            if isinstance(control, ttk.Combobox):
                self.assertEqual(str(control.cget("state")), "readonly")

    def test_default_chapter_section_style_applies_to_first_generated_draft(self):
        self.assertEqual(toc_editor.SECTION_STYLES[self.editor.section_style.get()], "chapter_section")
        for original, expected in (("1. Basics", "1.1 Basics"),
                                   ("第一节基本概念", "1.1 基本概念"),
                                   ("Section 2 Methods", "1.2 Methods")):
            with self.subTest(original=original):
                draft = _format_generated_titles(Draft(self.pdf, 6,
                    [DraftEntry(1, "第一章基础", 1, 2), DraftEntry(2, original, 2, 3)],
                    [1], {"offset": 1}, "测试识别", []))
                with patch.object(toc_editor, "generate_toc", return_value=draft):
                    self.editor.generate()
                    self.spin(lambda: self.editor.draft is draft and not self.editor.busy)
                self.assertEqual(self.titles(), ["第一章 基础", expected])
                self.assertEqual([(entry.level, entry.pdf_page) for entry in draft.entries], [(1, 2), (2, 3)])
                self.assertFalse(any(entry.confirmed for entry in draft.entries))

    def test_repeated_choices_use_original_titles_without_changing_targets_or_levels(self):
        self.load_auto()
        default = self.titles()
        evidence = [(e.level, e.printed_page, e.pdf_page) for e in self.editor.draft.entries]
        for _ in range(2):
            self.choose("section")
            self.assertEqual(self.titles()[2:4], ["1. 基本概念", "2. 更多概念"])
            self.choose("preserve")
            self.assertEqual(self.titles()[2:4], ["1.1 基本概念", "更多概念"])
            self.choose("chapter_section")
            self.assertEqual(self.titles(), default)
        self.assertEqual([(e.level, e.printed_page, e.pdf_page) for e in self.editor.draft.entries], evidence)

    def test_manual_title_is_committed_and_protected_when_changing_numbering(self):
        self.load_auto()
        self.editor.tree.selection_set("2")
        self.editor.tree.focus("2")
        self.editor._selected()
        self.editor.title.set("§自定编号 我的手工标题")
        self.choose("section")
        self.assertEqual(self.titles()[2], "§自定编号 我的手工标题")
        self.choose("preserve")
        self.choose("chapter_section")
        self.assertEqual(self.titles()[2], "§自定编号 我的手工标题")
        self.assertEqual(self.titles()[3], "1.2 更多概念")

    def test_reordered_or_deleted_entries_keep_their_own_source_titles(self):
        self.load_auto()
        self.editor.tree.selection_set("3")
        self.editor.tree.focus("3")
        self.editor._selected()
        self.editor.move_entry(-1)
        self.choose("preserve")
        self.assertEqual(self.titles()[2:4], ["更多概念", "1.1 基本概念"])
        self.editor.tree.selection_set("2")
        self.editor.tree.focus("2")
        self.editor._selected()
        self.editor.delete_entry()
        self.choose("section")
        self.assertEqual(self.titles()[2], "1. 基本概念")
        self.assertEqual(self.titles()[-1], "1. 定义")

    def test_imported_json_is_not_reformatted_by_numbering_choices(self):
        toc = self.folder / "original.json"
        data = {"version": 1, "bookmarks": [{"title": "第一章原样", "pdf_page": 2,
                "children": [{"title": "§1.1不加空格", "pdf_page": 3}]}]}
        toc.write_text(json.dumps(data, ensure_ascii=False), encoding="utf8")
        original = toc.read_bytes()
        self.editor.json.set(str(toc))
        self.editor.import_json()
        self.spin(lambda: self.editor.draft is not None and not self.editor.busy)
        for style in ("section", "preserve", "chapter_section"):
            self.choose(style)
            self.assertEqual(self.titles(), ["第一章原样", "§1.1不加空格"])
            self.assertTrue(all(entry.confirmed for entry in self.editor.draft.entries))
        self.assertEqual(toc.read_bytes(), original)

    def test_minimum_window_keeps_choices_zoom_and_save_visible(self):
        self.root.update()
        wanted = {"放大", "缩小", "100%", "保存 JSON 并返回"}
        found = set()

        def inspect(widget):
            if "text" in widget.keys() and str(widget.cget("text")) in wanted:
                self.assertTrue(widget.winfo_ismapped())
                self.assertLess(widget.winfo_rooty() + widget.winfo_height(),
                                self.editor.window.winfo_rooty() + self.editor.window.winfo_height() + 2)
                found.add(str(widget.cget("text")))
            for child in widget.winfo_children():
                inspect(child)

        inspect(self.editor.window)
        self.assertEqual(found, wanted)
        self.assertGreater(self.editor.canvas.winfo_height(), 100)


if __name__ == "__main__":
    unittest.main()
