"""Reopened review information must describe the current draft and PDF bytes."""

import time
import unittest
from unittest.mock import patch

import test_editor_delete_shortcut as fixtures
from session_cache import pdf_identity
from source_preview import render_source_crop


class EditorReviewFreshnessTests(unittest.TestCase):
    setUp = fixtures.DeleteShortcutTests.setUp
    tearDown = fixtures.DeleteShortcutTests.tearDown
    load = fixtures.DeleteShortcutTests.load
    choose = fixtures.DeleteShortcutTests.choose

    def spin(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("只读审阅未在时限内完成")

    def test_reopening_mapping_preview_uses_current_mapping_and_current_draft(self):
        first = self.editor.preview_mapping()
        self.assertEqual(first.preview.changed, 0)
        self.editor.offset.set("2")
        second = self.editor.preview_mapping()
        self.assertEqual(second.preview.changed, 4)
        self.assertEqual([sample.after for sample in second.preview.samples], [3, 4, 5, 6])
        self.editor.draft.entries[0].printed_page = None
        third = self.editor.preview_mapping()
        self.assertEqual(third.preview.changed, 3)
        self.assertEqual([sample.index for sample in third.preview.samples], [1, 2, 3])

    def test_reopening_issue_list_recomputes_after_confirmation(self):
        first = self.editor.show_issues()
        self.assertTrue(any(issue.code == "unconfirmed" for issue in first.issues))
        for entry in self.editor.draft.entries:
            entry.confirmed = True
        self.editor._refresh()
        current = self.editor.show_issues()
        self.assertFalse(any(issue.code == "unconfirmed" for issue in current.issues))

    def test_pdf_change_during_source_crop_never_displays_stale_image(self):
        self.editor.draft.entries[1].source_page = 1
        self.editor.draft.entries[1].source_rect = (.1, .1, .8, .15)
        self.choose(1)
        document = pdf_identity(self.pdf)
        key = (document, 1, (.1, .1, .8, .15), 640, 150)
        def render_then_change(path, page, rect):
            result = render_source_crop(path, page, rect)
            self.pdf.write_bytes(self.pdf_bytes + b"\n% synthetic changed during crop\n")
            return result
        try:
            with patch("source_preview.render_source_crop", side_effect=render_then_change):
                self.editor.source_compare.set(True)
                self.editor._update_source_crop()
                future = self.editor._source_future
                self.spin(lambda: future.done() and self.editor.events.empty())
            self.assertIsNone(self.editor._source_photo, "Old-PDF source crop was displayed after its PDF identity changed")
            self.assertIsNone(self.editor.session_cache.get("source_crop", key, document=document))
        finally:
            self.pdf.write_bytes(self.pdf_bytes)


if __name__ == "__main__":
    unittest.main()
