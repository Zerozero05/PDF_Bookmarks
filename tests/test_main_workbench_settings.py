"""Workbench preferences and saved JSON survive concurrent main-window work."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import pymupdf
from tkinterdnd2 import TkinterDnD

from bookmarks_gui import BookmarkWindow
from gui_support import load_settings, save_settings


class WorkbenchMainTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="zotero-modeless-main-")
        self.folder = Path(self.temporary.name)
        self.settings = self.folder / "profile/settings.json"
        self.root = TkinterDnD.Tk()
        self.root.geometry("1100x860+20000+20000")
        self.main = BookmarkWindow(self.root, settings_path=self.settings)
        self.root.update_idletasks()
        self.pdfs = []

    def tearDown(self):
        self.root.update_idletasks()
        if self.main.editor is not None:
            self.main.editor.close()
        self.main.busy = False
        self.main._close()
        self.main.executor.shutdown(wait=True)
        for pdf, original in self.pdfs:
            self.assertEqual(hashlib.sha256(pdf.read_bytes()).hexdigest(), original)
        self.temporary.cleanup()

    def pair(self, name):
        pdf = self.folder / (name + ".pdf")
        with pymupdf.open() as document:
            document.new_page()
            document.new_page()
            document.save(pdf)
        self.pdfs.append((pdf, hashlib.sha256(pdf.read_bytes()).hexdigest()))
        toc = pdf.with_suffix(".toc.json")
        toc.write_text(json.dumps({"version": 1, "bookmarks": [{"title": name, "pdf_page": 2}]}), encoding="utf-8")
        return pdf, toc

    def pump(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.root.update()
            if predicate():
                return
            time.sleep(.01)
        self.fail("Main-window operation did not complete")

    def test_new_settings_roundtrip_preserves_original_settings(self):
        settings = load_settings(self.settings)
        settings.update(backup=False, clear_cache=True, topmost=True,
                        editor_topmost=False, editor_geometry="1280x900",
                        toc_save_mode="custom", toc_save_dir=str(self.folder / "中文目录"))
        save_settings(settings, self.settings)
        restored = load_settings(self.settings)
        for name, value in settings.items():
            self.assertEqual(restored.get(name), value, name)

    def test_legacy_topmost_is_inherited_once_then_editor_can_unpin_independently(self):
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({"topmost": True, "backup": False}), encoding="utf-8")
        restored = load_settings(self.settings)
        self.assertTrue(restored["topmost"])
        self.assertTrue(restored["editor_topmost"])
        restored["editor_topmost"] = False
        save_settings(restored, self.settings)
        restored = load_settings(self.settings)
        self.assertTrue(restored["topmost"])
        self.assertFalse(restored["editor_topmost"])
        self.assertFalse(restored["backup"])

    def test_workbench_preferences_persist_immediately_without_changing_backup(self):
        self.main.backup.set(False)
        self.main.clear_cache.set(True)
        updates = {"editor_geometry": "1280x900", "editor_topmost": True,
                   "toc_save_mode": "custom", "toc_save_dir": str(self.folder / "目录输出")}
        self.main._editor_settings_changed(updates)
        restored = load_settings(self.settings)
        for name, value in updates.items():
            self.assertEqual(restored[name], value)
        self.assertFalse(restored["backup"])
        self.assertTrue(restored["clear_cache"])
        self.assertFalse(self.main.topmost.get())

    def test_busy_main_keeps_saved_pair_until_work_completes(self):
        first = self.pair("原列表教材")
        second = self.pair("新目录教材")
        self.main._handle_drop_paths(first)
        self.main._set_busy(True)
        self.main._editor_saved(*second)
        self.assertEqual(self.main.pending_editor_saves, [second])
        self.assertEqual(len(self.main.items), 1)
        self.main.events.put(("preview_done", []))
        self.pump(lambda: not self.main.busy and len(self.main.plans) == 2)
        self.assertEqual(self.main.pending_editor_saves, [])
        self.assertEqual({item["pdf_path"]: item["toc_path"] for item in self.main.items.values()},
                         {first[0]: first[1], second[0]: second[1]})

    def test_main_passes_workbench_preferences_and_callback(self):
        with patch("toc_editor.open_editor", return_value=None) as opened:
            self.main._open_editor()
        self.assertEqual(opened.call_args.kwargs["editor_settings"], self.main.editor_settings)
        self.assertEqual(opened.call_args.kwargs["on_settings_changed"], self.main._editor_settings_changed)


if __name__ == "__main__":
    unittest.main()
