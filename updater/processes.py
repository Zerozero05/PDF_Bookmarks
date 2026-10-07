"""Windows process and file-release checks without an extra dependency."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import subprocess
import time

from . import UpdateError
from .manifest import assert_safe_path


def process_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            return kernel.WaitForSingleObject(handle, 0) == 0x102
        finally:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def process_image(pid):
    if os.name != "nt":
        try:
            return (Path("/proc") / str(pid) / "exe").resolve(strict=True)
        except OSError:
            return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            return Path(buffer.value)
        return None
    finally:
        kernel.CloseHandle(handle)


def matching_processes(executable):
    """Include both PyInstaller bootstrap and application processes."""
    wanted = os.path.normcase(os.path.abspath(executable))
    if os.name != "nt":
        matches = []
        proc = Path("/proc")
        if proc.exists():
            for item in proc.iterdir():
                if item.name.isdigit():
                    try:
                        if os.path.normcase(str((item / "exe").resolve())) == wanted:
                            matches.append(int(item.name))
                    except OSError:
                        continue
        return matches
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise UpdateError("不能检查仍在运行的其他实例。")
    matches = []
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            handle = kernel.OpenProcess(0x1000, False, entry.th32ProcessID)
            if handle:
                try:
                    buffer = ctypes.create_unicode_buffer(32768)
                    length = wintypes.DWORD(len(buffer))
                    if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                        if os.path.normcase(os.path.abspath(buffer.value)) == wanted:
                            matches.append(entry.th32ProcessID)
                finally:
                    kernel.CloseHandle(handle)
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return matches


def wait_for_release(executable, parent_pids=(), timeout=60):
    deadline = time.monotonic() + timeout
    while True:
        running = set(matching_processes(executable)) | {pid for pid in parent_pids if process_alive(pid)}
        running.discard(os.getpid())
        if not running:
            return
        if time.monotonic() >= deadline:
            raise UpdateError("程序或其他实例仍在运行，请关闭所有窗口后重试。")
        time.sleep(0.2)


def check_file_unlocked(path):
    path = assert_safe_path(path)
    if not path.exists():
        return
    if os.name != "nt":
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000 | 0x40000000, 0, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise UpdateError(f"文件被锁定或不可写，请关闭占用程序：{path.name}")
    kernel.CloseHandle(handle)


def terminate_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


@contextmanager
def installation_lock(executable, update_root):
    """One updater per installation, with an OS-owned lock released on crash."""
    directory = assert_safe_path(Path(update_root) / "locks")
    directory.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(os.path.normcase(os.path.abspath(executable)).encode("utf-8")).hexdigest()
    path = assert_safe_path(directory / (name + ".lock"))
    handle = None
    stream = None
    acquired = False
    try:
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                          wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            kernel.CreateFileW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.CreateFileW(str(path), 0x80000000 | 0x40000000, 0, None, 4, 0x80 | 0x4000000, None)
            if handle == ctypes.c_void_p(-1).value:
                handle = None
                raise UpdateError("此安装目录已有更新事务正在运行。")
        else:
            import fcntl
            stream = path.open("a+b")
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise UpdateError("此安装目录已有更新事务正在运行。") from exc
        acquired = True
        yield
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)
        if stream is not None:
            stream.close()
        if acquired:
            try:
                path.unlink(missing_ok=True)
                directory.rmdir()
            except OSError:
                pass
