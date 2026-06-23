import unittest, tempfile, json
from pathlib import Path
from improved.levine_curriculum.output import write_curriculum

def node(id, name):
    return {"id": id, "name": name, "summary": "S", "level": "beginner",
            "prerequisites": [], "keywords": [], "source_refs": [{"chapter": "C1", "pages": "p.1"}],
            "practice": []}

class TestOutput(unittest.TestCase):
    def test_writes_json_and_md(self):
        with tempfile.TemporaryDirectory() as d:
            write_curriculum([node("x", "X Concept")], d, {"missing": ["Y"], "notes": []})
            data = json.loads(Path(d, "curriculum.json").read_text())
            self.assertEqual(data[0]["id"], "x")
            self.assertIn("X Concept", Path(d, "curriculum.md").read_text())
            self.assertIn("Y", Path(d, "critic_report.md").read_text())

if __name__ == "__main__":
    unittest.main()
