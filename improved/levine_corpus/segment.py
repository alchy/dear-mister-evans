"""segment -- rozdělení textu na kapitoly podle nadpisů (s degradací na 1 celek)."""
import re

# Výchozí: VELKÉ nadpisy "CHAPTER ONE", INTRODUCTION, APPENDIX (i OCR překlep APPPENDIX).
# Case-sensitive schválně: ať se nechytá slovo "chapter" v běžné próze.
DEFAULT_HEADING_RE = r"(?m)^[ \t]*(?:CHAPTER[ \t]+[A-Z][A-Z-]+|INTRODUCTION|APP+ENDIX)[ \t]*$"


def _norm(title):
    return re.sub(r"\s+", " ", title).strip().upper()


def segment_chapters(text, heading_re=DEFAULT_HEADING_RE):
    """-> [(title, body)]. Když najde < 2 nadpisy, vrátí [('full', text)].
    Po sobě jdoucí stejné nadpisy (živé záhlaví kapitoly opakované po stranách) se
    sloučí do jedné kapitoly."""
    matches = list(re.finditer(heading_re, text))
    if len(matches) < 2:
        return [("full", text)]
    raw = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        first = block.splitlines()[0]
        title = first.strip()
        body = block[len(first):].lstrip("\n")
        raw.append([title, body])
    # sloučit po sobě jdoucí stejné nadpisy
    merged = [raw[0]]
    for title, body in raw[1:]:
        if _norm(title) == _norm(merged[-1][0]):
            merged[-1][1] = (merged[-1][1].rstrip() + "\n" + body).strip() + "\n"
        else:
            merged.append([title, body])
    return [(t, b) for t, b in merged]
