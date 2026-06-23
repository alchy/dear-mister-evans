# Levine Curriculum (lokální Ollama extrakce) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Z OCR korpusu Levinovy knihy vyrobit strukturovanou výukovou osnovu (graf konceptů, `curriculum.json` + `.md`) lokální extrakcí přes Ollama; Claude jen orchestruje.

**Architecture:** Deterministický Python orchestrátor chunkuje korpus do malých překrývajících oken, lokální Ollama model per okno extrahuje koncepty (vlastními slovy), pak deterministický dedup + topologické řazení + critic pass → graf. Model nikdy nedostane víc než jedno okno (malý kontext). Žádné Claude kredity na objem.

**Tech Stack:** Python 3.11 (`.venv`), stdlib `unittest`, stdlib `urllib` (HTTP na Ollama), lokální Ollama (`qwen3.6:27b-mlx` / `gemma4`).

## Global Constraints

- Balík kódu: `improved/levine_curriculum/`. Testy: `improved/levine_curriculum/tests/` (`unittest`).
- **Veškerá jazyková práce běží přes lokální Ollama.** Kód NEsmí volat Claude/žádné placené API. Orchestrace + skládání jsou deterministické.
- **Stdlib only** (žádné nové pip závislosti; HTTP přes `urllib`).
- Vstup (korpus): `~/OneDrive/Jazz Learning/Levine Corpus/` (.md z OCR pipeline).
- Výstup osnovy: `~/OneDrive/Jazz Learning/Levine Corpus/curriculum/`; cache map výstupů: `.../Levine Corpus/_work/map_cache/`. Obojí je už **gitignorováno** (`**/Levine Corpus/**`, `**/_work/**`) — text/osnova se nikdy nedostanou do gitu.
- **Schéma uzlu konceptu (přesně 8 klíčů):** `id, name, summary, level, prerequisites, keywords, source_refs, practice`.
- Osnova = **původní formulace** (prompt instruuje model „use your own words"); není to text knihy. Testy používají **výhradně syntetická data + FakeClient**, nikdy obsah knihy.
- Platforma macOS / Apple Silicon (M4 Pro, 24 GB). Testy: z kořene repa `PYTHONPATH=.:improved .venv/bin/python -m unittest ...`.
- Každý commit končí trailerem `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: concept.py — schéma + slugify

**Files:**
- Create: `improved/levine_curriculum/__init__.py`, `improved/levine_curriculum/concept.py`, `improved/levine_curriculum/tests/__init__.py`
- Test: `improved/levine_curriculum/tests/test_concept.py`

**Interfaces:**
- Produces: `CONCEPT_KEYS: list[str]`; `slugify(name: str) -> str`; `blank_concept(name: str, **kw) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_curriculum/tests/test_concept.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_concept -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_curriculum.concept'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_curriculum/__init__.py
"""levine_curriculum -- lokální Ollama extrakce výukové osnovy z Levinova korpusu."""
```
```python
# improved/levine_curriculum/tests/__init__.py
```
```python
# improved/levine_curriculum/concept.py
"""concept -- schéma uzlu osnovy + pomocníci (slugify, blank_concept)."""
import re

CONCEPT_KEYS = ["id", "name", "summary", "level", "prerequisites",
                "keywords", "source_refs", "practice"]


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "concept"


def blank_concept(name, **kw):
    c = {"id": slugify(name), "name": name, "summary": "", "level": "review",
         "prerequisites": [], "keywords": [], "source_refs": [], "practice": []}
    for k, v in kw.items():
        if k in CONCEPT_KEYS:
            c[k] = v
    return c
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_concept -v`
Expected: PASS (4 testy)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_curriculum/__init__.py improved/levine_curriculum/concept.py improved/levine_curriculum/tests/__init__.py improved/levine_curriculum/tests/test_concept.py
git commit -m "feat(curriculum): schéma uzlu + slugify (TDD)"
```

---

### Task 2: chunk.py — malá překrývající okna se source_ref

**Files:**
- Create: `improved/levine_curriculum/chunk.py`
- Test: `improved/levine_curriculum/tests/test_chunk.py`

**Interfaces:**
- Produces: `Chunk = namedtuple("Chunk", "text chapter pages")`; `chunk_corpus(corpus_dir, max_chars=4000, overlap=400) -> list[Chunk]`

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_curriculum/tests/test_chunk.py
import unittest, tempfile
from pathlib import Path
from improved.levine_curriculum.chunk import chunk_corpus, Chunk

class TestChunk(unittest.TestCase):
    def _corpus(self, d, text):
        Path(d, "01.md").write_text(text)

    def test_small_windows_cover_text_with_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, "A" * 50)
            chunks = chunk_corpus(d, max_chars=20, overlap=5)
            self.assertGreaterEqual(len(chunks), 3)
            self.assertTrue(all(isinstance(c, Chunk) for c in chunks))
            self.assertTrue(all(len(c.text) <= 20 for c in chunks))

    def test_attaches_chapter_and_pages(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, "CHAPTER SIX\n<!-- p.84 -->\nsome text here <!-- p.85 -->")
            chunks = chunk_corpus(d, max_chars=4000, overlap=100)
            self.assertEqual(chunks[0].chapter, "CHAPTER SIX")
            self.assertEqual(chunks[0].pages, "p.84-85")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_chunk -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_curriculum.chunk'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_curriculum/chunk.py
