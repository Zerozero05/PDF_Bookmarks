"""Off-screen Tk local recognition transactions, cancellation and file guards."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import threading
import time
import unittest
from unittest.mock import patch

import pymupdf

import test_editor_delete_shortcut as fixtures
from session_cache import pdf_identity
from toc_generation import Draft, DraftEntry, generate_toc


class EditorPartialRecognitionTests(unittest.TestCase):
    load = fixtures.DeleteShortcutTests.load
    choose = fixtures.DeleteShortcutTests.choose
    snapshot = fixtures.DeleteShortcutTests.snapshot

    def setUp(self):
        fixtures.DeleteShortcutTests.setUp(self)
        with pymupdf.open(self.pdf) as document:
            page = document[2]
            page.insert_text((50, 80), "1.2 Correct section ............ 2", fontsize=12)
            page.insert_text((50, 110), "1.3 More methods ............... 3", fontsize=12)
            data = document.tobytes()
        self.pdf.write_bytes(data)
        self.pdf_bytes = data
        self.reference_json = self.folder / "reference.json"
        self.reference_json.write_text('{"version":1,"bookmarks":[{"title":"unchanged","pdf_page":1}]}', encoding="utf8")
        self.reference_bytes = self.reference_json.read_bytes()
        self.sample()

    def tearDown(self):
        self.assertEqual(self.reference_json.read_bytes(), self.reference_bytes)
        fixtures.DeleteShortcutTests.tearDown(self)

    def sample(self):
        self.editor.draft = Draft(self.pdf, 6, [
            DraftEntry(1, "Chapter 1 Basics", 1, 1, "高", "保留章证据", True, 2, (.1, .1, .8, .15)),
            DraftEntry(2, "1.1 Prior section", 1, 1, "高", "保留跨页证据", True, 2, (.15, .2, .8, .25)),
            DraftEntry(2, "1.2 Wrong section", 2, 2, "低", "原错字", False, 3, (.08, .09, .8, .145)),
            DraftEntry(2, "1.3 More methods", 3, 3, "高", "保留手工证据", False, 3, (.08, .145, .8, .19)),
            DraftEntry(1, "Chapter 2 Applications", 4, 4, "高", "保留后一页", True, 4, (.1, .1, .8, .15)),
            DraftEntry(2, "2.1 Uses", 4, 4, "高", "保留后一节", True, 4, (.15, .2, .8, .25)),
        ], [2, 3, 4], {"offset": 0}, "原始完整草稿", ["原始总证据"])
        # Existing drafts retain the actual original line boxes, rather than
        # rough rectangles guessed from the text's insertion baseline.
        with pymupdf.open(self.pdf) as document:
            page = document[2]
            lines = [line for block in page.get_text("dict")["blocks"] if block["type"] == 0
                     for line in block["lines"]]
            for entry, line in zip(self.editor.draft.entries[2:4], lines):
                x0, y0, x1, y1 = line["bbox"]
                entry.source_rect = (x0 / page.rect.width, y0 / page.rect.height,
                                     x1 / page.rect.width, y1 / page.rect.height)
        self.editor.draft.source_titles = [entry.title for entry in self.editor.draft.entries]
        self.editor._load_mapping()
        self.editor._refresh(2)
        self.editor.preview_page.set("3")
        self.root.update()

    def candidates(self, *, include_more=True):
        rows = [DraftEntry(1, "目录", None, 3),
                DraftEntry(1, "1.2 Correct section", 2, 2, "高", "局部文字证据", False, 3, (.08, .09, .8, .145))]
        rows[1].source_rect = self.editor.draft.entries[2].source_rect
        if include_more:
            rows.append(deepcopy(self.editor.draft.entries[3]))
        result = Draft(self.pdf, 6, rows, [3], {"offset": 0}, "局部测试", [])
        result.source_titles = [row.title for row in rows]
        return result

    def spin(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("局部重识别没有在时限内完成")

    def show(self, candidates=None):
        self.editor._show_recognition_candidates(candidates or self.candidates(), 3, None, pdf_identity(self.pdf))
        self.assertEqual(self.errors, [])
        return self.editor._review_windows["recognition"]

    def select_record(self, window, record):
        window.tree.selection_set(str(window.diff.records.index(record)))
        window.tree.event_generate("<<TreeviewSelect>>")
        self.root.update()

    def test_accepting_one_page_change_preserves_other_fields_and_one_undo_redo(self):
        self.editor._manual_tokens.add(self.editor._entry_token(self.editor.draft.entries[3]))
        before = self.snapshot()
        before_tokens = [self.editor._entry_token(entry) for entry in self.editor.draft.entries]
        before_numbering = self.editor._history_state()["numbering_sources"]
        count = len(self.editor.history._states)
        window = self.show()
        self.assertEqual(self.snapshot(), before)
        record = next(record for record in window.diff.records if record.kind == "change")
        self.select_record(window, record)
        window.apply_button.invoke()
        self.assertFalse(window.winfo_exists())
        after = self.snapshot()
        self.assertEqual(after["entries"][2]["title"], "1.2 Correct section")
        for index in (0, 1, 3, 4, 5):
            self.assertEqual(after["entries"][index], before["entries"][index])
            self.assertEqual(self.editor._entry_token(self.editor.draft.entries[index]), before_tokens[index])
        self.assertFalse(after["entries"][2]["confirmed"])
        self.assertEqual(len(self.editor.history._states), count + 1)
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.editor._history_state()["numbering_sources"], before_numbering)
        self.editor.redo()
        self.assertEqual(self.snapshot(), after)

    def test_confirmed_or_manual_override_requires_explicit_check(self):
        self.editor.draft.entries[2].confirmed = True
        self.editor._refresh(2)
        before = self.snapshot()
        window = self.show()
        record = next(record for record in window.diff.records if record.kind == "change")
        self.assertTrue(record.protected)
        self.select_record(window, record)
        window.apply_button.invoke()
        self.assertEqual(self.snapshot(), before)
        self.assertIn("保护", window.status.get())
        window.override_protected.set(True)
        window.apply_button.invoke()
        self.assertEqual(self.editor.draft.entries[2].title, "1.2 Correct section")
        self.assertFalse(self.editor.draft.entries[2].confirmed)

    def test_ambiguous_row_is_not_automatically_accepted(self):
        candidates = self.candidates(include_more=False)
        candidates.entries[1].source_rect = None
        before = self.snapshot()
        window = self.show(candidates)
        record = next(record for record in window.diff.records if record.kind == "ambiguous")
        self.select_record(window, record)
        self.assertTrue(window.apply_button.instate(["disabled"]))
        window.apply_button.invoke()
        self.assertEqual(self.snapshot(), before)

    def test_current_page_region_and_force_ocr_only_request_that_page(self):
        self.editor.page_regions = {3: {"rect": (.05, .07, .9, .3), "mode": "double", "split": .5},
                                    4: {"rect": (.1, .1, .8, .8)}}
        self.editor.column_mode.set("双栏")
        calls = []
        def recognize(path, **kwargs):
            calls.append((path, kwargs))
            return self.candidates()
        with patch("toc_editor.generate_toc", side_effect=recognize):
            before = self.snapshot()
            self.editor.recognize_current(force_ocr=True)
            self.spin(lambda: not self.editor.busy and "recognition" in self.editor._review_windows)
        self.assertEqual(len(calls), 1)
        path, options = calls[0]
        self.assertEqual(path, self.pdf)
        self.assertEqual((options["toc_start"], options["toc_end"], options["prefer_existing"]), (3, 3, False))
        self.assertEqual(options["force_ocr_pages"], [3])
        self.assertEqual(options["page_regions"], {3: self.editor.page_regions[3]})
        self.assertEqual(options["column_mode"], "double")
        self.assertIs(options["cancel"], self.editor.cancel)
        self.assertEqual(self.snapshot(), before)

    def test_cancellation_discards_late_result_and_keeps_current_draft(self):
        entered, release = threading.Event(), threading.Event()
        def recognize(path, **kwargs):
            entered.set()
            release.wait(3)
            return self.candidates()
        before = self.snapshot()
        with patch("toc_editor.generate_toc", side_effect=recognize):
            try:
                self.editor.recognize_current()
                self.assertTrue(entered.wait(2))
                self.editor.cancel_operation()
            finally:
                release.set()
            self.spin(lambda: not self.editor.busy)
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn("recognition", self.editor._review_windows)
        self.assertIn("取消", self.editor.status.get())

    def test_stale_draft_never_overwrites_later_edit(self):
        window = self.show()
        record = next(record for record in window.diff.records if record.kind == "change")
        self.editor.draft.entries[0].note = "比较期间另一次有效编辑"
        changed = self.snapshot()
        self.select_record(window, record)
        window.apply_button.invoke()
        self.assertTrue(window.winfo_exists())
        self.assertIn("已变化", window.status.get())
        self.assertEqual(self.snapshot(), changed)

    def test_accepting_only_later_new_candidate_numbers_in_actual_selected_context(self):
        self.editor.draft.entries[2].source_rect = (.1, .1, .8, .125)
        self.editor.draft.entries[3].source_rect = (.1, .6, .8, .625)
        self.editor._refresh(2)
        before = self.snapshot()
        first = deepcopy(self.editor.draft.entries[2])
        first.level = 1
        last = deepcopy(self.editor.draft.entries[3])
        candidates = Draft(self.pdf, 6, [first,
            DraftEntry(1, "Additional A", 2, 2, "高", "新候选A", False, 3, (.1, .3, .8, .325)),
            DraftEntry(1, "Additional B", 2, 2, "高", "新候选B", False, 3, (.1, .4, .8, .425)),
            last], [3], {"offset": 0}, "局部候选", [])
        candidates.source_titles = [entry.title for entry in candidates.entries]
        window = self.show(candidates)
        new = [record for record in window.diff.records if record.kind == "new"]
        self.assertEqual([record.after.title for record in new], ["1.4 Additional A", "1.5 Additional B"])
        self.select_record(window, new[1])
        window.apply_button.invoke()
        self.assertFalse(window.winfo_exists())
        self.assertEqual(self.editor.draft.entries[3].title, "1.4 Additional B")
        self.assertNotIn("1.4 Additional A", [entry.title for entry in self.editor.draft.entries])
        for old, kept in zip(before["entries"], [asdict(entry) for index, entry in enumerate(self.editor.draft.entries) if index != 3]):
            self.assertEqual(kept, old)
        record = self.editor._numbering_sources[id(self.editor.draft.entries[3])]
        self.assertEqual(record[1:3], ["Additional B", "1.4 Additional B"])
        self.editor.undo()
        self.assertEqual(self.snapshot(), before)

    def test_changed_pdf_identity_rejects_comparison_and_adoption(self):
        window = self.show()
        record = next(record for record in window.diff.records if record.kind == "change")
        before = self.snapshot()
        self.pdf.write_bytes(self.pdf_bytes + b"\n% synthetic changed identity\n")
        try:
            self.select_record(window, record)
            window.apply_button.invoke()
            self.assertIn("PDF 已变化", window.status.get())
            self.assertEqual(self.snapshot(), before)
            self.editor._show_recognition_candidates(self.candidates(), 3, None,
                                                    (*pdf_identity(self.pdf)[:-1], "wrong"))
            self.assertIn("PDF 已变化", self.errors[-1])
        finally:
            self.pdf.write_bytes(self.pdf_bytes)

    def test_actual_text_page_recognition_drives_comparison_without_file_writes(self):
        before = self.snapshot()
        source_sha = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        candidates = generate_toc(self.pdf, toc_start=3, toc_end=3, offset=0, column_mode="single")
        self.assertEqual(candidates.method, "文字提取")
        self.assertTrue(any("Correct section" in entry.title for entry in candidates.entries))
        window = self.show(candidates)
        record = next(record for record in window.diff.records
                      if record.kind == "change" and "Correct section" in record.after.title)
        self.assertEqual(record.after.level, 2)
        self.select_record(window, record)
        window.apply_button.invoke()
        self.assertEqual(self.editor.draft.entries[2].title, "1.2 Correct section")
        for index in (0, 1, 3, 4, 5):
            self.assertEqual(asdict(self.editor.draft.entries[index]), before["entries"][index])
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), source_sha)

    def test_real_generated_candidate_is_not_replaced_by_later_manual_title(self):
        candidates = generate_toc(self.pdf, toc_start=3, toc_end=3, offset=0, column_mode="single")
        self.assertEqual(candidates.method, "文字提取")
        for confirmed in (False, True):
            current = self.editor.draft.entries[2]
            current.title = "1.2 Correct section TEST"
            current.confidence, current.note = "手工校正", "实测手工追加，不存在于 PDF"
            current.confirmed = confirmed
            self.editor.draft.source_titles[2] = "1.2 Correct section"
            self.editor._numbering_sources.pop(id(current), None)
            self.editor._manual_tokens.add(self.editor._entry_token(current))
            self.editor._refresh(2)
            before = self.snapshot()
            window = self.show(candidates)
            target = next(record for record in window.diff.records if record.existing_indices == (2,))
            with self.subTest(confirmed=confirmed):
                self.assertEqual(target.kind, "change")
                self.assertTrue(target.protected)
                self.assertEqual(target.before.title, "1.2 Correct section TEST")
                self.assertEqual(target.after.title, "1.2 Correct section")
                self.select_record(window, target)
                window.apply_button.invoke()
                self.assertEqual(self.snapshot(), before)
                self.assertIn("保护", window.status.get())
                window.override_protected.set(True)
                window.apply_button.invoke()
                self.assertEqual(self.editor.draft.entries[2].title, "1.2 Correct section")
                self.assertFalse(self.editor.draft.entries[2].confirmed)
                for index in (0, 1, 3, 4, 5):
                    self.assertEqual(asdict(self.editor.draft.entries[index]), before["entries"][index])
                self.editor.undo()
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
