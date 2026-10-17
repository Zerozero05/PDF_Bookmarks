"""Closing an offscreen editor releases rendered bytes awaiting the Tk poll."""

from concurrent.futures import ThreadPoolExecutor
import gc
import hashlib
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
import weakref

import pymupdf

import toc_editor


class EditorResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-editor-resources-")
        self.pdf = Path(self.temporary.name) / "synthetic.pdf"
        with pymupdf.open() as document:
            document.new_page().insert_text((50, 50), "Synthetic queued preview")
            document.save(self.pdf)
        self.original = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.root = tk.Tk()
        self.root.withdraw()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.editor = toc_editor.open_editor(self.root, self.executor, self.pdf, draft_dir=None)
        self.editor.window.geometry("1240x900+30000+30000")
        self.editor.window.attributes("-topmost", False)
        self.root.update()

    def tearDown(self):
        if self.editor is not None:
            self.editor.close()
        self.executor.shutdown(wait=True)
        self.root.update()
        self.root.destroy()
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.original)
        self.temporary.cleanup()

    def test_close_releases_render_queued_before_poll(self):
        self.editor.preview_page.set("1")
        self.editor.show_page()
        # Block this thread until the real renderer returns; Tk cannot poll yet.
        self.editor._render_future.result(timeout=10)
        with self.editor.events.mutex:
            rendered = [event for event in self.editor.events.queue
                        if event[0] == "render" and isinstance(event[2], bytes)]
        self.assertEqual(len(rendered), 1)
        self.assertGreater(len(rendered[0][2]), 0)
        self.editor.close()
        self.assertTrue(self.editor.events.empty(), "Closed editor still retains a queued PNG payload")
        self.assertIsNone(self.editor._photo)
        self.assertEqual(len(self.editor.history._states), 0)

    def test_closed_editor_is_released_while_shared_root_and_executor_live(self):
        reference = weakref.ref(self.editor)
        self.editor.close()
        self.root.update()
        self.editor = None
        gc.collect()
        self.assertTrue(self.root.winfo_exists())
        self.assertTrue(self.executor.submit(lambda: True).result(timeout=2))
        self.assertIsNone(reference(), "Closed editor is still held by registered Tk variable callbacks")


if __name__ == "__main__":
    unittest.main()
