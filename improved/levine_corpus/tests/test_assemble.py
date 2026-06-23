# improved/levine_corpus/tests/test_assemble.py
import unittest
from improved.levine_corpus.assemble import assemble

class TestAssemble(unittest.TestCase):
    def test_inserts_markers_and_orders(self):
        out = assemble([(1, 1, "first"), (2, 2, "second")])
        self.assertIn("<!-- p.1 -->", out)
        self.assertIn("<!-- p.2 -->", out)
        self.assertLess(out.index("first"), out.index("second"))

    def test_range_marker_for_multipage_batch(self):
        out = assemble([(1, 40, "blob")])
        self.assertIn("<!-- p.1 -->", out)

if __name__ == "__main__":
    unittest.main()
