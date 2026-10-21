"""Tree-only selection shortcuts and recursive display state, without data edits."""

import unittest

import test_editor_delete_shortcut as fixtures


class TreeSelectionTests(unittest.TestCase):
    setUp = fixtures.DeleteShortcutTests.setUp
    tearDown = fixtures.DeleteShortcutTests.tearDown
    load = fixtures.DeleteShortcutTests.load
    choose = fixtures.DeleteShortcutTests.choose
    snapshot = fixtures.DeleteShortcutTests.snapshot

    def tree_mode(self):
        self.load((1, 2, 3, 1, 2, 3))
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()

    def press(self, key):
        self.editor.tree.focus_force()
        self.root.update()
        self.editor.tree.event_generate(key)
        self.root.update()

    def test_ctrl_a_includes_collapsed_children_without_editing_model(self):
        self.tree_mode()
        self.choose(3)
        self.editor.set_selected_expanded(False)
        before, history = self.snapshot(), len(self.editor.history._states)
        self.press("<Control-a>")
        self.assertEqual(set(self.editor.tree.selection()), {str(index) for index in range(6)})
        self.assertEqual(self.editor.tree.focus(), "3")
        self.assertFalse(self.editor.tree.item("3", "open"))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.editor.history._states), history)

    def test_filtered_all_selects_matches_not_hidden_rows_or_context_ancestors(self):
        self.tree_mode()
        self.editor.draft.entries[2].title = "match leaf"
        self.editor.draft.entries[5].title = "match another"
        self.editor.search_text.set("match")
        self.editor._filter_changed()
        self.assertTrue(self.editor.tree.exists("0"))
        self.assertIn("context", self.editor.tree.item("0", "tags"))
        self.press("<Control-a>")
        self.assertEqual(set(self.editor.tree.selection()), {"2", "5"})
        self.assertEqual(len(self.editor.draft.entries), 6)

    def test_clear_selection_commits_valid_edit_and_leaves_no_implicit_first_row(self):
        self.choose(1)
        self.editor.title.set("updated title")
        self.editor.entry_menu.invoke("清除选中")
        self.root.update()
        self.assertEqual(self.editor.draft.entries[1].title, "updated title")
        self.assertEqual(self.editor.tree.selection(), ())
        self.assertEqual(self.editor.tree.focus(), "")
        self.assertIsNone(self.editor._editing_index)
        self.assertEqual(self.editor.title.get(), "")

    def test_invalid_edit_blocks_both_all_and_clear_without_losing_input(self):
        self.choose(1)
        self.editor.target.set("invalid")
        before = self.snapshot()
        for method in (self.editor.select_all_entries, self.editor.clear_selection):
            self.assertEqual(method(), "break")
            self.assertEqual(self.editor.tree.selection(), ("1",))
            self.assertEqual(self.editor.target.get(), "invalid")
            self.assertEqual(self.snapshot(), before)

    def test_escape_then_plus_minus_reaches_all_depths_without_selection_or_history_changes(self):
        self.tree_mode()
        before, history = self.snapshot(), len(self.editor.history._states)
        self.press("<Escape>")
        self.assertEqual(self.editor.tree.selection(), ())
        for key, expanded in (("<minus>", False), ("<plus>", True)):
            self.press(key)
            for index in (0, 1, 3, 4):
                self.assertEqual(bool(self.editor.tree.item(str(index), "open")), expanded)
            self.assertEqual(self.editor.tree.selection(), ())
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(len(self.editor.history._states), history)

    def test_selection_menus_and_shortcuts_keep_table_mode_and_busy_guards(self):
        self.editor.entry_menu.invoke("全选当前目录项")
        self.assertEqual(len(self.editor.tree.selection()), 4)
        self.editor._set_busy(True)
        self.editor.clear_selection()
        self.assertEqual(len(self.editor.tree.selection()), 4)
        self.editor._set_busy(False)
        self.editor.clear_selection()
        self.editor.set_selected_expanded(False)
        self.assertTrue(self.editor.tree.item("0", "open"))
        self.editor.draft = None
        self.assertEqual(self.editor.select_all_entries(), "break")

    def test_ctrl_a_and_escape_in_entry_do_not_select_or_clear_tree(self):
        self.choose(1)
        before = self.snapshot()
        entry = next(widget for widget in self.editor._controls
            if isinstance(widget, fixtures.toc_editor.ttk.Entry)
            and str(widget.cget("textvariable")) == str(self.editor.title))
        entry.focus_force()
        self.root.update()
        for key in ("<Control-a>", "<Escape>"):
            entry.event_generate(key)
            self.root.update()
            self.assertEqual(self.editor.tree.selection(), ("1",))
            self.assertEqual(self.editor.title.get(), "Row 1")
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
