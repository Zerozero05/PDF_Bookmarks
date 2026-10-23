"""Opt-in timing is out-of-band, current-run-only, and survives failures."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pymupdf

from session_cache import SessionCache
import toc_generation as generation


class RecognitionTimingTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="toc-timings-")
        self.addCleanup(folder.cleanup)
        self.pdf = Path(folder.name) / "synthetic.pdf"
        with pymupdf.open() as document:
            for index in range(3):
                page = document.new_page(width=300, height=400)
                page.insert_text((30, 50), "Contents")
                page.insert_text((30, 100), "Chapter 1 Alpha .... 1")
                page.insert_text((40, 140), "1.1 Beta .... 2")
            document.save(self.pdf)
        self.original = self.pdf.read_bytes()

    def tearDown(self):
        self.assertEqual(self.pdf.read_bytes(), self.original)
        self.assertIsNone(generation._TIMINGS.get(), "A completed or failed call leaked timing context")

    def generate(self, **kwargs):
        return generation.generate_toc(self.pdf, toc_start=1, toc_end=1, offset=0, **kwargs)

    def test_optional_timing_leaves_draft_exactly_unchanged(self):
        expected = self.generate()
        metrics = {"caller_note": "retain"}
        actual = self.generate(timings=metrics)
        self.assertEqual(actual, expected)
        self.assertEqual(metrics["status"], "completed")
        self.assertEqual(metrics["caller_note"], "retain")
        self.assertEqual(metrics["extraction_pages"], 1)
        self.assertEqual(metrics["text_pages"], 1)
        self.assertEqual(metrics["ocr_pages"], 0)
        self.assertGreater(metrics["extraction_seconds"], 0)
        self.assertGreaterEqual(metrics["total_seconds"], metrics["extraction_seconds"])
        self.assertNotIn("timings", vars(actual))

    def test_cache_hit_does_not_replay_old_page_costs(self):
        cache, first, second = SessionCache(), {}, {}
        expected = self.generate(timings=first, session_cache=cache)
        actual = self.generate(timings=second, session_cache=cache)
        self.assertEqual(actual, expected)
        self.assertEqual(first["cache_misses"], 1)
        self.assertEqual(second["cache_hits"], 1)
        for name in ("extraction_seconds", "render_seconds", "ocr_seconds", "refinement_seconds"):
            self.assertEqual(second[name], 0.)
        self.assertEqual(second["extraction_pages"], 0)
        self.assertEqual(second["text_pages"], 0)
        self.assertGreater(second["total_seconds"], 0.)

    @staticmethod
    def engine(cancel=None):
        texts = ["Contents", "Chapter 1 Alpha .... 1", "1.1 Beta .... 2"]
        class Engine:
            use_cls = True
            def __call__(self, image, use_cls=None):
                self.use_cls = use_cls
                return SimpleNamespace(boxes=[np.array([[20, y], [250, y], [250, y + 14], [20, y + 14]], float)
                                              for y in (20, 50, 80)], txts=texts, scores=[.98] * 3)
            def cls_and_rotate(self, crops):
                return crops, None
            def recognize_txt(self, crops):
                if cancel is not None:
                    cancel.set()
                return SimpleNamespace(txts=None, scores=None)
        return Engine()

    def test_ocr_includes_real_subphase_timing_and_completed_counts(self):
        metrics = {}
        with patch.object(generation, "_engine", return_value=self.engine()), \
                patch.object(generation, "_title_crop", return_value=np.zeros((10, 40, 3), np.uint8)):
            self.generate(force_ocr_pages=[1], timings=metrics)
        self.assertEqual(metrics["ocr_pages"], 1)
        self.assertGreaterEqual(metrics["ocr_calls"], 2)
        self.assertGreaterEqual(metrics["refinement_batches"], 1)
        self.assertGreater(metrics["refinement_seconds"], 0.)
        self.assertGreaterEqual(metrics["ocr_seconds"], metrics["refinement_seconds"])
        self.assertGreaterEqual(metrics["total_seconds"], metrics["ocr_seconds"])
        self.assertGreater(metrics["render_seconds"], 0.)
        self.assertIn("Do not sum", metrics["timing_note"])

    def test_failure_preserves_finished_extraction_and_failed_stage_time(self):
        metrics = {}
        with patch.object(generation, "_ocr_lines", side_effect=RuntimeError("controlled failure")):
            with self.assertRaisesRegex(RuntimeError, "controlled failure"):
                generation.generate_toc(self.pdf, toc_start=1, toc_end=2, offset=0,
                                        force_ocr_pages=[2], timings=metrics)
        self.assertEqual(metrics["status"], "failed")
        self.assertEqual(metrics["text_pages"], 1)
        self.assertEqual(metrics["extraction_pages"], 1)
        self.assertEqual(metrics["ocr_pages"], 0)
        self.assertGreater(metrics["ocr_seconds"], 0.)
        self.assertGreater(metrics["total_seconds"], 0.)

    def test_cancel_after_one_completed_retry_keeps_counts_and_restores_context(self):
        metrics, cancel = {}, threading.Event()
        engine = self.engine(cancel)
        with patch.object(generation, "_engine", return_value=engine), \
                patch.object(generation, "_title_crop", return_value=np.zeros((10, 40, 3), np.uint8)):
            with self.assertRaisesRegex(generation.BookmarkError, "取消"):
                self.generate(force_ocr_pages=[1], timings=metrics, cancel=cancel)
        self.assertEqual(metrics["status"], "cancelled")
        self.assertEqual(metrics["refinement_batches"], 1)
        self.assertEqual(metrics["ocr_pages"], 0)
        self.assertGreater(metrics["refinement_seconds"], 0.)
        self.assertTrue(engine.use_cls)

    def test_reusing_metrics_dictionary_starts_a_new_run(self):
        metrics = {}
        self.generate(timings=metrics)
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(generation.BookmarkError):
            self.generate(timings=metrics, cancel=cancel)
        self.assertEqual(metrics["status"], "cancelled")
        self.assertEqual(metrics["extraction_pages"], 0)
        self.assertEqual(metrics["extraction_seconds"], 0.)

    def test_timing_context_is_local_to_the_calling_worker(self):
        with ThreadPoolExecutor(max_workers=1) as worker:
            metrics = {}
            # Only one worker opens a PDF; this is context isolation, not
            # concurrent PyMuPDF access or a production threading strategy.
            worker.submit(self.generate, timings=metrics).result()
            self.assertIsNone(worker.submit(generation._TIMINGS.get).result())
        self.assertEqual(metrics["status"], "completed")
        self.assertIsNone(generation._TIMINGS.get())


if __name__ == "__main__":
    unittest.main()
