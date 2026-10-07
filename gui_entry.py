"""Launch the GUI; files dropped onto the EXE icon arrive as arguments."""

import argparse
from dataclasses import asdict
from pathlib import Path
import sys

from build_info import get_build_info


def await_update_commit(window, transaction_dir):
    """Keep PDF tasks disabled until the helper durably commits this update."""
    from updater import UpdateError
    from updater.manifest import load_json
    if window.closed:
        return
    directory = Path(transaction_dir)
    try:
        committed = not directory.exists() or load_json(directory / "journal.json").get("state") == "committed"
    except (OSError, UpdateError):
        committed = False
    if committed:
        window._set_busy(False)
        window.status.set("更新已完成，可以继续处理 PDF。")
    else:
        window.root.after(150, await_update_commit, window, transaction_dir)


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-info-json", metavar="PATH", help="write embedded build identity and exit")
    parser.add_argument("--update-transaction", metavar="PATH")
    parser.add_argument("--update-token")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(arguments)
    info = get_build_info()
    if args.build_info_json:
        from updater.journal import atomic_json
        atomic_json(Path(args.build_info_json), asdict(info))
        return
    if bool(args.update_transaction) != bool(args.update_token):
        parser.error("update transaction and token must be used together")
    from updater.launcher import resume_pending_update
    if not args.update_transaction and resume_pending_update(info):
        return
    config_path = None
    on_ready = None
    if args.update_transaction:
        from config_manager import migrate_config, read_config
        from updater.healthcheck import ack_health, validate_health_start
        data = validate_health_start(args.update_transaction, args.update_token, info)
        config_path = data["config_path"]
        try:
            migrate_config(config_path, backup_dir=Path(args.update_transaction) / "backup" / "config_migration")
            read_config(config_path, strict=True)
        except OSError as error:
            from updater.journal import atomic_json
            atomic_json(Path(args.update_transaction) / "health-failure.json", {"message": str(error)})
            return 1

        def on_ready(window):
            window._set_busy(True)
            window.status.set("正在完成程序更新，请稍候…")
            # Main GUI imports the PDF core and builds TkDnD before this callback.
            import bookmarks_core
            import pymupdf
            with pymupdf.open() as document:
                document.new_page(width=20, height=20)
                if document.page_count != 1 or not callable(bookmarks_core.write_plan):
                    raise RuntimeError("PDF core initialization failed")
            ack_health(args.update_transaction, args.update_token, info,
                       config_ready=True, gui_ready=bool(window.root.winfo_exists()), core_ready=True)
            window.root.after(150, await_update_commit, window, args.update_transaction)

    from bookmarks_gui import launch
    try:
        launch(args.paths, settings_path=config_path, on_ready=on_ready)
    except Exception as error:
        if not args.update_transaction:
            raise
        from updater.journal import atomic_json
        atomic_json(Path(args.update_transaction) / "health-failure.json", {"message": str(error)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