"""chunk -- korpus -> malá překrývající okna s kapitolou/stranami (source_ref)."""
import re
from collections import namedtuple
from pathlib import Path

Chunk = namedtuple("Chunk", "text chapter pages")
PAGE = re.compile(r"<!-- p\.(\d+) -->")
CHAP = re.compile(r"(?mi)^[ \t]*(CHAPTER[ \t]+[A-Z][A-Z-]+|INTRODUCTION|APP?ENDIX)[ \t]*$")


def _read_corpus(corpus_dir):
    return "\n".join(p.read_text(errors="ignore") for p in sorted(Path(corpus_dir).glob("*.md")))


def chunk_corpus(corpus_dir, max_chars=4000, overlap=400):
    """-> [Chunk(text, chapter, pages)]; okna max_chars s překryvem, kapitola = poslední
    nadpis při/před koncem okna, pages = rozsah page markerů v okně."""
    text = _read_corpus(corpus_dir)
    chunks = []
    n = len(text)
    i = 0
    step = max(1, max_chars - overlap)
    while i < n:
        window = text[i:i + max_chars]
        heads = CHAP.findall(text[:i + max_chars])
        chapter = re.sub(r"\s+", " ", heads[-1]).strip() if heads else "UNKNOWN"
        pgs = PAGE.findall(window)
        pages = f"p.{pgs[0]}-{pgs[-1]}" if pgs else ""
        chunks.append(Chunk(window, chapter, pages))
        if i + max_chars >= n:
            break
        i += step
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_chunk -v`
Expected: PASS (2 testy)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_curriculum/chunk.py improved/levine_curriculum/tests/test_chunk.py
git commit -m "feat(curriculum): chunking na malá překrývající okna se source_ref (TDD)"
```

---

### Task 3: ollama_client.py — HTTP klient (stdlib)

**Files:**
- Create: `improved/levine_curriculum/ollama_client.py`
- Test: `improved/levine_curriculum/tests/test_ollama_client.py`

