"""Safety checks use generated PDFs in temporary folders, never a Zotero library."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pymupdf

import bookmarks_core as core


class BookmarkSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zotero-bookmark-tests-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.pdf = self.folder / "中文书籍.pdf"
        self.toc = self.folder / "中文书籍.toc.json"
        self.make_pdf(self.pdf)

    @staticmethod
    def make_pdf(path, bookmarks=None, encrypted=False, user_password="reader-password"):
        with pymupdf.open() as doc:
            for index in range(6):
                page = doc.new_page(width=240, height=320)
                page.insert_text((20, 30), f"Original page {index + 1}")
            doc[1].add_text_annot((30, 65), "原始批注：请保留")
            doc.set_metadata({"title": "测试书籍", "author": "原作者", "subject": "Preserve metadata"})
            doc.set_page_labels([
                {"startpage": 0, "prefix": "封面", "style": "", "firstpagenum": 1},
                {"startpage": 1, "prefix": "", "style": "D", "firstpagenum": 1},
            ])
            if bookmarks:
                doc.set_toc(bookmarks)
            if encrypted:
                doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                         owner_pw="owner-password", user_pw=user_password)
            else:
                doc.save(path)

    def save_toc(self, data=None, bom=False, path=None):
        if data is None:
            data = {
                "version": 1,
                "mapping": {"offset": 1},
                "bookmarks": [{
                    "title": "第一章 基本概念", "page": 1,
                    "children": [{
                        "title": "§1.1 定义", "page": 2,
                        "children": [{"title": "1.1.1 示例", "page": 3}],
                    }],
                }],
            }
        target = path or self.toc
        target.write_text(json.dumps(data, ensure_ascii=False),
                          encoding="utf-8-sig" if bom else "utf-8")
        return target

    @staticmethod
    def content_snapshot(path):
        with pymupdf.open(path) as doc:
            return {
                "pages": doc.page_count,
                "metadata": doc.metadata,
                "labels": doc.get_page_labels(),
                "text": [page.get_text() for page in doc],
                "renders": [hashlib.sha256(page.get_pixmap(alpha=False).samples).hexdigest()
                            for page in doc],
                "annotations": [[(annot.type, annot.info, tuple(annot.rect))
                                 for annot in page.annots()] for page in doc],
                "page_xrefs": [doc.page_xref(index) for index in range(doc.page_count)],
            }

    def test_preview_maps_three_levels_and_never_writes(self):
        self.save_toc(bom=True)
        before = self.pdf.read_bytes()
        before_names = set(self.folder.iterdir())
        plan = core.inspect_pdf(self.pdf, self.toc)
        self.assertEqual(plan.rows, [
            [1, "第一章 基本概念", 2],
            [2, "§1.1 定义", 3],
            [3, "1.1.1 示例", 4],
        ])
        self.assertEqual(plan.existing, [])
        self.assertEqual(plan.page_count, 6)
        self.assertEqual(plan.source_sha256, hashlib.sha256(before).hexdigest())
        self.assertEqual(Path(plan.pdf_path), self.pdf.resolve())
        self.assertEqual(Path(plan.toc_path), self.toc.resolve())
        self.assertEqual([row["printed_page"] for row in plan.preview], [1, 2, 3])
        self.assertEqual([row["pdf_page"] for row in plan.preview], [2, 3, 4])
        self.assertEqual(self.pdf.read_bytes(), before)
        self.assertEqual(set(self.folder.iterdir()), before_names)
        self.assertFalse((self.folder / "_backup").exists())

    def test_write_preserves_path_original_prefix_and_page_content(self):
        self.save_toc()
        original = self.pdf.read_bytes()
        snapshot = self.content_snapshot(self.pdf)
        plan = core.inspect_pdf(self.pdf, self.toc)
        result = core.write_plan(plan)
        self.assertEqual(result["status"], "written")
        self.assertTrue(self.pdf.is_file())
        self.assertTrue(self.pdf.read_bytes().startswith(original))
        backup = Path(result["backup"])
        self.assertEqual(backup.parent, self.folder / "_backup")
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(self.content_snapshot(self.pdf), snapshot)
        with pymupdf.open(self.pdf) as doc:
            self.assertEqual(doc.get_toc(), plan.rows)
        self.assertEqual({p.name for p in self.folder.iterdir() if p.is_file()},
                         {self.pdf.name, self.toc.name})

    def test_piecewise_and_direct_mapping(self):
        self.save_toc({
            "version": 1,
            "mapping": {"segments": [
                {"printed_start": 1, "printed_end": 2, "pdf_start": 2},
                {"printed_start": 3, "printed_end": 4, "pdf_start": 5},
            ]},
            "bookmarks": [
                {"title": "前一段", "page": 2},
                {"title": "后一段", "page": 3},
                {"title": "直接指定 PDF 页", "pdf_page": 1},
            ],
        })
        plan = core.inspect_pdf(self.pdf, self.toc)
        self.assertEqual(plan.rows, [[1, "前一段", 3], [1, "后一段", 5],
                                     [1, "直接指定 PDF 页", 1]])
        self.assertIsNone(plan.preview[2]["printed_page"])

    def test_negative_fixed_offset_and_default_mapping(self):
        for mapping, printed, expected in [({"offset": -1}, 2, 1), (None, 3, 3)]:
            with self.subTest(mapping=mapping):
                data = {"version": 1, "bookmarks": [{"title": "章", "page": printed}]}
                if mapping is not None:
                    data["mapping"] = mapping
                self.save_toc(data)
                self.assertEqual(core.inspect_pdf(self.pdf, self.toc).rows, [[1, "章", expected]])

    def test_existing_bookmarks_detected_and_skipped_by_default(self):
        self.pdf.unlink()
        self.make_pdf(self.pdf, bookmarks=[[1, "已有目录", 2]])
        self.save_toc()
        original = self.pdf.read_bytes()
        plan = core.inspect_pdf(self.pdf, self.toc)
        self.assertEqual(plan.existing, [[1, "已有目录", 2]])
        result = core.write_plan(plan)
        self.assertEqual(result["status"], "skipped")
        self.assertIsNone(result["backup"])
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertFalse((self.folder / "_backup").exists())

    def test_existing_bookmarks_replaced_only_when_explicit(self):
        self.pdf.unlink()
        self.make_pdf(self.pdf, bookmarks=[[1, "已有目录", 2]])
        self.save_toc()
        original = self.pdf.read_bytes()
        plan = core.inspect_pdf(self.pdf, self.toc)
        result = core.write_plan(plan, existing="replace")
        self.assertEqual(result["status"], "written")
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        with pymupdf.open(self.pdf) as doc:
            self.assertEqual(doc.get_toc(), plan.rows)

    def test_repeated_writes_keep_distinct_original_backups(self):
        self.save_toc()
        original = self.pdf.read_bytes()
        first = core.write_plan(core.inspect_pdf(self.pdf, self.toc))
        once_written = self.pdf.read_bytes()
        self.save_toc({"version": 1, "bookmarks": [{"title": "更新后的目录", "pdf_page": 5}]})
        second = core.write_plan(core.inspect_pdf(self.pdf, self.toc), existing="replace")
        self.assertNotEqual(first["backup"], second["backup"])
        self.assertEqual(Path(first["backup"]).read_bytes(), original)
        self.assertEqual(Path(second["backup"]).read_bytes(), once_written)

    def test_invalid_targets_leave_original_untouched(self):
        original = self.pdf.read_bytes()
        for bookmark, mapping in [
            ({"title": "超出页数", "pdf_page": 7}, {"offset": 0}),
            ({"title": "零页", "pdf_page": 0}, {"offset": 0}),
            ({"title": "负映射", "page": 1}, {"offset": -2}),
            ({"title": "未映射", "page": 5}, {"segments": [
                {"printed_start": 1, "printed_end": 2, "pdf_start": 1}]}),
        ]:
            with self.subTest(bookmark=bookmark):
                self.save_toc({"version": 1, "mapping": mapping, "bookmarks": [bookmark]})
                with self.assertRaises(core.BookmarkError):
                    core.inspect_pdf(self.pdf, self.toc)
                self.assertEqual(self.pdf.read_bytes(), original)
                self.assertFalse((self.folder / "_backup").exists())

    def test_strict_schema_rejects_ambiguous_or_mistyped_data(self):
        good = {"version": 1, "bookmarks": [{"title": "章", "page": 1}]}
        invalid = [
            {**good, "unknown": 1},
            {**good, "version": True},
            {**good, "version": "1"},
            {**good, "mapping": {"offset": True}},
            {**good, "mapping": {"offset": 1.5}},
            {**good, "mapping": {"offset": 0, "unknown": 1}},
            {**good, "mapping": {"segments": []}},
            {**good, "mapping": {"segments": [1]}},
            {**good, "mapping": {"offset": 0, "segments": [
                {"printed_start": 1, "printed_end": 2, "pdf_start": 1}]}},
            {**good, "mapping": {"segments": [
                {"printed_start": 1, "printed_end": 3, "pdf_start": 1},
                {"printed_start": 3, "printed_end": 4, "pdf_start": 4}]}},
            {**good, "mapping": {"segments": [
                {"printed_start": True, "printed_end": 2, "pdf_start": 1}]}},
            {**good, "mapping": {"segments": [
                {"printed_start": 1, "printed_end": 2, "pdf_start": 1, "unknown": 1}]}},
            {**good, "bookmarks": [{"title": "章", "page": True}]},
            {**good, "bookmarks": [{"title": "章", "page": "1"}]},
            {**good, "bookmarks": [{"title": "章", "page": 1, "pdf_page": 1}]},
            {**good, "bookmarks": [{"title": "章", "page": 1, "unknown": 1}]},
            {**good, "bookmarks": [{"title": "章", "page": 1, "children": {}}]},
        ]
        original = self.pdf.read_bytes()
        for data in invalid:
            with self.subTest(data=data):
                self.save_toc(data)
                with self.assertRaises(core.BookmarkError):
                    core.inspect_pdf(self.pdf, self.toc)
                self.assertEqual(self.pdf.read_bytes(), original)

    def test_source_change_after_preview_is_rejected(self):
        self.save_toc()
        plan = core.inspect_pdf(self.pdf, self.toc)
        with self.pdf.open("ab") as handle:
            handle.write(b"\n% changed after preview\n")
        changed = self.pdf.read_bytes()
        with self.assertRaises(core.BookmarkError):
            core.write_plan(plan)
        self.assertEqual(self.pdf.read_bytes(), changed)
        self.assertFalse((self.folder / "_backup").exists())

    def test_atomic_replace_failure_keeps_original_and_cleans_temporary(self):
        self._assert_failed_replace_keeps_original(OSError("simulated replace failure"))

    def test_locked_destination_keeps_original_and_backup(self):
        self._assert_failed_replace_keeps_original(PermissionError("simulated locked PDF"))

    def _assert_failed_replace_keeps_original(self, failure):
        self.save_toc()
        original = self.pdf.read_bytes()
        plan = core.inspect_pdf(self.pdf, self.toc)
        real_replace = os.replace

        def refuse_pdf_destination(source, destination):
            if Path(destination).resolve() == self.pdf.resolve():
                raise failure
            return real_replace(source, destination)

        with patch.object(core.os, "replace", side_effect=refuse_pdf_destination):
            with self.assertRaises(core.BookmarkError):
                core.write_plan(plan)
        self.assertEqual(self.pdf.read_bytes(), original)
        backups = list((self.folder / "_backup").glob("*.pdf"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual({p.name for p in self.folder.iterdir() if p.is_file()},
                         {self.pdf.name, self.toc.name})

    def test_encrypted_pdf_rejected_without_modification(self):
        self.pdf.unlink()
        self.make_pdf(self.pdf, encrypted=True)
        self.save_toc()
        original = self.pdf.read_bytes()
        with self.assertRaises(core.BookmarkError):
            core.inspect_pdf(self.pdf, self.toc)
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertFalse((self.folder / "_backup").exists())

    def test_signature_field_pdf_rejected_without_modification(self):
        with pymupdf.open(self.pdf) as doc:
            widget = pymupdf.Widget()
            widget.field_name = "signature_field"
            widget.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
            widget.rect = pymupdf.Rect(20, 100, 200, 150)
            doc[0].add_widget(widget)
            doc.saveIncr()
        self.save_toc()
        original = self.pdf.read_bytes()
        with self.assertRaises(core.BookmarkError):
            core.inspect_pdf(self.pdf, self.toc)
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertFalse((self.folder / "_backup").exists())

    def test_owner_only_encryption_rejected_without_modification(self):
        self.pdf.unlink()
        self.make_pdf(self.pdf, encrypted=True, user_password="")
        self.save_toc()
        original = self.pdf.read_bytes()
        with self.assertRaises(core.BookmarkError):
            core.inspect_pdf(self.pdf, self.toc)
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertFalse((self.folder / "_backup").exists())

    def test_existing_tool_lock_is_preserved(self):
        self.save_toc()
        original = self.pdf.read_bytes()
        plan = core.inspect_pdf(self.pdf, self.toc)
        lock = self.pdf.with_name(f".{self.pdf.name}.bookmarks.lock")
        lock.write_bytes(b"pid=another-process\n")
        with self.assertRaises(core.BookmarkError):
            core.write_plan(plan)
        self.assertEqual(lock.read_bytes(), b"pid=another-process\n")
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertFalse((self.folder / "_backup").exists())

    def test_duplicate_json_keys_are_rejected(self):
        original = self.pdf.read_bytes()
        for text in [
            '{"version":1,"version":1,"bookmarks":[{"title":"章","page":1}]}',
            '{"version":1,"bookmarks":[{"title":"章","title":"另一章","page":1}]}',
        ]:
            with self.subTest(text=text):
                self.toc.write_text(text, encoding="utf-8")
                with self.assertRaises(core.BookmarkError):
                    core.inspect_pdf(self.pdf, self.toc)
                self.assertEqual(self.pdf.read_bytes(), original)
                self.assertFalse((self.folder / "_backup").exists())

    def test_folder_discovery_pairs_and_excludes_backups(self):
        self.save_toc()
        missing = self.folder / "missing.pdf"
        self.make_pdf(missing)
        nested = self.folder / "storage" / "AB12CD34"
        nested.mkdir(parents=True)
        nested_pdf = nested / "另一本书.PDF"
        self.make_pdf(nested_pdf)
        nested_toc = self.save_toc(path=nested / "另一本书.toc.json")
        backup_dir = self.folder / "_backup"
        backup_dir.mkdir()
        self.make_pdf(backup_dir / "旧副本.pdf")
        nested_backup = nested / "_backup"
        nested_backup.mkdir()
        self.make_pdf(nested_backup / "旧副本.pdf")
        top = core.discover_pairs(self.folder)
        self.assertEqual(set(top), {(self.pdf, self.toc), (missing, None)})
        all_pairs = core.discover_pairs(self.folder, recursive=True)
        self.assertEqual(set(all_pairs), {(self.pdf, self.toc), (missing, None),
                                          (nested_pdf, nested_toc)})
        self.assertEqual(core.discover_pairs(backup_dir, recursive=True), [])

    def test_write_without_backup_preserves_content_and_default_cache(self):
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        original = self.pdf.read_bytes()
        snapshot = self.content_snapshot(self.pdf)
        plan = core.inspect_pdf(self.pdf, self.toc)
        result = core.write_plan(plan, backup=False)
        self.assertEqual(result["status"], "written")
        self.assertIsNone(result["backup"])
        self.assertFalse((self.folder / "_backup").exists())
        self.assertTrue(self.pdf.read_bytes().startswith(original))
        self.assertEqual(self.content_snapshot(self.pdf), snapshot)
        self.assertEqual(result["cache_status"], "not_requested")
        self.assertEqual(result["warnings"], [])
        self.assertEqual(cache.read_bytes(), b'{"original_cache":true}')
        with pymupdf.open(self.pdf) as doc:
            self.assertEqual(doc.get_toc(), plan.rows)

    def test_failed_no_backup_write_keeps_original_and_requested_cache(self):
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        original = self.pdf.read_bytes()
        original_names = set(self.folder.iterdir())
        plan = core.inspect_pdf(self.pdf, self.toc)
        with patch.object(core.os, "replace", side_effect=PermissionError("locked destination")):
            with self.assertRaises(core.BookmarkError):
                core.write_plan(plan, backup=False, clear_jasminum_cache=True)
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertEqual(cache.read_bytes(), b'{"original_cache":true}')
        self.assertEqual(set(self.folder.iterdir()), original_names)
        self.assertFalse((self.folder / "_backup").exists())

    def test_custom_nested_chinese_backup_directory_has_exact_original(self):
        self.save_toc()
        original = self.pdf.read_bytes()
        directory = self.folder / "自定义备份" / "数学书籍"
        result = core.write_plan(core.inspect_pdf(self.pdf, self.toc), backup_dir=directory)
        self.assertEqual(result["status"], "written")
        backup = Path(result["backup"])
        self.assertEqual(backup.parent, directory)
        self.assertEqual(backup.read_bytes(), original)
        self.assertFalse((self.folder / "_backup").exists())

    def test_preview_keeps_jasminum_cache_and_all_files_unchanged(self):
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        before = {path: path.read_bytes() for path in self.folder.iterdir()}
        core.inspect_pdf(self.pdf, self.toc)
        self.assertEqual({path: path.read_bytes() for path in self.folder.iterdir()}, before)

    def test_existing_bookmark_skip_does_not_clear_requested_cache(self):
        self.pdf.unlink()
        self.make_pdf(self.pdf, bookmarks=[[1, "已有目录", 2]])
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        original = self.pdf.read_bytes()
        result = core.write_plan(core.inspect_pdf(self.pdf, self.toc), clear_jasminum_cache=True)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertEqual(cache.read_bytes(), b'{"original_cache":true}')
        self.assertFalse((self.folder / "_backup").exists())

    def test_success_clears_only_exact_same_directory_jasminum_cache(self):
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        other_json = self.folder / "other.json"
        other_json.write_bytes(b'{"unrelated":true}')
        nested = self.folder / "storage" / "OTHER123"
        nested.mkdir(parents=True)
        nested_cache = nested / "jasminum-outline.json"
        nested_cache.write_bytes(b'{"another_pdf_cache":true}')
        toc_bytes = self.toc.read_bytes()
        plan = core.inspect_pdf(self.pdf, self.toc)
        result = core.write_plan(plan, clear_jasminum_cache=True)
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["cache_status"], "deleted")
        self.assertEqual(Path(result["cache_path"]), cache)
        self.assertEqual(result["warnings"], [])
        self.assertFalse(cache.exists())
        self.assertEqual(self.toc.read_bytes(), toc_bytes)
        self.assertEqual(other_json.read_bytes(), b'{"unrelated":true}')
        self.assertEqual(nested_cache.read_bytes(), b'{"another_pdf_cache":true}')
        with pymupdf.open(self.pdf) as doc:
            self.assertEqual(doc.get_toc(), plan.rows)

    def test_jasminum_cache_used_as_toc_input_is_protected(self):
        cache = self.save_toc(path=self.folder / "jasminum-outline.json")
        cache_bytes = cache.read_bytes()
        plan = core.inspect_pdf(self.pdf, cache)
        result = core.write_plan(plan, clear_jasminum_cache=True)
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["cache_status"], "failed")
        self.assertTrue(result["warnings"])
        self.assertEqual(cache.read_bytes(), cache_bytes)
        with pymupdf.open(self.pdf) as doc:
            self.assertEqual(doc.get_toc(), plan.rows)

    def test_cache_deletion_permission_error_reports_success_with_warning(self):
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        plan = core.inspect_pdf(self.pdf, self.toc)
        original_unlink = Path.unlink

        def refuse_cache_deletion(path, *args, **kwargs):
            if path == cache:
                raise PermissionError("cache is locked")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", new=refuse_cache_deletion):
            result = core.write_plan(plan, clear_jasminum_cache=True)
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["cache_status"], "failed")
        self.assertTrue(result["warnings"])
        self.assertEqual(cache.read_bytes(), b'{"original_cache":true}')
        with pymupdf.open(self.pdf) as doc:
            self.assertEqual(doc.get_toc(), plan.rows)
        self.assertEqual({path.name for path in self.folder.iterdir() if path.is_file()},
                         {self.pdf.name, self.toc.name, cache.name})

    def test_missing_cache_is_normal_success_without_warning(self):
        self.save_toc()
        result = core.write_plan(core.inspect_pdf(self.pdf, self.toc), clear_jasminum_cache=True)
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["cache_status"], "not_found")
        self.assertEqual(result["warnings"], [])

    def test_unexpected_cache_error_after_replace_keeps_written_status(self):
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        original = self.pdf.read_bytes()
        plan = core.inspect_pdf(self.pdf, self.toc)
        original_unlink = Path.unlink

        def fail_cache_deletion(path, *args, **kwargs):
            if path == cache:
                raise RuntimeError("unexpected cache deletion failure")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", new=fail_cache_deletion):
            result = core.write_plan(plan, clear_jasminum_cache=True)
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["cache_status"], "failed")
        self.assertTrue(result["warnings"])
        self.assertEqual(cache.read_bytes(), b'{"original_cache":true}')
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        self.assertTrue(self.pdf.read_bytes().startswith(original))
        with pymupdf.open(self.pdf) as doc:
            self.assertEqual(doc.get_toc(), plan.rows)

    def test_custom_backup_directory_is_excluded_from_recursive_discovery(self):
        self.save_toc()
        directory = self.folder / "备份集中保存" / "书籍"
        directory.mkdir(parents=True)
        backup_pdf = directory / "原始版本.pdf"
        self.make_pdf(backup_pdf)
        self.save_toc(path=backup_pdf.with_suffix(".toc.json"))
        self.assertEqual(len(core.discover_pairs(self.folder, recursive=True)), 2)
        self.assertEqual(core.discover_pairs(self.folder, recursive=True, exclude_dirs=[directory]),
                         [(self.pdf, self.toc)])
        self.assertEqual(core.discover_pairs(directory, recursive=True, exclude_dirs=[directory]),
                         [(backup_pdf, backup_pdf.with_suffix(".toc.json"))])

    def test_source_folder_can_also_be_selected_as_backup_directory(self):
        self.save_toc()
        original = self.pdf.read_bytes()
        result = core.write_plan(core.inspect_pdf(self.pdf, self.toc), backup_dir=self.folder)
        backup = Path(result["backup"])
        self.assertEqual(result["status"], "written")
        self.assertEqual(backup.parent, self.folder)
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(set(core.discover_pairs(self.folder, recursive=True,
                                                exclude_dirs=[self.folder])),
                         {(self.pdf, self.toc), (backup, None)})

    def test_disabled_backup_with_directory_is_rejected_without_writes(self):
        self.save_toc()
        original = self.pdf.read_bytes()
        directory = self.folder / "不用的备份文件夹"
        with self.assertRaises(core.BookmarkError):
            core.write_plan(core.inspect_pdf(self.pdf, self.toc), backup=False, backup_dir=directory)
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertFalse(directory.exists())
        self.assertFalse((self.folder / "_backup").exists())

    def run_cli(self, *arguments, expected_exit=0, json_report=True):
        entry = Path(core.__file__).with_name("bookmarks.py")
        args = [sys.executable, "-X", "utf8", str(entry), *map(str, arguments)]
        if json_report:
            args.append("--json")
        process = subprocess.run(args, capture_output=True, text=True,
                                 encoding="utf-8", cwd=entry.parent, timeout=30)
        self.assertEqual(process.returncode, expected_exit,
                         f"stdout: {process.stdout}\nstderr: {process.stderr}")
        if json_report:
            self.assertEqual(process.stderr, "")
            return json.loads(process.stdout)
        return process

    def test_cli_dry_run_preserves_cache_and_does_not_create_custom_backup(self):
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        directory = self.folder / "预览不要创建备份"
        original = self.pdf.read_bytes()
        report = self.run_cli("write", self.pdf, "--dry-run", "--backup-dir", directory,
                              "--clear-jasminum-cache")
        self.assertEqual(report["mode"], "preview")
        self.assertEqual(report["results"][0]["status"], "preview")
        self.assertTrue(report["results"][0]["backup_enabled"])
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertEqual(cache.read_bytes(), b'{"original_cache":true}')
        self.assertFalse(directory.exists())
        self.assertFalse((self.folder / "_backup").exists())

    def test_cli_no_backup_write_can_clear_cache(self):
        self.save_toc()
        cache = self.folder / "jasminum-outline.json"
        cache.write_bytes(b'{"original_cache":true}')
        report = self.run_cli("write", self.pdf, "--no-backup", "--clear-jasminum-cache")
        record = report["results"][0]
        self.assertEqual(record["status"], "written")
        self.assertFalse(record["backup_enabled"])
        self.assertIsNone(record["backup"])
        self.assertEqual(record["cache_status"], "deleted")
        self.assertFalse(cache.exists())
        self.assertTrue(self.toc.exists())
        self.assertFalse((self.folder / "_backup").exists())

    def test_cli_batch_custom_backup_excludes_saved_pdf_copies(self):
        self.save_toc()
        directory = self.folder / "批量备份" / "原书"
        directory.mkdir(parents=True)
        backup_pdf = directory / "旧书.pdf"
        self.make_pdf(backup_pdf)
        self.save_toc(path=backup_pdf.with_suffix(".toc.json"))
        report = self.run_cli("batch", self.folder, "--recursive", "--backup-dir", directory)
        self.assertEqual(report["mode"], "preview")
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(Path(report["results"][0]["pdf"]), self.pdf)

    def test_cli_conflicting_backup_flags_rejected_before_file_changes(self):
        self.save_toc()
        original = self.pdf.read_bytes()
        directory = self.folder / "不应创建"
        self.run_cli("write", self.pdf, "--no-backup", "--backup-dir", directory,
                     expected_exit=2, json_report=False)
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertFalse(directory.exists())


if __name__ == "__main__":
    unittest.main()
