"""Real editor events keep menu, focus guards, history and saved keys aligned."""

from copy import deepcopy
import unittest
from unittest.mock import patch

import test_editor_delete_shortcut as editor_fixtures
import test_main_shortcuts_preview as main_fixtures
from gui_support import load_settings
from config_manager import read_config, save_config


class EditorCommandShortcutTests(unittest.TestCase):
    setUp = editor_fixtures.DeleteShortcutTests.setUp
    tearDown = editor_fixtures.DeleteShortcutTests.tearDown
    load = editor_fixtures.DeleteShortcutTests.load
    choose = editor_fixtures.DeleteShortcutTests.choose
    snapshot = editor_fixtures.DeleteShortcutTests.snapshot

    def key(self, sequence, widget=None):
        widget = widget or self.editor.tree
        widget.focus_force()
        self.root.update()
        widget.event_generate(sequence)
        self.root.update()

    def test_ctrl_n_adds_after_selection_with_unknown_target_and_can_undo(self):
        self.choose(0)
        before = self.snapshot()
        self.key('<Control-n>')
        added = self.editor.draft.entries[1]
        self.assertEqual((added.title, added.level, added.pdf_page, added.confirmed),
                         ('新书签', 1, None, False))
        self.assertEqual(self.editor.tree.selection(), ('1',))
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)

    def test_alt_up_down_reuse_original_single_item_move_and_keep_confirmation(self):
        self.choose(1)
        before = deepcopy(self.editor.draft.entries)
        self.key('<Alt-Up>')
        self.assertEqual(self.editor.draft.entries, [before[1], before[0], *before[2:]])
        self.assertEqual(self.editor.tree.selection(), ('0',))
        self.key('<Alt-Down>')
        self.assertEqual(self.editor.draft.entries, before)
        self.assertEqual(self.editor.tree.selection(), ('1',))

    def test_new_commands_do_not_run_from_text_fields_busy_or_other_page_work(self):
        self.choose(1)
        before = self.snapshot()
        for sequence in ('<Control-n>', '<Alt-Up>', '<Alt-Down>'):
            self.key(sequence, self.editor._title_entry)
        self.assertEqual(self.snapshot(), before)
        self.editor._set_busy(True)
        for sequence in ('<Control-n>', '<Alt-Up>', '<Alt-Down>'):
            self.key(sequence)
        self.assertEqual(self.snapshot(), before)
        self.editor._set_busy(False)
        self.editor.task_guard = lambda: True
        self.key('<Control-n>')
        self.key('<Alt-Up>')
        self.assertEqual(self.snapshot(), before)

    def test_invalid_pending_page_is_preserved_and_move_cannot_break_hierarchy(self):
        self.choose(1)
        before = deepcopy(self.editor.draft.entries)
        self.editor.target.set('invalid')
        self.editor._cancel_edit_timer()
        self.key('<Control-n>')
        self.key('<Alt-Up>')
        self.assertEqual(self.editor.draft.entries, before)
        self.assertEqual(self.editor.target.get(), 'invalid')
        self.assertTrue(self.errors)
        self.errors.clear()
        self.editor.target.set('2')
        self.editor._cancel_edit_timer()
        self.load((1, 2, 1, 1))
        self.choose(1)
        before = deepcopy(self.editor.draft.entries)
        self.key('<Alt-Up>')
        self.assertEqual(self.editor.draft.entries, before)
        self.assertTrue(self.errors)

    def test_custom_key_replaces_old_binding_updates_menu_and_reset_restores(self):
        self.choose(0)
        profile = self.editor.shortcut_profile
        profile.set_key('add', 'Ctrl+M')
        self.assertEqual(self.editor.entry_menu.entrycget('添加', 'accelerator'), 'Ctrl+M')
        self.assertEqual(self.editor.editor_settings['editor_shortcuts'], {'add': 'Ctrl+M'})
        count = len(self.editor.draft.entries)
        self.key('<Control-n>')
        self.assertEqual(len(self.editor.draft.entries), count)
        self.key('<Control-m>')
        self.assertEqual(len(self.editor.draft.entries), count + 1)
        profile.reset('add')
        self.assertEqual(self.editor.entry_menu.entrycget('添加', 'accelerator'), 'Ctrl+N')
        self.key('<Control-m>')
        self.assertEqual(len(self.editor.draft.entries), count + 1)
        self.key('<Control-n>')
        self.assertEqual(len(self.editor.draft.entries), count + 2)

    def test_conflict_and_failed_save_leave_menu_bindings_and_work_unchanged(self):
        self.choose(0)
        profile = self.editor.shortcut_profile
        before = self.snapshot()
        with self.assertRaises(ValueError):
            profile.set_key('add', 'Ctrl+F')
        self.callback.side_effect = OSError('blocked setting write')
        with self.assertRaises(OSError):
            profile.set_key('add', 'Ctrl+M')
        self.assertEqual(profile.overrides, {})
        self.assertEqual(self.editor.entry_menu.entrycget('添加', 'accelerator'), 'Ctrl+N')
        self.assertEqual(self.snapshot(), before)
        self.callback.side_effect = None
        self.key('<Control-n>')
        self.assertEqual(len(self.editor.draft.entries), len(before['entries']) + 1)

    def test_rebinding_root_command_keeps_menu_and_entry_editing_separate(self):
        self.editor.shortcut_profile.set_key('find', 'Ctrl+G')
        self.key('<Control-g>')
        self.assertIs(self.editor.window.focus_get(), self.editor.search_entry)
        self.editor.shortcut_profile.set_key('move_down', 'Ctrl+Shift+M')
        self.assertEqual(self.editor.context_menu.entrycget('下移', 'accelerator'), 'Ctrl+Shift+M')

    def test_close_releases_every_dynamic_root_and_tree_callback(self):
        self.editor.shortcut_profile.set_key('find', 'Ctrl+G')
        root = self.editor.window.winfo_toplevel()
        callbacks = [(widget, sequence, callback) for widget, sequence, callback
                     in self.editor._command_bindings if widget is root]
        with patch('toc_editor.messagebox.askyesnocancel', return_value=False):
            self.editor.close()
        self.assertTrue(self.editor.closed)
        self.assertEqual(self.editor._command_bindings, [])
        self.assertEqual(self.editor.shortcut_profile.overrides, {'find': 'Ctrl+G'})
        for _widget, _sequence, callback in callbacks:
            self.assertFalse(self.root.tk.call('info', 'commands', callback))


