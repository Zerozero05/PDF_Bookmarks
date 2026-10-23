"""Main window appearance scaling persists separately from read-only PDF zoom."""

from tkinter import font as tkfont
import unittest

import test_main_shortcuts_preview as fixtures
from gui_support import load_settings


class MainUIScaleTests(unittest.TestCase):
    setUp = fixtures.MainShortcutsPreviewTests.setUp
    tearDown = fixtures.MainShortcutsPreviewTests.tearDown
    pump = fixtures.MainShortcutsPreviewTests.pump
    load = fixtures.MainShortcutsPreviewTests.load

    def test_scale_menu_persists_and_does_not_change_pdf_zoom_geometry_or_checks(self):
        main = self.main
        ids = self.load()
        main._preview_scale = 1.5
        main.preview_zoom.set("150%")
        main.file_tree.selection_set(ids[:2])
        baseline_size = tkfont.nametofont("TkDefaultFont", root=self.root).cget("size")
        before = self.root.geometry(), main.file_tree.selection(), [item["checked"] for item in main.items.values()]
        for scale, label in ((125, "大字（125%）"), (110, "较大（110%）"), (100, "标准（100%）")):
            main.ui_scale_menu.invoke(label)
            self.root.update()
            self.assertEqual(main.ui_scale.get(), scale)
            self.assertEqual(load_settings(self.settings)["ui_scale"], scale)
            self.assertEqual(main._preview_scale, 1.5)
            self.assertEqual(main.preview_zoom.get(), "150%")
            self.assertEqual(self.root.geometry(), before[0])
            self.assertEqual(main.file_tree.selection(), before[1])
            self.assertEqual([item["checked"] for item in main.items.values()], before[2])
            self.assertEqual(tkfont.nametofont("TkDefaultFont", root=self.root).cget("size"), round(baseline_size * scale / 100))
            self.assertEqual(str(main.log.cget("font")), "TkTextFont")

    def test_larger_text_expanded_write_settings_fit_minimum_window(self):
        self.root.geometry("1000x760+10000+10000")
        self.pump(lambda: self.main.workspace_tabs.winfo_width() == 1000)
        self.main._toggle_write_options()
        self.main.ui_scale_menu.invoke("大字（125%）")
        self.root.update()
        for widget in self.main.write_options.winfo_children():
            if widget.winfo_manager():
                self.assertTrue(widget.winfo_ismapped(), str(widget))
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                     self.root.winfo_rootx() + self.root.winfo_width(), str(widget))
        self.assertTrue(self.main.write_button.winfo_ismapped())


if __name__ == "__main__":
    unittest.main()
