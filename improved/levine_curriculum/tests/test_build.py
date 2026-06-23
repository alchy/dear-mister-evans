import unittest, tempfile, json
from pathlib import Path
from improved.levine_curriculum.build import build_curriculum

class FakeClient:
    """MAP prompt -> koncepty; CRITIC prompt -> report. Počítá MAP volání."""
    def __init__(self): self.map_calls = 0
    def generate_json(self, prompt):
        if "curriculum concept names" in prompt:
            return {"missing": [], "notes": []}
        self.map_calls += 1
        return {"concepts": [{"name": "Tritone Substitution", "summary": "s",
                              "level": "intermediate", "prerequisites": [], "keywords": ["sub"]}]}

class TestBuild(unittest.TestCase):
    def test_builds_and_is_resumable(self):
        with tempfile.TemporaryDirectory() as corpus, tempfile.TemporaryDirectory() as work, \
             tempfile.TemporaryDirectory() as out:
            Path(corpus, "01.md").write_text("CHAPTER SIX\n<!-- p.84 -->\n" + "x" * 200)
            client = FakeClient()
            build_curriculum(corpus, out, client, work, max_chars=80, overlap=10)
            self.assertTrue(Path(out, "curriculum.json").exists())
            data = json.loads(Path(out, "curriculum.json").read_text())
            self.assertTrue(any(c["id"] == "tritone-substitution" for c in data))
            first = client.map_calls
            self.assertGreater(first, 0)
            cache = list(Path(work, "map_cache").glob("chunk-*.json"))
            self.assertTrue(cache)
            build_curriculum(corpus, out, client, work, max_chars=80, overlap=10)
            self.assertEqual(client.map_calls, first)

    def test_failing_chunk_is_skipped_not_fatal(self):
        class RaisingClient:
            def generate_json(self, prompt):
                if "curriculum concept names" in prompt:
                    return {"missing": [], "notes": []}
                raise ValueError("bad json from model")
        with tempfile.TemporaryDirectory() as corpus, tempfile.TemporaryDirectory() as work, \
             tempfile.TemporaryDirectory() as out:
            Path(corpus, "01.md").write_text("CHAPTER SIX\n" + "x" * 200)
            build_curriculum(corpus, out, RaisingClient(), work, max_chars=80, overlap=10)
            data = json.loads(Path(out, "curriculum.json").read_text())
            self.assertEqual(data, [])

if __name__ == "__main__":
    unittest.main()
