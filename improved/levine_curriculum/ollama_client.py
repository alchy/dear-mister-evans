"""ollama_client -- tenký HTTP klient na lokální Ollama (stdlib urllib)."""
import json
import urllib.request


class OllamaClient:
    def __init__(self, model, num_ctx=8192, host="http://localhost:11434"):
        self.model = model
        self.num_ctx = num_ctx
        self.host = host

    def _http_json(self, path, body=None):
        url = self.host + path
        if body is None:
            req = urllib.request.Request(url)
        else:
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)

    def available(self):
        try:
            tags = self._http_json("/api/tags")
        except Exception:
            return False
        names = [m.get("name", "") for m in tags.get("models", [])]
        return any(n == self.model or n.startswith(self.model) for n in names)

    def generate_json(self, prompt):
        resp = self._http_json("/api/generate", {
            "model": self.model, "prompt": prompt, "format": "json",
            "stream": False, "options": {"num_ctx": self.num_ctx}})
        return json.loads(resp["response"])
