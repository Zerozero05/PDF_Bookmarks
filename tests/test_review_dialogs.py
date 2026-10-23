"""Real Tk review windows keep decisions explicit and bottom controls visible."""

from copy import deepcopy
from pathlib import Path
import tkinter as tk
import unittest

from bookmarks_core import BookmarkError
from review_dialogs import (show_issues, show_mapping_preview, show_recognition_diff,
                            show_title_editor)
from review_tools import diff_recognition
from toc_generation import Draft, DraftEntry
from ui_theme import apply_theme, apply_ui_scale


class ReviewDialogTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.close_root)
        apply_theme(self.root, "light")

    def close_root(self):
        self.root.update_idletasks()
        self.root.destroy()

    def draft(self, confirmed=False):
        return Draft(Path("D:/synthetic-review-dialog.pdf"), 30,
            [DraftEntry(1, "第一章 基础", 1, 2, "高", "识别证据", confirmed, 1, (.1, .1, .8, .15)),
             DraftEntry(2, "1.1 概念", 2, 3, "低", "识别证据", confirmed, 1, (.15, .2, .8, .25))],
            [1], {"offset": 1}, "测试", [])

    def test_issue_window_locates_selected_issue_without_changing_draft(self):
        current = self.draft()
        before, located = deepcopy(current), []
        window = show_issues(self.root, current, located.append)
        window.tree.selection_set("1")
        window.tree.event_generate("<<TreeviewSelect>>")
        self.root.update()
        window.locate_button.invoke()
        self.assertEqual(located, [1])
        self.assertFalse(window.winfo_exists())
        self.assertEqual(current, before)

    def test_global_issue_cannot_jump_to_nonexistent_item(self):
        current = self.draft()
        current.entries.clear()
        located = []
        window = show_issues(self.root, current, located.append)
        self.root.update()
        self.assertTrue(window.locate_button.instate(["disabled"]))
        window.locate_button.invoke()
        self.assertEqual(located, [])

    def test_nonmodal_issue_details_survive_removal_of_original_rows(self):
        current = self.draft()
        errors = []
        self.root.report_callback_exception = lambda *args: errors.append(args)
        window = show_issues(self.root, current, lambda index: False)
        current.entries.clear()
        window.tree.selection_set("1")
        window.tree.event_generate("<<TreeviewSelect>>")
        self.root.update()
        self.assertEqual(errors, [])
        self.assertIn("1.1 概念", window.detail.get("1.0", "end"))
        window.locate_button.invoke()
        self.assertTrue(window.winfo_exists())

    def test_read_only_mapping_preview_has_no_apply_control(self):
        current = self.draft(True)
        before = deepcopy(current)
        window = show_mapping_preview(self.root, current, {"offset": 2})
        self.assertIsNone(window.apply_button)
        self.assertEqual((window.preview.changed, window.preview.needs_review), (2, 2))
        window.close_button.invoke()
        self.assertEqual(current, before)

    def test_mapping_apply_passes_independent_mapping_only_after_click(self):
        current = self.draft(True)
        mapping, applied = {"offset": 2}, []
        window = show_mapping_preview(self.root, current, mapping, lambda value: applied.append(value) or False)
        self.assertEqual(applied, [])
        window.apply_button.invoke()
        self.assertEqual(applied, [mapping])
        self.assertIsNot(applied[0], mapping)
        self.assertTrue(window.winfo_exists())
        self.assertTrue(all(entry.confirmed for entry in current.entries))

    def test_invalid_mapping_is_rejected_before_opening_window(self):
        children = self.root.winfo_children()
        with self.assertRaises(BookmarkError):
            show_mapping_preview(self.root, self.draft(), {"offset": True})
        self.assertEqual(self.root.winfo_children(), children)

    def test_title_edit_requires_preview_and_explicit_apply(self):
        current = self.draft(True)
        before, changes = deepcopy(current), []
        window = show_title_editor(self.root, current, [1], lambda value: changes.extend(value) or False)
        self.assertTrue(window.apply_button.instate(["disabled"]))
        window.form_vars["find"].set("概念")
        window.form_vars["replace"].set("基本概念")
        window.preview_button.invoke()
        self.assertEqual(changes, [])
        self.assertFalse(window.apply_button.instate(["disabled"]))
        window.apply_button.invoke()
        self.assertEqual([(c.index, c.before, c.after) for c in changes], [(1, "1.1 概念", "1.1 基本概念")])
        self.assertEqual(current, before)
        window.form_vars["suffix"].set("补充")
        self.assertTrue(window.apply_button.instate(["disabled"]))

    def test_empty_result_is_visible_but_cannot_apply(self):
        current = self.draft()
        applied = []
        window = show_title_editor(self.root, current, [1], applied.append)
        window.form_vars["find"].set("1.1 概念")
        window.preview_button.invoke()
        self.assertEqual(window.changes[0].after, "")
        self.assertTrue(window.apply_button.instate(["disabled"]))
        self.assertIn("为空", window.status.get())
        self.assertEqual(applied, [])

    def test_stale_title_preview_does_not_apply_to_changed_row(self):
        current = self.draft()
        applied = []
        window = show_title_editor(self.root, current, [1], applied.append)
        window.form_vars["prefix"].set("新")
        window.preview_button.invoke()
        current.entries[1].title = "刚刚手工编辑"
        window.apply_button.invoke()
        self.assertEqual(applied, [])
        self.assertIn("已变化", window.status.get())

    def test_callback_failure_keeps_review_and_shows_inline_error(self):
        def fail(changes):
            raise BookmarkError("未完成编辑，请先修正目标页。")
        window = show_title_editor(self.root, self.draft(), [1], fail)
        window.form_vars["prefix"].set("新")
        window.preview_button.invoke()
        window.apply_button.invoke()
        self.assertTrue(window.winfo_exists())
        self.assertIn("目标页", window.status.get())

    def test_recognition_defaults_no_selection_and_protects_confirmed_rows(self):
        current = self.draft(True)
        candidate = deepcopy(current.entries[1])
        candidate.title = "1.1 修正"
        proposal = diff_recognition(current, [candidate], source_page=1)
        applied = []
        window = show_recognition_diff(self.root, current, proposal,
                                      lambda ids, overrides: applied.append((ids, overrides)) or False)
        self.assertEqual(window.tree.selection(), ())
        self.assertTrue(window.apply_button.instate(["disabled"]))
        window.tree.selection_set("0")
        window.tree.event_generate("<<TreeviewSelect>>")
        self.root.update()
        window.apply_button.invoke()
        self.assertEqual(applied, [])
        self.assertIn("保护", window.status.get())
        window.override_protected.set(True)
        window.apply_button.invoke()
        self.assertEqual(applied, [(("candidate:0",), ("candidate:0",))])
        self.assertEqual(current.entries[1].title, "1.1 概念")

    def test_missing_and_ambiguous_results_never_automatically_adopted(self):
        current = self.draft()
        candidate = deepcopy(current.entries[1])
        candidate.source_page = None
        proposal = diff_recognition(current, [candidate], source_page=1)
        applied = []
        window = show_recognition_diff(self.root, current, proposal, lambda *args: applied.append(args))
        window.tree.selection_set("0")
        window.tree.event_generate("<<TreeviewSelect>>")
        self.root.update()
        self.assertTrue(window.apply_button.instate(["disabled"]))
        self.assertEqual(applied, [])

    def test_footer_visible_at_minimum_size_in_every_theme_and_font_size(self):
        # Transient review windows follow their owner's visibility. Geometry
        # assertions need a mapped owner, as in the running application.
        self.root.geometry("900x700+20000+20000")
        self.root.deiconify()
        self.root.update()
        for theme in ("light", "dark", "eye_care"):
            apply_theme(self.root, theme)
            for scale in (100, 110, 125):
                apply_ui_scale(self.root, scale)
                current = self.draft()
                candidate = deepcopy(current.entries[1])
                candidate.title = "1.1 新概念"
                proposal = diff_recognition(current, [candidate], source_page=1)
                windows = [show_issues(self.root, current, lambda index: None),
                           show_mapping_preview(self.root, current, {"offset": 2}, lambda value: None),
                           show_title_editor(self.root, current, [1], lambda value: None),
                           show_recognition_diff(self.root, current, proposal, lambda *args: None)]
                for window in windows:
                    width, height = window.minsize()
                    window.geometry(f"{width}x{height}")
                    self.root.update()
                    for button in (window.close_button, window.apply_button,
                                   getattr(window, "preview_button", None), getattr(window, "locate_button", None)):
                        if button is None:
                            continue
                        with self.subTest(theme=theme, scale=scale, window=window.title(), button=button.cget("text")):
                            self.assertTrue(button.winfo_ismapped())
                            self.assertGreater(button.winfo_width(), 20)
                            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                                 window.winfo_rooty() + window.winfo_height())
                    window.destroy()


if __name__ == "__main__":
    unittest.main()
