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
        for name in ui_theme.PALETTES:
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
        for name in ("dark", "eye_care", "light", "eye_care", "dark", "light"):
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

    def test_eye_care_refreshes_menu_and_passive_help_with_the_same_palette(self):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="目录操作")
        button = ttk.Button(self.frame, text="设置")
        button.pack()
        handle = ui_theme.add_tooltip(button, "暖色界面；PDF 内容保持原样。")
        try:
            palette = ui_theme.apply_theme(self.root, "eye_care")
            self.root.deiconify()
            self.root.update()
            handle._show()
            self.assertIsNotNone(handle.tip)
            label = handle.tip.winfo_children()[0]
            expected_menu = ui_theme.menu_colors(menu, palette)
            self.assertEqual(self.rgb(menu.cget("background")), self.rgb(expected_menu["background"]))
            self.assertEqual(self.rgb(menu.cget("foreground")), self.rgb(expected_menu["foreground"]))
            self.assertEqual(self.rgb(label.cget("background")), self.rgb(palette["surface"]))
            self.assertEqual(self.rgb(label.cget("foreground")), self.rgb(palette["foreground"]))
            self.assertIsNone(self.root.grab_current())
        finally:
            handle.close()
            self.root.withdraw()

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
        for name in ("dark", "eye_care", "light", "dark", "eye_care"):
            p = ui_theme.apply_theme(self.root, name)
            for option, expected in (("background", "input_background"), ("foreground", "foreground"),
                                     ("selectbackground", "selected_background"), ("selectforeground", "selected_foreground")):
                self.assertEqual(self.rgb(self.root.tk.call(existing, "cget", "-" + option)), self.rgb(p[expected]))
        later = ttk.Combobox(self.frame, state="readonly", values=("新建",))
        popup = popdown_listbox(later)
        self.assertEqual(self.rgb(self.root.tk.call(popup, "cget", "-background")), self.rgb(p["input_background"]))
        self.assertEqual(self.rgb(self.root.tk.call(popup, "cget", "-foreground")), self.rgb(p["foreground"]))

    def test_checkbutton_indicator_draws_a_tick_instead_of_a_cross(self):
        for name in ui_theme.PALETTES:
            with self.subTest(theme=name):
                p = ui_theme.apply_theme(self.root, name)
                style = ttk.Style(self.root)
                self.assertIn("Checkbutton.indicator", style.element_names())
                images = self.root._pdf_checkbutton_images["pdf_" + name]
                checked = images["selected"]
                size = checked.width()

                def pixel(x, y):
                    return checked.get(round(x * (size - 1)), round(y * (size - 1)))

                # The rising long stroke and lower short stroke form a tick;
                # a cross would also have a white upper-left diagonal.
                self.assertEqual(pixel(.25, .30), tuple(v // 257 for v in self.rgb(p["accent"])))
                self.assertEqual(pixel(.30, .54), (255, 255, 255))
                self.assertEqual(pixel(.70, .40), (255, 255, 255))
                self.assertEqual(images["unselected"].get(size // 2, size // 2),
                                 tuple(v // 257 for v in self.rgb(p["input_background"])))
                self.assertNotEqual(images["disabled_selected"].get(size // 2, size // 2),
                                    images["disabled_unselected"].get(size // 2, size // 2))

    def test_tick_pixels_remain_unambiguous_at_different_indicator_sizes(self):
        # A font/DPI-dependent 15px image quantizes the old (.40, .60)
        # sample into the bend's background. Sample inside both strokes.
        for name, palette in ui_theme.PALETTES.items():
            for size in range(14, 37):
                with self.subTest(theme=name, size=size):
                    images = ui_theme._checkbutton_images(self.root, palette, size)
                    checked = images["selected"]

                    def pixel(x, y):
                        return checked.get(round(x * (size - 1)), round(y * (size - 1)))

                    self.assertEqual(pixel(.25, .30), tuple(v // 257 for v in self.rgb(palette["accent"])))
                    self.assertEqual(pixel(.30, .54), (255, 255, 255))
                    self.assertEqual(pixel(.70, .40), (255, 255, 255))
                    self.assertEqual(images["unselected"].get(size // 2, size // 2),
                                     tuple(v // 257 for v in self.rgb(palette["input_background"])))

    def test_themed_checkbuttons_keep_variable_command_keyboard_and_disabled_behavior(self):
        enabled = tk.BooleanVar(self.root, False)
        mode = tk.StringVar(self.root, "light")
        calls = []
        folder = ttk.Checkbutton(self.frame, text="包含子文件夹", variable=enabled,
                                 command=lambda: calls.append(enabled.get()))
        later = tk.Toplevel(self.root)
        later.withdraw()
        night = ttk.Checkbutton(later, text="夜间模式", variable=mode,
                                onvalue="dark", offvalue="light")
        folder.pack()
        for name in ("light", "dark", "light"):
            ui_theme.apply_theme(self.root, name)
            folder.invoke()
            self.assertTrue(enabled.get())
            folder.state(["disabled"])
            folder.invoke()
            self.assertTrue(enabled.get())
            self.assertTrue(folder.instate(["disabled", "selected"]))
            folder.state(["!disabled"])
            folder.invoke()
            self.assertFalse(enabled.get())
            night.invoke()
            self.assertEqual(mode.get(), "dark")
            night.invoke()
            self.assertEqual(mode.get(), "light")
        self.assertEqual(calls, [True, False] * 3)
        self.root.deiconify()
        self.root.update()
        folder.focus_force()
        folder.event_generate("<KeyPress-space>")
        folder.event_generate("<KeyRelease-space>")
        self.root.update()
        self.assertTrue(enabled.get())
        self.assertEqual(calls[-1], True)
        self.root.withdraw()

    def test_checkbutton_images_are_shared_with_later_windows_and_reused(self):
        ui_theme.apply_theme(self.root, "light")
        images = self.root._pdf_checkbutton_images
        names = {str(image) for theme in images.values() for image in theme.values()}
        later = tk.Toplevel(self.root)
        later.withdraw()
        ttk.Checkbutton(later, text="已核对目标页").pack()
        ui_theme.apply_theme(later, "dark")
        later.destroy()
        ui_theme.apply_theme(self.root, "light")
        self.assertIs(self.root._pdf_checkbutton_images, images)
        self.assertTrue(names <= set(map(str, self.root.image_names())))

    def test_main_hint_review_and_selection_colors_have_readable_contrast(self):
        def luminance(color):
            rgb = [channel / 65535 for channel in self.rgb(color)]
            linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in rgb]
            return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))

        for name in ui_theme.PALETTES:
            p = ui_theme.apply_theme(self.root, name)
            for foreground, background in (("foreground", "background"), ("muted", "background"),
                                           ("context", "surface"), ("pending", "surface"),
                                           ("selected_foreground", "selected_background")):
                with self.subTest(theme=name, foreground=foreground):
                    low, high = sorted((luminance(p[foreground]), luminance(p[background])))
                    self.assertGreaterEqual((high + .05) / (low + .05), 4.5)


if __name__ == "__main__":
    unittest.main()
