"""Per-document detail reporting preserves complete errors and has no file effects."""

import copy
from pathlib import Path
import tkinter as tk
import unittest

from details_dialog import FileDetailsDialog, format_file_details
from ui_theme import PALETTES, apply_theme, apply_ui_scale


class FileDetailsTests(unittest.TestCase):
    def test_preview_does_not_claim_write_or_backup_and_never_truncates_errors(self):
        record = {"pdf_path": Path("D:/合成 教材.pdf"), "toc_path": None, "state": "预览失败",
                  "preview_result": {"status": "预览失败", "error": "第一行\n第二行" + "详细原因" * 500},
                  "write_result": None}
        before = copy.deepcopy(record)
        text = format_file_details(record)
        self.assertIn(record["preview_result"]["error"], text)
        self.assertIn("尚无写入结果；预览成功不表示已写入", text)
        self.assertIn("未匹配", text)
        self.assertEqual(record, before)

    def test_write_result_keeps_actual_backup_cache_and_toc_warning_separate(self):
        record = {"pdf_path": Path("D:/合成.pdf"), "toc_path": Path("D:/合成.toc.json"), "state": "已写入，有提示",
                  "preview_result": {"status": "已预览", "page_count": 5, "existing_count": 0, "planned_count": 2},
                  "write_result": {"status": "written", "message": "写入成功", "backup": "D:/备份/原文.pdf",
                                   "cache_status": "failed", "cache_path": "D:/目录/缓存.json",
                                   "warnings": ["缓存占用，已保留"],
                                   "toc_cleanup": {"status": "retained", "path": "D:/合成.toc.json", "warning": "JSON身份变化，已保留"}}}
        text = format_file_details(record)
        for expected in ("状态：已写入", "PDF 页数：5", "实际备份：D:/备份/原文.pdf",
                         "茉莉花缓存：失败", "缓存占用，已保留", "目录 JSON 清理：已保留", "JSON身份变化，已保留"):
            self.assertIn(expected, text)

    def test_readonly_dialog_shares_theme_font_and_updates_without_editing_record(self):
        root = tk.Tk()
        root.withdraw()
        errors = []
        root.report_callback_exception = lambda *error: errors.append(error)
        try:
            apply_theme(root, "light")
            apply_ui_scale(root, 125)
            record = {"pdf_path": Path("D:/合成.pdf"), "toc_path": None, "state": "未预览"}
            dialog = FileDetailsDialog(root, "one", record)
            root.update_idletasks()
            self.assertIsNone(root.grab_current())
            self.assertEqual(str(dialog.text.cget("state")), "disabled")
            self.assertEqual(str(dialog.text.cget("font")), "TkTextFont")
            before = dialog.text.get("1.0", "end-1c")
            dialog.text.insert("end", "不应插入")
            self.assertEqual(dialog.text.get("1.0", "end-1c"), before)
            record = dict(record, pdf_path=Path("D:/另一本.pdf"), state="预览失败",
                          preview_result={"status": "预览失败", "error": "完整新错误"})
            dialog.update_record("two", record)
            self.assertEqual(dialog.iid, "two")
            self.assertIn("完整新错误", dialog.text.get("1.0", "end-1c"))
            for theme, palette in PALETTES.items():
                apply_theme(root, theme)
                self.assertEqual(dialog.text.cget("background"), palette["input_background"])
            dialog.close()
            self.assertFalse(dialog.window.winfo_exists())
            self.assertEqual(errors, [])
        finally:
            root.update_idletasks()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
