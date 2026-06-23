# improved/levine_corpus/tests/test_build.py
import unittest, tempfile
from pathlib import Path
from unittest import mock
from improved.levine_corpus.engine import OcrEngine
from improved.levine_corpus.build import batch_pages, build_corpus

class FakeEngine(OcrEngine):
    max_pages = 2
    def __init__(self): self.calls = 0
    def available(self): return True
    def ocr_batch(self, image_paths):
        self.calls += 1
        return "Chapter One\nbody " + " ".join(p.name for p in image_paths)

class TestBatch(unittest.TestCase):
    def test_batches_by_max_pages(self):
        imgs = [Path(f"page-{i:03d}.png") for i in (1, 2, 3)]
        b = batch_pages(imgs, 2)
        self.assertEqual(len(b), 2)
        self.assertEqual(b[0][0], 1); self.assertEqual(b[0][1], 2)
        self.assertEqual(b[1][0], 3); self.assertEqual(b[1][1], 3)

class TestBuildCorpus(unittest.TestCase):
    def _imgs(self, d):
        ps = []
        for i in (1, 2, 3):
            fp = Path(d) / f"page-{i:03d}.png"; fp.write_bytes(b"x"); ps.append(fp)
        return ps

    def test_build_writes_chapters_and_caches(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as out:
            eng = FakeEngine()
            with mock.patch("improved.levine_corpus.build.render_pages",
                            return_value=self._imgs(work)):
                paths = build_corpus("x.pdf", work, out, eng)
            self.assertTrue(paths)
            self.assertTrue(any(p.suffix == ".md" for p in paths))
            cache = list(Path(work, "cache").glob("batch-*.md"))
            self.assertTrue(cache)
            # resumable: druhý běh nevolá engine znovu
            calls_after_first = eng.calls
            with mock.patch("improved.levine_corpus.build.render_pages",
                            return_value=self._imgs(work)):
                build_corpus("x.pdf", work, out, eng)
            self.assertEqual(eng.calls, calls_after_first)

if __name__ == "__main__":
    unittest.main()
