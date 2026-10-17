"""Read-only directory preview scrolling and zoom use only temporary PDFs."""

from concurrent.futures import ThreadPoolExecutor
import gc
import hashlib
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

import pymupdf

import toc_editor


class EditorPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-editor-preview-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "预览 测试.pdf"
        with pymupdf.open() as document:
            for index in range(2):
                document.new_page().insert_text((50, 50), f"Page {index + 1}")
            document.save(self.pdf)
        self.original = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.root = tk.Tk()
        self.root.withdraw()
        self.callback_errors = []
        self.root.report_callback_exception = lambda *error, errors=self.callback_errors: errors.append(error)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.errors = []
        self.error_patch = patch.object(toc_editor.messagebox, "showerror",
                                       side_effect=lambda *args, errors=self.errors, **kwargs: errors.append(args))
        self.error_patch.start()
        self.editor = toc_editor.open_editor(self.root, self.executor, self.pdf)
        self.editor.window.attributes("-topmost", False)
        self.root.update()

    def tearDown(self):
        self.editor.close()
        self.executor.shutdown(wait=True)
        self.root.update()
        self.root.destroy()
        self.error_patch.stop()
        # Mock call histories may retain destroyed Tk widgets in reference cycles.
        gc.collect()
        self.assertEqual(self.callback_errors, [])
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.original)
        self.assertEqual(list(self.folder.iterdir()), [self.pdf])
        self.temporary.cleanup()

    def spin(self, condition, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("预览操作未在时限内完成。")

    def settle(self, seconds=0.35):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)

    def show(self, page=1):
        previous = self.editor._photo
        self.editor.preview_page.set(str(page))
        self.editor.show_page()
        self.spin(lambda: self.editor._photo is not None and self.editor._photo is not previous)

    def wheel(self, delta, control=False, widget=None):
        (widget or self.editor.canvas).event_generate("<MouseWheel>", delta=delta,
                                                    state=0x0004 if control else 0)
        self.root.update()

    def zoom(self, factor):
        previous = self.editor._photo
        self.editor.zoom_preview(factor)
        self.spin(lambda: self.editor._photo is not None and self.editor._photo is not previous)

    def test_plain_wheel_scrolls_preview_without_rendering_or_zooming(self):
        self.show()
        before = self.editor.canvas.yview()[0]
        with patch.object(toc_editor, "render_page", wraps=toc_editor.render_page) as render:
            self.wheel(-120)
            down = self.editor.canvas.yview()[0]
            self.assertGreater(down, before)
            self.wheel(120)
            self.assertLess(self.editor.canvas.yview()[0], down)
            self.settle()
            render.assert_not_called()
        self.assertEqual(self.editor._preview_scale, 1.0)

    def test_control_wheel_zooms_without_plain_scroll_command(self):
        self.show()
        previous = self.editor._photo
        with patch.object(self.editor.canvas, "yview_scroll", wraps=self.editor.canvas.yview_scroll) as scroll:
            self.wheel(120, control=True)
            self.spin(lambda: self.editor._photo is not previous)
            scroll.assert_not_called()
        self.assertGreater(self.editor._preview_scale, 1.0)
        self.assertGreater(int(self.editor.preview_zoom.get().rstrip("%")), 100)
        self.wheel(-120, control=True)
        self.spin(lambda: self.editor.preview_zoom.get() == "100%")
        self.assertEqual(self.editor.preview_page.get(), "1")

    def test_wheel_binding_stays_local_to_preview(self):
        self.show()
        self.editor.canvas.yview_moveto(0.2)
        original_view = self.editor.canvas.yview()
        original_scale = self.editor._preview_scale
        self.wheel(-120, widget=self.editor.tree)
        self.wheel(120, control=True, widget=self.editor.tree)
        self.assertEqual(self.editor.canvas.yview(), original_view)
        self.assertEqual(self.editor._preview_scale, original_scale)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.assertTrue(self.editor.canvas.bind(sequence), sequence)

    def test_zoom_buttons_enlarge_reduce_and_restore_100_percent(self):
        self.show()
        buttons = {}

        def collect(widget):
            if isinstance(widget, ttk.Button):
                buttons[str(widget.cget("text"))] = widget
            for child in widget.winfo_children():
                collect(child)

        collect(self.editor.window)
        for label in ("放大", "缩小", "100%"):
            self.assertIn(label, buttons)
        width = self.editor._photo.width()
        buttons["放大"].invoke()
        self.spin(lambda: self.editor._photo.width() > width)
        buttons["缩小"].invoke()
        self.spin(lambda: self.editor.preview_zoom.get() == "100%")
        self.zoom(1.2)
        buttons["100%"].invoke()
        self.spin(lambda: self.editor.preview_zoom.get() == "100%")
        self.assertAlmostEqual(self.editor._preview_scale, 1.0)

    def test_zoom_limits_bound_render_dimensions(self):
        self.show()
        original_size = (self.editor._photo.width(), self.editor._photo.height())
        actual_render = toc_editor.render_page
        with patch.object(toc_editor, "render_page", wraps=actual_render) as render:
            self.zoom(100)
            self.assertEqual(self.editor._preview_scale, 3.0)
            self.assertEqual(self.editor.preview_zoom.get(), "300%")
            self.assertEqual(render.call_args.kwargs,
                             {"max_width": 1950, "max_height": 2550, "max_scale": 6.0})
            for baseline, actual in zip(original_size, (self.editor._photo.width(), self.editor._photo.height())):
                self.assertAlmostEqual(actual, baseline * 3, delta=2)
            self.zoom(0.001)
            self.assertEqual(self.editor._preview_scale, 0.5)
            self.assertEqual(self.editor.preview_zoom.get(), "50%")
            self.assertEqual(render.call_args.kwargs,
                             {"max_width": 325, "max_height": 425, "max_scale": 1.0})
            for baseline, actual in zip(original_size, (self.editor._photo.width(), self.editor._photo.height())):
                self.assertAlmostEqual(actual, baseline * 0.5, delta=2)

    def test_zoom_keeps_current_page_center_and_new_page_starts_at_top(self):
        self.show()
        self.zoom(2)
        canvas = self.editor.canvas
        canvas.xview_moveto(0.2)
        canvas.yview_moveto(0.25)

        def center():
            return (canvas.canvasx(canvas.winfo_width() / 2) / self.editor._photo.width(),
                    canvas.canvasy(canvas.winfo_height() / 2) / self.editor._photo.height())

        before = center()
        self.zoom(1.2)
        after = center()
        for expected, actual in zip(before, after):
            self.assertAlmostEqual(expected, actual, delta=0.025)
        self.show(2)
        self.assertLessEqual(canvas.yview()[0], 0.005)
        self.assertLessEqual(canvas.xview()[0], 0.005)

    def test_rapid_control_wheel_combines_render_requests(self):
        self.show()
        with patch.object(toc_editor, "render_page", wraps=toc_editor.render_page) as render:
            for _ in range(4):
                self.editor.canvas.event_generate("<MouseWheel>", delta=120, state=0x0004)
            self.settle(0.6)
            self.assertEqual(render.call_count, 1)
        self.assertGreater(self.editor._preview_scale, 1.5)

    def test_preview_controls_without_pdf_do_not_raise_or_write(self):
        self.editor.pdf.set("")
        with patch.object(toc_editor, "render_page") as render:
            self.editor.zoom_preview(1.2)
            self.editor.reset_preview_zoom()
            self.wheel(-120)
            self.wheel(120, control=True)
            self.settle()
            render.assert_not_called()
        self.assertEqual(self.errors, [])

    def test_close_cancels_pending_zoom_render(self):
        self.show()
        with patch.object(toc_editor, "render_page", wraps=toc_editor.render_page) as render:
            self.wheel(120, control=True)
            self.editor.close()
            self.settle()
            render.assert_not_called()

    def test_zoom_discards_inflight_old_scale_before_delayed_render(self):
        actual_render = toc_editor.render_page
        entered, release_old, zoom_entered, release_zoom = (threading.Event() for _ in range(4))

        def render(pdf, page, **kwargs):
            if not entered.is_set():
                entered.set()
                release_old.wait(3)
                return actual_render(pdf, page, max_width=300, max_height=400)
            zoom_entered.set()
            release_zoom.wait(3)
            return actual_render(pdf, page, **kwargs)

        try:
            with patch.object(toc_editor, "render_page", side_effect=render):
                self.editor.preview_page.set("1")
                self.editor.show_page()
                self.assertTrue(entered.wait(2))
                self.wheel(120, control=True)
                release_old.set()
                self.spin(zoom_entered.is_set)
                self.assertIsNone(self.editor._photo)
                release_zoom.set()
                self.spin(lambda: self.editor._photo is not None)
                self.assertGreater(self.editor._photo.width(), 650)
        finally:
            release_old.set()
            release_zoom.set()

    def test_older_async_render_does_not_replace_new_page(self):
        actual_render = toc_editor.render_page
        first_entered, release_first, second_finished = (threading.Event() for _ in range(3))
        second_png = actual_render(self.pdf, 2, max_width=650, max_height=850)

        def render(pdf, page, **kwargs):
            if page == 1:
                first_entered.set()
                release_first.wait(3)
                return actual_render(pdf, page, max_width=300, max_height=400)
            second_finished.set()
            return second_png

        try:
            with patch.object(toc_editor, "render_page", side_effect=render):
                self.editor.preview_page.set("1")
                self.editor.show_page()
                self.assertTrue(first_entered.wait(2))
                self.editor.preview_page.set("2")
                self.editor.show_page()
                release_first.set()
                self.spin(lambda: second_finished.is_set() and self.editor._photo is not None)
                self.assertEqual(self.editor._photo.width(), pymupdf.Pixmap(second_png).width)
                self.assertEqual(self.editor.preview_page.get(), "2")
        finally:
            release_first.set()


if __name__ == "__main__":
    unittest.main()
