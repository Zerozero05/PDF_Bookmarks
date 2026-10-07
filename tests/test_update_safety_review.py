"""Independent regressions for modal task guards and truthful health receipts."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tkinterdnd2 import TkinterDnD

import bookmarks_gui
import gui_entry
from build_info import APP_ID
from updater import UpdateError
from updater.cleanup import cleanup_stale_update_transactions, cleanup_transaction
from updater.controller import UpdateState
from updater.journal import atomic_json
from updater.manifest import load_json


class UpdateSafetyReviewTests(unittest.TestCase):
    def test_launch_acknowledges_only_after_update_protocol_initialization(self):
        order = []
        root, window = Mock(), Mock()
        root.update_idletasks.side_effect = lambda: order.append("layout")
        window.enable_updates.side_effect = lambda: order.append("update_protocol")
        root.mainloop.side_effect = lambda: order.append("mainloop")
        with patch.object(bookmarks_gui.TkinterDnD, "Tk", return_value=root), \
                patch.object(bookmarks_gui, "BookmarkWindow", return_value=window):
            bookmarks_gui.launch(on_ready=lambda owner: order.append("health_ack"))
        self.assertLess(order.index("update_protocol"), order.index("health_ack"))
        self.assertLess(order.index("layout"), order.index("health_ack"))
        self.assertLess(order.index("health_ack"), order.index("mainloop"))

    def test_update_protocol_initialization_failure_never_acknowledges_health(self):
        root, window, ack = Mock(), Mock(), Mock()
        window.enable_updates.side_effect = RuntimeError("update protocol cannot initialize")
        with patch.object(bookmarks_gui.TkinterDnD, "Tk", return_value=root), \
                patch.object(bookmarks_gui, "BookmarkWindow", return_value=window):
            with self.assertRaises(RuntimeError):
                bookmarks_gui.launch(on_ready=ack)
        ack.assert_not_called()
        root.mainloop.assert_not_called()

    def test_pdf_core_initialization_failure_exits_without_healthy_receipt(self):
        with tempfile.TemporaryDirectory(prefix="pdf-core-health-review-") as name:
            config = Path(name) / "settings.json"
            config.write_bytes(b'{"schema":1,"backup":false,"unknown":{"keep":true}}')
            original = config.read_bytes()

            def launch(*args, **kwargs):
                kwargs["on_ready"](Mock())

            with patch("updater.healthcheck.validate_health_start", return_value={"config_path": str(config)}), \
                    patch("updater.healthcheck.ack_health") as ack, \
                    patch("bookmarks_gui.launch", side_effect=launch), \
                    patch("pymupdf.open", side_effect=ImportError("PDF core is unavailable")):
                self.assertEqual(gui_entry.main(["--update-transaction", name, "--update-token", "token"]), 1)
            ack.assert_not_called()
            self.assertEqual(config.read_bytes(), original)
            self.assertIn("PDF core is unavailable", (Path(name) / "health-failure.json").read_text(encoding="utf-8"))

    def test_install_rechecks_tasks_changed_during_confirmation(self):
        with tempfile.TemporaryDirectory(prefix="pdf-modal-update-review-") as name:
            root = TkinterDnD.Tk()
            root.withdraw()
            owner = bookmarks_gui.BookmarkWindow(root, settings_path=Path(name) / "settings.json")
            try:
                owner._show_updates()
                dialog = owner.updates

                def confirm(*args, **kwargs):
                    # Tk's modal confirmation runs a nested event loop; an
                    # existing callback may start a PDF operation meanwhile.
                    owner.busy = True
                    return True

                with patch("update_dialog.messagebox.askyesno", side_effect=confirm), \
                        patch("update_dialog.messagebox.showinfo"), \
                        patch.object(dialog.controller, "install") as install:
                    dialog._install()
                install.assert_not_called()
                self.assertFalse(owner.closed)
            finally:
                owner.busy = False
                if not owner.closed:
                    owner._close()

    def test_async_install_temporarily_blocks_new_pdf_jobs_and_closes_after_helper_event(self):
        with tempfile.TemporaryDirectory(prefix="pdf-async-install-ui-review-") as name:
            root = TkinterDnD.Tk()
            root.withdraw()
            owner = bookmarks_gui.BookmarkWindow(root, settings_path=Path(name) / "settings.json")
            try:
                owner._show_updates()
                dialog = owner.updates

                def begin():
                    dialog.controller.state = UpdateState.INSTALLING
                    return Mock()

                with patch("update_dialog.messagebox.askyesno", return_value=True), \
                        patch.object(dialog.controller, "install", side_effect=begin), \
                        patch.object(owner.executor, "submit") as pdf_job:
                    dialog._install()
                    self.assertTrue(owner.busy)
                    self.assertTrue(dialog._install_pending)
                    self.assertFalse(owner.closed)
                    owner._preview()
                    owner._open_editor()
                    owner._handle_drop_paths([Path(name) / "用户 PDF.pdf"])
                    pdf_job.assert_not_called()
                dialog.controller.events.put(("helper_started", Mock()))
                root.after_cancel(dialog._poll_after)
                dialog._poll()
                self.assertTrue(owner.closed)
                self.assertFalse(dialog._install_pending)
            finally:
                owner.busy = False
                if not owner.closed:
                    owner._close()

    def test_async_helper_failure_releases_task_guard_and_keeps_main_window(self):
        with tempfile.TemporaryDirectory(prefix="pdf-async-failure-ui-review-") as name:
            root = TkinterDnD.Tk()
            root.withdraw()
            owner = bookmarks_gui.BookmarkWindow(root, settings_path=Path(name) / "settings.json")
            try:
                owner._show_updates()
                dialog = owner.updates
                owner._set_busy(True)
                dialog._install_pending = True
                dialog.controller.state = UpdateState.READY
                dialog.controller.events.put(("error", {"message": "helper copy failed", "automatic": False}))
                root.after_cancel(dialog._poll_after)
                dialog._poll()
                self.assertFalse(owner.busy)
                self.assertFalse(owner.closed)
                self.assertFalse(dialog._install_pending)
                self.assertEqual(dialog.status.get(), "helper copy failed")
            finally:
                owner.busy = False
                if not owner.closed:
                    owner._close()

    def test_pending_commit_blocks_pdf_entries_until_durable_commit(self):
        with tempfile.TemporaryDirectory(prefix="pdf-pending-commit-ui-review-") as name:
            directory = Path(name) / "transaction"
            directory.mkdir()
            atomic_json(directory / "journal.json", {"state": "verifying_install"})
            root = TkinterDnD.Tk()
            root.withdraw()
            owner = bookmarks_gui.BookmarkWindow(root, settings_path=Path(name) / "settings.json")
            try:
                owner.pdf.set(str(Path(name) / "用户 PDF.pdf"))
                owner._set_busy(True)
                with patch.object(root, "after") as poll, \
                        patch.object(owner.executor, "submit") as pdf_job, \
                        patch.object(owner, "_checked_items") as selected, \
                        patch("toc_editor.open_editor") as editor:
                    gui_entry.await_update_commit(owner, directory)
                    self.assertTrue(owner.busy)
                    self.assertEqual(str(owner.preview_button.cget("state")), "disabled")
                    self.assertEqual(str(owner.write_button.cget("state")), "disabled")
                    owner._preview()
                    owner._open_editor()
                    owner._write()
                    owner._handle_drop_paths([Path(name) / "another.pdf"])
                    pdf_job.assert_not_called()
                    selected.assert_not_called()
                    editor.assert_not_called()
                    self.assertEqual(owner.drop_paths, [])
                    poll.assert_called_once_with(150, gui_entry.await_update_commit, owner, directory)
                atomic_json(directory / "journal.json", {"state": "committed"})
                with patch.object(root, "after") as poll:
                    gui_entry.await_update_commit(owner, directory)
                self.assertFalse(owner.busy)
                self.assertEqual(str(owner.preview_button.cget("state")), "normal")
                self.assertIn("更新已完成", owner.status.get())
                poll.assert_not_called()
                with patch.object(owner.executor, "submit") as pdf_job:
                    owner._preview()
                    pdf_job.assert_called_once()
            finally:
                owner.busy = False
                if not owner.closed:
                    owner._close()

    def test_commit_failure_or_unreadable_journal_keeps_pdf_guard(self):
        with tempfile.TemporaryDirectory(prefix="pdf-failed-commit-ui-review-") as name:
            directory = Path(name) / "transaction"
            directory.mkdir()
            root = TkinterDnD.Tk()
            root.withdraw()
            owner = bookmarks_gui.BookmarkWindow(root, settings_path=Path(name) / "settings.json")
            try:
                owner._set_busy(True)
                for state in ("healthcheck_ok", "rollback_started", None):
                    with self.subTest(state=state):
                        if state is None:
                            (directory / "journal.json").write_bytes(b"incomplete journal")
                        else:
                            atomic_json(directory / "journal.json", {"state": state})
                        with patch.object(root, "after") as poll, \
                                patch.object(owner.executor, "submit") as pdf_job:
                            gui_entry.await_update_commit(owner, directory)
                            owner._preview()
                            owner._write()
                        self.assertTrue(owner.busy)
                        self.assertFalse(owner.closed)
                        pdf_job.assert_not_called()
                        poll.assert_called_once_with(150, gui_entry.await_update_commit, owner, directory)
            finally:
                owner.busy = False
                if not owner.closed:
                    owner._close()

    def test_health_ack_observes_real_tk_guard_already_applied(self):
        with tempfile.TemporaryDirectory(prefix="pdf-health-guard-order-review-") as name:
            config = Path(name) / "settings.json"
            config.write_bytes(b'{"schema":1,"backup":false,"unknown":{"keep":true}}')
            original = config.read_bytes()
            root = TkinterDnD.Tk()
            root.withdraw()
            owner = bookmarks_gui.BookmarkWindow(root, settings_path=config)
            order = []
            set_busy = owner._set_busy

            def guard(value):
                order.append("guard")
                set_busy(value)

            def acknowledge(*args, **kwargs):
                order.append("ack")
                self.assertTrue(owner.busy)
                self.assertEqual(str(owner.preview_button.cget("state")), "disabled")
                self.assertIn("正在完成程序更新", owner.status.get())
                self.assertTrue(kwargs["gui_ready"])

            def launch(*args, **kwargs):
                kwargs["on_ready"](owner)

            try:
                with patch("updater.healthcheck.validate_health_start", return_value={"config_path": str(config)}), \
                        patch("updater.healthcheck.ack_health", side_effect=acknowledge) as ack, \
                        patch("bookmarks_gui.launch", side_effect=launch), \
                        patch.object(owner, "_set_busy", side_effect=guard), \
                        patch.object(root, "after") as poll:
                    self.assertEqual(gui_entry.main(["--update-transaction", name, "--update-token", "token"]), 0)
                self.assertEqual(order, ["guard", "ack"])
                ack.assert_called_once()
                poll.assert_called_once_with(150, gui_entry.await_update_commit, owner, name)
                self.assertTrue(owner.busy)
                self.assertEqual(config.read_bytes(), original)
            finally:
                owner.busy = False
                if not owner.closed:
                    owner._close()

    def test_real_tk_guard_initialization_failure_never_acknowledges_health(self):
        with tempfile.TemporaryDirectory(prefix="pdf-health-guard-failure-review-") as name:
            config = Path(name) / "settings.json"
            config.write_bytes(b'{"schema":1,"backup":false,"unknown":{"keep":true}}')
            original = config.read_bytes()
            root = TkinterDnD.Tk()
            root.withdraw()
            owner = bookmarks_gui.BookmarkWindow(root, settings_path=config)

            def launch(*args, **kwargs):
                kwargs["on_ready"](owner)

            try:
                with patch("updater.healthcheck.validate_health_start", return_value={"config_path": str(config)}), \
                        patch("updater.healthcheck.ack_health") as ack, \
                        patch("bookmarks_gui.launch", side_effect=launch), \
                        patch.object(owner, "_set_busy", side_effect=RuntimeError("PDF task guard cannot initialize")):
                    self.assertEqual(gui_entry.main(["--update-transaction", name, "--update-token", "token"]), 1)
                ack.assert_not_called()
                self.assertEqual(config.read_bytes(), original)
                self.assertIn("PDF task guard cannot initialize", (Path(name) / "health-failure.json").read_text(encoding="utf-8"))
            finally:
                owner.busy = False
                if not owner.closed:
                    owner._close()

    def test_startup_cleanup_retains_verified_transaction_during_helper_bootstrap(self):
        with tempfile.TemporaryDirectory(prefix="pdf-cleanup-bootstrap-safety-review-") as name:
            root = Path(name)
            program, base = root / "program", root / "transactions"
            program.mkdir()
            base.mkdir()
            directory = base / ("tx-" + "d" * 32)
            directory.mkdir()
            atomic_json(directory / "journal.json", {"schema": 1, "transaction": directory.name,
                        "app_id": APP_ID, "state": "verified", "operations": [],
                        "helper_pid": None, "parent_pids": [12344],
                        "target_root": str(program), "target_exe": str(program / "program.exe")})
            (directory / "updater.exe").write_bytes(b"MZ helper bootstrap")
            payload = directory / "package.exe"
            payload.write_bytes(b"verified transaction payload")
            with patch("updater.cleanup.process_alive", return_value=False), \
                    patch("updater.cleanup.processes.matching_processes", return_value=[12345]):
                result = cleanup_stale_update_transactions(APP_ID, base)
            self.assertEqual(load_json(directory / "journal.json")["state"], "verified")
            self.assertEqual(payload.read_bytes(), b"verified transaction payload")
            self.assertEqual(result[str(directory)], "pending")

    def test_external_cleanup_receipt_retains_foreign_and_unfinished_transactions(self):
        with tempfile.TemporaryDirectory(prefix="pdf-cleanup-receipt-safety-review-") as name:
            root = Path(name)
            program, base = root / "program", root / "transactions"
            program.mkdir()
            base.mkdir()
            directory = base / ("tx-" + "a" * 32)
            directory.mkdir()
            payload = directory / "package.exe"
            payload.write_bytes(b"transaction payload")
            receipt = base / ("cleanup_" + directory.name + ".json")
            for app_id, state in (("another-application", "committed"), (APP_ID, "installing"), (APP_ID, "failed")):
                with self.subTest(app_id=app_id, state=state):
                    atomic_json(receipt, {"schema": 1, "transaction": directory.name,
                                         "app_id": app_id, "state": state,
                                         "operations": [{"started": True}] if state == "failed" else [],
                                         "target_root": str(program), "target_exe": str(program / "program.exe")})
                    original = receipt.read_bytes()
                    with patch("updater.cleanup.process_alive", return_value=False), \
                            patch("updater.cleanup.processes.matching_processes", return_value=[]):
                        if app_id != APP_ID:
                            with self.assertRaises(UpdateError):
                                cleanup_transaction(directory, APP_ID)
                        else:
                            self.assertFalse(cleanup_transaction(directory, APP_ID))
                    self.assertEqual(payload.read_bytes(), b"transaction payload")
                    self.assertEqual(receipt.read_bytes(), original)

    def test_cleanup_recognizes_health_failure_but_retains_unknown_user_file(self):
        with tempfile.TemporaryDirectory(prefix="pdf-cleanup-products-safety-review-") as name:
            root = Path(name)
            program, base = root / "program", root / "transactions"
            program.mkdir()
            base.mkdir()
            directory = base / ("tx-" + "b" * 32)
            directory.mkdir()
            atomic_json(directory / "journal.json", {"schema": 1, "transaction": directory.name,
                        "app_id": APP_ID, "state": "rolled_back", "operations": [],
                        "target_root": str(program), "target_exe": str(program / "program.exe")})
            atomic_json(directory / "health-failure.json", {"message": "configuration cannot initialize"})
            unknown = directory / "用户保存的文件.pdf"
            unknown.write_bytes(b"USER DATA")
            with patch("updater.cleanup.process_alive", return_value=False), \
                    patch("updater.cleanup.processes.matching_processes", return_value=[]):
                with self.assertRaises(UpdateError):
                    cleanup_transaction(directory, APP_ID)
                self.assertEqual(unknown.read_bytes(), b"USER DATA")
                self.assertTrue((directory / "journal.json").exists())
                unknown.unlink()
                self.assertTrue(cleanup_transaction(directory, APP_ID))
            self.assertFalse(directory.exists())
            self.assertFalse((base / ("cleanup_" + directory.name + ".json")).exists())
            self.assertTrue((base / "diagnostics" / (directory.name + "_journal.json")).exists())

    def test_last_journal_unlink_then_rmdir_failure_recovers_from_durable_receipt(self):
        with tempfile.TemporaryDirectory(prefix="pdf-cleanup-last-window-safety-review-") as name:
            root = Path(name)
            program, base = root / "program", root / "transactions"
            program.mkdir()
            base.mkdir()
            directory = base / ("tx-" + "c" * 32)
            directory.mkdir()
            data = {"schema": 1, "transaction": directory.name, "app_id": APP_ID,
                    "state": "committed", "operations": [], "target_root": str(program),
                    "target_exe": str(program / "program.exe"), "to_version": "1.5.0"}
            atomic_json(directory / "journal.json", data)
            (directory / "updater.exe").write_bytes(b"released helper")
            receipt = base / ("cleanup_" + directory.name + ".json")
            remove_directory = Path.rmdir

            def deny_final_remove(path):
                if path == directory:
                    raise OSError("final directory removal temporarily blocked")
                return remove_directory(path)

            with patch("updater.cleanup.process_alive", return_value=False), \
                    patch("updater.cleanup.processes.matching_processes", return_value=[]):
                with patch.object(Path, "rmdir", autospec=True, side_effect=deny_final_remove):
                    with self.assertRaisesRegex(OSError, "temporarily blocked"):
                        cleanup_transaction(directory, APP_ID)
                self.assertTrue(directory.exists())
                self.assertFalse((directory / "journal.json").exists())
                self.assertEqual(load_json(receipt), data)
                self.assertTrue(cleanup_transaction(directory, APP_ID))
            self.assertFalse(directory.exists())
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
