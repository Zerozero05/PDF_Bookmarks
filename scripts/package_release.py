"""Package tracked source, Windows binaries and their SHA-256 checksums."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def version():
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("VERSION must contain a stable version such as 1.4.1")
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/") and ref != f"refs/tags/v{value}":
        raise ValueError("Release tag must match VERSION exactly")
    return value


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    current = version()
    # Only Git-tracked files enter the package; local books/settings stay outside it.
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    sources = [Path(name) for name in tracked if name]
    required = {Path(name) for name in (
        "bookmarks_core.py", "bookmarks_gui.py", "gui_entry.py", "bookmarks.py",
        "README.md", "LICENSE.txt", "THIRD_PARTY_NOTICES.md", "VERSION",
        "requirements.txt", "requirements-build.txt")}
    if not required <= set(sources):
        raise ValueError("Commit/stage all project source files before packaging")
    forbidden = {".git", ".venv", "build", "dist", "artifacts", "__pycache__", "_backup"}
    for path in sources:
        if forbidden.intersection(path.parts) or path.suffix.lower() in {".exe", ".pdf", ".pyc", ".zip"}:
            raise ValueError(f"Unexpected tracked generated/private file: {path}")
        if path.suffix.lower() == ".json" and path.parts[0] != "examples":
            raise ValueError(f"Only examples/ may contain tracked JSON: {path}")
        if (ROOT / path).is_symlink() or not (ROOT / path).is_file():
            raise ValueError(f"Source file is missing or not regular: {path}")

    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    gui = ROOT / "dist/ZoteroPDFBookmarks.exe"
    cli = ROOT / "dist/ZoteroPDFBookmarks-CLI.exe"
    for executable in (gui, cli):
        with executable.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise ValueError(f"Not a Windows executable: {executable}")
    standalone = []
    for executable in (gui, cli):
        destination = output / f"{executable.stem}-v{current}.exe"
        shutil.copyfile(executable, destination)
        standalone.append(destination)

    archive = output / f"ZoteroPDFBookmarks-Windows-x64-v{current}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for source in sorted(sources):
            package.write(ROOT / source, Path("ZoteroPDFBookmarks") / source)
        for executable in (gui, cli):
            package.write(executable, Path("ZoteroPDFBookmarks/dist") / executable.name)
    with zipfile.ZipFile(archive) as package:
        bad = package.testzip()
        if bad:
            raise ValueError(f"ZIP integrity check failed: {bad}")

    checksums = output / "SHA256SUMS.txt"
    checksums.write_text("".join(
        f"{sha256(asset)}  {asset.name}\n" for asset in [*standalone, archive]), encoding="utf-8")
    for asset in [*standalone, archive, checksums]:
        print(f"{asset.name}: {asset.stat().st_size} bytes")


if __name__ == "__main__":
    main()