**Interfaces:**
- Produces: `OllamaClient(model, num_ctx=8192, host="http://localhost:11434")` s `available() -> bool`, `generate_json(prompt: str) -> dict`, a seamem `_http_json(path, body=None) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_curriculum/tests/test_ollama_client.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_ollama_client -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_curriculum.ollama_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_curriculum/ollama_client.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_ollama_client -v`
Expected: PASS (3 testy)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_curriculum/ollama_client.py improved/levine_curriculum/tests/test_ollama_client.py
git commit -m "feat(curriculum): Ollama HTTP klient (stdlib, TDD)"
```

---

### Task 4: extract.py — MAP (koncepty z okna)

**Files:**
- Create: `improved/levine_curriculum/extract.py`
- Test: `improved/levine_curriculum/tests/test_extract.py`

**Interfaces:**
- Consumes: `Chunk` (Task 2), `slugify` (Task 1), klient s `.generate_json(prompt)->dict`.
- Produces: `MAP_PROMPT: str`; `extract_concepts(chunk, client) -> list[dict]` (uzly dle schématu, `source_refs` z chunku).

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_curriculum/tests/test_extract.py
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

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_extract -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_curriculum.extract'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_curriculum/extract.py
"""extract -- MAP krok: z jednoho okna textu vytáhne koncepty (Ollama, vlastní slova)."""
from .concept import slugify

MAP_PROMPT = (
    "You are building a jazz-piano learning curriculum. From the passage below, "
    "list the distinct musical CONCEPTS a student should learn. Use your OWN words; "
    "do NOT copy sentences from the text. For each concept give a short summary "
    "(1-3 sentences), a difficulty level (beginner|intermediate|advanced), the names "
    "of prerequisite concepts, and a few keywords. Return strict JSON: "
    '{"concepts":[{"name":...,"summary":...,"level":...,"prerequisites":[...],"keywords":[...]}]}.'
    "\n\nPASSAGE:\n%s"
)


def extract_concepts(chunk, client):
    """-> list uzlů dle schématu; source_refs převzaty z chunku."""
    data = client.generate_json(MAP_PROMPT % chunk.text)
    out = []
    for c in data.get("concepts", []):
        name = (c.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "id": slugify(name),
            "name": name,
            "summary": (c.get("summary") or "").strip(),
            "level": (c.get("level") or "review"),
            "prerequisites": [slugify(p) for p in c.get("prerequisites", []) if (p or "").strip()],
            "keywords": [k for k in c.get("keywords", []) if (k or "").strip()],
            "source_refs": [{"chapter": chunk.chapter, "pages": chunk.pages}],
            "practice": [],
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_extract -v`
Expected: PASS (2 testy)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_curriculum/extract.py improved/levine_curriculum/tests/test_extract.py
git commit -m "feat(curriculum): MAP extrakce konceptů z okna (TDD)"
```

---

### Task 5: graph.py — merge (dedup) + order (topo)

**Files:**
- Create: `improved/levine_curriculum/graph.py`
- Test: `improved/levine_curriculum/tests/test_graph.py`

**Interfaces:**
- Produces: `merge_concepts(per_chunk: list[list[dict]]) -> list[dict]`; `order_concepts(concepts: list[dict]) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_curriculum/tests/test_graph.py
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

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_graph -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_curriculum.graph'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_curriculum/graph.py
"""graph -- deterministické sloučení konceptů (dedup) + topologické řazení."""


def merge_concepts(per_chunk):
    """Sloučí uzly se stejným id napříč okny: union prereq/keywords/source_refs,
    delší summary vyhrává. -> list uzlů (pořadí prvního výskytu)."""
    by_id = {}
    order = []
    for lst in per_chunk:
        for c in lst:
            cur = by_id.get(c["id"])
            if cur is None:
                by_id[c["id"]] = {**c,
                                  "prerequisites": list(c["prerequisites"]),
                                  "keywords": list(c["keywords"]),
                                  "source_refs": list(c["source_refs"])}
                order.append(c["id"])
            else:
                cur["prerequisites"] = sorted(set(cur["prerequisites"]) | set(c["prerequisites"]))
                cur["keywords"] = sorted(set(cur["keywords"]) | set(c["keywords"]))
                for s in c["source_refs"]:
                    if s not in cur["source_refs"]:
                        cur["source_refs"].append(s)
                if len(c["summary"]) > len(cur["summary"]):
                    cur["summary"] = c["summary"]
    return [by_id[i] for i in order]


def order_concepts(concepts):
    """Topologické řazení dle prerekvizit (prereq před závislým). Cykly přeruší
    (back-edge se ignoruje), takže vždy vrátí všechny uzly. Stabilní vůči vstupu."""
    cmap = {c["id"]: c for c in concepts}
    ids = set(cmap)
    deps = {c["id"]: [p for p in c["prerequisites"] if p in ids and p != c["id"]] for c in concepts}
    state = {i: 0 for i in ids}     # 0 unvisited, 1 in-progress, 2 done
    result = []

    def visit(i):
        if state[i] != 0:
            return                  # done nebo in-progress (cyklus) -> přeskoč
        state[i] = 1
        for p in deps[i]:
            visit(p)
        state[i] = 2
        result.append(cmap[i])

    for c in concepts:              # stabilní pořadí vstupu
        visit(c["id"])
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_graph -v`
Expected: PASS (3 testy)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_curriculum/graph.py improved/levine_curriculum/tests/test_graph.py
git commit -m "feat(curriculum): dedup + topologické řazení konceptů (TDD)"
```

---

### Task 6: critic.py — kontrolní pass (report)

**Files:**
- Create: `improved/levine_curriculum/critic.py`
- Test: `improved/levine_curriculum/tests/test_critic.py`

**Interfaces:**
- Consumes: klient s `.generate_json(prompt)->dict`.
- Produces: `CRITIC_PROMPT: str`; `critique(concepts: list[dict], client, batch=80) -> dict` (`{"missing": [str], "notes": [str]}`).

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_curriculum/tests/test_critic.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_critic -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_curriculum.critic'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_curriculum/critic.py
"""critic -- kontrolní pass nad KOMPAKTNÍM seznamem konceptů (po dávkách).
Vrací report (chybějící koncepty + poznámky) pro spot-check; graf NEmutuje."""

