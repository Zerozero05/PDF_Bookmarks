"""Real offscreen Tk interactions, old editor module vs current dependencies.

No physical key/mouse input, visible windows, user settings or user PDFs. The
baseline replaces toc_editor.py only; it is explicitly not an old full package.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from toc_generation import Draft, DraftEntry


def fingerprint():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in ROOT.glob("*.py")}


def load_module(path, name):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def settle(root, editor, timeout=10):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        root.update()
        future = editor._render_future
        if (future is None or future.done()) and editor.events.empty():
            root.update_idletasks()
            return
        time.sleep(.002)
    raise TimeoutError("Offscreen preview did not settle")


def trial(module, pdf, count):
    root = tk.Tk()
    root.withdraw()
    root.geometry("1200x900+30000+30000")
    host = ttk.Frame(root)
    host.pack(fill="both", expand=True)
    executor = ThreadPoolExecutor(max_workers=1)
    editor = None
    results, errors = {}, []
    counters = {"tree_delete_calls": 0, "render_calls": 0, "render_seconds": 0., "render_png_bytes": 0}
    original_render, original_error = module.render_page, module.messagebox.showerror
    def render(*args, **kwargs):
        started = time.perf_counter()
        png = original_render(*args, **kwargs)
        counters["render_calls"] += 1
        counters["render_seconds"] += time.perf_counter() - started
        counters["render_png_bytes"] += len(png)
        return png
    module.render_page = render
    module.messagebox.showerror = lambda title, message, **kwargs: errors.append(str(message))
    try:
        editor = module.open_editor(root, executor, pdf, host=host, draft_dir=None,
                                    editor_settings={"editor_topmost": False})
        editor.auto_save.set(False)
        editor.view_mode.set("目录树")
        original_delete = editor.tree.delete
        def counted_delete(*args):
            counters["tree_delete_calls"] += 1
            return original_delete(*args)
        editor.tree.delete = counted_delete
        editor.draft = Draft(pdf, 4, [
            DraftEntry(1 if index % 20 == 0 else 2,
                       f"Chapter {index // 20 + 1}" if index % 20 == 0 else f"Synthetic section {index}",
                       index % 3 + 1, 2, "低", "Synthetic unconfirmed entry", False)
            for index in range(count)], [1], {"offset": 0}, "Synthetic interaction benchmark", [])
        editor._load_mapping()

        def sample(name, action):
            before = dict(counters)
            cache = getattr(editor, "session_cache", None)
            before_hits = cache.hits if cache is not None else 0
            before_misses = cache.misses if cache is not None else 0
            started = time.perf_counter()
            action()
            root.update_idletasks()
            handler = time.perf_counter() - started
            settle(root, editor)
            elapsed = time.perf_counter() - started
            item = {key: counters[key] - before[key] for key in counters}
            item.update({"handler_seconds": handler, "settled_seconds": elapsed,
                         "cache_hits": cache.hits - before_hits if cache is not None else 0,
                         "cache_misses": cache.misses - before_misses if cache is not None else 0,
                         "cache_bytes": cache.used_bytes if cache is not None else 0,
                         "first_chapter_open": bool(editor.tree.item("0", "open")) if editor.tree.exists("0") else None})
            results[name] = item

        def choose(indices):
            editor.tree.selection_set(*(str(index) for index in indices))
            editor.tree.focus(str(indices[0]))
            editor._selected()
            settle(root, editor)

        sample("first_table_build", editor._refresh)
        choose([21])
        editor.tree.item("0", open=False)
        sample("enter_single_confirm", editor.confirm_selected)
        if not editor.draft.entries[21].confirmed:
            raise AssertionError("Single Enter handler did not confirm its selected entry")
        choose(list(range(41, 51)))
        editor.tree.item("0", open=False)
        sample("enter_multi_confirm_10", editor.confirm_selected)
        if not all(editor.draft.entries[index].confirmed for index in range(41, 51)):
            raise AssertionError("Multi Enter handler did not confirm all selected entries")
        editor.tree.item("0", open=False)
        before_search_selection = editor.tree.selection()
        def search():
            editor.search_text.set(f"Synthetic section {count - 1}")
            editor._filter_changed()
        sample("search_apply", search)
        def clear():
            editor.search_text.set("")
            editor._filter_changed()
        sample("search_clear", clear)
        results["search_clear"]["selection_restored"] = editor.tree.selection() == before_search_selection
        results["all_confirmations_correct"] = sum(entry.confirmed for entry in editor.draft.entries) == 11
        results["errors"] = errors.copy()
        if errors:
            raise AssertionError(errors)
        return results
    finally:
        module.render_page = original_render
        module.messagebox.showerror = original_error
        if editor is not None:
            editor.close()
        executor.shutdown(wait=True)
        root.update_idletasks()
        root.destroy()
        gc.collect()


def run(output, repetitions):
    output = Path(output).resolve()
    if not output.is_dir() or output.drive.upper() != "D:":
        raise ValueError("Choose an existing task-owned D: output directory")
    target = output / "editor_interaction_benchmark.json"
    if target.exists():
        raise FileExistsError(target)
    baseline = subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "show", "0097a07:toc_editor.py"],
                              cwd=ROOT, capture_output=True, check=True).stdout
    baseline_path, current_path = output / "toc_editor_baseline_0097a07.py", output / "toc_editor_current.py"
    if baseline_path.exists() or current_path.exists():
        raise FileExistsError("Module snapshots already exist; use a new task output subdirectory")
    baseline_path.write_bytes(baseline)
    current_path.write_bytes((ROOT / "toc_editor.py").read_bytes())
    dependencies = fingerprint()
    modules = {"baseline_editor_only": load_module(baseline_path, "benchmark_old_editor"),
               "current_editor": load_module(current_path, "benchmark_new_editor")}
    pdf = output / "interaction_synthetic.pdf"
    with pymupdf.open() as document:
        for index in range(4):
            page = document.new_page(width=600, height=800)
            page.insert_text((30, 70), f"Synthetic interaction target page {index + 1}")
        document.save(pdf)
    original = hashlib.sha256(pdf.read_bytes()).hexdigest()
    rows = []
    for count in (1000, 5000):
        samples = {name: [] for name in modules}
        for index in range(repetitions):
            for name, module in modules.items():
                result = trial(module, pdf, count)
                samples[name].append(result)
                print(json.dumps({"entries": count, "trial": index + 1, "variant": name, "completed": True}), flush=True)
        summary = {}
        for name, variant_samples in samples.items():
            summary[name] = {}
            for operation in ("first_table_build", "enter_single_confirm", "enter_multi_confirm_10", "search_apply", "search_clear"):
                summary[name][operation] = {
                    "median_handler_seconds": statistics.median(sample[operation]["handler_seconds"] for sample in variant_samples),
                    "median_settled_seconds": statistics.median(sample[operation]["settled_seconds"] for sample in variant_samples),
                    "tree_delete_calls": [sample[operation]["tree_delete_calls"] for sample in variant_samples],
                    "render_calls": [sample[operation]["render_calls"] for sample in variant_samples],
                    "cache_hits": [sample[operation]["cache_hits"] for sample in variant_samples],
                    "first_chapter_open": [sample[operation]["first_chapter_open"] for sample in variant_samples]}
        rows.append({"entries": count, "summary": summary, "samples": samples})
    unchanged = hashlib.sha256(pdf.read_bytes()).hexdigest() == original
    if not unchanged:
        raise AssertionError("Interaction modified synthetic PDF")
    report = {"python": sys.version, "platform": platform.platform(), "pymupdf": pymupdf.VersionBind,
              "baseline_commit": "0097a07", "baseline_module_sha256": hashlib.sha256(baseline).hexdigest(),
              "current_module_sha256": hashlib.sha256(current_path.read_bytes()).hexdigest(),
              "shared_dependency_fingerprints": dependencies, "dependencies_unchanged_during_run": dependencies == fingerprint(),
              "repetitions": repetitions, "pdf_sha256": original, "input_unchanged": unchanged, "results": rows,
              "limits": ["Baseline replaces toc_editor.py only and shares current backend; this is not a complete old-package benchmark.",
                         "Tk root stays withdrawn with an embedded editor; real widgets and handlers run without visible windows or physical keyboard input.",
                         "Enter uses its real bound command handler directly; handler times exclude asynchronous settling, which is reported separately.",
                         "Editor stages may include new B/C paths; fingerprints bind the measured sources."]}
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(target), "dependencies_unchanged_during_run": report["dependencies_unchanged_during_run"],
                      "results": [{"entries": item["entries"], "summary": item["summary"]} for item in rows]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    options = parser.parse_args()
    run(options.output, options.repetitions)
