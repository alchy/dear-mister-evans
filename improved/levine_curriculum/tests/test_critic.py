import unittest
from improved.levine_curriculum.critic import critique

class FakeClient:
    def __init__(self, payload): self.payload = payload; self.calls = 0
    def generate_json(self, prompt): self.calls += 1; return self.payload

def node(id, name): return {"id": id, "name": name}

class TestCritic(unittest.TestCase):
    def test_collects_missing_and_notes(self):
        client = FakeClient({"missing": ["Modal Interchange", ""], "notes": ["check order"]})
        rep = critique([node("a", "A")], client)
        self.assertEqual(rep["missing"], ["Modal Interchange"])
        self.assertEqual(rep["notes"], ["check order"])

    def test_batches_long_lists(self):
        client = FakeClient({"missing": [], "notes": []})
        critique([node(f"n{i}", f"N{i}") for i in range(170)], client, batch=80)
        self.assertEqual(client.calls, 3)

if __name__ == "__main__":
    unittest.main()
