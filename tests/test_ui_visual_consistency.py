"""Compact theme chrome keeps text, control states and tab geometry stable."""

import tkinter as tk
from tkinter import font as tkfont, ttk
import unittest

import ui_theme


class VisualConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.geometry("1000x760+12000+12000")
        self.style = ttk.Style(self.root)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)
        self.page = ttk.Frame(self.notebook)
        self.other = ttk.Frame(self.notebook)
        self.notebook.add(self.page, text="主界面 · 预览与写入")
        self.notebook.add(self.other, text="目录工作台 · 生成与编辑")
        self.group = ttk.LabelFrame(self.page, text="文件")
        self.group.pack(fill="x")
        self.entry = ttk.Entry(self.group, width=30)
        self.entry.insert(0, "第一章 基本概念")
        self.entry.pack(side="left")
        self.combo = ttk.Combobox(self.group, width=20, state="readonly",
                                  values=("章.节", "每章节号", "保留识别编号"))
        self.combo.current(0)
        self.combo.pack(side="left")
        self.button = ttk.Button(self.group, text="预览")
        self.button.pack(side="left")
        self.menu_button = ttk.Menubutton(self.group, text="目录操作")
        self.menu_button.pack(side="left")
        self.root.update_idletasks()

    def tearDown(self):
        self.root.destroy()

    def padding(self, style_name, state=()):
        value = self.style.lookup(style_name, "padding", state)
        return tuple(int(str(part)) for part in self.root.tk.splitlist(value))

    def rgb(self, value):
        return self.root.winfo_rgb(value)

    def test_theme_switching_keeps_compact_control_sizes_and_system_fonts(self):
        fonts = {name: tkfont.nametofont(name, root=self.root).actual()
                 for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont")}
        sizes = None
        geometry = self.root.geometry()
        for name in ("light", "dark", "eye_care", "light"):
            with self.subTest(theme=name):
                ui_theme.apply_theme(self.root, name)
                self.root.update_idletasks()
                actual = tuple((widget.winfo_reqwidth(), widget.winfo_reqheight())
                               for widget in (self.entry, self.combo, self.button, self.menu_button))
                if sizes is None:
                    sizes = actual
                self.assertEqual(actual, sizes)
                self.assertEqual(self.root.geometry(), geometry)
                self.assertEqual(self.padding("TButton"), (6, 3))
                self.assertEqual(self.padding("TMenubutton"), (6, 3))
                self.assertEqual(self.padding("TEntry"), (5, 2))
                self.assertEqual(self.padding("TCombobox"), (5, 2))
                for font_name, font in fonts.items():
                    self.assertEqual(tkfont.nametofont(font_name, root=self.root).actual(), font)
                self.assertGreaterEqual(self.entry.winfo_reqheight(),
                                        tkfont.nametofont("TkTextFont", root=self.root).metrics("linespace") + 4)

    def test_input_focus_and_disabled_edges_use_one_palette_without_resizing(self):
        for name in ui_theme.PALETTES:
            palette = ui_theme.apply_theme(self.root, name)
            self.root.update_idletasks()
            for widget, style_name in ((self.entry, "TEntry"), (self.combo, "TCombobox")):
                size = widget.winfo_reqwidth(), widget.winfo_reqheight()
                for state, expected in (("focus", "accent"), ("hover", "accent"),
                                        ("disabled focus", "border")):
                    with self.subTest(theme=name, control=style_name, state=state):
                        widget.state(("!focus", "!hover", "!disabled"))
                        widget.state(state.split())
                        self.root.update_idletasks()
                        for option in ("bordercolor", "lightcolor", "darkcolor"):
                            self.assertEqual(self.rgb(self.style.lookup(style_name, option, widget.state())),
                                             self.rgb(palette[expected]))
                        self.assertEqual((widget.winfo_reqwidth(), widget.winfo_reqheight()), size)
                widget.state(("!focus", "!hover", "!disabled"))
                self.assertEqual(str(self.style.lookup(style_name, "relief")), "solid")
                self.assertEqual(int(self.style.lookup(style_name, "borderwidth")), 1)

    def test_readonly_disabled_and_selection_semantics_survive_theme_changes(self):
        self.entry.selection_range(0, 3)
        self.entry.state(("readonly",))
        for name in ui_theme.PALETTES:
            with self.subTest(theme=name):
                palette = ui_theme.apply_theme(self.root, name)
                self.entry.insert("end", "不可插入")
                self.assertEqual(self.entry.get(), "第一章 基本概念")
                self.assertTrue(self.entry.selection_present())
                self.assertEqual((self.entry.index("sel.first"), self.entry.index("sel.last")), (0, 3))
                self.assertTrue(self.entry.instate(("readonly",)))
                self.assertTrue(self.combo.instate(("readonly",)))
                self.assertEqual(self.combo.get(), "章.节")
                self.assertEqual(self.rgb(self.style.lookup("TCombobox", "fieldbackground", ("readonly",))),
                                 self.rgb(palette["input_background"]))
                for style_name in ("TEntry", "TCombobox"):
                    self.assertEqual(self.rgb(self.style.lookup(style_name, "foreground", ("disabled",))),
                                     self.rgb(palette["disabled"]))
                self.assertEqual(int(self.style.lookup("TLabelframe", "borderwidth")), 1)

    def test_tab_selection_has_constant_padding_and_does_not_resize_the_window(self):
        geometry = self.root.geometry()
        for name in ui_theme.PALETTES:
            ui_theme.apply_theme(self.root, name)
            self.root.update_idletasks()
            size = self.notebook.winfo_reqwidth(), self.notebook.winfo_reqheight()
            for index in (1, 0, 1, 0):
                with self.subTest(theme=name, tab=index):
                    self.notebook.select(index)
                    self.root.update_idletasks()
                    for state in ((), ("selected",), ("active",), ("disabled",)):
                        self.assertEqual(self.padding("TNotebook.Tab", state), (10, 4))
                    self.assertEqual((self.notebook.winfo_reqwidth(), self.notebook.winfo_reqheight()), size)
                    self.assertEqual(self.root.geometry(), geometry)
                    self.assertEqual(self.entry.get(), "第一章 基本概念")
                    self.assertEqual(self.combo.get(), "章.节")


if __name__ == "__main__":
    unittest.main()