CRITIC_PROMPT = (
    "Below is a list of jazz-piano curriculum concept names. As a jazz educator, "
    "identify (a) important concepts that are MISSING from this list, and (b) brief "
    "notes on anything clearly out of order. Use your own words. Return strict JSON: "
    '{"missing":[names], "notes":[strings]}.\n\nCONCEPTS:\n%s'
)


def critique(concepts, client, batch=80):
    names = [c["name"] for c in concepts]
    missing, notes = [], []
    for i in range(0, len(names), batch):
        data = client.generate_json(CRITIC_PROMPT % "\n".join(names[i:i + batch]))
        missing += [m for m in data.get("missing", []) if (m or "").strip()]
        notes += [n for n in data.get("notes", []) if (n or "").strip()]
    seen = set()
    uniq_missing = [m for m in missing if not (m in seen or seen.add(m))]
    return {"missing": uniq_missing, "notes": notes}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_critic -v`
Expected: PASS (2 testy)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_curriculum/critic.py improved/levine_curriculum/tests/test_critic.py
git commit -m "feat(curriculum): critic pass -> report (TDD)"
```

---

### Task 7: output.py — zápis curriculum.json + .md + critic_report.md

**Files:**
- Create: `improved/levine_curriculum/output.py`
- Test: `improved/levine_curriculum/tests/test_output.py`

**Interfaces:**
- Produces: `write_curriculum(concepts: list[dict], out_dir, critic_report=None) -> pathlib.Path`.

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_curriculum/tests/test_output.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_output -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_curriculum.output'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_curriculum/output.py
"""output -- zápis osnovy: curriculum.json (graf) + curriculum.md + critic_report.md."""
import json
from pathlib import Path


def write_curriculum(concepts, out_dir, critic_report=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "curriculum.json").write_text(json.dumps(concepts, ensure_ascii=False, indent=2))
    lines = ["# Výuková osnova (auto-extrakce z Levina — vlastní formulace)\n"]
    for c in concepts:
        prereq = ", ".join(c["prerequisites"]) or "—"
        src = "; ".join(f"{s['chapter']} {s['pages']}".strip() for s in c["source_refs"]) or "—"
        lines.append(f"### {c['name']} · {c['level']}\n{c['summary']}\n"
                     f"- Prerekvizity: {prereq}\n- Zdroj: {src}\n- Cvičení: (zatím nenamapováno)\n")
    (out / "curriculum.md").write_text("\n".join(lines))
    if critic_report is not None:
        rep = ["# Critic report\n", "## Možné chybějící koncepty"]
        rep += [f"- {m}" for m in critic_report.get("missing", [])] or ["(žádné)"]
        rep += ["\n## Poznámky"]
        rep += [f"- {n}" for n in critic_report.get("notes", [])] or ["(žádné)"]
        (out / "critic_report.md").write_text("\n".join(rep))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_output -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_curriculum/output.py improved/levine_curriculum/tests/test_output.py
