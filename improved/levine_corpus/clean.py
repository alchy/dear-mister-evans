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
