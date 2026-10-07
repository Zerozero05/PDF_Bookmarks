"""Real Tk controls keep downloads separate and installation behind task guards."""

from concurrent.futures import Future
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from tkinterdnd2 import TkinterDnD

from bookmarks_gui import BookmarkWindow
import gui_entry
from updater.controller import UpdateState
from updater.checker import UpdateOffer


class UpdateGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pdf-update-ui-")
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / "profile/settings.json"
        self.root = TkinterDnD.Tk()
        self.root.withdraw()
        self.window = BookmarkWindow(self.root, settings_path=self.config)
        self.addCleanup(self.close_window)

    def close_window(self):
        self.window.busy = False
        self.window.editor = None
        if not self.window.closed:
            self.window._close()

    def test_help_controls_display_build_identity_without_starting_pdf_job(self):
        self.window._show_updates()
        dialog = self.window.updates
        self.root.update_idletasks()
        self.assertEqual(dialog.window.title(), "PDF_Bookmarks · 帮助 / 更新")
        self.assertNotEqual(dialog.controller.executor, self.window.executor)
        self.assertFalse(self.window.busy)
        self.assertEqual(str(dialog.download_button["state"]), "disabled")

    def test_install_guard_covers_write_editor_save_and_render(self):
        self.assertEqual(self.window.update_block_reason(), "")
        self.window.busy = True
        self.assertTrue(self.window.update_block_reason())
        self.window.busy = False
        self.window.pending_editor_saves.append("save")
        self.assertTrue(self.window.update_block_reason())
        self.window.pending_editor_saves.clear()
        editor = tk.Toplevel(self.root)
        self.window.editor = editor
        self.assertTrue(self.window.update_block_reason())
        editor.destroy()
        self.window.editor = None
        self.window._render_future = Future()
        self.assertTrue(self.window.update_block_reason())
        self.window._render_future.set_result(None)
        self.assertEqual(self.window.update_block_reason(), "")

    def test_busy_install_never_starts_updater_or_exits_main_window(self):
        self.window._show_updates()
        self.window.busy = True
        with patch("update_dialog.messagebox.showinfo"), patch.object(self.window.updates.controller, "install") as install:
            self.window.updates._install()
        install.assert_not_called()
        self.assertFalse(self.window.closed)

    def test_offer_progress_ready_are_applied_only_by_tk_poll(self):
        self.window._show_updates()
        dialog = self.window.updates
        offer = UpdateOffer("1.5.1", {}, {"file": "program.exe", "size": 1024},
                            "Test release notes", "https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v1.5.1")
        dialog.controller.offer = offer
        dialog.controller.events.put(("checked", {"offer": offer, "automatic": False}))
        dialog.controller.events.put(("progress", (512, 1024)))
        dialog.controller.state = UpdateState.READY
        dialog.controller.events.put(("ready", Mock()))
        self.root.after_cancel(dialog._poll_after)
        dialog._poll()
        self.assertEqual(dialog.progress.get(), 100)
        self.assertEqual(str(dialog.install_button["state"]), "normal")
        self.assertIn("Test release notes", dialog.notes.get("1.0", "end"))
        self.assertIn("1.5.1", self.window.update_button["text"])

    def test_failed_config_save_refuses_installation(self):
        self.window._show_updates()
        with patch("update_dialog.messagebox.askyesno", return_value=True), \
                patch.object(self.window, "_save_settings", side_effect=OSError("cannot save")), \
                patch.object(self.window.updates.controller, "install") as install:
            self.window.updates._install()
        install.assert_not_called()
        self.assertFalse(self.window.closed)


class GuiEntryTests(unittest.TestCase):
    def test_identity_diagnostic_never_creates_gui(self):
        with tempfile.TemporaryDirectory() as name, patch("bookmarks_gui.launch") as launch:
            output = Path(name) / "identity.json"
            gui_entry.main(["--build-info-json", str(output)])
            info = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(info["app_id"], "com.linzh.PDFBookmarks")
            self.assertEqual(info["entrypoint"], "source")
            launch.assert_not_called()

    def test_normal_arguments_and_interruption_recovery(self):
        with patch("updater.launcher.resume_pending_update", return_value=False), \
                patch("bookmarks_gui.launch") as launch:
            gui_entry.main(["D:/中文 图书/test.pdf"])
            launch.assert_called_once_with(["D:/中文 图书/test.pdf"], settings_path=None, on_ready=None)
        with patch("updater.launcher.resume_pending_update", return_value=True), \
                patch("bookmarks_gui.launch") as launch:
            gui_entry.main([])
            launch.assert_not_called()

    def test_health_config_failure_never_initializes_gui_or_acknowledges(self):
        with tempfile.TemporaryDirectory() as name:
            config = Path(name) / "settings.json"
            config.write_text("{bad-json", encoding="utf-8")
            with patch("updater.healthcheck.validate_health_start", return_value={"config_path": str(config)}), \
                    patch("updater.healthcheck.ack_health") as ack, patch("bookmarks_gui.launch") as launch:
                self.assertEqual(gui_entry.main(["--update-transaction", name, "--update-token", "token"]), 1)
                ack.assert_not_called()
                launch.assert_not_called()
                self.assertEqual(config.read_text(), "{bad-json")
                self.assertTrue((Path(name) / "health-failure.json").is_file())
