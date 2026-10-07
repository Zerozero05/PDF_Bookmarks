"""Exercise production Windows EXEs with a separately frozen successor.

No test-only health receipt is accepted: the successor must initialize its real
configuration, TkDnD GUI and PDF core through gui_entry.py. All installs and
settings are copies in an isolated temporary profile. No release is published.
"""

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_info import APP_ID, BuildInfo
from config_manager import read_config
from updater import journal, processes, transaction
from updater.manifest import load_json, sha256_file
from scripts.package_release import portable_manifest


def wait_until(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.05)
    raise TimeoutError("Frozen integration condition did not become true")


@contextmanager
def isolated_environment(folder):
    changes = {"LOCALAPPDATA": str(folder / "profile"),
               "TEMP": str(folder / "runtime_temp"), "TMP": str(folder / "runtime_temp")}
    Path(changes["TEMP"]).mkdir(parents=True)
    before = {key: os.environ.get(key) for key in changes}
    old_tempdir = tempfile.tempdir
    os.environ.update(changes)
    tempfile.tempdir = None
    try:
        yield dict(os.environ)
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        tempfile.tempdir = old_tempdir


def app_windows(executable):
    pids = set(processes.matching_processes(executable))
    user = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    windows = []

    @callback_type
    def collect(handle, _):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if pid.value in pids:
            title = ctypes.create_unicode_buffer(512)
            user.GetWindowTextW(handle, title, len(title))
            if "Zotero PDF" in title.value:
                windows.append((handle, pid.value))
        return True

    user.EnumWindows(collect, 0)
    return windows


def close_app(executable):
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    for handle, _ in app_windows(executable):
        user.PostMessageW(handle, 0x0010, 0, 0)  # WM_CLOSE invokes the normal save/close path.
    wait_until(lambda: not processes.matching_processes(executable), timeout=25)


def kill_owned_app(executable):
    # Used only after rollback is complete, when a deliberately corrupt config
    # would show a save warning during normal closing. The EXE is our temp copy.
    for pid in processes.matching_processes(executable):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    wait_until(lambda: not processes.matching_processes(executable), timeout=25)


def launch(executable, env):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return subprocess.Popen([str(executable)], cwd=executable.parent, env=env,
                            startupinfo=startup, close_fds=True)


def identity(executable, env, output):
    subprocess.run([str(executable), "--build-info-json", str(output)], cwd=executable.parent,
                   env=env, check=True, timeout=60)
    return load_json(output)


def successor_version(current):
    major, minor, patch = map(int, current.split("."))
    return f"{major}.{minor}.{patch + 1}"


def build_successor(current):
    target = ROOT / "dist" / ("test_v" + current)
    expected = (target / "PDF_Bookmarks.exe", target / "portable/PDF_Bookmarks/PDF_Bookmarks.exe",
                target / "updater/updater.exe")
    if not all(path.is_file() for path in expected):
        subprocess.run([sys.executable, str(ROOT / "scripts/build_windows.py"), "--test-version", current,
                        "--only", "helper", "--only", "single", "--only", "portable"], cwd=ROOT, check=True)
    portable = target / "portable/PDF_Bookmarks"
    production = ROOT / "dist/portable/PDF_Bookmarks"
    for name in ("LICENSE.txt", "THIRD_PARTY_NOTICES.md", "README.md"):
        shutil.copy2(production / name, portable / name)
    if (production / "licenses").is_dir():
        shutil.copytree(production / "licenses", portable / "licenses", dirs_exist_ok=True)
    (portable / "VERSION").write_text(current + "\n", encoding="utf-8")
    portable_manifest(portable, current)
    return target


def portable_package(folder, destination):
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, "PDF_Bookmarks/" + path.relative_to(folder).as_posix())
    return destination


