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
