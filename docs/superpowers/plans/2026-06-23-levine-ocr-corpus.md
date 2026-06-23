# Levine OCR Corpus — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Z naskenované Levinovy *The Jazz Piano Book* vyrobit čistý textový korpus (markdown po kapitolách) jako podklad pro učící nástroj.

**Architecture:** Pipeline s odděleným, vyměnitelným OCR krokem: `render_pages` → `OcrEngine.ocr_batch` (Tesseract baseline / Baidu po spike) → `assemble` (page markery) → `clean` → `segment_chapters` → markdown soubory. Engine je za rozhraním, takže jde vyměnit bez zásahu do zbytku. Backbone (render, čištění, segmentace, driver) je plně TDD nad syntetickými daty; reálnou OCR kvalitu ověřuje spike.

**Tech Stack:** Python 3.11 (projektový `.venv`), stdlib `unittest`, poppler (`pdftoppm`), Tesseract (`brew install tesseract`), volitelně Baidu Unlimited-OCR (HF Transformers / Ollama — rozhodne spike).

## Global Constraints

- Balík kódu: `improved/levine_corpus/`. Testy: `improved/levine_corpus/tests/` (`unittest`).
- **OCR výstup (text knihy) ani modelové váhy NIKDY do gitu.** Commituje se jen kód. Task 8 přidá `.gitignore` ochranu.
- Finální korpus → `~/OneDrive/Jazz Learning/Levine Corpus/` (mimo repo).
- Pracovní/cache adresář → `~/OneDrive/Jazz Learning/Levine Corpus/_work/` (mimo repo, gitignored).
- Zdroj (ověřeno): `~/OneDrive/Jazz Learning/The Jazz Piano Book - PDF Room.pdf`, 316 stran, sken 300 dpi bitonal, bez textové vrstvy.
- **Text-only.** Notový zápis se neřeší (žádné OMR).
- Testy používají **výhradně syntetický text**, nikdy obsah knihy.
- Platforma macOS / Apple Silicon. Minimum nových pip závislostí (stdlib + CLI nástroje).
- Každý commit končí trailerem `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Spouštění testů z kořene repa s `PYTHONPATH=.:improved` a aktivním `.venv`.

---

### Task 1: Render stran PDF na obrázky

**Files:**
- Create: `improved/levine_corpus/__init__.py`
- Create: `improved/levine_corpus/render.py`
- Create: `improved/levine_corpus/tests/__init__.py`
- Test: `improved/levine_corpus/tests/test_render.py`

**Interfaces:**
- Produces: `_pdftoppm_cmd(pdf_path: str, out_prefix: str, dpi: int, first: int|None, last: int|None) -> list[str]`; `render_pages(pdf_path, out_dir, dpi=300, first=None, last=None, force=False) -> list[pathlib.Path]`

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_corpus/tests/test_render.py
import unittest
from improved.levine_corpus.render import _pdftoppm_cmd

class TestPdftoppmCmd(unittest.TestCase):
    def test_full_range(self):
        cmd = _pdftoppm_cmd("book.pdf", "/out/page", 300, None, None)
        self.assertEqual(cmd, ["pdftoppm", "-png", "-gray", "-r", "300", "book.pdf", "/out/page"])

    def test_page_range(self):
        cmd = _pdftoppm_cmd("book.pdf", "/out/page", 300, 1, 5)
        self.assertIn("-f", cmd); self.assertIn("1", cmd)
        self.assertIn("-l", cmd); self.assertIn("5", cmd)
        self.assertEqual(cmd[-2:], ["book.pdf", "/out/page"])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_render -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_corpus.render'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_corpus/__init__.py
"""levine_corpus -- OCR pipeline z Levinovy Jazz Piano Book na textový korpus."""
```

```python
# improved/levine_corpus/tests/__init__.py
```

