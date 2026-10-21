"""Display-only focus mode and local directory context operations."""

import unittest
from unittest.mock import patch

import test_editor_delete_shortcut as fixtures
from ui_theme import apply_theme, menu_colors


class EditorFocusContextTests(unittest.TestCase):
    setUp = fixtures.DeleteShortcutTests.setUp
    tearDown = fixtures.DeleteShortcutTests.tearDown
    load = fixtures.DeleteShortcutTests.load
    choose = fixtures.DeleteShortcutTests.choose
    snapshot = fixtures.DeleteShortcutTests.snapshot

    def right_click(self, index):
        self.root.update_idletasks()
        box = self.editor.tree.bbox(str(index))
        self.assertTrue(box)
        self.editor.tree.event_generate("<Button-3>", x=20, y=box[1] + box[3] // 2)
        self.root.update()

    def test_focus_mode_preserves_invalid_edit_selection_history_preview_and_window(self):
        self.choose(1, 2)
        self.editor.target.set("unfinished")
        self.editor._cancel_edit_timer()
        before = self.snapshot()
        history = len(self.editor.history._states)
        geometry, minimum = self.editor.window.geometry(), self.editor.window.minsize()
        image, token = self.editor._photo, self.editor._render_token
        canvas = tuple(self.editor.canvas.find_all())
        for expected in (True, False, True, False):
            self.editor.view_menu.invoke("专注模式")
            self.root.update_idletasks()
            self.assertEqual(self.editor.focus_mode.get(), expected)
            for widget in (self.editor._focus_source, self.editor.source_tabs,
                           self.editor._focus_options, self.editor._focus_save_options):
                self.assertEqual(bool(widget.winfo_manager()), not expected)
            self.assertFalse(hasattr(self.editor, "focus_button"))
            self.assertEqual(str(self.editor.window.cget("menu")), str(self.editor.menu_bar))
            self.assertEqual(self.editor.view_menu.entrycget("专注模式", "state"), "normal")
            self.assertTrue(self.editor.tree.winfo_ismapped())
            self.assertTrue(self.editor.canvas.winfo_ismapped())
            self.assertEqual(self.editor.target.get(), "unfinished")
            self.assertEqual(self.editor.tree.selection(), ("1", "2"))
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(len(self.editor.history._states), history)
            self.assertIs(self.editor._photo, image)
            self.assertEqual(self.editor._render_token, token)
            self.assertEqual(tuple(self.editor.canvas.find_all()), canvas)
            self.assertEqual(self.editor.window.geometry(), geometry)
            self.assertEqual(self.editor.window.minsize(), minimum)
        self.assertFalse(self.errors)

    def test_focus_restore_pack_order_keeps_advanced_and_busy_mode_exit_available(self):
        self.editor._set_busy(True)
        self.assertEqual(self.editor.view_menu.entrycget("专注模式", "state"), "normal")
        self.editor.view_menu.invoke("专注模式")
        self.editor.advanced_open.set(True)
        self.editor._toggle_advanced()
        self.root.update_idletasks()
        self.assertEqual(self.editor.mapping_tabs.winfo_manager(), "pack")
        self.editor.view_menu.invoke("专注模式")
        self.root.update_idletasks()
        packed = self.editor._feedback.master.pack_slaves()
        self.assertLess(packed.index(self.editor._focus_source), packed.index(self.editor.source_tabs))
        self.assertLess(packed.index(self.editor.source_tabs), packed.index(self.editor._feedback))
        self.assertEqual(packed[packed.index(self.editor._footer) + 1], self.editor._focus_save_options)
        self.assertEqual(self.editor.mapping_tabs.winfo_manager(), "pack")
        self.editor._set_busy(False)
        self.assertFalse(self.editor.focus_mode.get())

    def test_focus_and_layout_preferences_persist_without_changing_legacy_geometry(self):
        with patch.object(self.editor._pane_memory, "snapshot", return_value=58), \
                patch.object(self.editor._column_memory, "snapshot", return_value={"title": 245}):
            self.editor.view_menu.invoke("专注模式")
        updates = self.callback.call_args.args[0]
        self.assertIs(updates["editor_focus_mode"], True)
        self.assertEqual(updates["editor_pane_ratio"], 58)
        self.assertEqual(updates["editor_column_widths"], {"title": 245})
        self.assertEqual(updates["editor_geometry"], self.editor.window.geometry())
        self.assertEqual(updates["toc_save_mode"], self.editor.save_mode.get())
        self.assertEqual(updates["editor_confirm_multi_delete"], self.editor.confirm_multi_delete.get())

    def test_right_click_selected_row_keeps_multi_selection_and_uses_original_commands(self):
        self.choose(0, 2)
        before = self.snapshot()
        with patch.object(self.editor.context_menu, "tk_popup") as popup, \
                patch.object(self.editor.context_menu, "grab_release") as release:
            self.right_click(2)
        popup.assert_called_once()
        release.assert_called_once()
        self.assertEqual(self.editor.tree.selection(), ("0", "2"))
        self.assertEqual(self.snapshot(), before)
        self.question.return_value = False
        self.editor.context_menu.invoke("删除所选目录项")
        self.assertEqual(self.snapshot(), before)
        self.question.assert_called_once()
        self.question.return_value = True
        self.editor.context_menu.invoke("删除所选目录项")
        self.assertEqual([entry.title for entry in self.editor.draft.entries], ["Row 1", "Row 3"])
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)

    def test_right_click_other_row_blocks_invalid_edit_then_commits_valid_edit(self):
        self.choose(0)
        self.editor.target.set("invalid")
        self.editor._cancel_edit_timer()
        before = self.snapshot()
        with patch.object(self.editor.context_menu, "tk_popup") as popup:
            self.right_click(2)
            popup.assert_not_called()
            self.assertEqual(self.editor.tree.selection(), ("0",))
            self.assertEqual(self.editor.target.get(), "invalid")
            self.assertEqual(self.snapshot(), before)
            self.editor.target.set("3")
            self.editor.title.set("Corrected title")
            self.right_click(2)
            popup.assert_called_once()
        self.assertEqual(self.editor.tree.selection(), ("2",))
        self.assertEqual(self.editor.draft.entries[0].title, "Corrected title")
        self.assertEqual(self.editor.draft.entries[0].pdf_page, 3)
        self.assertFalse(self.editor.draft.entries[0].confirmed)
        self.assertFalse(self.errors)

    def test_context_confirmation_keeps_next_pending_and_unknown_page_safety(self):
        self.choose(0)
        self.editor._update_context_menu()
        self.editor.context_menu.invoke("确认所选并下一项")
        self.assertTrue(self.editor.draft.entries[0].confirmed)
        self.assertEqual(self.editor.tree.selection(), ("2",))
        self.editor.draft.entries[2].pdf_page = None
        self.editor._refresh(2)
        before = self.snapshot()
        self.editor._update_context_menu()
        self.assertEqual(self.editor.context_menu.entrycget("查看目标页", "state"), "disabled")
        self.editor.context_menu.invoke("确认所选并下一项")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.editor.draft.entries[2].confirmed)
        self.assertTrue(self.errors)

    def test_context_edit_title_keeps_existing_inline_editor_and_hidden_column_access(self):
        self.choose(0)
        before = self.snapshot()
        for mode in ("详细表格", "目录树"):
            self.editor.view_mode.set(mode)
            self.editor._view_changed()
            self.root.update()
            self.editor._update_context_menu()
            self.editor.context_menu.invoke("编辑标题")
            self.assertIsNotNone(self.editor._inline)
            self.assertEqual(self.editor._inline.get(), "Row 0")
            self.editor._close_inline()
            self.assertEqual(self.snapshot(), before)
        self.editor.tree.focus_force()
        self.root.update()
        with patch.object(self.editor.tree, "bbox", return_value=(-500, 30, 210, 20)):
            self.editor.context_menu.invoke("编辑标题")
        self.root.update()
        self.assertIs(self.editor.window.focus_get(), self.editor._title_entry)
        self.assertEqual(self.editor._title_entry.get(), "Row 0")
        self.assertIsNone(self.editor._inline)
        self.assertEqual(self.snapshot(), before)

    def test_context_shortcut_is_tree_local_and_busy_or_missing_draft_does_not_post(self):
        self.choose(0)
        with patch.object(self.editor.context_menu, "tk_popup") as popup:
            self.editor.tree.focus_force()
            self.root.update()
            self.editor.tree.event_generate("<Shift-F10>")
            self.root.update()
            popup.assert_called_once()
            popup.reset_mock()
            entry = next(widget for widget in self.editor._controls
                         if isinstance(widget, fixtures.toc_editor.ttk.Entry)
                         and str(widget.cget("textvariable")) == str(self.editor.search_text))
            entry.focus_force()
            self.root.update()
            entry.event_generate("<Shift-F10>")
            self.root.update()
            popup.assert_not_called()
            self.editor._set_busy(True)
            self.right_click(0)
            popup.assert_not_called()
            self.editor._set_busy(False)
            self.editor.draft = None
            self.right_click(0)
            popup.assert_not_called()

    def test_context_target_and_tree_expansion_reuse_existing_behavior_and_theme(self):
        self.load((1, 2, 3, 1))
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()
        self.editor.clear_selection()
        before = self.snapshot()
        self.editor._update_context_menu()
        self.editor.context_menu.invoke("折叠所选或全部目录")
        self.assertFalse(self.editor.tree.item("0", "open"))
        self.assertFalse(self.editor.tree.item("1", "open"))
        self.editor.context_menu.invoke("展开所选或全部目录")
        self.assertTrue(self.editor.tree.item("0", "open"))
        self.assertTrue(self.editor.tree.item("1", "open"))
        self.choose(2)
        self.editor.preview_page.set("6")
        self.editor._update_context_menu()
        with patch.object(self.editor, "show_page") as show:
            self.editor.context_menu.invoke("查看目标页")
        show.assert_called_once()
        self.assertEqual(self.editor.preview_page.get(), "3")
        self.assertEqual(self.snapshot(), before)
        for theme in ("light", "dark", "eye_care"):
            palette = apply_theme(self.root, theme)
            expected = menu_colors(self.editor.context_menu, palette)
            self.assertEqual(self.root.winfo_rgb(self.editor.context_menu.cget("background")),
                             self.root.winfo_rgb(expected["background"]))
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
