"""Offline HTTP fixtures exercise release trust and bounded-memory downloads."""

import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.request

from build_info import APP_ID, BuildInfo
from updater import UpdateError
from updater import checker, downloader


class Response:
    def __init__(self, data, url, headers=None, failure=None, after_read=None):
        self.stream = io.BytesIO(data)
        self.url, self.headers = url, headers or {}
        self.failure, self.after_read = failure, after_read
        self.read_sizes = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def geturl(self):
        return self.url

    def read(self, size):
        self.read_sizes.append(size)
        if self.failure is not None and len(self.read_sizes) > 1:
            raise self.failure
        result = self.stream.read(size)
        if self.after_read:
            self.after_read(result)
        return result


def release_fixture(variant="single"):
    info = BuildInfo(APP_ID, "1.5.0", variant)
    tag, version = "v1.6.0", "1.6.0"
    prefix = f"https://github.com/{checker.REPOSITORY}/releases/download/{tag}/"
    manifest = {"schema": 1, "app_id": APP_ID, "version": version,
                "minimum_updater_schema": 1, "channel": "stable", "release_notes": "更新说明",
                "assets": {"single": {"file": "PDF_Bookmarks_v1.6.0_win_x64.exe", "sha256": "a" * 64},
                           "portable": {"file": "PDF_Bookmarks_v1.6.0_win_x64_portable.zip", "sha256": "b" * 64}}}
    assets = [{"name": "update-manifest.json", "browser_download_url": prefix + "update-manifest.json", "size": 800}]
    assets.extend({"name": asset["file"], "browser_download_url": prefix + asset["file"], "size": 1000}
                  for asset in manifest["assets"].values())
    release = {"tag_name": tag, "draft": False, "prerelease": False,
               "html_url": f"https://github.com/{checker.REPOSITORY}/releases/tag/{tag}",
               "body": "发布页介绍", "assets": assets}
    return info, release, manifest


def json_opener(release, manifest):
    calls = []

    def open_response(request, timeout):
        calls.append(request)
        data = release if request.full_url == checker.RELEASE_API else manifest
        return Response(json.dumps(data).encode("utf-8"), request.full_url)

    return open_response, calls


