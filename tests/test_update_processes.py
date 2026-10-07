"""Multi-instance checks and Windows exclusive-open checks use real OS APIs."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from updater import UpdateError
from updater import processes


class ProcessTests(unittest.TestCase):
    def test_current_process_is_found(self):
        self.assertTrue(processes.process_alive(os.getpid()))
        # A Windows venv uses a redirector EXE: its child image is the base
        # interpreter; frozen application images do not use that redirector.
        image = processes.process_image(os.getpid())
        self.assertIsNotNone(image)
        self.assertIn(os.getpid(), processes.matching_processes(image))
        self.assertFalse(processes.process_alive(-1))

    def test_main_or_other_instance_prevents_install(self):
        with patch.object(processes, "matching_processes", return_value=[os.getpid() + 100000]), \
                self.assertRaisesRegex(UpdateError, "其他实例"):
            processes.wait_for_release(sys.executable, timeout=0)
        with patch.object(processes, "matching_processes", return_value=[]), \
                patch.object(processes, "process_alive", return_value=True), \
                self.assertRaises(UpdateError):
            processes.wait_for_release(sys.executable, [os.getpid() + 100000], timeout=0)

    def test_released_program_returns(self):
        with patch.object(processes, "matching_processes", return_value=[]):
            processes.wait_for_release("not-running.exe", timeout=0)

    def test_installation_lock_is_exclusive(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with processes.installation_lock(directory / "program.exe", directory):
                with self.assertRaises(UpdateError):
                    with processes.installation_lock(directory / "program.exe", directory):
                        self.fail("Two updaters acquired the same installation")
            with processes.installation_lock(directory / "program.exe", directory):
                pass

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_locked_file_rejected_before_replace(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "locked.dll"
            path.write_bytes(b"runtime")
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                          ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            kernel.CreateFileW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            try:
                with self.assertRaises(UpdateError):
                    processes.check_file_unlocked(path)
            finally:
                kernel.CloseHandle(handle)
            processes.check_file_unlocked(path)


if __name__ == "__main__":
    unittest.main()
