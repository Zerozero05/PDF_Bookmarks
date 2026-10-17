"""Unfinished local drafts never modify PDF/TOC inputs or promote confirmation."""

from dataclasses import fields
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from editor_session import DraftStore, UndoHistory, restore_state, snapshot_state
from toc_generation import Draft, DraftEntry


class EditorSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-editor-session-")
        self.folder = Path(self.temporary.name)
        self.pdf = self.folder / "原 PDF.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\nsynthetic untouched input\n")
        self.toc = self.folder / "existing.toc.json"
        self.toc.write_text('{"bookmarks": []}', encoding="utf8")
        self.original_pdf = self.pdf.read_bytes()
        self.original_toc = self.toc.read_bytes()
        self.store = DraftStore(self.folder / "recovery")

    def tearDown(self):
        self.assertEqual(self.pdf.read_bytes(), self.original_pdf)
        self.assertEqual(self.toc.read_bytes(), self.original_toc)
        self.temporary.cleanup()

    def draft(self):
        return Draft(self.pdf, 12, [DraftEntry(1, "第一章 基础", 1, 3, confirmed=True),
            DraftEntry(2, "1.1 基本概念", None, None), DraftEntry(20, "", None, None)],
            [1, 2], {"offset": 2}, "测试", ["请人工核对"], ["第一章基础", "基本概念", ""])

    def state(self):
        return snapshot_state(self.draft(), numbering_sources=["第一章基础", "基本概念", None],
            options={"column_mode": "double", "last_titles": ["第一章 基础", "1.1 基本概念", None]})

    def test_json_roundtrip_preserves_unknown_and_confirmation_and_position_sources(self):
        state = self.state()
        restored, sources, options = restore_state(json.loads(json.dumps(state)))
        self.assertEqual(restored, self.draft())
        self.assertEqual(sources, ["第一章基础", "基本概念", None])
        self.assertEqual(options["column_mode"], "double")
        self.assertEqual([entry.confirmed for entry in restored.entries], [True, False, False])
        self.assertIsNone(restored.entries[1].pdf_page)
        self.assertIsNone(restored.entries[1].printed_page)
        self.assertEqual(restored.entries[2].level, 20)
        self.assertEqual(restored.entries[2].title, "")

    def test_snapshot_and_restore_are_independent_and_default_sources_are_none(self):
        draft = self.draft()
        state = snapshot_state(draft)
        draft.entries[0].title = "后来修改"
        self.assertEqual(state["draft"]["entries"][0]["title"], "第一章 基础")
        restored, sources, options = restore_state(state)
        restored.entries[1].title = "恢复后修改"
        self.assertEqual(state["draft"]["entries"][1]["title"], "1.1 基本概念")
        self.assertEqual(sources, [None, None, None])
        self.assertEqual(options, {})

    def test_source_coordinates_roundtrip_when_declared_by_draft_entry(self):
        if not {"source_page", "source_rect"} <= {item.name for item in fields(DraftEntry)}:
            self.skipTest("DraftEntry source fields are owned by the recognition change")
        draft = self.draft()
        draft.entries[1].source_page = 2
        draft.entries[1].source_rect = (0.1, 0.2, 0.8, 0.4)
        state = snapshot_state(draft)
        self.assertEqual(state["draft"]["entries"][1]["source_rect"], [0.1, 0.2, 0.8, 0.4])
        restored, _, _ = restore_state(state)
        self.assertEqual(restored.entries[1].source_rect, (0.1, 0.2, 0.8, 0.4))

    def test_invalid_states_are_rejected_without_applying_a_mapping(self):
        mutations = [
            lambda s: s.update(schema_version=True),
            lambda s: s["draft"].update(page_count=0),
            lambda s: s["draft"]["entries"][0].update(level=True),
            lambda s: s["draft"]["entries"][0].update(level=0),
            lambda s: s["draft"]["entries"][0].update(level=21),
            lambda s: s["draft"]["entries"][1].update(pdf_page=13),
            lambda s: s["draft"]["entries"][1].update(printed_page=0),
            lambda s: s["draft"]["entries"][1].update(confirmed="true"),
            lambda s: s["draft"]["entries"][1].update(confirmed=True),
            lambda s: s["draft"].update(mapping={"offset": float("nan")}),
            lambda s: s["draft"].update(toc_pages=[13]),
            lambda s: s.update(numbering_sources=["short"]),
            lambda s: s["options"].update(zoom=float("inf")),
            lambda s: s["options"].update({1: "non-string key"}),
            lambda s: s["draft"]["entries"][0].update(unknown=True),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                state = self.state()
                mutation(state)
                with self.assertRaises(ValueError):
                    restore_state(state)

    def test_invalid_source_rectangles_and_pages_are_rejected(self):
        if not {"source_page", "source_rect"} <= {item.name for item in fields(DraftEntry)}:
            self.skipTest("DraftEntry source fields are owned by the recognition change")
        for page, rect in ((0, None), (13, None), (2, (0.1, 0.2, 0.1, 0.3)),
                           (2, (0.1, 0.2, float("nan"), 0.3)), (2, (True, 0.2, 0.4, 0.5)),
                           (2, (0.1, 0.2, 1.1, 0.8)), (2, (0.1, 0.2, 0.8, 1.1))):
            with self.subTest(page=page, rect=rect):
                draft = self.draft()
                draft.entries[1].source_page, draft.entries[1].source_rect = page, rect
                with self.assertRaises(ValueError):
                    snapshot_state(draft)

    def test_store_is_explicit_keyed_and_atomic_and_keeps_imported_files(self):
        self.assertFalse(self.store.exists(self.pdf))
        self.assertFalse(self.store.root_dir.exists())
        target = self.store.save(self.pdf, self.state())
        self.assertEqual(target.parent, self.store.root_dir)
        self.assertEqual(len(target.stem), 64)
        self.assertNotEqual(target, self.pdf)
        self.assertNotEqual(target, self.toc)
        self.assertTrue(self.store.exists(self.pdf))
        self.assertEqual(self.store.load(self.pdf), self.state())
        changed = self.state()
        changed["draft"]["entries"][1]["title"] = "正常再次保存"
        self.assertEqual(self.store.save(self.pdf, changed), target)
        self.assertEqual(self.store.load(self.pdf), changed)
        self.assertEqual(list(self.store.root_dir.iterdir()), [target])
        alternate = self.folder / "another.pdf"
        self.assertNotEqual(self.store.path_for(alternate), target)

    def test_atomic_replace_failure_preserves_previous_recovery(self):
        target = self.store.save(self.pdf, self.state())
        original = target.read_bytes()
        changed = self.state()
        changed["draft"]["entries"][1]["title"] = "新编辑"
        with patch("editor_session.os.replace", side_effect=OSError("synthetic replacement failure")):
            with self.assertRaises(OSError):
                self.store.save(self.pdf, changed)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(list(self.store.root_dir.iterdir()), [target])

    def test_changed_pdf_recovery_is_rejected_without_overwriting_old_record(self):
        target = self.store.save(self.pdf, self.state())
        original = target.read_bytes()
        stat = self.pdf.stat()
        os.utime(self.pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        with self.assertRaisesRegex(ValueError, "PDF 已变化"):
            self.store.load(self.pdf)
        self.assertEqual(target.read_bytes(), original)

    def test_pdf_change_during_atomic_save_keeps_previous_recovery(self):
        target = self.store.save(self.pdf, self.state())
        before = target.read_bytes()
        identity = json.loads(before)["pdf"]
        changed_identity = dict(identity, size=identity["size"] + 1)
        with patch("editor_session._identity", side_effect=[identity, identity, identity, changed_identity]):
            with self.assertRaisesRegex(ValueError, "PDF 已变化"):
                self.store.save(self.pdf, self.state())
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(list(self.store.root_dir.iterdir()), [target])

    def test_save_refuses_to_overwrite_corrupt_record_without_explicit_archive(self):
        target = self.store.save(self.pdf, self.state())
        broken = b'{"broken recovery'
        target.write_bytes(broken)
        for kwargs in ({}, {"replace_invalid": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.store.save(self.pdf, self.state(), **kwargs)
            self.assertEqual(target.read_bytes(), broken)
        self.assertEqual(list(self.store.root_dir.iterdir()), [target])

    def test_save_refuses_to_overwrite_record_for_changed_pdf(self):
        target = self.store.save(self.pdf, self.state())
        original = target.read_bytes()
        stat = self.pdf.stat()
        os.utime(self.pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        with self.assertRaisesRegex(ValueError, "PDF 已变化"):
            self.store.save(self.pdf, self.state())
        self.assertEqual(target.read_bytes(), original)

    def test_archive_keeps_invalid_canonical_until_explicit_replacement(self):
        target = self.store.save(self.pdf, self.state())
        broken = b'{"unfinished recovery'
        target.write_bytes(broken)
        with patch("editor_session.time.time_ns", return_value=123456789):
            backup = self.store.archive(self.pdf)
            second_backup = self.store.archive(self.pdf)
        self.assertEqual(backup.parent, target.parent)
        self.assertEqual(backup.name, f"{target.stem}_123456789.backup.json")
        self.assertNotEqual(backup, second_backup)
        self.assertEqual(backup.read_bytes(), broken)
        self.assertEqual(second_backup.read_bytes(), broken)
        self.assertEqual(target.read_bytes(), broken)
        with self.assertRaises(ValueError):
            self.store.save(self.pdf, self.state())
        self.assertEqual(target.read_bytes(), broken)
        self.store.save(self.pdf, self.state(), replace_invalid=True)
        self.assertEqual(self.store.load(self.pdf), self.state())
        self.assertEqual(backup.read_bytes(), broken)
        self.assertEqual(second_backup.read_bytes(), broken)

    def test_changed_pdf_size_is_also_rejected(self):
        target = self.store.save(self.pdf, self.state())
        record = target.read_bytes()
        stat = self.pdf.stat()
        try:
            self.pdf.write_bytes(self.original_pdf + b"extra")
            os.utime(self.pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "PDF 已变化"):
                self.store.load(self.pdf)
            self.assertEqual(target.read_bytes(), record)
        finally:
            self.pdf.write_bytes(self.original_pdf)

    def test_corrupt_or_invalid_records_are_not_repaired_or_overwritten(self):
        target = self.store.save(self.pdf, self.state())
        valid = target.read_text(encoding="utf8")
        invalid_schema = json.loads(valid)
        invalid_schema["schema_version"] = 2
        invalid_state = json.loads(valid)
        invalid_state["state"]["draft"]["entries"][1]["confirmed"] = True
        duplicate_key = valid.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1', 1)
        for raw in ("{broken", json.dumps(invalid_schema), json.dumps(invalid_state), duplicate_key, "[]"):
            with self.subTest(raw=raw):
                target.write_text(raw, encoding="utf8")
                before = target.read_bytes()
                with self.assertRaises(ValueError):
                    self.store.load(self.pdf)
                self.assertEqual(target.read_bytes(), before)

    def test_mismatched_pdf_state_cannot_replace_recovery(self):
        target = self.store.save(self.pdf, self.state())
        before = target.read_bytes()
        state = self.state()
        state["draft"]["pdf_path"] = str(self.folder / "other.pdf")
        with self.assertRaises(ValueError):
            self.store.save(self.pdf, state)
        self.assertEqual(target.read_bytes(), before)

    def test_unknown_optional_fields_use_dataclass_defaults(self):
        state = self.state()
        state["draft"].pop("source_titles")
        for entry in state["draft"]["entries"]:
            for name in ("confidence", "note", "confirmed", "source_page", "source_rect"):
                entry.pop(name, None)
        draft, _, _ = restore_state(state)
        self.assertFalse(any(entry.confirmed for entry in draft.entries))
        self.assertIsNone(draft.source_titles)


class UndoHistoryTests(unittest.TestCase):
    def test_undo_redo_deduplicate_and_branch(self):
        history = UndoHistory()
        self.assertIsNone(history.undo())
        self.assertIsNone(history.redo())
        history.reset({"title": "A"})
        self.assertFalse(history.record({"title": "A"}))
        self.assertTrue(history.record({"title": "B"}))
        self.assertTrue(history.record({"title": "C"}))
        self.assertEqual(history.undo(), {"title": "B"})
        self.assertEqual(history.undo(), {"title": "A"})
        self.assertIsNone(history.undo())
        self.assertEqual(history.redo(), {"title": "B"})
        self.assertTrue(history.record({"title": "D"}))
        self.assertIsNone(history.redo())
        self.assertEqual(history.undo(), {"title": "B"})

    def test_history_is_bounded_and_reset_is_a_new_baseline(self):
        history = UndoHistory(limit=3)
        for number in range(6):
            history.record({"number": number})
        self.assertEqual(history.undo(), {"number": 4})
        self.assertEqual(history.undo(), {"number": 3})
        self.assertIsNone(history.undo())
        history.reset({"number": 99})
        self.assertFalse(history.can_undo)
        self.assertFalse(history.can_redo)
        self.assertIsNone(history.undo())

    def test_input_and_returned_states_do_not_alias_history(self):
        history = UndoHistory()
        state = {"values": [1]}
        history.reset(state)
        state["values"].append(2)
        history.record({"values": [3]})
        returned = history.undo()
        returned["values"].append(9)
        self.assertEqual(history.redo(), {"values": [3]})
        self.assertEqual(history.undo(), {"values": [1]})

    def test_history_validates_limit_and_json_values(self):
        for limit in (0, -1, True, 2.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                UndoHistory(limit)
        history = UndoHistory(limit=1)
        history.record({"v": 1})
        history.record({"v": 2})
        self.assertIsNone(history.undo())
        with self.assertRaises(ValueError):
            history.record({"v": float("nan")})


if __name__ == "__main__":
    unittest.main()
