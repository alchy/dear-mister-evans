import unittest
from unittest import mock
from improved.levine_curriculum.ollama_client import OllamaClient

class TestOllamaClient(unittest.TestCase):
    def test_available_true_when_model_present(self):
        c = OllamaClient("gemma4")
        with mock.patch.object(c, "_http_json", return_value={"models": [{"name": "gemma4:latest"}]}):
            self.assertTrue(c.available())

    def test_available_false_on_error(self):
        c = OllamaClient("gemma4")
        with mock.patch.object(c, "_http_json", side_effect=OSError("down")):
            self.assertFalse(c.available())

    def test_generate_json_parses_response_field(self):
        c = OllamaClient("gemma4")
        with mock.patch.object(c, "_http_json", return_value={"response": '{"concepts": []}'}):
            self.assertEqual(c.generate_json("hi"), {"concepts": []})

if __name__ == "__main__":
    unittest.main()
