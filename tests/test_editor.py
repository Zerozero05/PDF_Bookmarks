"""Directory editor integration checks use only temporary PDFs and JSON files."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import pymupdf
from tkinterdnd2 import TkinterDnD

import toc_editor
from toc_generation import Draft, DraftEntry


class EditorInputTests(unittest.TestCase):
    def test_unknown_pages_stay_unknown_and_zero_is_rejected(self):
        self.assertIsNone(toc_editor.optional_page("", "页码"))
        self.assertEqual(toc_editor.optional_page(" 12 ", "页码"), 12)
        for value in ("0", "-2", "abc", "1.2"):
            with self.assertRaises(ValueError):
                toc_editor.optional_page(value, "页码")

    def test_segment_editor_accepts_chinese_separator_and_rejects_overlap(self):
        result = toc_editor.parse_segments("101,200,114\n1，100，13")
        self.assertEqual(result["segments"][0], {"printed_start": 1, "printed_end": 100, "pdf_start": 13})
        for text in ("", "1,2", "1,2,", "3,2,1", "1,10,1\n10,20,11"):
            with self.assertRaises(ValueError):
                toc_editor.parse_segments(text)


class EditorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="zotero-toc-editor-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "中文 教材.pdf"
        with pymupdf.open() as document:
            for index in range(4):
                document.new_page().insert_text((72, 72), f"Page {index + 1}")
            document.save(self.pdf)
        self.source_sha = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.root = tk.Tk()
        self.root.withdraw()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.errors = []
        self.error_patch = patch.object(toc_editor.messagebox, "showerror", side_effect=lambda title, message, **kwargs: self.errors.append(message))
        self.error_patch.start()
        self.editor = toc_editor.open_editor(self.root, self.executor, self.pdf)
        self.root.update_idletasks()

    def tearDown(self):
        self.editor.close()
        self.executor.shutdown(wait=True)
        self.root.update_idletasks()
        self.root.destroy()
        self.error_patch.stop()
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.source_sha)
        self.temporary.cleanup()

    def draft(self, confirmed=False, target=2):
        return Draft(self.pdf, 4, [DraftEntry(1, "第一章 基础", 1, target, "高", "请核对", confirmed)],
                     [1], {"offset": 1}, "测试目录", [])

    def load(self, draft=None):
        self.editor.draft = draft or self.draft()
        self.editor._load_mapping()
        self.editor._refresh()

    def spin(self, condition, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("编辑器操作未在时限内完成。")

    def test_widgets_are_children_of_their_scroll_frames(self):
        self.assertEqual(self.editor.tree.winfo_manager(), "grid")
        self.assertEqual(self.editor.canvas.winfo_manager(), "grid")
        self.assertEqual(self.editor.tree.winfo_parent(), str(self.editor.tree.master))
        self.assertEqual(self.editor.canvas.winfo_parent(), str(self.editor.canvas.master))

    def test_edit_revokes_confirmation_and_checks_target_range(self):
        self.load(self.draft(confirmed=True))
        self.editor.title.set("第一章 校正标题")
        self.assertFalse(self.editor.confirmed.get())
        self.editor.update_entry()
        self.assertFalse(self.editor.draft.entries[0].confirmed)
        self.assertEqual(self.editor.draft.entries[0].confidence, "手工校正")
        self.editor.target.set("5")
        self.editor.confirmed.set(True)
        self.editor.update_entry()
        self.assertIn("不能超过", self.errors[-1])
        self.assertEqual(self.editor.draft.entries[0].pdf_page, 2)

    def test_unknown_target_cannot_be_confirmed_or_saved(self):
        self.load(self.draft(target=None))
        self.editor.confirmed.set(True)
        self.editor.update_entry()
        self.assertIn("未知", self.errors[-1])
        self.editor.confirmed.set(False)
        with patch.object(toc_editor.filedialog, "asksaveasfilename") as dialog:
            self.editor.save()
            dialog.assert_not_called()
        self.assertIn("未知", self.errors[-1])

    def test_confirm_all_requires_explicit_yes(self):
        self.load()
        with patch.object(toc_editor.messagebox, "askyesno", return_value=False) as question:
            self.editor.confirm_all()
            question.assert_called_once()
        self.assertFalse(self.editor.draft.entries[0].confirmed)
        with patch.object(toc_editor.messagebox, "askyesno", return_value=True):
            self.editor.confirm_all()
        self.assertTrue(self.editor.draft.entries[0].confirmed)

    def test_mapping_changes_targets_and_revokes_confirmation(self):
        self.load(self.draft(confirmed=True))
        self.editor.offset.set("2")
        self.editor.apply_offset()
        entry = self.editor.draft.entries[0]
        self.assertEqual(entry.pdf_page, 3)
        self.assertFalse(entry.confirmed)
        self.editor.segments.insert("1.0", "1,4,3")
        self.editor.apply_segments()
        self.assertIn("超出", self.errors[-1])
        self.assertEqual(entry.pdf_page, 3)

    def test_existing_json_import_is_worker_only_and_read_only(self):
        toc = self.pdf.with_suffix(".toc.json")
        toc.write_text(json.dumps({"version": 1, "bookmarks": [{"title": "目录", "pdf_page": 1}]}), encoding="utf-8")
        original = toc.read_bytes()
        self.editor.json.set(str(toc))
        self.editor.import_json()
        self.spin(lambda: self.editor.draft is not None and not self.editor.busy)
        self.assertEqual(self.editor.draft.entries[0].title, "目录")
        self.assertEqual(toc.read_bytes(), original)

    def test_generate_and_preview_share_the_supplied_worker(self):
        calls = []
        main_thread = threading.get_ident()
        actual_render = toc_editor.render_page

        def generate(pdf, **kwargs):
            calls.append(("generate", threading.get_ident()))
            kwargs["progress"]("测试识别进度")
            return self.draft()

        def render(*args, **kwargs):
            calls.append(("render", threading.get_ident()))
            return actual_render(*args, **kwargs)

        with patch.object(toc_editor, "generate_toc", side_effect=generate), patch.object(toc_editor, "render_page", side_effect=render):
            self.editor.generate()
            self.spin(lambda: self.editor._photo is not None)
        self.assertTrue(any(name == "generate" for name, _ in calls))
        self.assertTrue(any(name == "render" for name, _ in calls))
        self.assertEqual(len({identity for _, identity in calls}), 1)
        self.assertNotEqual(calls[0][1], main_thread)

    def test_saving_rejects_original_pdf_filename(self):
        self.load(self.draft(confirmed=True))
        with patch.object(toc_editor.filedialog, "asksaveasfilename", return_value=str(self.pdf)), patch.object(toc_editor, "save_toc") as save:
            self.editor.save_as()
            save.assert_not_called()
        self.assertIn("不能覆盖 PDF", self.errors[-1])

    def test_save_closes_workbench_before_callback(self):
        self.load(self.draft(confirmed=True))
        target = self.pdf.with_suffix(".toc.json")
        callback = Mock(side_effect=lambda pdf, toc: self.assertTrue(self.editor.closed))
        self.editor.on_saved = callback
        self.editor.save()
        self.spin(lambda: self.editor.closed)
        callback.assert_called_once_with(self.pdf, target)
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(data["bookmarks"][0]["title"], "第一章 基础")

    def test_close_cancels_generation_without_creating_files(self):
        entered, cancelled = threading.Event(), threading.Event()

        def generate(pdf, **kwargs):
            entered.set()
            if kwargs["cancel"].wait(3):
                cancelled.set()
            return self.draft()

        with patch.object(toc_editor, "generate_toc", side_effect=generate):
            self.editor.generate()
            self.assertTrue(entered.wait(2))
            self.editor.close()
            self.assertTrue(cancelled.wait(2))
        self.assertEqual(list(self.folder.iterdir()), [self.pdf])


class MainWindowEditorTests(unittest.TestCase):
    def test_saved_json_returns_to_preview_and_preserves_other_batch_items(self):
        from bookmarks_gui import BookmarkWindow

        with tempfile.TemporaryDirectory(prefix="zotero-editor-return-") as temporary:
            folder = Path(temporary)
            pdfs = [folder / "第一本.pdf", folder / "第二本.pdf"]
            for pdf in pdfs:
                with pymupdf.open() as document:
                    document.new_page()
                    document.new_page()
                    document.save(pdf)
            originals = [pdf.read_bytes() for pdf in pdfs]
            second_toc = pdfs[1].with_suffix(".toc.json")
            second_toc.write_text(json.dumps({"version": 1, "bookmarks": [{"title": "原目录", "pdf_page": 2}]}), encoding="utf-8")
            root = TkinterDnD.Tk()
            root.withdraw()
            main = BookmarkWindow(root, settings_path=folder / "isolated-settings.json")
            try:
                main._handle_drop_paths([pdfs[0], pdfs[1], second_toc])
                iid = next(iid for iid, item in main.items.items() if Path(item["pdf_path"]) == pdfs[0])
                main.file_tree.selection_set(iid)
                main._open_editor(True)
                editor = main.editor
                self.assertIs(editor.executor, main.executor)
                editor.draft = Draft(pdfs[0], 2, [DraftEntry(1, "第一章 新目录", 1, 2, "手工", "", True)],
                                     [1], {"offset": 1}, "测试", [])
                editor._load_mapping()
                editor._refresh()
                first_toc = pdfs[0].with_suffix(".toc.json")
                with patch.object(toc_editor.filedialog, "asksaveasfilename") as choose:
                    editor.save()
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        root.update()
                        if editor.closed and not main.busy and all(item["ready"] for item in main.items.values()):
                            break
                        time.sleep(0.01)
                    else:
                        self.fail("保存目录后主窗口未完成预览。")
                    choose.assert_not_called()
                self.assertEqual(len(main.items), 2)
                self.assertEqual(main.mode.get(), "dropped")
                pairs = {Path(item["pdf_path"]): Path(item["toc_path"]) for item in main.items.values()}
                self.assertEqual(pairs, {pdfs[0]: first_toc, pdfs[1]: second_toc})
                self.assertEqual([pdf.read_bytes() for pdf in pdfs], originals)
            finally:
                if main.editor is not None:
                    main.editor.close()
                main.executor.shutdown(wait=True)
                main._close()


if __name__ == "__main__":
    unittest.main()
