"""Repeatable synthetic-PDF benchmark; no real OCR accuracy/RSS claim.

The controlled engine returns fixed same-image boxes. Timing measures the real
render/group/parse/cache path plus that fake engine, not production inference.
Pass an existing D: directory with --output; the generated PDF/report stay there.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from session_cache import SessionCache
import toc_generation as generation


class CountingEngine:
    use_cls = True

    def __init__(self):
        self.detect_calls = self.retry_calls = 0

    def __call__(self, image, use_cls=None):
        self.detect_calls += 1
        self.use_cls = use_cls
        titles = ["Contents", "Chapter 1 Alpha .... 1"] + [
            f"1.{number} Synthetic topic .... {number + 1}" for number in range(1, 21)]
        boxes = [np.array([[75, y], [920, y], [920, y + 22], [75, y + 22]], dtype=float)
                 for y in range(100, 100 + len(titles) * 60, 60)]
        return SimpleNamespace(boxes=boxes, txts=titles, scores=[.98] * len(titles))

    def cls_and_rotate(self, crops):
        return crops, None

    def recognize_txt(self, crops):
        self.retry_calls += 1
        # No invented supplemental text when synthetic ink lacks such a row.
        return SimpleNamespace(txts=None, scores=None)


def run(output, repetitions=7):
    output = Path(output).resolve()
    if not output.is_dir() or output.drive.upper() != "D:":
        raise ValueError("Choose an existing task-owned D: output directory.")
    pdf = output / "recognition_cache_synthetic.pdf"
    if pdf.exists():
        raise FileExistsError(pdf)
    with pymupdf.open() as doc:
        for number in range(23):
            page = doc.new_page(width=600, height=800)
            page.insert_text((30, 50), f"Synthetic source page {number + 1}; original text retained.")
        doc.save(pdf)
    original = hashlib.sha256(pdf.read_bytes()).hexdigest()
    scenarios = {}
    baseline_draft = None
    for name, use_cache in (("without_session_cache", False), ("with_session_cache", True)):
        engine = CountingEngine()
        cache = SessionCache() if use_cache else None
        samples = []
        with patch.object(generation, "_engine", return_value=engine):
            for _ in range(repetitions):
                before_calls = engine.detect_calls
                started = time.perf_counter()
                draft = generation.generate_toc(pdf, toc_start=1, toc_end=1, offset=1,
                                                force_ocr_pages=[1], session_cache=cache)
                samples.append({"seconds": time.perf_counter() - started,
                                "detect_calls": engine.detect_calls - before_calls})
                if baseline_draft is None:
                    baseline_draft = draft
                elif draft != baseline_draft:
                    raise AssertionError("Cached and uncached drafts must match exactly")
        scenarios[name] = {"samples": samples, "median_seconds": statistics.median(item["seconds"] for item in samples),
                           "total_detect_calls": engine.detect_calls, "retry_calls": engine.retry_calls,
                           "cache_hits": cache.hits if cache is not None else 0,
                           "cache_bytes": cache.used_bytes if cache is not None else 0,
                           "cache_budget_bytes": cache.max_bytes if cache is not None else 0}
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != original:
        raise AssertionError("Recognition changed the input PDF")
    report = {"scenario": "23-page generated text PDF; forced local OCR on page 1 using a controlled fake engine",
              "python": sys.version, "platform": platform.platform(), "pymupdf": pymupdf.VersionBind,
              "repetitions": repetitions, "entries": len(baseline_draft.entries),
              "pdf_sha256": original, "input_unchanged": True, "drafts_equal": True,
              "scenarios": scenarios,
              "limits": ["Fake engine timing is not real model inference speed or OCR accuracy.",
                         "Cache accounting measures stored Python payloads, not whole-app RSS.",
                         "Preview rendering, Tk layout and production DPI are outside this benchmark."]}
    target = output / "recognition_cache_benchmark.json"
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repetitions", type=int, default=7)
    options = parser.parse_args()
    if options.repetitions < 2:
        parser.error("At least two repetitions are needed to compare a warm cache.")
    run(options.output, options.repetitions)
