"""Command-line entry point; no arguments open the desktop interface."""
import argparse
import json
import sys
from pathlib import Path

from bookmarks_core import BookmarkError, discover_pairs, inspect_pdf, write_plan


def plan_record(plan, existing):
    return {
        "pdf": str(plan.pdf_path), "toc": str(plan.toc_path),
        "page_count": plan.page_count, "existing_count": len(plan.existing),
        "existing_bookmarks": plan.existing, "bookmarks": plan.preview,
        "action": "skip" if plan.existing and existing == "skip" else "write",
    }


def print_plan(record):
    print(f"\nPDF：{record['pdf']}（{record['page_count']} 页）")
    print(f"已有书签：{record['existing_count']}；正式操作：{record['action']}")
    for item in record["bookmarks"]:
        printed = item["printed_page"]
        source = f"印刷页 {printed}" if printed is not None else "直接指定"
        print(f"{'  ' * (item['level'] - 1)}{item['title']}  [{source} → PDF 第 {item['pdf_page']} 页]")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Zotero PDF 原地添加书签目录；默认预览，备份可选。")
    sub = parser.add_subparsers(dest="command")
    for name, help_text in (("preview", "预览，不创建备份或修改 PDF"), ("write", "原地写入，默认备份")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("pdf", type=Path)
        p.add_argument("--toc", type=Path, help="默认：PDF 同目录下的同名 .toc.json")
        p.add_argument("--existing", choices=("skip", "replace"), default="skip", help="已有书签默认跳过；replace 明确覆盖全部原书签")
        p.add_argument("--json", action="store_true", help="输出 JSON 报告")
        if name == "write":
            p.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    batch = sub.add_parser("batch", help="按同名 .toc.json 处理文件夹")
    batch.add_argument("folder", type=Path)
    batch.add_argument("--recursive", action="store_true", help="含子目录，自动排除 _backup")
    batch.add_argument("--write", action="store_true", help="正式写入；不加此参数仅预览")
    batch.add_argument("--dry-run", action="store_true", help="强制预览，即使同时提供 --write")
    batch.add_argument("--existing", choices=("skip", "replace"), default="skip")
    batch.add_argument("--json", action="store_true")
    for p in (sub.choices["preview"], sub.choices["write"], batch):
        backups = p.add_mutually_exclusive_group()
        backups.add_argument("--no-backup", dest="backup", action="store_false", help="不创建 PDF 备份")
        backups.add_argument("--backup-dir", type=Path, help="自定义备份文件夹，默认：PDF 旁的 _backup")
        p.add_argument("--clear-jasminum-cache", action="store_true", help="写入成功后删除 PDF 同目录的 jasminum-outline.json")
    gui = sub.add_parser("gui", help="打开中文图形界面")
    gui.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    if args.command in (None, "gui"):
        from bookmarks_gui import launch
        launch(getattr(args, "paths", []))
        return 0

    records = []
    errors = 0
    try:
        pairs = (discover_pairs(args.folder, args.recursive,
                                exclude_dirs=[args.backup_dir] if args.backup_dir else []) if args.command == "batch"
                 else [(args.pdf, args.toc or args.pdf.with_suffix(".toc.json"))])
        if not pairs:
            raise BookmarkError("文件夹中没有可处理的 PDF。")
    except (BookmarkError, OSError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"错误：{exc}", file=sys.stderr)
        return 1

    writing = ((args.command == "write") or
               (args.command == "batch" and args.write)) and not getattr(args, "dry_run", False)
    for pdf, toc in pairs:
        if toc is None:
            record = {"pdf": str(pdf), "status": "missing_toc", "message": "缺少同名 .toc.json，已跳过。"}
            records.append(record)
            if not args.json:
                print(f"跳过：{pdf}；{record['message']}")
            continue
        try:
            plan = inspect_pdf(pdf, toc)
            record = plan_record(plan, args.existing)
            record["backup_enabled"] = args.backup
            record["backup_directory"] = str(args.backup_dir.expanduser().absolute() if args.backup_dir else plan.pdf_path.parent / "_backup") if args.backup else None
            record["clear_jasminum_cache"] = args.clear_jasminum_cache
            if not args.json:
                print_plan(record)
                print(f"备份：{record['backup_directory'] or '关闭'}；自动清除茉莉花缓存：{'开启' if args.clear_jasminum_cache else '关闭'}")
            if writing:
                record.update(write_plan(plan, existing=args.existing, backup=args.backup,
                                         backup_dir=args.backup_dir, clear_jasminum_cache=args.clear_jasminum_cache))
                if not args.json:
                    print(record["message"])
                    if record.get("backup"):
                        print(f"备份：{record['backup']}")
                    if record.get("cache_status") == "deleted":
                        print(f"已删除茉莉花缓存：{record['cache_path']}")
                    for warning in record.get("warnings", []):
                        print(f"提示：{warning}", file=sys.stderr)
            else:
                record["status"] = "preview"
            records.append(record)
        except (BookmarkError, OSError, ValueError) as exc:
            errors += 1
            records.append({"pdf": str(pdf), "status": "error", "message": str(exc)})
            if not args.json:
                print(f"错误：{pdf}；{exc}", file=sys.stderr)
    if args.json:
        print(json.dumps({"mode": "write" if writing else "preview", "results": records, "errors": errors}, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'写入' if writing else '预览'}结束：共 {len(records)} 个 PDF，错误 {errors} 个。")
    return 1 if errors else 0


if __name__ == "__main__":
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
