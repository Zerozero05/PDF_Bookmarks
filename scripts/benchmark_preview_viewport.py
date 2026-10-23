"""Compare existing full preview against clipped rendering on synthetic PDF.

This is feasibility evidence, not a GUI implementation. No user PDF is opened.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time

import numpy as np
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gui_support import render_page


def run(output, repetitions=7):
    output = Path(output).resolve()
    if output.drive.upper() != "D:" or not output.is_dir():
        raise ValueError("Choose an existing task-owned D: directory.")
    pdf, target = output / "preview_viewport_synthetic.pdf", output / "preview_viewport_benchmark.json"
    if pdf.exists() or target.exists():
        raise FileExistsError("Benchmark output already exists; choose a new task directory.")
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=2400)
        for index in range(150):
            y = 20 + index * 15
            page.insert_text((25, y), f"Synthetic long PDF row {index + 1}: preview coordinate check", fontsize=8)
            page.draw_line((25, y + 3), (575, y + 3), color=(.3, .5, .7), width=.2)
        doc.save(pdf)
    original = hashlib.sha256(pdf.read_bytes()).hexdigest()
    scale = min(6., (3600 - .5) / 600, (8192 - .5) / 2400)
    clip = pymupdf.Rect(512 / scale, 2048 / scale, 1412 / scale, 2748 / scale)
    full_times, clipped_times = [], []
    for _ in range(repetitions):
        start = time.perf_counter()
        full_png = render_page(pdf, 1, 3600, 8192, max_scale=6.)
        full_times.append(time.perf_counter() - start)
        start = time.perf_counter()
        with pymupdf.open(pdf) as doc:
            viewport = doc[0].get_pixmap(matrix=pymupdf.Matrix(scale, scale),
                                         clip=clip, colorspace=pymupdf.csRGB, alpha=False)
            viewport_png = viewport.tobytes("png")
        clipped_times.append(time.perf_counter() - start)
    full = pymupdf.Pixmap(full_png)
    full_pixels = np.frombuffer(full.samples, np.uint8).reshape(full.height, full.width, 3)
    view_pixels = np.frombuffer(viewport.samples, np.uint8).reshape(viewport.height, viewport.width, 3)
    corresponding = full_pixels[viewport.y:viewport.y + viewport.height, viewport.x:viewport.x + viewport.width]
    equal = np.array_equal(corresponding, view_pixels)
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != original:
        raise AssertionError("Read-only rendering modified its synthetic PDF")
    report = {"python": sys.version, "platform": platform.platform(), "pymupdf": pymupdf.VersionBind,
              "scenario": "600x2400-point generated PDF, zoom constrained by existing 8192-pixel bounds",
              "scale": scale, "repetitions": repetitions, "pdf_sha256": original, "input_unchanged": True,
              "full": {"samples_seconds": full_times, "median_seconds": statistics.median(full_times),
                       "width": full.width, "height": full.height, "raw_rgb_bytes": len(full.samples), "png_bytes": len(full_png)},
              "viewport": {"samples_seconds": clipped_times, "median_seconds": statistics.median(clipped_times),
                           "width": viewport.width, "height": viewport.height,
                           "pixel_origin": [viewport.x, viewport.y], "pdf_rect": list(clip),
                           "raw_rgb_bytes": len(viewport.samples), "png_bytes": len(viewport_png)},
              "viewport_pixels_equal_corresponding_full_region": equal,
              "limits": ["No GUI viewport/canvas integration was changed by this benchmark.",
                         "Offscreen highlight, selection and scrolling transforms need integration tests.",
                         "This generated long-page case is not a promise for all PDFs or normal fit-page previews."]}
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repetitions", type=int, default=7)
    args = parser.parse_args()
    run(args.output, args.repetitions)
