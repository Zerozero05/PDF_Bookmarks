"""Optional TOC cleanup uses only temporary files and verified PDF writes."""

import json
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch

import pymupdf

import bookmarks_gui as gui
from bookmarks_core import inspect_pdf
import gui_support as support
import test_gui as fixtures
from test_gui import make_pdf, make_toc


class DeleteTocTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="zotero-delete-toc-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.pdf = self.folder / "中文 教材.pdf"
        self.toc = self.folder / "异名 目录.json"
        make_pdf(self.pdf)
        make_toc(self.toc)
        self.plan = inspect_pdf(self.pdf, self.toc)
        self.window = gui.BookmarkWindow.__new__(gui.BookmarkWindow)
        self.window.events = queue.Queue()

    def write(self, enabled=True, plans=None, existing="replace", signatures=None):
        plans = plans or [("first", self.plan)]
        if signatures is None:
            signatures = {iid: support.toc_file_signature(plan.toc_path) for iid, plan in plans}
        self.window._write_worker(plans, existing, {"backup": False}, enabled, signatures)
        events = []
        while not self.window.events.empty():
            events.append(self.window.events.get_nowait())
        return events[-1][1], [payload for kind, payload in events if kind == "write_item"]

    def test_default_disabled_and_settings_persist_without_changing_old_values(self):
        config = self.folder / "settings.json"
        config.write_text(json.dumps({"backup": False, "topmost": True}), encoding="utf-8")
        settings = support.load_settings(config)
        self.assertFalse(settings["delete_toc"])
        settings["delete_toc"] = True
        support.save_settings(settings, config)
        restored = support.load_settings(config)
        self.assertTrue(restored["delete_toc"])
        self.assertFalse(restored["backup"])
        self.assertTrue(restored["topmost"])

    def test_enabled_deletes_only_used_json_after_verified_pdf_write(self):
        unrelated = self.folder / "其他目录.json"
        cache = self.folder / "jasminum-outline.json"
        unrelated.write_text("{}", encoding="utf-8")
        cache.write_text("{}", encoding="utf-8")
        result, states = self.write()
        self.assertEqual(result, (1, 0, [], []))
        self.assertFalse(self.toc.exists())
        self.assertTrue(unrelated.exists())
        self.assertTrue(cache.exists())
        self.assertIn("目录 JSON 已删除", states[-1][1])
        with pymupdf.open(self.pdf) as document:
            self.assertEqual(document.get_toc(), self.plan.rows)
            self.assertEqual(document.page_count, 2)

    def test_disabled_preserves_json_on_success(self):
        before = self.toc.read_bytes()
        result, _ = self.write(enabled=False)
        self.assertEqual(result, (1, 0, [], []))
        self.assertEqual(self.toc.read_bytes(), before)

    def test_skip_preserves_json(self):
        with pymupdf.open(self.pdf) as document:
            document.set_toc([[1, "已有书签", 1]])
            document.saveIncr()
        self.plan = inspect_pdf(self.pdf, self.toc)
        before = self.pdf.read_bytes()
        result, _ = self.write(existing="skip")
        self.assertEqual(result[:2], (0, 1))
        self.assertTrue(self.toc.exists())
        self.assertEqual(self.pdf.read_bytes(), before)

    def test_writer_failure_preserves_json_and_pdf(self):
        before = self.pdf.read_bytes()
        with patch.object(gui, "write_plan", side_effect=OSError("simulated replace failure")):
            result, states = self.write()
        self.assertEqual(result[:2], (0, 0))
        self.assertEqual(len(result[2]), 1)
        self.assertEqual(states[-1][1], "写入失败")
        self.assertTrue(self.toc.exists())
        self.assertEqual(self.pdf.read_bytes(), before)

    def test_unlink_failure_is_warning_with_pdf_still_successful(self):
        original = Path.unlink

        def fail_toc(path, *args, **kwargs):
            if path == self.toc:
                raise PermissionError("simulated sharing violation")
            return original(path, *args, **kwargs)

        with patch.object(Path, "unlink", fail_toc):
            result, states = self.write()
        self.assertEqual(result[:3], (1, 0, []))
        self.assertEqual(len(result[3]), 1)
        self.assertTrue(self.toc.exists())
        self.assertIn("已写入", states[-1][1])
        self.assertNotIn("写入失败", states[-1][1])
        with pymupdf.open(self.pdf) as document:
            self.assertEqual(document.get_toc(), self.plan.rows)

    def test_changed_json_after_preview_is_preserved(self):
        signatures = {"first": support.toc_file_signature(self.toc)}
        make_toc(self.toc, "工作台刚保存的新标题")
        result, _ = self.write(signatures=signatures)
        self.assertEqual(result[:3], (1, 0, []))
        self.assertEqual(len(result[3]), 1)
        self.assertTrue(self.toc.exists())

    def test_shared_json_deleted_only_after_both_pdf_writes(self):
        second = self.folder / "第二本.pdf"
        make_pdf(second)
        plans = [("first", self.plan), ("second", inspect_pdf(second, self.toc))]
        original = gui.write_plan
        calls = []

        def check_before_write(plan, **kwargs):
            self.assertTrue(self.toc.exists())
            calls.append(plan.pdf_path)
            return original(plan, **kwargs)

        with patch.object(gui, "write_plan", side_effect=check_before_write):
            result, _ = self.write(plans=plans)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result, (2, 0, [], []))
        self.assertFalse(self.toc.exists())

    def test_shared_json_preserved_if_one_write_fails_or_skips(self):
        second = self.folder / "第二本.pdf"
        make_pdf(second)
        with pymupdf.open(second) as document:
            document.set_toc([[1, "已有书签", 1]])
            document.saveIncr()
        plans = [("first", self.plan), ("second", inspect_pdf(second, self.toc))]
        original = gui.write_plan
        for mode in ("skip", "failure"):
            with self.subTest(mode=mode):
                make_pdf(self.pdf)
                plans[0] = ("first", inspect_pdf(self.pdf, self.toc))

                def skip_or_fail(plan, **kwargs):
                    if mode == "failure" and plan.pdf_path == second:
                        raise OSError("simulated second failure")
                    return original(plan, **kwargs)

                with patch.object(gui, "write_plan", side_effect=skip_or_fail):
                    result, states = self.write(plans=plans, existing="skip")
                self.assertEqual(result[0], 1)
                self.assertTrue(self.toc.exists())
                self.assertTrue(any("目录 JSON 保留" in state for _, state in states))

    def test_cleanup_rejects_missing_signature_cache_or_pdf_same_file(self):
        signature = support.toc_file_signature(self.toc)
        self.assertEqual(support.delete_written_toc(self.toc, None, [self.pdf])["status"], "retained")
        self.assertEqual(support.delete_written_toc(self.toc, signature, [self.toc])["status"], "retained")
        cache = self.folder / "jasminum-outline.json"
        make_toc(cache)
        self.assertEqual(support.delete_written_toc(cache, support.toc_file_signature(cache), [self.pdf])["status"], "retained")
        self.assertTrue(self.toc.exists())
        self.assertTrue(cache.exists())

    def test_shared_json_path_alias_is_retained_when_other_pdf_skips(self):
        second = self.folder / "第二本.pdf"
        make_pdf(second)
        with pymupdf.open(second) as document:
            document.set_toc([[1, "已有书签", 1]])
            document.saveIncr()
        nested = self.folder / "subfolder"
        nested.mkdir()
        alias = nested / ".." / self.toc.name
        self.assertTrue(alias.samefile(self.toc))
        plans = [("first", self.plan), ("second", inspect_pdf(second, alias))]
        result, _ = self.write(plans=plans, existing="skip")
        self.assertEqual(result[:2], (1, 1))
        self.assertTrue(self.toc.exists())

    def test_cleanup_preserves_symlink(self):
        link = self.folder / "linked.json"
        try:
            link.symlink_to(self.toc)
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        self.assertIsNone(support.toc_file_signature(link))
        self.assertEqual(support.delete_written_toc(link, None, [self.pdf])["status"], "retained")
        self.assertTrue(link.is_symlink())
        self.assertTrue(self.toc.exists())


