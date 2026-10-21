"""Real Tk selection, removal and read-only preview controls preserve files."""

import gc
import hashlib
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pymupdf
from tkinterdnd2 import TkinterDnD

from bookmarks_gui import BookmarkWindow
from gui_support import load_settings


class MainShortcutsPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="main-shortcuts-")
        self.folder = Path(self.temporary.name)
        self.settings = self.folder / "profile" / "settings.json"
        self.pdfs, self.inputs = [], []
        for index in range(3):
            pdf = self.folder / f"合成教材{index}.pdf"
            with pymupdf.open() as document:
                page = document.new_page(width=600, height=1800)
                page.draw_rect(page.rect, color=None, fill=(.1, .8, .2))
                document.save(pdf)
            toc = pdf.with_suffix(".toc.json")
            toc.write_text(json.dumps({"version": 1, "bookmarks": [
                {"title": f"第一章 合成{index}", "pdf_page": 1},
            ]}, ensure_ascii=False), encoding="utf8")
            self.pdfs.append(pdf)
            self.inputs.extend((pdf, toc))
        self.hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.inputs}
        self.root = TkinterDnD.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.main = BookmarkWindow(self.root, settings_path=self.settings)
        self.root.maxsize(2000, 1400)
        self.root.geometry("1100x860+10000+10000")
        self.root.deiconify()
        self.root.update()

    def tearDown(self):
        self.main._set_busy(False)
        if not self.main.closed:
            self.main._close()
        self.main.executor.shutdown(wait=True, cancel_futures=True)
        self.main = None
        self.root = None
        gc.collect()
        self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.inputs}, self.hashes)
        self.temporary.cleanup()
        self.assertEqual(self.errors, [])

    def pump(self, condition, timeout=10):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("Tk preview did not finish")

    def load(self, batch=False):
        if batch:
            self.main.mode.set("batch")
            self.main.folder.set(str(self.folder))
        else:
            self.main._handle_drop_paths(self.inputs)
        self.main._preview()
        self.pump(lambda: not self.main.busy)
        self.assertEqual(len(self.main.items), 3)
        return self.main.file_tree.get_children()

    def focus(self, widget):
        self.root.focus_force()
        widget.focus_set()
        self.root.update()

    def render(self):
        self.load()
        self.main.bookmark_tree.selection_set(self.main.bookmark_tree.get_children()[0])
        self.pump(lambda: self.main._render_photo is not None)

    def test_ctrl_a_and_clear_selection_preserve_write_checks(self):
        ids = self.load()
        self.main._set_all_checked(False)
        self.main._toggle_item(ids[1])
        checked = [item["checked"] for item in self.main.items.values()]
        self.focus(self.main.file_tree)
        self.main.file_tree.event_generate("<Control-a>")
        self.root.update()
        self.assertEqual(set(self.main.file_tree.selection()), set(ids))
        self.main.file_actions_menu.invoke("清除选中")
        self.root.update()
        self.assertEqual(self.main.file_tree.selection(), ())
        self.assertEqual([item["checked"] for item in self.main.items.values()], checked)
        self.main.file_actions_menu.invoke("选中全部")
        self.assertEqual(set(self.main.file_tree.selection()), set(ids))

    def test_ctrl_shift_clicks_extend_selection_without_toggling_write_column(self):
        ids = self.load()
        tree = self.main.file_tree
        self.focus(tree)
        before = [item["checked"] for item in self.main.items.values()]
        tree.selection_set(ids[0])
        tree.focus(ids[0])
        x, y, width, height = tree.bbox(ids[2], "#1")
        tree.event_generate("<Button-1>", x=x + width // 2, y=y + height // 2, state=1)
        tree.event_generate("<ButtonRelease-1>", x=x + width // 2, y=y + height // 2, state=1)
        self.root.update()
        self.assertEqual(set(tree.selection()), set(ids))
        self.assertEqual([item["checked"] for item in self.main.items.values()], before)
        tree.selection_set(ids[0])
        x, y, width, height = tree.bbox(ids[2], "#1")
        tree.event_generate("<Button-1>", x=x + width // 2, y=y + height // 2, state=4)
        tree.event_generate("<ButtonRelease-1>", x=x + width // 2, y=y + height // 2, state=4)
        self.root.update()
        self.assertEqual(set(tree.selection()), {ids[0], ids[2]})
        self.assertEqual([item["checked"] for item in self.main.items.values()], before)
        tree.event_generate("<space>")
        self.root.update()
        self.assertEqual([item["checked"] for item in self.main.items.values()], [False, True, False])

    def test_delete_removes_only_list_rows_and_survives_repreview_and_option_change(self):
        ids = self.load(batch=True)
        removed = {self.main.items[iid]["pdf_path"] for iid in (ids[0], ids[2])}
        self.main.file_tree.selection_set(ids[0], ids[2])
        self.focus(self.main.file_tree)
        self.main.file_tree.event_generate("<Delete>")
        self.root.update()
        self.assertEqual(len(self.main.items), 1)
        self.assertEqual(len(self.main.plans), 1)
        self.assertEqual(len(self.main._checked_items()), 1)
        self.assertIn("原 PDF 和 JSON 文件未删除", self.main.status.get())
        self.main.backup.set(False)
        self.main._preview()
        self.pump(lambda: not self.main.busy)
        self.assertEqual(len(self.main.items), 1)
        self.assertTrue(removed.isdisjoint(item["pdf_path"] for item in self.main.items.values()))

    def test_explicit_readd_restores_removed_pdf_but_not_other_removed_files(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[0], ids[2])
        self.main._remove_selected_files()
        self.main._handle_drop_paths([self.pdfs[0]])
        self.main._preview()
        self.pump(lambda: not self.main.busy)
        self.assertEqual({item["pdf_path"] for item in self.main.items.values()}, set(self.pdfs[:2]))

    def test_busy_shortcuts_do_not_remove_select_or_change_checked_files(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[1])
        self.main._set_busy(True)
        self.main._select_all_files()
        self.main._clear_file_selection()
        self.main._remove_selected_files()
        self.main._file_space(None)
        self.assertEqual(self.main.file_tree.selection(), (ids[1],))
        self.assertEqual(len(self.main.items), 3)
        self.assertTrue(all(item["checked"] for item in self.main.items.values()))

    def test_cancelled_menu_picker_preserves_source_plans_and_removed_set(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[1])
        self.main._remove_selected_files()
        before = (self.main.mode.get(), list(self.main.plans), set(self.main._removed_files),
                  self.main.workspace_tabs.select(), list(self.main.items))
        with patch("bookmarks_gui.filedialog.askopenfilename", return_value="") as picker:
            try:
                self.main.file_menu.invoke("选择 PDF…")
            finally:
                picker.reset_mock()
        self.assertEqual((self.main.mode.get(), self.main.plans, self.main._removed_files,
                          self.main.workspace_tabs.select(), list(self.main.items)), before)

    def test_successful_menu_picker_switches_source_and_previews_chosen_file(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[1])
        self.main._remove_selected_files()
        self.assertTrue(self.main._removed_files)
        with patch("bookmarks_gui.filedialog.askopenfilename", return_value=str(self.pdfs[1])) as picker:
            try:
                self.main.file_menu.invoke("选择 PDF…")
            finally:
                picker.reset_mock()
        self.assertEqual(self.main.mode.get(), "single")
        self.assertEqual(self.main.pdf.get(), str(self.pdfs[1]))
        self.assertEqual(self.main.toc.get(), str(self.pdfs[1].with_suffix(".toc.json")))
        self.assertEqual(self.main._removed_files, set())
        self.assertEqual(self.main.plans, [])
        self.main._preview()
        self.pump(lambda: not self.main.busy)
        self.assertEqual({item["pdf_path"] for item in self.main.items.values()}, {self.pdfs[1]})

    def test_focused_selected_row_controls_preview_and_json_pairing(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids)
        self.main.file_tree.focus(ids[2])
        self.main._selected_file()
        self.assertEqual(self.main._focused_file(), ids[2])
        self.assertIn(str(self.pdfs[2]), self.main.file_detail.get())
        self.assertEqual(next(iter(self.main.bookmark_rows.values()))["pdf_path"], self.pdfs[2])
        replacement = self.folder / "独立新目录.json"
        replacement.write_text('{"version":1,"bookmarks":[]}', encoding="utf8")
        self.main._handle_drop_paths([replacement])
        self.assertEqual(self.main.toc_overrides[self.main._key(self.pdfs[2])], replacement)

    def test_edit_menu_is_local_to_focused_list_and_keeps_entry_shortcuts(self):
        ids = self.load()
        self.main.source_tabs.select(0)
        self.root.update()
        entry = next(widget for widget in self.main.inputs if isinstance(widget, ttk.Entry))
        entry.delete(0, "end")
        entry.insert(0, "待编辑的路径")
        self.focus(entry)
        self.main._update_edit_menu()
        self.assertEqual(str(self.main.edit_menu.entrycget(0, "state")), "disabled")
        self.main._edit_action("select_all")
        entry.selection_range(0, 2)
        entry.event_generate("<Delete>")
        self.root.update()
        self.assertEqual(entry.get(), "辑的路径")
        self.assertEqual(len(self.main.items), 3)
        self.assertNotEqual(set(self.main.file_tree.selection()), set(ids))
        self.focus(self.main.file_tree)
        self.main._update_edit_menu()
        self.assertEqual(str(self.main.edit_menu.entrycget(0, "state")), "normal")
        self.main.edit_menu.invoke("选中全部")
        self.assertEqual(set(self.main.file_tree.selection()), set(ids))

    def test_menu_theme_persists_three_modes_and_window_client_size_stays_fixed(self):
        geometry = self.root.geometry()
        for label, mode in (("夜间模式", "dark"), ("护眼模式", "eye_care"), ("日间模式", "light")):
            self.main.theme_menu.invoke(label)
            self.root.update()
            self.assertEqual(self.main.theme.get(), mode)
            self.assertEqual(load_settings(self.settings)["theme"], mode)
            self.assertEqual(self.root.geometry(), geometry)
            self.assertEqual(self.main.workspace_tabs.winfo_width(), self.root.winfo_width())
            self.assertEqual(self.main.workspace_tabs.winfo_height(), self.root.winfo_height())

    def test_wheel_scrolls_and_ctrl_wheel_renders_larger_original_pixels(self):
        self.render()
        canvas = self.main.image_canvas
        old_size = self.main._render_photo.width(), self.main._render_photo.height()
        original_pixel = self.main._render_photo.get(20, 20)
        canvas.yview_moveto(0)
        canvas.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(canvas.yview()[0], 0)
        canvas.event_generate("<MouseWheel>", delta=120, state=4)
        self.pump(lambda: self.main._render_after is None and self.main._render_future.done()
                  and self.main._render_photo.height() > old_size[1])
        self.assertGreater(self.main._render_photo.width(), old_size[0])
        self.assertAlmostEqual(self.main._preview_scale, 1.2)
        self.assertEqual(self.main._render_photo.get(20, 20), original_pixel)
        self.assertEqual(len(canvas.find_all()), 1)
        self.main._zoom_preview(reset=True)
        self.pump(lambda: self.main._render_after is None and self.main._render_future.done()
                  and self.main._render_photo.height() == old_size[1])
        self.assertEqual(self.main.preview_zoom.get(), "100%")

    def test_zoom_burst_is_coalesced_clamped_and_pending_render_blocks_update(self):
        self.render()
        canvas = self.main.image_canvas
        with patch.object(self.main.executor, "submit", wraps=self.main.executor.submit) as submitted:
            try:
                for _ in range(20):
                    self.main._preview_wheel(SimpleNamespace(delta=120, state=4))
                self.assertEqual(self.main._preview_scale, 3.0)
                self.assertIn("页面预览", self.main.update_block_reason())
                self.assertIsNotNone(self.main._render_after)
                submitted.assert_not_called()
                self.pump(lambda: self.main._render_after is None and self.main._render_future.done()
                          and self.main._render_photo.width() > 500)
                self.assertEqual(submitted.call_count, 1)
                for _ in range(30):
                    self.main._preview_wheel(SimpleNamespace(delta=-120, state=4))
                self.assertEqual(self.main._preview_scale, .5)
                self.main._clear_bookmarks()
                self.assertIsNone(self.main._render_after)
                self.assertIsNone(self.main._preview_target)
                self.assertEqual(canvas.find_all(), ())
            finally:
                submitted.reset_mock()


if __name__ == "__main__":
    unittest.main()
