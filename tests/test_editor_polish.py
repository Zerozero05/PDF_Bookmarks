"""Shared focus, compact tool groups and scoped navigation without data changes."""

import tkinter as tk
import unittest
from unittest.mock import patch

import test_editor_delete_shortcut as fixtures


class EditorPolishTests(unittest.TestCase):
    setUp = fixtures.DeleteShortcutTests.setUp
    tearDown = fixtures.DeleteShortcutTests.tearDown
    load = fixtures.DeleteShortcutTests.load
    choose = fixtures.DeleteShortcutTests.choose
    snapshot = fixtures.DeleteShortcutTests.snapshot

    def replace_editor(self, **kwargs):
        self.editor.on_settings_changed = None
        self.editor.close()
        self.editor = fixtures.toc_editor.open_editor(self.root, self.executor, self.pdf,
            on_settings_changed=self.callback, draft_dir=self.folder / "drafts", **kwargs)
        self.editor.window.geometry("1000x720+20000+20000")
        self.editor.auto_save.set(False)
        self.load()
        self.callback.reset_mock()

    def press(self, widget, key):
        widget.focus_force()
        self.root.update()
        widget.event_generate(key)
        self.root.update()

    def test_shared_focus_changes_display_only_and_releases_its_trace_on_close(self):
        shared = tk.BooleanVar(master=self.root, value=False)
        self.replace_editor(focus_var=shared)
        self.assertIs(self.editor.focus_mode, shared)
        self.choose(1, 2)
        self.editor.target.set("unfinished")
        self.editor._cancel_edit_timer()
        before, history = self.snapshot(), len(self.editor.history._states)
        for expected in (True, False):
            shared.set(expected)
            self.root.update_idletasks()
            self.assertEqual(bool(self.editor._focus_source.winfo_manager()), not expected)
            self.assertEqual(self.editor.target.get(), "unfinished")
            self.assertEqual(self.editor.tree.selection(), ("1", "2"))
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(len(self.editor.history._states), history)
        self.callback.assert_not_called()
        self.assertTrue(shared.trace_info())
        self.editor.on_settings_changed = None
        self.editor.close()
        self.assertFalse(shared.trace_info())
        shared.set(True)
        self.root.update()

    def test_canonical_focus_preference_overrides_legacy_editor_setting(self):
        self.replace_editor(editor_settings={"focus_mode": True, "editor_focus_mode": False})
        self.assertTrue(self.editor.focus_mode.get())
        self.assertFalse(self.editor._focus_source.winfo_manager())
        self.editor.view_menu.invoke("专注模式")
        updates = self.callback.call_args.args[0]
        self.assertIs(updates["focus_mode"], False)
        self.assertIs(updates["editor_focus_mode"], False)

    def test_find_and_page_shortcuts_select_text_and_preserve_directory(self):
        before = self.snapshot()
        self.editor.search_text.set("Row")
        self.press(self.editor.tree, "<Control-f>")
        self.assertIs(self.editor.window.focus_get(), self.editor.search_entry)
        self.assertTrue(self.editor.search_entry.selection_present())
        self.press(self.editor.search_entry, "<Control-l>")
        self.assertIs(self.editor.window.focus_get(), self.editor.preview_page_entry)
        self.assertTrue(self.editor.preview_page_entry.selection_present())
        self.assertEqual(self.snapshot(), before)
        self.editor._set_busy(True)
        with patch.object(self.editor.search_entry, "focus_set") as focus:
            self.editor.focus_search()
            focus.assert_not_called()
        self.editor._set_busy(False)

    def test_navigation_shortcut_blocks_invalid_edit_without_overwriting_fields(self):
        self.choose(0)
        self.editor.target.set("unfinished")
        self.editor._cancel_edit_timer()
        before = self.snapshot()
        with patch.object(self.editor.preview_page_entry, "focus_set") as focus:
            self.editor.focus_page()
            focus.assert_not_called()
        self.assertEqual(self.editor.target.get(), "unfinished")
        self.assertEqual(self.snapshot(), before)
        self.assertIn("尚未应用", self.editor.entry_note.get())

    def test_f2_is_tree_local_and_uses_existing_title_editor(self):
        self.choose(0)
        before = self.snapshot()
        self.press(self.editor.tree, "<F2>")
        self.assertIsNotNone(self.editor._inline)
        self.assertEqual(self.editor._inline.get(), "Row 0")
        self.editor._close_inline()
        self.press(self.editor.search_entry, "<F2>")
        self.assertIsNone(self.editor._inline)
        self.editor.target.set("invalid")
        self.editor._cancel_edit_timer()
        self.press(self.editor.tree, "<F2>")
        self.assertIsNone(self.editor._inline)
        self.assertEqual(self.snapshot(), before)

    def test_layout_reset_changes_no_model_selection_numbering_or_focus(self):
        self.choose(0, 2)
        self.editor.focus_mode.set(True)
        before = self.snapshot()
        with patch.object(self.editor._pane_memory, "reset") as pane, \
                patch.object(self.editor._column_memory, "reset") as columns:
            self.editor.view_menu.invoke("恢复本页默认布局")
        pane.assert_called_once_with()
        columns.assert_called_once_with()
        self.assertTrue(self.editor.focus_mode.get())
        self.assertEqual(self.editor.tree.selection(), ("0", "2"))
        self.assertEqual(self.snapshot(), before)

    def test_book_name_and_file_actions_keep_complete_path_and_do_not_write_pdf(self):
        before = self.snapshot()
        self.assertEqual(self.editor.book_name.get(), self.pdf.name)
        with patch.object(self.editor.window, "clipboard_clear") as clear, \
                patch.object(self.editor.window, "clipboard_append") as append:
            self.editor.path_menu.invoke("复制完整 PDF 路径")
        clear.assert_called_once_with()
        append.assert_called_once_with(str(self.pdf))
        with patch.object(fixtures.toc_editor.os, "startfile") as open_folder:
            self.editor.path_menu.invoke("打开所在文件夹")
        open_folder.assert_called_once_with(str(self.pdf.parent))
        self.assertEqual(self.editor.pdf.get(), str(self.pdf))
        self.assertEqual(self.snapshot(), before)
        self.editor._set_busy(True)
        self.editor._update_path_menu()
        self.assertEqual(self.editor.path_menu.entrycget("打开所在文件夹", "state"), "disabled")
        self.editor._set_busy(False)

    def test_empty_directory_hint_tracks_filter_and_selection_count(self):
        self.assertFalse(self.editor.empty_directory.winfo_manager())
        self.choose(0, 2)
        self.assertIn("已选 2", self.editor.summary.get())
        self.assertIn("已确认 2/4", self.editor.summary.get())
        self.editor.clear_selection()
        self.assertIn("已选 0", self.editor.summary.get())
        before = self.snapshot()
        self.editor.search_text.set("not-present")
        self.editor._filter_changed()
        self.assertEqual(self.editor.empty_directory.winfo_manager(), "place")
        self.assertIn("没有匹配", self.editor.empty_directory.cget("text"))
        self.editor.search_text.set("")
        self.editor._filter_changed()
        self.assertFalse(self.editor.empty_directory.winfo_manager())
        self.assertEqual(self.snapshot(), before)

    def test_compact_preview_keeps_region_tools_and_one_live_zoom_indicator(self):
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        zoom_widgets = [widget for widget in descendants(self.editor.window)
                        if "textvariable" in widget.keys()
                        and str(widget.cget("textvariable")) == str(self.editor.preview_zoom)]
        self.assertEqual(len(zoom_widgets), 1)
        self.assertIsInstance(zoom_widgets[0], fixtures.toc_editor.ttk.Button)
        self.editor.preview_zoom.set("150%")
        self.root.update_idletasks()
        self.assertEqual(zoom_widgets[0].cget("text"), "150%")
        self.editor.region_menu.invoke("浏览")
        self.assertEqual(self.editor.region_tool.get(), "浏览")
        self.editor.region_menu.invoke("框选目录区域")
        self.assertEqual(self.editor.region_tool.get(), "框选目录区域")
        self.assertIn("拖出识别区域", self.editor.preview_status.get())
        self.assertEqual(self.editor.preview_location_menu.entrycget("清除此页设置", "state"), "normal")


if __name__ == "__main__":
    unittest.main()
