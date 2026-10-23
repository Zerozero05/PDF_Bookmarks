"""Review refreshes retain browsing identity without changing the draft."""

from unittest.mock import patch
import unittest

import test_editor_delete_shortcut as fixtures


class ReviewContextTests(unittest.TestCase):
    setUp = fixtures.DeleteShortcutTests.setUp
    tearDown = fixtures.DeleteShortcutTests.tearDown
    load = fixtures.DeleteShortcutTests.load
    choose = fixtures.DeleteShortcutTests.choose
    snapshot = fixtures.DeleteShortcutTests.snapshot

    def test_search_opens_ancestors_temporarily_then_restores_collapse(self):
        self.load((1, 2, 3, 1, 2))
        editor = self.editor
        editor.view_mode.set("目录树")
        editor._view_changed()
        editor.tree.item("0", open=False)
        self.choose(3)
        before = self.snapshot()
        editor.search_text.set("Row 2")
        editor._filter_changed()
        self.assertTrue(editor.tree.item("0", "open"))
        self.assertEqual(editor.tree.selection(), ("2",))
        editor.search_text.set("")
        editor._filter_changed()
        self.assertFalse(editor.tree.item("0", "open"))
        self.assertEqual(editor.tree.selection(), ("3",))
        self.assertEqual(self.snapshot(), before)

    def test_structural_refresh_does_not_transfer_collapse_to_new_index(self):
        self.load((1, 2, 1, 2))
        editor = self.editor
        editor.view_mode.set("目录树")
        editor._view_changed()
        editor.tree.item("2", open=False)
        editor.draft.entries[0:0] = [fixtures.DraftEntry(1, "New", None, 1)]
        editor._refresh()
        self.assertTrue(editor.tree.item("2", "open"))
        self.assertFalse(editor.tree.item("3", "open"))

    def test_enter_confirmation_updates_rows_without_rebuilding_tree(self):
        self.choose(0, 2)
        with patch.object(self.editor.tree, "delete", wraps=self.editor.tree.delete) as delete:
            self.editor.confirm_selected()
        delete.assert_not_called()
        self.assertTrue(self.editor.draft.entries[0].confirmed)
        self.assertTrue(self.editor.draft.entries[2].confirmed)
        self.editor.undo()
        self.assertFalse(self.editor.draft.entries[0].confirmed)
        self.assertFalse(self.editor.draft.entries[2].confirmed)

    def test_undo_move_keeps_selected_entry_identity_instead_of_numeric_row(self):
        self.choose(1)
        self.editor.move_entry(1)
        self.assertEqual(self.editor.tree.selection(), ("2",))
        self.assertEqual(self.editor.title.get(), "Row 1")
        self.editor.undo()
        self.assertEqual(self.editor.tree.selection(), ("1",))
        self.assertEqual(self.editor.title.get(), "Row 1")
        self.editor.redo()
        self.assertEqual(self.editor.tree.selection(), ("2",))
        self.assertEqual(self.editor.title.get(), "Row 1")

    def test_invalid_field_is_highlighted_and_cleared_without_changing_model(self):
        self.choose(0)
        before = self.snapshot()
        self.editor.target.set("-")
        self.editor._cancel_edit_timer()
        target = self.editor._field_widgets[str(self.editor.target)]
        self.assertEqual(str(target.cget("style")), "Invalid.TEntry")
        self.assertFalse(self.editor._apply_auto())
        self.assertEqual(self.snapshot(), before)
        self.editor.target.set("2")
        self.assertEqual(str(target.cget("style")), "TEntry")
        self.assertTrue(self.editor._apply_auto())

    def test_mapping_preview_is_read_only_and_issue_location_clears_filter(self):
        from dataclasses import asdict
        from review_tools import preview_mapping
        before = asdict(self.editor.draft)
        preview_mapping(self.editor.draft, {"offset": 1})
        self.assertEqual(asdict(self.editor.draft), before)
        self.editor.search_text.set("Row 1")
        self.editor._filter_changed()
        self.editor._locate_issue(2)
        self.assertEqual(self.editor.search_text.get(), "")
        self.assertEqual(self.editor.tree.selection(), ("2",))


if __name__ == "__main__":
    unittest.main()
