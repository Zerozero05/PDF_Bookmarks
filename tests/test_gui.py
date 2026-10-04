"""GUI and helper integration checks use temporary PDFs and isolated settings."""

import json
import os
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tkinterdnd2 import TkinterDnD

import pymupdf

import gui_support as support


def make_pdf(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as document:
        for color in ((1, 0, 0), (0, 1, 0)):
            page = document.new_page(width=200, height=240)
            page.draw_rect(page.rect, color=None, fill=color)
        document.save(path)


def make_toc(path, title="第二页书签"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "bookmarks": [
        {"title": title, "pdf_page": 2},
    ]}, ensure_ascii=False), encoding="utf-8")


class GuiSupportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="zotero-gui-support-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def test_settings_survive_reload_and_bad_json_uses_defaults(self):
        config = self.folder / "用户设置" / "settings.json"
        defaults = support.load_settings(config)
        settings = dict(defaults, backup=False, backup_dir="D:/数学备份",
                        clear_cache=True, recursive=True, existing="replace",
                        last_dir="D:/中文 图书", topmost=True, geometry="1200x900+20+30")
        support.save_settings(settings, config)
        self.assertEqual(support.load_settings(config), settings)
        config.write_text("{invalid JSON", encoding="utf-8")
        self.assertEqual(support.load_settings(config), defaults)

    def test_default_settings_are_outside_the_pdf_directory(self):
        source = self.folder / "Zotero storage" / "AB12CD34"
        source.mkdir(parents=True)
        pdf = source / "数学教材.pdf"
        make_pdf(pdf)
        original = pdf.read_bytes()
        names = set(source.iterdir())
        profile = self.folder / "用户配置"
        with patch.dict(os.environ, {"LOCALAPPDATA": str(profile)}):
            settings = support.load_settings()
            settings["topmost"] = True
            support.save_settings(settings)
            self.assertTrue(support.load_settings()["topmost"])
        self.assertTrue((profile / "ZoteroPDFBookmarks" / "settings.json").is_file())
        self.assertEqual(set(source.iterdir()), names)
        self.assertEqual(pdf.read_bytes(), original)

    def test_drop_multiple_chinese_space_paths_pairs_each_json(self):
        first = self.folder / "中文 一" / "第一本 书.pdf"
        second = self.folder / "中文 二" / "第二本 书.pdf"
        make_pdf(first)
        make_pdf(second)
        first_toc = first.with_suffix(".toc.json")
        second_toc = second.with_suffix(".toc.json")
        make_toc(first_toc)
        make_toc(second_toc)
        pairs = support.dropped_pairs([second_toc, first, first_toc, second])
        self.assertEqual(pairs, [(first, first_toc), (second, second_toc)])
        self.assertEqual(support.dropped_pairs([first, first, first_toc]), [(first, first_toc)])

    def test_explicit_one_pdf_and_different_name_json_are_paired(self):
        pdf = self.folder / "中文 书名.pdf"
        toc = self.folder / "用户手工目录.json"
        make_pdf(pdf)
        make_toc(toc)
        self.assertEqual(support.dropped_pairs([toc, pdf]), [(pdf, toc)])

    def test_same_name_pdf_across_folders_does_not_guess_ambiguous_json(self):
        first = self.folder / "甲目录" / "同名书.pdf"
        second = self.folder / "乙目录" / "同名书.pdf"
        toc = self.folder / "丙目录" / "同名书.toc.json"
        make_pdf(first)
        make_pdf(second)
        make_toc(toc)
        self.assertEqual(support.dropped_pairs([first, second, toc]),
                         [(first, None), (second, None)])

    def test_same_directory_json_disambiguates_identical_pdf_names(self):
        first = self.folder / "甲目录" / "同名书.pdf"
        second = self.folder / "乙目录" / "同名书.pdf"
        make_pdf(first)
        make_pdf(second)
        first_toc = first.with_suffix(".toc.json")
        second_toc = second.with_suffix(".toc.json")
        make_toc(first_toc)
        make_toc(second_toc)
        self.assertEqual(support.dropped_pairs([first, second, second_toc, first_toc]),
                         [(first, first_toc), (second, second_toc)])

    def test_explicit_matching_json_has_priority_over_automatic_sidecar(self):
        pdf = self.folder / "中文 书名.pdf"
        explicit = self.folder / "中文 书名.json"
        make_pdf(pdf)
        make_toc(explicit)
        make_toc(pdf.with_suffix(".toc.json"), title="自动找到的旧目录")
        self.assertEqual(support.dropped_pairs([pdf, explicit]), [(pdf, explicit)])

    def test_render_uses_actual_one_based_page_without_modifying_source(self):
        pdf = self.folder / "彩色 测试.pdf"
        make_pdf(pdf)
        original = pdf.read_bytes()
        first = support.render_page(pdf, 1, max_width=100, max_height=120)
        second = support.render_page(pdf, 2, max_width=100, max_height=120)
        self.assertTrue(second.startswith(b"\x89PNG\r\n\x1a\n"))
        pixmap = pymupdf.Pixmap(second)
        self.assertEqual((pixmap.width, pixmap.height), (100, 120))
        self.assertEqual(pixmap.pixel(20, 20)[:3], (0, 255, 0))
        self.assertEqual(pymupdf.Pixmap(first).pixel(20, 20)[:3], (255, 0, 0))
        for invalid in (0, 3, True, 1.5):
            with self.subTest(page=invalid), self.assertRaises(ValueError):
                support.render_page(pdf, invalid)
        self.assertEqual(pdf.read_bytes(), original)
        self.assertEqual(set(self.folder.iterdir()), {pdf})


