"""Source-line clips follow normalized displayed-page coordinates, including rotation."""

import hashlib
from pathlib import Path
import tempfile
import unittest

import pymupdf

from source_preview import render_source_crop


class SourcePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="source-row-crop-")
        self.folder = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def make_pdf(self, rotation=0):
        pdf = self.folder / f"quadrants_{rotation}.pdf"
        with pymupdf.open() as document:
            page = document.new_page(width=400, height=600)
            for rectangle, color in (((0, 0, 200, 300), (1, 0, 0)), ((200, 0, 400, 300), (0, 1, 0)),
                                     ((0, 300, 200, 600), (0, 0, 1)), ((200, 300, 400, 600), (1, 1, 0))):
                page.draw_rect(rectangle, color=None, fill=color)
            page.set_rotation(rotation)
            document.save(pdf)
        return pdf

    def test_display_coordinates_and_bounds_for_all_quarter_turn_rotations(self):
        expected = {0: (255, 0, 0), 90: (0, 0, 255), 180: (255, 255, 0), 270: (0, 255, 0)}
        for rotation, color in expected.items():
            with self.subTest(rotation=rotation):
                pdf = self.make_pdf(rotation)
                before = hashlib.sha256(pdf.read_bytes()).hexdigest()
                png = render_source_crop(pdf, 1, (.1, .1, .3, .3), max_width=211, max_height=83)
                image = pymupdf.Pixmap(png)
                self.assertLessEqual(image.width, 211)
                self.assertLessEqual(image.height, 83)
                self.assertGreater(image.width, 0)
                self.assertGreater(image.height, 0)
                self.assertEqual(image.pixel(image.width // 2, image.height // 2), color)
                self.assertEqual(hashlib.sha256(pdf.read_bytes()).hexdigest(), before)
                self.assertEqual(set(self.folder.glob("*")), set(self.folder.glob("*.pdf")))

    def test_invalid_rectangles_pages_and_dimensions_are_rejected(self):
        pdf = self.make_pdf()
        before = pdf.read_bytes()
        for rect in (None, (), (0, 0, 0, .1), (0, .2, .1, .1), (-.1, 0, .1, .2),
                     (0, 0, 1.1, .2), (0, 0, float("nan"), .2), (0, 0, float("inf"), .2),
                     (False, 0, .1, .2), (0, "0", .1, .2)):
            with self.subTest(rect=rect), self.assertRaises(ValueError):
                render_source_crop(pdf, 1, rect)
        for page in (0, -1, True, 1.0, "1", 2):
            with self.subTest(page=page), self.assertRaises(ValueError):
                render_source_crop(pdf, page, (.1, .1, .3, .3))
        for option in ("max_width", "max_height"):
            for value in (0, -1, True, 1.5, "100", 2049):
                with self.subTest(option=option, value=value), self.assertRaises(ValueError):
                    render_source_crop(pdf, 1, (.1, .1, .3, .3), **{option: value})
        self.assertEqual(pdf.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
