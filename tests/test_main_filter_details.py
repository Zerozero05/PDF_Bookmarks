"""Filtering never narrows write checks; per-book outcomes stay distinct."""

import unittest
from unittest.mock import patch

import test_main_shortcuts_preview as fixtures


class MainFilterDetailsTests(unittest.TestCase):
    setUp = fixtures.MainShortcutsPreviewTests.setUp
    tearDown = fixtures.MainShortcutsPreviewTests.tearDown
    pump = fixtures.MainShortcutsPreviewTests.pump
    load = fixtures.MainShortcutsPreviewTests.load
    focus = fixtures.MainShortcutsPreviewTests.focus

    def test_search_preserves_order_pairing_ready_plans_checks_and_hidden_write_count(self):
        ids = self.load()
        records = [(iid, item["pdf_path"], item["toc_path"], item["checked"], item["plan"])
                   for iid, item in self.main.items.items()]
        self.main.file_search.set("教材1")
        self.assertEqual(self.main.file_tree.get_children(), (ids[1],))
        self.assertEqual([(iid, item["pdf_path"], item["toc_path"], item["checked"], item["plan"])
                          for iid, item in self.main.items.items()], records)
        self.assertIn("勾选写入 3 本", self.main.selection_status.get())
        self.assertIn("隐藏 2 本", self.main.selection_status.get())
        self.assertEqual(len(self.main._checked_items()), 3)
        self.main._set_all_checked(False)
        self.assertTrue(all(not item["checked"] for item in self.main.items.values()))
        self.main._set_all_checked(True)
        self.assertTrue(all(item["checked"] for item in self.main.items.values()))
        self.main._clear_file_filters()
        self.assertEqual(self.main.file_tree.get_children(), ids)

    def test_ctrl_a_explicitly_clears_filters_and_keeps_full_list_selection_meaning(self):
        ids = self.load()
        self.main._set_all_checked(False)
        self.main._toggle_item(ids[1])
        before = [item["checked"] for item in self.main.items.values()]
        self.main.file_search.set("教材1")
        self.focus(self.main.file_tree)
        self.main.file_tree.event_generate("<Control-a>")
        self.root.update()
        self.assertEqual(self.main.file_search.get(), "")
        self.assertEqual(self.main.file_filter.get(), "全部")
        self.assertEqual(set(self.main.file_tree.selection()), set(ids))
        self.assertEqual([item["checked"] for item in self.main.items.values()], before)
        self.assertIn("清除筛选并选中全部", self.main.status.get())

    def test_status_filters_show_missing_preview_failure_write_failure_and_pending(self):
        ids = self.load()
        self.main.items[ids[0]]["toc_path"] = None
        self.main.items[ids[0]]["ready"] = False
        self.main.items[ids[1]]["error"] = "模拟预览错误"
        self.main.items[ids[1]]["ready"] = False
        self.main.items[ids[1]]["preview_result"] = {"status": "预览失败", "error": "模拟预览错误"}
        for name, expected in (("缺少 JSON", (ids[0],)), ("预览失败", (ids[1],)), ("待写入", (ids[2],))):
            self.main.file_filter.set(name)
            self.assertEqual(self.main.file_tree.get_children(), expected, name)
        self.main.items[ids[2]]["write_result"] = {"status": "failed", "error": "模拟写入错误"}
        self.main.file_filter.set("写入失败")
        self.assertEqual(self.main.file_tree.get_children(), (ids[2],))
        self.main.file_filter.set("已写入")
        self.assertEqual(self.main.file_tree.get_children(), ())
        self.root.update_idletasks()
        self.assertTrue(self.main.empty_files.winfo_ismapped())

    def test_replacing_filtered_list_removes_hidden_rows_and_enter_search_is_local(self):
        ids = self.load()
        self.main.file_search.set("教材1")
        self.main._replace_items([self.main._record(self.pdfs[0], self.pdfs[0].with_suffix(".toc.json"))])
        self.assertEqual(len(self.main.items), 1)
        self.assertFalse(self.main.file_tree.exists(ids[2]))
        self.main._clear_file_filters()
        self.focus(self.main.file_search_entry)
        self.main.file_search_entry.insert("end", "不存在")
        self.main.file_search_entry.event_generate("<Return>")
        self.root.update()
        self.assertEqual(self.main.file_tree.get_children(), ())
        self.assertEqual(len(self.main.items), 1)

    def test_details_reuses_window_and_preserves_preview_result_across_write_outcomes(self):
        ids = self.load()
        self.main.file_tree.selection_set(ids[0])
        self.main.file_tree.focus(ids[0])
        self.main._show_file_details()
        dialog = self.main._file_details
        self.assertIn("最近一次预览（只读）", dialog.text.get("1.0", "end-1c"))
        self.assertIn("尚无写入结果", dialog.text.get("1.0", "end-1c"))
        plans = [(iid, self.main.items[iid]["plan"]) for iid in ids]
        expected_preview = self.main.items[ids[0]]["preview_result"].copy()
        results = [{"status": "written", "message": "模拟已写入", "backup": "D:/模拟备份.pdf",
                    "cache_status": "failed", "warnings": ["模拟缓存占用，已保留"]},
                   {"status": "skipped", "message": "按策略跳过", "backup": None}, OSError("模拟完整写入错误\n多行原因")]
        with patch("bookmarks_gui.write_plan", side_effect=results), \
                patch("bookmarks_gui.delete_written_toc", return_value={"status": "retained", "warning": "模拟 JSON 身份变化，已保留"}), \
                patch("bookmarks_gui.messagebox.showerror"), patch("bookmarks_gui.messagebox.showwarning"):
            self.main._set_busy(True)
            self.main._write_worker(plans, "replace", {}, delete_toc=True)
            self.pump(lambda: not self.main.busy)
        self.assertEqual(self.main.items[ids[0]]["preview_result"], expected_preview)
        self.assertEqual(self.main.items[ids[0]]["write_result"]["status"], "written")
        self.assertEqual(self.main.items[ids[0]]["write_result"]["toc_cleanup"]["status"], "retained")
        self.assertEqual(self.main.items[ids[1]]["write_result"]["status"], "skipped")
        self.assertEqual(self.main.items[ids[2]]["write_result"]["error"], "模拟完整写入错误\n多行原因")
        text = dialog.text.get("1.0", "end-1c")
        for phrase in ("模拟备份.pdf", "模拟缓存占用", "模拟 JSON 身份变化"):
            self.assertIn(phrase, text)
        self.main.file_tree.selection_set(ids[2])
        self.main.file_tree.focus(ids[2])
        self.main._show_file_details()
        self.assertIs(self.main._file_details, dialog)
        self.assertIn("模拟完整写入错误\n多行原因", dialog.text.get("1.0", "end-1c"))

    def test_write_confirmation_counts_hidden_checked_targets_and_cancel_keeps_files(self):
        self.load()
        self.main.file_search.set("教材1")
        with patch("bookmarks_gui.messagebox.askyesno", return_value=False) as confirm:
            self.main._write()
            self.assertIn("包含 2 本被筛选隐藏", confirm.call_args.args[1])
            self.assertIn("将原地写入 3 个", confirm.call_args.args[1])
        self.assertFalse(self.main.busy)
        self.assertEqual(len(self.main._checked_items()), 3)


if __name__ == "__main__":
    unittest.main()
