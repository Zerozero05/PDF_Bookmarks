"""Windows icon inheritance must not retain a new native family per dialog."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


def _native_probe(mode):
    import ctypes
    from ctypes import wintypes
    import gc
    import tkinter as tk
    import weakref

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ui_theme import apply_app_icon

    gui_resources = ctypes.windll.user32.GetGuiResources
    gui_resources.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    gui_resources.restype = wintypes.DWORD
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = wintypes.HANDLE
    process = get_process()
    class_icon = ctypes.windll.user32.GetClassLongPtrW
    class_icon.argtypes = (wintypes.HWND, ctypes.c_int)
    class_icon.restype = ctypes.c_void_p

    def resources():
        return (gui_resources(process, 0), gui_resources(process, 1))

    def icons(window):
        window.update_idletasks()
        frame = int(window.frame(), 0)
        # WM_GETICON is empty when a window inherits the TkTopLevel class icon.
        return (class_icon(frame, -14), class_icon(frame, -34))

    def new_root():
        window = tk.Tk()
        window.withdraw()
        return window

    def collect_closed(window):
        reference = weakref.ref(window)
        window.destroy()
        return reference

    root = new_root()
    builtin = icons(root)
    if mode == "child_first":
        child = tk.Toplevel(root)
        child.withdraw()
        assert apply_app_icon(child)
        expected = icons(child)
        assert icons(root) == expected
        child.destroy()
        child = None
    else:
        assert apply_app_icon(root)
        expected = icons(root)
    assert all(expected), expected
    assert builtin != expected, (builtin, expected)

    if mode == "same_root":
        # Warm the native child class before counting the repeated operation.
        child = tk.Toplevel(root)
        child.withdraw()
        assert apply_app_icon(child)
        assert icons(child) == expected
        child.destroy()
        child = None
        gc.collect()
        baseline = resources()
        observed = [baseline]
        for _ in range(100):
            assert apply_app_icon(root)
            assert icons(root) == expected
            child = tk.Toplevel(root)
            child.withdraw()
            assert apply_app_icon(child)
            assert icons(child) == expected
            child.destroy()
            child = None
            gc.collect()
            observed.append(resources())
        final = resources()
        reference = collect_closed(root)
        root = None
        gc.collect()
        assert reference() is None
    else:
        reference = collect_closed(root)
        root = None
        gc.collect()
        assert reference() is None
        baseline = resources()
        observed = [baseline]
        for _ in range(100):
            root = new_root()
            assert apply_app_icon(root)
            assert icons(root) == expected
            child = tk.Toplevel(root)
            child.withdraw()
            assert apply_app_icon(child)
            assert icons(child) == expected
            child.destroy()
            child = None
            reference = collect_closed(root)
            root = None
            gc.collect()
            assert reference() is None
            observed.append(resources())
        final = resources()
    return {
        "mode": mode, "cycles": 100, "builtin_icons": builtin,
        "inherited_icons": expected, "baseline": baseline, "final": final,
        "peak": [max(item[index] for item in observed) for index in range(2)],
    }


@unittest.skipUnless(os.name == "nt", "Windows native icon resource contract")
class IconResourceTests(unittest.TestCase):
    def probe(self, mode):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--icon-probe", mode],
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["cycles"], 100)
        self.assertTrue(all(data["inherited_icons"]))
        self.assertNotEqual(data["builtin_icons"], data["inherited_icons"])
        # This allows a few lazily allocated platform handles, not the old
        # 27 GDI / 9 USER resources retained by every ICO family load.
        for index, name in enumerate(("GDI", "USER")):
            self.assertLessEqual(data["peak"][index] - data["baseline"][index], 4,
                                 f"{name} resources accumulated: {data}")
            self.assertLessEqual(data["final"][index] - data["baseline"][index], 4,
                                 f"{name} resources remained: {data}")

    def test_repeated_root_and_child_icon_requests_reuse_native_family(self):
        self.probe("same_root")

    def test_new_interpreters_and_children_inherit_the_original_native_icons(self):
        self.probe("recreate")

    def test_first_icon_request_from_a_child_also_sets_the_shared_default(self):
        self.probe("child_first")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--icon-probe":
        print(json.dumps(_native_probe(sys.argv[2])))
    else:
        unittest.main()
