"""Real icon assets and provenance must survive packaging without stale builds."""
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from scripts import build_windows, package_release
from test_packaging import PackagingFixture


class AppIconTests(PackagingFixture, unittest.TestCase):
    def test_changed_icon_invalidates_all_previously_matching_build_reports(self):
        icon = self.root / 'assets/PDF_Bookmarks.ico'
        with patch.object(build_windows, 'ROOT', self.root):
            before = build_windows.runtime_fingerprint()
            self.assertIn('assets/PDF_Bookmarks.ico', before)
            state = self.root / 'build/build-state'
            state.mkdir(parents=True)
            for kind in ('helper', 'single', 'portable', 'cli'):
                (state / (kind + '.json')).write_text(json.dumps(
                    dict(version='1.4.1', runtime_sources=before)), encoding='utf-8')
            with patch.object(package_release, 'ROOT', self.root):
                package_release.verify_build_provenance('1.4.1')
                icon.write_bytes(b'new icon content')
                with self.assertRaisesRegex(ValueError, 'different sources'):
                    package_release.verify_build_provenance('1.4.1')

    def test_icon_source_must_be_in_complete_source_package(self):
        self.sources.remove('assets/PDF_Bookmarks.ico')
        with self.assertRaisesRegex(ValueError, 'Commit/stage'):
            self.package()

    def test_actual_ico_has_standard_small_and_large_sizes(self):
        data = (Path(__file__).resolve().parents[1] / 'assets/PDF_Bookmarks.ico').read_bytes()
        reserved, kind, count = struct.unpack_from('<HHH', data)
        self.assertEqual((reserved, kind), (0, 1))
        sizes = set()
        for i in range(count):
            width, height, _, _, _, depth, length, offset = struct.unpack_from('<BBBBHHII', data, 6 + i * 16)
            sizes.add((width or 256, height or 256))
            self.assertEqual(depth, 32)
            self.assertGreater(length, 0)
            self.assertLessEqual(offset + length, len(data))
        self.assertEqual(sizes, {(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)})
