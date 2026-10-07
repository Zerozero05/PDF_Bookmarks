"""Package tracked source, matching Windows builds and update manifests."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_info import APP_ID, CONFIG_SCHEMA, UPDATE_CHANNEL, UPDATE_SCHEMA, BuildInfo

if __package__:
    from .build_windows import runtime_fingerprint
    from .smoke_binaries import verify_identity, verify_portable
else:
    from build_windows import runtime_fingerprint
    from smoke_binaries import verify_identity, verify_portable


def version():
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value):
        raise ValueError("VERSION must contain a stable semantic version")
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/") and ref != f"refs/tags/v{value}":
        raise ValueError("Release tag must match VERSION exactly")
    return value


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def release_notes(current):
    changelog = ROOT / "CHANGELOG.md"
    if changelog.is_file():
        section = []
        for line in changelog.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if section:
                    break
                if not re.match(rf"## \[?v?{re.escape(current)}(?:\]|\s|$)", line):
                    continue
                section.append(line)
            elif section:
                section.append(line)
        if section:
            return "\n".join(section).strip()
    return f"PDF_Bookmarks v{current}: https://github.com/Zerozero05/PDF_Bookmarks/blob/v{current}/CHANGELOG.md"


def source_files():
    # Only Git-tracked files enter the complete package; books/settings stay out.
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    sources = [Path(name) for name in tracked if name]
    required = {Path(name) for name in (
        "bookmarks_core.py", "bookmarks_gui.py", "gui_entry.py", "bookmarks.py",
        "build_info.py", "config_manager.py", "update_dialog.py", "updater_entry.py",
        "scripts/build_windows.py", "scripts/test_frozen_updates.py",
        "README.md", "LICENSE.txt", "THIRD_PARTY_NOTICES.md", "VERSION",
        "requirements.txt", "requirements-build.txt")}
    required |= {path.relative_to(ROOT) for path in [*ROOT.glob("*.py"), *(ROOT / "updater").rglob("*.py")]}
    if not required <= set(sources):
        raise ValueError("Commit/stage all project source files before packaging")
    forbidden = {".git", ".venv", "build", "dist", "artifacts", "__pycache__", "_backup"}
    for path in sources:
        if forbidden.intersection(path.parts) or path.suffix.lower() in {".exe", ".pdf", ".pyc", ".zip"}:
            raise ValueError(f"Unexpected tracked generated/private file: {path}")
        if path.suffix.lower() == ".json" and not (
                path.parts[0] == "examples" or path.parts[:3] == ("tests", "fixtures", "config")):
            raise ValueError(f"Only examples/ and tests/fixtures/config/ may contain tracked JSON: {path}")
        if (ROOT / path).is_symlink() or not (ROOT / path).is_file():
            raise ValueError(f"Source file is missing or not regular: {path}")
    return sources


def verify_build_provenance(current):
    fingerprint = runtime_fingerprint()
    for kind in ("helper", "single", "portable", "cli"):
        report = json.loads((ROOT / "build/build-state" / f"{kind}.json").read_text(encoding="utf-8"))
        if report.get("version") != current or report.get("runtime_sources") != fingerprint:
            raise ValueError(f"{kind} was built from different sources/version; rebuild before publishing")


def portable_manifest(folder, current):
    from updater.manifest import validate_package_manifest

    if (folder / ".pdf_bookmarks").exists():
        raise ValueError("Portable build must not contain installed state or user data")
    records = []
    for file in sorted(folder.rglob("*")):
        if file.is_symlink():
            raise ValueError(f"Portable package cannot contain symbolic links: {file}")
        if file.is_file() and file.relative_to(folder).as_posix() != "package-manifest.json":
            records.append({"path": file.relative_to(folder).as_posix(),
                            "size": file.stat().st_size, "sha256": sha256(file)})
    manifest = {
        "schema": UPDATE_SCHEMA, "app_id": APP_ID, "version": current,
        "variant": "portable", "entrypoint": "PDF_Bookmarks.exe",
        "config_schema": CONFIG_SCHEMA, "managed_files": records,
        # A manifest cannot recursively include the hash of its own content.
        "manifest_excludes": ["package-manifest.json"],
    }
    validate_package_manifest(manifest, BuildInfo(APP_ID, current, "portable"), current)
    (folder / "package-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    from updater.manifest import validate_release_manifest

    current = version()
    sources = source_files()
    verify_build_provenance(current)
    gui = ROOT / "dist/PDF_Bookmarks.exe"
    cli = ROOT / "dist/PDF_Bookmarks_CLI.exe"
    portable = ROOT / "dist/portable/PDF_Bookmarks"
    for executable in (gui, cli, portable / "_internal/updater.exe"):
        with executable.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise ValueError(f"Not a Windows executable: {executable}")
    verify_portable(portable)
    verify_identity(gui, "single", "gui")
    verify_identity(cli, "single", "cli")
    verify_identity(portable / "PDF_Bookmarks.exe", "portable", "gui")
    verify_identity(portable / "_internal/updater.exe", "single", "updater")
    for source in sources:
        if source.name in {"LICENSE.txt", "THIRD_PARTY_NOTICES.md", "VERSION"} or source.parts[0] == "licenses":
            target = portable / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, target)
    (portable / "README.md").write_text(f"""# PDF_Bookmarks v{current} — Portable

