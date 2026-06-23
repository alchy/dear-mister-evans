import unittest
from unittest import mock
from improved.levine_corpus.engine import OcrEngine, TesseractEngine

class TestTesseractEngine(unittest.TestCase):
    def test_is_ocr_engine_with_per_page_batch(self):
        eng = TesseractEngine()
        self.assertIsInstance(eng, OcrEngine)
        self.assertEqual(eng.max_pages, 1)

    def test_available_reflects_which(self):
        eng = TesseractEngine()
        with mock.patch("improved.levine_corpus.engine.which", return_value="/usr/bin/tesseract"):
            self.assertTrue(eng.available())
        with mock.patch("improved.levine_corpus.engine.which", return_value=None):
            self.assertFalse(eng.available())

    def test_ocr_batch_calls_tesseract_per_page_and_joins(self):
        eng = TesseractEngine()
        calls = []
        def fake_run(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(stdout=f"text-{cmd[1]}\n")
        with mock.patch("improved.levine_corpus.engine.subprocess.run", side_effect=fake_run):
            out = eng.ocr_batch(["a.png", "b.png"])
        self.assertEqual(len(calls), 2)
        self.assertIn("text-a.png", out)
        self.assertIn("text-b.png", out)

if __name__ == "__main__":
    unittest.main()
