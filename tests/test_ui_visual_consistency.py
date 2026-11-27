"""Compact theme chrome keeps text, control states and tab geometry stable."""

import tkinter as tk
from tkinter import font as tkfont, ttk
import unittest
from unittest.mock import patch

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

    def contrast(self, first, second):
        def luminance(color):
            channels = [part / 65535 for part in self.rgb(color)]
            linear = [part / 12.92 if part <= .04045 else ((part + .055) / 1.055) ** 2.4
                      for part in channels]
            return sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))

        dark, pale = sorted((luminance(first), luminance(second)))
        return (pale + .05) / (dark + .05)

    def test_workspace_tab_text_and_input_focus_are_readable_in_all_themes(self):
        for name in ui_theme.PALETTES:
            with self.subTest(theme=name):
                ui_theme.apply_theme(self.root, name)
                for role, states in (("Workspace.TNotebook.Tab", ("selected",)),
                                     ("Accent.TButton", ("active",)),
                                     ("Hint.TLabel", ()), ("ReaderHint.TLabel", ()),
                                     ("Masthead.TLabel", ()), ("Document.TLabel", ()),
                                     ("PaperHeading.TLabel", ()), ("PaperDetail.TLabel", ())):
                    fg = self.style.lookup(role, "foreground", states)
                    bg = self.style.lookup(role, "background", states)
                    self.assertGreaterEqual(self.contrast(fg, bg), 4.5, role)
                for states in ((), ("focus",)):
                    edge = self.style.lookup("TEntry", "bordercolor", states)
                    fill = self.style.lookup("TEntry", "fieldbackground", states)
                    self.assertGreaterEqual(self.contrast(edge, fill), 3, states)

    def test_reading_contrast_and_line_height_across_all_themes_and_sizes(self):
        tree = ttk.Treeview(self.page, style="Review.Treeview")
        for scale in ui_theme.UI_SCALES:
            ui_theme.apply_ui_scale(self.root, scale)
            for theme in ui_theme.PALETTES:
                with self.subTest(theme=theme, scale=scale):
                    p = ui_theme.apply_theme(self.root, theme)
                    for fg, bg in (("foreground", "surface"), ("foreground", "heading"),
                                   ("muted", "paper_surround"), ("muted", "background"),
                                   ("context", "chapter"), ("pending", "chapter"),
                                   ("error", "background"), ("success", "background"),
                                   ("selected_foreground", "selected_background"),
                                   ("action_foreground", "action"), ("action_foreground", "accent_active"),
                                   ("checkmark", "action")):
                        self.assertGreaterEqual(self.contrast(p[fg], p[bg]), 7, (fg, bg))
                    for bg in ("surface", "chapter", "selected_background"):
                        self.assertGreaterEqual(self.contrast(p["accent"], p[bg]), 3, bg)
                    self.assertGreaterEqual(self.contrast(p["disabled"], p["background"]), 4.5)
                    for state, role in (((), "pending"), (("selected",), "foreground"),
                                        (("disabled",), "disabled")):
                        self.assertEqual(self.style.lookup("Review.TCheckbutton", "foreground", state), p[role])
                    self.assertEqual(self.rgb(tree.tag_configure("outline_heading", "background")), self.rgb(p["chapter"]))
                    for state in (("selected", "focus"), ("selected", "!focus")):
                        self.assertEqual(self.rgb(self.style.lookup("Review.Treeview", "background", state)),
                                         self.rgb(p["selected_background"]))
                    for name in ("PdfBody", "PdfOutlineTitle"):
                        height = tkfont.nametofont(name, root=self.root).metrics("linespace")
                        self.assertGreaterEqual(int(self.style.lookup("Review.Treeview", "rowheight")), height + 8)
                    self.assertEqual(str(self.combo.cget("font")), "PdfBody")

    def test_new_faces_keep_native_editing_and_distinct_tab_and_menu_states(self):
        def names(layout):
            for element, opts in layout:
                yield element
                yield from names(opts.get("children", ()))

        for name in ui_theme.PALETTES:
            with self.subTest(theme=name):
                p = ui_theme.apply_theme(self.root, name)
                for style, required in (
                        ("TEntry", {"PdfInput.field", "Entry.textarea"}),
                        ("TCombobox", {"PdfInput.field", "PdfSelect.downarrow", "Combobox.textarea"}),
                        ("Document.TMenubutton", {"PdfDocument.face", "PdfSelect.downarrow"}),
                        ("TNotebook.Tab", {"PdfTab.line", "Notebook.label"}),
                        ("Workspace.TNotebook.Tab", {"PdfWorkspace.tab", "PdfWorkspace.line", "Notebook.label"}),
                        ("Vertical.TScrollbar", {"Vertical.Scrollbar.thumb", "Vertical.Scrollbar.downarrow"}),
                        ("Review.Horizontal.TProgressbar", {"PdfReview.pbar", "PdfReview.trough"})):
                    self.assertTrue(required.issubset(names(self.style.layout(style))), style)
                self.assertNotIn("PdfSelect.downarrow", names(self.style.layout("Document.TButton")))
                for style in ("Treeview.Row", "Review.Treeview.Row"):
                    self.assertIn("PdfSelection.line", names(self.style.layout(style)))
                images = self.root._pdf_control_images["pdf_" + name]
                self.assertEqual((images["row_idle"].width(), images["row_idle"].height()), (0, 0))
                self.assertEqual(images["row_mark"].get(1, 1), tuple(v // 257 for v in self.rgb(p["accent"])))
                self.assertTrue(images["empty_line"].transparency_get(0, 0))
                self.assertFalse(images["underline"].transparency_get(0, 0))
                self.assertTrue(images["arrow"].transparency_get(8, 1))
                self.assertFalse(images["open_arrow"].transparency_get(8, 1))
                face = images["surface", "surface", 1, 4]
                self.assertTrue(face.transparency_get(0, 0))
                self.assertEqual(face.get(6, 6), tuple(channel // 257 for channel in self.rgb(p["surface"])))
                for style, state in (("Workspace.TNotebook.Tab", "selected"), ("Document.TMenubutton", "active")):
                    self.assertGreaterEqual(self.contrast(self.style.lookup(style, "foreground", (state,)),
                                                          self.style.lookup(style, "background", (state,))), 7)

    def test_pressed_label_moves_inside_the_same_hit_area_at_each_size(self):
        ui_theme.apply_theme(self.root, "light")
        for scale in ui_theme.UI_SCALES:
            ui_theme.apply_ui_scale(self.root, scale)
            for role in ("TButton", "TMenubutton", "Primary.TButton", "Zoom.TButton"):
                x, y = self.padding(role)
                self.assertEqual(self.padding(role, ("pressed",)), (x, y + 1, x, y - 1))
                self.assertEqual(self.padding(role, ("pressed", "disabled")), (x, y))

    def test_open_combobox_and_full_scrollbar_follow_the_native_widget_states(self):
        p = ui_theme.apply_theme(self.root, "dark")
        self.root.deiconify()
        self.root.update()
        self.root.tk.call("ttk::combobox::Post", str(self.combo))
        try:
            self.root.update()
            self.assertTrue(self.combo.instate(("pressed",)))
        finally:
            self.root.tk.call("ttk::combobox::Unpost", str(self.combo))
        self.root.update()
        self.assertFalse(self.combo.instate(("pressed",)))
        self.assertEqual(self.combo.get(), "章.节")
        scrollbar = ttk.Scrollbar(self.page)
        scrollbar.set(0, 1)
        self.assertTrue(scrollbar.instate(("disabled",)))
        self.assertEqual(self.rgb(self.style.lookup("Vertical.TScrollbar", "arrowcolor", scrollbar.state())),
                         self.rgb(p["surface"]))
        scrollbar.set(.2, .8)
        self.assertFalse(scrollbar.instate(("disabled",)))

    def test_theme_images_stop_growing_once_the_three_palettes_have_been_used(self):
        for theme in ui_theme.PALETTES:
            ui_theme.apply_theme(self.root, theme)
        warmed = set(self.root.image_names())
        for _ in range(3):
            for theme in ui_theme.PALETTES:
                ui_theme.apply_theme(self.root, theme)
                self.assertEqual(set(self.root.image_names()), warmed)

    def test_review_motion_stops_on_hide_and_respects_reduced_motion(self):
        bar = ui_theme.ReviewProgressbar(self.root)
        with patch.object(bar, "winfo_ismapped", return_value=True), patch.object(ui_theme, "_motion_allowed") as motion:
            bar.set_count("book", 2, 8)
            self.assertEqual(float(bar.cget("value")), 2)
            motion.assert_not_called()
            motion.return_value = True
            bar.set_count("book", 5, 8)
            first = bar._timer
            self.assertIsNotNone(first)
            bar.set_count("book", 5, 8)
            self.assertEqual(bar._timer, first)
            bar.set_count("book", 4, 8)
            self.assertNotEqual(bar._timer, first)
            bar.event_generate("<Unmap>")
            self.assertEqual(float(bar.cget("value")), 4)
            self.assertIsNone(bar._timer)
            motion.return_value = False
            bar.set_count("book", 6, 8)
            self.assertEqual(float(bar.cget("value")), 6)
            self.assertIsNone(bar._timer)
            bar.set_count("next book", 0, 3)
            self.assertEqual(float(bar.cget("maximum")), 3)
            self.assertEqual(float(bar.cget("value")), 0)

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
