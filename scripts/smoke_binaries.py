"""Verify frozen CLI startup and packaged TkDnD/OCR resources on Windows."""

from pathlib import Path
import subprocess

from PyInstaller.archive.readers import CArchiveReader


ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run([str(ROOT / "dist/ZoteroPDFBookmarks-CLI.exe"), "--help"],
                   check=True, timeout=60)
    bundle = CArchiveReader(str(ROOT / "dist/ZoteroPDFBookmarks.exe"))
    names = [name.replace("\\", "/").lower() for name in bundle.toc]
    requirements = {
        "Python runtime": lambda name: name.startswith("python3") and name.endswith(".dll"),
        "Tk runtime": lambda name: name.endswith("tk86t.dll") or name.endswith("tk90.dll"),
        "TkDnD runtime": lambda name: "tkinterdnd2/tkdnd/win-x64" in name and name.endswith(".dll"),
        "OCR configuration": lambda name: name.startswith("rapidocr/") and name.endswith(".yaml"),
        "OCR models": lambda name: name.startswith("rapidocr/models/") and name.endswith(".onnx"),
    }
    for label, matches in requirements.items():
        count = sum(matches(name) for name in names)
        if count < (3 if label == "OCR models" else 1):
            raise RuntimeError(f"Missing frozen {label}")
        print(f"Verified {label}: {count} resources")


if __name__ == "__main__":
    main()
