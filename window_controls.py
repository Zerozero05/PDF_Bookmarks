"""One window-level pin, beside the native Windows caption buttons.

Keep the system frame intact. A non-activating owned tool window holds only the
pin button; Windows still handles caption dragging, resizing and system buttons.
"""

import ctypes
from ctypes import wintypes
import sys
import tkinter as tk
from tkinter import ttk


class _TitlebarInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("title", wintypes.RECT),
                ("state", wintypes.DWORD * 6), ("rect", wintypes.RECT * 6)]


class _WindowsCaption:
    def __init__(self, root, popup):
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        signatures = {
            "GetAncestor": ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
            "GetWindowLongPtrW": ([wintypes.HWND, ctypes.c_int], ctypes.c_ssize_t),
            "SetWindowLongPtrW": ([wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t),
            "SendMessageW": ([wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], ctypes.c_ssize_t),
            "SetWindowPos": ([wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL),
            "IsWindowEnabled": ([wintypes.HWND], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result
        self.owner = self.api.GetAncestor(root.winfo_id(), 2)  # GA_ROOT: Tk's native wrapper.
        self.popup = self.api.GetAncestor(popup.winfo_id(), 2)
        if not self.owner or not self.popup:
            raise OSError("Native window handles are unavailable")
        # TOOLWINDOW excludes a second taskbar/Alt+Tab entry; NOACTIVATE keeps
        # the input focus in the current editor when the pin is clicked.
        style = self.api.GetWindowLongPtrW(self.popup, -20) | 0x08000080
        for field, value in ((-20, style), (-8, self.owner)):
            ctypes.set_last_error(0)
            self.api.SetWindowLongPtrW(self.popup, field, value)
            if ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())

    def bounds(self):
        info = _TitlebarInfo()
        info.size = ctypes.sizeof(info)
        self.api.SendMessageW(self.owner, 0x033F, 0, ctypes.addressof(info))  # WM_GETTITLEBARINFOEX
        button = info.rect[2]  # Minimize, in screen coordinates at the window's DPI.
        if info.state[2] & 0x18000 or button.right <= button.left or button.bottom <= button.top:
            return None
        return button.left, button.top, button.right - button.left, button.bottom - button.top

    def move(self, bounds):
        # NOZORDER | NOACTIVATE: neither steal focus nor raise unrelated windows.
        if not self.api.SetWindowPos(self.popup, None, *bounds, 0x14):
            raise ctypes.WinError(ctypes.get_last_error())

    def enabled(self):
        return bool(self.api.IsWindowEnabled(self.owner))

    def set_topmost(self, pinned):
        # Tk changes the owner's topmost band without promoting this native
        # owned popup. Promote the button without reordering its owner above
        # an already open native menu (NOOWNERZORDER | NOACTIVATE | NOMOVE | NOSIZE).
        if not self.api.SetWindowPos(self.popup, -1 if pinned else -2, 0, 0, 0, 0, 0x213):
            raise ctypes.WinError(ctypes.get_last_error())


class TitlebarPin:
    def __init__(self, root, variable):
        self.root, self.variable = root, variable
        self.popup = self.native = self.button = None
        self._bounds = None
        self._topmost_after = None
        self.closed = False
        self._bindings = []
        self.fallback_reason = None
        if sys.platform == "win32":
            try:
                self.popup = tk.Toplevel(root)
                self.popup.withdraw()
                self.popup.overrideredirect(True)
                # Tk creates the native wrapper only on the first map. Create
                # it invisibly before applying Win32 styles to that wrapper.
                # Do not use wm transient: an override-redirect transient is a
                # native CHILD, clipped to the owner's client area on Windows.
                self.popup.attributes("-toolwindow", True, "-alpha", 0)
                self.popup.deiconify()
                self.popup.update_idletasks()
                self.native = _WindowsCaption(root, self.popup)
                self.popup.withdraw()
                self.popup.attributes("-alpha", 1)
            except (AttributeError, OSError, tk.TclError) as error:
                self.fallback_reason = str(error)
                if self.popup is not None:
                    self.popup.destroy()
                self.popup = self.native = None
        self.button = ttk.Button(self.popup if self.popup is not None else root,
                                 width=8, takefocus=False, command=self._toggle)
        if self.popup is not None:
            self.button.pack(fill="both", expand=True)
        else:
            self.button.place(relx=1, x=-6, y=2, anchor="ne")
        self._trace = variable.trace_add("write", self._refresh)
        self._refresh()
        for sequence in ("<Configure>", "<Map>", "<Unmap>"):
            self._bindings.append((sequence, root.bind(sequence, self._position, add="+")))
        self._bindings.append(("<FocusIn>", root.bind("<FocusIn>", self._queue_topmost, add="+")))
        self._position()

    def _refresh(self, *_):
        pinned = self.variable.get()
        self.button.configure(text="取消置顶" if pinned else "置顶",
                              style="Accent.TButton" if pinned else "TButton")
        self._queue_topmost()

    def _queue_topmost(self, event=None):
        if self.closed or self.native is None or event is not None and event.widget is not self.root:
            return
        if self._topmost_after is not None:
            self.root.after_cancel(self._topmost_after)
        # Run after all variable traces/activation work: the owner's later
        # SetWindowPos can otherwise cover the button even in the same band.
        self._topmost_after = self.root.after_idle(self._sync_topmost)

    def _sync_topmost(self):
        self._topmost_after = None
        if not self.closed and self.native is not None:
            self.native.set_topmost(self.variable.get())

    def _toggle(self):
        # A native modal dialog disables its owner, but not the floating button.
        # Match the disabled owner instead of changing its state behind a dialog.
        if not self.closed and (self.native is None or self.native.enabled()):
            self.variable.set(not self.variable.get())

    def _position(self, event=None):
        if self.closed or self.native is None or event is not None and event.widget is not self.root:
            return
        if self.root.state() in ("withdrawn", "iconic"):
            self.popup.withdraw()
            self._bounds = None
            return
        bounds = self.native.bounds()
        if bounds is None:
            self.popup.withdraw()
            self._bounds = None
            return
        left, top, width, height = bounds
        width = max(width, self.button.winfo_reqwidth())
        bounds = (left - width, top, width, height)
        if bounds == self._bounds and self.popup.state() != "withdrawn":
            return
        self.popup.geometry(f"{width}x{height}")
        if self.popup.state() == "withdrawn":
            self.popup.deiconify()
        self.native.move(bounds)
        self._bounds = bounds

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self._topmost_after is not None:
            self.root.after_cancel(self._topmost_after)
            self._topmost_after = None
        self.variable.trace_remove("write", self._trace)
        for sequence, callback in self._bindings:
            self.root.unbind(sequence, callback)
        self._bindings.clear()
        if self.popup is not None:
            self.popup.destroy()
        else:
            self.button.destroy()
