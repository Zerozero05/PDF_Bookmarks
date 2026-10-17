"""Regression contracts for column order, pages, and hierarchy."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pymupdf
import toc_generation as generation
from toc_generation import _group_boxes, _parse, generate_toc


LEFT = ["Chapter 1 Integration .... 1", "Basic sets .... 2", "Measurability .... 3"]
RIGHT = ["Simple functions .... 4", "Chapter 2 Measures .... 5", "Positive measures .... 6"]


def boxes(stagger=0):
    return ([(40, 40 + i * 20, 280, 52 + i * 20, text, 1.) for i, text in enumerate(LEFT)]
            + [(340, 40 + i * 20 + stagger, 580, 52 + i * 20 + stagger, text, 1.) for i, text in enumerate(RIGHT)])


class ColumnRecognitionTests(unittest.TestCase):
    def recognize_text_pages(self, pages):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / "columns.pdf"
            with pymupdf.open() as doc:
                for rows in pages:
                    page = doc.new_page(width=600, height=800)
                    for x, y, text in rows:
                        page.insert_text((x, y), text, fontsize=9)
                for _ in range(15):
                    doc.new_page().insert_text((40, 50), "Body")
                doc.save(pdf)
            original = pdf.read_bytes()
            draft = generate_toc(pdf, toc_start=1, toc_end=len(pages), offset=0)
            self.assertEqual(pdf.read_bytes(), original)
            self.assertFalse(any(entry.confirmed for entry in draft.entries))
            return draft

    def test_aligned_columns_keep_titles_and_pages_separate(self):
        parsed = _parse(_group_boxes(boxes()))
        self.assertEqual([item[0] for item in parsed],
                         ["Chapter 1 Integration", "Basic sets", "Measurability",
                          "Simple functions", "Chapter 2 Measures", "Positive measures"])
        self.assertEqual([item[1] for item in parsed], list(range(1, 7)))

    def test_staggered_columns_read_down_left_then_right(self):
        parsed = _parse(_group_boxes(boxes(stagger=9)))
        self.assertEqual([item[1] for item in parsed], list(range(1, 7)))

    def test_single_column_remote_page_boxes_are_not_two_columns(self):
        rows = []
        for i, title in enumerate(["Chapter 1 Integration", "Basic sets", "Measurability"]):
            rows += [(40, 40+i*20, 175, 52+i*20, title, 1.),
                     (550, 40+i*20, 570, 52+i*20, str(i+1), 1.)]
        parsed = _parse(_group_boxes(rows))
        self.assertEqual(len(parsed), 3)
        self.assertEqual([item[1] for item in parsed], [1, 2, 3])

    def test_text_pdf_cross_column_chapter_context_and_numbering(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / "columns.pdf"
            with pymupdf.open() as doc:
                page = doc.new_page(width=600, height=800)
                for texts, x in ((LEFT, 40), (RIGHT, 340)):
                    for i, text in enumerate(texts):
                        page.insert_text((x, 55+i*20), text, fontsize=9)
                for _ in range(9):
                    doc.new_page().insert_text((40, 50), "Body")
                doc.save(pdf)
            original = pdf.read_bytes()
            draft = generate_toc(pdf, toc_start=1, toc_end=1, offset=0)
            self.assertEqual(pdf.read_bytes(), original)
            entries = draft.entries[1:]
            self.assertEqual([entry.printed_page for entry in entries], list(range(1, 7)))
            self.assertEqual([entry.level for entry in entries], [1, 2, 2, 2, 1, 2])
            self.assertEqual([entry.title for entry in entries],
                             ["Chapter 1 Integration", "1.1 Basic sets", "1.2 Measurability",
                              "1.3 Simple functions", "Chapter 2 Measures", "2.1 Positive measures"])
            self.assertTrue(all(not entry.confirmed for entry in draft.entries))

    def test_fake_ocr_entry_uses_columns_and_restores_engine_state(self):
        rows = boxes(stagger=7)
        output = SimpleNamespace(
            boxes=np.array([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                            for x0, y0, x1, y1, _, _ in rows]),
            txts=[row[4] for row in rows], scores=[.97] * len(rows),
        )

        class Engine:
            use_cls = False

            def __call__(self, image, use_cls=None):
                self.use_cls = use_cls
                if isinstance(image, np.ndarray):
                    return SimpleNamespace(boxes=None, txts=None, scores=None)
                return output

        engine = Engine()
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / "scanned.pdf"
            with pymupdf.open() as doc:
                for _ in range(10):
                    doc.new_page(width=600, height=800)
                doc.save(pdf)
            original = pdf.read_bytes()
            with patch.object(generation, "_engine", return_value=engine):
                draft = generate_toc(pdf, toc_start=1, toc_end=1, offset=1)
            self.assertEqual(pdf.read_bytes(), original)
        self.assertFalse(engine.use_cls)
        self.assertEqual(draft.method, "本地 OCR")
        self.assertEqual([entry.printed_page for entry in draft.entries[1:]], list(range(1, 7)))
        self.assertEqual([entry.pdf_page for entry in draft.entries[1:]], list(range(2, 8)))
        self.assertEqual([entry.level for entry in draft.entries[1:]], [1, 2, 2, 2, 1, 2])
        self.assertEqual([entry.title for entry in draft.entries[1:]],
                         ["Chapter 1 Integration", "1.1 Basic sets", "1.2 Measurability",
                          "1.3 Simple functions", "Chapter 2 Measures", "2.1 Positive measures"])
        self.assertFalse(any(entry.confirmed for entry in draft.entries))

    def test_chapter_and_missing_section_numbers_continue_across_pages_and_columns(self):
        pages = [
            [(40, 55+i*20, text) for i, text in enumerate(LEFT)]
            + [(340, 55+i*20, text) for i, text in enumerate(RIGHT)],
            [(40, 55+i*20, text) for i, text in enumerate([
                "Continuation one .... 7", "Continuation two .... 8", "Chapter 3 Limits .... 9"])]
            + [(340, 55+i*20, text) for i, text in enumerate([
                "Sequences .... 10", "Convergence .... 11", "Exercises .... 12"])],
        ]
        draft = self.recognize_text_pages(pages)
        self.assertEqual([entry.printed_page for entry in draft.entries[1:]], list(range(1, 13)))
        self.assertEqual([entry.level for entry in draft.entries[1:]],
                         [1, 2, 2, 2, 1, 2, 2, 2, 1, 2, 2, 2])
        self.assertEqual([entry.title for entry in draft.entries[7:]],
                         ["2.2 Continuation one", "2.3 Continuation two", "Chapter 3 Limits",
                          "3.1 Sequences", "3.2 Convergence", "3.3 Exercises"])

    def test_right_column_position_is_not_indent_but_local_nested_indent_is(self):
        draft = self.recognize_text_pages([[
            (40, 55, "Chapter 1 Integration .... 1"),
            (60, 75, "Section 1 Basics .... 2"),
            (90, 95, "A nested example .... 3"),
            (60, 115, "A sibling section .... 4"),
            (340, 55, "Continued section .... 5"),
            (370, 75, "A continued nested example .... 6"),
            (340, 95, "Another sibling section .... 7"),
            (340, 115, "Chapter 2 Measures .... 8"),
        ]])
        self.assertEqual([entry.level for entry in draft.entries[1:]], [1, 2, 3, 2, 2, 3, 2, 1])
        self.assertEqual(draft.entries[5].title, "1.3 Continued section")
        self.assertIn("缩进", draft.entries[6].note)
        self.assertEqual(draft.entries[7].title, "1.4 Another sibling section")

    def test_single_column_section_numbers_and_remote_pages_stay_together(self):
        titles = ["Chapter 1 Integration", "Section 1 Basics", "1.2 Measurability",
                  "1.2.1 Detail", "Section 2 Limits"]
        rows = []
        for i, title in enumerate(titles):
            rows += [(40, 40+i*20, 245, 52+i*20, title, 1.),
                     (550, 40+i*20, 570, 52+i*20, str(10+i), 1.)]
        lines = _group_boxes(rows)
        self.assertEqual([line.column for line in lines], [0] * len(titles))
        self.assertEqual([(title, page) for title, page, _, _ in _parse(lines)],
                         list(zip(titles, range(10, 15))))

    def test_pending_wrapped_heading_does_not_leak_into_next_column(self):
        rows = boxes()
        rows.append((40, 110, 280, 122, "Chapter 8 Incomplete heading", 1.))
        parsed = _parse(_group_boxes(rows))
        self.assertEqual([item[0] for item in parsed],
                         ["Chapter 1 Integration", "Basic sets", "Measurability",
                          "Simple functions", "Chapter 2 Measures", "Positive measures"])
        self.assertEqual([item[1] for item in parsed], list(range(1, 7)))

    def test_pending_wrapped_heading_still_joins_inside_its_column(self):
        rows = boxes()
        rows[0] = (40, 25, 280, 37, "Chapter 1", 1.)
        rows.insert(1, (40, 40, 280, 52, "Integration .... 1", 1.))
        self.assertEqual([item[0] for item in _parse(_group_boxes(rows))],
                         ["Chapter 1 Integration", "Basic sets", "Measurability",
                          "Simple functions", "Chapter 2 Measures", "Positive measures"])

    def test_spanning_header_does_not_mix_aligned_columns(self):
        lines = _group_boxes([(40, 10, 580, 22, "Contents", 1.)] + boxes())
        self.assertEqual(lines[0].text, "Contents")
        self.assertEqual([line.column for line in lines[1:]], [0, 0, 0, 1, 1, 1])
        self.assertEqual([item[1] for item in _parse(lines)], list(range(1, 7)))

    def test_title_refinement_crop_cannot_select_longer_neighbor_column_leader(self):
        image = np.full((100, 600, 3), 255, dtype=np.uint8)
        image[50:70, 40:130] = 0
        image[50:70, 340:420] = 0
        for x in range(150, 260, 10):
            image[60:62, x:x+2] = 0
        for x in range(440, 595, 8):
            image[60:62, x:x+2] = 0
        lines = [generation._Line("Basics ...... 1", 40, 60, 20, .8, column=0, left=40, right=300),
                 generation._Line("Limits ...... 2", 340, 60, 20, .8, column=1, left=300, right=600)]
        left_crop = generation._title_crop(image, lines[0])
        right_crop = generation._title_crop(image, lines[1])
        self.assertIsNotNone(left_crop)
        self.assertIsNotNone(right_crop)
        self.assertEqual(left_crop.shape[1], 114)
        self.assertEqual(right_crop.shape[1], 104)
        received = []

        def rotate(crops):
            received.extend(crop.shape for crop in crops)
            return crops, None

        engine = SimpleNamespace(
            cls_and_rotate=rotate,
            recognize_txt=lambda crops: SimpleNamespace(txts=["Basic sets", "Limit sets"], scores=[.999, .999]),
        )
        pix = pymupdf.Pixmap(pymupdf.csRGB, 600, 100, image.tobytes(), False)
        generation._refine_ocr_titles(pix, lines, engine, None)
        self.assertEqual(received, [left_crop.shape, right_crop.shape])
        self.assertEqual([item[1] for item in _parse(lines)], [1, 2])



    def test_column_retry_preserves_original_complete_page(self):
        old = generation._Line("Basic sets .... 12", 30, 50, 12, .8, right=300)
        retry = generation._Line("Other title .... 99", 30, 50, 12, .99, right=300)
        lines = generation._merge_ocr_lines([old], [retry])
        self.assertEqual(_parse(lines)[0][:2], ("Basic sets", 12))

    def test_column_retry_adds_missing_row_and_completes_partial_row(self):
        partial = generation._Line("Basic sets", 30, 50, 12, .8, right=300)
        full = generation._Line("Basic sets .... 12", 30, 50, 12, .99, right=300)
        next_row = generation._Line("Measures .... 13", 30, 75, 12, .98, right=300)
        self.assertEqual([p[:2] for p in _parse(generation._merge_ocr_lines([partial], [full, next_row]))],
                         [("Basic sets", 12), ("Measures", 13)])

    def test_incomplete_row_retry_rejects_changed_label_page_and_low_score(self):
        cases = [("Chapter 1 Basics", "Chapter 2 Basics .... 12", .99),
                 (".... 12", "Basic sets .... 13", .99),
                 ("Basic sets", "Basic sets .... 12", .5),
                 ("Basic sets", "Unrelated title .... 12", .99)]
        for original, candidate, score in cases:
            with self.subTest(original=original, candidate=candidate):
                line = generation._Line(original, 30, 50, 12, .9, right=300)
                engine = SimpleNamespace(recognize_txt=lambda crops: SimpleNamespace(txts=[candidate], scores=[score]))
                lines = [line]
                generation._recover_ocr_rows(np.full((100, 320, 3), 255, dtype=np.uint8), lines, engine, None)
                self.assertEqual(lines[0].text, original)

    def test_incomplete_row_retry_keeps_low_confidence_and_cancel_boundary(self):
        line = generation._Line("Basic sets", 30, 50, 12, .85, right=300)
        engine = SimpleNamespace(recognize_txt=lambda crops: SimpleNamespace(txts=["Basic sets .... 12"], scores=[.95]))
        lines = [line]
        image = np.full((100, 320, 3), 255, dtype=np.uint8)
        generation._recover_ocr_rows(image, lines, engine, None)
        self.assertEqual(_parse(lines)[0][:2], ("Basic sets", 12))
        self.assertEqual(lines[0].score, .85)
        import threading
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(generation.BookmarkError):
            generation._recover_ocr_rows(image, [line], engine, cancel)


    def test_column_retry_cannot_change_partial_section_chapter_or_known_page(self):
        cases = [("§1.1 Basics", "§1.11 Basics .... 12"),
                 ("Chapter 1 Basics", "Chapter 2 Basics .... 12"),
                 (".... 12", "Basics .... 13"),
                 ("Basic sets", "Unrelated title .... 12")]
        for original, retry in cases:
            with self.subTest(original=original):
                old = generation._Line(original, 30, 50, 12, .8)
                new = generation._Line(retry, 30, 50, 12, .99)
                self.assertEqual(generation._merge_ocr_lines([old], [new])[0].text, original)

    def test_single_column_appendix_labels_and_math_fragments_are_not_columns(self):
        for labels in (["Appendix I", "Appendix II"], ["L 2", "H 1"]):
            with self.subTest(labels=labels):
                rows = []
                for i, label in enumerate(labels):
                    rows.extend([(40, 40+i*20, 130, 52+i*20, label, 1.),
                                 (200, 40+i*20, 570, 52+i*20, f"Basics .... {10+i}", 1.)])
                lines = _group_boxes(rows)
                self.assertEqual(len(lines), 2)
                self.assertEqual([p[1] for p in _parse(lines)], [10, 11])

    def test_column_retry_preserves_page_behind_unicode_leaders(self):
        for text in ("…193", "⋯193", "．193", "... 193"):
            with self.subTest(text=text):
                old = generation._Line(text, 250, 50, 12, .8)
                good = generation._Line("Representation theorem .... 193", 30, 50, 12, .99)
                wrong = generation._Line("Representation theorem .... 194", 30, 50, 12, .99)
                self.assertEqual(generation._merge_ocr_lines([old], [wrong])[0].text, text)
                self.assertEqual(_parse(generation._merge_ocr_lines([old], [good]))[0][1], 193)


if __name__ == "__main__":
    unittest.main()
