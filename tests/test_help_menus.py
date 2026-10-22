"""Menus reuse existing operations; help and workspace navigation stay scoped."""

from tkinter import ttk
import unittest
from unittest.mock import patch

import test_main_shortcuts_preview as fixtures
import test_editor_delete_shortcut as editor_fixtures


class HelpMenuTests(unittest.TestCase):
    setUp = fixtures.MainShortcutsPreviewTests.setUp
    tearDown = fixtures.MainShortcutsPreviewTests.tearDown
    pump = fixtures.MainShortcutsPreviewTests.pump
    load = fixtures.MainShortcutsPreviewTests.load
    focus = fixtures.MainShortcutsPreviewTests.focus

    def open_editor(self):
        self.main._open_editor()
        self.pump(lambda: self.main.editor is not None and not self.main.editor.busy)
        return self.main.editor

    def test_f1_from_path_entry_opens_local_singleton_and_keeps_text_and_update_controller(self):
        entry = next(widget for widget in self.main.inputs if isinstance(widget, ttk.Entry))
        entry.insert(0, "尚未完成的 PDF 路径")
        self.focus(entry)
        entry.selection_range(1, 4)
        before = entry.get(), entry.index("sel.first"), entry.index("sel.last")
        entry.event_generate("<F1>")
        self.root.update()
        dialog = self.root._pdf_help_dialog
        self.assertTrue(dialog.window.winfo_exists())
        self.assertIsNone(self.main.updates)
        self.assertEqual((entry.get(), entry.index("sel.first"), entry.index("sel.last")), before)
        self.main.help_menu.invoke("操作说明与快捷键…")
        self.assertIs(self.root._pdf_help_dialog, dialog)
        dialog.close()
        self.assertIsNone(self.main.updates)
        with patch.object(self.main, "enable_updates") as updates:
            self.main.help_menu.invoke("版本与更新…")
            updates.assert_called_once()
            updates.return_value.show.assert_called_once()

    def test_help_is_shared_from_both_workspaces_and_editor_close_keeps_it(self):
        self.main._show_help()
        dialog = self.root._pdf_help_dialog
        editor = self.open_editor()
        self.focus(editor.search_entry)
        editor.search_entry.event_generate("<F1>")
        self.root.update()
        self.assertIs(self.root._pdf_help_dialog, dialog)
        editor.close()
        self.assertTrue(dialog.window.winfo_exists())
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))

    @staticmethod
    def menu_labels(menu):
        return [menu.entrycget(index, "label") for index in range(menu.index("end") + 1)
                if menu.type(index) != "separator"]

    def test_top_menus_have_only_approved_entries_and_show_active_page_actions(self):
        self.assertEqual(self.menu_labels(self.main.menu_bar), ["编辑", "视图", "帮助"])
        self.assertEqual(self.menu_labels(self.main.view_menu), ["外观", "专注模式", "恢复本页默认布局"])
        self.assertEqual(self.menu_labels(self.main.help_menu), ["操作说明与快捷键…", "版本与更新…"])
        self.assertFalse(hasattr(self.main, "file_menu"))
        self.assertFalse(hasattr(self.main, "review_menu"))
        self.main._update_edit_menu()
        self.assertEqual(self.menu_labels(self.main.edit_menu),
                         ["选中全部", "清除选中", "移除所选（保留文件）"])
        editor = self.open_editor()
        self.main._update_edit_menu()
        self.assertEqual(self.menu_labels(self.main.edit_menu),
                         ["选中全部", "清除选中", "删除所选目录项",
                          "撤销目录修改", "重做目录修改", "查找目录…"])
        self.assertEqual(self.main.edit_menu.entrycget("撤销目录修改", "state"), "disabled")
        self.assertEqual(self.main.edit_menu.entrycget("重做目录修改", "state"), "disabled")
        self.assertEqual(self.main.edit_menu.entrycget("查找目录…", "state"), "normal")
        self.main._select_workspace(self.main.main_page)
        self.main._update_edit_menu()
        self.assertEqual(self.menu_labels(self.main.edit_menu),
                         ["选中全部", "清除选中", "移除所选（保留文件）"])
        self.assertFalse(editor.closed)

    def test_context_menu_states_keep_existing_controls_and_busy_guards(self):
        ids = self.load()
        self.focus(self.main.file_tree)
        self.main._update_edit_menu()
        self.assertEqual(self.main.edit_menu.entrycget("选中全部", "state"), "normal")
        self.main.file_tree.focus(ids[0])
        editor = self.open_editor()
        self.focus(editor.tree)
        self.main._update_edit_menu()
        self.main._update_view_menu()
        self.assertEqual(self.main.edit_menu.entrycget("查找目录…", "state"), "normal")
        with patch.object(editor, "focus_search") as search:
            self.main.edit_menu.invoke("查找目录…")
            search.assert_called_once()
        self.focus(editor.tree)
        editor.tree.event_generate("<Control-l>")
        self.root.update()
        self.assertEqual(str(self.root.focus_get().cget("textvariable")), str(editor.preview_page))
        editor._set_busy(True)
        self.main._update_edit_menu()
        self.main._update_view_menu()
        self.assertTrue(all(str(widget.cget("state")) == "disabled" for widget in editor._controls))
        self.assertEqual(self.main.edit_menu.entrycget("选中全部", "state"), "disabled")
        self.assertEqual(self.main.edit_menu.entrycget("查找目录…", "state"), "disabled")
        self.main._switch_workspace()
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))
        with patch.object(editor, "focus_search") as search:
            self.main._editor_action("focus_search")
            search.assert_not_called()
        editor._set_busy(False)

    def test_workspace_shortcuts_switch_only_workspace_tabs_and_preserve_selected_checks(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[:2])
        self.main.file_tree.focus(ids[0])
        selection = self.main.file_tree.selection()
        checks = [item["checked"] for item in self.main.items.values()]
        self.focus(self.main.file_tree)
        self.main.file_tree.event_generate("<Control-Tab>")
        self.pump(lambda: self.main.editor is not None and not self.main.editor.busy)
        editor = self.main.editor
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))
        self.focus(editor.tree)
        editor.tree.event_generate("<Control-Shift-Tab>")
        self.root.update()
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.assertEqual(self.main.file_tree.selection(), selection)
        self.assertEqual([item["checked"] for item in self.main.items.values()], checks)
        self.assertFalse(self.root.bind_all("<Control-Tab>"))

    def test_workspace_shortcut_keeps_busy_or_invalid_editor_in_place(self):
        self.main._set_busy(True)
        self.main._switch_workspace()
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.assertIsNone(self.main.editor)
        self.main._set_busy(False)
        ids = self.load()
        self.main.file_tree.focus(ids[0])
        editor = self.open_editor()
        editor.target.set("待填写")
        editor._cancel_edit_timer()
        before = editor.draft.entries[0].pdf_page
        with patch("toc_editor.messagebox.showerror") as error:
            self.focus(editor.tree)
            editor.tree.event_generate("<Control-Tab>")
            self.root.update()
            error.assert_called_once()
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))
        self.assertEqual(editor.target.get(), "待填写")
        self.assertEqual(editor.draft.entries[0].pdf_page, before)
        editor.target.set(str(before))
        editor._cancel_edit_timer()
        editor._set_busy(True)
        self.main._switch_workspace()
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))
        editor._set_busy(False)

    def test_workspace_switch_from_search_entry_keeps_query(self):
        editor = self.open_editor()
        editor.search_text.set("未完成的查找文字")
        self.focus(editor.search_entry)
        editor.search_entry.event_generate("<Control-Tab>")
        self.root.update()
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.main._switch_workspace()
        self.root.update()
        self.assertEqual(editor.search_text.get(), "未完成的查找文字")

    def test_notebook_focus_shortcuts_keep_busy_and_invalid_edit_guards(self):
        self.main._set_busy(True)
        self.focus(self.main.workspace_tabs)
        self.main.workspace_tabs.event_generate("<Control-Tab>")
        self.root.update()
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.main_page))
        self.main._set_busy(False)
        ids = self.load()
        self.main.file_tree.focus(ids[0])
        editor = self.open_editor()
        editor.target.set("未完成")
        editor._cancel_edit_timer()
        original = editor.source_tabs.select()
        with patch("toc_editor.messagebox.showerror") as error:
            self.focus(editor.source_tabs)
            editor.source_tabs.event_generate("<Control-Tab>")
            self.root.update()
            error.assert_called_once()
        self.assertEqual(editor.source_tabs.select(), original)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))
        self.assertEqual(editor.target.get(), "未完成")
        editor.target.set("1")
        editor._cancel_edit_timer()

    def test_inner_notebook_shortcut_changes_workspace_only(self):
        before = self.main.view_tabs.select()
        self.focus(self.main.view_tabs)
        self.main.view_tabs.event_generate("<Control-Tab>")
        self.pump(lambda: self.main.editor is not None and not self.main.editor.busy)
        self.assertEqual(self.main.workspace_tabs.select(), str(self.main.editor_page))
        self.assertEqual(self.main.view_tabs.select(), before)

    def test_history_menus_and_local_review_controls_keep_original_operations(self):
        ids = self.load()
        self.main.file_tree.focus(ids[0])
        editor = self.open_editor()
        self.main._update_edit_menu()
        for label, method in (("撤销目录修改", "undo"), ("重做目录修改", "redo")):
            with self.subTest(label=label), patch.object(editor, method) as operation:
                self.main.edit_menu.invoke(label)
                operation.assert_called_once()
        editor.draft_menu.invoke("暂存草稿")
        self.assertIn("草稿已暂存", editor.draft_status.get())
        self.assertTrue(editor.store.exists(editor.draft.pdf_path))
        self.focus(editor.tree)
        editor.tree.event_generate("<Control-s>")
        self.root.update()
        self.assertIn("草稿已暂存", editor.draft_status.get())
        editor.tree.event_generate("<F2>")
        self.root.update()
        self.assertIsNotNone(editor._inline)
        self.assertEqual(editor._inline.get(), editor.draft.entries[0].title)
        editor._close_inline()
        editor.confirmed.set(False)
        editor.update_entry()
        self.focus(editor.tree)
        editor.tree.event_generate("<Return>")
        self.root.update()
        self.assertTrue(editor.draft.entries[0].confirmed)
        next_pending = next(control for control in editor._controls
                            if "text" in control.keys() and control.cget("text") == "下一待核对")
        editor.confirmed.set(False)
        editor.update_entry()
        editor.clear_selection()
        next_pending.invoke()
        self.root.update()
        self.assertEqual(editor.tree.selection(), ("0",))


class StandaloneHelpTests(unittest.TestCase):
    setUp = editor_fixtures.DeleteShortcutTests.setUp
    tearDown = editor_fixtures.DeleteShortcutTests.tearDown
    load = editor_fixtures.DeleteShortcutTests.load

    def test_standalone_f1_and_menu_share_help_without_changing_work(self):
        before = [(e.title, e.level, e.pdf_page, e.confirmed) for e in self.editor.draft.entries]
        self.editor.tree.focus_force()
        self.editor.tree.event_generate("<F1>")
        self.root.update()
        dialog = self.editor.window._pdf_help_dialog
        self.editor.help_menu.invoke("操作说明与快捷键…")
        self.assertIs(self.editor.window._pdf_help_dialog, dialog)
        self.assertEqual([(e.title, e.level, e.pdf_page, e.confirmed)
                          for e in self.editor.draft.entries], before)
        dialog.close()
        self.assertFalse(hasattr(self.editor.window, "_pdf_help_dialog"))


if __name__ == "__main__":
    unittest.main()
