"""Measure 80-state history on synthetic 1,000/5,000-entry JSON drafts.

The report measures UndoHistory itself, excluding Tk and snapshot construction.
Run unchanged code first, then optimized code with a different --label.
"""

import argparse
import gc
import json
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor_session import UndoHistory
from session_cache import _size


def measure(count, steps=80):
    entries = [{"level": 1 if index % 15 == 0 else 2, "title": f"1.{index + 1} Synthetic title 基本概念",
                "printed_page": index + 1, "pdf_page": index + 2,
                "confidence": "低", "note": "Synthetic OCR; review required.", "confirmed": False,
                "source_page": 1 + index // 100, "source_rect": [.1, .1, .9, .2]}
               for index in range(count)]
    state = {"schema_version": 1,
             "draft": {"pdf_path": "D:\\synthetic_undo_only.pdf", "page_count": count + 10,
                       "entries": entries, "toc_pages": [1], "mapping": {"offset": 1},
                       "method": "Synthetic benchmark", "notes": [], "source_titles": None},
             "numbering_sources": [entry["title"] for entry in entries], "options": {"section_numbering": "chapter_section"}}
    history = UndoHistory()
    history.reset(state)
    samples = []
    for index in range(steps):
        entries[index % count]["confirmed"] = not entries[index % count]["confirmed"]
        started = time.perf_counter()
        recorded = history.record(state)
        samples.append(time.perf_counter() - started)
        if not recorded:
            raise AssertionError("A changed confirmation must make an undo state")
    noop = []
    for _ in range(steps):
        started = time.perf_counter()
        recorded = history.record(state)
        noop.append(time.perf_counter() - started)
        if recorded:
            raise AssertionError("An unchanged draft must not make another state")
    undo_count = redo_count = 0
    while history.can_undo:
        history.undo()
        undo_count += 1
    while history.can_redo:
        history.redo()
        redo_count += 1
    if len(history._states) != 80 or undo_count != 79 or redo_count != 79:
        raise AssertionError("The original 80-state history semantics changed")
    result = {"entries": count, "steps": steps, "states_retained": len(history._states),
              "undo_count": undo_count, "redo_count": redo_count,
              "changed_seconds": samples, "noop_seconds": noop,
              "changed_median_seconds": statistics.median(samples),
              "noop_median_seconds": statistics.median(noop),
              "history_payload_bytes": _size(history._states),
              "comparison_key_bytes": _size(history._current_json) if getattr(history, "_current_json", None) is not None else 0,
              "input_snapshot_json_bytes": len(json.dumps(state, ensure_ascii=False).encode("utf-8"))}
    del history, state, entries
    gc.collect()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", required=True, choices=("baseline", "optimized", "optimized_canonical"))
    options = parser.parse_args()
    target = Path(options.output).resolve() / f"undo_history_{options.label}.json"
    if not target.parent.is_dir() or target.drive.upper() != "D:" or target.exists():
        parser.error("Choose an existing D: output directory and an unused report label.")
    report = {"label": options.label, "python": sys.version, "platform": platform.platform(),
              "results": [measure(count) for count in (1000, 5000)],
              "limits": ["Synthetic payload timing is not a whole-GUI latency measurement.",
                         "Stored Python payload accounting is not operating-system RSS.",
                         "The existing limit is 80 stored states, permitting 79 undo transitions."]}
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(target), "results": [
        {key: value for key, value in item.items() if not key.endswith("_seconds") or "median" in key}
        for item in report["results"]]}, ensure_ascii=False, indent=2))
