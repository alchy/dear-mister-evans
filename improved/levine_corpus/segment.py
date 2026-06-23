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
