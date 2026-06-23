import unittest
from improved.levine_corpus.segment import segment_chapters

class TestSegment(unittest.TestCase):
    def test_splits_on_chapter_headings(self):
        text = "Chapter One\nIntro body\nChapter Two\nSecond body"
        out = segment_chapters(text, r"(?m)^Chapter .+$")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0], "Chapter One")
        self.assertIn("Intro body", out[0][1])
        self.assertEqual(out[1][0], "Chapter Two")

    def test_degrades_to_single_when_no_headings(self):
        text = "no headings here at all"
        out = segment_chapters(text, r"(?m)^Chapter .+$")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "full")

if __name__ == "__main__":
    unittest.main()
