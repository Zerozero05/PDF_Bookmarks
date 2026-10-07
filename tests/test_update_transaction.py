"""Install/rollback tests operate only on synthetic temporary programs/settings."""

import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from build_info import APP_ID, BuildInfo
from updater import UpdateError, journal, transaction
from updater.cleanup import cleanup_stale_update_transactions, cleanup_transaction
from updater.manifest import load_json, sha256_file
from updater.healthcheck import ack_health, validate_health_start
from updater.launcher import resume_pending_update


class FakeProcess:
    def __init__(self):
        self.pid = os.getpid()
        self.code = None

    def poll(self):
        return self.code

    def terminate(self):
        self.code = -1

    def kill(self):
        self.code = -9

    def wait(self, timeout=None):
        self.code = -1
        return self.code


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-update-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.install = self.root / "移动 文件夹 中文"
        self.install.mkdir()
        self.exe = self.install / "我的 PDF 程序.exe"
        self.exe.write_bytes(b"MZ OLD exe")
        self.config = self.root / "profile/settings.json"
        self.config.parent.mkdir()
        self.original_config = b'{"theme":"my-setting","backup":false,"future":{"keep":1}}'
        self.config.write_bytes(self.original_config)
        self.info = BuildInfo(APP_ID, "1.4.1", "single")
        self.package = self.root / "download.exe"
        self.package.write_bytes(b"MZ NEW exe")
        self.release = {"schema": 1, "app_id": APP_ID, "version": "1.5.0",
                        "channel": "stable", "assets": {"single": {"file": "download.exe",
                        "sha256": sha256_file(self.package), "size": self.package.stat().st_size}}}
        self.base = self.root / "temporary-transactions"

    def prepare(self):
        with patch.object(transaction.processes, "matching_processes", return_value=[]):
            return transaction.prepare_transaction(self.package, self.release, self.info, self.exe, self.config, self.base)

    def launch_healthy(self, command, **kwargs):
        directory = Path(command[command.index("--update-transaction") + 1])
        data = load_json(directory / "journal.json")
        journal.atomic_json(directory / "health.json", {"token": data["health_token"], "app_id": APP_ID,
                            "version": "1.5.0", "variant": self.info.variant, "pid": os.getpid(),
                            "config_ready": True, "gui_ready": True, "core_ready": True})
        return FakeProcess()

    def run_tx(self, tx, **kwargs):
        with patch.object(transaction.processes, "wait_for_release"), \
                patch.object(transaction.processes, "matching_processes", return_value=[os.getpid()]):
            return transaction.run_transaction(tx.directory, health_timeout=0.2, **kwargs)

    def clean(self, tx):
        with patch("updater.cleanup.process_alive", return_value=False):
            self.assertTrue(cleanup_transaction(tx.directory, APP_ID))
        self.assertFalse(tx.directory.exists())

    def portable(self):
        self.info = BuildInfo(APP_ID, "1.4.1", "portable")
        old_files = {self.exe.name: b"MZ OLD exe", "_internal/old.dll": b"obsolete", "resources/readme.txt": b"old resource"}
        new_files = {"PDF_Bookmarks.exe": b"MZ NEW exe", "_internal/new.dll": b"new runtime", "resources/readme.txt": b"new resource"}
        for name, payload in old_files.items():
            path = self.install / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        old_manifest = self.make_manifest(old_files, "1.4.1", self.exe.name)
        journal.atomic_json(self.install / transaction.PACKAGE, old_manifest)
        self.package = self.root / "download.zip"
        self.new_manifest = self.make_manifest(new_files, "1.5.0", "PDF_Bookmarks.exe")
        with zipfile.ZipFile(self.package, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("OfficialFolder/package-manifest.json", json.dumps(self.new_manifest))
            for name, payload in new_files.items():
                archive.writestr("OfficialFolder/" + name, payload)
        self.release["assets"] = {"portable": {"file": "download.zip", "sha256": sha256_file(self.package)}}
        return old_files, new_files

    @staticmethod
    def make_manifest(files, version, entrypoint):
        return {"schema": 1, "app_id": APP_ID, "version": version, "variant": "portable", "entrypoint": entrypoint,
                "managed_files": [{"path": path, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                                  for path, payload in files.items()]}

    def test_single_renamed_moved_chinese_space_path_success(self):
        tx = self.prepare()
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "committed")
        self.assertEqual(self.exe.read_bytes(), b"MZ NEW exe")
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.assertEqual(list(self.install.iterdir()), [self.exe])
        self.clean(tx)
        self.assertFalse(list(self.base.glob("**/*.old*")))
        self.assertFalse(list(self.base.glob("**/*.new*")))
        self.assertFalse(list(self.base.glob("**/*.part")))

    def test_original_name_single_and_other_single_not_managed(self):
        official = self.install / "PDF_Bookmarks.exe"
        self.exe.rename(official)
        self.exe = official
        neighbor = self.install / "UserTool.exe"
        neighbor.write_bytes(b"USER")
        tx = self.prepare()
        self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "committed")
        self.assertEqual(neighbor.read_bytes(), b"USER")
        self.clean(tx)

    def test_single_name_move_path_matrix(self):
        scenarios = (("original", "PDF_Bookmarks.exe"), ("renamed", "MyTool.exe"),
                     ("moved", "PDF_Bookmarks.exe"), ("renamed_moved", "MyTool.exe"),
                     ("中文目录", "中文程序.exe"), ("directory with spaces", "file with spaces.exe"))
        for folder, launcher in scenarios:
            with self.subTest(folder=folder, launcher=launcher):
                destination = self.root / "single_matrix" / folder
                destination.mkdir(parents=True)
                self.exe = destination / launcher
                self.exe.write_bytes(b"MZ OLD exe")
                tx = self.prepare()
                self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "committed")
                self.assertEqual(self.exe.read_bytes(), b"MZ NEW exe")
                self.assertEqual([p.name for p in destination.iterdir()], [launcher])
                self.clean(tx)

    def test_hash_error_never_modifies_program(self):
        self.package.write_bytes(b"MZ broken download")
        with self.assertRaisesRegex(UpdateError, "SHA-256"):
            self.prepare()
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_no_write_permission_preflight(self):
        with patch.object(transaction, "_writable_directory", side_effect=UpdateError("不可写")):
            with self.assertRaises(UpdateError):
                self.prepare()
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")

    def test_disk_space_failure(self):
        with patch.object(transaction.shutil, "disk_usage", return_value=type("Space", (), {"free": 1})()):
            with self.assertRaisesRegex(UpdateError, "空间"):
                self.prepare()
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")

    def test_other_instance_and_lock_stop_before_backup(self):
        tx = self.prepare()
        with patch.object(transaction.processes, "wait_for_release", side_effect=UpdateError("other instance")):
            self.assertEqual(transaction.run_transaction(tx.directory, launch=self.launch_healthy), "failed")
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertIsNone(load_json(tx.directory / "journal.json")["config_snapshot"])
        self.clean(tx)

    def test_failed_exclusive_file_open_does_not_start_install(self):
        tx = self.prepare()
        with patch.object(transaction.processes, "check_file_unlocked", side_effect=UpdateError("file locked")):
            self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "failed")
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertIsNone(load_json(tx.directory / "journal.json")["config_snapshot"])
        self.clean(tx)

    def test_health_failure_rolls_back_program_and_migrated_configuration(self):
        tx = self.prepare()

        def bad_health(command, **kwargs):
            self.config.write_text('{"schema":99,"theme":"new"}', encoding="utf-8")
            process = FakeProcess()
            process.code = 1
            return process

        self.assertEqual(self.run_tx(tx, launch=bad_health), "rolled_back")
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.clean(tx)

    def test_missing_health_receipt_times_out_and_rolls_back(self):
        tx = self.prepare()
        with patch.object(transaction.processes, "terminate_tree", side_effect=lambda p: p.terminate()):
            self.assertEqual(self.run_tx(tx, launch=lambda *a, **k: FakeProcess()), "rolled_back")
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.clean(tx)

    def test_configuration_created_by_failed_new_version_is_removed(self):
        self.config.unlink()
        tx = self.prepare()

        def bad_health(*args, **kwargs):
            self.config.write_bytes(b"new configuration")
            process = FakeProcess()
            process.code = 1
            return process

        self.assertEqual(self.run_tx(tx, launch=bad_health), "rolled_back")
        self.assertFalse(self.config.exists())
        self.clean(tx)

    def test_persistent_journal_recovers_interrupted_replace(self):
        tx = self.prepare()

        def power_loss(operation):
            raise SystemExit("simulated power loss")

        with self.assertRaises(SystemExit):
            self.run_tx(tx, launch=self.launch_healthy, fault_hook=power_loss)
        self.assertEqual(self.exe.read_bytes(), b"MZ NEW exe")
        self.config.write_bytes(b"interrupted migrated config")
        with patch.object(transaction.processes, "process_alive", return_value=False), \
                patch.object(transaction.processes, "wait_for_release"):
            self.assertEqual(transaction.recover_transaction(tx.directory), "rolled_back")
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.clean(tx)

    def test_portable_replaces_managed_only_and_removes_obsolete_runtime(self):
        self.portable()
        extras = {"论文.pdf": b"USER PDF", "custom.txt": b"USER TXT", "我的文件夹/a.json": b"USER DATA", "config.json": b"USER SETTINGS", "UserData/history": b"USER HISTORY"}
        for name, payload in extras.items():
            path = self.install / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        tx = self.prepare()
        self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "committed")
        self.assertEqual(self.exe.read_bytes(), b"MZ NEW exe")
        self.assertFalse((self.install / "PDF_Bookmarks.exe").exists())
        self.assertFalse((self.install / "_internal/old.dll").exists())
        self.assertEqual((self.install / "_internal/new.dll").read_bytes(), b"new runtime")
        self.assertEqual((self.install / "resources/readme.txt").read_bytes(), b"new resource")
        installed = load_json(self.install / transaction.INSTALLED)
        self.assertEqual(installed["version"], "1.5.0")
        self.assertEqual(installed["entrypoint"], self.exe.name)
        for name, payload in extras.items():
            self.assertEqual((self.install / name).read_bytes(), payload)
        self.clean(tx)

    def test_portable_first_use_manifest_maps_renamed_entrypoint(self):
        self.portable()
        old = load_json(self.install / transaction.PACKAGE)
        old["managed_files"][0]["path"] = "Official.exe"
        old["entrypoint"] = "Official.exe"
        journal.atomic_json(self.install / transaction.PACKAGE, old)
        result = transaction.ensure_installed_manifest(self.exe, self.info)
        self.assertEqual(result["entrypoint"], self.exe.name)
        self.assertEqual(result["managed_files"][0]["path"], self.exe.name)

    def test_portable_rename_move_matrix(self):
        self.portable()
        original_install = self.install
        original_exe = self.exe
        scenarios = (("PDF_Bookmarks", "PDF_Bookmarks.exe"), ("RenamedFolder", "PDF_Bookmarks.exe"),
                     ("MovedFolder", "PDF_Bookmarks.exe"), ("PDF_BookmarksRenamedEntry", "MyPDF.exe"),
                     ("FolderAndEntryRenamed", "Renamed.exe"), ("中文文件夹", "中文程序.exe"),
                     ("folder with spaces", "file with spaces.exe"))
        for folder, launcher in scenarios:
            with self.subTest(folder=folder, launcher=launcher):
                self.install = self.root / "portable_matrix" / folder
                shutil.copytree(original_install, self.install)
                (self.install / original_exe.name).rename(self.install / launcher)
                self.exe = self.install / launcher
                tx = self.prepare()
                self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "committed")
                self.assertEqual(self.exe.read_bytes(), b"MZ NEW exe")
                self.assertFalse((self.install / "_internal/old.dll").exists())
                self.assertEqual(load_json(self.install / transaction.INSTALLED)["entrypoint"], launcher)
                self.clean(tx)

    @unittest.skipUnless(os.name == "nt", "Windows multi-volume paths")
    def test_portable_moved_to_another_drive(self):
        self.portable()
        workspace = Path(__file__).resolve().parent.parent.parent
        if workspace.drive.casefold() == self.install.drive.casefold():
            self.skipTest("Only one writable drive in this CI environment")
        with tempfile.TemporaryDirectory(prefix="pdf-update-crossdrive-", dir=workspace) as temporary:
            destination = Path(temporary) / "跨盘 移动后的目录"
            shutil.move(str(self.install), destination)
            self.install = destination
            self.exe = destination / self.exe.name
            tx = self.prepare()
            self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "committed")
            self.assertEqual(self.exe.read_bytes(), b"MZ NEW exe")
            self.assertFalse((destination / "_internal/old.dll").exists())
            self.clean(tx)

    def test_unknown_filename_collision_rejected(self):
        self.portable()
        unknown = self.install / "_internal/new.dll"
        unknown.write_bytes(b"USER UNKNOWN")
        with self.assertRaisesRegex(UpdateError, "未知文件"):
            self.prepare()
        self.assertEqual(unknown.read_bytes(), b"USER UNKNOWN")
        self.assertTrue((self.install / "_internal/old.dll").exists())

    def test_portable_health_failure_restores_manifest_runtime_and_configuration(self):
        old, new = self.portable()
        tx = self.prepare()
        old_manifest_bytes = (self.install / transaction.INSTALLED).read_bytes()

        def bad_launch(*args, **kwargs):
            self.config.write_bytes(b"migrated incompatible")
            process = FakeProcess()
            process.code = 1
            return process

        self.assertEqual(self.run_tx(tx, launch=bad_launch), "rolled_back")
        for name, payload in old.items():
            self.assertEqual((self.install / name).read_bytes(), payload)
        self.assertFalse((self.install / "_internal/new.dll").exists())
        self.assertEqual((self.install / transaction.INSTALLED).read_bytes(), old_manifest_bytes)
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.clean(tx)

    def test_portable_replace_fault_rolls_back(self):
        old, new = self.portable()
        tx = self.prepare()

        def fail(operation):
            if operation["path"] == "_internal/old.dll":
                raise OSError("replacement failed after managed deletion")

        self.assertEqual(self.run_tx(tx, launch=self.launch_healthy, fault_hook=fail), "rolled_back")
        for name, payload in old.items():
            self.assertEqual((self.install / name).read_bytes(), payload)
        self.assertFalse((self.install / "_internal/new.dll").exists())
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.clean(tx)

    def test_portable_interrupted_install_recovers(self):
        old, new = self.portable()
        tx = self.prepare()

        def crash(operation):
            if operation["path"] == "_internal/old.dll":
                raise SystemExit("portable power loss")

        with self.assertRaises(SystemExit):
            self.run_tx(tx, launch=self.launch_healthy, fault_hook=crash)
        with patch.object(transaction.processes, "process_alive", return_value=False), \
                patch.object(transaction.processes, "wait_for_release"):
            self.assertEqual(transaction.recover_transaction(tx.directory), "rolled_back")
        for name, payload in old.items():
            self.assertEqual((self.install / name).read_bytes(), payload)
        self.clean(tx)

    def test_rollback_failure_preserves_persisted_restore_progress(self):
        self.portable()
        tx = self.prepare()
        original_copy = transaction._copy_atomic
        restored = []

        def fail_second_restore(source, destination, temporary_path=None):
            if "backup/program" in Path(source).as_posix():
                restored.append(Path(destination))
                if len(restored) == 2:
                    raise OSError("second restore temporarily locked")
            return original_copy(source, destination, temporary_path)

        def failed_launch(*args, **kwargs):
            process = FakeProcess()
            process.code = 1
            return process

        with patch.object(transaction, "_copy_atomic", side_effect=fail_second_restore):
            self.assertEqual(self.run_tx(tx, launch=failed_launch), "rollback_started")
        data = load_json(tx.directory / "journal.json")
        first_restored = restored[0].relative_to(self.install).as_posix()
        operation = next(item for item in data["operations"] if item["path"] == first_restored)
        self.assertFalse(operation["started"])
        self.assertFalse(operation["completed"])
        self.assertIn("second restore", data["rollback_error"])
        with patch.object(transaction.processes, "process_alive", return_value=False), \
                patch.object(transaction.processes, "wait_for_release"):
            self.assertEqual(transaction.recover_transaction(tx.directory), "rolled_back")
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.clean(tx)

    @unittest.skipUnless(os.name == "nt", "Windows non-delete-shared reader")
    def test_journal_atomic_replace_retries_transient_reader_lock(self):
        import ctypes
        from ctypes import wintypes
        path = self.root / "journal-reader-lock.json"
        journal.atomic_json(path, {"state": "before"})
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(path), 0x80000000, 1 | 2, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)

        def release_reader():
            time.sleep(0.12)
            kernel.CloseHandle(handle)

        thread = threading.Thread(target=release_reader)
        thread.start()
        try:
            start = time.monotonic()
            journal.atomic_json(path, {"state": "after"})
            self.assertGreaterEqual(time.monotonic() - start, 0.1)
        finally:
            thread.join()
        self.assertEqual(load_json(path), {"state": "after"})
        self.assertFalse(list(self.root.glob(".journal-*")))

    @unittest.skipUnless(os.name == "nt", "Windows persistent sharing error")
    def test_atomic_replace_persistent_lock_fails_without_changing_old_file(self):
        source = self.root / "staged.txt"
        target = self.root / "installed.txt"
        source.write_bytes(b"new")
        target.write_bytes(b"old")
        error = PermissionError("persistent Windows access denial")
        error.winerror = 5
        with patch.object(journal.os, "replace", side_effect=error), self.assertRaises(PermissionError):
            journal.replace_file(source, target, timeout=0)
        self.assertEqual(source.read_bytes(), b"new")
        self.assertEqual(target.read_bytes(), b"old")

    def test_journal_failed_write_does_not_advance_in_memory_state(self):
        value = {"state": "healthcheck_ok", "updated_at": "before"}
        with patch.object(journal, "atomic_json", side_effect=OSError("journal disk write failed")):
            with self.assertRaises(OSError):
                journal.save(self.root, value, "committed")
        self.assertEqual(value, {"state": "healthcheck_ok", "updated_at": "before"})

    def test_durable_commit_failure_rolls_back_instead_of_false_success(self):
        tx = self.prepare()
        original_atomic_json = journal.atomic_json

        def cannot_commit(path, value):
            if Path(path).name == "journal.json" and value.get("state") == "committed":
                raise OSError("commit could not be made durable")
            return original_atomic_json(path, value)

        with patch.object(journal, "atomic_json", side_effect=cannot_commit), \
                patch.object(transaction.processes, "terminate_tree", side_effect=lambda p: p.terminate()):
            self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "rolled_back")
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertEqual(load_json(tx.directory / "journal.json")["state"], "rolled_back")
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.clean(tx)

    def test_gui_health_requires_config_core_window_token_and_actual_image(self):
        tx = self.prepare()
        data = load_json(tx.directory / "journal.json")
        journal.save(tx.directory, data, "verifying_install")
        newer = BuildInfo(APP_ID, "1.5.0", "single")
        with patch("updater.healthcheck.sys.executable", str(self.exe)):
            self.assertEqual(validate_health_start(tx.directory, data["health_token"], newer)["config_path"], str(self.config))
            with self.assertRaises(UpdateError):
                validate_health_start(tx.directory, "wrong-token", newer)
            for name in ("config_ready", "core_ready", "gui_ready"):
                values = dict(config_ready=True, core_ready=True, gui_ready=True)
                values[name] = False
                with self.subTest(component=name), self.assertRaises(UpdateError):
                    ack_health(tx.directory, data["health_token"], newer, **values)
        with self.assertRaisesRegex(UpdateError, "路径"):
            validate_health_start(tx.directory, data["health_token"], newer)

    def test_ready_discard_and_never_install_without_consent_on_next_start(self):
        tx = self.prepare()
        with patch("updater.launcher.sys.frozen", True, create=True), \
                patch("updater.launcher.start_updater") as start:
            self.assertFalse(resume_pending_update(self.info, self.exe, self.base))
            start.assert_not_called()
        self.assertTrue(transaction.discard_prepared_transaction(tx))
        self.assertFalse(tx.directory.exists())
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")

    def test_prepared_payload_independent_of_download_directory(self):
        tx = self.prepare()
        self.package.unlink()
        self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "committed")
        self.assertEqual(self.exe.read_bytes(), b"MZ NEW exe")
        self.clean(tx)

    def test_cleanup_failure_after_commit_does_not_rollback(self):
        tx = self.prepare()
        with patch("updater.cleanup.cleanup_transaction", side_effect=OSError("helper still closing")):
            self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "committed")
        self.assertEqual(self.exe.read_bytes(), b"MZ NEW exe")
        self.assertEqual(load_json(tx.directory / "journal.json")["state"], "committed")
        self.clean(tx)

    def test_configuration_target_cannot_be_managed_program_file(self):
        self.portable()
        self.config = self.install / "resources/readme.txt"
        with self.assertRaisesRegex(UpdateError, "配置"):
            self.prepare()
        self.assertEqual(self.config.read_bytes(), b"old resource")

    @unittest.skipUnless(os.name == "nt", "Windows junctions")
    def test_windows_junction_program_root_is_rejected(self):
        import subprocess
        link = self.root / "program-junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.install)],
                       capture_output=True, check=True)
        try:
            self.exe = link / self.exe.name
            with self.assertRaisesRegex(UpdateError, "联接"):
                self.prepare()
            self.assertEqual((self.install / self.exe.name).read_bytes(), b"MZ OLD exe")
        finally:
            # Remove only the synthetic junction itself, never its target.
            link.rmdir()

    def test_invalid_zip_entries_and_tampered_member_never_installed(self):
        self.portable()
        original = self.package.read_bytes()
        for name, payload in (("../escape", b"bad"), ("OfficialFolder/_internal/New.DLL", b"duplicate"),
                              ("OfficialFolder/extra.txt", b"not in manifest")):
            with self.subTest(name=name):
                self.package.write_bytes(original)
                with zipfile.ZipFile(self.package, "a") as archive:
                    archive.writestr(name, payload)
                self.release["assets"]["portable"]["sha256"] = sha256_file(self.package)
                with self.assertRaises(UpdateError):
                    self.prepare()
                self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.package.write_bytes(original)
        with zipfile.ZipFile(self.package, "a") as archive:
            link = zipfile.ZipInfo("OfficialFolder/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "../outside")
        self.release["assets"]["portable"]["sha256"] = sha256_file(self.package)
        with self.assertRaisesRegex(UpdateError, "链接"):
            self.prepare()

    def test_wrong_package_hash_record_is_rejected(self):
        self.portable()
        manifest = copy.deepcopy(self.new_manifest)
        manifest["managed_files"][1]["sha256"] = "0" * 64
        with zipfile.ZipFile(self.package, "r") as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        files["OfficialFolder/package-manifest.json"] = json.dumps(manifest).encode()
        with zipfile.ZipFile(self.package, "w") as archive:
            for name, value in files.items():
                archive.writestr(name, value)
        self.release["assets"]["portable"]["sha256"] = sha256_file(self.package)
        with self.assertRaisesRegex(UpdateError, "SHA-256"):
            self.prepare()
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        self.assertFalse(list(self.base.glob("tx-*")))
        self.assertTrue(list((self.base / "diagnostics").glob("tx-*_journal.json")))

    def test_cleanup_retains_unfinished_transactions_and_other_app(self):
        tx = self.prepare()
        other = self.base / ("tx-" + "b" * 32)
        other.mkdir()
        journal.atomic_json(other / "journal.json", {"schema": 1, "transaction": other.name, "app_id": "other", "state": "committed"})
        result = cleanup_stale_update_transactions(APP_ID, self.base)
        self.assertEqual(result[str(tx.directory)], "pending")
        self.assertTrue(other.exists())
        self.assertTrue(tx.directory.exists())

    def mark_completed(self, tx):
        data = load_json(tx.directory / "journal.json")
        data["helper_pid"] = None
        journal.save(tx.directory, data, "committed")
        return data

    @unittest.skipUnless(os.name == "nt", "Windows locked temporary helper")
    def test_cleanup_keeps_journal_when_helper_file_is_temporarily_locked(self):
        import ctypes
        from ctypes import wintypes
        tx = self.prepare()
        self.mark_completed(tx)
        helper = tx.directory / "updater.exe"
        helper.write_bytes(b"MZ synthetic helper")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(helper), 0x80000000, 1 | 2, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            with self.assertRaises(OSError):
                cleanup_transaction(tx.directory, APP_ID)
            self.assertTrue((tx.directory / "journal.json").is_file())
            self.assertEqual(load_json(tx.directory / "journal.json")["app_id"], APP_ID)
            self.assertTrue(helper.is_file())
        finally:
            kernel.CloseHandle(handle)
        self.assertTrue(cleanup_transaction(tx.directory, APP_ID))
        self.assertFalse(tx.directory.exists())
        self.assertFalse(list(self.base.glob("cleanup_*.json")))

    def test_concurrent_completed_cleanup_is_idempotent(self):
        tx = self.prepare()
        self.mark_completed(tx)
        barrier = threading.Barrier(2)

        def clean():
            barrier.wait()
            return cleanup_transaction(tx.directory, APP_ID)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(clean), executor.submit(clean)]
            self.assertTrue(all(future.result(timeout=10) for future in futures))
        self.assertFalse(tx.directory.exists())
        self.assertFalse(list(self.base.glob("cleanup_*.json")))
        self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")

    def test_final_rmdir_failure_keeps_external_ownership_for_startup_retry(self):
        tx = self.prepare()
        self.mark_completed(tx)
        original_rmdir = Path.rmdir

        def fail_final_rmdir(path):
            if path == tx.directory:
                raise PermissionError("temporary directory reader")
            return original_rmdir(path)

        with patch.object(Path, "rmdir", autospec=True, side_effect=fail_final_rmdir):
            with self.assertRaises(PermissionError):
                cleanup_transaction(tx.directory, APP_ID)
        self.assertTrue(tx.directory.is_dir())
        self.assertFalse((tx.directory / "journal.json").exists())
        receipt = self.base / ("cleanup_" + tx.directory.name + ".json")
        self.assertEqual(load_json(receipt)["app_id"], APP_ID)
        result = cleanup_stale_update_transactions(APP_ID, self.base)
        self.assertEqual(result[str(tx.directory)], "cleaned")
        self.assertFalse(tx.directory.exists())
        self.assertFalse(receipt.exists())

    def test_cleanup_receipt_rejects_foreign_identity_pending_state_and_malformed_data(self):
        tx = self.prepare()
        data = self.mark_completed(tx)
        (tx.directory / "journal.json").unlink()
        receipt = self.base / ("cleanup_" + tx.directory.name + ".json")
        for changed in (dict(data, app_id="other"), dict(data, schema=True), dict(data, operations=[1]),
                        dict(data, target_exe=str(self.root / "outside.exe"))):
            journal.atomic_json(receipt, changed)
            with self.assertRaises(UpdateError):
                cleanup_transaction(tx.directory, APP_ID)
            self.assertTrue(tx.directory.exists())
            self.assertTrue(receipt.exists())
        journal.atomic_json(receipt, dict(data, state="installing"))
        self.assertFalse(cleanup_transaction(tx.directory, APP_ID))
        self.assertTrue(tx.directory.exists())
        journal.atomic_json(receipt, data)
        self.assertTrue(cleanup_transaction(tx.directory, APP_ID))
        self.assertFalse(receipt.exists())

    def test_cleanup_retains_unknown_top_level_file_and_ownership(self):
        tx = self.prepare()
        self.mark_completed(tx)
        unknown = tx.directory / "user_note.txt"
        unknown.write_bytes(b"unknown user information")
        with self.assertRaisesRegex(UpdateError, "未知文件"):
            cleanup_transaction(tx.directory, APP_ID)
        self.assertEqual(unknown.read_bytes(), b"unknown user information")
        self.assertTrue((tx.directory / "journal.json").is_file())

    def test_cleanup_accepts_owned_health_failure_diagnostic(self):
        tx = self.prepare()
        data = load_json(tx.directory / "journal.json")
        data["helper_pid"] = None
        journal.save(tx.directory, data, "rolled_back")
        journal.atomic_json(tx.directory / "health-failure.json", {"reason": "synthetic malformed config"})
        self.assertTrue(cleanup_transaction(tx.directory, APP_ID))
        self.assertFalse(tx.directory.exists())
        self.assertTrue(list((self.base / "diagnostics").glob("tx-*_journal.json")))

    @unittest.skipUnless(os.name == "nt", "Windows readonly attribute")
    def test_windows_readonly_target_prevents_install(self):
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetFileAttributesW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
        self.assertTrue(kernel.SetFileAttributesW(str(self.exe), 1))
        try:
            with self.assertRaisesRegex(UpdateError, "只读"):
                self.prepare()
            self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        finally:
            kernel.SetFileAttributesW(str(self.exe), 0x80)

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_portable_runtime_file_lock_stops_before_changing_any_file(self):
        import ctypes
        from ctypes import wintypes
        old, new = self.portable()
        tx = self.prepare()
        locked = self.install / "_internal/old.dll"
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(locked), 0x80000000, 1, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            self.assertEqual(self.run_tx(tx, launch=self.launch_healthy), "failed")
        finally:
            kernel.CloseHandle(handle)
        for name, payload in old.items():
            self.assertEqual((self.install / name).read_bytes(), payload)
        self.assertIsNone(load_json(tx.directory / "journal.json")["config_snapshot"])
        self.clean(tx)

    @unittest.skipUnless(os.name == "nt", "Windows file attributes")
    def test_portable_readonly_managed_runtime_stops_before_install(self):
        import ctypes
        self.portable()
        target = self.install / "_internal/old.dll"
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetFileAttributesW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
        self.assertTrue(kernel.SetFileAttributesW(str(target), 1))
        try:
            with self.assertRaisesRegex(UpdateError, "只读"):
                self.prepare()
            self.assertEqual(target.read_bytes(), b"obsolete")
            self.assertEqual(self.exe.read_bytes(), b"MZ OLD exe")
        finally:
            kernel.SetFileAttributesW(str(target), 0x80)


if __name__ == "__main__":
    unittest.main()
