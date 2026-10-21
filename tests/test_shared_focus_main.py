"""One focus preference and the main review affordances preserve input data."""

import json
import unittest
from unittest.mock import patch

import config_manager
import test_main_shortcuts_preview as fixtures
from gui_support import load_settings


class SharedFocusSettingsTests(unittest.TestCase):
    def test_shared_preference_has_priority_over_legacy_page_values(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                settings = config_manager.sanitize_settings({
                    "focus_mode": enabled, "main_focus_mode": not enabled,
                    "editor_focus_mode": not enabled})
                self.assertIs(settings["focus_mode"], enabled)
        self.assertEqual(config_manager.CONFIG_SCHEMA, 1)

    def test_legacy_migration_uses_valid_main_then_valid_editor(self):
        examples = [({}, False), ({"main_focus_mode": True}, True),
                    ({"editor_focus_mode": True}, True),
                    ({"main_focus_mode": False, "editor_focus_mode": True}, False),
                    ({"main_focus_mode": None, "editor_focus_mode": True}, True),
                    ({"focus_mode": "yes", "main_focus_mode": True}, True),
                    ({"focus_mode": 1, "main_focus_mode": None,
                      "editor_focus_mode": "yes"}, False)]
        for source, expected in examples:
            with self.subTest(source=source):
                self.assertIs(config_manager.sanitize_settings(source)["focus_mode"], expected)


class SharedFocusMainTests(unittest.TestCase):
    setUp = fixtures.MainShortcutsPreviewTests.setUp
    tearDown = fixtures.MainShortcutsPreviewTests.tearDown
    pump = fixtures.MainShortcutsPreviewTests.pump
    load = fixtures.MainShortcutsPreviewTests.load
    focus = fixtures.MainShortcutsPreviewTests.focus
    render = fixtures.MainShortcutsPreviewTests.render

    def open_editor(self):
        self.main._open_editor()
        self.pump(lambda: self.main.editor is not None and not self.main.editor.busy)
        return self.main.editor

    def test_main_and_recreated_editor_keep_one_state_and_save_legacy_keys(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[0])
        self.main.file_tree.focus(ids[0])
        self.main._update_view_menu()
        self.main.view_menu.invoke("专注模式")
        editor = self.open_editor()
        self.assertIs(editor.focus_mode, self.main.focus_mode)
        self.assertTrue(editor.focus_mode.get())
        self.assertFalse(bool(editor.source_tabs.winfo_manager()))
        editor.close()
        self.assertTrue(editor.closed)
        self.main.focus_mode.set(False)
        self.main._save_settings()
        saved = load_settings(self.settings)
        for name in ("focus_mode", "main_focus_mode", "editor_focus_mode"):
            self.assertIs(saved[name], False)
        replacement = self.open_editor()
        self.assertIsNot(replacement, editor)
        self.assertIs(replacement.focus_mode, self.main.focus_mode)
        self.assertFalse(replacement.focus_mode.get())
        self.main._update_view_menu()
        self.main.view_menu.invoke("专注模式")
        self.assertTrue(replacement.focus_mode.get())
        self.assertFalse(bool(self.main.source_tabs.winfo_manager()))
        self.assertFalse(bool(replacement.source_tabs.winfo_manager()))

    def test_write_settings_exits_shared_focus_without_changing_existing_options(self):
        self.load()
        editor = self.open_editor()
        before = (self.main.existing.get(), self.main.backup.get(), self.main.backup_dir.get(),
                  self.main.clear_cache.get(), self.main.delete_toc.get())
        self.main.focus_mode.set(True)
        self.main.workspace_tabs.select(self.main.main_page)
        self.root.update()
        self.main.write_options_button.invoke()
        self.root.update()
        self.assertFalse(self.main.focus_mode.get())
        self.assertFalse(editor.focus_mode.get())
        self.assertTrue(self.main.write_options.winfo_ismapped())
        self.assertEqual((self.main.existing.get(), self.main.backup.get(), self.main.backup_dir.get(),
                          self.main.clear_cache.get(), self.main.delete_toc.get()), before)

    def test_find_and_page_navigation_work_from_owner_focus_only_on_active_editor(self):
        self.load()
        editor = self.open_editor()
        for sequence, entry in (('<Control-f>', editor.search_entry),
                                ('<Control-l>', editor.preview_page_entry)):
            self.root.focus_force()
            self.root.update()
            self.root.event_generate(sequence)
            self.root.update()
            self.assertIs(self.root.focus_get(), entry)
        self.main.workspace_tabs.select(self.main.main_page)
        self.root.update()
        self.focus(self.main.file_tree)
        original_focus = self.root.focus_get()
        for sequence in ('<Control-f>', '<Control-l>'):
            self.root.event_generate(sequence)
            self.root.update()
            self.assertIs(self.root.focus_get(), original_focus)

    def test_selection_and_write_counts_are_distinct_and_primary_action_tracks_readiness(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[:2])
        self.main._set_all_checked(False)
        self.main._toggle_item(ids[2])
        self.root.update()
        self.assertEqual(self.main.selection_status.get(), "选中 2 本 · 勾选写入 1 本")
        self.assertEqual(self.main.write_button.cget("style"), "Accent.TButton")
        self.assertEqual(self.main.preview_button.cget("style"), "Secondary.TButton")
        self.main._set_all_checked(False)
        self.assertEqual(self.main.selection_status.get(), "选中 2 本 · 勾选写入 0 本")
        self.assertEqual(self.main.preview_button.cget("style"), "Accent.TButton")
        self.assertEqual(str(self.main.write_button.cget("state")), "disabled")

    def test_empty_hints_full_paths_and_single_zoom_control_remain_read_only(self):
        self.root.update()
        self.assertTrue(self.main.empty_files.winfo_ismapped())
        ids = self.load()
        self.main.file_tree.selection_set(ids[2])
        self.main.file_tree.focus(ids[2])
        self.main._selected_file()
        self.root.update()
        self.assertFalse(self.main.empty_files.winfo_ismapped())
        self.assertFalse(self.main.empty_bookmarks.winfo_ismapped())
        self.assertTrue(self.main.empty_page.winfo_ismapped())
        self.assertEqual(self.main.current_book.get(), self.pdfs[2].name)
        self.assertIn(str(self.pdfs[2]), self.main._current_file_tip.text)
        with patch.object(self.root, "clipboard_clear") as clear, \
                patch.object(self.root, "clipboard_append") as append:
            try:
                self.main._copy_current_path()
                clear.assert_called_once_with()
                append.assert_called_once_with(str(self.pdfs[2]))
            finally:
                clear.reset_mock()
                append.reset_mock()
        with patch("bookmarks_gui.os.startfile") as startfile:
            try:
                self.main._open_current_folder()
                startfile.assert_called_once_with(self.pdfs[2].parent)
            finally:
                startfile.reset_mock()
        self.main.bookmark_tree.selection_set(self.main.bookmark_tree.get_children()[0])
        self.pump(lambda: self.main._render_photo is not None)
        self.assertFalse(self.main.empty_page.winfo_ismapped())
        self.main._zoom_preview(1.2)
        self.pump(lambda: self.main._render_after is None and self.main._render_future.done())
        self.assertEqual(self.main.preview_zoom_button.cget("textvariable"), str(self.main.preview_zoom))
        self.assertEqual(self.main.preview_zoom.get(), "120%")
        self.main.preview_zoom_button.invoke()
        self.pump(lambda: self.main._render_after is None and self.main._render_future.done())
        self.assertEqual(self.main.preview_zoom.get(), "100%")

    def test_main_layout_reset_preserves_input_and_current_review(self):
        self.render()
        main = self.main
        before = (main.file_tree.selection(), list(main.plans), dict(main.bookmark_rows),
                  main._render_photo, main._render_token, main._preview_target,
                  main.existing.get(), main.backup.get(), self.root.geometry())
        main._layout_memories["main_pane_ratio"]._ratio = 50
        # Reset the actual memories using the same menu command as the user.
        main.workspace_tabs.select(main.main_page)
        main.view_menu.invoke("恢复本页默认布局")
        self.root.update()
        self.assertEqual((main.file_tree.selection(), list(main.plans), dict(main.bookmark_rows),
                          main._render_photo, main._render_token, main._preview_target,
                          main.existing.get(), main.backup.get(), self.root.geometry()), before)
        saved = json.loads(self.settings.read_text(encoding="utf-8"))
        for name in ("main_pane_ratio", "main_preview_ratio"):
            self.assertEqual(saved[name], 0)
        for name in ("file_column_widths", "bookmark_column_widths"):
            self.assertEqual(saved[name], {})


if __name__ == "__main__":
    unittest.main()
