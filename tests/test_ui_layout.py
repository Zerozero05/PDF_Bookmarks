"""Real Tk resizing, tab remapping and separator-only layout persistence."""

import gc
import tkinter as tk
from tkinter import ttk
import unittest

from ui_layout import ColumnMemory, PaneMemory


class LayoutMemoryTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("820x460+12000+12000")
        self.root.maxsize(2000, 1400)
        ttk.Style(self.root).theme_use("clam")
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True)
        self.page = ttk.Frame(self.tabs)
        self.other = ttk.Frame(self.tabs)
        self.tabs.add(self.page, text="校对")
        self.tabs.add(self.other, text="另一页")
        self.pane = ttk.Panedwindow(self.page, orient="horizontal", height=120)
        self.pane.pack(fill="x")
        self.left, self.right = ttk.Frame(self.pane, width=240), ttk.Frame(self.pane, width=400)
        self.pane.add(self.left, weight=1)
        self.pane.add(self.right, weight=1)
        self.entry = ttk.Entry(self.page)
        self.entry.pack(fill="x")
        self.tree = ttk.Treeview(self.page, columns=("title", "pdf", "hidden"), show="tree headings")
        for name, width in (("#0", 160), ("title", 220), ("pdf", 90), ("hidden", 100)):
            self.tree.column(name, width=width, minwidth=40, stretch=False)
            self.tree.heading(name, text=name)
        self.tree.configure(displaycolumns=("title", "pdf"))
        self.tree.pack(fill="both", expand=True)
        self.tree.insert("", "end", text="第一章", values=("原标题", 13, "保持隐藏"))
        self.memories = []
        self.root.update()

    def tearDown(self):
        for memory in self.memories:
            memory.close()
        self.root.destroy()
        self.memories.clear()
        self.root = self.tabs = self.page = self.other = None
        self.pane = self.left = self.right = self.entry = self.tree = None
        gc.collect()
        self.assertEqual(self.errors, [])

    def pane_memory(self, ratio=0):
        memory = PaneMemory(self.pane, ratio)
        self.memories.append(memory)
        return memory

    def column_memory(self, widths=None):
        memory = ColumnMemory(self.tree, widths)
        self.memories.append(memory)
        return memory

    def test_natural_layout_is_not_saved_by_mapping_or_automatic_resize(self):
        before = self.pane.sashpos(0)
        pane_memory = self.pane_memory()
        column_memory = self.column_memory()
        self.root.update()
        self.assertEqual(self.pane.sashpos(0), before)
        self.root.geometry("1000x460+12000+12000")
        self.tree.column("title", stretch=True)
        self.root.update()
        self.tabs.select(self.other)
        self.root.update()
        self.tabs.select(self.page)
        self.root.update()
        self.assertEqual(pane_memory.snapshot(), 0)
        self.assertEqual(column_memory.snapshot(), {})

    def test_saved_ratio_restores_after_resize_and_tab_remap_without_focus_or_window_change(self):
        memory = self.pane_memory(38)
        self.entry.focus_force()
        self.root.update()
        self.assertAlmostEqual(self.pane.sashpos(0) / self.pane.winfo_width(), .38, delta=.01)
        self.root.geometry("1060x520+12000+12000")
        self.root.update()
        expected_geometry = self.root.geometry()
        self.assertAlmostEqual(self.pane.sashpos(0) / self.pane.winfo_width(), .38, delta=.01)
        self.assertIs(self.root.focus_get(), self.entry)
        self.tabs.select(self.other)
        self.root.update()
        self.pane.sashpos(0, 100)
        self.tabs.select(self.page)
        self.root.update()
        self.assertAlmostEqual(self.pane.sashpos(0) / self.pane.winfo_width(), .38, delta=.01)
        self.assertEqual(memory.snapshot(), 38)
        self.assertEqual(self.root.geometry(), expected_geometry)

    def test_only_actual_sash_drag_records_ratio_and_keeps_existing_bindings(self):
        seen = []
        existing = self.pane.bind("<ButtonRelease-1>", lambda _event: seen.append(True), add="+")
        memory = self.pane_memory()
        self.pane.event_generate("<ButtonPress-1>", x=20, y=20)
        self.pane.event_generate("<ButtonRelease-1>", x=20, y=20)
        self.root.update()
        self.assertEqual(memory.snapshot(), 0)
        x, y = self.pane.sashpos(0), 30
        self.pane.event_generate("<ButtonPress-1>", x=x, y=y)
        self.pane.event_generate("<ButtonRelease-1>", x=x, y=y)
        self.root.update()
        self.assertEqual(memory.snapshot(), 0)
        self.pane.event_generate("<ButtonPress-1>", x=x, y=y)
        self.pane.event_generate("<B1-Motion>", x=x + 85, y=y)
        self.pane.event_generate("<ButtonRelease-1>", x=x + 85, y=y)
        self.root.update()
        expected = round(self.pane.sashpos(0) * 100 / self.pane.winfo_width())
        self.assertEqual(memory.snapshot(), expected)
        self.assertNotEqual(memory.snapshot(), 0)
        memory.close()
        self.assertIn(existing, self.pane.bind("<ButtonRelease-1>"))
        self.assertEqual(len(seen), 3)

    def test_column_restore_preserves_tree_mode_hidden_columns_and_column_options(self):
        self.tree.column("title", stretch=True, anchor="e")
        properties = {key: self.tree.column("title", key) for key in ("stretch", "minwidth", "anchor", "id")}
        memory = self.column_memory({"#0": 200, "title": 320, "hidden": 180, "absent": 100})
        self.root.update()
        self.assertEqual(self.tree.column("#0", "width"), 200)
        self.assertEqual(self.tree.column("hidden", "width"), 180)
        self.assertEqual(tuple(self.tree.cget("displaycolumns")), ("title", "pdf"))
        self.assertEqual({key: self.tree.column("title", key) for key in properties}, properties)
        original = self.tree.item(self.tree.get_children()[0])
        self.tree.configure(show="headings", displaycolumns=("pdf", "title"))
        self.tabs.select(self.other)
        self.root.update()
        self.tabs.select(self.page)
        self.root.update()
        self.assertEqual(tuple(self.tree.cget("displaycolumns")), ("pdf", "title"))
        self.assertEqual(self.tree.item(self.tree.get_children()[0]), original)
        self.assertEqual(memory.snapshot(), {"#0": 200, "title": 320, "hidden": 180})

    def test_extreme_sash_drags_restore_visible_panes_when_released(self):
        memory = self.pane_memory()
        width, y = self.pane.winfo_width(), 30
        for destination, expected in ((-width, 10), (2 * width, 90)):
            with self.subTest(expected_ratio=expected):
                start = self.pane.sashpos(0)
                self.pane.event_generate("<ButtonPress-1>", x=start, y=y)
                self.pane.event_generate("<B1-Motion>", x=destination, y=y)
                self.pane.event_generate("<ButtonRelease-1>", x=destination, y=y)
                self.root.update()
                self.assertEqual(memory.snapshot(), expected)
                self.assertAlmostEqual(self.pane.sashpos(0) / width, expected / 100, delta=.01)
                for pane in (self.left, self.right):
                    self.assertTrue(pane.winfo_viewable())
                    self.assertGreater(pane.winfo_width(), 1)

    def test_only_dragged_symbolic_column_is_recorded_after_reordering(self):
        self.tree.configure(show="headings", displaycolumns=("pdf", "title"))
        memory = self.column_memory()
        self.root.update()
        separator = next(x for x in range(self.tree.winfo_width())
                         if self.tree.identify_region(x, 5) == "separator"
                         and self.tree.identify_column(x) == "#1")
        self.tree.event_generate("<ButtonPress-1>", x=separator, y=5)
        self.tree.event_generate("<ButtonRelease-1>", x=separator, y=5)
        self.root.update()
        self.assertEqual(memory.snapshot(), {})
        self.tree.event_generate("<ButtonPress-1>", x=separator, y=5)
        self.tree.event_generate("<B1-Motion>", x=separator + 35, y=5)
        self.tree.event_generate("<ButtonRelease-1>", x=separator + 35, y=5)
        self.root.update()
        self.assertEqual(memory.snapshot(), {"pdf": self.tree.column("pdf", "width")})
        snapshot = memory.snapshot()
        snapshot["pdf"] = 1000
        self.assertNotEqual(memory.snapshot(), snapshot)

    def test_close_cancels_pending_restore_and_unbinds_only_owned_callbacks(self):
        pane_memory = self.pane_memory(60)
        column_memory = self.column_memory({"title": 400})
        original_position = self.pane.sashpos(0)
        original_width = self.tree.column("title", "width")
        pane_memory.close()
        column_memory.close()
        self.root.update()
        self.assertEqual(self.pane.sashpos(0), original_position)
        self.assertEqual(self.tree.column("title", "width"), original_width)
        pane_memory.close()
        column_memory.close()
        self.assertIsNone(pane_memory._pending)
        self.assertIsNone(column_memory._pending)


if __name__ == "__main__":
    unittest.main()