class UpdateCheckTests(unittest.TestCase):
    def test_url_trust_requires_https_and_approved_github_hosts(self):
        for url in ("https://github.com/a", "https://api.github.com/a",
                    "https://release-assets.githubusercontent.com/a?token=temporary"):
            self.assertEqual(checker.trusted_https(url), url)
        for url in ("http://github.com/a", "https://github.com.evil.test/a",
                    "https://evilgithub.com/a", "https://github.com:invalid/a",
                    "https://github.com:444/a", "https://name:secret@github.com/a",
                    "https://@github.com/a",
                    "https://github.com/a#fragment", "https://github.com/a\n",
                    "https://github.com/\x00", None):
            with self.subTest(url=url), self.assertRaises(checker.UpdateCheckError):
                checker.trusted_https(url)

    def test_redirect_policy_rejects_destination_before_sending_request(self):
        handler = checker.GitHubRedirectHandler()
        request = urllib.request.Request("https://github.com/test")
        for url in ("http://github.com/file", "https://untrusted.test/file"):
            with self.subTest(url=url), self.assertRaises(checker.UpdateCheckError):
                handler.redirect_request(request, None, 302, "Found", {}, url)
        result = handler.redirect_request(request, None, 302, "Found", {},
                                          "https://objects.githubusercontent.com/file")
        self.assertEqual(result.full_url, "https://objects.githubusercontent.com/file")

    def test_stable_release_selects_only_the_current_build_variant(self):
        for variant in ("single", "portable"):
            with self.subTest(variant=variant):
                info, release, manifest = release_fixture(variant)
                opener, calls = json_opener(release, manifest)
                offer = checker.check_for_update(info, opener=opener)
                self.assertEqual(offer.version, "1.6.0")
                self.assertEqual(offer.asset["file"], manifest["assets"][variant]["file"])
                self.assertEqual(offer.release_notes, "更新说明")
                self.assertEqual(len(calls), 2)
                self.assertTrue(all(request.get_header("Authorization") is None for request in calls))

    def test_current_or_older_release_does_not_fetch_manifest(self):
        for tag in ("v1.5.0", "1.4.9"):
            with self.subTest(tag=tag):
                info, release, manifest = release_fixture()
                release["tag_name"] = tag
                opener, calls = json_opener(release, manifest)
                self.assertIsNone(checker.check_for_update(info, opener=opener))
                self.assertEqual(len(calls), 1)

    def test_stable_rejects_drafts_prereleases_and_invalid_tags(self):
        for field, value in (("draft", True), ("prerelease", True), ("tag_name", "v1.6.0-beta.1"),
                             ("tag_name", "v01.6.0"), ("tag_name", None)):
            with self.subTest(field=field, value=value):
                info, release, manifest = release_fixture()
                release[field] = value
                opener, _ = json_opener(release, manifest)
                with self.assertRaises(checker.UpdateCheckError):
                    checker.check_for_update(info, opener=opener)

    def test_release_and_manifest_links_are_bound_to_current_repository(self):
        for kind in ("release", "manifest", "asset"):
            with self.subTest(kind=kind):
                info, release, manifest = release_fixture()
                if kind == "release":
                    release["html_url"] = "https://github.com/other/repo/releases/tag/v1.6.0"
                else:
                    index = 0 if kind == "manifest" else 1
                    release["assets"][index]["browser_download_url"] = "https://github.com/other/repo/file"
                opener, _ = json_opener(release, manifest)
                with self.assertRaises(checker.UpdateCheckError):
                    checker.check_for_update(info, opener=opener)

    def test_mismatched_manifest_app_variant_protocol_version_or_hash_is_rejected(self):
        def mutate(data, kind):
            if kind == "variant":
                data["assets"]["single"]["variant"] = "portable"
            elif kind == "hash":
                data["assets"]["single"]["sha256"] = "wrong"
            else:
                data[kind] = {"app_id": "foreign", "schema": 99, "minimum_updater_schema": 2,
                              "version": "1.7.0", "channel": "beta"}[kind]

        for kind in ("app_id", "schema", "minimum_updater_schema", "version", "channel", "variant", "hash"):
            with self.subTest(kind=kind):
                info, release, manifest = release_fixture()
                mutate(manifest, kind)
                opener, _ = json_opener(release, manifest)
                with self.assertRaises((checker.UpdateCheckError, UpdateError)):
                    checker.check_for_update(info, opener=opener)

    def test_missing_duplicate_or_invalid_asset_records_fail_safely(self):
        for assets in ([], [None], [{}], [{"name": []}], "not-list"):
            with self.subTest(assets=assets):
                info, release, manifest = release_fixture()
                release["assets"] = assets
                opener, _ = json_opener(release, manifest)
                with self.assertRaises(checker.UpdateCheckError):
                    checker.check_for_update(info, opener=opener)
        info, release, manifest = release_fixture()
        release["assets"].append(copy.deepcopy(release["assets"][0]))
        opener, _ = json_opener(release, manifest)
        with self.assertRaises(checker.UpdateCheckError):
            checker.check_for_update(info, opener=opener)

    def test_invalid_or_inconsistent_download_size_is_rejected(self):
        for size in (0, -1, True, "1000", 8 * 1024**3 + 1):
            with self.subTest(size=size):
                info, release, manifest = release_fixture()
                release["assets"][1]["size"] = size
                opener, _ = json_opener(release, manifest)
                with self.assertRaises(checker.UpdateCheckError):
                    checker.check_for_update(info, opener=opener)
        info, release, manifest = release_fixture()
        manifest["assets"]["single"]["size"] = 2000
        opener, _ = json_opener(release, manifest)
        with self.assertRaises(checker.UpdateCheckError):
            checker.check_for_update(info, opener=opener)

    def test_json_read_is_bounded_and_checks_final_url_and_structure(self):
        url = checker.RELEASE_API
        for data, final_url in ((b"x" * (checker.MAX_JSON_BYTES + 1), url),
                                (b"[]", url), (b'{"size": NaN}', url),
                                (b'{bad', url), (b'{}', "http://github.com/file")):
            with self.subTest(data=data[:20], final_url=final_url):
                response = Response(data, final_url)
                with self.assertRaises(checker.UpdateCheckError):
                    checker.read_json(url, opener=lambda request, timeout: response)
                self.assertTrue(all(size == checker.MAX_JSON_BYTES + 1 for size in response.read_sizes))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pdf-update-download-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.destination = self.folder / "package"
        self.payload = b"MZ" + b"download-data" * 70000
        self.url = "https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/package.exe"
        self.asset = {"url": self.url, "size": len(self.payload), "sha256": hashlib.sha256(self.payload).hexdigest()}

    def response(self, **kwargs):
        return Response(self.payload, self.url, **kwargs)

    def assert_clean(self):
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.destination.with_name("package.part").exists())

    def test_streamed_download_checks_hash_size_and_reports_bounded_progress(self):
        response = self.response(headers={"Content-Length": str(len(self.payload))})
        progress = []
        asset = dict(self.asset, sha256=self.asset["sha256"].upper())
        result = downloader.download_asset(asset, self.destination,
                                            progress=lambda done, total: progress.append((done, total)),
                                            opener=lambda request, timeout: response)
        self.assertEqual(result, self.destination)
        self.assertEqual(self.destination.read_bytes(), self.payload)
        self.assertFalse(self.destination.with_name("package.part").exists())
        self.assertTrue(all(size == downloader.CHUNK_SIZE for size in response.read_sizes))
        self.assertEqual(progress[-1], (len(self.payload), len(self.payload)))
        self.assertEqual(sorted(done for done, _ in progress), [done for done, _ in progress])

    def test_bad_hash_short_oversized_or_wrong_declared_size_remove_partial(self):
        cases = (dict(self.asset, sha256="0" * 64), dict(self.asset, size=len(self.payload) + 1),
                 dict(self.asset, size=len(self.payload) - 1))
        for asset in cases:
            with self.subTest(size=asset["size"]), self.assertRaises(downloader.DownloadError):
                downloader.download_asset(asset, self.destination, opener=lambda request, timeout: self.response())
            self.assert_clean()
        for declared in (str(len(self.payload) + 1), "not-a-number"):
            with self.subTest(declared=declared), self.assertRaises(downloader.DownloadError):
                downloader.download_asset(self.asset, self.destination,
                                          opener=lambda request, timeout: self.response(headers={"Content-Length": declared}))
            self.assert_clean()

    def test_network_disconnect_progress_error_and_interruption_remove_partial(self):
        for error in (OSError("network disconnected"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                response = self.response(failure=error)
                with self.assertRaises(KeyboardInterrupt if isinstance(error, KeyboardInterrupt) else downloader.DownloadError):
                    downloader.download_asset(self.asset, self.destination, opener=lambda request, timeout: response)
                self.assert_clean()
        with self.assertRaises(downloader.DownloadError):
            downloader.download_asset(self.asset, self.destination, progress=Mock(side_effect=RuntimeError("UI closed")),
                                      opener=lambda request, timeout: self.response())
        self.assert_clean()

    def test_early_midstream_and_eof_cancellation_leave_no_download(self):
        cancelled = threading.Event()
        cancelled.set()
        opener = Mock()
        with self.assertRaises(downloader.DownloadError):
            downloader.download_asset(self.asset, self.destination, cancelled=cancelled, opener=opener)
        opener.assert_not_called()
        cancelled.clear()
        with self.assertRaises(downloader.DownloadError):
            downloader.download_asset(self.asset, self.destination, cancelled=cancelled,
                                      progress=lambda *_: cancelled.set(), opener=lambda request, timeout: self.response())
        self.assert_clean()
        cancelled.clear()
        response = self.response(after_read=lambda block: cancelled.set() if not block else None)
        with self.assertRaises(downloader.DownloadError):
            downloader.download_asset(self.asset, self.destination, cancelled=cancelled, opener=lambda request, timeout: response)
        self.assert_clean()

    def test_disk_space_failure_stops_before_network_and_creating_partial(self):
        opener = Mock()
        with patch.object(downloader.shutil, "disk_usage", return_value=SimpleNamespace(free=0)):
            with self.assertRaises(downloader.DownloadError):
                downloader.download_asset(self.asset, self.destination, opener=opener)
        opener.assert_not_called()
        self.assert_clean()

    def test_existing_destination_or_partial_is_not_overwritten_or_deleted(self):
        for path in (self.destination, self.destination.with_name("package.part")):
            with self.subTest(path=path.name):
                path.write_bytes(b"user-owned-existing")
                with self.assertRaises(downloader.DownloadError):
                    downloader.download_asset(self.asset, self.destination, opener=Mock())
                self.assertEqual(path.read_bytes(), b"user-owned-existing")
                path.unlink()

    def test_malformed_asset_and_untrusted_redirect_are_rejected(self):
        for asset in ({}, dict(self.asset, size=True), dict(self.asset, size=0), dict(self.asset, sha256="wrong")):
            with self.subTest(asset=asset), self.assertRaises(downloader.DownloadError):
                downloader.download_asset(asset, self.destination, opener=Mock())
            self.assert_clean()
        response = Response(self.payload, "https://untrusted.test/file")
        with self.assertRaises(downloader.DownloadError):
            downloader.download_asset(self.asset, self.destination, opener=lambda request, timeout: response)
        self.assert_clean()

    def test_permission_failure_preserves_existing_files(self):
        original_open = Path.open

        def locked(path, mode="r", *args, **kwargs):
            if Path(path).name == "package.part" and mode == "xb":
                raise PermissionError("download directory not writable")
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", locked), self.assertRaises(downloader.DownloadError):
            downloader.download_asset(self.asset, self.destination, opener=lambda request, timeout: self.response())
        self.assert_clean()

    def test_owned_download_cleanup_keeps_foreign_unknown_live_and_malformed_directories(self):
        root = self.folder / "downloads"
        with patch.object(downloader, "downloads_root", return_value=root):
            removable = downloader.new_download_directory(APP_ID)
            (removable / "package.part").write_bytes(b"partial")
            foreign = downloader.new_download_directory("foreign.app")
            unknown = downloader.new_download_directory(APP_ID)
            (unknown / "论文.pdf").write_bytes(b"user file")
            live = downloader.new_download_directory(APP_ID)
            malformed = downloader.new_download_directory(APP_ID)
            (malformed / "download.json").write_text("[]", encoding="utf-8")
            wrong_name = root / ("z" * 32)
            wrong_name.mkdir()
            (wrong_name / "download.json").write_text(json.dumps({"app_id": APP_ID}), encoding="utf-8")
            self.assertFalse(downloader.remove_download_directory(wrong_name, APP_ID))
            live_marker = json.loads((live / "download.json").read_bytes())
            live_marker["pid"] = 12345
            (live / "download.json").write_text(json.dumps(live_marker), encoding="utf-8")
            with patch("updater.processes.process_alive", side_effect=lambda pid: pid == 12345):
                downloader.cleanup_interrupted_downloads(APP_ID)
            self.assertFalse(removable.exists())
            for directory in (foreign, unknown, live, malformed, wrong_name):
                self.assertTrue(directory.exists())
            self.assertEqual((unknown / "论文.pdf").read_bytes(), b"user file")


if __name__ == "__main__":
    unittest.main()
