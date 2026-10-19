"""Native caption integration without changing the system frame or editor focus."""

import ctypes
import sys
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ui_theme import apply_theme
from window_controls import TitlebarPin


class TitlebarPinTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.geometry("1000x760+100+80")
        self.root.maxsize(2000, 1400)
        apply_theme(self.root, "light")
        self.value = tk.BooleanVar(self.root, False)
        self.value.trace_add("write", lambda *_: self.root.attributes("-topmost", self.value.get()))
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.pin = TitlebarPin(self.root, self.value)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.pin.close()
        self.root.destroy()
        self.assertEqual(self.errors, [])

    def show(self):
        self.root.deiconify()
        self.root.update()

    def test_one_button_toggles_and_distinguishes_both_states_in_both_themes(self):
        self.show()
        for theme in ("light", "dark"):
            apply_theme(self.root, theme)
            for enabled in (True, False):
                geometry, state = self.root.geometry(), self.root.state()
                self.pin.button.invoke()
                self.root.update()
                self.assertEqual(self.value.get(), enabled)
                self.assertEqual(bool(self.root.attributes("-topmost")), enabled)
                self.assertEqual(self.pin.button.cget("text"), "取消置顶" if enabled else "置顶")
                self.assertEqual((self.root.geometry(), self.root.state()), (geometry, state))

    @unittest.skipUnless(sys.platform == "win32", "Native Windows caption")
    def test_native_owner_styles_and_button_bounds_preserve_the_system_frame(self):
        self.show()
        native = self.pin.native
        self.assertIsNotNone(native, self.pin.fallback_reason)
        style = native.api.GetWindowLongPtrW(native.owner, -16)
        extended = native.api.GetWindowLongPtrW(native.popup, -20)
        self.assertEqual(extended & 0x08000080, 0x08000080)
        self.assertFalse(extended & 0x00040000)  # No APPWINDOW/taskbar button.
        self.assertEqual(native.api.GetWindowLongPtrW(native.popup, -8), native.owner)
        popup_style = native.api.GetWindowLongPtrW(native.popup, -16)
        self.assertFalse(popup_style & 0x40000000)  # Not a clipped WS_CHILD.
        self.assertTrue(popup_style & 0x80000000)  # Owned WS_POPUP outside the client area.
        self.assertTrue(style & 0x00C00000)  # Original WS_CAPTION.
        self.assertTrue(style & 0x00040000)  # Original WS_THICKFRAME.
        self.assertTrue(style & 0x00020000)  # Original WS_MINIMIZEBOX.
        self.assertTrue(style & 0x00010000)  # Original WS_MAXIMIZEBOX.
        for geometry in ("1000x760+100+80", "1240x900+180+110", "1000x760-20+80"):
            self.root.geometry(geometry)
            self.root.update()
            left, top, _, height = native.bounds()
            x, y, width, actual_height = self.pin._bounds
            self.assertEqual((x + width, y, actual_height), (left, top, height))
            actual = ctypes.wintypes.RECT()
            native.api.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]
            self.assertTrue(native.api.GetWindowRect(native.popup, ctypes.byref(actual)))
            self.assertEqual((actual.left, actual.top, actual.right, actual.bottom),
                             (x, y, x + width, y + height))
            self.assertEqual(native.api.GetWindowLongPtrW(native.owner, -16), style)

    @unittest.skipUnless(sys.platform == "win32", "Native Windows caption")
    def test_first_native_wrapper_creation_does_not_steal_existing_input_focus(self):
        self.pin.close()
        field = ttk.Entry(self.root)
        field.pack()
        self.show()
        field.focus_force()
        self.root.update()
        self.pin = TitlebarPin(self.root, self.value)
        self.root.update()
        self.assertIs(self.root.focus_get(), field)
        self.assertIsNotNone(self.pin.native, self.pin.fallback_reason)
        self.assertTrue(self.pin.popup.winfo_ismapped())

    @unittest.skipUnless(sys.platform == "win32", "Native Windows caption")
    def test_native_pin_keeps_editor_focus_and_follows_minimize_restore_and_hide(self):
        field = ttk.Entry(self.root)
        field.pack()
        self.show()
        field.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), field)
        for operation in (self.pin.button.invoke, lambda: self.root.geometry("1100x800+120+90")):
            operation()
            self.root.update()
            self.assertIs(self.root.focus_get(), field)
        self.root.iconify()
        self.root.update()
        self.assertEqual(self.pin.popup.state(), "withdrawn")
        self.root.deiconify()
        self.root.update()
        self.assertEqual(self.pin.popup.state(), "normal")
        self.root.state("zoomed")
        self.root.update()
        self.assertEqual(self.pin.popup.state(), "normal")
        self.assertEqual(self.pin._bounds[0] + self.pin._bounds[2], self.pin.native.bounds()[0])
        self.root.state("normal")
        self.root.withdraw()
        self.root.update()
        self.assertEqual(self.pin.popup.state(), "withdrawn")

    @unittest.skipUnless(sys.platform == "win32", "Native Windows caption")
    def test_unrelated_configure_and_unchanged_geometry_do_not_repeat_native_layout(self):
        self.show()
        with patch.object(self.pin.native, "move", wraps=self.pin.native.move) as move:
            self.pin._position(SimpleNamespace(widget=self.pin.button))
            for _ in range(10):
                self.pin._position(SimpleNamespace(widget=self.root))
            move.assert_not_called()

    @unittest.skipUnless(sys.platform == "win32", "Native Windows caption")
    def test_disabled_modal_owner_cannot_be_pinned_through_the_caption_button(self):
        self.show()
        native = self.pin.native
        native.api.EnableWindow.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.BOOL]
        native.api.EnableWindow(native.owner, False)
        try:
            self.pin.button.invoke()
            self.assertFalse(self.value.get())
        finally:
            native.api.EnableWindow(native.owner, True)
        self.pin.button.invoke()
        self.assertTrue(self.value.get())

    @unittest.skipUnless(sys.platform == "win32", "Native Windows caption")
    def test_pin_stays_in_the_owners_topmost_group_after_each_toggle(self):
        self.show()
        for enabled in (True, False, True, False):
            self.root.focus_force()
            self.root.update()
            self.pin.button.invoke()
            self.root.update()
            native = self.pin.native
            owner_topmost = bool(native.api.GetWindowLongPtrW(native.owner, -20) & 0x8)
            pin_topmost = bool(native.api.GetWindowLongPtrW(native.popup, -20) & 0x8)
            self.assertEqual(owner_topmost, enabled)
            self.assertEqual(pin_topmost, enabled,
                             "置顶后按钮留在普通窗口层，被主窗口遮住，无法再点击取消。")
            native.api.WindowFromPoint.argtypes = [ctypes.wintypes.POINT]
            native.api.WindowFromPoint.restype = ctypes.wintypes.HWND
            x, y, width, height = self.pin._bounds
            hit = native.api.WindowFromPoint(ctypes.wintypes.POINT(x + width // 2, y + height // 2))
            self.assertEqual(native.api.GetAncestor(hit, 2), native.popup,
                             "按钮中心须始终命中按钮自身，不能落到主窗口标题栏。")

    def test_close_releases_callbacks_and_owned_button_without_destroying_root(self):
        self.show()
        popup = self.pin.popup
        self.value.set(True)
        pending_sync = self.pin._topmost_after
        self.pin.close()
        self.pin.close()
        self.assertEqual(self.pin._bindings, [])
        self.assertNotIn(self.pin._trace, str(self.value.trace_info()))
        if pending_sync is not None:
            self.assertNotIn(pending_sync, self.root.tk.call("after", "info"))
        self.assertFalse(self.pin.button.winfo_exists())
        if popup is not None:
            self.assertFalse(popup.winfo_exists())
        self.value.set(True)
        self.root.geometry("1100x800")
        self.root.update()
        self.assertTrue(self.root.winfo_exists())

    def test_unavailable_native_setup_preserves_one_global_button(self):
        self.pin.close()
        with patch("window_controls._WindowsCaption", side_effect=OSError("synthetic unavailable")):
            self.pin = TitlebarPin(self.root, self.value)
        self.show()
        self.assertIsNone(self.pin.popup)
        self.assertIs(self.pin.button.master, self.root)
        self.pin.button.invoke()
        self.root.update()
        self.assertTrue(self.value.get())


if __name__ == "__main__":
    unittest.main()