解压整个 PDF_Bookmarks 文件夹，双击 PDF_Bookmarks.exe。
必须保留 _internal 和全部运行文件，不能只复制主 EXE。
Windows 10/11 x64，无需安装 Python，包含本地 OCR 模型和运行库。

支持普通 PDF，并适配 Zotero 附件。Single 与 Portable 功能相同；
Portable 省去每次启动的临时解包。两者继续共用
%LOCALAPPDATA%\\ZoteroPDFBookmarks\\settings.json，更新保留原设置。

程序或文件夹可改名、移动；更新保留当前入口名及 Portable 根目录。
package-manifest.json 是程序文件清单，请保留；首次准备更新时将生成
.pdf_bookmarks/installed-manifest.json，用于仅更新程序文件并保护未知文件。
v1.4.1 没有自动更新，首次使用此版本须手动下载。

完整说明：https://github.com/Zerozero05/PDF_Bookmarks
源码版本：https://github.com/Zerozero05/PDF_Bookmarks/releases/tag/v{current}
AGPL v3：LICENSE.txt；第三方许可：THIRD_PARTY_NOTICES.md 和 licenses/。
""", encoding="utf-8")
    portable_manifest(portable, current)
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    prefix = f"PDF_Bookmarks_v{current}_win_x64"
    names = [f"{prefix}.exe", f"{prefix}_cli.exe", f"{prefix}_full.zip",
             f"{prefix}_portable.zip", "SHA256SUMS.txt", f"{prefix}_portable.zip.sha256",
             "update-manifest.json"]
    unexpected = {file.name for file in output.iterdir()} - set(names)
    if unexpected:
        raise ValueError(f"Artifacts directory contains files from another build: {sorted(unexpected)}")
    standalone = []
    for executable, name in zip((gui, cli), names[:2]):
        destination = output / name
        shutil.copyfile(executable, destination)
        standalone.append(destination)
    archive = output / names[2]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for source in sorted(sources):
            package.write(ROOT / source, Path("PDF_Bookmarks") / source)
        for executable in (gui, cli):
            package.write(executable, Path("PDF_Bookmarks/dist") / executable.name)
    portable_archive = output / names[3]
    with zipfile.ZipFile(portable_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for file in sorted(portable.rglob("*")):
            if file.is_file():
                package.write(file, Path("PDF_Bookmarks") / file.relative_to(portable))
    for asset in (archive, portable_archive):
        with zipfile.ZipFile(asset) as package:
            if package.testzip():
                raise ValueError(f"ZIP integrity check failed: {asset.name}")
    release_manifest = {
        "schema": UPDATE_SCHEMA, "app_id": APP_ID, "version": current,
        "minimum_updater_schema": UPDATE_SCHEMA, "config_schema": CONFIG_SCHEMA,
        "channel": UPDATE_CHANNEL,
        "release_notes": release_notes(current),
        "assets": {variant: {"file": asset.name, "sha256": sha256(asset), "size": asset.stat().st_size}
                   for variant, asset in (("single", standalone[0]), ("portable", portable_archive))},
    }
    for variant in ("single", "portable"):
        validate_release_manifest(release_manifest, BuildInfo(APP_ID, "0.0.0", variant))
    manifest_path = output / "update-manifest.json"
    manifest_path.write_text(json.dumps(release_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assets = [*standalone, archive, portable_archive, manifest_path]
    checksums = output / "SHA256SUMS.txt"
    checksums.write_text("".join(f"{sha256(asset)}  {asset.name}\n" for asset in assets), encoding="utf-8")
    portable_checksum = portable_archive.with_suffix(".zip.sha256")
    portable_checksum.write_text(f"{sha256(portable_archive)}  {portable_archive.name}\n", encoding="utf-8")
    for asset in [*assets, checksums, portable_checksum]:
        print(f"{asset.name}: {asset.stat().st_size} bytes")


if __name__ == "__main__":
    main()
