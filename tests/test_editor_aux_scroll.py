"""Small-window auxiliary scrolling keeps directory and PDF review usable."""

from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
from tkinter import ttk
import unittest

import test_workspace_tabs as fixtures
from toc_generation import Draft, DraftEntry
from ui_theme import PALETTES, apply_theme, apply_ui_scale


class EditorAuxScrollTests(unittest.TestCase):
    cleanup = fixtures.WorkspaceTabTests.cleanup
    spin = fixtures.WorkspaceTabTests.spin

    def setUp(self):
        fixtures.WorkspaceTabTests.setUp(self)
        self.root.maxsize(2200, 1600)
        self.root.geometry("1000x760+20000+20000")
        self.root.deiconify()
        self.main._open_editor()
        self.editor = self.main.editor
        self.editor.auto_save.set(False)
        self.editor.draft = Draft(self.pdf, 4, [
            DraftEntry(1, "第一章 基础", 1, 1, "高", "已核对章首", True),
            *[DraftEntry(2, f"1.{index} 基本概念", 2, 2, "低", "待核对", False,
                         1, (.08, .07, .38, .18)) for index in range(1, 40)],
        ], [1], {"offset": 0}, "合成目录", [])
        self.editor._load_mapping()
        self.editor._refresh(selected=1)
        self.spin(lambda: not self.editor.busy and self.editor._photo is not None)
        self.settle()

    def settle(self):
        # Complete the existing coalesced notebook-layout callback, rather
        # than treating one update_idletasks as a completed resize.
        self.spin(lambda: self.main.workspace_tabs.winfo_width() == self.root.winfo_width()
                  and self.main.workspace_tabs.winfo_height() == self.root.winfo_height())
        for _ in range(3):
            self.root.update()
        self.root.update_idletasks()

    @staticmethod
    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from EditorAuxScrollTests.descendants(child)

    def assert_inside_root(self, widget):
        self.assertTrue(widget.winfo_ismapped(), str(widget))
        x = widget.winfo_rootx() - self.root.winfo_rootx()
        y = widget.winfo_rooty() - self.root.winfo_rooty()
        self.assertGreaterEqual(x, 0, str(widget))
        self.assertGreaterEqual(y, 0, str(widget))
        self.assertLessEqual(x + widget.winfo_width(), self.root.winfo_width(), str(widget))
        self.assertLessEqual(y + widget.winfo_height(), self.root.winfo_height(), str(widget))

    def expanded(self):
        self.editor.source_compare.set(True)
        self.editor._update_source_crop()
        self.spin(lambda: self.editor._source_photo is not None)
        self.assertGreater(self.editor._source_photo.height(), 100)
        self.editor.advanced_open.set(True)
        self.editor._toggle_advanced()
        if not self.main.write_options.winfo_manager():
            self.main._toggle_write_options()
        self.settle()

    def assert_directory_has_three_rows(self):
        tree = self.editor.tree
        tree.see("0")
        self.root.update_idletasks()
        for iid in ("0", "1", "2"):
            box = tree.bbox(iid)
            self.assertTrue(box, f"目录项 {iid} 无可视行，树高 {tree.winfo_height()}")
            self.assertGreaterEqual(box[1], 0)
            self.assertLessEqual(box[1] + box[3], tree.winfo_height(),
                                 f"目录项 {iid} 被截断，树高 {tree.winfo_height()}")

    def assert_edit_widget_visible(self, widget):
        self.assertTrue(widget.winfo_ismapped(), str(widget))
        top = widget.winfo_rooty() - self.editor._edit_scroll.winfo_rooty()
        self.assertGreaterEqual(top, 0, str(widget))
        self.assertLessEqual(top + widget.winfo_height(), self.editor._edit_scroll.winfo_height(), str(widget))

    def test_default_and_expanded_minimum_geometry_all_themes_and_text_scales(self):
        before = deepcopy(asdict(self.editor.draft))
        selection = self.editor.tree.selection()
        original_geometry = self.root.geometry()
        for expanded in (False, True):
            if expanded:
                self.expanded()
            for scale in (100, 110, 125):
                apply_ui_scale(self.root, scale)
                for theme in PALETTES:
                    apply_theme(self.root, theme)
                    for page_name, page in (("main", self.main.main_page), ("editor", self.main.editor_page)):
                        with self.subTest(expanded=expanded, scale=scale, theme=theme, page=page_name):
                            self.main.workspace_tabs.select(page)
                            self.settle()
                            self.assertEqual(self.root.geometry(), original_geometry)
                            self.assertEqual(asdict(self.editor.draft), before)
                            self.assertEqual(self.editor.tree.selection(), selection)
                            if page_name == "main":
                                self.assert_inside_root(self.main.preview_button)
                                self.assert_inside_root(self.main.write_button)
                                if expanded:
                                    for widget in self.descendants(self.main.write_options):
                                        if widget.winfo_manager() and widget.winfo_class() in (
                                                "TEntry", "TButton", "TCombobox", "TCheckbutton"):
                                            self.assert_inside_root(widget)
                                continue
                            self.assert_directory_has_three_rows()
                            self.assertGreaterEqual(self.editor.canvas.winfo_height(), 75)
                            for widget in self.editor._footer.winfo_children():
                                self.assert_inside_root(widget)
                            for widget in self.editor._field_widgets.values():
                                widget.event_generate("<FocusIn>")
                                self.root.update_idletasks()
                                self.assert_edit_widget_visible(widget)
                            for widget in self.descendants(self.editor._edit_inner):
                                if str(widget).startswith(str(self.editor.mapping_tabs)):
                                    continue
                                if widget.winfo_class() in ("TButton", "TMenubutton", "TCheckbutton"):
                                    widget.event_generate("<FocusIn>")
                                    self.root.update_idletasks()
                                    self.assert_edit_widget_visible(widget)
                            self.editor._edit_scroll.yview_moveto(0)
                            if expanded:
                                self.assertTrue(self.editor._edit_scrollbar.winfo_ismapped())
                                self.assert_inside_root(self.editor._edit_scrollbar)
                                self.assertTrue(self.editor._source_photo)
                                self.assertTrue(self.editor.source_crop_frame.winfo_ismapped())
                                for tab in self.editor.mapping_tabs.tabs():
                                    self.editor.mapping_tabs.select(tab)
                                    self.settle()
                                    frame = self.editor.window.nametowidget(tab)
                                    for widget in self.descendants(frame):
                                        if isinstance(widget, ttk.Button):
                                            widget.event_generate("<FocusIn>")
                                            self.root.update()
                                            self.assert_edit_widget_visible(widget)
                                            self.assert_inside_root(widget)

    def test_aux_wheel_is_local_and_does_not_zoom_pdf_or_change_selection(self):
        apply_ui_scale(self.root, 125)
        self.expanded()
        before = deepcopy(asdict(self.editor.draft))
        selection = self.editor.tree.selection()
        self.editor._edit_scroll.yview_moveto(0)
        original = self.editor._edit_scroll.yview()
        pdf_view = self.editor.canvas.yview()
        zoom = self.editor._preview_scale
        self.editor._edit_inner.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(self.editor._edit_scroll.yview()[0], original[0])
        self.assertEqual(self.editor.canvas.yview(), pdf_view)
        self.assertEqual(self.editor._preview_scale, zoom)
        scrolled = self.editor._edit_scroll.yview()
        self.editor._edit_inner.event_generate("<MouseWheel>", delta=-120, state=0x0004)
        self.root.update()
        self.assertEqual(self.editor._edit_scroll.yview(), scrolled)
        self.assertEqual(self.editor._preview_scale, zoom)
        self.assertEqual(self.editor.tree.selection(), selection)
        self.assertEqual(asdict(self.editor.draft), before)

    def test_tab_switch_remaps_aux_window_and_preserves_fields_and_selection(self):
        before = deepcopy(asdict(self.editor.draft))
        fields = [variable.get() for variable in (self.editor.level, self.editor.title,
                                                  self.editor.printed, self.editor.target)]
        selection = self.editor.tree.selection()
        geometry = self.root.geometry()
        for _ in range(3):
            self.main.workspace_tabs.select(self.main.main_page)
            self.settle()
            self.main.workspace_tabs.select(self.main.editor_page)
            self.settle()
            self.assertTrue(self.editor._edit_inner.winfo_ismapped())
            for widget in self.editor._field_widgets.values():
                self.assertTrue(widget.winfo_ismapped(), str(widget))
            self.assertEqual([variable.get() for variable in (self.editor.level, self.editor.title,
                                                               self.editor.printed, self.editor.target)], fields)
            self.assertEqual(self.editor.tree.selection(), selection)
            self.assertEqual(asdict(self.editor.draft), before)
            self.assertEqual(self.root.geometry(), geometry)

    def test_segment_text_wheel_keeps_native_scroll_inside_auxiliary_view(self):
        apply_ui_scale(self.root, 125)
        self.expanded()
        self.editor.mapping_tabs.select(1)
        self.settle()
        segments = self.editor.segments
        original = "\n".join(f"{number},{number},{number}" for number in range(1, 31))
        segments.delete("1.0", "end")
        segments.insert("1.0", original)
        segments.event_generate("<FocusIn>")
        self.root.update()
        segments.yview_moveto(0)
        self.root.update_idletasks()
        before = deepcopy(asdict(self.editor.draft))
        selection = self.editor.tree.selection()
        inner_view = segments.yview()
        outer_view = self.editor._edit_scroll.yview()
        pdf_view = self.editor.canvas.yview()
        zoom = self.editor._preview_scale
        self.assertLess(inner_view[1], 1)
        segments.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(segments.yview()[0], inner_view[0])
        self.assertEqual(self.editor._edit_scroll.yview(), outer_view)
        self.assertEqual(segments.get("1.0", "end-1c"), original)
        segments.event_generate("<MouseWheel>", delta=-120, state=0x0004)
        self.root.update()
        self.assertEqual(self.editor._edit_scroll.yview(), outer_view)
        self.assertEqual(self.editor._preview_scale, zoom)
        self.assertEqual(self.editor.canvas.yview(), pdf_view)
        self.assertEqual(self.editor.tree.selection(), selection)
        self.assertEqual(asdict(self.editor.draft), before)
        # With no inner overflow, scrolling can still reveal the surrounding
        # mapping controls instead of trapping the wheel over an empty Text.
        segments.delete("1.0", "end")
        segments.insert("1.0", "1,4,1")
        segments.yview_moveto(0)
        self.root.update_idletasks()
        self.assertEqual(segments.yview(), (0.0, 1.0))
        before_outer = self.editor._edit_scroll.yview()
        segments.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(self.editor._edit_scroll.yview()[0], before_outer[0])
        self.assertEqual(self.editor._preview_scale, zoom)

    def test_tab_focus_path_brings_hidden_fields_and_actions_into_view(self):
        apply_ui_scale(self.root, 125)
        self.expanded()
        before = deepcopy(asdict(self.editor.draft))
        self.editor._edit_scroll.yview_moveto(0)
        target = self.editor._field_widgets[str(self.editor.target)]
        self.assertGreater(target.winfo_rooty() + target.winfo_height(),
                           self.editor._edit_scroll.winfo_rooty() + self.editor._edit_scroll.winfo_height())
        path = str(self.editor._title_entry)
        visited = []
        for _ in range(10):
            path = self.root.tk.call("tk_focusNext", path)
            widget = self.root.nametowidget(path)
            visited.append(widget)
            if str(widget).startswith(str(self.editor._edit_inner)):
                widget.event_generate("<FocusIn>")
                self.root.update_idletasks()
                self.assert_edit_widget_visible(widget)
        self.assertIn(target, visited)
        self.assertTrue(any(widget.winfo_class() == "TMenubutton" for widget in visited))
        self.assertEqual(asdict(self.editor.draft), before)

    def test_large_window_restores_all_aux_content_without_scroll(self):
        apply_ui_scale(self.root, 125)
        self.expanded()
        self.root.geometry("1600x1300+20000+20000")
        self.settle()
        self.assertGreaterEqual(self.editor._edit_scroll.winfo_height(), self.editor._edit_inner.winfo_reqheight())
        self.assertFalse(self.editor._edit_scrollbar.winfo_ismapped())
        self.editor._edit_scroll.yview_moveto(0)
        before = self.editor._edit_scroll.yview()
        result = self.editor._edit_aux_wheel(SimpleNamespace(delta=-120, num=None, state=0))
        self.root.update()
        self.assertIsNone(result)
        self.assertEqual(self.editor._edit_scroll.yview(), before)
        self.assert_directory_has_three_rows()

    def test_mapping_preview_apply_and_undo_preserve_the_original_transaction(self):
        apply_ui_scale(self.root, 125)
        self.expanded()
        before = deepcopy(asdict(self.editor.draft))
        selection = self.editor.tree.selection()
        history = len(self.editor.history._states)
        self.editor.offset.set("1")
        window = self.editor.preview_mapping()
        self.assertEqual(asdict(self.editor.draft), before)
        self.assertEqual(self.editor.tree.selection(), selection)
        self.assertEqual(len(self.editor.history._states), history)
        self.assertEqual(window.preview.needs_review, 1)
        window.destroy()
        self.editor.apply_offset()
        self.assertEqual(self.editor.draft.mapping, {"offset": 1})
        self.assertTrue(all(not entry.confirmed for entry in self.editor.draft.entries))
        self.assertEqual(self.editor.tree.selection(), selection)
        self.assertEqual(len(self.editor.history._states), history + 1)
        self.editor.undo()
        self.assertEqual(asdict(self.editor.draft), before)
        self.assertEqual(self.editor.tree.selection(), selection)
        geometry = self.root.geometry()
        self.main.workspace_tabs.select(self.main.main_page)
        self.root.update()
        self.main.workspace_tabs.select(self.main.editor_page)
        self.root.update()
        self.assertEqual(self.root.geometry(), geometry)


if __name__ == "__main__":
    unittest.main()