git commit -m "feat(curriculum): zápis curriculum.json/.md + critic report (TDD)"
```

---

### Task 8: build.py — orchestrace (cache, resumable) + CLI

**Files:**
- Create: `improved/levine_curriculum/build.py`
- Test: `improved/levine_curriculum/tests/test_build.py`

**Interfaces:**
- Consumes: `chunk_corpus` (T2), `extract_concepts` (T4), `merge_concepts`/`order_concepts` (T5), `critique` (T6), `write_curriculum` (T7), `OllamaClient` (T3).
- Produces: `build_curriculum(corpus_dir, out_dir, client, work_dir, max_chars=4000, overlap=400, run_critic=True) -> pathlib.Path`.

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_curriculum/tests/test_build.py
import unittest, tempfile, json
from pathlib import Path
from improved.levine_curriculum.build import build_curriculum

class FakeClient:
    """MAP prompt -> koncepty; CRITIC prompt -> report. Počítá MAP volání."""
    def __init__(self): self.map_calls = 0
    def generate_json(self, prompt):
        if "MISSING" in prompt or "curriculum concept names" in prompt:
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
            # resumable: druhý běh nevolá MAP znovu
            build_curriculum(corpus, out, client, work, max_chars=80, overlap=10)
            self.assertEqual(client.map_calls, first)

    def test_failing_chunk_is_skipped_not_fatal(self):
        class RaisingClient:
            def generate_json(self, prompt):
                if "curriculum concept names" in prompt:   # critic
                    return {"missing": [], "notes": []}
                raise ValueError("bad json from model")
        with tempfile.TemporaryDirectory() as corpus, tempfile.TemporaryDirectory() as work, \
             tempfile.TemporaryDirectory() as out:
            Path(corpus, "01.md").write_text("CHAPTER SIX\n" + "x" * 200)
            build_curriculum(corpus, out, RaisingClient(), work, max_chars=80, overlap=10)
            data = json.loads(Path(out, "curriculum.json").read_text())
            self.assertEqual(data, [])   # vše přeskočeno, ale běh doběhl a zapsal výstup

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_build -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_curriculum.build'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_curriculum/build.py
"""build -- orchestrace osnovy: chunk -> MAP(cache) -> merge -> order -> critic -> zápis. + CLI."""
import json
import hashlib
from pathlib import Path
from .chunk import chunk_corpus
from .extract import extract_concepts
from .graph import merge_concepts, order_concepts
from .critic import critique
from .output import write_curriculum


def build_curriculum(corpus_dir, out_dir, client, work_dir,
                     max_chars=4000, overlap=400, run_critic=True):
    """Celá pipeline. MAP výstupy se cachují per okno (resumable). -> Path(out_dir)."""
    cache = Path(work_dir) / "map_cache"
    cache.mkdir(parents=True, exist_ok=True)
    chunks = chunk_corpus(corpus_dir, max_chars, overlap)
    per_chunk = []
    for idx, ch in enumerate(chunks):
        key = hashlib.sha1(ch.text.encode("utf-8")).hexdigest()[:16]
        cf = cache / f"chunk-{idx:04d}-{key}.json"
        if cf.exists():
            per_chunk.append(json.loads(cf.read_text()))
        else:
            concepts = []
            for attempt in (1, 2):                 # spec §9: 1 retry, pak skip s logem
                try:
                    concepts = extract_concepts(ch, client)
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"  [skip] okno {idx} ({ch.chapter} {ch.pages}): {type(e).__name__}: {e}")
            cf.write_text(json.dumps(concepts, ensure_ascii=False))
            per_chunk.append(concepts)
    merged = order_concepts(merge_concepts(per_chunk))
    report = critique(merged, client) if run_critic else None
    return write_curriculum(merged, out_dir, report)


def main():
    import argparse
    from .ollama_client import OllamaClient
    ap = argparse.ArgumentParser(description="Levine korpus -> výuková osnova (lokální Ollama)")
    ap.add_argument("corpus_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--work", required=True)
    ap.add_argument("--model", default="qwen3.6:27b-mlx")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--max-chars", type=int, default=4000)
    ap.add_argument("--overlap", type=int, default=400)
    ap.add_argument("--no-critic", action="store_true")
    a = ap.parse_args()
    client = OllamaClient(a.model, num_ctx=a.num_ctx)
    if not client.available():
        raise SystemExit(f"Ollama model '{a.model}' není dostupný (běží server? `ollama list`?)")
    out = build_curriculum(a.corpus_dir, a.out_dir, client, a.work,
                           max_chars=a.max_chars, overlap=a.overlap, run_critic=not a.no_critic)
    print(f"hotovo -> {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_curriculum.tests.test_build -v`
Expected: PASS (1 test)

