"""Remember user-adjusted panes and columns without changing window geometry."""

from __future__ import annotations

import tkinter as tk


class PaneMemory:
    """Keep a manually chosen ratio for a two-pane horizontal ttk.Panedwindow.

    Zero leaves the application's original, content-driven layout untouched.
    Restoring a ratio never counts as dragging or moves keyboard focus.
    """

    def __init__(self, paned, ratio=0):
        self.paned = paned
        self._ratio = ratio if type(ratio) is int and (ratio == 0 or 10 <= ratio <= 90) else 0
        self._dragging = False
        self._drag_start = None
        self._natural_ratio = None
        self._reset_requested = False
        self._pending = None
        self._closed = False
        self._bindings = [
            (event, paned.bind(event, callback, add="+"))
            for event, callback in (
                ("<ButtonPress-1>", self._press),
                ("<ButtonRelease-1>", self._release),
                ("<Configure>", self._queue_restore),
                ("<Map>", self._queue_restore),
            )
        ]
        self._queue_restore()

    def _press(self, event):
        self._capture_natural_ratio()
        self._dragging = self.paned.identify(event.x, event.y) in (0, "0")
        self._drag_start = self.paned.sashpos(0) if self._dragging else None
        if self._dragging and self._pending is not None:
            self.paned.after_cancel(self._pending)
            self._pending = None

    def _release(self, _event):
        if not self._dragging:
            return
        self._dragging = False
        width = self.paned.winfo_width()
        if self.paned.winfo_viewable() and width > 1 and len(self.paned.panes()) == 2:
            position = self.paned.sashpos(0)
            if position != self._drag_start:
                ratio = round(100 * position / width)
                self._ratio = max(10, min(90, ratio))
                if self._ratio != ratio:
                    self._queue_restore()
        self._drag_start = None

    def _queue_restore(self, _event=None):
        if (not self._closed and not self._dragging and self._pending is None
                and (self._ratio or self._reset_requested or self._natural_ratio is None)):
            self._pending = self.paned.after_idle(self._restore)

    def _capture_natural_ratio(self):
        if self._natural_ratio is not None:
            return True
        width = self.paned.winfo_width()
        if self.paned.winfo_viewable() and width > 1 and len(self.paned.panes()) == 2:
            position = self.paned.sashpos(0)
            if 0 < position < width:
                # Capture the first real layout before applying a saved ratio.
                self._natural_ratio = position / width
                return True
        return False

    def _restore(self):
        self._pending = None
        if self._closed or self._dragging or not self.paned.winfo_viewable():
            return
        width = self.paned.winfo_width()
        if width > 1 and len(self.paned.panes()) == 2 and self._capture_natural_ratio():
            if self._reset_requested:
                target = round(width * self._natural_ratio)
                self._reset_requested = False
            elif self._ratio:
                target = round(width * self._ratio / 100)
            else:
                return
            if self.paned.sashpos(0) != target:
                self.paned.sashpos(0, target)

    def snapshot(self):
        return self._ratio

    def reset(self):
        """Forget manual sizing and restore this instance's first natural split."""
        if self._closed:
            return
        self._ratio = 0
        self._dragging = False
        self._drag_start = None
        self._reset_requested = True
        if self._pending is not None:
            self.paned.after_cancel(self._pending)
            self._pending = None
        self._queue_restore()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._pending is not None:
                self.paned.after_cancel(self._pending)
                self._pending = None
            for event, binding in self._bindings:
                self.paned.unbind(event, binding)
        except tk.TclError:
            # Parent-window destruction may precede the owner's cleanup.
            pass
        self._bindings.clear()


class ColumnMemory:
    """Restore known widths; record only a separator dragged by the user.

    Automatic stretching is deliberately not saved. Symbolic column IDs keep
    widths attached to the same data when a Treeview changes displaycolumns.
    """

    def __init__(self, tree, widths=None):
        self.tree = tree
        columns = ("#0", *tree.cget("columns"))
        self._default_widths = {name: tree.column(name, "width") for name in columns}
        self._widths = {
            name: width for name, width in (widths or {}).items()
            if name in columns and type(width) is int and 30 <= width <= 3000
        }
        self._dragged = None
        self._reset_requested = False
        self._pending = None
        self._closed = False
        self._bindings = [
            (event, tree.bind(event, callback, add="+"))
            for event, callback in (
                ("<ButtonPress-1>", self._press),
                ("<ButtonRelease-1>", self._release),
                ("<Map>", self._queue_restore),
            )
        ]
        self._queue_restore()

    def _press(self, event):
        self._dragged = None
        if self.tree.identify_region(event.x, event.y) != "separator":
            return
        displayed = self.tree.identify_column(event.x)
        column = "#0" if displayed == "#0" else str(self.tree.column(displayed, "id"))
        self._dragged = column, self.tree.column(column, "width")
        if self._pending is not None:
            self.tree.after_cancel(self._pending)
            self._pending = None

    def _release(self, _event):
        dragged, self._dragged = self._dragged, None
        if dragged is not None:
            column, original_width = dragged
            width = self.tree.column(column, "width")
            if width != original_width and 30 <= width <= 3000:
                self._widths[column] = width

    def _queue_restore(self, _event=None):
        if not self._closed and (self._widths or self._reset_requested) and self._pending is None:
            self._pending = self.tree.after_idle(self._restore)

    def _restore(self):
        self._pending = None
        if self._closed or self._dragged is not None or not self.tree.winfo_viewable():
            return
        widths = self._default_widths if self._reset_requested else self._widths
        for name, width in widths.items():
            self.tree.column(name, width=width)
        self._reset_requested = False

    def snapshot(self):
        return self._widths.copy()

    def reset(self):
        """Restore original widths without changing visibility or stretch rules."""
        if self._closed:
            return
        self._widths.clear()
        self._dragged = None
        self._reset_requested = True
        if self._pending is not None:
            self.tree.after_cancel(self._pending)
            self._pending = None
        self._queue_restore()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._pending is not None:
                self.tree.after_cancel(self._pending)
                self._pending = None
            for event, binding in self._bindings:
                self.tree.unbind(event, binding)
        except tk.TclError:
            pass
        self._bindings.clear()
