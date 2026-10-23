"""Session cache and forced-OCR checks use generated documents only."""

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

import pymupdf

from session_cache import SessionCache, pdf_identity
import toc_generation as generation


class SessionCacheTests(unittest.TestCase):
    def test_default_budget_and_isolation_on_put_and_get(self):
        cache = SessionCache()
        self.assertEqual(cache.max_bytes, 64 * 1024 * 1024)
        value = [generation._Line("Source", 1, 2, 3, .9, numbers=[(1, 5)])]
        cache.put("recognition", (1,), value)
        value[0].text = "Edited draft"
        result = cache.get("recognition", (1,))
        self.assertEqual(result[0].text, "Source")
        result[0].numbers.append((2, 7))
        self.assertEqual(cache.get("recognition", (1,))[0].numbers, [(1, 5)])
        self.assertEqual(cache.hits, 2)

    def test_namespaces_share_one_lru_budget(self):
        probe = SessionCache()
        probe.put("preview", (1,), b"a" * 1000)
        one_size = probe.used_bytes
        cache = SessionCache(max_bytes=one_size * 2 + 20)
        self.assertTrue(cache.put("preview", (1,), b"a" * 1000))
        self.assertTrue(cache.put("preview", (2,), b"b" * 1000))
        self.assertIsNotNone(cache.get("preview", (1,)))
        self.assertTrue(cache.put("preview", (3,), b"c" * 1000))
        self.assertIsNone(cache.get("preview", (2,)))
        self.assertEqual(cache.get("preview", (1,)), b"a" * 1000)
        self.assertLessEqual(cache.used_bytes, cache.max_bytes)
        self.assertGreater(cache.evictions, 0)
        # Recognition can evict previews under the same total budget.
        cache.put("recognition", (4,), ["line " * 300])
        self.assertLessEqual(cache.used_bytes, cache.max_bytes)

    def test_oversized_replacement_drops_old_key_without_over_budget(self):
        cache = SessionCache(max_bytes=1024)
        self.assertTrue(cache.put("preview", 1, b"small"))
        self.assertFalse(cache.put("preview", 1, b"x" * 2048))
        self.assertIsNone(cache.get("preview", 1))
        self.assertEqual(cache.used_bytes, 0)
        self.assertFalse(SessionCache(0).put("preview", 1, b""))

    def test_new_pdf_identity_invalidates_both_namespaces(self):
        cache = SessionCache()
        old, new, other = ("book.pdf", 100, 10), ("book.pdf", 101, 11), ("other.pdf", 100, 10)
        cache.put("recognition", 1, ["old"], document=old)
        cache.put("preview", 1, b"old", document=old)
        cache.put("preview", 1, b"other", document=other)
        self.assertIsNone(cache.get("recognition", 1, document=new))
        self.assertEqual(cache.count, 1)
        self.assertEqual(cache.get("preview", 1, document=other), b"other")

    def test_explicit_invalidation_and_clear(self):
        cache = SessionCache()
        document = ("book.pdf", 10, 20)
        cache.put("preview", 1, b"page", document=document)
        cache.put("recognition", 1, ["line"], document=document)
        cache.put("preview", 1, b"unbound")
        cache.invalidate(document=document, namespace="preview")
        self.assertEqual(len(cache), 2)
        cache.invalidate(namespace="recognition")
        self.assertEqual(len(cache), 1)
        cache.clear()
        self.assertEqual((len(cache), cache.used_bytes), (0, 0))

    def test_invalid_budget_is_rejected(self):
        for value in (-1, True, 1.5, "1024"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SessionCache(value)


class RecognitionCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="recognition-cache-")
        self.addCleanup(temporary.cleanup)
        self.pdf = Path(temporary.name) / "synthetic.pdf"
        with pymupdf.open() as doc:
            for number in range(1, 4):
                page = doc.new_page(width=300, height=400)
                for index, title in enumerate(("Chapter 1 Alpha .... 1", "1.1 Beta .... 2", "1.2 Gamma .... 3")):
                    page.insert_text((30, 70 + index * 40), title)
            doc.save(self.pdf)
        self.original = hashlib.sha256(self.pdf.read_bytes()).hexdigest()

    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.original)

    @staticmethod
    def lines(*args, **kwargs):
        return [generation._Line("Chapter 1 OCR Alpha .... 1", 30, 70, 15, .98),
                generation._Line("1.1 OCR Beta .... 2", 40, 100, 15, .98)]

    def generate(self, **kwargs):
        return generation.generate_toc(self.pdf, toc_start=1, toc_end=1, offset=0, **kwargs)

    def test_default_text_read_does_not_use_ocr(self):
        with patch.object(generation, "_ocr_lines", side_effect=AssertionError("unexpected OCR")):
            draft = self.generate(session_cache=SessionCache())
        self.assertEqual(draft.method, "文字提取")
        self.assertIn("1.1 Beta", [entry.title for entry in draft.entries])

    def test_force_is_explicit_page_local_and_keeps_results_unconfirmed(self):
        cache = SessionCache()
        with patch.object(generation, "_ocr_lines", side_effect=self.lines) as recognize:
            draft = self.generate(force_ocr_pages={1}, session_cache=cache)
            normal = self.generate(session_cache=cache)
            self.assertEqual(recognize.call_count, 1)
        self.assertEqual(draft.method, "本地 OCR")
        self.assertIn("1.1 OCR Beta", [entry.title for entry in draft.entries])
        self.assertIn("1.1 Beta", [entry.title for entry in normal.entries])
        self.assertFalse(any(entry.confirmed for entry in draft.entries))

    def test_force_option_does_not_apply_to_independent_body_evidence(self):
        with patch.object(generation, "_ocr_lines", side_effect=AssertionError("body must use its text")):
            draft = generation.generate_toc(self.pdf, toc_start=1, toc_end=1, force_ocr_pages=[2])
        self.assertEqual(draft.method, "文字提取")

    def test_force_on_one_directory_page_keeps_other_pages_on_text_path(self):
        with patch.object(generation, "_ocr_lines", side_effect=self.lines) as recognize:
            draft = generation.generate_toc(self.pdf, toc_start=1, toc_end=2, offset=0, force_ocr_pages=[1])
        self.assertEqual(recognize.call_count, 1)
        self.assertEqual(draft.toc_pages, [1, 2])
        self.assertIn("OCR Beta", draft.entries[2].title)
        self.assertIn("1.1 Beta", [entry.title for entry in draft.entries])
        self.assertEqual(draft.method, "文字提取 + 本地 OCR")

    def test_one_call_still_reuses_auto_detection_page_without_a_session_cache(self):
        def recognized_toc(*args, **kwargs):
            return [generation._Line("Contents", 30, 30, 15, .98)] + self.lines()
        with patch.object(generation, "_ocr_lines", side_effect=recognized_toc) as recognize:
            draft = generation.generate_toc(self.pdf, toc_end=None, offset=0, force_ocr_pages=[1])
        self.assertEqual(draft.toc_pages[0], 1)
        self.assertEqual(recognize.call_count, 1, "Auto-detection and TOC parsing must share the original local cache")

    def test_cached_read_skips_recognition_and_cannot_reuse_edited_draft(self):
        cache = SessionCache()
        with patch.object(generation, "_ocr_lines", side_effect=self.lines) as recognize:
            draft = self.generate(force_ocr_pages=[1], session_cache=cache)
            expected = deepcopy(draft)
            draft.entries[1].title = "Manually edited"
            draft.entries[1].confirmed = True
            again = self.generate(force_ocr_pages=[1], session_cache=cache)
        self.assertEqual(recognize.call_count, 1)
        self.assertEqual(again, expected)
        self.assertGreater(cache.hits, 0)

    def test_cache_key_covers_region_split_mode_and_force(self):
        cache = SessionCache()
        options = ({}, {"column_mode": "single"}, {"column_mode": "double"},
                   {"page_regions": {1: {"rect": (.05, .05, .95, .8)}}},
                   {"page_regions": {1: {"split": .6}}})
        with patch.object(generation, "_ocr_lines", side_effect=self.lines) as recognize:
            for option in options:
                self.generate(force_ocr_pages=[1], session_cache=cache, **option)
                self.generate(force_ocr_pages=[1], session_cache=cache, **option)
            self.assertEqual(recognize.call_count, len(options))

    def test_changed_pdf_mtime_expires_cached_recognition_and_preview(self):
        cache = SessionCache()
        with patch.object(generation, "_ocr_lines", side_effect=self.lines) as recognize:
            self.generate(force_ocr_pages=[1], session_cache=cache)
            old = pdf_identity(self.pdf)
            cache.put("preview", (1, 100), b"old preview", document=old)
            stat = self.pdf.stat()
            os.utime(self.pdf, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
            self.generate(force_ocr_pages=[1], session_cache=cache)
            self.assertEqual(recognize.call_count, 2)
            self.assertIsNone(cache.get("preview", (1, 100), document=pdf_identity(self.pdf)))

    def test_invalid_force_pages_are_rejected_before_ocr(self):
        for pages in (1, "1", {1: True}, [0], [4], [True], [1.5]):
            with self.subTest(pages=pages), patch.object(generation, "_ocr_lines") as recognize:
                with self.assertRaises(generation.BookmarkError):
                    self.generate(force_ocr_pages=pages)
                recognize.assert_not_called()

    def test_cancelled_result_is_not_cached(self):
        cache = SessionCache()
        cancel = threading.Event()
        def recognize(*args, **kwargs):
            cancel.set()
            return self.lines()
        with patch.object(generation, "_ocr_lines", side_effect=recognize):
            with self.assertRaisesRegex(generation.BookmarkError, "取消"):
                self.generate(force_ocr_pages=[1], session_cache=cache, cancel=cancel)
        self.assertEqual(cache.count, 0)


class OcrBatchTests(unittest.TestCase):
    def test_bounded_batches_preserve_order_and_rotate_each_small_batch(self):
        calls, rotations = [], []
        def recognize(crops):
            calls.append(list(crops))
            return SimpleNamespace(txts=[str(value) for value in crops], scores=[.99] * len(crops))
        def rotate(crops):
            rotations.append(list(crops))
            return crops, None
        engine = SimpleNamespace(recognize_txt=recognize, cls_and_rotate=rotate)
        texts, scores = generation._recognize_crops(engine, list(range(19)), None, rotate=True)
        self.assertEqual(texts, [str(value) for value in range(19)])
        self.assertEqual(scores, [.99] * 19)
        self.assertEqual([len(batch) for batch in calls], [8, 8, 3])
        self.assertEqual(calls, rotations)

    def test_cancel_after_inference_stops_before_next_batch(self):
        calls, cancel = [], threading.Event()
        def recognize(crops):
            calls.append(crops)
            cancel.set()
            return SimpleNamespace(txts=["title"] * len(crops), scores=[.99] * len(crops))
        engine = SimpleNamespace(recognize_txt=recognize)
        with self.assertRaisesRegex(generation.BookmarkError, "取消"):
            generation._recognize_crops(engine, list(range(30)), cancel)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]), 8)

    def test_empty_batch_does_not_shift_next_rows(self):
        def recognize(crops):
            if crops[0] == 0:
                return SimpleNamespace(txts=None, scores=None)
            return SimpleNamespace(txts=[str(value) for value in crops], scores=[.99] * len(crops))
        texts, scores = generation._recognize_crops(SimpleNamespace(recognize_txt=recognize), list(range(10)), None)
        self.assertEqual(texts, [""] * 8 + ["8", "9"])
        self.assertEqual(scores, [0.] * 8 + [.99, .99])


if __name__ == "__main__":
    unittest.main()
