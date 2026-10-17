"""One workspace keeps bookmark review and unfinished directory edits isolated."""

from copy import deepcopy
from dataclasses import asdict
import gc
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

import pymupdf
from tkinterdnd2 import COPY, REFUSE_DROP, TkinterDnD

import bookmarks_gui
import gui_support
import toc_editor
from toc_generation import Draft, DraftEntry


class WorkspaceTabTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workspace-tabs-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "合成 教材.pdf"
        with pymupdf.open() as document:
            for number in range(4):
                document.new_page().insert_text((72, 72), f"Synthetic page {number + 1}")
            document.save(self.pdf)
        self.pdf_hash = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.settings = self.folder / "独立设置" / "settings.json"
        self.errors = []
        self.dialogs = [
            patch.object(toc_editor.messagebox, "showerror", side_effect=lambda *args, errors=self.errors, **kw: errors.append(args)),
            patch.object(toc_editor.messagebox, "showinfo"),
            patch.object(toc_editor.messagebox, "showwarning"),
            patch.object(toc_editor.messagebox, "askyesno", return_value=True),
            patch.object(toc_editor.messagebox, "askyesnocancel", return_value=False),
        ]
        for dialog in self.dialogs:
            dialog.start()
        self.root = TkinterDnD.Tk()
        self.root.withdraw()
        self.callback_errors = []
        self.root.report_callback_exception = lambda *args, errors=self.callback_errors: errors.append(args)
        self.main = bookmarks_gui.BookmarkWindow(self.root, settings_path=self.settings)
        self.main.pdf.set(str(self.pdf))
        self.extra_editors = []
        self.addCleanup(self.cleanup)
        self.root.update()

    def cleanup(self):
        for editor in self.extra_editors + ([self.main.editor] if self.main is not None else []):
            if editor is not None and not editor.closed:
                editor.busy = False
                editor.auto_save.set(False)
                editor.on_settings_changed = None
                editor.close()
        if self.main is not None:
            self.main.executor.shutdown(wait=True, cancel_futures=True)
            if not self.main.closed:
                self.main.busy = False
                self.main._close()
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass
        for dialog in reversed(self.dialogs):
            dialog.stop()
        self.dialogs.clear()
        del self.root.report_callback_exception
        try:
            self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.pdf_hash)
            self.assertFalse(self.pdf.with_suffix(".toc.json").exists())
            self.assertEqual(self.callback_errors, [])
        finally:
            self.temporary.cleanup()
            # Dialog mock cycles may hold Tk parents; release them on the Tk thread.
            gc.collect()

    def spin(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("同窗标签页操作未在时限内完成。")

    def editor(self):
        self.main._open_editor()
        self.root.update()
        self.assertIsNotNone(self.main.editor)
        return self.main.editor

    def load_sample(self, editor):
        editor.draft = Draft(self.pdf, 4, [
            DraftEntry(1, "第一章 基础", 1, 1, "高", "已核对章首", True),
            DraftEntry(2, "1.1 基本概念", 2, 2, "低", "待核对", False),
        ], [1], {"offset": 0}, "合成目录", [])
        editor.auto_save.set(False)
        editor._refresh(selected=1)
        self.spin(lambda: not editor.busy and editor._photo is not None)
        return editor.draft

    def test_workspace_starts_with_two_pages_without_opening_an_editor(self):
        self.assertIsInstance(self.main.workspace_tabs, ttk.Notebook)
        self.assertEqual(set(self.main.workspace_tabs.tabs()),
                         {str(self.main.main_page), str(self.main.editor_page)})
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.assertIsNone(self.main.editor)
        self.assertFalse(any(isinstance(child, tk.Toplevel) for child in self.root.winfo_children()))

    def test_open_editor_embeds_a_frame_and_keeps_the_shared_worker(self):
        editor = self.editor()
        self.assertIsInstance(editor.window, ttk.Frame)
        self.assertIs(editor.window.winfo_toplevel(), self.root)
        self.assertIs(editor.executor, self.main.executor)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))
        self.assertTrue(str(editor.window).startswith(str(self.main.editor_page) + "."))
        self.assertFalse(any(isinstance(child, tk.Toplevel) for child in self.root.winfo_children()))
        self.assertEqual(editor.store.path_for(self.pdf).parent, self.settings.parent / "editor_drafts")

    def test_selecting_editor_tab_lazily_creates_the_editor(self):
        self.main.workspace_tabs.select(self.main.editor_page)
        self.spin(lambda: self.main.editor is not None)
        self.assertFalse(self.main.editor.closed)
        self.assertIs(self.main.editor.window.winfo_toplevel(), self.root)

    def test_repeated_open_reuses_the_existing_editor(self):
        editor = self.editor()
        self.main.workspace_tabs.select(self.main.main_page)
        self.main._open_editor()
        self.root.update()
        self.assertIs(self.main.editor, editor)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))

    def test_switching_tabs_preserves_unfinished_fields_model_and_preview(self):
        editor = self.editor()
        model = self.load_sample(editor)
        original = deepcopy(asdict(model))
        editor.level.set("未填完")
        editor.title.set("正在编辑但尚未提交的标题")
        editor._cancel_edit_timer()
        editor.canvas.yview_moveto(.3)
        photo, page, scale = editor._photo, editor.preview_page.get(), editor._preview_scale
        for page_frame in (self.main.main_page, self.main.editor_page, self.main.main_page, self.main.editor_page):
            self.main.workspace_tabs.select(page_frame)
            self.root.update()
        self.assertIs(self.main.editor, editor)
        self.assertIs(editor.draft, model)
        self.assertEqual(asdict(model), original)
        self.assertEqual(editor.level.get(), "未填完")
        self.assertEqual(editor.title.get(), "正在编辑但尚未提交的标题")
        self.assertIs(editor._photo, photo)
        self.assertEqual((editor.preview_page.get(), editor._preview_scale), (page, scale))
        self.assertTrue(editor._dirty_fields)
        self.assertFalse(self.errors)

    def test_closing_editor_returns_to_main_without_destroying_root(self):
        editor = self.editor()
        editor.close()
        self.root.update()
        self.assertTrue(editor.closed)
        self.assertFalse(editor.window.winfo_exists())
        self.assertTrue(self.root.winfo_exists())
        self.assertFalse(self.main.closed)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))

    def test_selecting_tab_after_editor_close_creates_a_new_frame(self):
        previous = self.editor()
        previous.close()
        self.root.update()
        self.main.workspace_tabs.select(self.main.editor_page)
        self.spin(lambda: self.main.editor is not previous and self.main.editor is not None)
        self.assertFalse(self.main.editor.closed)
        self.assertIs(self.main.editor.window.winfo_toplevel(), self.root)

    def test_standalone_editor_api_still_opens_a_toplevel(self):
        editor = toc_editor.open_editor(self.root, self.main.executor, self.pdf,
                                        draft_dir=self.folder / "独立窗口草稿")
        self.extra_editors.append(editor)
        self.root.update()
        self.assertIsInstance(editor.window, tk.Toplevel)
        self.assertIs(editor.window.master, self.root)
        editor.close()
        self.assertTrue(self.root.winfo_exists())

    def test_main_close_waits_for_in_progress_editor_json_save(self):
        editor = self.editor()
        editor.busy, editor._active_action = True, "saved"
        with patch.object(toc_editor.messagebox, "showinfo") as blocked:
            self.main._close()
        blocked.assert_called_once()
        self.assertFalse(self.main.closed)
        self.assertFalse(editor.closed)
        self.assertTrue(self.root.winfo_exists())
        editor.busy, editor._active_action = False, None

    def test_main_close_respects_cancel_then_closes_both_pages_without_new_settings_keys(self):
        editor = self.editor()
        self.load_sample(editor)
        editor.level.set("未填完")
        editor._cancel_edit_timer()
        with patch.object(toc_editor.messagebox, "askyesnocancel", return_value=None) as decision:
            self.main._close()
        decision.assert_called_once()
        self.assertFalse(editor.closed)
        self.assertFalse(self.main.closed)
        self.assertTrue(self.root.winfo_exists())
        self.assertEqual(editor.level.get(), "未填完")
        with patch.object(toc_editor.messagebox, "askyesnocancel", return_value=False):
            self.main._close()
        self.assertTrue(editor.closed)
        self.assertTrue(self.main.closed)
        with self.assertRaises(tk.TclError):
            self.root.winfo_exists()
        self.assertEqual(set(gui_support.load_settings(self.settings)), set(gui_support.SETTINGS_DEFAULTS))

    def test_editor_shortcuts_reach_entry_and_tree_but_leave_main_inputs_alone(self):
        def entries(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Entry):
                    yield child
                yield from entries(child)

        with patch.object(toc_editor.TocEditor, "undo") as undo, \
                patch.object(toc_editor.TocEditor, "redo") as redo, \
                patch.object(toc_editor.TocEditor, "save_draft") as save:
            editor = self.editor()
            self.root.deiconify()
            self.root.geometry("1240x930+32000+32000")
            self.root.update()
            title_input = next(child for child in entries(editor.window)
                               if child.cget("textvariable") == str(editor.title))
            main_input = next(child for child in entries(self.main.main_page)
                              if child.cget("textvariable") == str(self.main.pdf))
            for widget in (title_input, editor.tree):
                widget.focus_force()
                self.root.update()
                for key in ("<Control-z>", "<Control-y>", "<Control-s>"):
                    widget.event_generate(key)
                self.root.update()
            self.assertEqual((undo.call_count, redo.call_count, save.call_count), (2, 2, 2))
            self.main.workspace_tabs.select(self.main.main_page)
            self.root.update()
            main_input.focus_force()
            self.root.update()
            for key in ("<Control-z>", "<Control-y>", "<Control-s>"):
                main_input.event_generate(key)
            self.root.update()
            self.assertEqual((undo.call_count, redo.call_count, save.call_count), (2, 2, 2))

    def test_root_drop_routes_to_active_page_and_editor_rejects_multiple_pdfs(self):
        editor = self.editor()
        other = self.folder / "第二本 带空格.pdf"
        other.write_bytes(self.pdf.read_bytes())
        original_inputs = (self.main.mode.get(), self.main.pdf.get(), list(self.main.drop_paths))
        event = SimpleNamespace(data=self.root.tk.call("list", str(other)), widget=self.root)
        self.assertEqual(self.main._on_drop(event), COPY)
        self.assertEqual(Path(editor.pdf.get()), other)
        self.assertEqual((self.main.mode.get(), self.main.pdf.get(), self.main.drop_paths), original_inputs)
        multiple = SimpleNamespace(data=self.root.tk.call("list", str(self.pdf), str(other)), widget=self.root)
        self.assertEqual(self.main._on_drop(multiple), REFUSE_DROP)
        self.assertEqual(Path(editor.pdf.get()), other)
        self.assertEqual((self.main.mode.get(), self.main.pdf.get(), self.main.drop_paths), original_inputs)
        self.main.workspace_tabs.select(self.main.main_page)
        self.root.update()
        self.assertEqual(self.main._on_drop(event), COPY)
        self.assertEqual({Path(path) for path in self.main.drop_paths}, {self.pdf, other})
        self.assertEqual(Path(editor.pdf.get()), other)

    def test_main_and_editor_tasks_cannot_start_while_the_other_page_is_busy(self):
        editor = self.editor()
        operation = Mock()
        self.main.busy = True
        editor._run("generated", operation)
        self.assertFalse(editor.busy)
        self.assertFalse(operation.called)
        self.main.busy = False
        editor.busy = True
        with patch.object(self.main.executor, "submit") as submit:
            self.main._preview()
        submit.assert_not_called()
        self.assertFalse(self.main.busy)
        editor.busy = False

    def test_hidden_editor_remains_an_update_block_until_explicitly_closed(self):
        editor = self.editor()
        self.main.workspace_tabs.select(self.main.main_page)
        self.root.update()
        self.assertTrue(self.main.update_block_reason())
        editor.close()
        self.root.update()
        self.assertFalse(self.main.update_block_reason())

    def test_saved_editor_json_returns_to_main_and_preserves_other_batch_items(self):
        other = self.folder / "已有目录的 第二本.pdf"
        other.write_bytes(self.pdf.read_bytes())
        other_toc = other.with_suffix(".toc.json")
        other_toc.write_text(json.dumps({"version": 1, "bookmarks": [
            {"title": "原有书签", "pdf_page": 2}
        ]}, ensure_ascii=False), encoding="utf8")
        self.main._handle_drop_paths([self.pdf, other, other_toc])
        selected = next(iid for iid, item in self.main.items.items() if item["pdf_path"] == self.pdf)
        self.main.file_tree.selection_set(selected)
        editor = self.editor()
        draft = self.load_sample(editor)
        for entry in draft.entries:
            entry.confirmed = True
        editor._refresh()
        self.spin(lambda: editor._photo is not None)
        target = self.folder / "人工校对 新目录.json"
        with patch.object(toc_editor.filedialog, "asksaveasfilename", return_value=str(target)):
            editor.save_as()
            self.spin(lambda: editor.closed and not self.main.busy and not self.main.pending_editor_saves)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.assertEqual({item["pdf_path"] for item in self.main.items.values()}, {self.pdf, other})
        matched = next(item for item in self.main.items.values() if item["pdf_path"] == self.pdf)
        self.assertEqual(matched["toc_path"], target)
        self.assertIsNotNone(matched["plan"])
        self.assertEqual(other.read_bytes(), self.pdf.read_bytes())
        self.assertEqual(json.loads(target.read_text(encoding="utf8"))["bookmarks"][0]["title"], "第一章 基础")

    def test_separate_page_size_and_topmost_preferences_survive_close_and_reopen(self):
        self.root.geometry("1040x780+32000+32000")
        self.root.deiconify()
        self.main.topmost.set(False)
        self.root.update()
        self.assertEqual(self.root.geometry().split("+", 1)[0], "1040x780")
        editor = self.editor()
        self.root.geometry("1360x980+32000+32000")
        editor.topmost.set(True)
        editor._set_topmost()
        self.root.update()
        self.assertTrue(self.root.attributes("-topmost"))
        self.main.workspace_tabs.select(self.main.main_page)
        self.root.update()
        self.assertEqual(self.root.geometry().split("+", 1)[0], "1040x780")
        self.assertFalse(self.root.attributes("-topmost"))
        self.main.workspace_tabs.select(self.main.editor_page)
        self.root.update()
        self.assertEqual(self.root.geometry().split("+", 1)[0], "1360x980")
        self.assertTrue(self.root.attributes("-topmost"))
        self.main._close()
        self.assertTrue(self.main.closed)
        saved = gui_support.load_settings(self.settings)
        self.assertEqual(saved["geometry"], "1040x780")
        self.assertEqual(saved["editor_geometry"].split("+", 1)[0], "1360x980")
        self.assertFalse(saved["topmost"])
        self.assertTrue(saved["editor_topmost"])
        self.root = TkinterDnD.Tk()
        self.root.withdraw()
        self.root.report_callback_exception = lambda *args, errors=self.callback_errors: errors.append(args)
        self.main = bookmarks_gui.BookmarkWindow(self.root, settings_path=self.settings)
        self.root.geometry("1040x780+32000+32000")
        self.root.deiconify()
        self.root.update()
        self.assertEqual(self.root.geometry().split("+", 1)[0], "1040x780")
        self.assertFalse(self.root.attributes("-topmost"))
        self.editor()
        self.assertEqual(self.root.geometry().split("+", 1)[0], "1360x980")
        self.assertTrue(self.root.attributes("-topmost"))

    def test_hidden_editor_save_preferences_do_not_capture_main_page_geometry(self):
        self.root.geometry("1040x780+32000+32000")
        self.root.deiconify()
        self.root.update()
        editor = self.editor()
        self.root.geometry("1360x980+32000+32000")
        self.root.update()
        self.main.workspace_tabs.select(self.main.main_page)
        self.root.update()
        editor.save_dir.set(str(self.folder))
        editor.save_mode.set("custom")
        self.root.update()
        saved = gui_support.load_settings(self.settings)
        self.assertEqual(saved["geometry"], "1040x780")
        self.assertEqual(saved["editor_geometry"].split("+", 1)[0], "1360x980")
        self.assertEqual(saved["toc_save_dir"], str(self.folder))
        self.assertEqual(saved["toc_save_mode"], "custom")
        self.main.workspace_tabs.select(self.main.editor_page)
        self.root.update()
        self.assertEqual(self.root.geometry().split("+", 1)[0], "1360x980")

    def test_immediate_close_cancels_initial_json_import_idle_callback(self):
        toc = self.folder / "已存在的目录.json"
        toc.write_text(json.dumps({"version": 1, "bookmarks": [
            {"title": "已有目录", "pdf_page": 2}
        ]}, ensure_ascii=False), encoding="utf8")
        self.main.toc.set(str(toc))
        background_errors = []
        self.root.tk.createcommand("bgerror", lambda message: background_errors.append(str(message)))
        self.main._open_editor()
        editor = self.main.editor
        self.assertIsNotNone(editor)
        editor.close()
        self.root.update()
        self.assertTrue(editor.closed)
        self.assertEqual(background_errors, [])
        self.assertEqual(self.callback_errors, [])
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.assertIsNone(editor.draft)

    def test_closed_reading_editor_does_not_permanently_block_main_preview_or_write(self):
        editor = self.editor()
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def reading():
            started.set()
            release.wait(5)
            return Draft(self.pdf, 4, [], [], {"offset": 0}, "合成读取任务", [])

        editor._run("draft", reading)
        self.spin(started.is_set)
        self.assertTrue(editor.busy)
        editor.close()
        self.assertTrue(editor.closed)
        toc = self.folder / "仅供写入计划校验的目录.json"
        toc.write_text(json.dumps({"version": 1, "bookmarks": [
            {"title": "只校验，不执行写入", "pdf_page": 2}
        ]}, ensure_ascii=False), encoding="utf8")
        with patch.object(self.main.executor, "submit") as submit:
            self.main._preview()
            preview_queued = [call.args[0] for call in submit.call_args_list]
            self.main._set_busy(False)
            record = self.main._record(self.pdf, toc)
            record.update(plan=bookmarks_gui.inspect_pdf(self.pdf, toc), ready=True)
            self.main._replace_items([record])
            submit.reset_mock()
            self.main._write()
            write_queued = [call.args[0] for call in submit.call_args_list]
            self.main._set_busy(False)
        release.set()
        self.assertEqual(preview_queued, [self.main._preview_worker])
        self.assertEqual(write_queued, [self.main._write_worker])

    def test_closed_main_releases_variable_trace_references_while_root_is_still_referenced(self):
        closed_main = self.main
        reference = weakref.ref(closed_main)
        closed_main._close()
        closed_main.executor.shutdown(wait=True, cancel_futures=True)
        self.assertTrue(closed_main.closed)
        self.main = None
        del closed_main
        gc.collect()
        self.assertIsNone(reference(), "已关闭主窗口仍被 Tcl 变量回调持有。")
        self.assertIsNotNone(self.root.tk)

    def test_retained_closed_editor_does_not_keep_closed_main_callbacks_alive(self):
        retained_editor = self.editor()
        retained_editor.close()
        closed_main = self.main
        reference = weakref.ref(closed_main)
        closed_main._close()
        closed_main.executor.shutdown(wait=True, cancel_futures=True)
        self.assertTrue(retained_editor.closed)
        self.main = None
        del closed_main
        gc.collect()
        self.assertIsNone(reference(), "已关闭目录工作台仍通过父窗口回调持有主窗口。")
        self.assertIsNotNone(self.root.tk)


if __name__ == "__main__":
    unittest.main()
