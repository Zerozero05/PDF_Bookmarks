"""Configuration compatibility uses only isolated fixture copies and backups."""

import concurrent.futures
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import config_manager as config
import gui_support


FIXTURES = Path(__file__).parent / "fixtures" / "config"


def to_schema_2(document):
    document["recent_directory"] = document.pop("last_dir", "")
    document["schema"] = 2
    return document


def to_schema_3(document):
    document["last_dir"] = document.pop("recent_directory", "")
    document["schema"] = 3
    return document


class ConfigCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pdf-config-compatibility-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.path = self.folder / "用户 设置" / "settings.json"
        self.backups = self.folder / "transaction" / "backup" / "config"

    def fixture(self, name):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes((FIXTURES / name).read_bytes())
        return json.loads(self.path.read_bytes()) if "malformed_examples" not in name else None

    def test_schema_remains_independent_of_application_release(self):
        self.assertEqual(config.CONFIG_SCHEMA, 1)
        self.assertEqual(config.MIGRATIONS, {})
        self.assertEqual(config.DEFAULT_CONFIG, gui_support.SETTINGS_DEFAULTS)

    def test_current_full_fixture_retains_custom_values(self):
        original = self.fixture("schema_1_full.json")
        actual = gui_support.load_settings(self.path)
        for name in config.DEFAULT_CONFIG:
            self.assertEqual(actual[name], original[name], name)
        self.assertNotIn("future_preference", actual)
        self.assertNotIn("schema", actual)

    def test_minimal_fixture_fills_defaults_and_legacy_editor_topmost(self):
        self.fixture("schema_1_minimal.json")
        actual = config.read_config(self.path)
        self.assertFalse(actual["backup"])
        self.assertTrue(actual["editor_topmost"])
        self.assertEqual(actual["geometry"], "1100x860")
        self.assertTrue(actual["auto_check_update"])
        self.assertEqual(actual["last_update_check"], 0.0)

    def test_unversioned_legacy_is_schema_1_without_rewriting_bytes(self):
        self.fixture("legacy_unversioned.json")
        original = self.path.read_bytes()
        result = config.migrate_config(self.path, backup_dir=self.backups)
        self.assertEqual(result["schema"], 1)
        self.assertFalse(result["backup"])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(self.backups.exists())

    def test_unknown_fields_survive_gui_save_and_partial_update(self):
        original = self.fixture("schema_1_full.json")
        gui_support.save_settings({"topmost": False}, self.path)
        config.update_config({"last_update_check": 1791302500.5}, self.path)
        result = config.read_config(self.path)
        self.assertEqual(result["future_preference"], original["future_preference"])
        self.assertEqual(result["last_dir"], original["last_dir"])
        self.assertFalse(result["backup"])
        self.assertFalse(result["auto_check_update"])
        self.assertFalse(result["topmost"])
        self.assertEqual(result["last_update_check"], 1791302500.5)

    def test_invalid_optional_values_fall_back_individually(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"backup": "no", "existing": "merge",
                                         "geometry": "9x8", "last_dir": "保留",
                                         "last_update_check": -1}), encoding="utf-8")
        result = config.read_config(self.path)
        self.assertTrue(result["backup"])
        self.assertEqual(result["existing"], "skip")
        self.assertEqual(result["geometry"], "1100x860")
        self.assertEqual(result["last_dir"], "保留")
        self.assertEqual(result["last_update_check"], 0.0)

    def test_extreme_or_mistyped_timestamps_fall_back_without_crashing(self):
        for value in (True, "yesterday", -1, 10 ** 1000):
            with self.subTest(value_type=type(value).__name__):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps({"last_update_check": value}), encoding="utf-8")
                self.assertEqual(config.read_config(self.path)["last_update_check"], 0.0)

    def test_non_json_constants_are_rejected_without_saving_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'{"unknown": NaN}')
        with self.assertRaises(config.ConfigError):
            config.save_config({"backup": False}, self.path)
        self.assertEqual(self.path.read_bytes(), b'{"unknown": NaN}')

    def test_missing_config_uses_defaults_without_creating_file(self):
        result = config.read_config(self.path)
        self.assertTrue(result["backup"])
        self.assertFalse(self.path.exists())

    def test_default_location_and_gui_api_remain_unchanged(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.folder)}):
            expected = self.folder / "ZoteroPDFBookmarks" / "settings.json"
            self.assertEqual(config.settings_path(), expected)
            self.assertEqual(gui_support._settings_path(), expected)
            gui_support.save_settings({"backup": False})
            self.assertFalse(gui_support.load_settings()["backup"])

    def test_malformed_files_use_gui_defaults_but_are_not_overwritten(self):
        for fixture in (FIXTURES / "malformed_examples").glob("*.json"):
            with self.subTest(fixture=fixture.name):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_bytes(fixture.read_bytes())
                original = self.path.read_bytes()
                self.assertEqual(gui_support.load_settings(self.path), config.DEFAULT_CONFIG)
                with self.assertRaises(config.ConfigError):
                    config.read_config(self.path)
                with self.assertRaises(config.ConfigError):
                    gui_support.save_settings(config.DEFAULT_CONFIG, self.path)
                self.assertEqual(self.path.read_bytes(), original)

    def test_future_schema_cannot_be_silently_saved_or_health_acknowledged(self):
        self.fixture("schema_2_full.json")
        original = self.path.read_bytes()
        with self.assertRaises(config.ConfigError):
            config.read_config(self.path)
        with self.assertRaises(config.ConfigError):
            config.save_config({"backup": True}, self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_multi_level_migration_preserves_user_values_and_unknown_fields(self):
        original = self.fixture("schema_1_full.json")
        result = config.migrate_config(self.path, 3, {1: to_schema_2, 2: to_schema_3},
                                       backup_dir=self.backups)
        self.assertEqual(result["schema"], 3)
        self.assertEqual(result["last_dir"], original["last_dir"])
        self.assertFalse(result["backup"])
        self.assertEqual(result["future_preference"], original["future_preference"])
        self.assertEqual(json.loads(self.path.read_bytes())["schema"], 3)
        self.assertEqual(len(list(self.backups.glob("*.backup"))), 1)

    def test_old_intermediate_schema_fixture_migrates_to_latest_injected_schema(self):
        for name in ("schema_2_minimal.json", "schema_2_full.json"):
            with self.subTest(name=name):
                original = self.fixture(name)
                result = config.migrate_config(self.path, 3, {2: to_schema_3})
                self.assertEqual(result["last_dir"], original["recent_directory"])
                self.assertFalse(result["backup"])

    def test_backup_exists_before_migration_callback(self):
        self.fixture("schema_1_full.json")
        original = self.path.read_bytes()

        def checked(document):
            backups = list(self.backups.glob("*.backup"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertEqual(self.path.read_bytes(), original)
            return to_schema_2(document)

        config.migrate_config(self.path, 2, {1: checked}, backup_dir=self.backups)

    def test_migration_exception_and_interruption_leave_original_bytes(self):
        for error in (RuntimeError("migration failed"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                self.fixture("schema_1_full.json")
                original = self.path.read_bytes()

                def failing(document):
                    document["backup"] = True
                    raise error

                with self.assertRaises(type(error)):
                    config.migrate_config(self.path, 2, {1: failing})
                self.assertEqual(self.path.read_bytes(), original)

    def test_missing_migration_and_invalid_output_leave_original_bytes(self):
        invalid_outputs = ({}, {1: lambda document: {"schema": 2, "backup": "false"}},
                           {1: lambda document: {"schema": 9}})
        for migrations in invalid_outputs:
            with self.subTest(migrations=migrations):
                self.fixture("schema_1_full.json")
                original = self.path.read_bytes()
                with self.assertRaises(config.ConfigError):
                    config.migrate_config(self.path, 2, migrations)
                self.assertEqual(self.path.read_bytes(), original)

    def test_schema_specific_validation_failure_preserves_original(self):
        self.fixture("schema_1_full.json")
        original = self.path.read_bytes()

        def validate(document):
            raise config.ConfigError("new structure is invalid")

        with self.assertRaises(config.ConfigError):
            config.migrate_config(self.path, 2, {1: to_schema_2}, validators={2: validate})
        self.assertEqual(self.path.read_bytes(), original)

    def test_failed_atomic_replace_keeps_old_file_and_cleans_temporary(self):
        self.fixture("schema_1_full.json")
        original = self.path.read_bytes()
        replace = os.replace

        def fail_target(source, target):
            if Path(target) == self.path:
                raise OSError("simulated file lock")
            return replace(source, target)

        with patch.object(config.os, "replace", side_effect=fail_target):
            with self.assertRaises(OSError):
                config.migrate_config(self.path, 2, {1: to_schema_2})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_interruption_after_replace_restores_original(self):
        self.fixture("schema_1_full.json")
        original = self.path.read_bytes()
        replace = os.replace
        interrupted = False

        def interrupt_after_replace(source, target):
            nonlocal interrupted
            result = replace(source, target)
            if Path(target) == self.path and not interrupted:
                interrupted = True
                raise KeyboardInterrupt()
            return result

        with patch.object(config.os, "replace", side_effect=interrupt_after_replace):
            with self.assertRaises(KeyboardInterrupt):
                config.migrate_config(self.path, 2, {1: to_schema_2})
        self.assertEqual(self.path.read_bytes(), original)

    def test_program_rollback_restores_config_after_successful_migration(self):
        self.fixture("schema_1_full.json")
        original = self.path.read_bytes()
        snapshot = config.snapshot_config(self.path, self.backups)
        json.dumps(snapshot)
        config.migrate_config(self.path, 3, {1: to_schema_2, 2: to_schema_3},
                              backup_dir=self.backups)
        config.restore_config(snapshot)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(config.read_config(self.path)["backup"])

    def test_raw_malformed_snapshot_and_original_absence_restore(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"\xef\xbb\xbf{malformed-original")
        original = self.path.read_bytes()
        snapshot = config.snapshot_config(self.path, self.backups)
        self.path.write_bytes(b'{"schema":1}')
        config.restore_config(snapshot)
        self.assertEqual(self.path.read_bytes(), original)
        self.path.unlink()
        absent = config.snapshot_config(self.path, self.backups)
        config.save_config({"backup": False}, self.path)
        unknown = self.path.parent / "我的文件.txt"
        unknown.write_text("保留", encoding="utf-8")
        config.restore_config(absent)
        self.assertFalse(self.path.exists())
        self.assertEqual(unknown.read_text(encoding="utf-8"), "保留")

    def test_modified_backup_is_rejected_without_overwriting_live_config(self):
        self.fixture("schema_1_full.json")
        snapshot = config.snapshot_config(self.path, self.backups)
        Path(snapshot["backup"]).write_bytes(b"tampered")
        original = self.path.read_bytes()
        with self.assertRaises(config.ConfigError):
            config.restore_config(snapshot)
        self.assertEqual(self.path.read_bytes(), original)

    def test_parallel_gui_save_and_timestamp_updates_keep_both_settings(self):
        self.fixture("schema_1_full.json")

        def write(index):
            if index % 2:
                config.update_config({"last_update_check": 1791302500}, self.path)
            else:
                gui_support.save_settings({"topmost": False, "backup": False}, self.path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(write, range(24)))
        result = config.read_config(self.path)
        self.assertFalse(result["topmost"])
        self.assertFalse(result["backup"])
        self.assertFalse(result["auto_check_update"])
        self.assertEqual(result["last_update_check"], 1791302500)
        self.assertIn("future_preference", result)


if __name__ == "__main__":
    unittest.main()
