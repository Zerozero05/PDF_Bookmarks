"""Real Tk region/source interactions keep page identities and draft inputs safe."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pymupdf

import toc_editor
from toc_generation import Draft, DraftEntry, _format_generated_titles


class EditorRegionUITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-region-ui-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "目录区域交互.pdf"
        with pymupdf.open() as doc:
            for index in range(4):
                page = doc.new_page(width=600, height=800)
                page.insert_text((60, 100), f"Synthetic page {index + 1}")
            doc.save(self.pdf)
        self.original = self.pdf.read_bytes()
        self.root = tk.Tk()
        self.root.withdraw()
        self.callback_errors = []
        self.root.report_callback_exception = lambda *error, errors=self.callback_errors: errors.append(error)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.errors = []
        self.dialogs = patch.object(toc_editor.messagebox, "showerror",
                                    side_effect=lambda *args, errors=self.errors, **kwargs: errors.append(args))
        self.dialogs.start()
        self.editor = toc_editor.open_editor(self.root, self.executor, self.pdf,
            draft_dir=self.folder / "recovery", on_settings_changed=Mock())
        self.editor.window.geometry("1240x900+32000+32000")
        self.editor.window.attributes("-topmost", False)
        self.editor.auto_save.set(False)
        self.editor.draft = self.draft()
        self.editor._refresh()
        self.spin(lambda: self.editor._photo is not None)

    def tearDown(self):
        self.editor.on_settings_changed = None
        self.editor.auto_save.set(False)
        self.editor.close()
        self.executor.shutdown(wait=True)
        self.root.update()
        self.root.destroy()
        self.dialogs.stop()
        self.assertEqual(self.errors, [])
        self.assertEqual(self.callback_errors, [])
        self.assertEqual(self.pdf.read_bytes(), self.original)
        self.assertFalse(self.pdf.with_suffix(".toc.json").exists())
        self.temporary.cleanup()

    def draft(self):
        entries = [DraftEntry(1, "目录", None, 1),
            DraftEntry(1, "Chapter 1 Foundations", 1, 3, source_page=1, source_rect=(.1, .2, .8, .3)),
            DraftEntry(2, "1.1 Target section", 2, 4, source_page=2, source_rect=(.2, .3, .7, .4))]
        return _format_generated_titles(Draft(self.pdf, 4, entries, [1, 2], {"offset": 2}, "测试", []))

    def spin(self, condition, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("目录区域交互未在时限内完成。")

    def select(self, index):
        self.editor.tree.selection_set(str(index))
        self.editor.tree.focus(str(index))
        self.editor._selected()
        self.root.update_idletasks()

    def show(self, page=1, *, toc=True):
        previous = self.editor._photo
        self.editor.preview_page.set(str(page))
        self.editor._preview_kind = "toc" if toc else "target"
        self.editor.show_page()
        self.spin(lambda: self.editor._photo is not None and self.editor._photo is not previous)

    def event(self, x, y):
        return SimpleNamespace(x=round(x * self.editor._photo.width() - self.editor.canvas.canvasx(0)),
                               y=round(y * self.editor._photo.height() - self.editor.canvas.canvasy(0)))

    def draw(self, tool, start=(.1, .12), end=(.9, .65)):
        self.editor.region_tool.set(tool)
        self.editor._region_start(self.event(*start))
        self.editor._region_motion(self.event(*end))
        self.editor._region_end(self.event(*end))

    def test_tree_inline_editor_uses_clicked_display_cell_for_position(self):
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()
        self.select(1)
        for display_column, variable in (("#0", self.editor.title), ("#2", self.editor.printed),
                                          ("#3", self.editor.target)):
            with self.subTest(column=display_column):
                self.editor._close_inline()
                self.root.update_idletasks()
                box = self.editor.tree.bbox("1", display_column)
                self.assertTrue(box)
                self.editor._inline_edit(SimpleNamespace(x=box[0] + 10, y=box[1] + box[3] // 2))
                self.assertIsNotNone(self.editor._inline)
                actual = self.editor._inline.place_info()
                self.assertEqual(tuple(int(actual[key]) for key in ("x", "y", "width", "height")), box)
                self.assertEqual(str(self.editor._inline.cget("textvariable")), str(variable))

    def test_editing_page_input_without_showing_cannot_assign_region_to_another_page(self):
        self.show(1)
        self.editor.preview_page.set("2")
        self.draw("框选目录区域")
        self.assertEqual(self.editor.page_regions, {})

    def test_pending_async_page_without_a_displayed_image_cannot_accept_region(self):
        self.show(1)
        actual_render = toc_editor.render_page
        entered, release = threading.Event(), threading.Event()

        def slow_render(*args, **kwargs):
            entered.set()
            release.wait(4)
            return actual_render(*args, **kwargs)

        try:
            with patch.object(toc_editor, "render_page", side_effect=slow_render):
                self.editor.preview_page.set("2")
                self.editor.show_page()
                self.assertTrue(entered.wait(2))
                self.editor.region_tool.set("框选目录区域")
                self.editor._region_start(SimpleNamespace(x=30, y=40))
                self.editor._region_end(SimpleNamespace(x=250, y=250))
                self.assertEqual(self.editor.page_regions, {})
        finally:
            release.set()
            self.spin(lambda: self.editor._render_future.done())

    def test_valid_rectangle_and_separator_reach_generation_without_pdf_changes(self):
        self.show(1)
        width, height = self.editor._photo.width(), self.editor._photo.height()
        self.draw("框选目录区域")
        self.draw("设置分栏线", start=(.6, .2), end=(.6, .5))
        region = self.editor.page_regions[1]
        for actual, expected in zip(region["rect"], (.1, .12, .9, .65)):
            self.assertAlmostEqual(actual, expected, delta=2 / min(width, height))
        self.assertAlmostEqual(region["split"], .6, delta=2 / width)
        self.assertEqual(region["mode"], "double")
        expected = deepcopy(self.editor.page_regions)
        with patch.object(toc_editor, "generate_toc", return_value=self.draft()) as generate:
            self.editor.generate()
            self.spin(lambda: not self.editor.busy)
        self.assertEqual(generate.call_args.kwargs["page_regions"], expected)
        self.assertEqual(self.editor.page_regions, expected)

    def test_source_highlight_scales_with_image_and_changes_to_selected_source_page(self):
        self.select(1)
        previous = self.editor._photo
        self.editor.show_source()
        self.spin(lambda: self.editor._photo is not None and self.editor._photo is not previous)

        def check_overlay(rect):
            items = self.editor.canvas.find_withtag("review_overlay")
            self.assertEqual(len(items), 1)
            coordinates = self.editor.canvas.coords(items[0])
            expected = [value * (self.editor._photo.width() if index % 2 == 0 else self.editor._photo.height())
                        for index, value in enumerate(rect)]
            for actual, wanted in zip(coordinates, expected):
                self.assertAlmostEqual(actual, wanted, places=4)

        check_overlay((.1, .2, .8, .3))
        previous = self.editor._photo
        self.editor.zoom_preview(1.5)
        self.spin(lambda: self.editor._photo is not None and self.editor._photo is not previous)
        check_overlay((.1, .2, .8, .3))
        previous = self.editor._photo
        self.select(2)
        self.spin(lambda: self.editor._photo is not None and self.editor._photo is not previous)
        self.assertEqual(self.editor.preview_page.get(), "2")
        check_overlay((.2, .3, .7, .4))

    def test_clearing_one_page_region_preserves_other_page_settings(self):
        self.show(1)
        other = {"rect": [.2, .2, .8, .7], "split": .6, "mode": "double"}
        self.editor.page_regions = {1: {"rect": [.1, .1, .9, .9]}, 2: deepcopy(other)}
        self.editor.clear_page_region()
        self.assertEqual(self.editor.page_regions, {2: other})

    def test_filtered_tree_edit_keeps_original_entry_identity(self):
        self.editor.view_mode.set("目录树")
        self.editor.search_text.set("Target")
        self.editor._filter_changed()
        self.assertEqual(self.editor._visible_indices, {2})
        self.assertTrue(self.editor.tree.exists("1"))
        self.select(2)
        original_chapter = self.editor.draft.entries[1].title
        self.editor.title.set("1.1 Revised target")
        self.assertTrue(self.editor._apply_auto(report=True))
        self.assertEqual(self.editor.draft.entries[2].title, "1.1 Revised target")
        self.assertEqual(self.editor.draft.entries[1].title, original_chapter)

    def prepare_manual_draft(self):
        self.select(2)
        self.assertTrue(self.editor.save_draft(report=False))
        self.editor.auto_save.set(False)

    def test_close_with_uncommitted_title_and_autosave_off_asks_and_can_cancel(self):
        self.prepare_manual_draft()
        self.editor.title.set("Uncommitted title")
        with patch.object(toc_editor.messagebox, "askyesnocancel", return_value=None) as ask:
            self.editor.close()
        ask.assert_called_once()
        self.assertFalse(self.editor.closed)
        self.assertEqual(self.editor.title.get(), "Uncommitted title")

    def test_close_with_invalid_partial_page_and_autosave_off_can_save_raw_input(self):
        self.prepare_manual_draft()
        self.editor.target.set("not-a-page")
        with patch.object(toc_editor.messagebox, "askyesnocancel", return_value=True) as ask:
            self.editor.close()
        ask.assert_called_once()
        self.assertTrue(self.editor.closed)
        state = self.editor.store.load(self.pdf)
        self.assertEqual(state["options"]["raw_fields"]["target"], "not-a-page")
        self.assertEqual(state["draft"]["entries"][2]["pdf_page"], 4)


if __name__ == "__main__":
    unittest.main()
