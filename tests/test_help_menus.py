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
            self.main.help_menu.invoke("帮助 / 更新")
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

    def test_context_menu_states_keep_existing_entrypoints_and_enable_only_active_editor_commands(self):
        self.main._update_file_menu()
        self.main._update_edit_menu()
        self.main._update_view_menu()
        for label in ("选择 PDF…", "选择目录 JSON…", "选择文件夹…", "添加多个 PDF / JSON…", "生成 / 编辑目录…", "退出"):
            self.assertEqual(self.main.file_menu.entrycget(label, "state"), "normal")
        for menu, label in ((self.main.file_menu, "暂存校对草稿"), (self.main.edit_menu, "查找目录…"),
                            (self.main.view_menu, "跳到 PDF 页…")):
            self.assertEqual(menu.entrycget(label, "state"), "disabled")
        editor = self.open_editor()
        self.main._update_edit_menu()
        self.main._update_view_menu()
        self.assertEqual(self.main.edit_menu.entrycget("查找目录…", "state"), "normal")
        self.assertEqual(self.main.view_menu.entrycget("跳到 PDF 页…", "state"), "normal")
        with patch.object(editor, "focus_search") as search, patch.object(editor, "focus_page") as page:
            self.main.edit_menu.invoke("查找目录…")
            self.main.view_menu.invoke("跳到 PDF 页…")
            search.assert_called_once()
            page.assert_called_once()
        editor._set_busy(True)
        self.main._update_file_menu()
        self.main._update_edit_menu()
        self.main._update_view_menu()
        self.assertEqual(self.main.file_menu.entrycget("选择 PDF…", "state"), "disabled")
        self.assertEqual(self.main.edit_menu.entrycget("查找目录…", "state"), "disabled")
        self.assertEqual(self.main.view_menu.entrycget("切换工作页", "state"), "disabled")
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

    def test_menu_confirmation_title_history_and_draft_commands_reuse_editor_methods(self):
        ids = self.load()
        self.main.file_tree.focus(ids[0])
        editor = self.open_editor()
        self.main._update_file_menu()
        self.main._update_edit_menu()
        for label, method, menu in (("暂存校对草稿", "save_draft", self.main.file_menu),
                                    ("撤销目录修改", "undo", self.main.edit_menu),
                                    ("重做目录修改", "redo", self.main.edit_menu),
                                    ("编辑所选标题…", "_edit_title_shortcut", self.main.review_menu),
                                    ("确认所选并下一项", "confirm_selected", self.main.review_menu),
                                    ("下一待核对", "next_pending", self.main.review_menu)):
            with self.subTest(label=label), patch.object(editor, method) as operation:
                menu.invoke(label)
                operation.assert_called_once()


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
