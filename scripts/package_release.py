"""Package tracked source, Windows binaries and their SHA-256 checksums."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

if __package__:
    from .smoke_binaries import verify_portable
else:
    from smoke_binaries import verify_portable


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

    gui = ROOT / "dist/ZoteroPDFBookmarks.exe"
    cli = ROOT / "dist/ZoteroPDFBookmarks-CLI.exe"
    for executable in (gui, cli):
        with executable.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise ValueError(f"Not a Windows executable: {executable}")
    portable = ROOT / "dist/portable/ZoteroPDFBookmarks"
    verify_portable(portable)
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
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
    portable_archive = output / f"ZoteroPDFBookmarks-Portable-v{current}.zip"
    with zipfile.ZipFile(portable_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for file in sorted(portable.rglob("*")):
            if file.is_file():
                package.write(file, Path("ZoteroPDFBookmarks") / file.relative_to(portable))
        for source in sources:
            if source.name in {"LICENSE.txt", "THIRD_PARTY_NOTICES.md", "VERSION"} or source.parts[0] == "licenses":
                package.write(ROOT / source, Path("ZoteroPDFBookmarks") / source)
        package.writestr("ZoteroPDFBookmarks/README.md", f"""# Zotero PDF 书签目录工具 v{current} — 便携文件夹版

解压整个 ZoteroPDFBookmarks 文件夹，双击 ZoteroPDFBookmarks.exe。
必须保留 _internal 及其中全部文件；不能只复制 EXE。
面向 Windows 10/11 x64，无需安装 Python，包含本地 OCR 模型和运行库。

功能与同版本单文件 EXE 相同。文件夹版省去每次启动的临时解包，
不保证每页 OCR 都更快。单文件版携带更方便，启动时需临时解包。
两种方式共用 %LOCALAPPDATA%\\ZoteroPDFBookmarks\\settings.json；
此处“便携”表示解压即可运行，设置仍保存在上述用户目录。

完整说明与对应源码：https://github.com/Zerozero05/Zotero_PDF_Bookmarks
同版本原始源码与完整 Windows 包：https://github.com/Zerozero05/Zotero_PDF_Bookmarks/releases/tag/v{current}

本项目使用 AGPL v3，见 LICENSE.txt。第三方来源与许可见
THIRD_PARTY_NOTICES.md 和 licenses/。
""")
    for asset in (archive, portable_archive):
        with zipfile.ZipFile(asset) as package:
            bad = package.testzip()
            if bad:
                raise ValueError(f"ZIP integrity check failed: {bad}")

    checksums = output / "SHA256SUMS.txt"
    checksums.write_text("".join(
        f"{sha256(asset)}  {asset.name}\n" for asset in [*standalone, archive, portable_archive]), encoding="utf-8")
    portable_checksum = portable_archive.with_suffix(".zip.sha256")
    portable_checksum.write_text(
        f"{sha256(portable_archive)}  {portable_archive.name}\n", encoding="utf-8")
    for asset in [*standalone, archive, portable_archive, checksums, portable_checksum]:
        print(f"{asset.name}: {asset.stat().st_size} bytes")


if __name__ == "__main__":
    main()