def verify_frozen_pdf_cli(folder):
    import pymupdf
    pdf, toc = folder / "临时 原文件.pdf", folder / "临时 原文件.toc.json"
    with pymupdf.open() as document:
        document.new_page()
        document.new_page()
        document.save(pdf)
    original = pdf.read_bytes()
    toc.write_text(json.dumps({"version": 1, "bookmarks": [{"title": "第二页书签", "pdf_page": 2}]},
                              ensure_ascii=False), encoding="utf-8")
    executable = ROOT / "dist/PDF_Bookmarks_CLI.exe"

    def run(mode):
        result = subprocess.run([str(executable), mode, str(pdf), "--toc", str(toc), "--json"],
                                cwd=folder, capture_output=True, text=True, encoding="utf-8", check=True, timeout=60)
        return json.loads(result.stdout)

    if run("preview")["errors"] or pdf.read_bytes() != original:
        raise AssertionError("Frozen preview changed the PDF or failed")
    result = run("write")
    if result["errors"] or result["results"][0]["status"] != "written":
        raise AssertionError("Frozen in-place PDF write failed")
    backup = Path(result["results"][0]["backup"])
    if backup.read_bytes() != original:
        raise AssertionError("Frozen default backup did not preserve the original PDF")
    with pymupdf.open(pdf) as document:
        if document.get_toc() != [[1, "第二页书签", 2]]:
            raise AssertionError("Frozen PDF outline differs from the requested bookmark")
    written = pdf.read_bytes()
    skipped = run("write")
    if skipped["results"][0]["status"] != "skipped" or pdf.read_bytes() != written:
        raise AssertionError("Frozen default existing-bookmark policy changed")
    print("PASS real frozen CLI: preview, in-place write, original backup, default skip", flush=True)
    return {"preview_readonly": True, "in_place_write": True, "default_backup_original_bytes": True,
            "existing_bookmarks_default_skip": True}


