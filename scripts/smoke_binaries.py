"""Verify frozen CLI startup and onefile/portable TkDnD/OCR resources."""

from pathlib import Path
import subprocess

from PyInstaller.archive.readers import CArchiveReader


ROOT = Path(__file__).resolve().parents[1]


def verify_resources(names):
    names = [name.replace("\\", "/").lower() for name in names]
    requirements = {
        "Python runtime": lambda name: name.startswith("python3") and name.endswith(".dll"),
        "Tcl runtime": lambda name: name.endswith("tcl86t.dll") or name.endswith("tcl90.dll"),
        "Tk runtime": lambda name: name.endswith("tk86t.dll") or name.endswith("tk90.dll"),
        "Tcl scripts": lambda name: name == "_tcl_data/init.tcl",
        "Tk scripts": lambda name: name == "_tk_data/tk.tcl",
        "TkDnD runtime": lambda name: "tkinterdnd2/tkdnd/win-x64" in name and name.endswith(".dll"),
        "TkDnD scripts": lambda name: "tkinterdnd2/tkdnd/win-x64" in name and name.endswith("/pkgindex.tcl"),
        "OCR configuration": lambda name: name.startswith("rapidocr/") and name.endswith(".yaml"),
        "OCR models": lambda name: name.startswith("rapidocr/models/") and name.endswith(".onnx"),
        "ONNX Runtime": lambda name: name.endswith("onnxruntime_pybind11_state.pyd"),
        "OpenCV runtime": lambda name: name.startswith("cv2/") and name.endswith(".pyd"),
        "NumPy runtime": lambda name: name.startswith("numpy/") and "/_multiarray_umath" in name and name.endswith(".pyd"),
    }
    for label, matches in requirements.items():
        count = sum(matches(name) for name in names)
        if count < (3 if label == "OCR models" else 1):
            raise RuntimeError(f"Missing frozen {label}")
        print(f"Verified {label}: {count} resources")


def verify_portable(folder):
    executable = folder / "ZoteroPDFBookmarks.exe"
    with executable.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError(f"Not a Windows executable: {executable}")
    runtime = folder / "_internal"
    verify_resources(path.relative_to(runtime).as_posix()
                     for path in runtime.rglob("*") if path.is_file())


def main():
    subprocess.run([str(ROOT / "dist/ZoteroPDFBookmarks-CLI.exe"), "--help"],
                   check=True, timeout=60)
    bundle = CArchiveReader(str(ROOT / "dist/ZoteroPDFBookmarks.exe"))
    verify_resources(bundle.toc)
    verify_portable(ROOT / "dist/portable/ZoteroPDFBookmarks")


if __name__ == "__main__":
    main()
