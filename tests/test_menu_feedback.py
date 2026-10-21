"""Real Tk menu state, local hover feedback and combobox popup lifecycle.

Native Windows Menu.post enters TrackPopupMenu's modal loop. These checks use
Menu.invoke for command/disabled semantics; actual native popup painting and
physical clicks are checked separately in the normal application window.
"""

import gc
import tkinter as tk
from tkinter import ttk
import unittest
import weakref

import ui_theme
from window_controls import TitlebarPin


class MenuFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.geometry("640x400+12000+12000")
        self.root.maxsize(2000, 1400)
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        ui_theme.apply_theme(self.root, "dark")
        self.topmost = tk.BooleanVar(self.root, False)
        self.topmost.trace_add("write", self._apply_topmost)
        self.pin = TitlebarPin(self.root, self.topmost)
        self.entry = ttk.Entry(self.root)
        self.entry.insert(0, "Existing input stays unchanged")
        self.entry.pack(padx=20, pady=10)
        self.button = ttk.Button(self.root, text="预览")
        self.button.pack(padx=20, pady=10)
        self.menu_button = ttk.Menubutton(self.root, text="目录操作")
        self.menu_button.pack(padx=20, pady=10)
        self.calls = []
        self.menu = tk.Menu(self.menu_button, tearoff=False)
        self.menu.add_command(label="可用操作", command=lambda: self.calls.append("enabled"))
        self.menu.add_command(label="不可用操作", state="disabled",
                              command=lambda: self.calls.append("disabled"))
        self.menu_button.configure(menu=self.menu)
        self.choice = tk.StringVar(self.root, "章.节")
        self.combo = ttk.Combobox(self.root, state="readonly", textvariable=self.choice,
                                  values=("章.节", "每章节号", "保留识别编号"))
        self.combo.pack(padx=20, pady=10)
        ui_theme.refresh_theme_widgets(self.root)
        self.root.deiconify()
        self.root.update()

    def tearDown(self):
        reference = weakref.ref(self.root)
        self.root.tk.call("ttk::combobox::Unpost", str(self.combo))
        self.pin.close()
        self.root.destroy()
        self.pin = self.root = self.entry = self.button = self.menu_button = None
        self.menu = self.combo = self.choice = self.topmost = None
        gc.collect()
        self.assertIsNone(reference(), "Destroyed Tk interpreter retained by test callbacks")
        self.assertEqual(self.errors, [])

    def _apply_topmost(self, *_):
        self.root.attributes("-topmost", self.topmost.get())

    def rgb(self, color):
        return self.root.winfo_rgb(color)

    def assert_menu_colors(self, menu, palette):
        expected = ui_theme.menu_colors(menu, palette)
        if self.root.tk.call("tk", "windowingsystem") == "win32":
            self.assertEqual(expected["background"], "SystemMenu")
            self.assertEqual(expected["disabledforeground"], "SystemGrayText")
        else:
            self.assertEqual(expected["background"], palette["surface"])
            self.assertEqual(expected["disabledforeground"], palette["disabled"])
        for option, value in expected.items():
            self.assertEqual(self.rgb(menu.cget(option)), self.rgb(value), option)

    def popup(self):
        return str(self.root.tk.call("ttk::combobox::PopdownWindow", str(self.combo)))

    def popup_visible(self):
        return bool(int(self.root.tk.call("winfo", "viewable", self.popup())))

    def popup_key(self, key):
        listbox = self.popup() + ".f.l"
        self.root.tk.call("event", "generate", listbox, key)
        self.root.update()

    def click_combo(self):
        x, y = self.combo.winfo_width() - 5, self.combo.winfo_height() // 2
        self.combo.event_generate("<ButtonPress-1>", x=x, y=y)
        self.combo.event_generate("<ButtonRelease-1>", x=x, y=y)
        self.root.update()

    def test_three_themes_keep_native_menu_colors_and_real_disabled_semantics(self):
        geometry = self.root.geometry()
        for name in ui_theme.PALETTES:
            with self.subTest(theme=name):
                palette = ui_theme.apply_theme(self.root, name)
                self.assert_menu_colors(self.menu, palette)
                self.assertEqual(str(self.menu.entrycget("不可用操作", "state")), "disabled")
                self.menu.invoke("不可用操作")
                self.assertNotIn("disabled", self.calls)
                self.menu.invoke("可用操作")
                self.assertEqual(self.calls[-1], "enabled")
                self.assertEqual(self.root.geometry(), geometry)
                self.assertEqual(self.entry.get(), "Existing input stays unchanged")

    def test_later_menu_and_cascade_refresh_uses_active_theme_without_state_changes(self):
        for name in ui_theme.PALETTES:
            with self.subTest(theme=name):
                palette = ui_theme.apply_theme(self.root, name)
                later = tk.Menu(self.menu_button, tearoff=False)
                child = tk.Menu(later, tearoff=False)
                child.add_command(label="保留禁用", state="disabled")
                later.add_cascade(label="子菜单", menu=child)
                try:
                    ui_theme.refresh_theme_widgets(self.root)
                    self.assert_menu_colors(later, palette)
                    self.assert_menu_colors(child, palette)
                    self.assertEqual(str(child.entrycget(0, "state")), "disabled")
                    self.assertEqual(str(later.entrycget(0, "menu")), str(child))
                finally:
                    later.destroy()

    def test_hover_feedback_keeps_button_geometry_focus_and_disabled_state(self):
        self.root.focus_force()
        self.entry.focus_set()
        self.root.update()
        for name in ui_theme.PALETTES:
            palette = ui_theme.apply_theme(self.root, name)
            self.root.update()
            for widget, style_name in ((self.button, "TButton"), (self.menu_button, "TMenubutton")):
                with self.subTest(theme=name, control=style_name):
                    size = widget.winfo_width(), widget.winfo_height()
                    focus = self.root.focus_get()
                    style = ttk.Style(self.root)
                    widget.event_generate("<Enter>")
                    self.root.update()
                    self.assertTrue(widget.instate(("active",)))
                    self.assertEqual(self.rgb(style.lookup(style_name, "background", widget.state())),
                                     self.rgb(palette["hover"]))
                    self.assertEqual(self.rgb(style.lookup(style_name, "bordercolor", widget.state())),
                                     self.rgb(palette["accent"]))
                    widget.event_generate("<Leave>")
                    self.root.update()
                    self.assertFalse(widget.instate(("active",)))
                    widget.state(("disabled",))
                    widget.event_generate("<Enter>")
                    self.root.update()
                    self.assertTrue(widget.instate(("disabled",)))
                    self.assertEqual(self.rgb(style.lookup(style_name, "foreground", widget.state())),
                                     self.rgb(palette["disabled"]))
                    self.assertEqual(self.rgb(style.lookup(style_name, "bordercolor", widget.state())),
                                     self.rgb(palette["border"]))
                    self.assertEqual((widget.winfo_width(), widget.winfo_height()), size)
                    self.assertIs(self.root.focus_get(), focus)
                    widget.state(("!disabled", "!active"))

    def test_combobox_hover_feedback_does_not_change_value_focus_or_size(self):
        self.root.focus_force()
        self.entry.focus_set()
        self.root.update()
        for name in ui_theme.PALETTES:
            with self.subTest(theme=name):
                palette = ui_theme.apply_theme(self.root, name)
                self.root.update()
                style = ttk.Style(self.root)
                size = self.combo.winfo_width(), self.combo.winfo_height()
                focus = self.root.focus_get()
                x, y = self.combo.winfo_width() - 5, self.combo.winfo_height() // 2
                self.combo.event_generate("<Enter>", x=x, y=y)
                self.combo.event_generate("<Motion>", x=x, y=y)
                self.root.update()
                # Ttk's core Enter/Leave handler uses hover; unlike buttons,
                # Combobox has no Tcl binding that also sets active.
                self.assertTrue(self.combo.instate(("hover", "readonly")))
                self.assertEqual(self.rgb(style.lookup("TCombobox", "bordercolor", self.combo.state())),
                                 self.rgb(palette["accent"]))
                self.assertEqual(self.rgb(style.lookup("TCombobox", "arrowcolor", self.combo.state())),
                                 self.rgb(palette["accent"]))
                self.combo.event_generate("<Leave>")
                self.root.update()
                self.assertFalse(self.combo.instate(("hover",)))
                self.combo.state(("disabled",))
                self.combo.event_generate("<Enter>")
                self.root.update()
                self.assertEqual(self.rgb(style.lookup("TCombobox", "arrowcolor", self.combo.state())),
                                 self.rgb(palette["disabled"]))
                self.assertEqual(self.rgb(style.lookup("TCombobox", "bordercolor", self.combo.state())),
                                 self.rgb(palette["border"]))
                self.assertEqual(self.choice.get(), "章.节")
                self.assertEqual((self.combo.winfo_width(), self.combo.winfo_height()), size)
                self.assertIs(self.root.focus_get(), focus)
                self.combo.state(("!disabled", "!active"))

    def test_readonly_first_click_closes_and_reopens_in_both_topmost_states(self):
        geometry = self.root.geometry()
        for pinned in (False, True):
            self.topmost.set(pinned)
            self.root.update()
            for repeat in range(3):
                with self.subTest(topmost=pinned, repeat=repeat):
                    self.assertFalse(self.popup_visible())
                    self.click_combo()
                    self.assertTrue(self.popup_visible())
                    self.assertTrue(self.combo.instate(("pressed",)))
                    self.popup_key("<Escape>")
                    self.assertFalse(self.popup_visible())
                    self.assertFalse(self.combo.instate(("pressed",)))
                    self.assertEqual(self.choice.get(), "章.节")
                    self.assertEqual(bool(self.root.attributes("-topmost")), pinned)
                    self.assertEqual(self.root.geometry(), geometry)

    def test_readonly_keyboard_selection_and_escape_keep_original_behavior(self):
        self.topmost.set(True)
        self.root.focus_force()
        self.combo.focus_set()
        self.root.update()
        self.combo.event_generate("<Down>")
        self.root.update()
        self.assertTrue(self.popup_visible())
        self.popup_key("<Down>")
        self.popup_key("<Return>")
        self.assertFalse(self.popup_visible())
        self.assertEqual(self.choice.get(), "每章节号")
        self.combo.event_generate("<Down>")
        self.root.update()
        self.assertTrue(self.popup_visible())
        self.popup_key("<Down>")
        self.popup_key("<Escape>")
        self.assertFalse(self.popup_visible())
        self.assertEqual(self.choice.get(), "每章节号")
        self.assertTrue(self.root.attributes("-topmost"))

    def test_disabled_readonly_combobox_does_not_post_or_change_value(self):
        self.combo.state(("disabled",))
        self.click_combo()
        self.assertFalse(self.popup_visible())
        self.combo.event_generate("<Down>")
        self.root.update()
        self.assertFalse(self.popup_visible())
        self.assertEqual(self.choice.get(), "章.节")


if __name__ == "__main__":
    unittest.main()
