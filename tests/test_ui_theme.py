"""Local Tk themes retain content, PDF pixels and unrelated business colors."""

import tkinter as tk
from tkinter import ttk
import unittest

import ui_theme


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.geometry("640x480+80+60")
        self.frame = ttk.Frame(self.root)
        self.frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.frame, background="white")
        self.image = tk.PhotoImage(master=self.root, width=2, height=1)
        self.image.put("#ffffff", to=(0, 0))
        self.image.put("#ab1234", to=(1, 0))
        self.image_item = self.canvas.create_image(0, 0, image=self.image, anchor="nw")
        self.text = tk.Text(self.frame)
        self.text.insert("1.0", "只修改外观，不改变内容。")
        self.text.configure(state="disabled")
        self.tree = ttk.Treeview(self.frame, style="Review.Treeview")
        self.tree.insert("", "end", iid="chapter", text="第一章 基本概念", tags=("pending",))
        self.tree.tag_configure("pending", foreground="#805000")
        self.tree.tag_configure("context", foreground="#767676")
        self.tree.tag_configure("custom_warning", foreground="#a012ef")
        self.hint = ttk.Label(self.frame, text="草稿提示", foreground="#53616d")
        self.warning = ttk.Label(self.frame, text="业务提示", foreground="#a012ef")
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def rgb(self, color):
        return self.root.winfo_rgb(color)

    def test_both_local_themes_style_controls_and_readonly_disabled_states(self):
        style = ttk.Style(self.root)
        for name in ("light", "dark"):
            with self.subTest(theme=name):
                p = ui_theme.apply_theme(self.root, name)
                self.assertEqual(style.theme_use(), "pdf_" + name)
                for control in ("TFrame", "TLabel", "Title.TLabel", "Muted.TLabel", "TLabelframe", "TNotebook", "TButton", "TCheckbutton",
                                "TRadiobutton", "TEntry", "TCombobox", "TScrollbar", "TPanedwindow",
                                "Horizontal.TProgressbar", "Vertical.TProgressbar", "Review.Treeview"):
                    self.assertTrue(style.lookup(control, "background"), control)
                self.assertEqual(self.rgb(style.lookup("TEntry", "foreground", ("disabled",))), self.rgb(p["disabled"]))
                self.assertEqual(self.rgb(style.lookup("TCombobox", "fieldbackground", ("readonly",))), self.rgb(p["input_background"]))
                self.assertEqual(self.rgb(style.lookup("Review.Treeview", "foreground", ("selected",))), self.rgb(p["selected_foreground"]))
                self.assertEqual(self.rgb(style.lookup("Accent.TButton", "background")), self.rgb(p["accent"]))
                self.assertEqual(self.rgb(style.lookup("Accent.TButton", "foreground", ("disabled",))), self.rgb(p["disabled"]))
                self.assertGreaterEqual(int(style.lookup("Review.Treeview", "rowheight")), 20)

    def test_switching_themes_preserves_pixels_text_tree_and_window_geometry(self):
        geometry = self.root.geometry()
        for name in ("dark", "light", "dark", "light"):
            p = ui_theme.apply_theme(self.root, name)
            self.root.update()
            self.assertEqual(self.root.geometry(), geometry)
            self.assertEqual(self.rgb(self.canvas.cget("background")), self.rgb(p["surface"]))
            self.assertEqual(self.rgb(self.text.cget("background")), self.rgb(p["input_background"]))
            self.assertEqual(self.rgb(self.text.cget("foreground")), self.rgb(p["foreground"]))
            self.assertEqual(self.rgb(self.text.cget("insertbackground")), self.rgb(p["foreground"]))
            self.assertEqual(self.text.get("1.0", "end-1c"), "只修改外观，不改变内容。")
            self.assertEqual(self.text.cget("state"), "disabled")
            self.assertEqual((self.image.get(0, 0), self.image.get(1, 0)), ((255, 255, 255), (171, 18, 52)))
            self.assertEqual(self.canvas.itemcget(self.image_item, "image"), str(self.image))
            self.assertEqual(self.tree.item("chapter", "text"), "第一章 基本概念")
            self.assertEqual(self.tree.item("chapter", "tags"), ("pending",))
            self.assertEqual(str(self.tree.tag_configure("custom_warning", "foreground")), "#a012ef")
            self.assertEqual(str(self.warning.cget("foreground")), "#a012ef")

    def test_refresh_later_created_widgets_and_known_hint_colors(self):
        p = ui_theme.apply_theme(self.root, "dark")
        later = tk.Toplevel(self.root)
        later.withdraw()
        canvas, text = tk.Canvas(later, background="white"), tk.Text(later)
        tree = ttk.Treeview(later)
        hint = ttk.Label(later, text="稍后创建的提示", foreground="#767676")
        self.assertEqual(ui_theme.refresh_theme_widgets(later), p)
        self.assertEqual(self.rgb(later.cget("background")), self.rgb(p["background"]))
        self.assertEqual(self.rgb(canvas.cget("background")), self.rgb(p["surface"]))
        self.assertEqual(self.rgb(text.cget("selectbackground")), self.rgb(p["selected_background"]))
        self.assertEqual(self.rgb(tree.tag_configure("pending", "foreground")), self.rgb(p["pending"]))
        self.assertEqual(self.rgb(tree.tag_configure("context", "foreground")), self.rgb(p["context"]))
        self.assertEqual(hint.cget("style"), "Muted.TLabel")
        self.assertEqual(self.hint.cget("style"), "Muted.TLabel")
        self.assertEqual(str(hint.cget("foreground")), "")
        self.assertEqual(self.rgb(ttk.Style(later).lookup("Muted.TLabel", "foreground")), self.rgb(p["muted"]))

    def test_invalid_theme_is_rejected_without_changing_the_current_theme(self):
        ui_theme.apply_theme(self.root, "dark")
        with self.assertRaises(ValueError):
            ui_theme.apply_theme(self.root, "system")
        self.assertEqual(ttk.Style(self.root).theme_use(), "pdf_dark")

    def test_existing_and_later_combobox_popdowns_follow_the_local_theme(self):
        def popdown_listbox(combo):
            popup = self.root.tk.call("ttk::combobox::PopdownWindow", str(combo))
            pending = [popup]
            while pending:
                path = pending.pop()
                if self.root.tk.call("winfo", "class", path) == "Listbox":
                    return path
                pending.extend(self.root.tk.splitlist(self.root.tk.call("winfo", "children", path)))
            self.fail("Combobox popup listbox was not created")

        combo = ttk.Combobox(self.frame, state="readonly", values=("白天", "夜间"))
        existing = popdown_listbox(combo)
        for name in ("dark", "light", "dark"):
            p = ui_theme.apply_theme(self.root, name)
            for option, expected in (("background", "input_background"), ("foreground", "foreground"),
                                     ("selectbackground", "selected_background"), ("selectforeground", "selected_foreground")):
                self.assertEqual(self.rgb(self.root.tk.call(existing, "cget", "-" + option)), self.rgb(p[expected]))
        later = ttk.Combobox(self.frame, state="readonly", values=("新建",))
        popup = popdown_listbox(later)
        self.assertEqual(self.rgb(self.root.tk.call(popup, "cget", "-background")), self.rgb(p["input_background"]))
        self.assertEqual(self.rgb(self.root.tk.call(popup, "cget", "-foreground")), self.rgb(p["foreground"]))

    def test_main_hint_review_and_selection_colors_have_readable_contrast(self):
        def luminance(color):
            rgb = [channel / 65535 for channel in self.rgb(color)]
            linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in rgb]
            return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))

        for name in ("light", "dark"):
            p = ui_theme.apply_theme(self.root, name)
            for foreground, background in (("foreground", "background"), ("muted", "background"),
                                           ("context", "surface"), ("pending", "surface"),
                                           ("selected_foreground", "selected_background")):
                with self.subTest(theme=name, foreground=foreground):
                    low, high = sorted((luminance(p[foreground]), luminance(p[background])))
                    self.assertGreaterEqual((high + .05) / (low + .05), 4.5)


if __name__ == "__main__":
    unittest.main()
