"""Portable packages must retain the runtime, OCR data and license notices."""

import contextlib
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import package_release, smoke_binaries


RESOURCES = (
    "python312.dll", "tcl86t.dll", "tk86t.dll",
    "_tcl_data/init.tcl", "_tk_data/tk.tcl",
    "tkinterdnd2/tkdnd/win-x64/libtkdnd2.10.2.dll",
    "tkinterdnd2/tkdnd/win-x64/pkgIndex.tcl",
    "rapidocr/config.yaml", "rapidocr/models/det.onnx",
    "rapidocr/models/rec.onnx", "rapidocr/models/cls.onnx",
    "onnxruntime/capi/onnxruntime_pybind11_state.pyd",
    "cv2/cv2.pyd", "numpy/_core/_multiarray_umath.cp312-win_amd64.pyd",
)


class PortablePackagingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="zotero-package-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources = [
            "bookmarks_core.py", "bookmarks_gui.py", "gui_entry.py", "bookmarks.py",
            "README.md", "LICENSE.txt", "THIRD_PARTY_NOTICES.md", "VERSION",
            "requirements.txt", "requirements-build.txt", "licenses/ocr/LICENSE",
        ]
        for name in self.sources:
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("1.4.1\n" if name == "VERSION" else name, encoding="utf-8")
        self.portable = self.root / "dist/portable/ZoteroPDFBookmarks"
        for name in RESOURCES:
            file = self.portable / "_internal" / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"bundled resource")
        for executable in (
            self.root / "dist/ZoteroPDFBookmarks.exe",
            self.root / "dist/ZoteroPDFBookmarks-CLI.exe",
            self.portable / "ZoteroPDFBookmarks.exe",
        ):
            executable.write_bytes(b"MZ test binary")

    def package(self):
        tracked = ("\0".join(self.sources) + "\0").encode("utf-8")
        with patch.object(package_release, "ROOT", self.root), \
                patch.object(package_release.subprocess, "check_output", return_value=tracked), \
                patch.dict("os.environ", {"GITHUB_REF": ""}), \
                contextlib.redirect_stdout(io.StringIO()):
            package_release.main()

    def test_portable_archive_keeps_runtime_and_has_valid_checksums(self):
        self.package()
        output = self.root / "artifacts"
        archive = output / "ZoteroPDFBookmarks-Portable-v1.4.1.zip"
        with zipfile.ZipFile(archive) as package:
            self.assertIsNone(package.testzip())
            prefix = "ZoteroPDFBookmarks/"
            for name in RESOURCES:
                self.assertEqual(package.read(prefix + "_internal/" + name), b"bundled resource")
            for name in ("ZoteroPDFBookmarks.exe", "LICENSE.txt", "THIRD_PARTY_NOTICES.md", "licenses/ocr/LICENSE"):
                self.assertIn(prefix + name, package.namelist())
            readme = package.read(prefix + "README.md").decode("utf-8")
            self.assertIn("_internal", readme)
            self.assertIn("https://github.com/Zerozero05/Zotero_PDF_Bookmarks", readme)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        expected = f"{digest}  {archive.name}\n"
        self.assertEqual(archive.with_suffix(".zip.sha256").read_text(encoding="utf-8"), expected)
        sums = (output / "SHA256SUMS.txt").read_text(encoding="utf-8")
        self.assertIn(expected, sums)
        self.assertEqual(len(sums.splitlines()), 4)
        for row in sums.splitlines():
            hash_value, name = row.split("  ")
            self.assertEqual(hash_value, hashlib.sha256((output / name).read_bytes()).hexdigest())

    def test_missing_model_or_runtime_refuses_to_package(self):
        for resource in ("rapidocr/models/rec.onnx", "python312.dll",
                         "tkinterdnd2/tkdnd/win-x64/pkgIndex.tcl",
                         "onnxruntime/capi/onnxruntime_pybind11_state.pyd"):
            with self.subTest(resource=resource):
                missing = self.portable / "_internal" / resource
                payload = missing.read_bytes()
                missing.unlink()
                try:
                    with self.assertRaisesRegex(RuntimeError, "Missing frozen"):
                        self.package()
                    self.assertFalse((self.root / "artifacts").exists())
                finally:
                    missing.write_bytes(payload)

    def test_portable_executable_requires_windows_signature(self):
        (self.portable / "ZoteroPDFBookmarks.exe").write_bytes(b"not executable")
        with self.assertRaisesRegex(ValueError, "Not a Windows executable"):
            self.package()

    def test_resource_check_accepts_onefile_names(self):
        with contextlib.redirect_stdout(io.StringIO()):
            smoke_binaries.verify_resources(RESOURCES)


if __name__ == "__main__":
    unittest.main()
