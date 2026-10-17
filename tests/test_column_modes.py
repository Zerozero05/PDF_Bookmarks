"""Manual column selection must reach both text extraction and OCR retries."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pymupdf

import toc_generation as generation


def two_columns(*, pages=True, tight=False):
    left = ["Chapter 1 Basics", "Elementary concepts", "Further concepts"]
    right = ["Continued concepts", "Chapter 2 Limits", "Limit concepts"]
    left_end, right_start = (298, 302) if tight else (280, 340)
    return ([(40, 40 + i * 20, left_end, 52 + i * 20,
              title + (f" .... {i + 1}" if pages else ""), .97)
             for i, title in enumerate(left)]
            + [(right_start, 40 + i * 20, 580, 52 + i * 20,
                title + (f" .... {i + 4}" if pages else ""), .97)
               for i, title in enumerate(right)])


def ocr_output(rows):
    return SimpleNamespace(
        boxes=np.array([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                        for x0, y0, x1, y1, _, _ in rows]),
        txts=[row[4] for row in rows], scores=[row[5] for row in rows],
    )


class ColumnModeTests(unittest.TestCase):
    def make_pdf(self, folder, *, scanned=False, outline=False):
        pdf = Path(folder) / "columns.pdf"
        with pymupdf.open() as doc:
            for page_index in range(10):
                page = doc.new_page(width=600, height=800)
                if page_index == 0 and not scanned:
                    for x0, y0, _, _, text, _ in two_columns():
                        page.insert_text((x0, y0 + 10), text, fontsize=9)
            if outline:
                doc.set_toc([[1, "Manual title", 2], [2, "Manual child", 3]])
            doc.save(pdf)
        return pdf

    def test_explicit_auto_preserves_existing_detection(self):
        rows = two_columns()
        expected = generation._group_boxes(rows)
        actual = generation._group_boxes(rows, column_mode="auto", page_width=600)
        self.assertEqual(actual, expected)

    def test_single_bypasses_automatic_column_detection(self):
        rows = two_columns()
        actual = generation._group_boxes(rows, column_mode="single", page_width=600)
        self.assertEqual(actual, generation._baseline_lines(rows))
        self.assertTrue(all(line.right is None and line.column == 0 for line in actual))

    def test_double_handles_tight_gutter_without_merging_baselines(self):
        lines = generation._group_boxes(two_columns(tight=True), column_mode="double", page_width=600)
        self.assertEqual([item[1] for item in generation._parse(lines)], list(range(1, 7)))
        self.assertEqual([line.column for line in lines], [0, 0, 0, 1, 1, 1])

    def test_double_does_not_require_a_page_number_on_each_title(self):
        rows = two_columns(pages=False)
        lines = generation._group_boxes(rows, column_mode="double", page_width=600)
        self.assertEqual([line.text for line in lines], [row[4] for row in rows])
        self.assertEqual([line.column for line in lines], [0, 0, 0, 1, 1, 1])

    def test_centered_header_does_not_move_the_column_boundary(self):
        rows = [(235, 10, 365, 24, "Contents", .99)] + two_columns(pages=False, tight=True)
        lines = generation._group_boxes(rows, column_mode="double", page_width=600)
        self.assertEqual(lines[0].text, "Contents")
        self.assertEqual([line.text for line in lines[1:]], [row[4] for row in rows[1:]])
        self.assertEqual([line.column for line in lines[1:]], [0, 0, 0, 1, 1, 1])

    def test_spanning_boxes_are_retained_and_not_added_to_other_column_titles(self):
        rows = two_columns(pages=False)
        rows.insert(0, (150, 10, 450, 22, "Spanning heading", .99))
        rows.append((250, 130, 350, 142, "Spanning footer", .99))
        lines = generation._group_boxes(rows, column_mode="double", page_width=600)
        self.assertCountEqual([line.text for line in lines], [row[4] for row in rows])
        self.assertEqual(lines[0].text, "Spanning heading")
        self.assertEqual(lines[-1].text, "Spanning footer")

    def test_manual_double_text_pdf_keeps_hierarchy_mapping_and_review_required(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = self.make_pdf(folder)
            original = pdf.read_bytes()
            draft = generation.generate_toc(pdf, toc_start=1, toc_end=1, offset=1, column_mode="double")
            self.assertEqual(pdf.read_bytes(), original)
        self.assertEqual([entry.printed_page for entry in draft.entries[1:]], list(range(1, 7)))
        self.assertEqual([entry.pdf_page for entry in draft.entries[1:]], list(range(2, 8)))
        self.assertEqual([entry.level for entry in draft.entries[1:]], [1, 2, 2, 2, 1, 2])
        self.assertEqual([entry.title for entry in draft.entries[1:]],
                         ["Chapter 1 Basics", "1.1 Elementary concepts", "1.2 Further concepts",
                          "1.3 Continued concepts", "Chapter 2 Limits", "2.1 Limit concepts"])
        self.assertFalse(any(entry.confirmed for entry in draft.entries))

    def test_existing_pdf_bookmarks_are_not_reformatted_by_column_option(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = self.make_pdf(folder, outline=True)
            draft = generation.generate_toc(pdf, prefer_existing=True, column_mode="double")
        self.assertEqual([(entry.level, entry.title, entry.pdf_page) for entry in draft.entries],
                         [(1, "Manual title", 2), (2, "Manual child", 3)])
        self.assertFalse(any(entry.confirmed for entry in draft.entries))

    def test_invalid_column_mode_raises_readable_domain_error(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = self.make_pdf(folder)
            with self.assertRaises(generation.BookmarkError):
                generation.generate_toc(pdf, toc_start=1, toc_end=1, column_mode="triple")

    def test_single_ocr_does_not_retry_separate_columns(self):
        class Engine:
            use_cls = False
            crops = 0

            def __call__(self, image, use_cls=None):
                self.use_cls = use_cls
                if isinstance(image, np.ndarray):
                    self.crops += 1
                return ocr_output(two_columns())

        engine = Engine()
        pix = pymupdf.Pixmap(pymupdf.csRGB, 600, 800, bytes([255]) * 600 * 800 * 3, False)
        with patch.object(generation, "_engine", return_value=engine), \
                patch.object(generation, "_refine_ocr_titles"), \
                patch.object(generation, "_recover_ocr_rows") as recover:
            lines = generation._ocr_lines(pix, column_mode="single")
        self.assertEqual(engine.crops, 0)
        recover.assert_not_called()
        self.assertTrue(all(line.right is None for line in lines))
        self.assertFalse(engine.use_cls)

    def test_forced_double_retries_columns_even_when_full_page_ocr_misses_all_page_numbers(self):
        rows = two_columns(pages=False, tight=True)

        class Engine:
            use_cls = False
            crops = 0

            def __call__(self, image, use_cls=None):
                self.use_cls = use_cls
                if not isinstance(image, np.ndarray):
                    return ocr_output(rows)
                column = self.crops // 2
                self.crops += 1
                local = [(20, 40 + i * 20, 230, 52 + i * 20,
                          title + f" .... {column * 3 + i + 1}", .98)
                         for i, title in enumerate([row[4] for row in rows[column * 3:column * 3 + 3]])]
                return ocr_output(local)

        engine = Engine()
        pix = pymupdf.Pixmap(pymupdf.csRGB, 600, 800, bytes([255]) * 600 * 800 * 3, False)
        with patch.object(generation, "_engine", return_value=engine), \
                patch.object(generation, "_refine_ocr_titles"), \
                patch.object(generation, "_recover_ocr_rows"):
            lines = generation._ocr_lines(pix, column_mode="double")
        self.assertEqual(engine.crops, 4)
        self.assertEqual([item[1] for item in generation._parse(lines)], list(range(1, 7)))
        self.assertFalse(engine.use_cls)

    def test_generate_forwards_manual_layout_to_scanned_page_reader(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = self.make_pdf(folder, scanned=True)
            lines = generation._baseline_lines([(40, 40, 250, 52, "Chapter 1 Basics .... 1", .97)])
            with patch.object(generation, "_ocr_lines", return_value=lines) as reader:
                draft = generation.generate_toc(pdf, toc_start=1, toc_end=1, offset=0, column_mode="single")
        self.assertEqual(reader.call_args.kwargs.get("column_mode"), "single")
        self.assertEqual(draft.entries[1].title, "Chapter 1 Basics")
        self.assertFalse(any(entry.confirmed for entry in draft.entries))


if __name__ == "__main__":
    unittest.main()