```python
# improved/levine_corpus/render.py
"""render -- stránky PDF -> PNG přes poppler pdftoppm (idempotentní)."""
import subprocess
from pathlib import Path


def _pdftoppm_cmd(pdf_path, out_prefix, dpi, first, last):
    """Sestaví argv pro pdftoppm. Pure (testovatelné bez subprocesu)."""
    cmd = ["pdftoppm", "-png", "-gray", "-r", str(dpi)]
    if first is not None:
        cmd += ["-f", str(first)]
    if last is not None:
        cmd += ["-l", str(last)]
    cmd += [str(pdf_path), str(out_prefix)]
    return cmd


def render_pages(pdf_path, out_dir, dpi=300, first=None, last=None, force=False):
    """PDF -> page-NNN.png v out_dir. Idempotentní: pokud už PNG existují a ne force,
    jen je vrátí. -> seřazený list Path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    existing = sorted(out.glob("page-*.png"))
    if existing and not force:
        return existing
    cmd = _pdftoppm_cmd(pdf_path, out / "page", dpi, first, last)
    subprocess.run(cmd, check=True)
    return sorted(out.glob("page-*.png"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_render -v`
Expected: PASS (2 testy)

- [ ] **Step 5: Integration ověření na reálném PDF (5 stran) + commit**

Run (ověř, že vznikne 5 PNG; výstup je gitignored adresář):
```bash
cd /Users/j/Projects/dear-mister-evans
PYTHONPATH=.:improved .venv/bin/python -c "
from improved.levine_corpus.render import render_pages
p=render_pages('/Users/j/OneDrive/Jazz Learning/The Jazz Piano Book - PDF Room.pdf',
               '/Users/j/OneDrive/Jazz Learning/Levine Corpus/_work/pages_sample', first=40, last=44)
print('stránek:', len(p)); print(p[0].name if p else 'NIC')"
```
Expected: `stránek: 5`

```bash
git add improved/levine_corpus/__init__.py improved/levine_corpus/render.py improved/levine_corpus/tests/__init__.py improved/levine_corpus/tests/test_render.py
git commit -m "feat(levine): render stran PDF na PNG (poppler pdftoppm)"
```

---

### Task 2: OCR engine — rozhraní + Tesseract baseline

**Files:**
- Create: `improved/levine_corpus/engine.py`
- Test: `improved/levine_corpus/tests/test_engine.py`

**Interfaces:**
- Consumes: `pathlib.Path` (cesty k obrázkům z Tasku 1).
- Produces: `class OcrEngine` s atributem `max_pages: int` a metodami `available() -> bool`, `ocr_batch(image_paths: list[Path]) -> str`; `class TesseractEngine(OcrEngine)` (`max_pages = 1`, `__init__(self, lang="eng")`).

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_corpus/tests/test_engine.py
import unittest
from unittest import mock
from improved.levine_corpus.engine import OcrEngine, TesseractEngine

