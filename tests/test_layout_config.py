"""Optional layout preferences retain schema 1 and existing user settings."""

import json
from pathlib import Path
import tempfile
import unittest

import config_manager as config


class LayoutConfigTests(unittest.TestCase):
    def test_missing_layout_fields_keep_old_natural_layout(self):
        settings = config.sanitize_settings({"backup": False, "topmost": True})
        for name in ("main_focus_mode", "editor_focus_mode"):
            self.assertIs(settings[name], False)
        for name in ("main_pane_ratio", "main_preview_ratio", "editor_pane_ratio"):
            self.assertEqual(settings[name], 0)
        for name in ("file_column_widths", "bookmark_column_widths", "editor_column_widths"):
            self.assertEqual(settings[name], {})
        self.assertFalse(settings["backup"])
        self.assertTrue(settings["topmost"])
        self.assertTrue(settings["editor_topmost"])
        self.assertEqual(config.CONFIG_SCHEMA, 1)

    def test_ratio_values_reject_bool_and_out_of_range_without_coercion(self):
        for name in ("main_pane_ratio", "main_preview_ratio", "editor_pane_ratio"):
            for value in (0, 10, 35, 90):
                with self.subTest(name=name, value=value):
                    self.assertEqual(config.sanitize_settings({name: value})[name], value)
            for value in (-1, 1, 9, 91, 100, True, False, 40.0, "40", [], None):
                with self.subTest(name=name, invalid=value):
                    self.assertEqual(config.sanitize_settings({name: value})[name], 0)

    def test_focus_values_are_boolean_only(self):
        for name in ("main_focus_mode", "editor_focus_mode"):
            self.assertTrue(config.sanitize_settings({name: True})[name])
            for value in (0, 1, "yes", None, [], {}):
                with self.subTest(name=name, invalid=value):
                    self.assertIs(config.sanitize_settings({name: value})[name], False)

    def test_column_widths_accept_only_known_symbolic_columns_and_safe_integers(self):
        examples = {
            "file_column_widths": {"checked": 30, "name": 3000, "state": 100},
            "bookmark_column_widths": {"#0": 190, "printed": 60, "pdf": 65},
            "editor_column_widths": {"#0": 230, "title": 400, "level": 45,
                                     "printed": 65, "pdf": 65, "confidence": 85, "confirmed": 85},
        }
        for name, valid in examples.items():
            with self.subTest(name=name):
                actual = config.sanitize_settings({name: dict(valid, invalid=80, **{"#99": 80})})[name]
                self.assertEqual(actual, valid)
                for column in valid:
                    for value in (29, 3001, True, False, 80.0, "80", None, [], {}):
                        with self.subTest(column=column, invalid=value):
                            self.assertNotIn(column, config.sanitize_settings({name: {column: value}})[name])

    def test_layout_roundtrip_and_partial_save_preserve_unknown_and_original_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            original = {"schema": 1, "backup": False, "delete_toc": True,
                        "theme": "eye_care", "future_preference": {"keep": [1, "原值"]}}
            path.write_text(json.dumps(original), encoding="utf-8")
            updates = {"main_focus_mode": True, "editor_focus_mode": False,
                       "main_pane_ratio": 35, "main_preview_ratio": 45, "editor_pane_ratio": 55,
                       "file_column_widths": {"name": 370},
                       "bookmark_column_widths": {"#0": 245},
                       "editor_column_widths": {"title": 460, "#0": 240}}
            config.save_config(updates, path)
            config.update_config({"last_update_check": 1792500000.0}, path)
            restored = config.read_config(path)
            for name, value in {**original, **updates}.items():
                self.assertEqual(restored[name], value, name)
            self.assertEqual(config.load_config(path)["editor_column_widths"], updates["editor_column_widths"])

    def test_layout_defaults_and_sanitized_values_are_independent_copies(self):
        first = config.sanitize_settings({})
        first["editor_column_widths"]["title"] = 400
        self.assertEqual(config.DEFAULT_CONFIG["editor_column_widths"], {})
        self.assertEqual(config.sanitize_settings({})["editor_column_widths"], {})
        original = {"editor_column_widths": {"title": 450}}
        config.sanitize_settings(original)["editor_column_widths"]["title"] = 900
        self.assertEqual(original["editor_column_widths"], {"title": 450})

    def test_strict_migration_validation_rejects_invalid_layout_values(self):
        for settings in ({"main_pane_ratio": True}, {"editor_pane_ratio": 101},
                         {"editor_column_widths": {"unknown": 80}},
                         {"editor_column_widths": {"title": True}}):
            with self.subTest(settings=settings):
                with self.assertRaises(config.ConfigError):
                    config.validate_config(dict(settings, schema=1), 1, strict_values=True)


if __name__ == "__main__":
    unittest.main()
