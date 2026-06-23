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

    def test_default_regex_matches_uppercase_not_lowercase_prose(self):
        # výchozí regex bere jen VELKÉ nadpisy, ne výskyt slova v textu
        text = "CHAPTER ONE\nintro\nchapter here is just prose\nCHAPTER TWO\nmore"
        out = segment_chapters(text)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0], "CHAPTER ONE")

    def test_collapses_consecutive_duplicate_headings(self):
        # živé záhlaví kapitoly se opakuje po stranách -> jedna kapitola, ne mnoho
        text = "CHAPTER ONE\nbody A\nCHAPTER ONE\nbody B\nCHAPTER TWO\nbody C"
        out = segment_chapters(text)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0], "CHAPTER ONE")
        self.assertIn("body A", out[0][1])
        self.assertIn("body B", out[0][1])

if __name__ == "__main__":
    unittest.main()