class TestTesseractEngine(unittest.TestCase):
    def test_is_ocr_engine_with_per_page_batch(self):
        eng = TesseractEngine()
        self.assertIsInstance(eng, OcrEngine)
        self.assertEqual(eng.max_pages, 1)

    def test_available_reflects_which(self):
        eng = TesseractEngine()
        with mock.patch("improved.levine_corpus.engine.which", return_value="/usr/bin/tesseract"):
            self.assertTrue(eng.available())
        with mock.patch("improved.levine_corpus.engine.which", return_value=None):
            self.assertFalse(eng.available())

    def test_ocr_batch_calls_tesseract_per_page_and_joins(self):
        eng = TesseractEngine()
        calls = []
        def fake_run(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(stdout=f"text-{cmd[1]}\n")
        with mock.patch("improved.levine_corpus.engine.subprocess.run", side_effect=fake_run):
            out = eng.ocr_batch(["a.png", "b.png"])
        self.assertEqual(len(calls), 2)
        self.assertIn("text-a.png", out)
        self.assertIn("text-b.png", out)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_engine -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_corpus.engine'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_corpus/engine.py
"""engine -- vyměnitelný OCR krok. Rozhraní OcrEngine + Tesseract baseline."""
import subprocess
from pathlib import Path
from shutil import which


class OcrEngine:
    """Kontrakt OCR enginu. ocr_batch dostane dávku obrázků (<= max_pages) a vrátí text."""
    max_pages = 1

    def available(self) -> bool:
        raise NotImplementedError

    def ocr_batch(self, image_paths) -> str:
        raise NotImplementedError


class TesseractEngine(OcrEngine):
    """Per-strana Tesseract (subprocess), konkatenace. Spolehlivý lokální baseline."""
    max_pages = 1

    def __init__(self, lang="eng"):
        self.lang = lang

    def available(self) -> bool:
        return which("tesseract") is not None

    def ocr_batch(self, image_paths) -> str:
        texts = []
        for p in image_paths:
            r = subprocess.run(["tesseract", str(p), "stdout", "-l", self.lang],
                               capture_output=True, text=True, check=True)
            texts.append(r.stdout)
        return "\n".join(texts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_engine -v`
Expected: PASS (3 testy)

- [ ] **Step 5: Nainstaluj tesseract + smoke na 1 reálné straně + commit**

```bash
brew install tesseract
cd /Users/j/Projects/dear-mister-evans
PYTHONPATH=.:improved .venv/bin/python -c "
from improved.levine_corpus.engine import TesseractEngine
from pathlib import Path
eng=TesseractEngine(); print('available:', eng.available())
imgs=sorted(Path('/Users/j/OneDrive/Jazz Learning/Levine Corpus/_work/pages_sample').glob('page-*.png'))[:1]
print('znaků:', len(eng.ocr_batch(imgs)))"
```
Expected: `available: True` a `znaků: > 500` (próza strany).

```bash
git add improved/levine_corpus/engine.py improved/levine_corpus/tests/test_engine.py
git commit -m "feat(levine): OcrEngine rozhraní + TesseractEngine baseline"
```

---

### Task 3: SPIKE — Baidu Unlimited-OCR (rozhodovací brána)

> **Toto je explorační spike, ne čisté TDD.** Cíl: zjistit reálné API/runtime Baidu Unlimited-OCR (1 den starý, 2026-06-22), rozjet ho na Macu na 5 vzorových stranách (z Tasku 1) a objektivně porovnat s Tesseractem. Výstup = buď `BaiduEngine` splňující rozhraní z Tasku 2, nebo doložené rozhodnutí zůstat u Tesseractu.

**Files:**
- Create (dočasně, gitignored): `~/OneDrive/Jazz Learning/Levine Corpus/_work/spike_baidu.py`, `.../_work/spike_notes.md`
- Create (jen pokud Baidu vyhraje): `improved/levine_corpus/engine_baidu.py` (`class BaiduEngine(OcrEngine)`)

**Interfaces:**
- Produces (podmíněně): `class BaiduEngine(OcrEngine)` s `max_pages >= 5`, `available() -> bool`, `ocr_batch(image_paths: list[Path]) -> str` — stejné rozhraní jako TesseractEngine.

- [ ] **Step 1: Zjisti reálné API a runtime požadavky**

Run (WebFetch v rámci session):
- `https://github.com/baidu/Unlimited-OCR` — dotaz: „installation, inference example, Apple Silicon / MPS support, Ollama or llama.cpp GGUF availability, python dependencies".
- `https://huggingface.co/baidu/Unlimited-OCR` — dotaz: „minimal transformers inference snippet, processor/model class names, required packages, image input format".

Zapiš zjištění do `_work/spike_notes.md` (cesty, balíčky, třídy, runtime cesta).

- [ ] **Step 2: Rozjeď engine na 5 vzorových stranách**

Podle zjištění zvol cestu (preferuj nejjednodušší funkční):
- (a) HF Transformers + MPS: do venv `pip install` zjištěné balíčky; napiš `_work/spike_baidu.py`, který načte model na `device="mps"` a přepíše 5 PNG z `_work/pages_sample`.
- (b) Ollama (pokud existuje oficiální GGUF tag): `ollama pull <tag>`; volej přes API na 5 stran.

Run: `_work/spike_baidu.py` → ulož přepis 5 stran + změř **sekundy/strana**.

- [ ] **Step 3: Porovnej kvalitu vs Tesseract**

Na týchž 5 stranách vygeneruj i Tesseract výstup (`TesseractEngine.ocr_batch`). Do `_work/spike_notes.md` zapiš srovnání: čitelnost prózy, zachování odstavců, chybovost, rychlost, stabilita toolingu.

- [ ] **Step 4: ROZHODOVACÍ BRÁNA**

Kritéria (objektivní): próza bez zásadních chyb, zachované odstavce, únosná rychlost (umožní 316 stran v rozumném okně), žádné padání. Rozhodni:
- **Baidu vyhrál** → pokračuj Step 5.
- **Baidu syrový/pomalý/nestabilní** → zapiš důvod do `_work/spike_notes.md`, přeskoč Step 5–6, pipeline pojede s `TesseractEngine`. Task hotov.

- [ ] **Step 5: (jen když Baidu vyhrál) Implementuj BaiduEngine k rozhraní**

Z funkčního kódu spike udělej `improved/levine_corpus/engine_baidu.py`:

```python
# improved/levine_corpus/engine_baidu.py  (kostra — tělo dle zjištění spike)
"""engine_baidu -- Baidu Unlimited-OCR jako OcrEngine (jeden průchod přes dávku)."""
from .engine import OcrEngine


class BaiduEngine(OcrEngine):
    max_pages = 40        # dle modelu (40+ stran/průchod)

    def __init__(self, ...):   # parametry dle runtime (model path, device)
        ...

    def available(self) -> bool:
        # True jen když je runtime (model/váhy/balíčky) reálně k dispozici
        ...

    def ocr_batch(self, image_paths) -> str:
        # jeden průchod přes dávku obrázků -> markdown text
        ...
```

Doplň `available()`/`ocr_batch()` ověřeným kódem ze spike. Přidej test `tests/test_engine_baidu.py`, který ověří `isinstance(BaiduEngine(...), OcrEngine)` a `max_pages >= 5` (bez reálného modelu; běh modelu ověřil spike).

- [ ] **Step 6: Commit (bez vah a bez obsahu knihy)**

```bash
cd /Users/j/Projects/dear-mister-evans
git add improved/levine_corpus/engine_baidu.py improved/levine_corpus/tests/test_engine_baidu.py
git commit -m "feat(levine): BaiduEngine (Unlimited-OCR) za OcrEngine rozhraním"
```
(Pokud Baidu nevyhrál, žádný commit — jen `_work/spike_notes.md` mimo repo.)

---

### Task 4: Čisticí funkce (dehyfenace, page numbers, opakované řádky, normalizace)

**Files:**
- Create: `improved/levine_corpus/clean.py`
- Test: `improved/levine_corpus/tests/test_clean.py`

**Interfaces:**
- Produces: `dehyphenate(text: str) -> str`; `strip_page_numbers(text: str) -> str`; `drop_repeated_lines(pages: list[str], threshold: float=0.5) -> list[str]`; `normalize_whitespace(text: str) -> str`; `clean_document(text: str) -> str` (kompozice nad textem s page markery `<!-- p.N -->`).

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_corpus/tests/test_clean.py
import unittest
from improved.levine_corpus.clean import (
    dehyphenate, strip_page_numbers, drop_repeated_lines, normalize_whitespace)

class TestClean(unittest.TestCase):
    def test_dehyphenate_joins_linebreak_hyphen(self):
        self.assertEqual(dehyphenate("inter-\nval"), "interval")

    def test_dehyphenate_keeps_inline_hyphen(self):
        self.assertEqual(dehyphenate("ii-V-I cadence"), "ii-V-I cadence")

    def test_strip_page_numbers_removes_lone_number_lines(self):
        self.assertEqual(strip_page_numbers("text\n42\nmore"), "text\nmore")

    def test_strip_page_numbers_keeps_numbers_in_text(self):
        self.assertEqual(strip_page_numbers("chord 7 voicing"), "chord 7 voicing")

    def test_drop_repeated_lines_removes_running_header(self):
        pages = ["THE JAZZ PIANO BOOK\nreal a", "THE JAZZ PIANO BOOK\nreal b",
                 "THE JAZZ PIANO BOOK\nreal c", "THE JAZZ PIANO BOOK\nreal d"]
        out = drop_repeated_lines(pages, threshold=0.5)
        self.assertNotIn("THE JAZZ PIANO BOOK", "\n".join(out))
        self.assertIn("real a", out[0])

    def test_normalize_collapses_blank_runs(self):
        self.assertEqual(normalize_whitespace("a\n\n\n\nb"), "a\n\nb")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_clean -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_corpus.clean'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_corpus/clean.py
"""clean -- čištění OCR textu: dehyfenace, čísla stran, opakovaná záhlaví, normalizace."""
import re


def dehyphenate(text: str) -> str:
    """Spoj slovo rozdělené pomlčkou na konci řádku: 'inter-\\nval' -> 'interval'."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def strip_page_numbers(text: str) -> str:
    """Vyhoď řádky, které jsou jen číslo (čísla stran)."""
    return re.sub(r"(?m)^[ \t]*\d{1,4}[ \t]*\n?", "", text)


def drop_repeated_lines(pages, threshold: float = 0.5):
    """Z per-page textů vyhoď řádky (stripnuté), které se opakují na >= threshold
    podílu stran (živá záhlaví/zápatí). -> nový list per-page textů."""
    from collections import Counter
    seen = Counter()
    for pg in pages:
        for ln in {l.strip() for l in pg.splitlines() if l.strip()}:
            seen[ln] += 1
    n = len(pages) or 1
    repeated = {ln for ln, c in seen.items() if c / n >= threshold}
    out = []
    for pg in pages:
        kept = [l for l in pg.splitlines() if l.strip() not in repeated]
        out.append("\n".join(kept))
    return out


def normalize_whitespace(text: str) -> str:
    """Zkrať 3+ prázdných řádků na 2, ořež trailing mezery."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


PAGE_MARKER = re.compile(r"<!-- p\.\d+ -->")


def clean_document(text: str) -> str:
    """Kompozice: rozdělí dle page markerů, vyhodí opakované řádky, pak dehyfenace,
    čísla stran a normalizace. Markery zůstávají (dohledání zdroje)."""
    parts = PAGE_MARKER.split(text)
    markers = PAGE_MARKER.findall(text)
    cleaned_pages = drop_repeated_lines(parts)
    rebuilt = []
    for i, pg in enumerate(cleaned_pages):
        if i > 0 and i - 1 < len(markers):
            rebuilt.append(markers[i - 1])
        rebuilt.append(pg)
    joined = "\n".join(rebuilt)
    return normalize_whitespace(strip_page_numbers(dehyphenate(joined)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_clean -v`
Expected: PASS (5 testů)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_corpus/clean.py improved/levine_corpus/tests/test_clean.py
git commit -m "feat(levine): čisticí funkce OCR textu (TDD)"
```

---

### Task 5: Segmentace na kapitoly

**Files:**
- Create: `improved/levine_corpus/segment.py`
- Test: `improved/levine_corpus/tests/test_segment.py`

**Interfaces:**
- Produces: `DEFAULT_HEADING_RE: str`; `segment_chapters(text: str, heading_re: str=DEFAULT_HEADING_RE) -> list[tuple[str, str]]` (vrací `[(title, body), ...]`; při <2 nálezech vrátí `[("full", text)]`).

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_corpus/tests/test_segment.py
import unittest
from improved.levine_corpus.segment import segment_chapters

class TestSegment(unittest.TestCase):
    def test_splits_on_chapter_headings(self):
        text = "Chapter One\nIntro body\nChapter Two\nSecond body"
        out = segment_chapters(text, r"(?m)^Chapter .+$")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0], "Chapter One")
        self.assertIn("Intro body", out[0][1])
        self.assertEqual(out[1][0], "Chapter Two")

    def test_degrades_to_single_when_no_headings(self):
        text = "no headings here at all"
        out = segment_chapters(text, r"(?m)^Chapter .+$")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "full")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_segment -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_corpus.segment'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_corpus/segment.py
"""segment -- rozdělení textu na kapitoly podle nadpisů (s degradací na 1 celek)."""
import re

# Default: 'Chapter One' / 'CHAPTER 1' apod. Doladí se po prvním reálném OCR.
DEFAULT_HEADING_RE = r"(?mi)^\s*chapter\b.*$"


def segment_chapters(text, heading_re=DEFAULT_HEADING_RE):
    """-> [(title, body)]. Když najde < 2 nadpisy, vrátí [('full', text)]."""
    matches = list(re.finditer(heading_re, text))
    if len(matches) < 2:
        return [("full", text)]
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        title = block.splitlines()[0].strip()
        body = block[len(block.splitlines()[0]):].lstrip("\n")
        out.append((title, body))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_segment -v`
Expected: PASS (2 testy)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_corpus/segment.py improved/levine_corpus/tests/test_segment.py
git commit -m "feat(levine): segmentace na kapitoly (TDD)"
```

---

### Task 6: Sešití dávek s page markery

**Files:**
- Create: `improved/levine_corpus/assemble.py`
- Test: `improved/levine_corpus/tests/test_assemble.py`

**Interfaces:**
- Consumes: dávky jako `list[tuple[int, int, str]]` = `(first_page, last_page, text)`.
- Produces: `assemble(batches: list[tuple[int, int, str]]) -> str` (vkládá `<!-- p.N -->` před každou dávku, spojuje v pořadí).

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_assemble -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_corpus.assemble'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_corpus/assemble.py
"""assemble -- spojení OCR dávek do jednoho proudu s page markery."""


def assemble(batches):
    """batches: [(first_page, last_page, text)] v pořadí -> jeden markdown proud.
    Před každou dávku vloží '<!-- p.<first> -->' pro dohledání zdroje."""
    parts = []
    for first, _last, text in batches:
        parts.append(f"<!-- p.{first} -->")
        parts.append(text.strip())
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_assemble -v`
Expected: PASS (2 testy)

- [ ] **Step 5: Commit**

```bash
git add improved/levine_corpus/assemble.py improved/levine_corpus/tests/test_assemble.py
git commit -m "feat(levine): sešití dávek s page markery (TDD)"
```

---

### Task 7: Driver build_corpus — dávkování, cache/resumability, CLI

**Files:**
- Create: `improved/levine_corpus/build.py`
- Test: `improved/levine_corpus/tests/test_build.py`

**Interfaces:**
- Consumes: `render_pages` (Task 1), `OcrEngine` (Task 2), `assemble` (Task 6), `clean_document` (Task 4), `segment_chapters` (Task 5).
- Produces: `batch_pages(image_paths: list, max_pages: int) -> list[tuple[int, int, list]]`; `build_corpus(pdf_path, work_dir, out_dir, engine, first=None, last=None) -> list[pathlib.Path]`.

- [ ] **Step 1: Write the failing test**

```python
# improved/levine_corpus/tests/test_build.py
import unittest, tempfile
from pathlib import Path
from unittest import mock
from improved.levine_corpus.engine import OcrEngine
from improved.levine_corpus.build import batch_pages, build_corpus

class FakeEngine(OcrEngine):
    max_pages = 2
    def __init__(self): self.calls = 0
    def available(self): return True
    def ocr_batch(self, image_paths):
        self.calls += 1
        return "Chapter One\nbody " + " ".join(p.name for p in image_paths)

class TestBatch(unittest.TestCase):
    def test_batches_by_max_pages(self):
        imgs = [Path(f"page-{i:03d}.png") for i in (1, 2, 3)]
        b = batch_pages(imgs, 2)
        self.assertEqual(len(b), 2)
        self.assertEqual(b[0][0], 1); self.assertEqual(b[0][1], 2)
        self.assertEqual(b[1][0], 3); self.assertEqual(b[1][1], 3)

class TestBuildCorpus(unittest.TestCase):
    def _imgs(self, d):
        ps = []
        for i in (1, 2, 3):
            fp = Path(d) / f"page-{i:03d}.png"; fp.write_bytes(b"x"); ps.append(fp)
        return ps

    def test_build_writes_chapters_and_caches(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as out:
            eng = FakeEngine()
            with mock.patch("improved.levine_corpus.build.render_pages",
                            return_value=self._imgs(work)):
                paths = build_corpus("x.pdf", work, out, eng)
            self.assertTrue(paths)
            self.assertTrue(any(p.suffix == ".md" for p in paths))
            cache = list(Path(work, "cache").glob("batch-*.md"))
            self.assertTrue(cache)
            # resumable: druhý běh nevolá engine znovu
            calls_after_first = eng.calls
            with mock.patch("improved.levine_corpus.build.render_pages",
                            return_value=self._imgs(work)):
                build_corpus("x.pdf", work, out, eng)
            self.assertEqual(eng.calls, calls_after_first)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_build -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'improved.levine_corpus.build'`

- [ ] **Step 3: Write minimal implementation**

```python
# improved/levine_corpus/build.py
"""build -- orchestrace OCR korpusu: render -> dávky -> OCR(cache) -> assemble
-> clean -> segment -> markdown po kapitolách. + CLI."""
import re
from pathlib import Path
from .render import render_pages
from .assemble import assemble
from .clean import clean_document
from .segment import segment_chapters


def _page_no(path):
    m = re.search(r"(\d+)", Path(path).stem)
    return int(m.group(1)) if m else 0


def batch_pages(image_paths, max_pages):
    """-> [(first_page, last_page, [paths])] po max_pages."""
    out = []
    for i in range(0, len(image_paths), max_pages):
        chunk = image_paths[i:i + max_pages]
        out.append((_page_no(chunk[0]), _page_no(chunk[-1]), chunk))
    return out


def _slug(title, i):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "chapter"
    return f"{i:02d}-{s}.md"


def build_corpus(pdf_path, work_dir, out_dir, engine, first=None, last=None):
    """Celá pipeline. -> list cest k zapsaným .md kapitolám."""
    work = Path(work_dir); cache = work / "cache"; cache.mkdir(parents=True, exist_ok=True)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    pages = render_pages(pdf_path, work / "pages", first=first, last=last)
    batches = batch_pages(pages, engine.max_pages)
    texts = []
    for f, l, imgs in batches:
        cf = cache / f"batch-{f:04d}-{l:04d}.md"
        if cf.exists():
            text = cf.read_text()
        else:
            text = engine.ocr_batch(imgs)
            cf.write_text(text)
        texts.append((f, l, text))
    doc = clean_document(assemble(texts))
    written = []
    for i, (title, body) in enumerate(segment_chapters(doc), 1):
        fp = out / _slug(title, i)
        fp.write_text(f"# {title}\n\n{body}\n")
        written.append(fp)
    return written


def main():
    import argparse
    ap = argparse.ArgumentParser(description="OCR Levine -> markdown korpus")
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--work", required=True)
    ap.add_argument("--engine", choices=["tesseract", "baidu"], default="tesseract")
    ap.add_argument("--first", type=int)
    ap.add_argument("--last", type=int)
    a = ap.parse_args()
    if a.engine == "baidu":
        from .engine_baidu import BaiduEngine
        eng = BaiduEngine()
    else:
        from .engine import TesseractEngine
        eng = TesseractEngine()
    if not eng.available():
        raise SystemExit(f"engine '{a.engine}' není dostupný")
    paths = build_corpus(a.pdf, a.work, a.out_dir, eng, first=a.first, last=a.last)
    print(f"hotovo: {len(paths)} kapitol -> {a.out_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest improved.levine_corpus.tests.test_build -v`
Expected: PASS (2 testy)

- [ ] **Step 5: Spusť celou testovou sadu balíku + commit**

Run: `cd /Users/j/Projects/dear-mister-evans && PYTHONPATH=.:improved .venv/bin/python -m unittest discover -s improved/levine_corpus/tests -v`
Expected: PASS (všechny testy balíku)

```bash
git add improved/levine_corpus/build.py improved/levine_corpus/tests/test_build.py
git commit -m "feat(levine): driver build_corpus + cache/resumability + CLI (TDD)"
```

---

### Task 8: Gitignore ochrana + plný běh + korpus do OneDrive

**Files:**
- Modify: `.gitignore` (kořen repa)

**Interfaces:**
- Consumes: `build_corpus` / CLI (Task 7), zvolený engine (Task 3).

- [ ] **Step 1: Ochrana proti commitu textu knihy**

Přidej na konec `.gitignore` (kořen repa):
```
# Levine OCR korpus — text knihy ani modelové váhy NIKDY do gitu (autorská práva)
**/Levine Corpus/**
**/_work/**
*.gguf
```

- [ ] **Step 2: Ověř, že git výstup ignoruje**

Run:
```bash
cd /Users/j/Projects/dear-mister-evans
git check-ignore -v "/Users/j/OneDrive/Jazz Learning/Levine Corpus/01-test.md" 2>/dev/null && echo IGNOROVÁNO || echo "POZOR: necíleno (cesta je mimo repo, OK), kontroluj jen in-repo výstupy"
git status --short
```
Expected: `git status` neukazuje žádné soubory z „Levine Corpus" (výstup je beztak mimo repo; pravidla chrání i případné in-repo kopie).

- [ ] **Step 3: Commit .gitignore**

```bash
git add .gitignore
git commit -m "chore(levine): gitignore ochrana OCR výstupu a vah (autorská práva)"
```

- [ ] **Step 4: Plný běh na celé knize zvoleným enginem**

Run (engine = výsledek Tasku 3; níže příklad tesseract):
```bash
cd /Users/j/Projects/dear-mister-evans
PYTHONPATH=.:improved .venv/bin/python -m improved.levine_corpus.build \
  "/Users/j/OneDrive/Jazz Learning/The Jazz Piano Book - PDF Room.pdf" \
  "/Users/j/OneDrive/Jazz Learning/Levine Corpus" \
  --work "/Users/j/OneDrive/Jazz Learning/Levine Corpus/_work" \
  --engine tesseract
```
Expected: `hotovo: N kapitol -> .../Levine Corpus`

- [ ] **Step 5: Namátková kontrola kvality**

Otevři 2–3 výsledné `.md` a zkontroluj čitelnost prózy, zachování odstavců, smysluplné rozdělení kapitol. Pokud je segmentace špatná, dolaď `DEFAULT_HEADING_RE` v `segment.py` podle reálných nadpisů a spusť znovu (cache OCR zůstane, přepíše se jen segmentace/markdown — pro re-segmentaci stačí smazat `out_dir` .md, ne cache).

- [ ] **Step 6: Žádný commit obsahu** — korpus je v OneDrive a gitignored. Hotovo.

---

## Self-Review

**Spec coverage:**
- §4 pipeline render→engine→assemble→segment→clean → Tasks 1,2,6,5,4 (pořadí kódu se liší od diagramu, ale všechny kroky pokryty); driver Task 7. ✓
- §5 komponenty/rozhraní → render (T1), OcrEngine+Tesseract (T2), assemble (T6), segment (T5), clean (T4), build_corpus (T7). ✓
- §7 spike-first Baidu s fallbackem → Task 3 s rozhodovací bránou. ✓
- §8 autorská práva (kód v repu, text/váhy mimo git) → Task 8 gitignore + výstup do OneDrive. ✓
- §9 chyby/resumability → cache v T7 (resumable test), degradace segmentace v T5, `available()` v T2/T7. ✓
- §10 testování (synteticky, FakeEngine) → T4/T5/T6 syntetické, T7 FakeEngine. ✓
- Mimo rozsah (OMR, strukturování) → nezahrnuto. ✓

**Placeholder scan:** Deterministické tasky (1,2,4,5,6,7,8) mají kompletní kód a příkazy. Task 3 je vědomě explorační (spike) — kostra BaiduEngine se doplní ověřeným kódem ze spike; to je účel spike, ne placeholder.

**Type consistency:** `OcrEngine.ocr_batch(image_paths)->str`, `max_pages:int` konzistentní v T2/T3/T7. `assemble` bere `(first,last,text)` shodně produkované `batch_pages` v T7. `clean_document`/`segment_chapters`/`render_pages` názvy i podpisy sedí napříč T4/T5/T1 a driverem T7.
