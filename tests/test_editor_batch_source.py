"""Integrated batch edits and source-row comparison protect real draft boundaries."""

import hashlib
import threading
import time
import unittest
from unittest.mock import patch

import test_editor_delete_shortcut as fixtures
from source_preview import render_source_crop


class EditorBatchSourceTests(unittest.TestCase):
    setUp = fixtures.DeleteShortcutTests.setUp
    tearDown = fixtures.DeleteShortcutTests.tearDown
    load = fixtures.DeleteShortcutTests.load
    choose = fixtures.DeleteShortcutTests.choose
    snapshot = fixtures.DeleteShortcutTests.snapshot

    def spin(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("Source comparison did not reach the expected state")

    def test_batch_preview_changes_only_selected_titles_and_one_undo_restores_every_field(self):
        self.load((1, 2, 2, 1))
        for index, entry in enumerate(self.editor.draft.entries):
            entry.title = f"{index + 1}. 基本概念 x^2"
            entry.source_page, entry.source_rect = 1, (.1, .1 + index * .1, .8, .15 + index * .1)
        self.editor._refresh(1)
        self.choose(1, 3)
        before = self.snapshot()
        prior_count = len(self.editor.history._states)
        window = self.editor.batch_titles()
        window.form_vars["find"].set("基本概念")
        window.form_vars["replace"].set("基本定义")
        window.preview_button.invoke()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([change.index for change in window.changes], [1, 3])
        window.apply_button.invoke()
        self.assertFalse(window.winfo_exists())
        after = self.snapshot()
        for index in (0, 2):
            self.assertEqual(after["entries"][index], before["entries"][index])
        for index in (1, 3):
            self.assertEqual(after["entries"][index]["title"], before["entries"][index]["title"].replace("基本概念", "基本定义"))
            self.assertFalse(after["entries"][index]["confirmed"])
            for key in ("level", "printed_page", "pdf_page", "source_page", "source_rect"):
                self.assertEqual(after["entries"][index][key], before["entries"][index][key])
        self.assertEqual(len(self.editor.history._states), prior_count + 1)
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)
        self.editor.redo()
        self.assertEqual(self.snapshot(), after)

    def test_empty_title_and_changed_unselected_draft_block_the_whole_batch(self):
        self.choose(1)
        before = self.snapshot()
        window = self.editor.batch_titles()
        window.form_vars["find"].set(self.editor.draft.entries[1].title)
        window.preview_button.invoke()
        self.assertTrue(window.apply_button.instate(["disabled"]))
        window.apply_button.invoke()
        self.assertEqual(self.snapshot(), before)
        self.assertIn("为空", window.status.get())
        window.form_vars["find"].set("")
        window.form_vars["prefix"].set("新 ")
        window.preview_button.invoke()
        self.editor.draft.entries[0].note = "外部新证据，不能被批量窗口覆盖"
        changed = self.snapshot()
        window.apply_button.invoke()
        self.assertTrue(window.winfo_exists())
        self.assertIn("草稿已变化", window.status.get())
        self.assertEqual(self.snapshot(), changed)

    def test_stale_selected_title_and_busy_state_cannot_commit_preview(self):
        self.choose(1, 2)
        window = self.editor.batch_titles()
        window.form_vars["suffix"].set(" 补充")
        window.preview_button.invoke()
        self.editor.draft.entries[1].title = "刚刚手工修改的标题"
        changed = self.snapshot()
        window.apply_button.invoke()
        self.assertEqual(self.snapshot(), changed)
        self.assertIn("草稿已变化", window.status.get())
        window.destroy()
        self.editor._refresh(1)
        self.choose(1)
        window = self.editor.batch_titles()
        window.form_vars["suffix"].set(" 第二次补充")
        window.preview_button.invoke()
        changed = self.snapshot()
        self.editor.busy = True
        try:
            window.apply_button.invoke()
            self.assertEqual(self.snapshot(), changed)
            self.assertTrue(window.winfo_exists())
        finally:
            self.editor.busy = False

    def test_missing_source_is_explicit_and_never_guesses_a_crop(self):
        self.choose(1)
        before = self.snapshot()
        with patch("source_preview.render_source_crop") as render:
            self.editor.source_compare.set(True)
            self.editor._update_source_crop()
            self.root.update()
            self.assertIn("没有原目录行位置", self.editor.source_crop_status.get())
            self.assertIsNone(self.editor._source_photo)
            render.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_source_crop_is_readonly_async_and_hiding_releases_displayed_image(self):
        self.editor.draft.entries[1].source_page = 1
        self.editor.draft.entries[1].source_rect = (.1, .1, .8, .15)
        self.choose(1)
        before = self.snapshot()
        sha = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.editor.source_compare.set(True)
        self.editor._update_source_crop()
        self.spin(lambda: self.editor._source_photo is not None)
        image = self.editor._source_photo
        self.assertGreater(image.width(), 0)
        self.assertLessEqual(image.width(), 640)
        self.assertLessEqual(image.height(), 150)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), sha)
        self.editor.source_compare.set(False)
        self.editor._update_source_crop()
        self.root.update()
        self.assertIsNone(self.editor._source_photo)
        self.assertFalse(self.editor.source_crop_frame.winfo_ismapped())
        self.assertEqual(str(self.editor.source_crop_label.cget("image")), "")

    def test_hiding_pending_source_ignores_late_crop_and_close_releases_image(self):
        self.editor.draft.entries[1].source_page = 1
        self.editor.draft.entries[1].source_rect = (.1, .1, .8, .15)
        self.choose(1)
        entered, release = threading.Event(), threading.Event()

        def delayed_crop(*args, **kwargs):
            entered.set()
            if not release.wait(4):
                raise TimeoutError("source crop test release was not signaled")
            return render_source_crop(*args, **kwargs)

        with patch("source_preview.render_source_crop", side_effect=delayed_crop):
            self.editor.source_compare.set(True)
            self.editor._update_source_crop()
            self.assertTrue(entered.wait(3))
            self.editor.source_compare.set(False)
            self.editor._update_source_crop()
            release.set()
            self.spin(lambda: self.editor._source_future.done())
            self.assertIsNone(self.editor._source_photo)
        self.editor.source_compare.set(True)
        self.editor._update_source_crop()
        self.spin(lambda: self.editor._source_photo is not None)
        self.editor.on_settings_changed = None
        self.editor.close()
        self.assertTrue(self.editor.closed)
        self.assertIsNone(self.editor._source_photo)


if __name__ == "__main__":
    unittest.main()