class SharedShortcutProfileTests(unittest.TestCase):
    setUp = main_fixtures.MainShortcutsPreviewTests.setUp
    tearDown = main_fixtures.MainShortcutsPreviewTests.tearDown
    pump = main_fixtures.MainShortcutsPreviewTests.pump
    load = main_fixtures.MainShortcutsPreviewTests.load

    def test_customization_persists_without_losing_other_settings_and_editor_reopen_uses_it(self):
        self.main.shortcut_profile.set_key('add', 'Ctrl+M')
        self.main._save_settings()
        self.assertEqual(load_settings(self.settings)['editor_shortcuts'], {'add': 'Ctrl+M'})
        self.assertEqual(load_settings(self.settings)['backup'], self.main.backup.get())
        self.main._open_editor()
        self.pump(lambda: self.main.editor is not None)
        first = self.main.editor
        self.assertIs(first.shortcut_profile, self.main.shortcut_profile)
        self.assertEqual(first.entry_menu.entrycget('添加', 'accelerator'), 'Ctrl+M')
        first.close()
        self.main._open_editor()
        self.pump(lambda: self.main.editor is not None and self.main.editor is not first)
        self.assertEqual(self.main.editor.shortcut_profile.key('add'), 'Ctrl+M')
        self.main.shortcut_profile.reset()
        self.assertEqual(load_settings(self.settings)['editor_shortcuts'], {})

    def test_help_before_editor_creation_reads_shared_profile_and_top_menu_updates(self):
        self.main._show_help()
        dialog = self.root._pdf_help_dialog
        self.main.shortcut_profile.set_key('find', 'Ctrl+G')
        self.main._open_editor()
        self.pump(lambda: self.main.editor is not None)
        self.main._update_edit_menu()
        self.assertEqual(self.main.edit_menu.entrycget('查找目录…', 'accelerator'), 'Ctrl+G')
        self.assertIn('Ctrl+G', str([dialog.shortcuts.item(i, 'values')
                                   for i in dialog.shortcuts.get_children()]))
        dialog.close()

    def test_shortcut_saves_preserve_unknown_settings_and_main_write_failure_is_atomic(self):
        save_config({'future_preference': {'keep': True}, 'backup': False}, self.settings)
        original = self.settings.read_bytes()
        with patch('bookmarks_gui.save_settings', side_effect=OSError('blocked')):
            with self.assertRaises(OSError):
                self.main.shortcut_profile.set_key('add', 'Ctrl+M')
        self.assertEqual(self.settings.read_bytes(), original)
        self.assertEqual(self.main.shortcut_profile.overrides, {})
        self.assertEqual(self.main.editor_settings['editor_shortcuts'], {})
        self.main.shortcut_profile.set_key('add', 'Ctrl+M')
        saved = read_config(self.settings)
        self.assertEqual(saved['schema'], 1)
        self.assertEqual(saved['editor_shortcuts'], {'add': 'Ctrl+M'})
        self.assertEqual(saved['future_preference'], {'keep': True})
        self.assertFalse(saved['backup'])


if __name__ == '__main__':
    unittest.main()
