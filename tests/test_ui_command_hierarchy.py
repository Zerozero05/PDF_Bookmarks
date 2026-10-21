"""Primary and quiet commands keep familiar dimensions and readable states."""

import tkinter as tk
from tkinter import ttk
import unittest

from ui_theme import PALETTES, apply_theme


class CommandHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.style = ttk.Style(self.root)
        self.buttons = [ttk.Button(self.root, text="页面预览", style=name)
                        for name in ("TButton", "Secondary.TButton", "Accent.TButton", "Primary.TButton")]
        self.menus = [ttk.Menubutton(self.root, text="目录操作", style=name)
                      for name in ("TMenubutton", "Secondary.TMenubutton")]
        for widget in (*self.buttons, *self.menus):
            widget.pack()

    def tearDown(self):
        self.root.destroy()

    def rgb(self, color):
        return self.root.winfo_rgb(color)

    def test_quiet_commands_keep_original_text_geometry_across_all_themes(self):
        original_sizes = None
        for name in PALETTES:
            apply_theme(self.root, name)
            self.root.update_idletasks()
            sizes = tuple((widget.winfo_reqwidth(), widget.winfo_reqheight())
                          for widget in (*self.buttons, *self.menus))
            self.assertEqual(len(set(sizes[:4])), 1)
            self.assertEqual(sizes[4], sizes[5])
            if original_sizes is None:
                original_sizes = sizes
            self.assertEqual(sizes, original_sizes)
            for widget in (*self.buttons, *self.menus):
                size = widget.winfo_reqwidth(), widget.winfo_reqheight()
                for state in (("active",), ("focus",), ("disabled",)):
                    widget.state(("!active", "!focus", "!disabled"))
                    widget.state(state)
                    self.root.update_idletasks()
                    self.assertEqual((widget.winfo_reqwidth(), widget.winfo_reqheight()), size)
                widget.state(("!active", "!focus", "!disabled"))

    def test_quiet_surfaces_and_focus_states_follow_the_existing_palette(self):
        for name in PALETTES:
            palette = apply_theme(self.root, name)
            for style in ("Secondary.TButton", "Secondary.TMenubutton"):
                self.assertEqual(self.rgb(self.style.lookup(style, "background")), self.rgb(palette["background"]))
                self.assertEqual(self.rgb(self.style.lookup(style, "foreground")), self.rgb(palette["foreground"]))
                for state in (("active",), ("focus",), ("pressed",)):
                    self.assertEqual(self.rgb(self.style.lookup(style, "bordercolor", state)), self.rgb(palette["accent"]))
                self.assertEqual(self.rgb(self.style.lookup(style, "background", ("active",))), self.rgb(palette["hover"]))
                self.assertEqual(self.rgb(self.style.lookup(style, "foreground", ("disabled",))), self.rgb(palette["disabled"]))
            self.assertEqual(self.rgb(self.style.lookup("Toolbar.TFrame", "background")), self.rgb(palette["background"]))
            self.assertEqual(self.rgb(self.style.lookup("Section.TLabel", "foreground")), self.rgb(palette["foreground"]))
            self.assertEqual(self.rgb(self.style.lookup("Muted.TLabel", "foreground")), self.rgb(palette["muted"]))

    def test_primary_alias_and_disabled_command_behavior_match_existing_accent(self):
        called = []
        button = ttk.Button(self.root, text="保存", style="Secondary.TButton", command=lambda: called.append(True))
        for name in PALETTES:
            apply_theme(self.root, name)
            for state in ((), ("active",), ("pressed",), ("disabled",)):
                for option in ("background", "foreground", "bordercolor", "padding"):
                    self.assertEqual(str(self.style.lookup("Primary.TButton", option, state)),
                                     str(self.style.lookup("Accent.TButton", option, state)))
            button.state(("disabled",))
            button.invoke()
            self.assertFalse(called)
            button.state(("!disabled",))
            button.invoke()
            self.assertEqual(called, [True])
            called.clear()


if __name__ == "__main__":
    unittest.main()
