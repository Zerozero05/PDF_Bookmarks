"""Image-backed row/page recovery uses synthetic ink and controlled OCR only."""
from types import SimpleNamespace
import threading
import unittest

import cv2
import numpy as np
import pymupdf

import toc_generation as generation


class ScannedRowTests(unittest.TestCase):
    def line(self, text, y=40, **kwargs):
        return generation._Line(text, 20, y, 20, .98, **kwargs)

    def test_bare_numbered_label_is_not_a_title_and_page(self):
        for text in ("1.3.5", "§ 1.3.5", "12．5．2", "1.3.5 .... 7"):
            with self.subTest(text=text):
                self.assertEqual(generation._parse([self.line(text)]), [])
        self.assertEqual(generation._parse([self.line("1.3.5 Limits .... 7")])[0][:2],
                         ("1.3.5 Limits", 7))

    def test_missing_page_does_not_steal_distant_back_matter(self):
        lines = [self.line("13.4 Animation", 40), self.line("Published books .... 357", 140)]
        self.assertEqual(generation._parse(lines)[0][:2], ("Published books", 357))

    def test_bare_label_can_wrap_to_its_adjacent_title(self):
        lines = [self.line("1.3.5", 40), self.line("Limits and sums .... 7", 65)]
        self.assertEqual(generation._parse(lines)[0][:2], ("1.3.5 Limits and sums", 7))

    def test_wrapped_title_can_contain_root_keywords(self):
        for prefix, continuation in (("Chapter 1", "References and sources"),
                                     ("1.2 An introduction to", "Index theory")):
            with self.subTest(prefix=prefix):
                lines = [self.line(prefix, 40), self.line(continuation + " .... 7", 65)]
                self.assertEqual(generation._parse(lines)[0][:2], (prefix + " " + continuation, 7))

    def test_standalone_root_does_not_consume_pending_title(self):
        lines = [self.line("1.2 Incomplete title", 40), self.line("Index .... 7", 65)]
        self.assertEqual(generation._parse(lines)[0][:2], ("Index", 7))

    def test_missing_page_with_leader_does_not_prefix_next_row(self):
        lines = [self.line("13.4 Animation ......", 40), self.line("Index .... 357", 65)]
        self.assertEqual(generation._parse(lines)[0][:2], ("Index", 357))

    def ink(self, *, columns=1):
        image = np.full((125, 300 * columns, 3), 255, dtype=np.uint8)
        for col in range(columns):
            start = col * 300
            for y in (40, 85):
                image[y - 8:y + 9, start + 20:start + 100] = 0
                image[y - 8:y + 9, start + 272:start + 282] = 0
                for x in range(start + 115, start + 260, 8):
                    cv2.circle(image, (x, y), 1, (0, 0, 0), -1)
        return pymupdf.Pixmap(pymupdf.csRGB, image.shape[1], image.shape[0], image.tobytes(), False)

    def engine(self, titles, scores=None):
        calls = []
        def recognize(crops):
            calls.append([crop.shape for crop in crops])
            self.assertEqual(len(crops), len(titles))
            return SimpleNamespace(txts=titles, scores=scores or [.99] * len(titles))
        return SimpleNamespace(recognize_txt=recognize), calls

    def test_missing_rows_and_remote_pages_come_from_separate_same_row_crops(self):
        engine, calls = self.engine(["Chapter 1 Alpha", "1", "1.1 Basics", "12"])
        lines = generation._recover_leader_rows(self.ink(), [self.line("Chapter 1 Alpha")], engine, None)
        self.assertEqual([row[:2] for row in generation._parse(lines)],
                         [("Chapter 1 Alpha", 1), ("1.1 Basics", 12)])
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]), 4)
        self.assertTrue(all(shape[1] < 120 for shape in calls[0]))
        self.assertTrue(all(line.rect is not None for line in lines))

    def test_low_confidence_or_non_numeric_page_does_not_invent_entry(self):
        engine, _ = self.engine(["Chapter 1 Alpha", "?", "1.1 Basics", "12"], [.99, .99, .99, .4])
        original = [self.line("Chapter 1 Alpha")]
        self.assertEqual(generation._recover_leader_rows(self.ink(), original, engine, None), original)

    def test_existing_reliable_title_page_and_numbering_are_not_replaced(self):
        for score in (.98, .6):
            with self.subTest(original_score=score):
                engine, _ = self.engine(["Chapter 2 Wrong", "1", "1.1 Other", "99"])
                original = [self.line("Chapter 1 Alpha .... 1"), self.line("1.1 Basics .... 12", 85)]
                for row in original:
                    row.score = score
                result = generation._recover_leader_rows(self.ink(), original, engine, None)
                self.assertEqual(generation._parse(result), generation._parse(original))

    def test_same_label_and_page_allow_better_image_reread_of_low_score_title(self):
        engine, _ = self.engine(["1.1 Alpha", "12", "1.2 Next", "13"], [.94, .99, .94, .99])
        original = [self.line("1.1 XAlpha .... 12")]
        original[0].score = .6
        result = generation._recover_leader_rows(self.ink(), original, engine, None)
        self.assertEqual([row[:2] for row in generation._parse(result)],
                         [("1.1 Alpha", 12), ("1.2 Next", 13)])
        self.assertEqual(result[0].score, .6)
        self.assertEqual(result[0].x, original[0].x)
        self.assertEqual(result[0].rect, original[0].rect)

    def test_thin_horizontal_character_strokes_stay_in_recovered_title_crop(self):
        pix = self.ink()
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
        image[32:49, 20:100] = 255
        image[32:49, 45:100] = 0
        for y in (33, 39, 46):
            image[y:y + 2, 20:39] = 0
        pix = pymupdf.Pixmap(pymupdf.csRGB, image.shape[1], image.shape[0], image.tobytes(), False)
        engine, _ = self.engine(["Three angles", "12", "Another title", "13"])
        result = generation._recover_leader_rows(pix, [self.line("Three angles")], engine, None)
        self.assertLessEqual(result[0].x, 20, "Separated horizontal strokes must not be trimmed off")

    def test_low_score_complete_title_is_not_replaced_by_pure_truncation(self):
        engine, _ = self.engine(["Alpha", "12", "Another title", "13"])
        original = [self.line("XAlpha .... 12")]
        original[0].score = .6
        result = generation._recover_leader_rows(self.ink(), original, engine, None)
        self.assertEqual(generation._parse(result)[0][:2], ("XAlpha", 12))

    def test_known_columns_do_not_cross_pair_pages(self):
        engine, calls = self.engine(["Chapter 1 Alpha", "1", "1.1 Basics", "2",
                                     "Chapter 2 Beta", "20", "2.1 Limits", "21"])
        lines = [self.line("Chapter 1 Alpha", column=0, left=0, right=300),
                 self.line("Chapter 2 Beta", column=1, left=300, right=600)]
        result = generation._recover_leader_rows(self.ink(columns=2), lines, engine, None)
        self.assertEqual([row[1] for row in generation._parse(result)], [1, 2, 20, 21])
        self.assertEqual([line.column for line in result], [0, 0, 1, 1])
        self.assertEqual(len(calls), 1)

    def test_ambiguous_unclassified_columns_keep_original_rows(self):
        engine, calls = self.engine([])
        lines = [self.line("1.1 Alpha")]
        self.assertEqual(generation._recover_leader_rows(self.ink(columns=2), lines, engine, None), lines)
        self.assertEqual(calls, [])

    def test_cancel_before_row_recovery_does_not_call_recognizer(self):
        engine, calls = self.engine([])
        cancel = threading.Event()
        cancel.set()
        with self.assertRaisesRegex(generation.BookmarkError, "取消"):
            generation._recover_leader_rows(self.ink(), [self.line("1.1 Alpha")], engine, cancel)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