- [ ] **Step 5: Celý balík + commit**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest discover -s improved/levine_curriculum/tests -v`
Expected: PASS (všechny testy balíku)

```bash
git add improved/levine_curriculum/build.py improved/levine_curriculum/tests/test_build.py
git commit -m "feat(curriculum): orchestrace build_curriculum + cache + CLI (TDD)"
```

---

### Task 9: A/B test modelu na 1 kapitole + výběr defaultu + (volitelně) plný běh

**Files:**
- (žádná produkční změna kódu; operační task — ověření gitignore + běh)

**Interfaces:**
- Consumes: CLI z Tasku 8, korpus z OCR pipeline, lokální Ollama.

- [ ] **Step 1: Ověř, že výstup je gitignorovaný**

Run:
```bash
cd /Users/j/Projects/dear-mister-evans
git check-ignore -v "Levine Corpus/curriculum/curriculum.json" >/dev/null 2>&1 && echo "OK ignorováno (přes **/Levine Corpus/**)" || echo "POZOR: výstup mimo repo, ale zkontroluj pravidla"
git status --short
```
Expected: `git status` neukazuje žádné soubory osnovy (výstup je v OneDrive, mimo repo).

- [ ] **Step 2: A/B test qwen vs gemma na 1 kapitole**

Připrav vstup = 1 kapitola korpusu (např. zkopíruj `06-*.md` do dočasné složky), spusť build s oběma modely do oddělených out/work a změř čas + počet konceptů:
```bash
cd /Users/j/Projects/dear-mister-evans
SRC="/Users/j/OneDrive/Jazz Learning/Levine Corpus"
mkdir -p /tmp/levine_ab/in && cp "$SRC"/06-*.md /tmp/levine_ab/in/ 2>/dev/null || cp "$(ls "$SRC"/*.md | sed -n '6p')" /tmp/levine_ab/in/
for M in qwen3.6:27b-mlx gemma4:latest; do
  echo "=== $M ==="; time PYTHONPATH=.:improved .venv/bin/python -m improved.levine_curriculum.build \
    /tmp/levine_ab/in "/tmp/levine_ab/out_${M//[:.]/_}" --work "/tmp/levine_ab/work_${M//[:.]/_}" \
    --model "$M" --num-ctx 8192 --max-chars 4000 --overlap 400 --no-critic
  echo "konceptů: $(python3 -c "import json;print(len(json.load(open('/tmp/levine_ab/out_${M//[:.]/_}/curriculum.json'))))")"
done
```
Expected: oba doběhnou; porovnej počet/kvalitu konceptů a čas.

- [ ] **Step 3: Spot-check kvality + výběr defaultu**

Otevři oba `curriculum.md`, posuď: dávají koncepty smysl, jsou vlastními slovy (ne citace), rozumné prerekvizity. Vyber lepší model; pokud se liší od `--model` defaultu v `build.py`, uprav default (jednořádková změna + commit).

- [ ] **Step 4: (volitelně) Plný běh na celém korpusu**

Run (zvoleným modelem; ~delší, lze na pozadí):
```bash
cd /Users/j/Projects/dear-mister-evans
PYTHONPATH=.:improved .venv/bin/python -m improved.levine_curriculum.build \
  "/Users/j/OneDrive/Jazz Learning/Levine Corpus" \
  "/Users/j/OneDrive/Jazz Learning/Levine Corpus/curriculum" \
  --work "/Users/j/OneDrive/Jazz Learning/Levine Corpus/_work" --model <zvolený>
```
Expected: `hotovo -> .../curriculum`; zkontroluj `curriculum.md` + `critic_report.md`.

- [ ] **Step 5: Žádný commit obsahu** — osnova je v OneDrive a gitignored. Hotovo.

---

## Self-Review

**Spec coverage:**
- §4 architektura chunk→MAP→reduce→order→critic→output → Tasks 2,4,5,5,6,7; orchestrace T8. ✓
- §5 komponenty: chunk_corpus (T2), OllamaClient (T3), extract_concepts (T4), merge/order (T5), critique (T6), write_curriculum (T7), build_curriculum (T8). ✓
- §6 schéma uzlu (8 klíčů) → concept.py (T1) + použito v extract/merge/output. ✓
- §7 model qwen/gemma A/B → Task 9. ✓
- §8 IP/úložiště (kód v repu, výstup v OneDrive gitignored, vlastní formulace) → Global Constraints + T9 ověření + MAP_PROMPT „use your own words". ✓
- §9 kvalita: critic (T6) + cache/resumable (T8) + nevalidní JSON (OllamaClient vyhodí, build by měl logovat — viz pozn.) + spot-check (T9). ✓
- §10 testování: synteticky + FakeClient (T1-T8). ✓
- Mimo rozsah (practice mapping, UI) → nezahrnuto. ✓

**Placeholder scan:** Tasky 1-8 mají kompletní kód a příkazy. Task 9 je operační (běh + rozhodnutí), kroky konkrétní.

**Type consistency:** uzel = dict s 8 klíči konzistentně (concept/extract/merge/output). `client.generate_json(prompt)->dict` shodně v extract/critic/build a OllamaClient. `chunk_corpus(...)->[Chunk]`, Chunk(text,chapter,pages) shodně v chunk/extract/build. `build_curriculum(corpus,out,client,work,...)` shodně T8/T9.

**Spec §9 (nevalidní JSON) — pokryto:** `build_curriculum` MAP smyčka má 1 retry + skip s logem (prázdný seznam do cache), test `test_failing_chunk_is_skipped_not_fatal` ověřuje, že selhání okna neshodí běh.
