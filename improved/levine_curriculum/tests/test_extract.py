import unittest
from improved.levine_curriculum.chunk import Chunk
from improved.levine_curriculum.extract import extract_concepts

class FakeClient:
    def __init__(self, payload): self.payload = payload; self.calls = 0
    def generate_json(self, prompt): self.calls += 1; return self.payload

class TestExtract(unittest.TestCase):
    def test_maps_payload_to_schema_with_source_ref(self):
        client = FakeClient({"concepts": [
            {"name": "Tritone Substitution", "summary": "S", "level": "intermediate",
             "prerequisites": ["ii V I"], "keywords": ["sub"]}]})
        ch = Chunk("text", "CHAPTER SIX", "p.84-89")
        out = extract_concepts(ch, client)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "tritone-substitution")
        self.assertEqual(out[0]["prerequisites"], ["ii-v-i"])
        self.assertEqual(out[0]["source_refs"], [{"chapter": "CHAPTER SIX", "pages": "p.84-89"}])
        self.assertEqual(out[0]["practice"], [])

    def test_skips_nameless_concepts(self):
        client = FakeClient({"concepts": [{"summary": "x"}, {"name": "  "}]})
        out = extract_concepts(Chunk("t", "c", ""), client)
        self.assertEqual(out, [])

    def test_normalizes_level_case(self):
        client = FakeClient({"concepts": [{"name": "X", "level": "Intermediate"}]})
        out = extract_concepts(Chunk("t", "c", ""), client)
        self.assertEqual(out[0]["level"], "intermediate")

if __name__ == "__main__":
    unittest.main()
