"""Manual TOC regions and source geometry use temporary documents only."""

from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pymupdf

import toc_generation as generation


class ManualRegionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-manual-regions-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.originals = {}

    def tearDown(self):
        for pdf, original in self.originals.items():
            self.assertEqual(pdf.read_bytes(), original)

    def pdf(self, pages=None, *, outline=False):
        if pages is None:
            pages = [[(40, 50, "Contents"), (40, 100, "Chapter 1 Basics .... 1"),
                      (60, 130, "1.1 Concepts .... 2"), (40, 160, "Chapter 2 Limits .... 3"),
                      (60, 190, "2.1 Examples .... 4")]]
        target = self.folder / f"source_{len(self.originals)}.pdf"
        with pymupdf.open() as doc:
            for index in range(9):
                page = doc.new_page(width=600, height=800)
                if index < len(pages):
                    for x, y, text in pages[index]:
                        page.insert_text((x, y), text, fontsize=10)
                else:
                    printed = index - len(pages) + 1
                    page.insert_text((40, 80), "Body text with enough extractable words.")
                    page.insert_text((290, 780), str(printed), fontsize=10)
            if outline:
                doc.set_toc([[1, "Original manual title", 2]])
            doc.save(target)
        self.originals[target] = target.read_bytes()
        return target

    def generate(self, pdf, **kwargs):
        return generation.generate_toc(pdf, toc_start=1, toc_end=1, offset=1, **kwargs)

    def test_none_and_empty_regions_preserve_default_result_and_metadata(self):
        pdf = self.pdf()
        expected = self.generate(pdf)
        self.assertEqual(self.generate(pdf, page_regions=None), expected)
        self.assertEqual(self.generate(pdf, page_regions={}), expected)
        self.assertEqual(self.generate(pdf, page_regions={1: {}}), expected)
        self.assertIsNone(expected.entries[0].source_page)
        self.assertIsNone(expected.entries[0].source_rect)
        for entry in expected.entries[1:]:
            self.assertEqual(entry.source_page, 1)
            x0, y0, x1, y1 = entry.source_rect
            self.assertTrue(0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1)

    def test_text_crop_removes_outside_rows_and_preserves_whole_page_coordinates(self):
        pdf = self.pdf([[(40, 35, "Chapter 9 Outside .... 8"),
                         (70, 150, "Chapter 1 Basics .... 1"),
                         (90, 180, "1.1 Concepts .... 2"),
                         (40, 740, "Chapter 8 Footer .... 7")]])
        regions = {1: {"rect": [.1, .1, .9, .5], "mode": "single"}}
        before = deepcopy(regions)
        with patch.object(generation, "_engine", side_effect=AssertionError("text must not use OCR")):
            draft = self.generate(pdf, page_regions=regions)
        self.assertEqual([e.title for e in draft.entries], ["目录", "Chapter 1 Basics", "1.1 Concepts"])
        self.assertEqual([e.pdf_page for e in draft.entries], [1, 2, 3])
        self.assertEqual(regions, before)
        with pymupdf.open(pdf) as doc:
            words = [word for word in doc[0].get_text("words") if 130 < word[1] < 150]
        expected = (min(w[0] for w in words) / 600, min(w[1] for w in words) / 800,
                    max(w[2] for w in words) / 600, max(w[3] for w in words) / 800)
        for actual, coordinate in zip(draft.entries[1].source_rect, expected):
            self.assertAlmostEqual(actual, coordinate, places=5)

    def test_explicit_separator_overrides_single_and_keeps_cross_column_chapter(self):
        rows = [(40, 100, "Chapter 1 Basics .... 1"), (60, 130, "First concept .... 2"),
                (60, 160, "Second concept .... 3"), (410, 100, "Continued .... 4"),
                (410, 130, "Chapter 2 Limits .... 5"), (425, 160, "Last concept .... 6")]
        draft = self.generate(self.pdf([rows]), column_mode="single",
                              page_regions={1: {"rect": [.03, .08, .98, .4], "split": .65, "mode": "single"}})
        self.assertEqual([e.printed_page for e in draft.entries[1:]], list(range(1, 7)))
        self.assertEqual([e.pdf_page for e in draft.entries[1:]], list(range(2, 8)))
        self.assertEqual([e.level for e in draft.entries[1:]], [1, 2, 2, 2, 1, 2])
        self.assertEqual(draft.entries[4].title, "1.3 Continued")
        self.assertEqual(draft.entries[6].title, "2.1 Last concept")
        self.assertLess(draft.entries[3].source_rect[2], .65)
        self.assertGreater(draft.entries[4].source_rect[0], .65)
        self.assertFalse(any(e.confirmed for e in draft.entries))

    def test_per_page_layout_keeps_context_and_source_page_across_page_break(self):
        pdf = self.pdf([[(40, 100, "Chapter 1 Basics .... 1"), (60, 130, "First .... 2")],
                        [(40, 100, "Second .... 3"), (410, 100, "Third .... 4")]])
        draft = generation.generate_toc(pdf, toc_start=1, toc_end=2, offset=2,
            page_regions={1: {"mode": "single"}, 2: {"mode": "double", "split": .6}})
        self.assertEqual([e.title for e in draft.entries[1:]],
                         ["Chapter 1 Basics", "1.1 First", "1.2 Second", "1.3 Third"])
        self.assertEqual([e.source_page for e in draft.entries[1:]], [1, 1, 2, 2])
        self.assertEqual([e.pdf_page for e in draft.entries[1:]], [3, 4, 5, 6])

    def test_regions_on_body_pages_cannot_crop_footer_or_heading_mapping_evidence(self):
        pdf = self.pdf()
        baseline = generation.generate_toc(pdf, toc_start=1, toc_end=1)
        draft = generation.generate_toc(pdf, toc_start=1, toc_end=1,
            page_regions={number: {"rect": [.2, .2, .8, .8], "mode": "double", "split": .5}
                          for number in range(2, 10)})
        self.assertEqual(baseline.mapping, {"offset": 1})
        self.assertEqual(draft, baseline)

    def test_cropped_scan_sources_and_separator_use_full_page_coordinates(self):
        pdf = self.pdf([[]])
        captured = {}

        def recognize(pix, cancel, **options):
            captured.update(x=pix.x, y=pix.y, width=pix.width, height=pix.height, options=options)
            return generation._baseline_lines([(10, 20, 200, 40, "Chapter 1 Basics .... 1", .95),
                                                (20, 60, 220, 80, "1.1 Concepts .... 2", .95)])

        with patch.object(generation, "_ocr_lines", side_effect=recognize):
            draft = self.generate(pdf, page_regions={1: {"rect": [.1, .2, .9, .6], "split": .6}})
        scale = 1900 / 800
        self.assertAlmostEqual(captured["options"]["split"], .6 * 600 * scale - captured["x"])
        self.assertLess(captured["width"], 600 * scale)
        expected = ((captured["x"] + 10) / scale / 600, (captured["y"] + 20) / scale / 800,
                    (captured["x"] + 200) / scale / 600, (captured["y"] + 40) / scale / 800)
        for actual, coordinate in zip(draft.entries[1].source_rect, expected):
            self.assertAlmostEqual(actual, coordinate, places=5)
        self.assertEqual(draft.entries[1].source_page, 1)
        self.assertEqual(draft.entries[1].pdf_page, 2)

    def test_rotated_text_sources_and_cropped_scan_coordinates_follow_displayed_page(self):
        pdf = self.pdf()
        rotated = self.folder / "rotated.pdf"
        with pymupdf.open(pdf) as doc:
            doc[0].set_rotation(90)
            doc.save(rotated)
        self.originals[rotated] = rotated.read_bytes()
        draft = self.generate(rotated)
        with pymupdf.open(rotated) as doc:
            page = doc[0]
            words = [word for word in page.get_text("words") if 80 < word[1] < 100]
            bounds = pymupdf.Rect(min(w[0] for w in words), min(w[1] for w in words),
                                  max(w[2] for w in words), max(w[3] for w in words)) * page.rotation_matrix
            expected = generation._normalized_source(bounds, page.rect)
        for actual, coordinate in zip(draft.entries[1].source_rect, expected):
            self.assertAlmostEqual(actual, coordinate, places=5)

        captured = {}

        def recognize(pix, cancel, **options):
            captured.update(x=pix.x, y=pix.y)
            return generation._baseline_lines([(10, 20, 200, 40, "Chapter 1 Basics .... 1", .95)])

        with patch.object(generation, "_ocr_lines", side_effect=recognize) as reader:
            cropped = self.generate(rotated, page_regions={1: {"rect": [.1, .1, .9, .8]}})
        reader.assert_called_once()
        scale = 1900 / 800
        expected = ((captured["x"] + 10) / scale / 800, (captured["y"] + 20) / scale / 600,
                    (captured["x"] + 200) / scale / 800, (captured["y"] + 40) / scale / 600)
        for actual, coordinate in zip(cropped.entries[1].source_rect, expected):
            self.assertAlmostEqual(actual, coordinate, places=5)

    def test_unknown_ocr_geometry_does_not_invent_a_source_location(self):
        with patch.object(generation, "_ocr_lines", return_value=[
                generation._Line("Chapter 1 Basics .... 1", 20, 30, 10, .95)]):
            draft = self.generate(self.pdf([[]]))
        self.assertIsNone(draft.entries[1].source_page)
        self.assertIsNone(draft.entries[1].source_rect)

    def test_source_metadata_does_not_enter_export_and_import_cannot_invent_it(self):
        pdf = self.pdf()
        draft = self.generate(pdf, page_regions={1: {"mode": "single"}})
        for entry in draft.entries:
            entry.confirmed = True
        target = self.folder / "book.toc.json"
        generation.save_toc(draft, target)
        self.assertNotIn("source_page", target.read_text(encoding="utf8"))
        self.assertNotIn("source_rect", target.read_text(encoding="utf8"))
        imported = generation.load_draft(pdf, target)
        self.assertTrue(all(e.source_page is None and e.source_rect is None for e in imported.entries))
        reused = generation.generate_toc(self.pdf(outline=True), prefer_existing=True,
                                         page_regions={1: {"rect": [.1, .1, .8, .8]}})
        self.assertTrue(all(e.source_page is None and e.source_rect is None for e in reused.entries))

    def test_invalid_regions_are_rejected_without_ocr_or_document_changes(self):
        pdf = self.pdf()
        invalid = [[], {"1": {}}, {True: {}}, {0: {}}, {10: {}}, {1: None},
                   {1: {"other": 1}}, {1: {"mode": "triple"}}, {1: {"mode": None}},
                   {1: {"rect": [0, 0, 0, 1]}}, {1: {"rect": [0, 0, 1]}},
                   {1: {"rect": [-.1, 0, 1, 1]}}, {1: {"rect": [False, 0, 1, 1]}},
                   {1: {"rect": [0, float("nan"), 1, 1]}}, {1: {"split": True}},
                   {1: {"split": 0}}, {1: {"split": 1}}, {1: {"split": float("inf")}},
                   {1: {"rect": [.2, .1, .8, .9], "split": .1}}]
        with patch.object(generation, "_engine", side_effect=AssertionError("invalid input cannot start OCR")):
            for regions in invalid:
                with self.subTest(regions=regions), self.assertRaises(generation.BookmarkError):
                    self.generate(pdf, page_regions=regions)

    def test_wrapped_heading_source_bounds_include_both_observed_rows(self):
        lines = generation._baseline_lines([(10, 10, 90, 20, "Chapter 1", .98),
                                             (10, 30, 220, 40, "Foundations .... 1", .98)])
        sources = []
        parsed = generation._parse(lines, sources=sources)
        self.assertEqual(parsed[0][0], "Chapter 1 Foundations")
        self.assertEqual(sources, [(10, 10, 220, 40)])

    def test_explicit_ocr_separator_is_used_for_column_retries_without_neighbor_overlap(self):
        boxes = [(40, 40, 350, 52, "Chapter 1 Basics .... 1", .97),
                 (40, 70, 350, 82, "First .... 2", .97),
                 (430, 40, 570, 52, "Continued .... 3", .97),
                 (430, 70, 570, 82, "Last .... 4", .97)]

        class Engine:
            use_cls = False
            widths = []

            def __call__(self, image, use_cls=None):
                if isinstance(image, np.ndarray):
                    self.widths.append(image.shape[1])
                    return SimpleNamespace(boxes=[], txts=[], scores=[])
                return SimpleNamespace(boxes=np.array([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                    for x0, y0, x1, y1, _, _ in boxes]), txts=[row[4] for row in boxes],
                    scores=[row[5] for row in boxes])

        engine = Engine()
        pix = pymupdf.Pixmap(pymupdf.csRGB, 600, 800, bytes([255]) * 600 * 800 * 3, False)
        with patch.object(generation, "_engine", return_value=engine), \
                patch.object(generation, "_refine_ocr_titles"), patch.object(generation, "_recover_ocr_rows"):
            lines = generation._ocr_lines(pix, column_mode="single", split=400)
        self.assertEqual(engine.widths, [365, 365, 175, 175])
        self.assertEqual([row[1] for row in generation._parse(lines)], [1, 2, 3, 4])
        self.assertEqual([line.column for line in lines], [0, 0, 1, 1])
        self.assertFalse(engine.use_cls)

    def test_manual_separator_does_not_reinsert_old_ocr_row_merged_across_both_columns(self):
        def output(rows):
            return SimpleNamespace(boxes=np.array([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                for x0, y0, x1, y1, _ in rows]), txts=[row[4] for row in rows], scores=[.97] * len(rows))

        class Engine:
            use_cls = False

            def __call__(self, image, use_cls=None):
                if not isinstance(image, np.ndarray):
                    return output([(235, 10, 450, 22, "Contents"),
                                   (30, 40, 570, 52, "Chapter 1 Basics .... 1 Continued .... 3"),
                                   (30, 70, 570, 82, "First .... 2 Last .... 4"),
                                   (130, 200, 550, 212, "References .... 7")])
                if image.shape[1] == 400:
                    return output([(30, 40, 300, 52, "Chapter 1 Basics .... 1"),
                                   (30, 70, 300, 82, "First .... 2")])
                return output([(20, 40, 160, 52, "Continued .... 3"), (20, 70, 160, 82, "Last .... 4")])

        pix = pymupdf.Pixmap(pymupdf.csRGB, 600, 800, bytes([255]) * 600 * 800 * 3, False)
        with patch.object(generation, "_engine", return_value=Engine()), \
                patch.object(generation, "_refine_ocr_titles"), patch.object(generation, "_recover_ocr_rows"):
            lines = generation._ocr_lines(pix, split=400)
        self.assertEqual([row[1] for row in generation._parse(lines)], [1, 2, 3, 4, 7])
        self.assertEqual([lines[0].text, lines[-1].text], ["Contents", "References .... 7"])
        self.assertEqual(len(lines), 6)

    def test_manual_column_retry_limits_observed_outer_blank_margin_without_moving_separator(self):
        rows = [(100, 40, 280, 52, "Chapter 1 Basics .... 1"),
                (100, 70, 180, 82, "Missing"),
                (380, 40, 550, 52, "Continued .... 3"),
                (380, 70, 550, 82, "Last .... 4")]

        def output(items):
            return SimpleNamespace(boxes=np.array([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                for x0, y0, x1, y1, _ in items]), txts=[row[4] for row in items], scores=[.97] * len(items))

        class Engine:
            use_cls = False

            def __call__(self, image, use_cls=None):
                if not isinstance(image, np.ndarray):
                    return output(rows)
                if image[0, 0, 0] == 50:
                    # A wide empty outer margin changes detector resizing and
                    # loses this whole row, leaving no row crop to repair.
                    selected = [(5, 40, 180, 52, "Chapter 1 Basics .... 1")]
                    if image.shape[1] < 250:
                        selected.append((5, 70, 180, 82, "Missing .... 2"))
                    return output(selected)
                return output([(5, 40, 170, 52, "Continued .... 3"), (5, 70, 170, 82, "Last .... 4")])

            def recognize_txt(self, crops):
                return SimpleNamespace(txts=["Missing"] * len(crops), scores=[.98] * len(crops))

        image = np.full((800, 600, 3), 200, dtype=np.uint8)
        image[:, :320] = 50
        pix = pymupdf.Pixmap(pymupdf.csRGB, 600, 800, image.tobytes(), False)
        with patch.object(generation, "_engine", return_value=Engine()), \
                patch.object(generation, "_refine_ocr_titles"):
            lines = generation._ocr_lines(pix, split=320)
        self.assertEqual([row[1] for row in generation._parse(lines)], [1, 2, 3, 4])
        self.assertTrue(all(line.right == 320 if line.column == 0 else line.left == 320 for line in lines))


if __name__ == "__main__":
    unittest.main()
