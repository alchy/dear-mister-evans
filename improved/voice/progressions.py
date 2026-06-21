"""progressions -- stavebnice progresí: TÓNIKA x TONALITA x POSTUP -> changes.

Postupy jsou funkční šablony (římsky, relativně k tónice) -> z root + módu se
sestaví akordové changes. (Jen funkční harmonie, žádné chráněné melodie.)
"""
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

MAJOR = {
    "ii–V–I":               [(2, "m7"), (7, "7"), (0, "maj7"), (0, "maj7")],
    "ii–V–I–vi":            [(2, "m7"), (7, "7"), (0, "maj7"), (9, "m7")],
    "I–vi–ii–V":            [(0, "maj7"), (9, "m7"), (2, "m7"), (7, "7")],
    "I–VI–ii–V (sek.dom.)": [(0, "maj7"), (9, "7"), (2, "m7"), (7, "7")],
    "I–IV–iii–vi–ii–V":     [(0, "maj7"), (5, "maj7"), (4, "m7"), (9, "m7"), (2, "m7"), (7, "7")],
    "jazz blues":           [(0, "7"), (5, "7"), (0, "7"), (0, "7"), (5, "7"), (5, "7"),
                             (0, "7"), (9, "7"), (2, "m7"), (7, "7"), (0, "7"), (7, "7")],
    "rhythm changes A":     [(0, "maj7"), (9, "7"), (2, "m7"), (7, "7"),
                             (0, "maj7"), (5, "7"), (0, "maj7"), (7, "7")],
}
MINOR = {
    "iiø–V–i":              [(2, "m7b5"), (7, "7"), (0, "m7"), (0, "m7")],
    "iiø–V–i–iv":           [(2, "m7b5"), (7, "7"), (0, "m7"), (5, "m7")],
    "i–iv–iiø–V":           [(0, "m7"), (5, "m7"), (2, "m7b5"), (7, "7")],
    "i–VI–iiø–V":           [(0, "m7"), (8, "maj7"), (2, "m7b5"), (7, "7")],
    "moll blues":           [(0, "m7"), (0, "m7"), (0, "m7"), (0, "m7"), (5, "m7"), (5, "m7"),
                             (0, "m7"), (0, "m7"), (2, "m7b5"), (7, "7"), (0, "m7"), (7, "7")],
}
PATTERNS = {"dur": MAJOR, "moll": MINOR}


def patterns(mode):
    return list(PATTERNS.get(mode, MAJOR))


def build_changes(root_name, mode, pattern):
    """root_name (C..B) x mode (dur|moll) x pattern -> string akordů."""
    ri = NAMES.index(root_name) if root_name in NAMES else 0
    pats = PATTERNS.get(mode, MAJOR)
    seq = pats.get(pattern) or next(iter(pats.values()))
    return " ".join(NAMES[(ri + off) % 12] + q for off, q in seq)
