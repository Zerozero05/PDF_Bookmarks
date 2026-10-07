"""Update assets describe exactly the payload, without exposing user data."""

import json
import unittest
from unittest.mock import patch
import zipfile

from scripts import package_release
from test_packaging import PackagingFixture


class UpdatePackagingTests(PackagingFixture, unittest.TestCase):
    def test_manifest_hashes_all_payload_files(self):
        self.package()
        archive = self.root / "artifacts/PDF_Bookmarks_v1.4.1_win_x64_portable.zip"
        with zipfile.ZipFile(archive) as package:
            manifest = json.loads(package.read("PDF_Bookmarks/package-manifest.json"))
            self.assertEqual(manifest["app_id"], "com.linzh.PDFBookmarks")
            self.assertEqual(manifest["variant"], "portable")
            self.assertEqual(manifest["version"], "1.4.1")
            self.assertEqual(manifest["manifest_excludes"], ["package-manifest.json"])
            listed = {record["path"] for record in manifest["managed_files"]}
            actual = {name.removeprefix("PDF_Bookmarks/") for name in package.namelist()}
            self.assertEqual(actual - {"package-manifest.json"}, listed)
            self.assertNotIn(".pdf_bookmarks/installed-manifest.json", actual)
            import hashlib
            for record in manifest["managed_files"]:
                content = package.read("PDF_Bookmarks/" + record["path"])
                self.assertEqual(record["size"], len(content))
                self.assertEqual(record["sha256"], hashlib.sha256(content).hexdigest())

    def test_release_manifest_uses_version_and_exact_asset_digests(self):
        self.package()
        output = self.root / "artifacts"
        manifest = json.loads((output / "update-manifest.json").read_text())
        self.assertEqual(manifest["version"], "1.4.1")
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["config_schema"], 1)
        self.assertEqual(manifest["channel"], "stable")
        self.assertEqual(set(manifest["assets"]), {"single", "portable"})
        for item in manifest["assets"].values():
            file = output / item["file"]
            self.assertEqual(item["sha256"], package_release.sha256(file))
            self.assertEqual(item["size"], file.stat().st_size)

    def test_configuration_fixtures_allowed_but_private_json_rejected(self):
        fixture = "tests/fixtures/config/schema_1_minimal.json"
        target = self.root / fixture
        target.parent.mkdir(parents=True)
        target.write_text("{}")
        self.sources.append(fixture)
        self.package()
        private = "my_private_settings.json"
        (self.root / private).write_text("{}")
        self.sources.append(private)
        with self.assertRaisesRegex(ValueError, "Only examples/"):
            self.package()

    def test_installed_user_state_never_packaged(self):
        state = self.portable / ".pdf_bookmarks"
        state.mkdir()
        (state / "installed-manifest.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "installed state"):
            self.package()

    def test_tag_must_match_version(self):
        with patch.object(package_release, "ROOT", self.root), \
                patch.dict("os.environ", {"GITHUB_REF": "refs/tags/v9.9.9"}):
            with self.assertRaisesRegex(ValueError, "tag must match"):
                package_release.version()

    def test_stale_other_version_asset_refuses_publication(self):
        output = self.root / "artifacts"
        output.mkdir()
        (output / "PDF_Bookmarks_v0.1.0_win_x64.exe").write_bytes(b"MZ stale")
        with self.assertRaisesRegex(ValueError, "another build"):
            self.package()

    def test_build_source_drift_cannot_be_packaged_as_current_release(self):
        expected = {"VERSION": "one", "build_info.py": "two"}
        state = self.root / "build/build-state"
        state.mkdir(parents=True)
        for kind in ("helper", "single", "portable", "cli"):
            (state / f"{kind}.json").write_text(json.dumps({
                "version": "1.4.1", "runtime_sources": expected}), encoding="utf-8")
        with patch.object(package_release, "ROOT", self.root), \
                patch.object(package_release, "runtime_fingerprint", return_value=expected):
            package_release.verify_build_provenance("1.4.1")
        with patch.object(package_release, "ROOT", self.root), \
                patch.object(package_release, "runtime_fingerprint", return_value={**expected, "build_info.py": "changed"}):
            with self.assertRaisesRegex(ValueError, "different sources"):
                package_release.verify_build_provenance("1.4.1")
