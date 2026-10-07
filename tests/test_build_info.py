"""Build identity is embedded and cannot be inferred from paths or names."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import build_info


class BuildInfoTests(unittest.TestCase):
    def test_source_reads_single_version_source(self):
        with patch.dict(sys.modules, {"_build_identity": None}), \
                patch.object(sys, "frozen", False, create=True):
            info = build_info.get_build_info()
        self.assertEqual(info.version, (Path(build_info.__file__).parent / "VERSION").read_text().strip())
        self.assertEqual(info.app_id, "com.linzh.PDFBookmarks")
        self.assertEqual(info.variant, "single")
        self.assertEqual(info.config_schema, 1)
        self.assertEqual(info.update_schema, 1)
        self.assertEqual(info.channel, "stable")

    def test_frozen_identity_survives_renaming_and_moving(self):
        identity = types.SimpleNamespace(APP_VERSION="1.5.0", BUILD_VARIANT="portable", BUILD_ENTRYPOINT="gui")
        with patch.dict(sys.modules, {"_build_identity": identity}), \
                patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", "F:/文献 软件/我的PDF.exe"), \
                patch.object(sys, "_MEIPASS", "F:/arbitrary name/resources", create=True):
            info = build_info.get_build_info()
        self.assertEqual(info.version, "1.5.0")
        self.assertEqual(info.variant, "portable")
        with self.assertRaises(FrozenInstanceError):
            info.variant = "single"

    def test_frozen_missing_identity_fails_closed(self):
        with patch.dict(sys.modules, {"_build_identity": None}), \
                patch.object(sys, "frozen", True, create=True):
            with self.assertRaisesRegex(RuntimeError, "missing its build identity"):
                build_info.get_build_info()

    def test_invalid_embedded_identity_is_not_accepted(self):
        for value in ("other", "", "Portable"):
            with self.subTest(variant=value):
                identity = types.SimpleNamespace(APP_VERSION="1.5.0", BUILD_VARIANT=value, BUILD_ENTRYPOINT="gui")
                with patch.dict(sys.modules, {"_build_identity": identity}):
                    with self.assertRaises(ValueError):
                        build_info.get_build_info()
        for value in ("1", "v1.5.0", "01.5.0", "1.5.0-beta", "../../1.5.0"):
            with self.subTest(version=value):
                with self.assertRaises(ValueError):
                    build_info.BuildInfo(build_info.APP_ID, value, "single")

    def test_only_frozen_gui_build_can_install_updates(self):
        for frozen, entrypoint, expected in (
                (False, "gui", False), (True, "gui", True),
                (True, "cli", False), (True, "updater", False), (True, None, False)):
            with self.subTest(frozen=frozen, entrypoint=entrypoint):
                identity = types.SimpleNamespace(BUILD_ENTRYPOINT=entrypoint)
                with patch.dict(sys.modules, {"_build_identity": identity}), \
                        patch.object(sys, "frozen", frozen, create=True):
                    self.assertEqual(build_info.can_self_update(), expected)


if __name__ == "__main__":
    unittest.main()
