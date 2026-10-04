"""Regressions for review state, fast edits, batch hierarchy and modeless saving."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pymupdf
from tkinterdnd2 import TkinterDnD

import toc_editor
from toc_generation import Draft, DraftEntry


class FastEditorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="zotero-fast-editor-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "中文 图书.pdf"
        with pymupdf.open() as document:
            for _ in range(5):
                document.new_page()
            document.save(self.pdf)
        self.original = self.pdf.read_bytes()
        self.root = TkinterDnD.Tk()
        self.root.geometry("1100x860+32000+32000")
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.errors = []
        self.error_patch = patch.object(toc_editor.messagebox, "showerror",
                                       side_effect=lambda title, message, **kw: self.errors.append(message))
        self.error_patch.start()
        self.settings_callback = Mock()
        self.editor = toc_editor.open_editor(self.root, self.executor, self.pdf,
                                            on_settings_changed=self.settings_callback)
        self.editor.window.geometry("1240x900+32000+32000")
        self.root.update_idletasks()
        self.load()

    def tearDown(self):
        self.editor.close()
        self.executor.shutdown(wait=True)
        self.root.update_idletasks()
        self.root.destroy()
        self.error_patch.stop()
        self.assertEqual(self.pdf.read_bytes(), self.original)
        self.temporary.cleanup()

    def load(self, levels=(1, 1, 1), confirmed=False):
        self.editor.draft = Draft(self.pdf, 5, [DraftEntry(level, f"标题 {index}", index + 1,
                                  index + 1, "高", "请核对", confirmed)
                                  for index, level in enumerate(levels)],
                                 [1], {"offset": 0}, "测试", [])
        self.editor._load_mapping()
        self.editor._refresh()

    def spin(self, condition, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("编辑器操作未在时限内完成。")

    def choose(self, *indices):
        self.editor.tree.selection_set(*(str(index) for index in indices))
        self.editor.tree.focus(str(indices[0]))
        self.editor._selected()

    def test_queued_duplicate_selection_does_not_reset_checked_confirmation(self):
        # _refresh queued a select notification before the user toggled the box.
        self.editor.confirmed.set(True)
        self.root.update()
        self.assertTrue(self.editor.confirmed.get())
        self.editor.update_entry()
        self.root.update()
        self.assertTrue(self.editor.draft.entries[0].confirmed)
        self.assertEqual(self.editor.tree.set("0", "confirmed"), "已确认")

    def test_checkbox_command_commits_confirmation_immediately(self):
        checkbox = next(control for control in self.editor._controls
                        if control.winfo_class() == "TCheckbutton"
                        and control.cget("text") == "已核对目标页")
        checkbox.invoke()
        self.assertTrue(self.editor.draft.entries[0].confirmed)
        self.assertEqual(self.editor.tree.set("0", "confirmed"), "已确认")
        self.root.update()
        self.assertTrue(self.editor.draft.entries[0].confirmed)

    def test_switching_rows_applies_previous_form_to_previous_row(self):
        self.editor.title.set("前一行的新标题")
        self.choose(1)
        self.assertEqual(self.editor.draft.entries[0].title, "前一行的新标题")
        self.assertEqual(self.editor.draft.entries[1].title, "标题 1")
        self.assertEqual(self.editor.title.get(), "标题 1")

    def test_idle_debounce_applies_valid_edit_without_update_click(self):
        self.editor.title.set("无需按钮的修改")
        self.spin(lambda: self.editor.draft.entries[0].title == "无需按钮的修改")
        self.assertEqual(self.editor.tree.set("0", "title"), "无需按钮的修改")

    def test_invalid_intermediate_input_retains_form_and_blocks_selection(self):
        self.editor.target.set("abc")
        self.choose(1)
        self.assertEqual(self.editor._editing_index, 0)
        self.assertEqual(self.editor.target.get(), "abc")
        self.assertEqual(self.editor.draft.entries[0].pdf_page, 1)
        self.assertFalse(self.errors)
        self.editor.target.set("2")
        self.choose(1)
        self.assertEqual(self.editor.draft.entries[0].pdf_page, 2)
        self.assertEqual(self.editor._editing_index, 1)

    def test_invalid_edit_blocks_source_change_without_losing_draft(self):
        draft = self.editor.draft
        self.editor.title.set("")
        self.assertFalse(self.editor._set_pdf(self.pdf))
        self.assertIs(self.editor.draft, draft)
        self.assertEqual(self.editor.title.get(), "")
        self.editor.source_tabs.select(1)
        self.root.update()
        self.assertEqual(self.editor.source_tabs.index("current"), 0)

    def test_digit_key_changes_multiple_selected_levels_and_preserves_order_pages(self):
        self.choose(1, 2)
        result = self.editor._level_key(SimpleNamespace(char="2"))
        self.assertEqual(result, "break")
        self.assertEqual([entry.level for entry in self.editor.draft.entries], [1, 2, 2])
        self.assertEqual([entry.pdf_page for entry in self.editor.draft.entries], [1, 2, 3])
        self.assertEqual([entry.title for entry in self.editor.draft.entries], ["标题 0", "标题 1", "标题 2"])
        self.assertEqual(set(self.editor.tree.selection()), {"1", "2"})

    def test_invalid_batch_hierarchy_has_no_partial_mutation(self):
        self.choose(1, 2)
        self.assertFalse(self.editor.set_selected_levels(level=3))
        self.assertEqual([entry.level for entry in self.editor.draft.entries], [1, 1, 1])
        self.choose(0)
        self.assertFalse(self.editor.set_selected_levels(level=2))
        self.assertEqual([entry.level for entry in self.editor.draft.entries], [1, 1, 1])

    def test_dragging_selected_level_cells_changes_hierarchy_in_batch(self):
        self.choose(1, 2)
        self.root.update()
        x, y, _, height = self.editor.tree.bbox("1", "#1")
        self.assertEqual(self.editor._drag_start(SimpleNamespace(x=x + 8, y=y + height // 2, state=0)), "break")
        self.editor._drag_motion(SimpleNamespace(x=x + 38))
        self.editor._drag_end(SimpleNamespace(x=x + 38))
        self.assertEqual([entry.level for entry in self.editor.draft.entries], [1, 2, 2])
        self.assertEqual(set(self.editor.tree.selection()), {"1", "2"})

    def test_level_shortcuts_are_not_bound_to_text_entry(self):
        title_entry = next(control for control in self.editor._controls
                           if control.winfo_class() == "TEntry"
                           and str(control.cget("textvariable")) == str(self.editor.title))
        self.assertFalse(title_entry.bind("<KeyPress>"))
        self.editor.title.set("2026 数字标题")
        self.editor._apply_auto()
        self.assertEqual(self.editor.draft.entries[0].title, "2026 数字标题")
        self.assertEqual(self.editor.draft.entries[0].level, 1)

    def test_inline_title_edit_commits_without_update_button(self):
        self.root.update()
        x, y, width, height = self.editor.tree.bbox("1", "#2")
        self.editor._inline_edit(SimpleNamespace(x=x + width // 2, y=y + height // 2))
        self.assertIsNotNone(self.editor._inline)
        self.editor.title.set("双击后编辑")
        self.editor._finish_inline()
        self.assertEqual(self.editor.draft.entries[1].title, "双击后编辑")
        self.assertIsNone(self.editor._inline)

    def test_main_remains_operable_without_grab_or_transient_owner(self):
        self.assertIsNone(self.root.grab_current())
        self.assertEqual(str(self.editor.window.transient()), "")
        fired = Mock()
        from tkinter import ttk
        button = ttk.Button(self.root, text="主界面仍可操作", command=fired)
        button.pack()
        button.invoke()
        fired.assert_called_once()

    def test_independent_topmost_and_output_settings_are_remembered(self):
        self.root.attributes("-topmost", False)
        self.editor.topmost.set(True)
        self.editor._set_topmost()
        self.assertTrue(self.editor.window.attributes("-topmost"))
        self.assertFalse(self.root.attributes("-topmost"))
        custom = self.folder / "目录 JSON"
        custom.mkdir()
        self.editor.save_dir.set(str(custom))
        self.editor.save_mode.set("custom")
        self.assertEqual(self.editor._save_target(), custom / "中文 图书.toc.json")
        settings = self.settings_callback.call_args.args[0]
        self.assertEqual(settings["toc_save_dir"], str(custom))
        self.assertEqual(settings["toc_save_mode"], "custom")
        self.assertTrue(settings["editor_topmost"])

    def test_primary_save_uses_configured_folder_without_save_file_dialog(self):
        self.load(confirmed=True)
        custom = self.folder / "自定义目录"
        custom.mkdir()
        self.editor.save_dir.set(str(custom))
        self.editor.save_mode.set("custom")
        target = custom / "中文 图书.toc.json"
        with patch.object(toc_editor.filedialog, "asksaveasfilename") as dialog:
            self.editor.save()
            self.spin(lambda: self.editor.closed)
            dialog.assert_not_called()
        self.assertTrue(target.is_file())

    def test_existing_json_is_not_overwritten_without_accepting_question(self):
        self.load(confirmed=True)
        existing = self.folder / "旧目录.json"
        existing.write_text("existing", encoding="utf-8")
        self.editor._loaded_json = existing
        with patch.object(toc_editor.messagebox, "askyesno", return_value=False) as question:
            self.editor.save()
            question.assert_called_once()
        self.assertEqual(existing.read_text(encoding="utf-8"), "existing")
        self.assertFalse(self.editor.busy)

    def test_imported_json_name_is_retained_when_custom_folder_selected(self):
        self.editor._loaded_json = self.folder / "自定义文件名.json"
        custom = self.folder / "输出"
        custom.mkdir()
        self.editor.save_dir.set(str(custom))
        self.editor.save_mode.set("custom")
        self.assertEqual(self.editor._save_target(), custom / "自定义文件名.json")

    def test_missing_custom_directory_blocks_save_without_touching_pdf(self):
        self.load(confirmed=True)
        self.editor.save_mode.set("custom")
        with patch.object(toc_editor, "save_toc") as save:
            self.editor.save()
            save.assert_not_called()
        self.assertIn("请选择自定义", self.errors[-1])


if __name__ == "__main__":
    unittest.main()
