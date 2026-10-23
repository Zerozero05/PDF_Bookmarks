"""Application text scaling and help search leave document data and keys intact."""

import json
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import font as tkfont, ttk
import unittest
from unittest.mock import Mock

import config_manager as config
from help_dialog import FIXED_SHORTCUTS, show_help
from shortcut_keys import COMMANDS, ShortcutProfile
from ui_theme import PALETTES, apply_theme, apply_ui_scale


class UIScaleConfigTests(unittest.TestCase):
    def test_optional_scale_is_strict_and_keeps_schema_one(self):
        self.assertEqual(config.sanitize_settings({})["ui_scale"], 100)
        self.assertEqual(config.CONFIG_SCHEMA, 1)
        for value in (100, 110, 125):
            self.assertEqual(config.sanitize_settings({"ui_scale": value})["ui_scale"], value)
        for value in (True, False, 1, 0, 99, 120, 150, 110.0, "125", None, [], {}):
            with self.subTest(invalid=value):
                self.assertEqual(config.sanitize_settings({"ui_scale": value})["ui_scale"], 100)
                with self.assertRaises(config.ConfigError):
                    config.validate_config({"ui_scale": value}, 1, strict_values=True)

    def test_scale_roundtrip_and_partial_update_preserve_unknown_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(json.dumps({"schema": 1, "theme": "eye_care", "future": {"value": [3]}}),
                            encoding="utf-8")
            config.update_config({"ui_scale": 125}, path)
            config.update_config({"last_update_check": 12.0}, path)
            result = config.read_config(path)
            self.assertEqual(result["ui_scale"], 125)
            self.assertEqual(result["schema"], 1)
            self.assertEqual(result["theme"], "eye_care")
            self.assertEqual(result["future"], {"value": [3]})


class UIScaleHelpTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("1000x760+20000+20000")
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.save = Mock()
        self.profile = ShortcutProfile(save=self.save)
        self.root._pdf_shortcut_profile = self.profile
        apply_theme(self.root, "light")

    def tearDown(self):
        self.root.update_idletasks()
        self.root.destroy()
        self.assertEqual(self.errors, [])

    def test_scale_changes_shared_fonts_rows_and_tick_without_dpi_geometry_or_pixel_changes(self):
        baseline = {name: tkfont.nametofont(name, root=self.root).actual()
                    for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont")}
        style = ttk.Style(self.root)
        tree = ttk.Treeview(self.root)
        tree.insert("", "end", text="第一章 基本概念", iid="chapter")
        image = tk.PhotoImage(master=self.root, width=1, height=1)
        image.put("#ab1234", to=(0, 0))
        checkbox_image = self.root._pdf_checkbutton_images["pdf_light"]["selected"]
        self.root.update_idletasks()
        geometry = self.root.geometry()
        dpi = self.root.tk.call("tk", "scaling")
        default_row = int(style.lookup("Treeview", "rowheight"))
        rows = []
        for scale in (125, 110, 125, 100):
            for theme in PALETTES:
                apply_ui_scale(self.root, scale)
                apply_theme(self.root, theme)
                self.root.update_idletasks()
                self.assertEqual(self.root.geometry(), geometry)
                self.assertEqual(self.root.tk.call("tk", "scaling"), dpi)
                self.assertEqual(image.get(0, 0), (171, 18, 52))
                self.assertEqual(tree.item("chapter", "text"), "第一章 基本概念")
                for name, font in baseline.items():
                    actual = tkfont.nametofont(name, root=self.root).actual()
                    self.assertEqual(actual["size"], round(font["size"] * scale / 100))
                    self.assertEqual(actual["family"], font["family"])
                self.assertIs(self.root._pdf_checkbutton_images["pdf_light"]["selected"], checkbox_image)
                rows.append(int(style.lookup("Treeview", "rowheight")))
        self.assertGreater(rows[0], default_row)
        self.assertEqual(rows[-1], default_row)
        for name, font in baseline.items():
            self.assertEqual(tkfont.nametofont(name, root=self.root).actual(), font)

    def test_invalid_scale_does_not_change_fonts_and_child_uses_same_baseline(self):
        baseline = tkfont.nametofont("TkDefaultFont", root=self.root).cget("size")
        for value in (True, 150, 110.0, "110", None):
            with self.assertRaises(ValueError):
                apply_ui_scale(self.root, value)
            self.assertEqual(tkfont.nametofont("TkDefaultFont", root=self.root).cget("size"), baseline)
        child = tk.Toplevel(self.root)
        apply_ui_scale(child, 125)
        apply_ui_scale(self.root, 100)
        self.assertEqual(tkfont.nametofont("TkDefaultFont", root=self.root).cget("size"), baseline)

    def test_help_search_filters_current_keys_and_restores_all_without_editing_profile(self):
        dialog = show_help(self.root)
        instructions = dialog.usage.get("1.0", "end-1c")
        all_rows = dialog.shortcuts.get_children()
        dialog.search_text.set("添加")
        self.assertEqual(dialog.shortcuts.get_children(), ("add",))
        dialog.tabs.select(1)
        dialog.search_entry.event_generate("<Return>")
        dialog._next_match()
        self.assertEqual(dialog.shortcuts.selection(), ("add",))
        self.assertEqual(str(dialog.edit_shortcut_button.cget("state")), "normal")
        self.profile.set_key("add", "Ctrl+Shift+I")
        dialog.search_text.set("ctrl+shift+i")
        self.assertEqual(dialog.shortcuts.get_children(), ("add",))
        self.assertEqual(dialog.shortcuts.item("add", "values")[1], "Ctrl+Shift+I")
        dialog.search_text.set("没有这种操作")
        self.assertEqual(dialog.shortcuts.get_children(), ())
        self.assertEqual(dialog.shortcuts.selection(), ())
        self.assertEqual(str(dialog.edit_shortcut_button.cget("state")), "disabled")
        self.assertIn("快捷键 0 项", dialog.search_status.get())
        dialog.clear_search_button.invoke()
        self.assertEqual(dialog.shortcuts.get_children(), all_rows)
        self.assertEqual(len(all_rows), len(FIXED_SHORTCUTS) + len(COMMANDS))
        self.assertEqual(dialog.usage.get("1.0", "end-1c"), instructions)
        self.assertEqual(str(dialog.usage.cget("state")), "disabled")
        self.save.assert_called_once_with({"add": "Ctrl+Shift+I"})

    def test_help_control_f_is_local_and_never_redirects_editor_search(self):
        owner_search = Mock()
        self.root.bind("<Control-f>", owner_search)
        original = self.root.bind("<Control-f>")
        dialog = show_help(self.root)
        self.root.update()
        dialog.usage.focus_force()
        self.root.update()
        dialog.usage.event_generate("<Control-f>")
        self.root.update()
        self.assertIs(self.root.focus_get(), dialog.search_entry)
        owner_search.assert_not_called()
        self.assertEqual(self.root.bind("<Control-f>"), original)
        dialog.search_text.set("目录")
        self.assertGreater(len(dialog.usage.tag_ranges("help_match")), 0)
        self.assertGreater(len(dialog._usage_matches), 0)
        dialog._next_match()
        self.assertEqual(dialog._match_index, 0)
        dialog._next_match()
        self.assertEqual(dialog._match_index, 1)
        dialog.close()
        self.assertEqual(self.root.bind("<Control-f>"), original)

    def test_help_late_open_and_theme_switches_use_shared_ui_font(self):
        apply_ui_scale(self.root, 125)
        dialog = show_help(self.root)
        for theme in PALETTES:
            apply_theme(self.root, theme)
            self.assertEqual(str(dialog.usage.cget("font")), "TkDefaultFont")
            self.assertEqual(str(ttk.Style(self.root).lookup("TEntry", "font")), "TkDefaultFont")
            self.assertEqual(self.root._pdf_ui_scale, 125)
        apply_ui_scale(self.root, 100)
        self.assertEqual(self.root._pdf_ui_scale, 100)

    def test_help_search_settings_and_close_remain_accessible_in_large_text_at_minimum_size(self):
        dialog = show_help(self.root)
        dialog.tabs.select(1)
        self.root.update()
        for scale in (100, 110, 125):
            apply_ui_scale(self.root, scale)
            for theme in PALETTES:
                apply_theme(self.root, theme)
                dialog.window.geometry("610x420+20000+20000")
                dialog.shortcuts.selection_set("add")
                dialog._shortcut_selected()
                self.root.update_idletasks()
                with self.subTest(scale=scale, theme=theme):
                    for widget in (dialog.search_entry, dialog.edit_shortcut_button,
                                   dialog.reset_shortcut_button, dialog.reset_all_button,
                                   dialog.close_button):
                        self.assertTrue(widget.winfo_ismapped(), str(widget))
                        left = widget.winfo_rootx() - dialog.window.winfo_rootx()
                        top = widget.winfo_rooty() - dialog.window.winfo_rooty()
                        self.assertGreaterEqual(left, 0)
                        self.assertGreaterEqual(top, 0)
                        self.assertLessEqual(left + widget.winfo_width(), dialog.window.winfo_width())
                        self.assertLessEqual(top + widget.winfo_height(), dialog.window.winfo_height())
                    self.assertGreater(dialog.shortcuts.winfo_height(), 40)


if __name__ == "__main__":
    unittest.main()
