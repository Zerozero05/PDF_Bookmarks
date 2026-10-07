"""Update controller lifecycle uses isolated files and an independent executor."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import queue
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from build_info import APP_ID, BuildInfo
from config_manager import read_config, save_config
from updater import checker, controller, downloader
from updater.checker import UpdateOffer
from updater.transaction import prepare_transaction


class ControllerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pdf-update-controller-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.config = self.folder / "profile" / "settings.json"
        self.exe = self.folder / "科研 软件" / "我的 PDF.exe"
        self.exe.parent.mkdir()
        self.old_program = b"MZ-old-program"
        self.exe.write_bytes(self.old_program)
        self.payload = b"MZ-new-program"
        self.info = BuildInfo(APP_ID, "1.5.0", "single")
        self.asset = {"file": "PDF_Bookmarks_v1.6.0_win_x64.exe", "size": len(self.payload),
                      "sha256": hashlib.sha256(self.payload).hexdigest(),
                      "url": "https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/package.exe"}
        self.manifest = {"schema": 1, "app_id": APP_ID, "version": "1.6.0", "minimum_updater_schema": 1,
                         "channel": "stable", "assets": {"single": dict(self.asset)}}
        self.offer = UpdateOffer("1.6.0", self.manifest, self.asset, "Release notes", "https://github.com")
        save_config({"backup": False, "future_unknown": {"keep": True}}, self.config)
        self.manager = controller.UpdateController(self.info, self.config)
        self.addCleanup(self.manager.executor.shutdown, wait=True)
        self.addCleanup(self.manager.close)

    def drain(self):
        events = []
        while True:
            try:
                events.append(self.manager.events.get_nowait())
            except queue.Empty:
                return events

    def prepare(self, package, manifest, info, **kwargs):
        return prepare_transaction(package, manifest, info, current_exe=self.exe,
                                   transaction_root=self.folder / "transactions", **kwargs)

    def download(self, asset, destination, **kwargs):
        Path(destination).write_bytes(self.payload)
        if kwargs.get("progress"):
            kwargs["progress"](len(self.payload), len(self.payload))
        return Path(destination)

    def prepare_ready(self):
        self.manager.offer = self.offer
        self.manager.state = controller.UpdateState.AVAILABLE
        with patch.object(controller, "can_self_update", return_value=True), \
                patch.object(downloader, "downloads_root", return_value=self.folder / "downloads"), \
                patch.object(controller, "download_asset", side_effect=self.download), \
                patch.object(controller, "prepare_transaction", side_effect=self.prepare):
            self.assertTrue(self.manager.download())
            self.manager.future.result(timeout=5)
        self.assertEqual(self.manager.state, controller.UpdateState.READY)
        return self.manager.transaction

    def test_automatic_check_obeys_toggle_and_24_hour_interval(self):
        current = 1_800_000_000.0
        with patch.object(controller.time, "time", return_value=current), \
                patch.object(controller, "check_for_update", return_value=self.offer) as check:
            save_config({"auto_check_update": False}, self.config)
            self.assertFalse(self.manager.check(automatic=True))
            save_config({"auto_check_update": True, "last_update_check": current - 86399}, self.config)
            self.assertFalse(self.manager.check(automatic=True))
            check.assert_not_called()
            save_config({"last_update_check": current - 86400}, self.config)
            self.assertTrue(self.manager.check(automatic=True))
            self.manager.future.result(timeout=5)
            self.assertEqual(self.manager.state, controller.UpdateState.AVAILABLE)
            self.assertEqual(read_config(self.config)["last_update_check"], current)
            self.assertFalse(self.manager.check(automatic=True))
            self.assertEqual(check.call_count, 1)

    def test_manual_check_forces_check_despite_disabled_automatic_or_recent_timestamp(self):
        save_config({"auto_check_update": False, "last_update_check": 1_800_000_000.0}, self.config)
        with patch.object(controller.time, "time", return_value=1_800_000_001.0), \
                patch.object(controller, "check_for_update", return_value=None) as check:
            self.assertTrue(self.manager.check())
            self.manager.future.result(timeout=5)
            self.assertEqual(self.manager.state, controller.UpdateState.IDLE)
            check.assert_called_once_with(self.info)
        result = read_config(self.config)
        self.assertFalse(result["backup"])
        self.assertEqual(result["future_unknown"], {"keep": True})

    def test_malformed_config_is_never_replaced_by_automatic_or_manual_check(self):
        self.config.write_bytes(b"{malformed-original")
        with patch.object(controller, "check_for_update") as check:
            self.assertFalse(self.manager.check(automatic=True))
            self.assertTrue(self.manager.check())
            self.manager.future.result(timeout=5)
            check.assert_not_called()
        self.assertEqual(self.config.read_bytes(), b"{malformed-original")
        self.assertEqual(self.manager.state, controller.UpdateState.FAILED)

    def test_check_failure_clears_old_offer_and_reports_error(self):
        self.manager.offer = self.offer
        self.manager.state = controller.UpdateState.AVAILABLE
        with patch.object(controller, "check_for_update", side_effect=OSError("offline")):
            self.assertTrue(self.manager.check())
            self.manager.future.result(timeout=5)
        self.assertIsNone(self.manager.offer)
        self.assertEqual(self.manager.state, controller.UpdateState.FAILED)
        self.assertTrue(any(kind == "error" and "offline" in value["message"] for kind, value in self.drain()))
        self.assertFalse(self.manager.download())

    def test_update_executor_does_not_block_or_reuse_pdf_worker(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-pdf") as pdf_worker:
            pdf_future = pdf_worker.submit(gate.wait, 5)
            names = []

            def check(info):
                names.append(threading.current_thread().name)
                return None

            with patch.object(controller, "check_for_update", side_effect=check):
                self.assertTrue(self.manager.check())
                self.manager.future.result(timeout=5)
            self.assertFalse(pdf_future.done())
            self.assertTrue(names[0].startswith("pdf-update"))
            gate.set()

    def test_parallel_check_requests_submit_only_one_network_operation(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def check(info):
            started.set()
            self.assertTrue(release.wait(5))
            return self.offer

        with patch.object(controller, "check_for_update", side_effect=check) as network:
            with ThreadPoolExecutor(max_workers=8) as callers:
                results = list(callers.map(lambda _: self.manager.check(), range(16)))
            self.assertTrue(started.wait(5))
            self.assertEqual(sum(results), 1)
            release.set()
            self.manager.future.result(timeout=5)
            network.assert_called_once()

    def test_source_and_cli_identity_cannot_download_or_install_gui_update(self):
        self.manager.offer = self.offer
        self.manager.state = controller.UpdateState.AVAILABLE
        with patch.object(controller, "can_self_update", return_value=False), \
                patch.object(controller, "download_asset") as download:
            self.assertFalse(self.manager.download())
            download.assert_not_called()
        self.assertEqual(self.exe.read_bytes(), self.old_program)
        with self.assertRaises(OSError):
            self.manager.install()

    def test_download_reaches_ready_and_keeps_current_program_until_install(self):
        transaction = self.prepare_ready()
        states = [value for kind, value in self.drain() if kind == "state"]
        self.assertEqual(states, [controller.UpdateState.DOWNLOADING, controller.UpdateState.DOWNLOADED,
                                  controller.UpdateState.VERIFYING, controller.UpdateState.READY])
        self.assertTrue(transaction.directory.exists())
        self.assertEqual(self.exe.read_bytes(), self.old_program)
        self.assertFalse(self.manager.check())
        self.assertFalse(self.manager.download())
        downloads = self.folder / "downloads"
        self.assertEqual(list(downloads.iterdir()), [])

    def test_check_download_and_prepare_integration_uses_real_verification(self):
        prefix = "https://github.com/Zerozero05/PDF_Bookmarks/releases/download/v1.6.0/"
        release = {"draft": False, "prerelease": False, "tag_name": "v1.6.0",
                   "html_url": "https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v1.6.0",
                   "assets": [{"name": "update-manifest.json", "browser_download_url": prefix + "update-manifest.json"},
                              {"name": self.asset["file"], "browser_download_url": prefix + self.asset["file"],
                               "size": len(self.payload)}]}
        requests = []

        class Response(io.BytesIO):
            def __init__(response, body, url):
                super().__init__(body)
                response.url = url
                response.headers = {"Content-Length": str(len(body))}

            def geturl(response):
                return response.url

        def opener(request, timeout):
            requests.append(request.full_url)
            if request.full_url == checker.RELEASE_API:
                body = json.dumps(release).encode("utf-8")
            elif request.full_url == prefix + "update-manifest.json":
                body = json.dumps(self.manifest).encode("utf-8")
            else:
                self.assertEqual(request.full_url, prefix + self.asset["file"])
                body = self.payload
            return Response(body, request.full_url)

        with patch.object(controller, "can_self_update", return_value=True), \
                patch.object(checker, "open_github", side_effect=opener), \
                patch.object(downloader, "open_github", side_effect=opener), \
                patch.object(downloader, "downloads_root", return_value=self.folder / "downloads"), \
                patch.object(controller, "prepare_transaction", side_effect=self.prepare):
            self.assertTrue(self.manager.check())
            self.manager.future.result(timeout=5)
            self.assertTrue(self.manager.download())
            self.manager.future.result(timeout=5)
        self.assertEqual(self.manager.state, controller.UpdateState.READY)
        self.assertEqual(len(requests), 3)
        self.assertEqual((self.manager.transaction.directory / "package.exe").read_bytes(), self.payload)
        self.assertEqual(self.exe.read_bytes(), self.old_program)

    def test_close_ready_discards_transaction_without_touching_current_program(self):
        transaction = self.prepare_ready()
        self.manager.close()
        self.manager.future.result(timeout=5)
        self.assertFalse(transaction.directory.exists())
        self.assertIsNone(self.manager.transaction)
        self.assertEqual(self.exe.read_bytes(), self.old_program)
        self.assertFalse(self.manager.check())
        self.assertFalse(self.manager.download())

    def test_cancel_ready_discards_transaction_and_allows_new_check(self):
        transaction = self.prepare_ready()
        self.assertTrue(self.manager.cancel())
        self.manager.future.result(timeout=5)
        self.assertFalse(transaction.directory.exists())
        self.assertIsNone(self.manager.transaction)
        self.assertEqual(self.manager.state, controller.UpdateState.AVAILABLE)
        with patch.object(controller, "check_for_update", return_value=None):
            self.assertTrue(self.manager.check())
            self.manager.future.result(timeout=5)
        self.assertEqual(self.manager.state, controller.UpdateState.IDLE)

    def test_close_while_preparing_discards_new_transaction_without_ready_event(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        transactions = []

        def preparing(*args, **kwargs):
            transaction = self.prepare(*args, **kwargs)
            transactions.append(transaction)
            entered.set()
            self.assertTrue(release.wait(5))
            return transaction

        self.manager.offer = self.offer
        self.manager.state = controller.UpdateState.AVAILABLE
        with patch.object(controller, "can_self_update", return_value=True), \
                patch.object(downloader, "downloads_root", return_value=self.folder / "downloads"), \
                patch.object(controller, "download_asset", side_effect=self.download), \
                patch.object(controller, "prepare_transaction", side_effect=preparing):
            self.assertTrue(self.manager.download())
            future = self.manager.future
            self.assertTrue(entered.wait(5))
            self.manager.close()
            release.set()
            future.result(timeout=5)
        self.assertFalse(transactions[0].directory.exists())
        self.assertFalse(any(kind == "ready" for kind, value in self.drain()))
        self.assertEqual(self.exe.read_bytes(), self.old_program)

    def test_cancel_during_download_cleans_partial_directory_and_keeps_program(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def downloading(asset, destination, *, cancelled, **kwargs):
            Path(destination).with_name("package.part").write_bytes(b"partial")
            entered.set()
            self.assertTrue(release.wait(5))
            self.assertTrue(cancelled.is_set())
            raise downloader.DownloadError("cancelled")

        self.manager.offer = self.offer
        self.manager.state = controller.UpdateState.AVAILABLE
        with patch.object(controller, "can_self_update", return_value=True), \
                patch.object(downloader, "downloads_root", return_value=self.folder / "downloads"), \
                patch.object(controller, "download_asset", side_effect=downloading):
            self.assertTrue(self.manager.download())
            self.assertTrue(entered.wait(5))
            self.assertTrue(self.manager.cancel())
            release.set()
            self.manager.future.result(timeout=5)
        self.assertEqual(list((self.folder / "downloads").iterdir()), [])
        self.assertIsNone(self.manager.transaction)
        self.assertEqual(self.exe.read_bytes(), self.old_program)

    def test_install_hands_transaction_to_helper_and_close_does_not_discard_it(self):
        transaction = self.prepare_ready()
        process = SimpleNamespace(pid=12345)
        with patch.object(controller, "start_updater", return_value=process) as start, \
                patch.object(controller, "discard_prepared_transaction") as discard:
            future = self.manager.install()
            self.assertIs(future.result(timeout=5), process)
            self.assertEqual(self.manager.state, controller.UpdateState.INSTALLING)
            self.assertFalse(self.manager.cancel())
            self.manager.close()
            start.assert_called_once_with(transaction)
            discard.assert_not_called()
        self.assertTrue(transaction.directory.exists())

    def test_helper_copy_and_validation_run_on_update_worker_without_blocking_caller(self):
        transaction = self.prepare_ready()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        caller = threading.current_thread().ident
        threads = []
        process = SimpleNamespace(pid=12345)

        def start(transaction):
            threads.append(threading.current_thread().ident)
            entered.set()
            self.assertTrue(release.wait(5))
            return process

        with patch.object(controller, "start_updater", side_effect=start):
            future = self.manager.install()
            self.assertTrue(entered.wait(5))
            self.assertFalse(future.done())
            self.assertNotEqual(threads[0], caller)
            self.assertEqual(self.manager.state, controller.UpdateState.INSTALLING)
            self.assertFalse(self.manager.cancel())
            release.set()
            self.assertIs(future.result(timeout=5), process)
        self.assertTrue(any(kind == "helper_started" and value is process for kind, value in self.drain()))

    def test_helper_start_failure_returns_ready_for_retry_and_keeps_prepared_transaction(self):
        transaction = self.prepare_ready()
        with patch.object(controller, "start_updater", side_effect=OSError("copy/fsync failure")):
            self.assertIsNone(self.manager.install().result(timeout=5))
        self.assertEqual(self.manager.state, controller.UpdateState.READY)
        self.assertIs(self.manager.transaction, transaction)
        self.assertTrue(transaction.directory.exists())
        self.assertTrue(any(kind == "error" and "copy/fsync failure" in value["message"] for kind, value in self.drain()))
        with patch.object(controller, "start_updater", return_value=SimpleNamespace(pid=12345)):
            self.assertEqual(self.manager.install().result(timeout=5).pid, 12345)

    def test_helper_start_failure_after_close_discards_only_uninstalled_transaction(self):
        transaction = self.prepare_ready()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def start(transaction):
            entered.set()
            self.assertTrue(release.wait(5))
            raise OSError("helper unavailable")

        with patch.object(controller, "start_updater", side_effect=start):
            future = self.manager.install()
            self.assertTrue(entered.wait(5))
            self.manager.close()
            self.assertTrue(transaction.directory.exists())
            release.set()
            self.assertIsNone(future.result(timeout=5))
        self.assertFalse(transaction.directory.exists())
        self.assertEqual(self.exe.read_bytes(), self.old_program)

    def test_event_queue_is_bounded_and_handles_consumer_race(self):
        class RacyQueue(queue.Queue):
            raced = False

            def get_nowait(self):
                if not self.raced:
                    self.raced = True
                    super().get_nowait()
                    raise queue.Empty()
                return super().get_nowait()

        events = RacyQueue(maxsize=1)
        events.put(("progress", (1, 10)))
        self.manager.events = events
        self.manager._emit("ready", "transaction")
        self.assertEqual(events.get_nowait(), ("ready", "transaction"))
        self.manager.events = queue.Queue(maxsize=64)
        with ThreadPoolExecutor(max_workers=4) as producers:
            list(producers.map(lambda index: self.manager._emit("progress" if index % 2 else "state", index), range(1000)))
        self.assertLessEqual(self.manager.events.qsize(), 64)
        self.manager._emit("error", {"message": "final"})
        self.assertTrue(any(kind == "error" for kind, value in self.drain()))


if __name__ == "__main__":
    unittest.main()