def run_case(base, variant, fail_health, current, newer, successor):
    case = base / (variant + ("_rollback" if fail_health else "_success"))
    case.mkdir()
    original = case / "PDF_Bookmarks"
    if variant == "single":
        original.mkdir()
        shutil.copy2(ROOT / "dist/PDF_Bookmarks.exe", original / "PDF_Bookmarks.exe")
    else:
        shutil.copytree(ROOT / "dist/portable/PDF_Bookmarks", original)
        (original / "_internal/update_acceptance_obsolete.dll").write_bytes(b"MZ obsolete managed fixture")
        (original / "update_acceptance_resource.txt").write_text("old managed resource", encoding="utf-8")
        portable_manifest(original, current)
    install = case / "已移动 中文 工具"
    original.rename(install)
    executable = install / "我的 PDF 书签.exe"
    (install / "PDF_Bookmarks.exe").rename(executable)
    extras = {"额外 PDF.pdf": b"%PDF-1.4\nUser file; never updated",
              "自己的笔记.txt": "用户内容".encode(), "UserData/Presets/custom.json": b'{"keep":true}',
              "自定义文件夹/history.txt": b"user history"}
    for name, payload in extras.items():
        target = install / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    before_hash = sha256_file(executable)
    helper_process = None
    old_process = None
    tx = None
    report = {"variant": variant, "scenario": "health_failure_rollback" if fail_health else "successful_update",
              "install_path": str(executable), "cross_drive_from_build": executable.drive != ROOT.drive}
    with isolated_environment(case) as env:
        config = Path(env["LOCALAPPDATA"]) / "ZoteroPDFBookmarks/settings.json"
        config.parent.mkdir(parents=True)
        customized = {"schema": 1, "backup": False, "backup_dir": "D:/自定义 备份", "recursive": True,
                      "existing": "replace", "auto_check_update": False, "topmost": False,
                      "editor_topmost": True, "toc_save_mode": "source", "last_dir": "C:/中文 图书",
                      "future_field": {"keep": 123}, "geometry": "1100x860"}
        config.write_text(json.dumps(customized, ensure_ascii=False), encoding="utf-8")
        actual_old = identity(executable, env, case / "old-identity.json")
        if actual_old["version"] != current or actual_old["variant"] != variant or actual_old["entrypoint"] != "gui":
            raise AssertionError(f"Wrong real old build identity: {actual_old}")
        report["old_identity"] = actual_old
        if variant == "single":
            package = successor / "PDF_Bookmarks.exe"
        else:
            future = case / "future_portable"
            shutil.copytree(successor / "portable/PDF_Bookmarks", future)
            (future / "_internal/update_acceptance_added.dll").write_bytes(b"MZ new managed fixture")
            (future / "update_acceptance_resource.txt").write_text("new managed resource", encoding="utf-8")
            portable_manifest(future, newer)
            package = portable_package(future, case / "successor.zip")
        manifest = {"schema": 1, "app_id": APP_ID, "version": newer, "channel": "stable",
                    "assets": {variant: {"file": "successor.exe" if variant == "single" else "successor.zip",
                                         "variant": variant, "sha256": sha256_file(package), "size": package.stat().st_size}}}
        try:
            if not fail_health:
                old_process = launch(executable, env)
                wait_until(lambda: app_windows(executable))
            else:
                # Old GUI tolerates this file; the NEW health path must reject
                # it, exit, and restore the exact snapshot with the old EXE.
                config.write_bytes(b'{"schema":1,"backup":false, BROKEN JSON')
            tx = transaction.prepare_transaction(package, manifest, BuildInfo(APP_ID, current, variant),
                                                 executable, config)
            data = load_json(tx.directory / "journal.json")
            # The source test prepares a copied install, and is not its main
            # GUI process. Only actual frozen app PIDs should delay the helper.
            data["parent_pids"] = processes.matching_processes(executable)
            journal.save(tx.directory, data)
            shutil.copy2(ROOT / "dist/updater/updater.exe", tx.directory / "updater.exe")
            helper_process = subprocess.Popen([str(tx.directory / "updater.exe"), "--transaction", str(tx.directory)],
                                              env=env, cwd=tx.directory, creationflags=subprocess.CREATE_NO_WINDOW)
            if old_process is not None:
                # The live main process must be gone before any replacement.
                time.sleep(0.4)
                if sha256_file(executable) != before_hash:
                    raise AssertionError("Helper replaced the still-running old GUI")
                close_app(executable)
            pre_update_config = config.read_bytes()
            receipt = None
            deadline = time.monotonic() + 600
            while helper_process.poll() is None and time.monotonic() < deadline:
                if (tx.directory / "health.json").is_file():
                    receipt = load_json(tx.directory / "health.json")
                time.sleep(0.05)
            code = helper_process.wait(timeout=5)
            if fail_health:
                if code != 1 or sha256_file(executable) != before_hash or config.read_bytes() != pre_update_config:
                    raise AssertionError("Real health failure did not restore program AND configuration")
                if variant == "portable":
                    installed = load_json(install / transaction.INSTALLED)
                    if installed["version"] != current:
                        raise AssertionError("Portable rollback did not restore installed manifest")
                    for record in installed["managed_files"]:
                        if sha256_file(install / record["path"]) != record["sha256"]:
                            raise AssertionError(f"Portable rollback lost old managed file: {record['path']}")
                if receipt is not None:
                    raise AssertionError("Corrupt configuration produced a successful health receipt")
                diagnostics = list(tx.directory.parent.glob("diagnostics/*_journal.json"))
                report["rollback_diagnostics"] = [load_json(path) for path in diagnostics]
            else:
                if code != 0 or sha256_file(executable) != sha256_file(
                        successor / ("PDF_Bookmarks.exe" if variant == "single" else "portable/PDF_Bookmarks/PDF_Bookmarks.exe")):
                    raise AssertionError("Real helper did not commit the successor")
                if not receipt or not all(receipt[key] for key in ("config_ready", "gui_ready", "core_ready")):
                    raise AssertionError("No real three-component health receipt observed")
                report["health_receipt"] = receipt
                updated = read_config(config)
                for key, value in customized.items():
                    if updated[key] != value:
                        raise AssertionError(f"User preference lost: {key}")
                actual_new = identity(executable, env, case / "new-identity.json")
                if actual_new["version"] != newer or actual_new["variant"] != variant:
                    raise AssertionError("Actual restarted binary has wrong version/variant")
                report["new_identity"] = actual_new
                if variant == "portable":
                    if (install / "_internal/update_acceptance_obsolete.dll").exists():
                        raise AssertionError("Obsolete managed DLL remains")
                    if not (install / "_internal/update_acceptance_added.dll").is_file():
                        raise AssertionError("New managed DLL missing")
                    if (install / "update_acceptance_resource.txt").read_text() != "new managed resource":
                        raise AssertionError("Managed resource not replaced")
                    installed = load_json(install / transaction.INSTALLED)
                    if installed["version"] != newer or installed["entrypoint"] != executable.name:
                        raise AssertionError("Installed manifest did not retain launcher identity")
                    report["installed_managed_files"] = len(installed["managed_files"])
                if (install / "PDF_Bookmarks.exe").exists():
                    raise AssertionError("Renamed launcher duplicated with its official filename")
            wait_until(lambda: app_windows(executable))
            # Both successful startup and rollback startup clean their own
            # completed transaction after the temporary helper actually exits.
            cleanup_receipt = tx.directory.parent / ("cleanup_" + tx.directory.name + ".json")
            wait_until(lambda: not tx.directory.exists() and not cleanup_receipt.exists(), timeout=30)
            for name, payload in extras.items():
                if (install / name).read_bytes() != payload:
                    raise AssertionError(f"Unknown user data changed: {name}")
            for pattern in ("*.old", "*.new", "*.part", ".pdf-update-*"):
                if list(install.rglob(pattern)):
                    raise AssertionError(f"Program update residue: {pattern}")
            report.update({"helper_returncode": code, "renamed_launcher_preserved": True,
                           "unknown_files_preserved": list(extras), "program_and_config_verified": True,
                           "transaction_cleaned_by_application": True,
                           "cleanup_receipt_removed_by_application": True, "passed": True})
            print(f"PASS real frozen {variant}: {report['scenario']}", flush=True)
            return report
        except Exception as error:
            report["error"] = repr(error)
            report["passed"] = False
            if tx is not None:
                report["remaining_transaction_entries"] = sorted(
                    str(path.relative_to(tx.directory)) for path in tx.directory.rglob("*")
                ) if tx.directory.exists() else []
                cleanup_receipt = tx.directory.parent / ("cleanup_" + tx.directory.name + ".json")
                if cleanup_receipt.exists():
                    report["remaining_cleanup_receipt"] = load_json(cleanup_receipt)
                if (tx.directory / "journal.json").exists():
                    report["failed_journal"] = load_json(tx.directory / "journal.json")
                if (tx.directory / "update.log").exists():
                    report["update_log"] = (tx.directory / "update.log").read_text(encoding="utf-8")
            # Keep essential failure evidence outside the disposable install.
            journal.atomic_json(ROOT / "build" / f"frozen_failure_{variant}.json", report)
            raise
        finally:
            if helper_process is not None and helper_process.poll() is None:
                processes.terminate_tree(helper_process)
            if processes.matching_processes(executable):
                if fail_health:
                    kill_owned_app(executable)
                else:
                    try:
                        close_app(executable)
                    except TimeoutError:
                        kill_owned_app(executable)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "build/frozen_update_report.json")
    parser.add_argument("--only", choices=("single", "portable"), action="append")
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("Real frozen update integration requires Windows")
    current = (ROOT / "VERSION").read_text().strip()
    newer = successor_version(current)
    successor = build_successor(newer)
    report = {"current_version": current, "synthetic_successor": newer, "cases": [],
              "scope": "real frozen GUI/config/core health; no live GitHub release modified"}
    # On ordinary Windows and windows-latest, LOCALAPPDATA is on the system
    # drive while the build workspace can reside on a different drive.
    temporary_parent = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Temp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="PDF_Bookmarks_frozen_中文 ", dir=temporary_parent) as name:
            report["frozen_pdf_cli"] = verify_frozen_pdf_cli(Path(name))
            for variant in args.only or ("single", "portable"):
                for fail_health in (False, True):
                    report["cases"].append(run_case(Path(name), variant, fail_health, current, newer, successor))
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["error"] = repr(error)
        raise
    finally:
        journal.atomic_json(args.report, report)


if __name__ == "__main__":
    main()
