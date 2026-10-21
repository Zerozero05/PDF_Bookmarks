"""The compact write settings retain their controls, values and busy interlock."""

import gc
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from tkinterdnd2 import TkinterDnD

from bookmarks_gui import BookmarkWindow
from gui_support import load_settings


class MainCompactLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="main-compact-")
        self.settings = Path(self.temporary.name) / "settings.json"
        self.root = TkinterDnD.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.main = BookmarkWindow(self.root, settings_path=self.settings)
        self.root.geometry("1000x760+10000+10000")
        self.root.deiconify()
        self.root.update()

    def tearDown(self):
        self.main._set_busy(False)
        self.main._close()
        self.main.executor.shutdown(wait=True, cancel_futures=True)
        self.main = None
        self.root = None
        gc.collect()
        self.temporary.cleanup()
        self.assertEqual(self.errors, [])

    def test_collapsed_settings_show_all_current_write_choices(self):
        self.assertFalse(self.main.write_options.winfo_ismapped())
        self.assertTrue(self.main.write_options_button.winfo_ismapped())
        summary = self.main.write_options_summary.get()
        self.assertIn("跳过已有书签", summary)
        self.assertIn("备份开启（原目录 _backup）", summary)
        self.assertIn("清缓存关闭", summary)
        self.assertIn("删除 JSON 关闭", summary)
        self.assertTrue(self.main.backup.get())
        self.assertFalse(self.main.clear_cache.get())
        self.assertFalse(self.main.delete_toc.get())

    def test_fold_and_unfold_preserve_custom_choices_and_directory(self):
        custom = str(Path(self.temporary.name) / "自定义 备份")
        self.main.existing.set("替换已有书签")
        self.main.backup_dir.set(custom)
        self.main.clear_cache.set(True)
        self.main.delete_toc.set(True)
        for _ in range(3):
            self.main.write_options_button.invoke()
            self.root.update()
            self.assertTrue(self.main.write_options.winfo_ismapped())
            self.assertTrue(self.main.policy.winfo_ismapped())
            self.assertTrue(all(widget.winfo_ismapped() for widget in self.main.backup_widgets))
            self.main.write_options_button.invoke()
            self.root.update()
            self.assertFalse(self.main.write_options.winfo_ismapped())
        self.assertEqual(self.main.backup_dir.get(), custom)
        self.assertEqual(self.main.existing.get(), "替换已有书签")
        self.assertIn("自定义目录", self.main.write_options_summary.get())
        self.assertIn("清缓存开启（须退出 Zotero）", self.main.write_options_summary.get())
        self.assertIn("删除 JSON 开启", self.main.write_options_summary.get())
        self.main._save_settings()
        saved = load_settings(self.settings)
        self.assertEqual(saved["backup_dir"], custom)
        self.assertEqual(saved["existing"], "replace")
        self.assertTrue(saved["clear_cache"])
        self.assertTrue(saved["delete_toc"])

    def test_opening_hidden_settings_cannot_bypass_busy_or_backup_disable(self):
        self.main._set_busy(True)
        self.main.write_options_button.invoke()
        self.root.update()
        self.assertTrue(self.main.write_options.winfo_ismapped())
        self.assertEqual(str(self.main.policy.cget("state")), "disabled")
        self.assertTrue(all(str(widget.cget("state")) == "disabled" for widget in self.main.backup_widgets))
        for widget in self.main.write_options.winfo_children():
            if isinstance(widget, ttk.Checkbutton):
                self.assertTrue(widget.instate(("disabled",)))
        self.main._set_busy(False)
        self.assertEqual(str(self.main.policy.cget("state")), "readonly")
        self.main.backup.set(False)
        self.assertTrue(all(str(widget.cget("state")) == "disabled" for widget in self.main.backup_widgets))
        self.assertIn("备份关闭", self.main.write_options_summary.get())
        self.main.backup.set(True)
        self.assertTrue(all(str(widget.cget("state")) == "normal" for widget in self.main.backup_widgets))

    def test_editor_menu_preference_persists_through_main_and_editor_reopen(self):
        self.main.backup.set(False)
        self.main.backup_dir.set(str(Path(self.temporary.name) / "保留的备份目录"))
        self.main.clear_cache.set(True)
        self.main.delete_toc.set(True)
        self.main.existing.set("替换已有书签")
        self.main._save_settings()
        previous = load_settings(self.settings)
        unchanged = ("backup", "backup_dir", "clear_cache", "delete_toc", "existing",
                     "recursive", "last_dir", "theme")
        self.main._open_editor()
        self.root.update()
        first = self.main.editor
        self.assertTrue(first.confirm_multi_delete.get())
        first.draft_menu.invoke("删除多个目录项前询问")
        self.root.update()
        self.assertFalse(first.confirm_multi_delete.get())
        self.assertFalse(self.main.editor_settings["editor_confirm_multi_delete"])
        saved = load_settings(self.settings)
        self.assertFalse(saved["editor_confirm_multi_delete"])
        self.assertEqual({key: saved[key] for key in unchanged},
                         {key: previous[key] for key in unchanged})
        first.close()
        self.root.update()
        self.assertTrue(first.closed)
        self.main._open_editor()
        self.root.update()
        reopened = self.main.editor
        self.assertIsNot(reopened, first)
        self.assertFalse(reopened.confirm_multi_delete.get())
        persisted = load_settings(self.settings)
        self.assertFalse(persisted["editor_confirm_multi_delete"])
        self.assertEqual({key: persisted[key] for key in unchanged},
                         {key: previous[key] for key in unchanged})

    def test_write_completion_uses_visible_success_and_preserves_problem_dialogs(self):
        with patch("bookmarks_gui.messagebox.showinfo") as info, \
                patch("bookmarks_gui.messagebox.showerror") as error, \
                patch("bookmarks_gui.messagebox.showwarning") as warning:
            try:
                for errors, warnings, expected_dialog in (
                        ([], [], None), (["合成写入失败"], [], error),
                        ([], ["合成清理警告"], warning)):
                    self.root.after_cancel(self.main._poll_after)
                    self.main._set_busy(True)
                    self.main.events.put(("write_done", (2, 1, errors, warnings)))
                    self.main._poll()
                    self.assertFalse(self.main.busy)
                    self.assertIn("已写入 2 本；跳过 1 本", self.main.status.get())
                    self.assertIn(f"失败 {len(errors)} 本", self.main.status.get())
                    info.assert_not_called()
                    if expected_dialog is None:
                        error.assert_not_called()
                        warning.assert_not_called()
                        self.assertIn("处理完成：写入 2 本，跳过 1 本", self.main.log.get("1.0", "end"))
                        self.assertIn("在 Zotero 中重新打开原附件查看目录", self.main.log.get("1.0", "end"))
                    elif expected_dialog is error:
                        error.assert_called_once_with("部分文件写入失败", "合成写入失败\n详情见处理记录。", parent=self.root)
                        warning.assert_not_called()
                    else:
                        warning.assert_called_once_with("PDF 已写入，缓存清理有提示", "合成清理警告", parent=self.root)
                        error.assert_not_called()
                    error.reset_mock()
                    warning.reset_mock()
            finally:
                info.reset_mock()
                error.reset_mock()
                warning.reset_mock()

    def test_primary_actions_and_expanded_controls_fit_minimum_in_both_themes(self):
        self.root.maxsize(2000, 1400)
        for theme in ("light", "dark"):
            self.main.theme.set(theme)
            self.main._set_theme()
            for expanded in (False, True):
                if self.main._write_options_open != expanded:
                    self.main.write_options_button.invoke()
                self.root.update()
                visible = [self.main.directory_button, self.main.preview_button,
                           self.main.write_button, self.main.write_options_button]
                if expanded:
                    visible.extend(widget for widget in self.main.inputs
                                   if widget.winfo_ismapped() and widget.winfo_parent() == str(self.main.write_options))
                for widget in visible:
                    with self.subTest(theme=theme, expanded=expanded, widget=str(widget)):
                        self.assertTrue(widget.winfo_ismapped())
                        self.assertGreaterEqual(widget.winfo_rootx(), self.root.winfo_rootx())
                        self.assertGreaterEqual(widget.winfo_rooty(), self.root.winfo_rooty())
                        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                             self.root.winfo_rootx() + self.root.winfo_width())
                        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                             self.root.winfo_rooty() + self.root.winfo_height())


if __name__ == "__main__":
    unittest.main()
