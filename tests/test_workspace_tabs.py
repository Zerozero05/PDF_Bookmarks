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

    def assert_window_stays(self, action):
        self.root.update()
        geometry, state, minimum = self.root.geometry(), self.root.state(), self.root.minsize()
        size = self.root.winfo_width(), self.root.winfo_height()
        configured_sizes = []

        def configured(event):
            if event.widget is self.root:
                configured_sizes.append((event.width, event.height))

        binding = self.root.bind("<Configure>", configured, add="+")
        try:
            action()
            for _ in range(3):
                self.root.update()
                time.sleep(.01)
            self.assertEqual(self.root.geometry(), geometry)
            self.assertEqual(self.root.state(), state)
            self.assertEqual(self.root.minsize(), minimum)
            self.assertTrue(all(actual == size for actual in configured_sizes),
                            f"标签切换期间窗口曾改变尺寸：{configured_sizes}")
        finally:
            self.root.unbind("<Configure>", binding)

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
        self.assertEqual([child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)],
                         [self.main.titlebar_pin.popup] if self.main.titlebar_pin.popup is not None else [])

    def test_open_editor_embeds_a_frame_and_keeps_the_shared_worker(self):
        editor = self.editor()
        self.assertIsInstance(editor.window, ttk.Frame)
        self.assertIs(editor.window.winfo_toplevel(), self.root)
        self.assertIs(editor.executor, self.main.executor)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))
        self.assertTrue(str(editor.window).startswith(str(self.main.editor_page) + "."))
        self.assertEqual([child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)],
                         [self.main.titlebar_pin.popup] if self.main.titlebar_pin.popup is not None else [])
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

    def test_first_editor_open_and_repeated_tab_switches_preserve_window_geometry_and_state(self):
        self.root.maxsize(2000, 1400)
        self.root.deiconify()
        self.root.geometry("1100x860+80+60")
        self.root.update()
        self.main.editor_settings["editor_geometry"] = "1360x980+160+120"
        self.assert_window_stays(self.main._open_editor)
        self.assertIsNotNone(self.main.editor)
        self.assertEqual(self.root.minsize(), (1000, 760))
        for _ in range(12):
            self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.main_page))
            self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.editor_page))

    def test_resizing_either_workspace_page_is_preserved_on_the_other_page(self):
        self.root.maxsize(2000, 1400)
        self.root.deiconify()
        self.editor()
        for page, other, geometry in (
                (self.main.main_page, self.main.editor_page, "1040x780+80+60"),
                (self.main.editor_page, self.main.main_page, "1320x940+160+120")):
            with self.subTest(page=str(page)):
                self.main.workspace_tabs.select(page)
                self.root.update()
                self.root.geometry(geometry)
                self.root.update()
                self.assert_window_stays(lambda: self.main.workspace_tabs.select(other))
                self.assert_window_stays(lambda: self.main.workspace_tabs.select(page))

    def test_width_drag_coalesces_layout_without_changing_preview_or_edits(self):
        self.root.maxsize(2000, 1400)
        self.root.geometry("1100x860+80+60")
        self.root.deiconify()
        editor = self.editor()
        model = self.load_sample(editor)
        self.spin(lambda: self.main.workspace_tabs.winfo_width() == self.root.winfo_width())
        original, photo = deepcopy(asdict(model)), editor._photo
        configured = []
        binding = self.main.workspace_tabs.bind(
            "<Configure>", lambda event: configured.append(event.width), add="+")
        try:
            with patch.object(self.main.executor, "submit", wraps=self.main.executor.submit) as submit:
                widths = list(range(1120, 1321, 20))
                for width in widths:
                    self.root.geometry(f"{width}x860")
                    self.root.update()
                self.assertLess(len(configured), len(widths) // 2,
                                "连续拖宽时仍逐次重排全部控件。")
                self.spin(lambda: self.main.workspace_tabs.winfo_width() == self.root.winfo_width()
                          and self.main.workspace_tabs.winfo_height() == self.root.winfo_height())
                self.assertEqual(asdict(model), original)
                self.assertIs(editor._photo, photo)
                submit.assert_not_called()
            self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.main_page))
        finally:
            self.main.workspace_tabs.unbind("<Configure>", binding)

    def test_close_cancels_pending_window_layout(self):
        self.root.deiconify()
        self.editor()
        self.spin(lambda: self.main._resize_after is None
                  and self.main._workspace_size == (self.root.winfo_width(), self.root.winfo_height()))
        # Schedule synchronously: update() could already run the 80ms timer,
        # leaving no pending work for this cancellation test to inspect.
        self.main._resize_workspace(SimpleNamespace(widget=self.root,
            width=self.root.winfo_width() + 1, height=self.root.winfo_height()))
        pending = self.main._resize_after
        self.assertIsNotNone(pending)
        with patch.object(self.root, "after_cancel", wraps=self.root.after_cancel) as cancel:
            self.main._close()
        cancel.assert_any_call(pending)
        self.assertIsNone(self.main._resize_after)
        self.assertTrue(self.main.closed)

    def test_theme_switch_from_either_page_preserves_work_and_saves_preference(self):
        editor = self.editor()
        model = self.load_sample(editor)
        original, photo = deepcopy(asdict(model)), editor._photo
        editor.title.set("正在编辑的标题")
        editor._cancel_edit_timer()

        def theme_button(parent):
            for child in parent.winfo_children():
                if isinstance(child, ttk.Checkbutton) and child.cget("text") == "夜间模式":
                    return child
                found = theme_button(child)
                if found is not None:
                    return found

        self.assertIs(editor.theme_var, self.main.theme)
        for page, mode in ((self.main.main_page, "dark"), (self.main.editor_page, "light")):
            theme_button(page).invoke()
            self.root.update()
            self.assertEqual(self.main.theme.get(), mode)
            self.assertEqual(ttk.Style(self.root).theme_use(), "pdf_" + mode)
            self.assertEqual(gui_support.load_settings(self.settings)["theme"], mode)
            self.assertEqual(asdict(model), original)
            self.assertEqual(editor.title.get(), "正在编辑的标题")
            self.assertIs(editor._photo, photo)

    def test_editor_save_controls_remain_visible_at_minimum_size_in_both_themes(self):
        self.root.maxsize(2000, 1400)
        self.root.geometry("1000x760+80+60")
        self.root.deiconify()
        editor = self.editor()
        for mode in ("light", "dark"):
            self.main.theme.set(mode)
            self.main._set_theme()
            self.spin(lambda: self.main.workspace_tabs.winfo_height() == self.root.winfo_height())
            self.root.update()
            for button in editor._controls:
                if isinstance(button, ttk.Button) and button.cget("text") in (
                        "保存 JSON 并返回", "另存为…", "下一待核对"):
                    self.assertTrue(button.winfo_ismapped())
                    self.assertGreaterEqual(button.winfo_rootx(), self.root.winfo_rootx())
                    self.assertGreaterEqual(button.winfo_rooty(), self.root.winfo_rooty())
                    self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                         self.root.winfo_rootx() + self.root.winfo_width())
                    self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                         self.root.winfo_rooty() + self.root.winfo_height())

    def test_maximized_and_restored_workspace_stay_in_place_while_switching_tabs(self):
        self.root.maxsize(2000, 1400)
        self.root.deiconify()
        self.root.geometry("1100x860+80+60")
        self.root.update()
        self.editor()
        try:
            for state in ("zoomed", "normal"):
                with self.subTest(state=state):
                    self.root.state(state)
                    self.root.update()
                    self.assertEqual(self.root.state(), state)
                    for _ in range(3):
                        self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.main_page))
                        self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.editor_page))
        finally:
            self.root.state("normal")
            self.root.update()

    def test_closing_editor_returns_to_main_without_destroying_root(self):
        self.root.maxsize(2000, 1400)
        self.root.deiconify()
        self.root.geometry("1100x860+80+60")
        editor = self.editor()
        self.assert_window_stays(editor.close)
        self.assertTrue(editor.closed)
        self.assertFalse(editor.window.winfo_exists())
        self.assertTrue(self.root.winfo_exists())
        self.assertFalse(self.main.closed)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.assert_window_stays(self.main._open_editor)
        self.assertIsNot(self.main.editor, editor)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))

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
            def save_and_return():
                editor.save_as()
                self.spin(lambda: editor.closed and not self.main.busy and not self.main.pending_editor_saves)
            self.assert_window_stays(save_and_return)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.assertEqual({item["pdf_path"] for item in self.main.items.values()}, {self.pdf, other})
        matched = next(item for item in self.main.items.values() if item["pdf_path"] == self.pdf)
        self.assertEqual(matched["toc_path"], target)
        self.assertIsNotNone(matched["plan"])
        self.assertEqual(other.read_bytes(), self.pdf.read_bytes())
        self.assertEqual(json.loads(target.read_text(encoding="utf8"))["bookmarks"][0]["title"], "第一章 基础")

    def test_shared_window_geometry_and_topmost_preference_survive_close_and_reopen(self):
        # Keep requested sizes independent of the CI desktop's default cap.
        self.root.maxsize(2000, 1400)
        self.root.geometry("1040x780+80+60")
        self.root.deiconify()
        self.main.topmost.set(False)
        self.root.update()
        self.assertEqual(self.root.geometry().split("+", 1)[0], "1040x780")
        legacy_editor_geometry = self.main.editor_settings["editor_geometry"]
        self.assert_window_stays(self.main._open_editor)
        editor = self.main.editor
        self.assertIs(editor.topmost, self.main.topmost)
        self.root.geometry("1360x980+160+120")
        editor.topmost.set(True)
        editor._set_topmost()
        self.root.update()
        self.assertTrue(self.root.attributes("-topmost"))
        self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.main_page))
        self.assertTrue(self.root.attributes("-topmost"))
        self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.editor_page))
        self.assertTrue(self.root.attributes("-topmost"))
        self.main._close()
        self.assertTrue(self.main.closed)
        saved = gui_support.load_settings(self.settings)
        self.assertEqual(saved["geometry"].split("+", 1)[0], "1360x980")
        self.assertEqual(saved["editor_geometry"], legacy_editor_geometry)
        self.assertTrue(saved["topmost"])
        self.assertTrue(saved["editor_topmost"])
        self.root = TkinterDnD.Tk()
        self.root.maxsize(2000, 1400)
        self.root.withdraw()
        self.root.report_callback_exception = lambda *args, errors=self.callback_errors: errors.append(args)
        self.main = bookmarks_gui.BookmarkWindow(self.root, settings_path=self.settings)
        self.root.deiconify()
        self.root.update()
        self.assertEqual(self.root.geometry().split("+", 1)[0], "1360x980")
        self.assertTrue(self.root.attributes("-topmost"))
        self.assert_window_stays(self.main._open_editor)
        self.assertTrue(self.root.attributes("-topmost"))
        self.assertEqual(self.root.minsize(), (1000, 760))

    def test_topmost_change_from_either_page_keeps_one_shared_state_and_unfinished_work(self):
        self.root.deiconify()
        editor = self.editor()
        model = self.load_sample(editor)
        original, photo = deepcopy(asdict(model)), editor._photo
        editor.title.set("尚未提交的标题")
        editor._cancel_edit_timer()
        for page, enabled in ((self.main.main_page, True), (self.main.editor_page, False),
                              (self.main.editor_page, True), (self.main.main_page, False)):
            self.main.workspace_tabs.select(page)
            self.root.update()
            self.main.topmost.set(enabled)
            self.root.update()
            self.assertEqual(editor.topmost.get(), enabled)
            self.assertEqual(bool(self.root.attributes("-topmost")), enabled)
            self.assertEqual(asdict(model), original)
            self.assertIs(editor._photo, photo)
            self.assertEqual(editor.title.get(), "尚未提交的标题")
        self.assertFalse(self.errors)

    def test_old_editor_topmost_does_not_override_the_shared_main_preference(self):
        self.main.editor_settings["editor_topmost"] = True
        self.main.topmost.set(False)
        self.root.deiconify()
        self.editor()
        self.assertFalse(self.main.editor.topmost.get())
        self.assertFalse(self.root.attributes("-topmost"))

    def test_both_pages_use_only_the_single_window_pin_button(self):
        self.root.deiconify()
        self.editor()

        def pin_buttons(widget):
            found = []
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Checkbutton)) and child.cget("text") in ("置顶", "取消置顶"):
                    found.append(child)
                found.extend(pin_buttons(child))
            return found

        for page in (self.main.main_page, self.main.editor_page):
            self.main.workspace_tabs.select(page)
            self.root.update()
            self.assertEqual(pin_buttons(self.root), [self.main.titlebar_pin.button])
            self.assertTrue(self.main.titlebar_pin.button.winfo_ismapped())

    def test_hidden_editor_preferences_preserve_shared_geometry_and_legacy_standalone_geometry(self):
        self.root.maxsize(2000, 1400)
        self.root.geometry("1040x780+80+60")
        self.root.deiconify()
        self.root.update()
        legacy_editor_geometry = self.main.editor_settings["editor_geometry"]
        self.assert_window_stays(self.main._open_editor)
        editor = self.main.editor
        self.root.geometry("1360x980+160+120")
        self.root.update()
        self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.main_page))
        geometry = self.root.geometry()
        editor.save_dir.set(str(self.folder))
        editor.save_mode.set("custom")
        self.root.update()
        saved = gui_support.load_settings(self.settings)
        self.assertEqual(self.root.geometry(), geometry)
        self.assertEqual(saved["geometry"].split("+", 1)[0], "1360x980")
        self.assertEqual(saved["editor_geometry"], legacy_editor_geometry)
        self.assertEqual(saved["toc_save_dir"], str(self.folder))
        self.assertEqual(saved["toc_save_mode"], "custom")
        self.assert_window_stays(lambda: self.main.workspace_tabs.select(self.main.editor_page))

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
