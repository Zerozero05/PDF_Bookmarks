"""Protocol and archive paths fail closed before installed files change."""

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from build_info import APP_ID, BuildInfo
from updater import UpdateError
from updater.manifest import (assert_safe_path, relative_path, validate_package_manifest,
                              validate_release_manifest, version_key)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.info = BuildInfo(APP_ID, "1.4.1", "single")
        self.release = {"schema": 1, "app_id": APP_ID, "version": "1.5.0",
                        "minimum_updater_schema": 1, "channel": "stable",
                        "assets": {"single": {"file": "PDF_Bookmarks_v1.5.0_win_x64.exe", "sha256": "a" * 64}}}

    def test_identity_variant_schema_version_and_hash(self):
        self.assertIs(validate_release_manifest(self.release, self.info), self.release)
        for field, value in (("app_id", "other"), ("schema", 2), ("schema", True),
                             ("minimum_updater_schema", 2), ("minimum_updater_schema", True),
                             ("version", "1.4.1"), ("version", "1.4.0"), ("version", "1.5.0-beta.1"),
                             ("version", "bad"), ("channel", "beta")):
            with self.subTest(field=field, value=value):
                broken = copy.deepcopy(self.release)
                broken[field] = value
                with self.assertRaises(UpdateError):
                    validate_release_manifest(broken, self.info)
        for field, value in (("sha256", "bad"), ("file", "../package.exe"), ("file", "package.zip"),
                             ("size", -1), ("variant", "portable")):
            broken = copy.deepcopy(self.release)
            broken["assets"]["single"][field] = value
            with self.assertRaises(UpdateError):
                validate_release_manifest(broken, self.info)

    def test_semantic_version_order(self):
        ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0", "1.0.1", "1.1.0", "2.0.0"]
        self.assertEqual(sorted(ordered, key=version_key), ordered)
        self.assertEqual(version_key("1.0.0+abc"), version_key("1.0.0+def"))
        for malformed in ("01.0.0", "1.0", "1.0.0-alpha..b", "1.0.0-01"):
            with self.assertRaises(UpdateError):
                version_key(malformed)

    def test_windows_paths(self):
        for bad in ("../escape", "/root/file", "a//b", "./file", "a\\b", "C:/exe", "NUL.txt", "COM1", "a.", "a ", "a:b", "a?b"):
            with self.subTest(path=bad), self.assertRaises(UpdateError):
                relative_path(bad)
        self.assertEqual(relative_path("_internal/中文 名称.dll"), "_internal/中文 名称.dll")

    def test_portable_records_user_data_and_duplicates(self):
        manifest = {"schema": 1, "app_id": APP_ID, "version": "1.5.0", "variant": "portable",
                    "entrypoint": "PDF.exe", "managed_files": [{"path": "PDF.exe", "size": 2,
                    "sha256": hashlib.sha256(b"MZ").hexdigest()}]}
        validate_package_manifest(manifest, self.info, "1.5.0")
        for name in ("pdf.EXE", "UserData/private.json", "settings.json", "templates/sample", "package-manifest.json", ".pdf_bookmarks/private"):
            broken = copy.deepcopy(manifest)
            broken["managed_files"].append(dict(broken["managed_files"][0], path=name))
            with self.subTest(path=name), self.assertRaises(UpdateError):
                validate_package_manifest(broken, self.info)

    def test_symlink_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "outside").mkdir()
            try:
                (root / "link").symlink_to(root / "outside", target_is_directory=True)
            except OSError:
                self.skipTest("Symlink privilege unavailable; junction protection covered on Windows")
            with self.assertRaises(UpdateError):
                assert_safe_path(root / "link/new.exe")


if __name__ == "__main__":
    unittest.main()
