"""Help is local, nonmodal, owner-scoped and follows the existing theme."""

import gc
import tkinter as tk
from tkinter import ttk
import unittest

from help_dialog import show_help
from ui_theme import PALETTES, apply_theme


class HelpDialogTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)

    def tearDown(self):
        if self.root is not None:
            self.root.destroy()
        self.root = None
        gc.collect()
        self.assertEqual(self.errors, [])

    def test_same_owner_reuses_one_help_window_and_reopens_after_close(self):
        self.root.deiconify()
        self.root.update()
        apply_theme(self.root, "dark")
        first = show_help(self.root, "dark")
        child = ttk.Frame(self.root)
        second = show_help(child, "dark")
        self.assertIs(first, second)
        self.assertEqual(self.root.grab_current(), None)
        self.assertEqual(str(first.window.transient()), str(self.root))
        first.window.withdraw()
        self.assertIs(show_help(self.root), first)
        self.root.update()
        self.assertEqual(first.window.state(), "normal")
        first.close()
        self.assertFalse(hasattr(self.root, "_pdf_help_dialog"))
        replacement = show_help(self.root)
        self.assertIsNot(replacement, first)

    def test_escape_closes_only_help_and_owner_destroy_destroys_the_reopened_help(self):
        self.root.deiconify()
        dialog = show_help(self.root)
        self.root.update()
        dialog.tabs.focus_force()
        dialog.tabs.event_generate("<Escape>")
        self.root.update()
        self.assertFalse(dialog.window.winfo_exists())
        self.assertTrue(self.root.winfo_exists())
        self.assertFalse(hasattr(self.root, "_pdf_help_dialog"))
        show_help(self.root)
        owner = self.root
        owner.destroy()
        self.root = None
        self.assertFalse(hasattr(owner, "_pdf_help_dialog"))
        self.assertEqual(owner.children, {})

    def test_help_does_not_switch_an_external_host_theme_or_install_global_bindings(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        before = style.theme_use()
        global_bindings = self.root.bind_all("<F1>")
        dialog = show_help(self.root, "dark")
        self.assertEqual(style.theme_use(), before)
        self.assertEqual(dialog.usage.cget("background"), PALETTES["dark"]["input_background"])
        self.assertEqual(self.root.bind_all("<F1>"), global_bindings)

    def test_both_reference_tabs_retain_readonly_content_and_follow_three_themes(self):
        apply_theme(self.root, "light")
        dialog = show_help(self.root)
        instructions = dialog.usage.get("1.0", "end-1c")
        rows = [dialog.shortcuts.item(iid, "values") for iid in dialog.shortcuts.get_children()]
        self.assertEqual(len(dialog.tabs.tabs()), 2)
        self.assertIn("Ctrl+S 只暂存校对草稿", instructions)
        self.assertTrue(any("Enter" == row[1] and "确认" in row[2] for row in rows))
        self.assertTrue(any("Delete" == row[1] and "保留磁盘文件" in row[2] for row in rows))
        self.assertEqual(str(dialog.usage.cget("state")), "disabled")
        for name, palette in PALETTES.items():
            apply_theme(self.root, name)
            self.assertEqual(dialog.usage.cget("background"), palette["input_background"])
            self.assertEqual(dialog.usage.cget("foreground"), palette["foreground"])
            self.assertEqual(dialog.usage.get("1.0", "end-1c"), instructions)
            self.assertEqual([dialog.shortcuts.item(iid, "values") for iid in dialog.shortcuts.get_children()], rows)

    def test_standalone_owners_have_independent_help_lifecycles(self):
        main_help = show_help(self.root)
        editor_owner = tk.Toplevel(self.root)
        editor_help = show_help(editor_owner)
        self.assertIsNot(editor_help, main_help)
        editor_owner.destroy()
        self.assertFalse(editor_help.window.winfo_exists())
        self.assertTrue(main_help.window.winfo_exists())

    def test_shortcut_details_remain_readable_at_minimum_width(self):
        self.root.deiconify()
        dialog = show_help(self.root)
        dialog.tabs.select(1)
        dialog.window.geometry("610x420")
        self.root.update()
        iid = next(i for i in dialog.shortcuts.get_children()
                   if dialog.shortcuts.item(i, "values")[1] == "Ctrl+S")
        dialog.shortcuts.selection_set(iid)
        self.root.update()
        action = dialog.shortcuts.item(iid, "values")[2]
        self.assertIn(action, dialog.shortcut_detail.cget("text"))
        self.assertLessEqual(int(dialog.shortcut_detail.cget("wraplength")), 610)


if __name__ == "__main__":
    unittest.main()
