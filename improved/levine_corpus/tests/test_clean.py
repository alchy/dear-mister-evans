import unittest
from improved.levine_corpus.clean import (
    dehyphenate, strip_page_numbers, drop_repeated_lines, normalize_whitespace)

class TestClean(unittest.TestCase):
    def test_dehyphenate_joins_linebreak_hyphen(self):
        self.assertEqual(dehyphenate("inter-\nval"), "interval")

    def test_dehyphenate_keeps_inline_hyphen(self):
        self.assertEqual(dehyphenate("ii-V-I cadence"), "ii-V-I cadence")

    def test_strip_page_numbers_removes_lone_number_lines(self):
        self.assertEqual(strip_page_numbers("text\n42\nmore"), "text\nmore")

    def test_strip_page_numbers_keeps_numbers_in_text(self):
        self.assertEqual(strip_page_numbers("chord 7 voicing"), "chord 7 voicing")

    def test_drop_repeated_lines_removes_running_header(self):
        pages = ["THE JAZZ PIANO BOOK\nreal a", "THE JAZZ PIANO BOOK\nreal b",
                 "THE JAZZ PIANO BOOK\nreal c", "THE JAZZ PIANO BOOK\nreal d"]
        out = drop_repeated_lines(pages, threshold=0.5)
        self.assertNotIn("THE JAZZ PIANO BOOK", "\n".join(out))
        self.assertIn("real a", out[0])

    def test_normalize_collapses_blank_runs(self):
        self.assertEqual(normalize_whitespace("a\n\n\n\nb"), "a\n\nb\n")

if __name__ == "__main__":
    unittest.main()
