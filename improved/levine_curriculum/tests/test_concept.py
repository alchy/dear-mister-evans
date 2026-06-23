import unittest
from improved.levine_curriculum.concept import slugify, blank_concept, CONCEPT_KEYS

class TestConcept(unittest.TestCase):
    def test_slugify_basic(self):
        self.assertEqual(slugify("Tritone Substitution"), "tritone-substitution")
    def test_slugify_strips_punct_and_case(self):
        self.assertEqual(slugify("II-V-I !!"), "ii-v-i")
    def test_slugify_empty_fallback(self):
        self.assertEqual(slugify("()"), "concept")
    def test_blank_concept_has_all_keys_and_id(self):
        c = blank_concept("Block Chords")
        self.assertEqual(sorted(c), sorted(CONCEPT_KEYS))
        self.assertEqual(c["id"], "block-chords")
        self.assertEqual(c["practice"], [])

if __name__ == "__main__":
    unittest.main()
