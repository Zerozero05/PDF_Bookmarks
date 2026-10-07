"""Build Windows binaries with explicit, embedded Single/Portable identities."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import sysconfig


ROOT = Path(__file__).resolve().parents[1]


def runtime_fingerprint():
    paths = [ROOT / "VERSION", *ROOT.glob("*.py"), *(ROOT / "updater").rglob("*.py")]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def version():
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value):
        raise ValueError("VERSION must contain a stable semantic version")
    return value


def build(kind, test_version=None):
    if sys.platform != "win32":
        raise RuntimeError("Release binaries must be built on Windows")
    if sys.maxsize < 2**32 or sysconfig.get_platform() != "win-amd64":
        raise RuntimeError("Windows x64 release assets require a 64-bit Python interpreter")
    current = version()
    if test_version is not None:
        if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", test_version):
            raise ValueError("Test version must contain a stable semantic version")
        if test_version == current:
            raise ValueError("Use the normal build for the current production version")
        current = test_version
    # Synthetic successor builds go into a separate tree and cannot overwrite
    # production binaries or enter scripts/package_release.py's release assets.
    suffix = f"/test_v{current}" if test_version is not None else ""
    dist_root = f"dist{suffix}"
    build_root = f"build{suffix}"
    variant = "portable" if kind == "portable" else "single"
    identity_dir = ROOT / build_root / "identities" / kind
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "_build_identity.py").write_text(
        f"APP_VERSION = {current!r}\nBUILD_VARIANT = {variant!r}\n"
        f"BUILD_ENTRYPOINT = {('gui' if kind in {'single', 'portable'} else 'updater' if kind == 'helper' else 'cli')!r}\n",
        encoding="utf-8")
    entry, name, window_mode, bundle, distribution = {
        "helper": ("updater_entry.py", "updater", "--console", "--onefile", f"{dist_root}/updater"),
        "single": ("gui_entry.py", "PDF_Bookmarks", "--windowed", "--onefile", dist_root),
        "portable": ("gui_entry.py", "PDF_Bookmarks", "--windowed", "--onedir", f"{dist_root}/portable"),
        "cli": ("bookmarks.py", "PDF_Bookmarks_CLI", "--console", "--onefile", dist_root),
    }[kind]
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", bundle,
        window_mode, "--additional-hooks-dir=.", "--name", name,
        "--distpath", distribution, "--workpath", f"{build_root}/{kind}",
        "--specpath", str(identity_dir), "--paths", str(identity_dir),
        "--hidden-import", "_build_identity", "--hidden-import", "build_info",
    ]
    if kind == "portable":
        command += ["--contents-directory", "_internal"]
    if kind in {"single", "portable"}:
        helper = ROOT / dist_root / "updater/updater.exe"
        if not helper.is_file():
            raise ValueError("Build the external updater before building GUI binaries")
        command += ["--add-data", f"{helper};."]
    if kind == "helper":
        # The helper owns filesystem/network/transaction work; it must not
        # collect the GUI, OCR models, or PDF dependencies as a second bundle.
        command += ["--exclude-module", "tkinter", "--exclude-module", "fitz",
                    "--exclude-module", "pymupdf", "--exclude-module", "rapidocr",
                    "--exclude-module", "numpy", "--exclude-module", "cv2"]
    command.append(entry)
    fingerprint = runtime_fingerprint()
    subprocess.run(command, cwd=ROOT, check=True)
    if runtime_fingerprint() != fingerprint:
        raise RuntimeError("Application sources changed during this build; rebuild before packaging")
    report = ROOT / build_root / "build-state" / f"{kind}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"version": current, "variant": variant,
                                 "runtime_sources": fingerprint}, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=("helper", "single", "portable", "cli"), action="append")
    parser.add_argument("--test-version", help="Synthetic integration successor; isolated under dist/test_vVERSION")
    args = parser.parse_args()
    for kind in (args.only or ["helper", "single", "cli", "portable"]):
        build(kind, args.test_version)


if __name__ == "__main__":
    main()
