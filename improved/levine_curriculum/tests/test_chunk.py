import unittest, tempfile
from pathlib import Path
from improved.levine_curriculum.chunk import chunk_corpus, Chunk

class TestChunk(unittest.TestCase):
    def _corpus(self, d, text):
        Path(d, "01.md").write_text(text)

    def test_small_windows_cover_text_with_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, "A" * 50)
            chunks = chunk_corpus(d, max_chars=20, overlap=5)
            self.assertGreaterEqual(len(chunks), 3)
            self.assertTrue(all(isinstance(c, Chunk) for c in chunks))
            self.assertTrue(all(len(c.text) <= 20 for c in chunks))

    def test_attaches_chapter_and_pages(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, "CHAPTER SIX\n<!-- p.84 -->\nsome text here <!-- p.85 -->")
            chunks = chunk_corpus(d, max_chars=4000, overlap=100)
            self.assertEqual(chunks[0].chapter, "CHAPTER SIX")
            self.assertEqual(chunks[0].pages, "p.84-85")

if __name__ == "__main__":
    unittest.main()