class DeleteTocWindowTests(unittest.TestCase):
    # Reuse only the existing GUI fixture methods, without inheriting its tests.
    setUp = fixtures.GuiWindowTests.setUp
    new_window = fixtures.GuiWindowTests.new_window
    close_windows = fixtures.GuiWindowTests.close_windows
    pump = fixtures.GuiWindowTests.pump
    pdf_pair = fixtures.GuiWindowTests.pdf_pair
    preview = fixtures.GuiWindowTests.preview

    def test_preview_preserves_json_and_checkbox_changes_require_new_preview(self):
        pdf, toc = self.pdf_pair()
        before = pdf.read_bytes(), toc.read_bytes()
        self.window.delete_toc.set(True)
        self.window._handle_drop_paths([pdf, toc])
        self.preview()
        self.assertEqual((pdf.read_bytes(), toc.read_bytes()), before)
        self.assertIsNotNone(next(iter(self.window.items.values()))["toc_signature"])
        self.window.delete_toc.set(False)
        self.assertFalse(self.window.plans)
        self.assertEqual(str(self.window.write_button.cget("state")), "disabled")

    def test_option_persists_through_real_window_close(self):
        self.assertFalse(self.window.delete_toc.get())
        self.window.delete_toc.set(True)
        self.window._close()
        _, reopened = self.new_window()
        self.assertTrue(reopened.delete_toc.get())

    def test_cancelled_confirmation_retains_json_and_pdf(self):
        pdf, toc = self.pdf_pair()
        before = pdf.read_bytes(), toc.read_bytes()
        self.window.delete_toc.set(True)
        self.window._handle_drop_paths([pdf, toc])
        self.preview()
        with patch.object(gui.messagebox, "askyesno", return_value=False):
            self.window._write()
        self.assertFalse(self.window.busy)
        self.assertEqual((pdf.read_bytes(), toc.read_bytes()), before)

    def test_changed_option_during_confirmation_does_not_write(self):
        pdf, toc = self.pdf_pair()
        before = pdf.read_bytes(), toc.read_bytes()
        self.window._handle_drop_paths([pdf, toc])
        self.preview()

        def change_setting(*args, **kwargs):
            self.window.delete_toc.set(True)
            return True

        with patch.object(gui.messagebox, "askyesno", side_effect=change_setting):
            self.window._write()
        self.assertFalse(self.window.busy)
        self.assertEqual((pdf.read_bytes(), toc.read_bytes()), before)


if __name__ == "__main__":
    unittest.main()
