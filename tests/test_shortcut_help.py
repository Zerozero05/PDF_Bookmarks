"""F1 edits only scoped shortcut settings and reflects the shared profile."""

import gc
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from help_dialog import show_help
from shortcut_keys import COMMANDS, ShortcutProfile
from ui_theme import apply_theme


class ShortcutHelpTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("200x100+20000+20000")
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.save = Mock()
        self.profile = ShortcutProfile(save=self.save)
        self.root._pdf_shortcut_profile = self.profile
        apply_theme(self.root, "light")

    def tearDown(self):
        self.root.destroy()
        self.root = None
        gc.collect()
        self.assertEqual(self.errors, [])

    def open(self):
        dialog = show_help(self.root)
        dialog.window.geometry("610x420+20000+20000")
        dialog.tabs.select(1)
        self.root.update()
        return dialog

    def choose(self, dialog, action):
        dialog.shortcuts.selection_set(action)
        dialog.shortcuts.focus(action)
        dialog._shortcut_selected()
        self.root.update()

    def test_table_shows_every_command_defaults_and_keeps_fixed_rows_readonly(self):
        dialog = self.open()
        self.assertEqual(len(COMMANDS), 15)
        for action, command in COMMANDS.items():
            self.assertEqual(dialog.shortcuts.item(action, "values")[:2],
                             (command["scope"], command["default"]))
        self.choose(dialog, "add")
        self.assertEqual(str(dialog.edit_shortcut_button.cget("state")), "normal")
        self.assertEqual(str(dialog.reset_shortcut_button.cget("state")), "disabled")
        self.choose(dialog, "fixed:0")
        self.assertEqual(str(dialog.edit_shortcut_button.cget("state")), "disabled")
        self.assertIn("固定操作", dialog.shortcut_detail.cget("text"))
        dialog._edit_shortcut()
        self.assertIsNone(dialog._capture_window)
        self.save.assert_not_called()

    def test_capture_and_apply_saves_before_table_and_listener_updates(self):
        dialog = self.open()
        self.choose(dialog, "add")
        before_bindings = [self.root.bind_all(key) for key in ("<Return>", "<Control-n>", "<Delete>")]
        listener = Mock()
        self.profile.subscribe(listener)
        dialog.edit_shortcut_button.invoke()
        self.assertEqual(self.root.grab_current(), None)
        self.assertEqual(str(dialog.capture_entry.cget("state")), "readonly")
        dialog._capture_key(SimpleNamespace(keysym="Control_L", state=0x4))
        self.assertEqual(dialog.capture_value.get(), "Ctrl+N")
        dialog._capture_key(SimpleNamespace(keysym="i", state=0x4 | 0x1))
        self.assertEqual(dialog.capture_value.get(), "Ctrl+Shift+I")
        self.save.side_effect = lambda updates: self.assertEqual(
            dialog.shortcuts.item("add", "values")[1], "Ctrl+N")
        dialog._apply_shortcut()
        self.save.assert_called_once_with({"add": "Ctrl+Shift+I"})
        listener.assert_called_once_with()
        self.assertEqual(dialog.shortcuts.item("add", "values")[1], "Ctrl+Shift+I")
        self.assertEqual(dialog.shortcuts.selection(), ("add",))
        self.assertIsNone(dialog._capture_window)
        self.assertEqual([self.root.bind_all(key) for key in ("<Return>", "<Control-n>", "<Delete>")],
                         before_bindings)

    def test_collision_and_reserved_keys_keep_capture_open_and_do_not_save(self):
        dialog = self.open()
        self.choose(dialog, "add")
        dialog._edit_shortcut()
        for key, message in (("Alt+Up", "冲突"), ("F1", "保留"), ("1", "普通输入")):
            with self.subTest(key=key):
                dialog.capture_value.set(key)
                dialog._apply_shortcut()
                self.assertTrue(dialog._capture_window.winfo_exists())
                self.assertIn(message, dialog.capture_status.get())
                self.assertEqual(self.profile.overrides, {})
                self.assertEqual(dialog.shortcuts.item("add", "values")[1], "Ctrl+N")
        self.save.assert_not_called()

    def test_saving_failure_keeps_old_setting_and_can_retry(self):
        dialog = self.open()
        self.choose(dialog, "move_down")
        dialog._edit_shortcut()
        dialog.capture_value.set("Ctrl+Alt+Down")
        self.save.side_effect = OSError("模拟设置写入失败")
        dialog._apply_shortcut()
        self.assertIn("模拟设置写入失败", dialog.capture_status.get())
        self.assertEqual(self.profile.overrides, {})
        self.assertEqual(dialog.shortcuts.item("move_down", "values")[1], "Alt+Down")
        self.assertTrue(dialog._capture_window.winfo_exists())
        self.save.side_effect = None
        dialog._apply_shortcut()
        self.assertEqual(self.profile.overrides, {"move_down": "Ctrl+Alt+Down"})
        self.assertIsNone(dialog._capture_window)

    def test_escape_cancels_only_capture_then_help_escape_keeps_owner(self):
        dialog = self.open()
        self.choose(dialog, "add")
        dialog._edit_shortcut()
        capture = dialog._capture_window
        dialog.capture_entry.focus_force()
        self.root.update()
        dialog.capture_entry.event_generate("<Escape>")
        self.root.update()
        self.assertFalse(capture.winfo_exists())
        self.assertTrue(dialog.window.winfo_exists())
        self.save.assert_not_called()
        dialog.tabs.focus_force()
        self.root.update()
        dialog.tabs.event_generate("<Escape>")
        self.root.update()
        self.assertFalse(dialog.window.winfo_exists())
        self.assertTrue(self.root.winfo_exists())

    def test_reset_selected_and_reset_all_preserve_unrelated_customizations(self):
        self.profile.set_key("add", "Ctrl+Shift+I")
        self.profile.set_key("move_up", "Ctrl+Alt+Up")
        self.save.reset_mock()
        dialog = self.open()
        self.choose(dialog, "add")
        dialog.reset_shortcut_button.invoke()
        self.assertEqual(self.profile.overrides, {"move_up": "Ctrl+Alt+Up"})
        self.assertEqual(dialog.shortcuts.item("add", "values")[1], "Ctrl+N")
        self.assertEqual(dialog.shortcuts.item("move_up", "values")[1], "Ctrl+Alt+Up")
        dialog.reset_all_button.invoke()
        self.assertEqual(self.profile.overrides, {})
        self.save.assert_called_with({})
        self.assertEqual(dialog.shortcuts.item("move_up", "values")[1], "Alt+Up")
        self.assertEqual(str(dialog.reset_all_button.cget("state")), "disabled")

    def test_failed_reset_keeps_rows_and_shows_inline_error(self):
        self.profile.set_key("add", "Ctrl+Shift+I")
        dialog = self.open()
        self.choose(dialog, "add")
        self.save.side_effect = OSError("设置只读")
        dialog.reset_shortcut_button.invoke()
        self.assertIn("设置只读", dialog.shortcut_status.get())
        self.assertEqual(self.profile.key("add"), "Ctrl+Shift+I")
        self.assertEqual(dialog.shortcuts.item("add", "values")[1], "Ctrl+Shift+I")

    def test_shared_profile_updates_both_help_windows_and_unsubscribes_on_destroy(self):
        dialog = self.open()
        other_owner = tk.Toplevel(self.root)
        other_owner._pdf_shortcut_profile = self.profile
        other_dialog = show_help(other_owner)
        self.choose(dialog, "move_up")
        self.profile.set_key("move_up", "Ctrl+Alt+Up")
        self.assertEqual(dialog.shortcuts.item("move_up", "values")[1], "Ctrl+Alt+Up")
        self.assertEqual(other_dialog.shortcuts.item("move_up", "values")[1], "Ctrl+Alt+Up")
        self.assertEqual(dialog.shortcuts.selection(), ("move_up",))
        self.choose(dialog, "add")
        dialog._edit_shortcut()
        capture = dialog._capture_window
        with patch.object(self.profile, "unsubscribe", wraps=self.profile.unsubscribe) as unsubscribe:
            dialog.close()
            unsubscribe.assert_called_once_with(dialog._profile_listener)
        self.assertFalse(capture.winfo_exists())
        self.profile.set_key("add", "Ctrl+Shift+I")
        self.assertEqual(other_dialog.shortcuts.item("add", "values")[1], "Ctrl+Shift+I")

    def test_without_editable_profile_help_stays_readonly_and_preserves_usage(self):
        self.root._pdf_shortcut_profile = ShortcutProfile()
        dialog = self.open()
        self.choose(dialog, "add")
        self.assertEqual(str(dialog.edit_shortcut_button.cget("state")), "disabled")
        self.assertEqual(str(dialog.reset_all_button.cget("state")), "disabled")
        dialog._edit_shortcut()
        self.assertIsNone(dialog._capture_window)
        self.assertIn("当前窗口仅查看", dialog.shortcut_detail.cget("text"))
        self.assertEqual(str(dialog.usage.cget("state")), "disabled")
        before = dialog.usage.get("1.0", "end-1c")
        self.root._pdf_shortcut_profile = None
        dialog.close()
        delattr(self.root, "_pdf_shortcut_profile")
        dialog = self.open()
        self.choose(dialog, "add")
        self.assertEqual(str(dialog.edit_shortcut_button.cget("state")), "disabled")
        self.assertEqual(dialog.usage.get("1.0", "end-1c"), before)
        self.save.assert_not_called()

    def test_selected_details_leave_footer_and_settings_visible_at_both_sizes_in_all_themes(self):
        dialog = self.open()
        for theme in ("light", "dark", "eye_care"):
            apply_theme(self.root, theme)
            for width, height in ((760, 550), (610, 420)):
                with self.subTest(theme=theme, width=width, height=height):
                    dialog.window.geometry(f"{width}x{height}+20000+20000")
                    self.choose(dialog, "add")
                    self.root.update_idletasks()
                    self.assertIn("添加目录项", dialog.shortcut_detail.cget("text"))
                    for widget in (dialog.shortcut_detail, dialog.edit_shortcut_button,
                                   dialog.reset_shortcut_button, dialog.reset_all_button,
                                   dialog.close_button):
                        self.assertTrue(widget.winfo_ismapped())
                        left = widget.winfo_rootx() - dialog.window.winfo_rootx()
                        top = widget.winfo_rooty() - dialog.window.winfo_rooty()
                        self.assertGreaterEqual(left, 0)
                        self.assertGreaterEqual(top, 0)
                        self.assertLessEqual(left + widget.winfo_width(), dialog.window.winfo_width())
                        self.assertLessEqual(top + widget.winfo_height(), dialog.window.winfo_height())
                    self.assertGreater(dialog.shortcuts.winfo_height(), 60)
                    self.assertGreaterEqual(dialog.close_button.winfo_y(), 0)
                    self.assertLessEqual(
                        dialog.tabs.winfo_rooty() + dialog.tabs.winfo_height(),
                        dialog.close_button.winfo_rooty())


if __name__ == "__main__":
    unittest.main()

