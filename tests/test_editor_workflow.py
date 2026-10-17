"""Resumable directory review uses temporary drafts and the existing Tk worker."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import pymupdf

import toc_editor
from toc_generation import Draft, DraftEntry


class EditorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-editor-workflow-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "中文 目录审校.pdf"
        with pymupdf.open() as document:
            for index in range(8):
                document.new_page().insert_text((72, 72), f"Page {index + 1}")
            document.save(self.pdf)
        self.pdf_hash = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.toc = self.pdf.with_suffix(".toc.json")
        self.toc.write_text(json.dumps({"version": 1, "bookmarks": [
            {"title": "原正式目录不能被暂存覆盖", "pdf_page": 2}
        ]}, ensure_ascii=False), encoding="utf8")
        self.toc_bytes = self.toc.read_bytes()
        self.drafts = self.folder / "drafts"
        self.root = tk.Tk()
        self.root.withdraw()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.editors = []
        self.errors = []
        self.dialogs = [
            patch.object(toc_editor.messagebox, "showerror", side_effect=lambda title, message, errors=self.errors, **kw: errors.append(str(message))),
            patch.object(toc_editor.messagebox, "showinfo"),
            patch.object(toc_editor.messagebox, "showwarning"),
            patch.object(toc_editor.messagebox, "askyesno", return_value=True),
        ]
        for dialog in self.dialogs:
            dialog.start()
        self.addCleanup(self.cleanup)
        self.editor = self.open()

    def cleanup(self):
        for editor in self.editors:
            if not editor.closed:
                editor.close()
        self.executor.shutdown(wait=True)
        try:
            self.root.update_idletasks()
            self.root.destroy()
        finally:
            for dialog in reversed(self.dialogs):
                dialog.stop()
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.pdf_hash)
        self.assertEqual(self.toc.read_bytes(), self.toc_bytes)
        self.temporary.cleanup()

    def open(self):
        editor = toc_editor.open_editor(self.root, self.executor, self.pdf, draft_dir=self.drafts)
        self.editors.append(editor)
        editor.window.geometry("1240x900+32000+32000")
        editor.window.attributes("-topmost", False)
        self.root.update_idletasks()
        return editor

    def sample(self):
        return Draft(self.pdf, 8, [
            DraftEntry(1, "第一章 基础", 1, 2, "高", "已核对章首", True),
            DraftEntry(2, "1.1 基本概念", 2, 3, "低", "请复核文字", False),
            DraftEntry(3, "1.1.1 细节", 3, None, "低", "目标页未知", False),
            DraftEntry(2, "1.2 极限", 4, 5, "高", "已核对目标", True),
            DraftEntry(1, "第二章 延伸", 5, 6, "高", "尚未确认", False),
        ], [1], {"offset": 1}, "本地测试识别", ["测试证据"])

    def spin(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("目录审校工作流未在时限内完成。")

    def load(self, editor=None):
        editor = editor or self.editor
        draft = self.sample()
        calls = []

        def recognize(*args, **kwargs):
            calls.append(threading.get_ident())
            return draft

        with patch.object(toc_editor, "generate_toc", side_effect=recognize):
            editor.generate()
            self.spin(lambda: editor.draft is draft and not editor.busy)
        self.assertIs(editor.executor, self.executor)
        self.assertTrue(calls)
        self.assertNotEqual(calls[0], threading.get_ident())
        editor.auto_save.set(False)
        return draft

    def choose(self, index, editor=None):
        editor = editor or self.editor
        editor.tree.selection_set(str(index))
        editor.tree.focus(str(index))
        editor._selected()

    def snapshot(self, editor=None):
        return deepcopy(asdict((editor or self.editor).draft))

    def draft_files(self):
        return sorted(self.drafts.rglob("*.json")) if self.drafts.exists() else []

    def test_manual_draft_accepts_pending_unknown_targets_without_exporting_json(self):
        self.load()
        expected = self.snapshot()
        self.assertTrue(self.editor.save_draft())
        self.assertTrue(self.draft_files())
        self.assertEqual(self.snapshot(), expected)
        self.assertFalse(self.errors)
        with patch.object(toc_editor.filedialog, "asksaveasfilename") as choose:
            self.editor.save()
        choose.assert_not_called()
        self.assertTrue(self.errors)
        self.assertEqual(self.toc.read_bytes(), self.toc_bytes)

    def test_restore_preserves_incomplete_raw_fields_and_review_state(self):
        self.load()
        expected = self.snapshot()
        self.choose(1)
        self.editor.title.set("")
        self.editor.target.set("尚未填完")
        self.assertTrue(self.editor.save_draft())
        self.editor.close()
        self.editor = self.open()
        self.assertTrue(self.editor.restore_draft())
        self.assertEqual(self.snapshot(), expected)
        self.assertEqual(self.editor._editing_index, 1)
        self.assertEqual(self.editor.title.get(), "")
        self.assertEqual(self.editor.target.get(), "尚未填完")
        self.editor.save()
        self.assertTrue(self.errors)
        self.assertEqual(self.editor.target.get(), "尚未填完")

    def test_pdf_stat_change_refuses_restore_and_blocks_automatic_overwrite(self):
        self.load()
        self.assertTrue(self.editor.save_draft())
        saved = {path: path.read_bytes() for path in self.draft_files()}
        previous = self.snapshot()
        stat = self.pdf.stat()
        os.utime(self.pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
        self.assertFalse(self.editor.restore_draft())
        self.assertTrue(self.errors)
        self.assertEqual(self.snapshot(), previous)
        self.editor.auto_save.set(True)
        self.editor.title.set("不能覆盖旧恢复证据")
        self.editor.update_entry()
        deadline = time.monotonic() + 1.8
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertEqual({path: path.read_bytes() for path in self.draft_files()}, saved)

    def test_undo_redo_restores_title_confidence_note_and_confirmation(self):
        self.load()
        before = self.snapshot()
        self.editor.title.set("第一章 手工校对后的基础")
        self.editor.update_entry()
        after = self.snapshot()
        self.assertFalse(self.editor.draft.entries[0].confirmed)
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)
        self.editor.redo()
        self.assertEqual(self.snapshot(), after)

    def test_undo_redo_of_add_and_delete_preserves_original_entries(self):
        self.load()
        original = self.snapshot()
        self.choose(1)
        self.editor.add_entry()
        added = self.snapshot()
        self.assertEqual(len(self.editor.draft.entries), 6)
        self.editor.delete_entry()
        self.assertEqual(self.snapshot(), original)
        self.editor.undo()
        self.assertEqual(self.snapshot(), added)
        self.editor.undo()
        self.assertEqual(self.snapshot(), original)
        self.editor.redo()
        self.assertEqual(self.snapshot(), added)
        self.editor.redo()
        self.assertEqual(self.snapshot(), original)

    def test_undo_redo_of_level_change_restores_confirmed_entry_and_targets(self):
        self.load()
        self.choose(3)
        before = self.snapshot()
        self.assertTrue(self.editor.set_selected_levels(level=1))
        after = self.snapshot()
        self.assertEqual(self.editor.draft.entries[3].level, 1)
        self.assertFalse(self.editor.draft.entries[3].confirmed)
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)
        self.editor.redo()
        self.assertEqual(self.snapshot(), after)

    def test_undo_redo_of_mapping_restores_targets_evidence_and_confirmation(self):
        self.load()
        before = self.snapshot()
        self.editor.offset.set("2")
        self.editor.apply_offset()
        after = self.snapshot()
        self.assertEqual(self.editor.draft.mapping, {"offset": 2})
        self.assertEqual([entry.pdf_page for entry in self.editor.draft.entries], [3, 4, 5, 6, 7])
        self.assertFalse(any(entry.confirmed for entry in self.editor.draft.entries))
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)
        self.editor.redo()
        self.assertEqual(self.snapshot(), after)

    def test_filters_keep_original_row_ids_and_do_not_renumber_the_draft(self):
        self.load()
        before = self.snapshot()
        self.assertEqual(self.editor.view_mode.get(), "详细表格")
        for mode, wanted in (("待确认", ("1", "2", "4")), ("低可信", ("1", "2")),
                             ("未知页码", ("2",)), ("全部", ("0", "1", "2", "3", "4"))):
            with self.subTest(mode=mode):
                self.editor.filter_mode.set(mode)
                self.editor._filter_changed()
                self.assertEqual(self.editor.tree.get_children(), wanted)
                self.assertEqual(self.snapshot(), before)

    def test_search_and_filter_commit_valid_edit_to_original_index(self):
        self.load()
        self.choose(3)
        self.editor.title.set("1.2 校对后的极限")
        self.editor.search_text.set("校对后的极限")
        self.editor._filter_changed()
        self.assertEqual(self.editor.tree.get_children(), ("3",))
        self.assertEqual(self.editor.draft.entries[3].title, "1.2 校对后的极限")
        self.assertFalse(self.editor.draft.entries[3].confirmed)
        self.editor.title.set("1.2 再次核对极限")
        self.editor.update_entry()
        self.assertEqual(self.editor.draft.entries[0].title, "第一章 基础")
        self.assertEqual(self.editor.draft.entries[3].title, "1.2 再次核对极限")

    def test_invalid_fields_block_filter_change_without_losing_unfinished_text(self):
        self.load()
        self.choose(1)
        before = self.snapshot()
        rows = self.editor.tree.get_children()
        self.editor.target.set("abc")
        self.editor.filter_mode.set("未知页码")
        self.editor._filter_changed()
        self.assertEqual(self.editor.target.get(), "abc")
        self.assertEqual(self.editor._editing_index, 1)
        self.assertEqual(self.editor.tree.get_children(), rows)
        self.assertEqual(self.snapshot(), before)

    def test_next_pending_skips_confirmed_and_wraps_without_changing_data(self):
        self.load()
        before = self.snapshot()
        self.choose(0)
        for expected in (1, 2, 4, 1):
            self.editor.next_pending()
            self.assertEqual(self.editor._editing_index, expected)
        self.assertEqual(self.snapshot(), before)

    def test_directory_tree_has_real_parents_and_preserves_original_ids_and_pages(self):
        self.load()
        before = self.snapshot()
        self.choose(3)
        self.editor.view_mode.set("目录树")
        self.editor._view_changed()
        self.assertEqual(self.editor.tree.get_children(), ("0", "4"))
        self.assertEqual(self.editor.tree.get_children("0"), ("1", "3"))
        self.assertEqual(self.editor.tree.get_children("1"), ("2",))
        self.assertEqual(self.editor.tree.parent("2"), "1")
        self.assertEqual(self.editor._editing_index, 3)
        self.assertEqual(self.snapshot(), before)
        self.editor.view_mode.set("详细表格")
        self.editor._view_changed()
        self.assertEqual(self.editor.tree.get_children(), ("0", "1", "2", "3", "4"))
        self.assertEqual(self.snapshot(), before)

    def test_automatic_draft_uses_only_explicit_local_draft_directory(self):
        self.load()
        self.editor.auto_save.set(True)
        self.editor.title.set("第一章 已自动暂存的审校")
        self.editor.update_entry()
        self.spin(lambda: self.draft_files() and any("已自动暂存的审校" in path.read_text(encoding="utf8")
                                                   for path in self.draft_files()))
        self.assertTrue(all(path.is_relative_to(self.drafts) for path in self.draft_files()))
        self.assertEqual(self.toc.read_bytes(), self.toc_bytes)
        self.assertFalse(self.errors)

    def test_invalid_numbering_options_reject_restore_without_replacing_live_objects(self):
        self.load()
        current = self.editor.draft
        entries = tuple(current.entries)
        before = self.snapshot()
        state = self.editor._history_state()
        state["options"]["numbering_meta"] = [["不完整编号记录"]] * len(entries)
        saved = self.editor.store.save(self.pdf, state)
        original = saved.read_bytes()
        self.assertFalse(self.editor.restore_draft())
        self.assertTrue(self.errors)
        self.assertIn("编号", self.errors[-1])
        self.assertIs(self.editor.draft, current)
        self.assertTrue(all(restored is previous for restored, previous in zip(current.entries, entries)))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(saved.read_bytes(), original)

    def test_manual_replacement_archives_corrupt_draft_after_explicit_yes_only(self):
        self.load()
        self.assertTrue(self.editor.save_draft())
        canonical = self.editor.store.path_for(self.pdf)
        damaged = b'{"schema_version":1,\n"unfinished":\x00'
        canonical.write_bytes(damaged)
        with patch.object(toc_editor.messagebox, "askyesno", return_value=True) as question:
            self.assertFalse(self.editor.save_draft(report=False))
            question.assert_not_called()
            self.assertEqual(canonical.read_bytes(), damaged)
            self.assertEqual(list(self.drafts.glob("*.backup.json")), [])
            self.assertTrue(self.editor.save_draft())
            question.assert_called_once()
        backups = list(self.drafts.glob("*.backup.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), damaged)
        self.assertNotEqual(canonical.read_bytes(), damaged)
        restored = self.editor.store.load(self.pdf)
        self.assertEqual(restored["draft"]["entries"][0]["title"], self.editor.draft.entries[0].title)
        self.assertFalse(self.errors)

    def test_restore_recovers_preview_page_scale_and_target_toc_or_source_context(self):
        self.load()
        self.choose(1)
        entry = self.editor.draft.entries[1]
        entry.source_page = 1
        entry.source_rect = (.05, .08, .45, .14)
        before = self.snapshot()
        for kind, page, scale in (("target", "3", 1.25), ("toc", "1", 1.5), ("source", "1", 1.75)):
            with self.subTest(preview_kind=kind):
                self.editor._preview_kind = kind
                self.editor.preview_page.set(page)
                self.editor._preview_scale = scale
                self.editor.preview_zoom.set(f"{scale:.0%}")
                self.editor.show_page()
                self.spin(lambda: self.editor._photo is not None and self.editor._displayed_page == int(page))
                self.assertTrue(self.editor.save_draft())
                self.editor._preview_kind = "target"
                self.editor.preview_page.set("8")
                self.editor._preview_scale = .5
                self.editor.preview_zoom.set("50%")
                self.editor.show_page()
                self.spin(lambda: self.editor._displayed_page == 8)
                self.assertTrue(self.editor.restore_draft())
                self.spin(lambda: self.editor._photo is not None and self.editor._displayed_page == int(page))
                self.assertEqual(self.editor.preview_page.get(), page)
                self.assertEqual(self.editor._preview_kind, kind)
                self.assertEqual(self.editor._preview_scale, scale)
                self.assertEqual(self.editor.preview_zoom.get(), f"{scale:.0%}")
                self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.errors)

    def test_restore_under_active_filter_keeps_saved_fields_on_their_original_entry(self):
        self.load()
        self.choose(0)
        before = self.snapshot()
        self.assertTrue(self.editor.save_draft())
        self.editor.search_text.set("极限")
        self.editor._filter_changed()
        self.assertEqual(self.editor.tree.get_children(), ("3",))
        self.assertEqual(self.editor._editing_index, 3)
        self.assertTrue(self.editor.restore_draft())
        self.editor.update_entry()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.editor._editing_index, 0)
        self.assertEqual(self.editor.title.get(), "第一章 基础")
        self.assertFalse(self.errors)

    def test_cancel_close_after_export_keeps_event_polling_and_reports_export_once(self):
        self.load()
        for index, entry in enumerate(self.editor.draft.entries):
            entry.pdf_page = index + 2
            entry.confirmed = True
        self.editor._refresh()
        self.editor.on_settings_changed = Mock()
        self.addCleanup(setattr, self.editor, "on_settings_changed", None)
        self.editor.on_saved = Mock()
        export_dir = self.folder / "正式导出"
        export_dir.mkdir()
        self.editor.save_dir.set(str(export_dir))
        self.editor.save_mode.set("custom")
        exported = export_dir / self.toc.name
        with patch.object(toc_editor.messagebox, "askyesnocancel", return_value=None) as question:
            self.editor.save()
            self.spin(lambda: self.editor.on_saved.called)
            question.assert_called_once()
            self.assertFalse(self.editor.closed)
            self.assertTrue(exported.is_file())
            self.editor.on_saved.assert_called_once_with(self.pdf, exported)
            self.editor.preview_page.set("7")
            self.editor.show_page()
            self.spin(lambda: self.editor._displayed_page == 7)
            self.editor.on_saved.assert_called_once_with(self.pdf, exported)
        self.assertFalse(self.errors)


if __name__ == "__main__":
    unittest.main()