class GuiWindowTests(unittest.TestCase):
    def setUp(self):
        import bookmarks_gui
        self.gui = bookmarks_gui
        temporary = tempfile.TemporaryDirectory(prefix="zotero-gui-window-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.settings_path = self.folder / "用户配置" / "settings.json"
        dialogs = patch.multiple(bookmarks_gui.messagebox, askyesno=Mock(return_value=True),
                                 showerror=Mock(), showinfo=Mock(), showwarning=Mock())
        self.dialogs = dialogs.start()
        self.addCleanup(dialogs.stop)
        self.windows = []
        self.addCleanup(self.close_windows)
        self.root, self.window = self.new_window()

    def new_window(self):
        root = TkinterDnD.Tk()
        root.withdraw()
        window = self.gui.BookmarkWindow(root, settings_path=self.settings_path)
        self.windows.append((root, window))
        root.update_idletasks()
        return root, window

    def close_windows(self):
        for root, window in reversed(self.windows):
            try:
                if root.winfo_exists():
                    self.pump(lambda: not window.busy, root=root, timeout=5)
                    window._close()
            except tk.TclError:
                pass
            finally:
                window.executor.shutdown(wait=True, cancel_futures=True)

    def pump(self, condition, root=None, timeout=10):
        root = root or self.root
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            root.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("GUI worker did not finish within the test deadline")

    def pdf_pair(self, name="第一本 中文书.pdf"):
        pdf = self.folder / "PDF 文件" / name
        make_pdf(pdf)
        toc = pdf.with_suffix(".toc.json")
        make_toc(toc)
        return pdf, toc

    def preview(self):
        self.window._preview()
        self.pump(lambda: not self.window.busy)

    def item_for_pdf(self, pdf):
        return next((iid, item) for iid, item in self.window.items.items()
                    if Path(item["pdf_path"]) == pdf)

    def test_settings_survive_real_window_close_and_reopen(self):
        self.window.backup.set(False)
        self.window.backup_dir.set(str(self.folder / "中文 集中备份"))
        self.window.clear_cache.set(True)
        self.window.recursive.set(True)
        self.window.existing.set("替换已有书签")
        self.window._close()
        reopened_root, reopened = self.new_window()
        self.assertFalse(reopened.backup.get())
        self.assertEqual(reopened.backup_dir.get(), str(self.folder / "中文 集中备份"))
        self.assertTrue(reopened.clear_cache.get())
        self.assertTrue(reopened.recursive.get())
        self.assertEqual(reopened.existing.get(), "替换已有书签")
        reopened_root.update()

    def test_topmost_toggle_calls_native_window_and_persists(self):
        with patch.object(self.root, "attributes", wraps=self.root.attributes) as attributes:
            self.window.topmost.set(True)
            self.root.update()
            self.assertTrue(any(call.args[:2] == ("-topmost", True)
                                for call in attributes.call_args_list))
            self.window.topmost.set(False)
            self.root.update()
            self.assertTrue(any(call.args[:2] == ("-topmost", False)
                                for call in attributes.call_args_list))
            self.window.topmost.set(True)
        self.window._close()
        _, reopened = self.new_window()
        self.assertTrue(reopened.topmost.get())
        self.assertTrue(support.load_settings(self.settings_path)["topmost"])

    def test_close_cancels_poll_callback_before_restarting(self):
        def pending_poll_scripts():
            return [str(self.root.tk.call("after", "info", timer))
                    for timer in self.root.tk.call("after", "info")
                    if "_poll" in str(self.root.tk.call("after", "info", timer))]

        self.assertTrue(pending_poll_scripts())
        self.window._close()
        self.assertEqual(pending_poll_scripts(), [])
        restarted_root, _ = self.new_window()
        restarted_root.update()

    def test_multiple_drop_paths_are_all_previewed_in_gui(self):
        first, first_toc = self.pdf_pair()
        second, second_toc = self.pdf_pair("第二本 空格书.pdf")
        original = {pdf: pdf.read_bytes() for pdf in (first, second)}
        self.window._handle_drop_paths([first_toc, first, second, second_toc])
        self.preview()
        self.assertEqual(len(self.window.items), 2)
        self.assertEqual({(Path(item["pdf_path"]), Path(item["toc_path"]))
                          for item in self.window.items.values()},
                         {(first, first_toc), (second, second_toc)})
        self.assertTrue(all(item["plan"] is not None for item in self.window.items.values()))
        self.assertEqual({pdf: pdf.read_bytes() for pdf in original}, original)

    def test_editor_uses_selected_batch_pdf_and_shared_worker(self):
        first, first_toc = self.pdf_pair()
        second, second_toc = self.pdf_pair("编辑的 第二本.pdf")
        self.window._handle_drop_paths([first, first_toc, second, second_toc])
        second_iid, _ = self.item_for_pdf(second)
        self.window.file_tree.selection_set(second_iid)
        with patch("toc_editor.open_editor", return_value=None) as opened:
            self.window._open_editor()
            opened.assert_called_once_with(self.root, self.window.executor, pdf_path=second,
                                            toc_path=second_toc, on_saved=self.window._editor_saved,
                                            editor_settings=self.window.editor_settings,
                                            on_settings_changed=self.window._editor_settings_changed)
            opened.reset_mock()
            self.window._open_editor(True)
            opened.assert_called_once_with(self.root, self.window.executor, pdf_path=second,
                                            toc_path=None, on_saved=self.window._editor_saved,
                                            editor_settings=self.window.editor_settings,
                                            on_settings_changed=self.window._editor_settings_changed)

    def test_saved_generated_json_retains_batch_and_previews_without_writing(self):
        first, first_toc = self.pdf_pair()
        second = self.folder / "PDF 文件" / "新生成 第二本.pdf"
        make_pdf(second)
        second_toc = self.folder / "新目录" / "新生成 第二本.toc.json"
        original = {pdf: pdf.read_bytes() for pdf in (first, second)}
        self.window._handle_drop_paths([first, first_toc, second])
        self.window.backup.set(False)
        self.window.clear_cache.set(True)
        make_toc(second_toc)
        self.window._editor_saved(second, second_toc)
        self.pump(lambda: not self.window.busy)
        self.assertEqual(len(self.window.plans), 2)
        _, item = self.item_for_pdf(second)
        self.assertEqual(item["toc_path"], second_toc)
        self.assertTrue(item["ready"])
        self.assertFalse(self.window.backup.get())
        self.assertTrue(self.window.clear_cache.get())
        self.assertEqual({pdf: pdf.read_bytes() for pdf in original}, original)

    def test_dnd_binding_and_synthetic_tcl_drop_preserve_spaced_chinese_paths(self):
        pdf, toc = self.pdf_pair()
        original = pdf.read_bytes()
        self.assertTrue(self.root.tk.call("bind", self.root._w, "<<Drop>>"))
        data = self.root.tk.call("format", "%s", self.root.tk.call("list", str(pdf), str(toc)))
        self.assertIsInstance(data, str)
        self.assertEqual(self.root.tk.splitlist(data), (str(pdf), str(toc)))
        self.window._on_drop(SimpleNamespace(data=data))
        self.preview()
        _, item = self.item_for_pdf(pdf)
        self.assertEqual(Path(item["toc_path"]), toc)
        self.assertIsNotNone(item["plan"])
        self.assertEqual(pdf.read_bytes(), original)

    def test_native_drop_list_bookmarks_page_and_log_receive_clicks(self):
        first, first_toc = self.pdf_pair()
        second, second_toc = self.pdf_pair("第二本 空格书.pdf")
        original = {pdf: pdf.read_bytes() for pdf in (first, second)}
        self.root.geometry("1100x860+20000+20000")
        self.root.deiconify()
        self.root.update()

        def assert_visible(widget):
            self.assertTrue(widget.winfo_ismapped())
            self.assertGreater(widget.winfo_width(), 40)
            self.assertGreater(widget.winfo_height(), 50)
            self.assertIs(self.root.winfo_containing(widget.winfo_rootx() + 20,
                                                     widget.winfo_rooty() + 40), widget)

        data = self.root.tk.call("list", *(str(path) for path in (first_toc, first, second, second_toc)))
        target = self.window.file_tree
        x, y = target.winfo_rootx() + 20, target.winfo_rooty() + 40
        self.root.tk.call("tkdnd::olednd::HandleDragEnter", target._w,
                          ("CF_HDROP",), ("copy",), (), x, y, (1,), data)
        self.assertEqual(self.root.tk.call("tkdnd::olednd::HandleDrop", target._w,
                                           (), x, y, "CF_HDROP", data), "copy")
        self.root.update()
        self.assertEqual(len(self.window.items), 2)
        assert_visible(self.window.file_tree)

        self.preview()
        self.root.update()
        self.assertEqual(len(self.window.plans), 2)
        self.assertTrue(self.window.bookmark_rows)
        assert_visible(self.window.bookmark_tree)
        bookmark = next(iter(self.window.bookmark_rows))
        self.window.bookmark_tree.selection_set(bookmark)
        self.pump(lambda: self.window._displayed_page == 2)
        assert_visible(self.window.image_canvas)
        self.assertEqual(self.window._render_photo.get(20, 20), (0, 255, 0))

        self.window.view_tabs.select(1)
        self.root.update()
        assert_visible(self.window.log)
        self.assertIn("开始预览", self.window.log.get("1.0", "end"))
        self.assertEqual({pdf: pdf.read_bytes() for pdf in original}, original)
        self.root.withdraw()

    def test_json_only_drop_uses_current_single_pdf(self):
        pdf = self.folder / "PDF 文件" / "中文 书名.pdf"
        toc = self.folder / "手工目录.json"
        make_pdf(pdf)
        make_toc(toc)
        self.window._handle_drop_paths([pdf])
        self.window._handle_drop_paths([toc])
        self.preview()
        _, item = self.item_for_pdf(pdf)
        self.assertEqual(Path(item["toc_path"]), toc)
        self.assertIsNotNone(item["plan"])

    def test_json_only_drop_after_browsing_another_pdf_targets_current_file(self):
        first, first_toc = self.pdf_pair()
        second, _ = self.pdf_pair("手工改选的 第二本.pdf")
        replacement = self.folder / "异名 手工目录.json"
        make_toc(replacement, title="第二本的手工目录")
        original_first = first.read_bytes()
        original_first_toc = first_toc.read_bytes()
        self.window._handle_drop_paths([first])
        self.preview()
        first_iid, _ = self.item_for_pdf(first)
        self.window.file_tree.selection_set(first_iid)
        self.root.update()
        self.window.pdf.set(str(second))
        self.window.toc.set("")
        self.assertEqual(self.window.pdf.get(), str(second))
        self.window._handle_drop_paths([replacement])
        _, second_item = self.item_for_pdf(second)
        self.assertEqual(len(self.window.items), 1)
        self.assertEqual(Path(second_item["toc_path"]), replacement)
        self.preview()
        _, second_item = self.item_for_pdf(second)
        self.assertEqual(second_item["plan"].rows, [[1, "第二本的手工目录", 2]])
        self.assertEqual(first.read_bytes(), original_first)
        self.assertEqual(first_toc.read_bytes(), original_first_toc)

    def test_drop_two_external_jsons_repairs_folder_rows_without_sidecars(self):
        first = self.folder / "storage" / "第一本.pdf"
        second = first.parent / "第二本.pdf"
        make_pdf(first)
        make_pdf(second)
        first_toc = self.folder / "Downloads" / "第一本.toc.json"
        second_toc = first_toc.parent / "第二本.toc.json"
        make_toc(first_toc)
        make_toc(second_toc)
        original = {pdf: pdf.read_bytes() for pdf in (first, second)}
        self.window._handle_drop_paths([first.parent])
        self.preview()
        self.assertTrue(all(item["plan"] is None for item in self.window.items.values()))
        self.window._handle_drop_paths([first_toc, second_toc])
        self.preview()
        _, first_item = self.item_for_pdf(first)
        _, second_item = self.item_for_pdf(second)
        self.assertEqual(Path(first_item["toc_path"]), first_toc)
        self.assertEqual(Path(second_item["toc_path"]), second_toc)
        self.assertTrue(first_item["checked"])
        self.assertTrue(second_item["checked"])
        self.assertIsNotNone(first_item["plan"])
        self.assertIsNotNone(second_item["plan"])
        self.assertEqual({pdf: pdf.read_bytes() for pdf in original}, original)
        self.assertFalse(first.with_suffix(".toc.json").exists())
        self.assertFalse(second.with_suffix(".toc.json").exists())

    def test_action_buttons_fit_default_and_minimum_client_geometry(self):
        default = support.load_settings(self.folder / "missing-settings.json")["geometry"].split("+")[0]
        default_width, default_height = map(int, default.split("x"))
        for width, height in ((default_width, default_height), self.root.minsize()):
            with self.subTest(size=(width, height)):
                self.root.geometry(f"{width}x{height}+10000+10000")
                self.root.deiconify()
                self.root.update()
                origin_x = self.root.winfo_rootx()
                origin_y = self.root.winfo_rooty()
                for button in (self.window.preview_button, self.window.write_button):
                    x = button.winfo_rootx() - origin_x
                    y = button.winfo_rooty() - origin_y
                    self.assertTrue(button.winfo_ismapped())
                    self.assertGreaterEqual(x, 0)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + button.winfo_width(), self.root.winfo_width())
                    self.assertLessEqual(y + button.winfo_height(), self.root.winfo_height())
        self.root.withdraw()

    def test_batch_list_shows_missing_failed_and_writes_only_checked_pdf(self):
        first, _ = self.pdf_pair()
        second, _ = self.pdf_pair("第二本 空格书.pdf")
        missing = first.parent / "缺少 JSON.pdf"
        failed = first.parent / "无效 JSON.pdf"
        make_pdf(missing)
        make_pdf(failed)
        failed.with_suffix(".toc.json").write_text("{invalid", encoding="utf-8")
        original = {pdf: pdf.read_bytes() for pdf in (first, second, missing, failed)}
        self.window.folder.set(str(first.parent))
        self.window.mode.set("batch")
        self.preview()
        self.assertEqual(len(self.window.items), 4)
        missing_iid, missing_item = self.item_for_pdf(missing)
        failed_iid, failed_item = self.item_for_pdf(failed)
        self.assertIsNone(missing_item["plan"])
        self.assertIsNone(failed_item["plan"])
        self.assertIn("缺少", str(self.window.file_tree.item(missing_iid, "values")))
        self.assertIn("失败", str(self.window.file_tree.item(failed_iid, "values")))
        self.window._set_all_checked(False)
        first_iid, first_item = self.item_for_pdf(first)
        self.window._toggle_item(first_iid)
        self.assertTrue(first_item["checked"])
        self.window._write()
        self.pump(lambda: not self.window.busy)
        with pymupdf.open(first) as document:
            self.assertEqual(document.get_toc(), [[1, "第二页书签", 2]])
        self.assertNotEqual(first.read_bytes(), original[first])
        for pdf in (second, missing, failed):
            self.assertEqual(pdf.read_bytes(), original[pdf])

    def test_changed_write_options_require_another_preview(self):
        pdf, toc = self.pdf_pair()
        self.window._handle_drop_paths([pdf, toc])
        self.preview()
        original = pdf.read_bytes()
        self.window.backup.set(False)
        self.assertEqual(str(self.window.write_button.cget("state")), "disabled")
        self.window._write()
        self.root.update()
        self.assertEqual(pdf.read_bytes(), original)
        self.assertFalse(self.window.busy)
        self.assertFalse((pdf.parent / "_backup").exists())

    def test_change_during_confirmation_rejects_stale_plan_before_worker(self):
        for change in ("pdf", "backup"):
            with self.subTest(change=change):
                self.window._clear_inputs()
                pdf, toc = self.pdf_pair(f"确认对话框 {change}.pdf")
                original = pdf.read_bytes()
                self.window.backup.set(True)
                self.window._handle_drop_paths([pdf, toc])
                self.preview()

                def confirm_after_change(*args, **kwargs):
                    if change == "pdf":
                        self.window.pdf.set(str(self.folder / "另一份 尚未预览.pdf"))
                    else:
                        self.window.backup.set(False)
                    return True

                with patch.object(self.gui.messagebox, "askyesno", side_effect=confirm_after_change), \
                     patch.object(self.window.executor, "submit", wraps=self.window.executor.submit) as submitted:
                    self.window._write()
                    self.assertFalse(self.window.busy)
                    submitted.assert_not_called()
                self.root.update()
                self.assertEqual(pdf.read_bytes(), original)
                self.assertFalse((pdf.parent / "_backup").exists())

    def test_click_bookmark_renders_its_actual_target_page(self):
        pdf, toc = self.pdf_pair()
        original = pdf.read_bytes()
        self.window._handle_drop_paths([pdf, toc])
        self.preview()
        file_iid, _ = self.item_for_pdf(pdf)
        self.window.file_tree.selection_set(file_iid)
        self.root.update()
        bookmark_iid = next(iter(self.window.bookmark_rows))
        self.window.bookmark_tree.selection_set(bookmark_iid)
        self.pump(lambda: self.window._displayed_page == 2)
        self.assertEqual(self.window._render_photo.get(20, 20), (0, 255, 0))
        self.assertEqual(pdf.read_bytes(), original)

    def test_stale_render_completion_does_not_replace_new_selection(self):
        pdf, toc = self.pdf_pair()
        toc.write_text(json.dumps({"version": 1, "bookmarks": [
            {"title": "第一页", "pdf_page": 1},
            {"title": "第二页", "pdf_page": 2},
        ]}, ensure_ascii=False), encoding="utf-8")
        original = pdf.read_bytes()
        first_started = threading.Event()
        second_started = threading.Event()
        release_first = threading.Event()
        release_second = threading.Event()
        self.addCleanup(release_first.set)
        self.addCleanup(release_second.set)
        real_render = support.render_page

        def controlled_render(path, page, *args, **kwargs):
            started, release = ((first_started, release_first) if page == 1
                                else (second_started, release_second))
            started.set()
            if not release.wait(8):
                raise RuntimeError("test render release timed out")
            return real_render(path, page, *args, **kwargs)

        with patch.object(self.gui, "render_page", side_effect=controlled_render):
            self.window._handle_drop_paths([pdf, toc])
            self.preview()
            file_iid, _ = self.item_for_pdf(pdf)
            self.window.file_tree.selection_set(file_iid)
            self.root.update()
            bookmark_ids = {row["pdf_page"]: iid for iid, row in self.window.bookmark_rows.items()}
            self.window.bookmark_tree.selection_set(bookmark_ids[1])
            self.pump(first_started.is_set)
            self.window.bookmark_tree.selection_set(bookmark_ids[2])
            self.root.update()
            release_first.set()
            self.pump(second_started.is_set)
            self.pump(lambda: self.window.events.empty())
            self.assertNotEqual(self.window._displayed_page, 1)
            self.assertIsNone(self.window._render_photo)
            release_second.set()
            self.pump(lambda: self.window._displayed_page == 2)
        self.assertEqual(pdf.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
