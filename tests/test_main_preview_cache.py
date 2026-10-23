"""Preview cache reduces actual renderer calls without changing PNG results."""

import gc
import hashlib
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import test_main_shortcuts_preview as fixtures
import bookmarks_gui
from gui_support import render_page
from session_cache import pdf_identity


class MainPreviewCacheTests(unittest.TestCase):
    setUp = fixtures.MainShortcutsPreviewTests.setUp
    pump = fixtures.MainShortcutsPreviewTests.pump
    load = fixtures.MainShortcutsPreviewTests.load

    def tearDown(self):
        if not self.main.closed:
            return fixtures.MainShortcutsPreviewTests.tearDown(self)
        self.main.executor.shutdown(wait=True, cancel_futures=True)
        self.main = None
        self.root = None
        gc.collect()
        self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.inputs}, self.hashes)
        self.temporary.cleanup()
        self.assertEqual(self.errors, [])

    def test_same_pdf_page_size_reuses_png_and_zoom_has_its_own_key(self):
        token = self.main._render_token
        with patch.object(bookmarks_gui, "render_page", wraps=render_page) as render:
            self.main._render_worker(token, self.pdfs[0], 1, 300)
            first = self.main.events.get_nowait()[1][3]
            self.main._render_worker(token, self.pdfs[0], 1, 300)
            second = self.main.events.get_nowait()[1][3]
            self.assertEqual(first, second)
            self.assertEqual(render.call_count, 1)
            self.main._render_worker(token, self.pdfs[0], 1, 300, 1.5)
            larger = self.main.events.get_nowait()[1][3]
            self.assertNotEqual(first, larger)
            self.assertEqual(render.call_count, 2)
            render.assert_called_with(self.pdfs[0], 1, max_width=450, max_height=1500, max_scale=3.0)
        self.assertIs(self.main.session_cache, self.root._pdf_session_cache)
        self.assertGreaterEqual(self.main.session_cache.hits, 1)
        self.assertLessEqual(self.main.session_cache.used_bytes, 64 * 1024 * 1024)

    def test_identity_change_invalidates_preview_and_recognition_for_same_path(self):
        pdf = self.folder / "缓存身份测试.pdf"
        pdf.write_bytes(self.pdfs[0].read_bytes())
        old = pdf_identity(pdf)
        self.main.session_cache.put("recognition", 1, ["旧识别"], document=old)
        with patch.object(bookmarks_gui, "render_page", wraps=render_page) as render:
            self.main._render_worker(self.main._render_token, pdf, 1, 300)
            self.main.events.get_nowait()
            stat = pdf.stat()
            os.utime(pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
            new = pdf_identity(pdf)
            self.assertNotEqual(old, new)
            self.main._render_worker(self.main._render_token, pdf, 1, 300)
            self.main.events.get_nowait()
            self.assertEqual(render.call_count, 2)
        self.assertEqual(self.main.session_cache.count, 1)
        self.assertIsNone(self.main.session_cache.get("recognition", 1, document=new))

    def test_pdf_changed_during_render_does_not_enqueue_stale_png(self):
        pdf = self.folder / "渲染期间变化.pdf"
        pdf.write_bytes(self.pdfs[0].read_bytes())

        def change_during_render(*args, **kwargs):
            data = render_page(*args, **kwargs)
            stat = pdf.stat()
            os.utime(pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
            return data

        with patch.object(bookmarks_gui, "render_page", side_effect=change_during_render):
            self.main._render_worker(self.main._render_token, pdf, 1, 300)
        kind, payload = self.main.events.get_nowait()
        self.assertEqual(kind, "render_done")
        self.assertIsNone(payload[3])
        self.assertIn("PDF 在预览期间发生变化", payload[4])
        self.assertEqual(self.main.session_cache.count, 0)

    def test_closing_during_renderer_does_not_repopulate_cache_and_closes_details(self):
        entered, release = threading.Event(), threading.Event()
        self.main._handle_drop_paths(self.inputs)
        self.main._show_file_details()
        details = self.main._file_details
        destroyed = []
        details.window.bind("<Destroy>", lambda event: destroyed.append(True)
                            if event.widget is details.window else None, add="+")
        self.main.session_cache.put("recognition", 1, ["临时缓存"])

        def slow_render(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("renderer test release did not arrive")
            return render_page(*args, **kwargs)

        with patch.object(bookmarks_gui, "render_page", side_effect=slow_render):
            future = self.main.executor.submit(self.main._render_worker, self.main._render_token,
                                               self.pdfs[0], 1, 300)
            self.assertTrue(entered.wait(3))
            try:
                self.main._close()
                self.assertEqual(destroyed, [True])
                self.assertEqual(self.main.session_cache.count, 0)
            finally:
                release.set()
                future.result(timeout=5)
        self.assertEqual(self.main.session_cache.used_bytes, 0)


if __name__ == "__main__":
    unittest.main()
