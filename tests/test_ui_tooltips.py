"""Delayed help stays local, passive and collectible after its control closes."""

import gc
import time
import tkinter as tk
from tkinter import ttk
import unittest
import weakref

import ui_theme


class TooltipTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("380x160+20000+20000")
        self.errors = []
        self.root.report_callback_exception = lambda *args, errors=self.errors: errors.append(args)
        self.button = ttk.Button(self.root, text="目录操作")
        self.button.pack()
        self.root.update()
        self.handles = []

    def tearDown(self):
        for handle in self.handles:
            handle.close()
        self.handles.clear()
        if self.root is not None:
            self.root.update_idletasks()
            self.root.destroy()
        self.root = self.button = None
        gc.collect()
        self.assertEqual(self.errors, [])

    def tooltip(self, **kwargs):
        handle = ui_theme.add_tooltip(self.button, "目录操作的简短说明。", **kwargs)
        self.handles.append(handle)
        return handle

    def wait_for(self, condition):
        end = time.monotonic() + 2
        while not condition() and time.monotonic() < end:
            self.root.update()
            time.sleep(.002)
        self.assertTrue(condition())

    def show(self, handle, event="<Enter>"):
        self.button.event_generate(event)
        self.wait_for(lambda: handle.tip is not None)

    def test_hover_and_keyboard_focus_show_delayed_help_without_grab_or_focus_change(self):
        handle = self.tooltip(delay=20)
        focused = self.root.focus_get()
        self.button.event_generate("<Enter>")
        timer = handle.pending
        self.assertIsNotNone(timer)
        self.assertIsNone(handle.tip)
        self.wait_for(lambda: handle.tip is not None)
        self.assertIsNone(handle.pending)
        self.assertIsNone(self.root.grab_current())
        self.assertEqual(self.root.focus_get(), focused)
        self.assertTrue(handle.tip.overrideredirect())
        self.button.event_generate("<Leave>")
        self.show(handle, "<FocusIn>")
        self.assertEqual(self.root.focus_get(), focused)
        self.assertIsNone(self.root.grab_current())

    def test_exit_click_keys_and_focus_loss_cancel_pending_and_visible_help(self):
        handle = self.tooltip(delay=20)
        self.button.focus_force()
        self.root.update()
        for event in ("<Leave>", "<ButtonPress-1>", "<KeyPress-Escape>", "<FocusOut>"):
            with self.subTest(event=event):
                self.button.event_generate("<Enter>")
                timer = handle.pending
                self.assertIsNotNone(timer)
                self.button.event_generate(event)
                self.assertIsNone(handle.pending)
                self.assertNotIn(timer, self.root.tk.call("after", "info"))
                self.assertIsNone(handle.tip)
                self.show(handle)
                self.button.event_generate(event)
                self.assertIsNone(handle.tip)
                self.assertIsNone(handle.pending)

    def test_hidden_control_and_owner_cancel_pending_and_visible_help(self):
        handle = self.tooltip(delay=20)
        self.button.event_generate("<Enter>")
        timer = handle.pending
        self.button.pack_forget()
        self.root.update()
        self.assertIsNone(handle.pending)
        self.assertNotIn(timer, self.root.tk.call("after", "info"))
        self.button.pack()
        self.root.update()
        self.show(handle)
        self.root.withdraw()
        self.root.update()
        self.assertIsNone(handle.tip)

    def test_destroyed_control_releases_all_callbacks_and_widget_reference(self):
        handle = self.tooltip(delay=20)
        self.show(handle)
        callbacks = [callback for _, callback in handle.bindings]
        self.button.event_generate("<Enter>")
        timer = handle.pending
        reference = weakref.ref(self.button)
        self.button.destroy()
        self.button = None
        self.root.update()
        gc.collect()
        self.assertIsNone(reference())
        self.assertIsNone(handle.widget)
        self.assertIsNone(handle.pending)
        self.assertIsNone(handle.tip)
        self.assertEqual(handle.bindings, [])
        self.assertNotIn(timer, self.root.tk.call("after", "info"))
        self.assertTrue(all(not self.root.tk.call("info", "commands", callback) for callback in callbacks))

    def test_manual_close_preserves_existing_bindings_and_allows_handle_collection(self):
        calls = []
        original = self.button.bind("<Enter>", lambda _event, calls=calls: calls.append("original"), add="+")
        handle = self.tooltip()
        reference = weakref.ref(handle)
        self.assertEqual(handle.delay, 600)
        handle.close()
        self.handles.clear()
        del handle
        gc.collect()
        self.assertIsNone(reference())
        self.button.event_generate("<Enter>")
        self.assertEqual(calls, ["original"])
        self.assertIn(original, self.button.bind("<Enter>"))

    def test_owner_destroy_releases_tooltip_during_pending_or_visible_help(self):
        for visible in (False, True):
            owner = tk.Toplevel(self.root)
            owner.geometry("380x160+20000+20000")
            button = ttk.Button(owner, text="草稿设置")
            button.pack()
            self.root.update()
            handle = ui_theme.add_tooltip(button, "草稿仅暂存到本机。", delay=20)
            self.handles.append(handle)
            button.event_generate("<Enter>")
            timer = handle.pending
            if visible:
                self.wait_for(lambda: handle.tip is not None)
            owner_reference, button_reference = weakref.ref(owner), weakref.ref(button)
            owner.destroy()
            self.root.update()
            del owner, button
            gc.collect()
            self.assertIsNone(owner_reference())
            self.assertIsNone(button_reference())
            self.assertIsNone(handle.widget)
            self.assertIsNone(handle.tip)
            self.assertIsNone(handle.pending)
            self.assertNotIn(timer, self.root.tk.call("after", "info"))

    def test_tooltip_uses_current_palette_and_preserves_an_external_theme(self):
        handle = self.tooltip(delay=20)
        style = ttk.Style(self.root)
        for name in ("light", "dark"):
            palette = ui_theme.apply_theme(self.root, name)
            self.root.update()
            self.show(handle)
            label = handle.tip.winfo_children()[0]
            self.assertEqual(self.root.winfo_rgb(label.cget("background")), self.root.winfo_rgb(palette["surface"]))
            self.assertEqual(self.root.winfo_rgb(label.cget("foreground")), self.root.winfo_rgb(palette["foreground"]))
            self.button.event_generate("<Leave>")
        style.theme_create("light", parent="clam")
        for name in ("clam", "light"):
            style.theme_use(name)
            self.root.update()
            expected = tk.Label(self.root)
            colors = expected.cget("background"), expected.cget("foreground")
            expected.destroy()
            self.show(handle)
            label = handle.tip.winfo_children()[0]
            self.assertEqual((label.cget("background"), label.cget("foreground")), colors)
            self.assertEqual(style.theme_use(), name)
            self.button.event_generate("<Leave>")

    def test_theme_changes_dismiss_old_color_help_and_do_not_restart_timers(self):
        ui_theme.apply_theme(self.root, "light")
        self.root.update()
        handle = self.tooltip(delay=20)
        self.show(handle)
        ui_theme.apply_theme(self.root, "dark")
        self.root.update()
        self.assertIsNone(handle.tip)
        self.assertIsNone(handle.pending)
        self.button.event_generate("<Enter>")
        timer = handle.pending
        ui_theme.apply_theme(self.root, "light")
        self.root.update()
        self.assertIsNone(handle.pending)
        self.assertNotIn(timer, self.root.tk.call("after", "info"))


if __name__ == "__main__":
    unittest.main()
