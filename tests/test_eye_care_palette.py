"""A visibly deeper eye-care surface must retain readable UI text."""

import unittest

from ui_theme import PALETTES


def luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
              for value in channels]
    return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))


def contrast(first, second):
    low, high = sorted((luminance(first), luminance(second)))
    return (high + .05) / (low + .05)


class EyeCarePaletteTests(unittest.TestCase):
    def test_deeper_green_surfaces_keep_clear_background_panel_and_field_layers(self):
        palette = PALETTES["eye_care"]
        background, panel, field = [luminance(palette[key]) for key in
                                    ("background", "surface", "input_background")]
        self.assertLess(background, .75)
        self.assertGreater(panel - background, .04)
        self.assertGreater(field - panel, .03)
        self.assertLess(field, .85)
        for key in ("background", "surface", "input_background"):
            red, green, blue = (int(palette[key][index:index + 2], 16) for index in (1, 3, 5))
            self.assertGreater(green, red)
            self.assertGreater(red, blue)
            self.assertLess(green - blue, 32)

    def test_normal_hint_disabled_and_review_text_remain_readable(self):
        palette = PALETTES["eye_care"]
        for foreground in ("foreground", "muted", "disabled", "context", "pending"):
            for background in ("background", "surface", "input_background"):
                with self.subTest(foreground=foreground, background=background):
                    self.assertGreaterEqual(contrast(palette[foreground], palette[background]), 4.5)
        for background in ("selected_background", "accent", "accent_active"):
            with self.subTest(background=background):
                self.assertGreaterEqual(contrast(palette["selected_foreground"], palette[background]), 4.5)


if __name__ == "__main__":
    unittest.main()
