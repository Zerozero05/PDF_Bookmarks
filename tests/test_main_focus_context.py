"""Focus layout and context actions retain the existing main review workflow."""

import unittest
from unittest.mock import patch

import test_main_shortcuts_preview as fixtures
from gui_support import load_settings
from ui_theme import apply_theme


class MainFocusContextTests(unittest.TestCase):
    setUp = fixtures.MainShortcutsPreviewTests.setUp
    tearDown = fixtures.MainShortcutsPreviewTests.tearDown
    pump = fixtures.MainShortcutsPreviewTests.pump
    load = fixtures.MainShortcutsPreviewTests.load
    focus = fixtures.MainShortcutsPreviewTests.focus
    render = fixtures.MainShortcutsPreviewTests.render

    def toggle_focus(self):
        self.main._update_view_menu()
        self.main.view_menu.invoke("专注模式")

    def right_click(self, iid=None):
        self.root.update()
        box = self.main.file_tree.bbox(iid) if iid else ()
        y = box[1] + box[3] // 2 if box else self.main.file_tree.winfo_height() - 8
        self.main.file_tree.event_generate('<Button-3>', x=70, y=y)
        self.root.update()

    def test_focus_roundtrip_preserves_loaded_preview_selection_and_window(self):
        self.render()
        self.root.update()
        main = self.main
        selection = main.file_tree.selection()
        plans = list(main.plans)
        checks = [item['checked'] for item in main.items.values()]
        photo, token = main._render_photo, main._render_token
        geometry, minimum = self.root.geometry(), self.root.minsize()
        original_height = main.main_body.winfo_height()
        for expected in (True, False, True, False):
            self.toggle_focus()
            self.root.update()
            self.assertEqual(main.focus_mode.get(), expected)
            self.assertEqual(bool(main.source_tabs.winfo_manager()), not expected)
            self.assertFalse(hasattr(main, 'focus_button'))
            self.assertEqual(str(self.root.cget('menu')), str(main.menu_bar))
            self.assertEqual(main.view_menu.entrycget('专注模式', 'state'), 'normal')
            self.assertTrue(main.preview_button.winfo_ismapped())
            self.assertTrue(main.write_button.winfo_ismapped())
            self.assertTrue(main.write_options_button.winfo_ismapped())
            self.assertEqual(main.file_tree.selection(), selection)
            self.assertEqual(main.plans, plans)
            self.assertEqual([item['checked'] for item in main.items.values()], checks)
            self.assertIs(main._render_photo, photo)
            self.assertEqual(main._render_token, token)
            self.assertEqual((self.root.geometry(), self.root.minsize()), (geometry, minimum))
            if expected:
                self.assertGreater(main.main_body.winfo_height(), original_height)

    def test_focus_keeps_values_and_restores_expanded_settings_even_when_busy(self):
        main = self.main
        main.pdf.set('尚未输完的 PDF 路径')
        main.backup_dir.set('尚未输完的备份路径')
        main.existing.set('替换已有书签')
        main._toggle_write_options()
        self.toggle_focus()
        self.root.update()
        self.assertFalse(main.write_options.winfo_ismapped())
        self.assertTrue(main._write_options_open)
        main._set_busy(True)
        self.toggle_focus()
        self.root.update()
        self.assertFalse(main.focus_mode.get())
        self.assertTrue(main.write_options.winfo_ismapped())
        self.assertTrue(main.policy.instate(('disabled',)))
        self.assertEqual(main.pdf.get(), '尚未输完的 PDF 路径')
        self.assertEqual(main.backup_dir.get(), '尚未输完的备份路径')
        self.assertEqual(main.existing.get(), '替换已有书签')
        main._set_busy(False)
        self.toggle_focus()
        main.write_options_button.invoke()
        self.root.update()
        self.assertFalse(main.focus_mode.get())
        self.assertTrue(main.write_options.winfo_ismapped())

    def test_view_menu_shares_focus_between_pages_and_preferences_are_saved(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[0])
        self.main.file_tree.focus(ids[0])
        self.toggle_focus()
        self.main._update_view_menu()
        self.assertTrue(self.main._view_focus_mode.get())
        self.main._open_editor()
        self.pump(lambda: self.main.editor is not None and not self.main.editor.busy)
        self.main._update_view_menu()
        self.assertTrue(self.main._view_focus_mode.get())
        self.assertIs(self.main.editor.focus_mode, self.main.focus_mode)
        self.assertFalse(hasattr(self.main.editor, 'focus_button'))
        self.assertFalse(hasattr(self.main.editor, 'menu_bar'))
        self.toggle_focus()
        self.assertFalse(self.main.editor.focus_mode.get())
        self.assertFalse(self.main.focus_mode.get())
        self.toggle_focus()
        self.assertTrue(self.main.editor.focus_mode.get())
        self.assertTrue(self.main.focus_mode.get())
        self.main.workspace_tabs.select(self.main.main_page)
        self.root.update()
        self.main._update_view_menu()
        self.assertTrue(self.main._view_focus_mode.get())
        self.main.workspace_tabs.select(self.main.editor_page)
        self.root.update()
        self.toggle_focus()
        self.main._save_settings()
        saved = load_settings(self.settings)
        self.assertFalse(saved['focus_mode'])
        self.assertFalse(saved['main_focus_mode'])
        self.assertFalse(saved['editor_focus_mode'])
        self.assertEqual(saved['editor_pane_ratio'], 0)
        self.assertEqual(saved['editor_column_widths'], {})

    def test_context_keeps_multi_selection_and_checks_only_requested_rows(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[:2])
        checks = [item['checked'] for item in self.main.items.values()]
        with patch.object(self.main.file_context_menu, 'tk_popup') as popup:
            self.right_click(ids[1])
            popup.assert_called_once()
        self.assertEqual(self.main.file_tree.selection(), ids[:2])
        self.assertEqual(self.main.file_tree.focus(), ids[1])
        self.assertEqual([item['checked'] for item in self.main.items.values()], checks)
        self.main.file_context_menu.invoke('取消所选勾选')
        self.assertEqual([item['checked'] for item in self.main.items.values()], [False, False, True])
        self.main.file_context_menu.invoke('勾选所选项目')
        self.assertEqual([item['checked'] for item in self.main.items.values()], [True, True, True])

    def test_context_selects_new_row_but_blank_space_cannot_remove_old_selection(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[:2])
        with patch.object(self.main.file_context_menu, 'tk_popup'):
            self.right_click(ids[2])
            self.assertEqual(self.main.file_tree.selection(), (ids[2],))
            self.right_click()
        self.assertEqual(self.main.file_tree.selection(), (ids[2],))
        self.assertEqual(str(self.main.file_context_menu.entrycget('移除所选（保留文件）', 'state')), 'disabled')
        self.assertEqual(str(self.main.file_context_menu.entrycget('选中全部', 'state')), 'normal')

    def test_context_remove_reuses_the_original_session_only_operation(self):
        ids = self.load(batch=True)
        self.main.file_tree.selection_set(ids[:2])
        with patch.object(self.main.file_context_menu, 'tk_popup'):
            self.right_click(ids[0])
        self.main.file_context_menu.invoke('移除所选（保留文件）')
        self.assertEqual(self.main.file_tree.get_children(), (ids[2],))
        self.assertIn('原 PDF 和 JSON 文件未删除', self.main.status.get())
        self.main._preview()
        self.pump(lambda: not self.main.busy)
        self.assertEqual(len(self.main.items), 1)

    def test_context_keyboard_is_local_and_busy_menu_actions_cannot_bypass_lock(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[:2])
        self.focus(self.main.file_tree)
        with patch.object(self.main.file_context_menu, 'tk_popup') as popup:
            self.main.file_tree.event_generate('<Shift-F10>')
            self.root.update()
            popup.assert_called_once()
            self.main._set_busy(True)
            popup.reset_mock()
            self.right_click(ids[1])
            popup.assert_not_called()
        self.main._set_selected_checked(False)
        self.main._remove_selected_files()
        self.assertEqual(len(self.main.items), 3)
        self.assertTrue(all(item['checked'] for item in self.main.items.values()))
        self.assertFalse(self.root.bind('<Shift-F10>'))
        self.main._set_busy(False)

    def test_minimum_three_theme_focus_layout_keeps_primary_controls_visible(self):
        self.root.geometry('1000x760+10000+10000')
        self.pump(lambda: self.main.workspace_tabs.winfo_height() == self.root.winfo_height())
        for theme in ('light', 'dark', 'eye_care'):
            apply_theme(self.root, theme)
            for focused in (False, True):
                self.main.focus_mode.set(focused)
                self.main._apply_focus_mode()
                self.root.update()
                self.assertEqual(self.main.view_menu.entrycget('专注模式', 'state'), 'normal')
                for widget in (self.main.preview_button, self.main.write_button,
                               self.main.file_tree, self.main.image_canvas):
                    self.assertTrue(widget.winfo_ismapped())
                    self.assertGreater(widget.winfo_width(), 10)
                    self.assertGreater(widget.winfo_height(), 10)
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         self.root.winfo_rooty() + self.root.winfo_height())
