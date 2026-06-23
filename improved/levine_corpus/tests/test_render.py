import unittest
from improved.levine_corpus.render import _pdftoppm_cmd

class TestPdftoppmCmd(unittest.TestCase):
    def test_full_range(self):
        cmd = _pdftoppm_cmd("book.pdf", "/out/page", 300, None, None)
        self.assertEqual(cmd, ["pdftoppm", "-png", "-gray", "-r", "300", "book.pdf", "/out/page"])

    def test_page_range(self):
        cmd = _pdftoppm_cmd("book.pdf", "/out/page", 300, 1, 5)
        self.assertIn("-f", cmd); self.assertIn("1", cmd)
        self.assertIn("-l", cmd); self.assertIn("5", cmd)
        self.assertEqual(cmd[-2:], ["book.pdf", "/out/page"])

if __name__ == "__main__":
    unittest.main()
