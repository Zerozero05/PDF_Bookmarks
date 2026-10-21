"""Reset layout preferences without resetting window, content or tree options."""

from tkinter import ttk
import unittest

import test_ui_layout as fixtures
from ui_layout import PaneMemory


class LayoutResetTests(unittest.TestCase):
    setUp = fixtures.LayoutMemoryTests.setUp
    tearDown = fixtures.LayoutMemoryTests.tearDown
    pane_memory = fixtures.LayoutMemoryTests.pane_memory
    column_memory = fixtures.LayoutMemoryTests.column_memory

    def test_reset_saved_split_restores_initial_ratio_at_current_window_width(self):
        natural = self.pane.sashpos(0) / self.pane.winfo_width()
        memory = self.pane_memory(75)
        self.root.update()
        self.assertAlmostEqual(self.pane.sashpos(0) / self.pane.winfo_width(), .75, delta=.01)
        self.root.geometry("1080x520+12000+12000")
        self.root.update()
        self.entry.focus_force()
        self.root.update()
        geometry, minimum = self.root.geometry(), self.root.minsize()
        memory.reset()
        self.assertEqual(memory.snapshot(), 0)
        self.root.update()
        self.assertAlmostEqual(self.pane.sashpos(0) / self.pane.winfo_width(), natural, delta=.01)
        self.assertEqual(self.root.geometry(), geometry)
        self.assertEqual(self.root.minsize(), minimum)
        self.assertIs(self.root.focus_get(), self.entry)

    def test_reset_before_pending_saved_restore_does_not_apply_stale_value(self):
        natural = self.pane.sashpos(0)
        memory = self.pane_memory(70)
        memory.reset()
        self.root.update()
        self.assertEqual(memory.snapshot(), 0)
        self.assertAlmostEqual(self.pane.sashpos(0), natural, delta=1)
        self.assertIsNone(memory._pending)

    def test_hidden_initialization_captures_natural_split_before_saved_restore(self):
        pairs = []
        for _ in range(2):
            pane = ttk.Panedwindow(self.other, orient="horizontal", height=120)
            pane.pack(fill="x")
            left, right = ttk.Frame(pane, width=240), ttk.Frame(pane, width=400)
            pane.add(left, weight=1)
            pane.add(right, weight=1)
            pairs.append(pane)
        pane, reference = pairs
        memory = PaneMemory(pane, 72)
        self.memories.append(memory)
        self.root.update()
        self.assertIsNone(memory._natural_ratio)
        self.tabs.select(self.other)
        self.root.update()
        natural = reference.sashpos(0) / reference.winfo_width()
        self.assertAlmostEqual(memory._natural_ratio, natural, delta=.01)
        self.assertAlmostEqual(pane.sashpos(0) / pane.winfo_width(), .72, delta=.01)
        memory.reset()
        self.root.update()
        self.assertAlmostEqual(pane.sashpos(0) / pane.winfo_width(), natural, delta=.01)
        self.assertEqual(memory.snapshot(), 0)

    def test_reset_hidden_page_is_applied_when_it_is_mapped_again(self):
        natural = self.pane.sashpos(0) / self.pane.winfo_width()
        memory = self.pane_memory(65)
        columns = self.column_memory({"title": 340, "hidden": 190})
        self.root.update()
        self.tabs.select(self.other)
        self.root.update()
        memory.reset()
        columns.reset()
        self.root.update()
        self.assertEqual(memory.snapshot(), 0)
        self.assertEqual(columns.snapshot(), {})
        self.tabs.select(self.page)
        self.root.update()
        self.assertAlmostEqual(self.pane.sashpos(0) / self.pane.winfo_width(), natural, delta=.01)
        self.assertEqual(self.tree.column("title", "width"), 220)
        self.assertEqual(self.tree.column("hidden", "width"), 100)

    def test_column_reset_keeps_selection_data_display_and_column_semantics(self):
        original_widths = {name: self.tree.column(name, "width")
                           for name in ("#0", "title", "pdf", "hidden")}
        columns = self.column_memory({"#0": 240, "title": 340, "hidden": 190})
        self.root.update()
        self.tree.configure(show="headings", displaycolumns=("pdf", "title"))
        self.tree.column("title", anchor="e")
        iid = self.tree.get_children()[0]
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.entry.focus_force()
        self.root.update()
        properties = {name: {key: self.tree.column(name, key) for key in ("stretch", "minwidth", "anchor", "id")}
                      for name in original_widths}
        item, geometry = self.tree.item(iid), self.root.geometry()
        columns.reset()
        self.root.update()
        self.assertEqual(columns.snapshot(), {})
        self.assertEqual({name: self.tree.column(name, "width") for name in original_widths}, original_widths)
        self.assertEqual({name: {key: self.tree.column(name, key) for key in properties[name]}
                          for name in properties}, properties)
        self.assertEqual(tuple(self.tree.cget("displaycolumns")), ("pdf", "title"))
        self.assertEqual(tuple(map(str, self.tree.cget("show"))), ("headings",))
        self.assertEqual(self.tree.item(iid), item)
        self.assertEqual(self.tree.selection(), (iid,))
        self.assertEqual(self.tree.focus(), iid)
        self.assertEqual(self.root.geometry(), geometry)
        self.assertIs(self.root.focus_get(), self.entry)

    def test_column_reset_before_pending_restore_wins_without_changing_stretch(self):
        columns = self.column_memory({"title": 340})
        self.tree.column("title", stretch=True)
        columns.reset()
        self.root.update()
        self.assertEqual(columns.snapshot(), {})
        self.assertTrue(self.tree.column("title", "stretch"))
        self.assertIsNone(columns._pending)

    def test_reset_after_close_is_safe_and_does_not_schedule_callbacks(self):
        memory = self.pane_memory(65)
        columns = self.column_memory({"title": 340})
        self.root.update()
        memory.close()
        columns.close()
        position, width = self.pane.sashpos(0), self.tree.column("title", "width")
        memory.reset()
        columns.reset()
        self.root.update()
        self.assertEqual(self.pane.sashpos(0), position)
        self.assertEqual(self.tree.column("title", "width"), width)
        self.assertIsNone(memory._pending)
        self.assertIsNone(columns._pending)


if __name__ == "__main__":
    unittest.main()
