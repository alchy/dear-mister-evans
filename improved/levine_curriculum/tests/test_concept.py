import unittest
from improved.levine_curriculum.concept import (
    slugify, blank_concept, CONCEPT_KEYS, norm_level, canonical_key)

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

    def test_norm_level_lowercases_known_and_falls_back(self):
        self.assertEqual(norm_level("Intermediate"), "intermediate")
        self.assertEqual(norm_level("ADVANCED"), "advanced")
        self.assertEqual(norm_level(""), "review")
        self.assertEqual(norm_level("nonsense"), "review")

    def test_canonical_key_collapses_plural_order_parens(self):
        self.assertEqual(canonical_key("Tritone Substitution"),
                         canonical_key("Tritone Substitutions"))
        self.assertEqual(canonical_key("Chord Voicing"), canonical_key("Voicing Chord"))
        self.assertEqual(canonical_key("Triads (Implicit/Review)"), canonical_key("Triads"))
        self.assertEqual(canonical_key("()"), "concept")

if __name__ == "__main__":
    unittest.main()
