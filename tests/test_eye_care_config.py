"""The additional appearance uses schema 1 and preserves existing preferences."""

import json
from pathlib import Path
import tempfile
import unittest

from config_manager import (CONFIG_SCHEMA, DEFAULT_CONFIG, load_config, read_config,
                            sanitize_settings, save_config)


class EyeCareConfigTests(unittest.TestCase):
    def test_all_appearance_modes_roundtrip_without_changing_schema_or_other_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            original = {"schema": 1, "backup": False, "delete_toc": True,
                        "editor_confirm_multi_delete": False, "unknown_future_setting": "保留"}
            path.write_text(json.dumps(original), encoding="utf-8")
            for name in ("eye_care", "dark", "light", "eye_care"):
                with self.subTest(theme=name):
                    save_config({"theme": name}, path)
                    document = read_config(path)
                    self.assertEqual(document["theme"], name)
                    self.assertEqual(load_config(path)["theme"], name)
                    for key, value in original.items():
                        self.assertEqual(document[key], value)
                    self.assertEqual(document["schema"], CONFIG_SCHEMA)

    def test_legacy_default_and_invalid_modes_keep_existing_fallback(self):
        self.assertEqual(CONFIG_SCHEMA, 1)
        self.assertEqual(DEFAULT_CONFIG["theme"], "light")
        self.assertEqual(sanitize_settings({})["theme"], "light")
        for value in ("system", "sepia", "", True, None):
            with self.subTest(value=value):
                self.assertEqual(sanitize_settings({"theme": value})["theme"], "light")


if __name__ == "__main__":
    unittest.main()
