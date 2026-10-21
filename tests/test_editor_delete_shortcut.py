"""Scoped Delete, optional batch confirmation and compact-menu integration."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
import gc
from pathlib import Path
import tempfile
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

import pymupdf

import config_manager
import toc_editor
from toc_generation import Draft, DraftEntry
from ui_theme import apply_theme, menu_colors


class DeleteShortcutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-delete-shortcut-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "sample.pdf"
        with pymupdf.open() as document:
            for _ in range(6):
                document.new_page()
            document.save(self.pdf)
        self.pdf_bytes = self.pdf.read_bytes()
        self.root = tk.Tk()
        self.root.withdraw()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.errors = []
        self.error_patch = patch.object(toc_editor.messagebox, "showerror",
            side_effect=lambda title, message, errors=self.errors, **kw: errors.append(str(message)))
        self.error_patch.start()
        self.question_patch = patch.object(toc_editor.messagebox, "askyesno", return_value=True)
        self.question = self.question_patch.start()
        self.callback = Mock()
        self.editor = toc_editor.open_editor(self.root, self.executor, self.pdf,
            on_settings_changed=self.callback, draft_dir=self.folder / "drafts")
        self.editor.window.geometry("1000x720+20000+20000")
        self.editor.auto_save.set(False)
        self.load()

    def tearDown(self):
        root_reference = weakref.ref(self.root)
        self.editor.on_settings_changed = None
        self.editor.auto_save.set(False)
        if not self.editor.closed:
            self.editor.close()
        self.executor.shutdown(wait=True)
        self.root.update_idletasks()
        self.root.destroy()
        self.error_patch.stop()
        self.question_patch.stop()
        self.question.reset_mock()
        self.callback.reset_mock()
        self.assertEqual(self.pdf.read_bytes(), self.pdf_bytes)
        self.assertFalse(self.pdf.with_suffix(".toc.json").exists())
        self.temporary.cleanup()
        self.editor = self.root = self.callback = self.executor = None
        self.question = self.question_patch = self.error_patch = None
        gc.collect()
        self.assertIsNone(root_reference(), "Test mocks retained a destroyed Tk interpreter")

    def load(self, levels=(1, 1, 1, 1)):
        self.editor.draft = Draft(self.pdf, 6, [
            DraftEntry(level, f"Row {index}", index + 1, index + 1, "高", f"note {index}", bool(index % 2))
            for index, level in enumerate(levels)], [1], {"offset": 0}, "test", [])
        self.editor._load_mapping()
        self.editor._refresh()
        self.root.update()

    def choose(self, *indices):
        self.editor.tree.selection_set(*(str(index) for index in indices))
        self.editor.tree.focus(str(indices[0]))
        self.editor._selected()

    def snapshot(self):
        return deepcopy(asdict(self.editor.draft))

    def press_delete(self, widget=None):
        widget = widget or self.editor.tree
        self.root.update()
        widget.focus_force()
        self.root.update()
        widget.event_generate("<Delete>")
        self.root.update()

    def test_delete_key_removes_selected_row_and_undo_redo_restores_all_fields(self):
        self.choose(1)
        before = self.snapshot()
        self.press_delete()
        after = self.snapshot()
        self.assertEqual([row.title for row in self.editor.draft.entries], ["Row 0", "Row 2", "Row 3"])
        self.question.assert_not_called()
        self.assertEqual(self.editor.tree.selection(), ("1",))
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)
        self.editor.redo()
        self.assertEqual(self.snapshot(), after)

    def test_multi_delete_cancel_keeps_entries_selection_and_history(self):
        self.choose(1, 3)
        before, history = self.snapshot(), len(self.editor.history._states)
        self.question.return_value = False
        self.press_delete()
        self.question.assert_called_once()
        self.assertIn("2", self.question.call_args.args[1])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.editor.tree.selection(), ("1", "3"))
        self.assertEqual(len(self.editor.history._states), history)

    def test_multi_delete_menu_and_key_share_confirmation_and_undo(self):
        self.choose(0, 2)
        before = self.snapshot()
        self.editor.entry_menu.invoke("删除所选目录项")
        self.question.assert_called_once()
        self.assertEqual([row.title for row in self.editor.draft.entries], ["Row 1", "Row 3"])
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)

    def test_preference_disables_batch_question_and_persists_through_existing_config(self):
        self.assertTrue(self.editor.confirm_multi_delete.get())
        self.editor.draft_menu.invoke("删除多个目录项前询问")
        self.assertFalse(self.editor.confirm_multi_delete.get())
        updates = self.callback.call_args.args[0]
        self.assertIs(updates["editor_confirm_multi_delete"], False)
        settings = self.folder / "settings.json"
        config_manager.save_config(updates, settings)
        reopened = config_manager.load_config(settings)
        self.assertFalse(reopened["editor_confirm_multi_delete"])
        self.assertEqual(config_manager.read_config(settings)["schema"], 1)
        self.choose(1, 3)
        self.press_delete()
        self.question.assert_not_called()
        self.assertEqual([row.title for row in self.editor.draft.entries], ["Row 0", "Row 2"])

    def test_filtered_delete_uses_model_indices_and_leaves_hidden_rows(self):
        self.editor.draft.entries[1].title = "match one"
        self.editor.draft.entries[3].title = "match two"
        self.editor._refresh()
        self.editor.search_text.set("match")
        self.editor._filter_changed()
        self.choose(1, 3)
        self.press_delete()
        self.assertEqual([row.title for row in self.editor.draft.entries], ["Row 0", "Row 2"])
        self.assertEqual(self.editor.tree.get_children(), ())

    def test_tree_parent_delete_does_not_silently_delete_unselected_children(self):
        self.load((1, 2, 3, 1))
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()
        self.choose(0)
        before = self.snapshot()
        self.press_delete()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.errors), 1)
        self.question.assert_not_called()

    def test_selected_subtree_can_be_deleted_as_one_undoable_batch(self):
        self.load((1, 2, 3, 1))
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()
        self.choose(0, 1, 2)
        before = self.snapshot()
        self.press_delete()
        self.assertEqual([row.title for row in self.editor.draft.entries], ["Row 3"])
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)

    def test_busy_empty_selection_or_missing_draft_does_not_delete_or_ask(self):
        self.choose(1, 3)
        before = self.snapshot()
        self.editor._set_busy(True)
        self.press_delete()
        self.assertEqual(self.snapshot(), before)
        for control in self.editor._controls:
            if isinstance(control, toc_editor.ttk.Menubutton):
                self.assertIn("disabled", control.state())
        self.editor._set_busy(False)
        self.editor.tree.selection_remove(*self.editor.tree.selection())
        self.press_delete()
        self.assertEqual(self.snapshot(), before)
        self.editor.draft = None
        self.assertEqual(self.editor.delete_entry(), "break")
        self.question.assert_not_called()

    def test_invalid_edit_blocks_delete_and_retains_input(self):
        self.choose(1)
        before = self.snapshot()
        self.editor.target.set("invalid")
        self.assertEqual(self.editor.delete_entry(), "break")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.editor.target.get(), "invalid")
        self.assertEqual(self.editor.tree.selection(), ("1",))

    def test_delete_in_title_search_and_page_entry_only_removes_text(self):
        self.choose(1)
        for variable in (self.editor.title, self.editor.search_text, self.editor.preview_page):
            widget = next(control for control in self.editor._controls
                if isinstance(control, toc_editor.ttk.Entry) and str(control.cget("textvariable")) == str(variable))
            variable.set("123")
            widget.selection_clear()
            widget.icursor(1)
            self.press_delete(widget)
            self.assertEqual(variable.get(), "13")
            self.assertEqual(len(self.editor.draft.entries), 4)
            self.assertEqual(self.editor.tree.selection(), ("1",))
        self.question.assert_not_called()

    def test_inline_entry_delete_only_edits_cell(self):
        self.choose(1)
        self.root.update()
        x, y, width, height = self.editor.tree.bbox("1", "title")
        self.editor._inline_edit(SimpleNamespace(x=x + width // 2, y=y + height // 2))
        widget = self.editor._inline
        self.assertIsNotNone(widget)
        widget.selection_clear()
        widget.icursor(0)
        self.press_delete(widget)
        self.assertEqual(len(self.editor.draft.entries), 4)
        self.assertEqual(widget.get(), "ow 1")
        self.question.assert_not_called()

    def test_compact_menus_keep_draft_add_move_and_preview_actions(self):
        self.choose(1)
        self.editor.entry_menu.invoke("添加")
        self.assertEqual(self.editor.draft.entries[2].title, "新书签")
        self.editor.entry_menu.invoke("下移")
        self.assertEqual(self.editor.draft.entries[3].title, "新书签")
        self.editor.entry_menu.invoke("上移")
        self.assertEqual(self.editor.draft.entries[2].title, "新书签")
        self.editor.draft_menu.invoke("暂存草稿")
        self.assertTrue(self.editor.store.exists(self.pdf))
        for menu, names in ((self.editor.draft_menu, ("恢复草稿",)),
                            (self.editor.preview_location_menu, ("目录页", "原目录行", "清除此页设置")),
                            (self.editor.preview_fit_menu, ("适合宽度", "整页"))):
            for label in names:
                self.assertTrue(menu.entrycget(label, "command"), label)

    def test_existing_and_later_menus_follow_light_dark_theme_without_changing_model(self):
        before = self.snapshot()
        for theme in ("dark", "light"):
            palette = apply_theme(self.root, theme)
            for menu in (self.editor.draft_menu, self.editor.entry_menu, self.editor.preview_location_menu, self.editor.preview_fit_menu):
                expected = menu_colors(menu, palette)
                self.assertEqual(self.root.winfo_rgb(menu.cget("background")), self.root.winfo_rgb(expected["background"]))
                self.assertEqual(self.root.winfo_rgb(menu.cget("foreground")), self.root.winfo_rgb(expected["foreground"]))
            self.assertEqual(self.snapshot(), before)

    def test_plus_minus_and_keypad_expand_only_selected_nodes_without_mutating_draft(self):
        self.load((1, 2, 3, 1))
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()
        self.choose(0, 1)
        before, history = self.snapshot(), len(self.editor.history._states)
        self.editor.tree.focus_force()
        self.root.update()
        for key, expected in (("minus", False), ("plus", True), ("KP_Subtract", False), ("KP_Add", True)):
            with self.subTest(key=key):
                if key.startswith("KP_") and self.root.tk.call("tk", "windowingsystem") == "win32":
                    # The independent probe records keysym=??/keycode=0 for
                    # synthesized keypad events on Windows Tk. Exercise its
                    # actual registered Tcl callback, as the KP_Enter tests do.
                    binding = self.editor.tree.bind(f"<{key}>")
                    self.assertTrue(binding)
                    self.editor.tree.tk.call(binding.split("[", 1)[1].split(" ", 1)[0])
                else:
                    self.editor.tree.event_generate(f"<{key}>")
                self.root.update()
                self.assertEqual(bool(self.editor.tree.item("0", "open")), expected)
                self.assertEqual(bool(self.editor.tree.item("1", "open")), expected)
                self.assertTrue(self.editor.tree.item("3", "open"))
                self.assertEqual(self.editor.tree.selection(), ("0", "1"))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(len(self.editor.history._states), history)

    def test_expand_collapse_respects_busy_and_table_mode_and_menu_alternative(self):
        self.load((1, 2, 3, 1))
        self.choose(0)
        self.editor.set_selected_expanded(False)
        self.assertTrue(self.editor.tree.item("0", "open"))
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()
        self.editor._set_busy(True)
        self.editor.set_selected_expanded(False)
        self.assertTrue(self.editor.tree.item("0", "open"))
        self.editor._set_busy(False)
        self.editor.entry_menu.invoke("折叠所选目录项")
        self.assertFalse(self.editor.tree.item("0", "open"))
        self.editor.entry_menu.invoke("展开所选目录项")
        self.assertTrue(self.editor.tree.item("0", "open"))

    def test_plus_minus_in_entry_remain_text_input_without_changing_tree_state(self):
        self.load((1, 2, 3, 1))
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()
        self.choose(0)
        entry = next(control for control in self.editor._controls
            if isinstance(control, toc_editor.ttk.Entry) and str(control.cget("textvariable")) == str(self.editor.title))
        entry.focus_force()
        self.root.update()
        entry.selection_clear()
        entry.icursor("end")
        for key in ("plus", "minus"):
            entry.event_generate(f"<{key}>")
            self.root.update()
        self.assertEqual(entry.get(), "Row 0+-")
        self.assertTrue(self.editor.tree.item("0", "open"))


class DeleteSettingCompatibilityTests(unittest.TestCase):
    def test_legacy_missing_or_invalid_setting_defaults_to_question_without_schema_change(self):
        self.assertIs(config_manager.sanitize_settings({})["editor_confirm_multi_delete"], True)
        for value in ("false", 0, None, []):
            self.assertIs(config_manager.sanitize_settings({"editor_confirm_multi_delete": value})["editor_confirm_multi_delete"], True)
        self.assertIs(config_manager.sanitize_settings({"editor_confirm_multi_delete": False})["editor_confirm_multi_delete"], False)
        self.assertEqual(config_manager.CONFIG_SCHEMA, 1)


if __name__ == "__main__":
    unittest.main()
