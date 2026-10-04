"""One directory workbench keeps generation and editing in the same window."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pymupdf
from tkinterdnd2 import COPY, REFUSE_DROP, TkinterDnD

import bookmarks_gui
import toc_editor
from toc_generation import Draft, DraftEntry


class DirectoryWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="zotero-directory-workbench-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "中文 教材.pdf"
        with pymupdf.open() as document:
            for index in range(4):
                document.new_page().insert_text((72, 72), f"Page {index + 1}")
            document.save(self.pdf)
        self.original_hash = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.toc = self.folder / "另一个目录" / "需要编辑的目录.json"
        self.toc.parent.mkdir()
        self.toc.write_text(json.dumps({"version": 1, "bookmarks": [
            {"title": "第一章 原标题", "pdf_page": 2},
        ]}, ensure_ascii=False), encoding="utf-8")
        self.original_json = self.toc.read_bytes()
        self.root = TkinterDnD.Tk()
        self.root.geometry("1100x860+32000+32000")
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.editor = self.main = None
        self.errors = []
        self.error_patch = patch.object(toc_editor.messagebox, "showerror",
                                       side_effect=lambda title, message, **kw: self.errors.append(message))
        self.error_patch.start()

    def tearDown(self):
        self.root.update_idletasks()
        if self.editor is not None:
            self.editor.close()
        if self.main is not None:
            self.main._close()
            self.main.executor.shutdown(wait=True)
        self.executor.shutdown(wait=True)
        try:
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass
        self.error_patch.stop()
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.original_hash)
        self.assertEqual(self.toc.read_bytes(), self.original_json)
        self.temporary.cleanup()

    def open(self, **kwargs):
        self.editor = toc_editor.open_editor(self.root, self.executor, **kwargs)
        self.editor.window.geometry("1240x900+32000+32000")
        self.root.update_idletasks()
        return self.editor

    def spin(self, condition, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("目录工作台未在时限内完成操作。")

    def visible_texts(self, widget):
        result = []
        for child in widget.winfo_children():
            if child.winfo_ismapped() and "text" in child.keys():
                result.append(str(child.cget("text")))
            result.extend(self.visible_texts(child))
        return result

    def test_main_has_one_visible_directory_entry(self):
        self.main = bookmarks_gui.BookmarkWindow(self.root, settings_path=self.folder / "settings.json")
        self.root.geometry("1100x860+32000+32000")
        self.root.update()
        texts = self.visible_texts(self.root)
        self.assertEqual(texts.count("生成 / 编辑目录…"), 1)
        self.assertNotIn("生成目录 JSON…", texts)
        self.assertNotIn("编辑目录 JSON…", texts)
        self.assertEqual(self.main.directory_button.cget("text"), "生成 / 编辑目录…")

    def test_empty_main_entry_opens_workbench_without_file_dialog(self):
        self.main = bookmarks_gui.BookmarkWindow(self.root, settings_path=self.folder / "settings.json")
        with patch.object(bookmarks_gui.filedialog, "askopenfilename") as choose, \
                patch.object(toc_editor, "open_editor", return_value=None) as opened:
            self.main._open_editor()
        choose.assert_not_called()
        opened.assert_called_once()
        self.assertIsNone(opened.call_args.kwargs["pdf_path"])
        self.assertIsNone(opened.call_args.kwargs["toc_path"])

    def test_generate_and_edit_share_one_window_with_distinct_source_tabs(self):
        editor = self.open(pdf_path=self.pdf)
        self.root.update()
        self.assertEqual(editor.window.title(), "目录工作台：生成与编辑 JSON")
        self.assertEqual([editor.source_tabs.tab(tab, "text") for tab in editor.source_tabs.tabs()],
                         ["从 PDF 生成", "编辑已有 JSON"])
        self.assertEqual(editor.source_tabs.index("current"), 0)
        texts = self.visible_texts(editor.window)
        self.assertIn("自动识别目录", texts)
        self.assertNotIn("载入 JSON", texts)
        tree, canvas, window = editor.tree, editor.canvas, editor.window
        editor.source_tabs.select(1)
        self.root.update()
        texts = self.visible_texts(editor.window)
        self.assertIn("载入 JSON", texts)
        self.assertNotIn("自动识别目录", texts)
        self.assertIs(editor.tree, tree)
        self.assertIs(editor.canvas, canvas)
        self.assertIs(editor.window, window)

    def test_prefilled_json_selects_edit_and_auto_imports_read_only(self):
        editor = self.open(pdf_path=self.pdf, toc_path=self.toc)
        self.spin(lambda: editor.draft is not None and not editor.busy)
        self.assertEqual(editor.source_tabs.index("current"), 1)
        self.assertEqual(editor.draft.entries[0].title, "第一章 原标题")
        self.assertEqual(len(editor.tree.get_children()), 1)
        self.assertFalse(self.errors)

    def test_switching_tabs_preserves_loaded_edits_and_does_not_run_ocr(self):
        editor = self.open(pdf_path=self.pdf, toc_path=self.toc)
        self.spin(lambda: editor.draft is not None and not editor.busy)
        draft = editor.draft
        editor.title.set("第一章 修改后的标题")
        editor.update_entry()
        with patch.object(toc_editor, "generate_toc") as recognize, \
                patch.object(toc_editor, "load_draft", wraps=toc_editor.load_draft) as load:
            editor.source_tabs.select(0)
            self.root.update()
            editor.source_tabs.select(1)
            self.root.update()
            recognize.assert_not_called()
            load.assert_not_called()
        self.assertIs(editor.draft, draft)
        self.assertEqual(editor.draft.entries[0].title, "第一章 修改后的标题")

    def test_browsing_json_in_edit_tab_auto_imports(self):
        editor = self.open(pdf_path=self.pdf, mode="edit")
        with patch.object(toc_editor.filedialog, "askopenfilename", return_value=str(self.toc)):
            editor._choose_json()
        self.spin(lambda: editor.draft is not None and not editor.busy)
        self.assertEqual(editor.draft.entries[0].title, "第一章 原标题")

    def test_browsing_pdf_after_json_auto_imports(self):
        editor = self.open(toc_path=self.toc, mode="edit")
        with patch.object(toc_editor.filedialog, "askopenfilename", return_value=str(self.pdf)):
            editor._choose_pdf()
        self.spin(lambda: editor.draft is not None and not editor.busy)
        self.assertEqual(Path(editor.draft.pdf_path), self.pdf)
        self.assertEqual(editor.draft.entries[0].pdf_page, 2)

    def test_edit_save_defaults_to_imported_json_folder_and_name(self):
        editor = self.open(pdf_path=self.pdf, toc_path=self.toc)
        self.spin(lambda: editor.draft is not None and not editor.busy)
        self.assertEqual(editor._save_target(), self.toc)
        with patch.object(toc_editor.filedialog, "asksaveasfilename") as choose, \
                patch.object(toc_editor.messagebox, "askyesno", return_value=False):
            editor.save()
        choose.assert_not_called()

    def test_new_generation_resets_save_default_without_modifying_existing_json(self):
        editor = self.open(pdf_path=self.pdf, toc_path=self.toc)
        self.spin(lambda: editor.draft is not None and not editor.busy)
        editor.source_tabs.select(0)
        self.root.update()
        generated = Draft(self.pdf, 4, [DraftEntry(1, "新识别的章节", 1, 2, "高", "", True)],
                          [1], {"offset": 1}, "测试识别", [])
        with patch.object(toc_editor, "generate_toc", return_value=generated):
            editor.generate()
            self.spin(lambda: editor.draft is generated and not editor.busy)
        self.assertEqual(editor._save_target(), self.pdf.with_suffix(".toc.json"))

    def test_pdf_only_drop_selects_generation_without_running_ocr(self):
        editor = self.open(mode="edit")
        with patch.object(toc_editor, "generate_toc") as recognize:
            self.assertTrue(editor._handle_drop_paths([self.pdf]))
            self.root.update()
            recognize.assert_not_called()
        self.assertEqual(Path(editor.pdf.get()), self.pdf)
        self.assertEqual(editor.source_tabs.index("current"), 0)
        self.assertIsNone(editor.draft)

    def test_json_drop_with_current_pdf_imports_and_previews(self):
        editor = self.open(pdf_path=self.pdf)
        self.assertTrue(editor._handle_drop_paths([self.toc]))
        self.spin(lambda: editor.draft is not None and not editor.busy and editor._photo is not None)
        self.assertEqual(editor.source_tabs.index("current"), 1)
        self.assertEqual(editor.draft.entries[0].title, "第一章 原标题")
        self.assertGreater(editor._photo.width(), 0)

    def test_tcl_drop_preserves_chinese_spaces_and_arbitrary_json_filename(self):
        editor = self.open()
        event = SimpleNamespace(data=" ".join("{" + str(path) + "}" for path in (self.toc, self.pdf)))
        self.assertEqual(editor._on_drop(event), COPY)
        self.spin(lambda: editor.draft is not None and not editor.busy)
        self.assertEqual(Path(editor.pdf.get()), self.pdf)
        self.assertEqual(Path(editor.json.get()), self.toc)
        self.assertEqual(editor.source_tabs.index("current"), 1)
        self.assertEqual(editor.draft.entries[0].title, "第一章 原标题")

    def test_json_first_then_pdf_drop_loads_existing_json(self):
        editor = self.open()
        self.assertTrue(editor._handle_drop_paths([self.toc]))
        self.root.update()
        self.assertEqual(editor.source_tabs.index("current"), 1)
        self.assertIsNone(editor.draft)
        self.assertTrue(editor._handle_drop_paths([self.pdf]))
        self.spin(lambda: editor.draft is not None and not editor.busy)
        self.assertEqual(Path(editor.json.get()), self.toc)
        self.assertEqual(editor.draft.entries[0].title, "第一章 原标题")

    def test_multiple_pdf_drop_refuses_without_replacing_edited_draft(self):
        editor = self.open(pdf_path=self.pdf, toc_path=self.toc)
        self.spin(lambda: editor.draft is not None and not editor.busy)
        draft = editor.draft
        editor.title.set("保留未保存的修改")
        editor.update_entry()
        other = self.folder / "其他 图书.pdf"
        other.write_bytes(self.pdf.read_bytes())
        event = SimpleNamespace(data=" ".join("{" + str(path) + "}" for path in (other, self.pdf)))
        self.assertEqual(editor._on_drop(event), REFUSE_DROP)
        self.assertIs(editor.draft, draft)
        self.assertEqual(editor.draft.entries[0].title, "保留未保存的修改")
        self.assertEqual(Path(editor.pdf.get()), self.pdf)

    def test_busy_drop_is_refused_without_changing_sources(self):
        editor = self.open(pdf_path=self.pdf)
        editor.busy = True
        try:
            event = SimpleNamespace(data="{" + str(self.toc) + "}")
            self.assertEqual(editor._on_drop(event), REFUSE_DROP)
            self.assertFalse(editor._handle_drop_paths([self.toc]))
            self.assertEqual(Path(editor.pdf.get()), self.pdf)
            self.assertEqual(editor.json.get(), "")
            self.assertIsNone(editor.draft)
        finally:
            editor.busy = False

    def test_pdf_entry_tree_canvas_and_tabs_have_native_drop_bindings(self):
        editor = self.open(pdf_path=self.pdf)
        self.root.update()
        pdf_entry = next(control for control in editor._controls
                         if control.winfo_class() == "TEntry"
                         and str(control.cget("textvariable")) == str(editor.pdf))
        for target in (pdf_entry, editor.tree, editor.canvas, editor.source_tabs):
            with self.subTest(widget=target.winfo_class()):
                types = self.root.tk.splitlist(self.root.tk.call("bind", target._w, "<<DropTargetTypes>>"))
                self.assertIn("CF_HDROP", types)
                self.assertTrue(self.root.tk.call("bind", target._w, "<<Drop>>"))
        target = editor.canvas
        x, y = target.winfo_rootx() + 20, target.winfo_rooty() + 40
        data = self.root.tk.call("list", str(self.toc))
        self.root.tk.call("tkdnd::olednd::HandleDragEnter", target._w,
                          ("CF_HDROP",), ("copy",), (), x, y, (1,), data)
        self.assertEqual(self.root.tk.call("tkdnd::olednd::HandleDrop", target._w,
                                           (), x, y, "CF_HDROP", data), COPY)
        self.spin(lambda: editor.draft is not None and not editor.busy)
        self.assertEqual(editor.draft.entries[0].title, "第一章 原标题")

    def test_both_source_tabs_and_primary_actions_fit_default_and_minimum_sizes(self):
        editor = self.open(pdf_path=self.pdf)
        for width, height in ((1240, 900), (1000, 720)):
            for index in (0, 1):
                with self.subTest(size=(width, height), source_tab=index):
                    editor.window.geometry(f"{width}x{height}+20000+20000")
                    editor.source_tabs.select(index)
                    self.root.update()
                    names = {"保存 JSON 并返回", "确认所有已核对项…", "更新选中项",
                             "自动识别目录" if index == 0 else "载入 JSON"}
                    found = set()
                    for control in editor._controls:
                        if "text" not in control.keys() or str(control.cget("text")) not in names:
                            continue
                        self.assertTrue(control.winfo_ismapped())
                        found.add(str(control.cget("text")))
                        x = control.winfo_rootx() - editor.window.winfo_rootx()
                        y = control.winfo_rooty() - editor.window.winfo_rooty()
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, 0)
                        self.assertLessEqual(x + control.winfo_width(), editor.window.winfo_width())
                        self.assertLessEqual(y + control.winfo_height(), editor.window.winfo_height())
                    self.assertEqual(found, names)
                    for target in (editor.tree, editor.canvas):
                        self.assertTrue(target.winfo_ismapped())
                        self.assertGreater(target.winfo_width(), 300)
                        self.assertGreater(target.winfo_height(), 150)
                        self.assertIs(self.root.winfo_containing(target.winfo_rootx() + 20,
                                                                 target.winfo_rooty() + 40), target)


if __name__ == "__main__":
    unittest.main()
