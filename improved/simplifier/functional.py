"""functional -- ii-V-I / ii-V / turnaround segmentace přes KLESAJÍCÍ KVINTY.

Jazzově spolehlivé: root motion dolů o kvintu (= nahoru o kvartu) je páteř ii-V-I.
  ii-V-I dur:  m7  -> 7   -> maj7/6     (kořeny dolů o kvintu)
  ii-V-i moll: m7b5-> 7   -> m7/m6/mmaj7
  ii-V:        m7/m7b5 -> 7             (bez rozvazu)

Vrací jednotky [(typ, i_start, i_end)] jako indexy do spans (včetně koncového).
"""

_DOM = {"7"}
_MIN = {"m7"}
_HALF = {"m7b5"}
_TONIC_MAJ = {"maj7", "6"}
_TONIC_MIN = {"m7", "m6"}


def _fifth(a, b):
    """root b je o kvintu níž než root a (D->G->C)."""
    return (a.root - b.root) % 12 == 7


def find_units(spans):
    units = []
    n = len(spans)
    i = 0
    while i < n:
        s = spans[i]
        # ii-V-I (dur i moll)
        if i + 2 < n:
            a, b, c = spans[i], spans[i + 1], spans[i + 2]
            if _fifth(a, b) and _fifth(b, c) and b.qual in _DOM:
                if a.qual in _MIN and c.qual in _TONIC_MAJ:
                    units.append(("ii-V-I", i, i + 2)); i += 3; continue
                if a.qual in _HALF and c.qual in _TONIC_MIN:
                    units.append(("ii-V-i", i, i + 2)); i += 3; continue
        # ii-V (bez rozvazu)
        if i + 1 < n:
            a, b = spans[i], spans[i + 1]
            if _fifth(a, b) and b.qual in _DOM and a.qual in (_MIN | _HALF):
                units.append(("ii-V", i, i + 1)); i += 2; continue
        # turnaround: řetěz dominant/kvint o délce >=3
        j = i
        while j + 1 < n and _fifth(spans[j], spans[j + 1]):
            j += 1
        if j - i >= 2:
            units.append(("turnaround", i, j)); i = j + 1; continue
        i += 1
    return units
