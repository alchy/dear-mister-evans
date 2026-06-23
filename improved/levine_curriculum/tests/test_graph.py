import unittest
from improved.levine_curriculum.graph import merge_concepts, order_concepts

def node(id, name, summary="", prereq=None, kw=None, refs=None):
    return {"id": id, "name": name, "summary": summary, "level": "review",
            "prerequisites": prereq or [], "keywords": kw or [],
            "source_refs": refs or [], "practice": []}

class TestGraph(unittest.TestCase):
    def test_merge_unions_prereqs_keywords_refs_and_keeps_longer_summary(self):
        a = [node("x", "X", "short", ["a"], ["k1"], [{"chapter": "C1", "pages": ""}])]
        b = [node("x", "X", "a longer summary", ["b"], ["k2"], [{"chapter": "C2", "pages": ""}])]
        out = merge_concepts([a, b])
        self.assertEqual(len(out), 1)
        m = out[0]
        self.assertEqual(m["summary"], "a longer summary")
        self.assertEqual(sorted(m["prerequisites"]), ["a", "b"])
        self.assertEqual(sorted(m["keywords"]), ["k1", "k2"])
        self.assertEqual(len(m["source_refs"]), 2)

    def test_order_puts_prerequisites_first(self):
        c = [node("a", "A", prereq=["b"]), node("b", "B")]
        out = [n["id"] for n in order_concepts(c)]
        self.assertLess(out.index("b"), out.index("a"))

    def test_order_survives_cycle(self):
        c = [node("a", "A", prereq=["b"]), node("b", "B", prereq=["a"])]
        out = [n["id"] for n in order_concepts(c)]
        self.assertEqual(sorted(out), ["a", "b"])

    def test_merge_fuzzy_collapses_plural_and_remaps_prereqs(self):
        a = [node("tritone-substitution", "Tritone Substitution", "s1")]
        b = [node("tritone-substitutions", "Tritone Substitutions", "s2 longer")]
        dep = [node("altered-dominant", "Altered Dominant", prereq=["tritone-substitutions"])]
        out = merge_concepts([a, b, dep])
        ids = {c["id"] for c in out}
        self.assertIn("tritone-substitution", ids)
        self.assertNotIn("tritone-substitutions", ids)            # plural sloučen
        self.assertEqual(sum(1 for c in out if "tritone" in c["id"]), 1)
        depc = next(c for c in out if c["id"] == "altered-dominant")
        self.assertEqual(depc["prerequisites"], ["tritone-substitution"])  # prereq přemapován

if __name__ == "__main__":
    unittest.main()
