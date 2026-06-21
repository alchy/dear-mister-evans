"""voicings -- basové (LH) voicingy podle TYPU, s KONZISTENTNÍM tvarem.

Řeší analýzou zjištěné míchání: každý typ má pevnou vnitřní strukturu a m7b5/dim7
v rootless jsou TAKÉ bez základního tónu (žádné míchání rootless/rooted).

Typy (kind):
  root      -- základní tvar (R-3-5-7), každý akord v základní poloze (bez VL)
  root_vl   -- R-3-5-7 + nejúspornější voice-leading (chromatický posun)
  drop2     -- close R-3-5-7, 2. tón shora o oktávu dolů
  drop3     -- 3. tón shora o oktávu dolů
  drop24    -- 2. a 4. tón shora o oktávu dolů
  rootless  -- Evans bezzákladový (3-5-7-9; m7b5/dim: b3-b5-b7-9), VL
  cluster   -- nejtěsnější tvar (rotace s min. rozpětím)
"""
import itertools

KINDS = ["root", "root_vl", "drop2", "drop3", "drop24", "rootless", "cluster"]
LABELS = {
    "root": "základní tvar (fix)", "root_vl": "základní + posun (voice-led)",
    "drop2": "drop 2", "drop3": "drop 3", "drop24": "drop 2&4",
    "rootless": "Evans rootless (A/B)", "cluster": "cluster",
}

# offsety chord-tónů od základu
SEV = {  # R 3 5 7
    "maj7": [0, 4, 7, 11], "6": [0, 4, 7, 9], "m7": [0, 3, 7, 10], "m6": [0, 3, 7, 9],
    "mmaj7": [0, 3, 7, 11], "7": [0, 4, 7, 10], "m7b5": [0, 3, 6, 10], "dim7": [0, 3, 6, 9],
}
RLESS = {  # 3 5 7 9  (Evans); m7b5/dim ROOTLESS: b3 b5 b7 9 (žádný root)
    "maj7": [4, 7, 11, 2], "6": [4, 7, 9, 2], "m7": [3, 7, 10, 2], "m6": [3, 7, 9, 2],
    "mmaj7": [3, 7, 11, 2], "7": [4, 10, 2, 9], "m7b5": [3, 6, 10, 2], "dim7": [3, 6, 9, 2],
}
REF = 58            # rejstřík voicingu (vrch ~ C4); bas je zvlášť dole


def _center(voic, ref):
    voic = sorted(voic)
    while sum(voic) / len(voic) < ref - 6:
        voic = [v + 12 for v in voic]
    while sum(voic) / len(voic) > ref + 6:
        voic = [v - 12 for v in voic]
    return voic


def _stack(offs, root, ref):
    """Close-position stack v pořadí offsetů, vycentrovaný k ref."""
    pcs = [(root + o) % 12 for o in offs]
    voic, cur = [], None
    for pc in pcs:
        if cur is None:
            base = ref - 6
            cur = base + ((pc - base) % 12)
        else:
            cur = cur + ((pc - cur) % 12)
            if cur == voic[-1]:
                cur += 12
        voic.append(cur)
    return _center(voic, ref)


def _drop(close, which):
    v = sorted(close)
    if which == "drop2":
        v[2] -= 12
    elif which == "drop3":
        v[1] -= 12
    elif which == "drop24":
        v[2] -= 12; v[0] -= 12
    return sorted(v)


def _cluster(offs, root, ref):
    best = None
    for r in range(len(offs)):
        o = offs[r:] + offs[:r]
        v = _stack(o, root, ref)
        span = max(v) - min(v)
        if best is None or span < best[0]:
            best = (span, sorted(v))
    return best[1]


def _place_near(pc, target):
    d = (pc - target) % 12
    return target + (d - 12 if d > 6 else d)


def _voice_lead(prev, pcs):
    """Min. pohyb 4 hlasů od prev (drží společné tóny)."""
    best, bc = None, 1e9
    for perm in itertools.permutations(pcs):
        placed = [_place_near(perm[i], prev[i]) for i in range(len(perm))]
        if len(set(placed)) < len(placed):
            continue
        c = sum(abs(placed[i] - prev[i]) for i in range(len(placed)))
        if c < bc:
            bc, best = c, sorted(placed)
    return best or sorted(_place_near(p, prev[0]) for p in pcs)


def _shift_near(voic, ref_mean):
    """Posuň CELÝ tvar o oktávy k ref_mean (nerozhází vnitřní strukturu)."""
    v = sorted(voic)
    m = sum(v) / len(v)
    while m - ref_mean > 6:
        v = [x - 12 for x in v]; m -= 12
    while ref_mean - m > 6:
        v = [x + 12 for x in v]; m += 12
    return v


def voicing_for(root, quality, kind, prev=None, ref=REF):
    q = quality if quality in SEV else "maj7"
    if kind == "rootless":
        pcs = [(root + o) % 12 for o in RLESS[q]]
        return _stack(RLESS[q], root, ref) if prev is None else _voice_lead(prev, pcs)
    if kind == "root_vl":
        pcs = [(root + o) % 12 for o in SEV[q]]
        return _stack(SEV[q], root, ref) if prev is None else _voice_lead(prev, pcs)
    # tvarově PEVNÉ typy (drží strukturu): centruj do STÁLÉHO rejstříku (ref) -> statický,
    # bez driftu (nevedou se k předchozímu, takže klaviatura "neutíká").
    if kind == "cluster":
        v = _cluster(RLESS[q], root, ref)
    elif kind in ("drop2", "drop3", "drop24"):
        v = _drop(_stack(SEV[q], root, ref), kind)
    else:  # root (fix)
        v = _stack(SEV[q], root, ref)
    return sorted(_shift_near(v, ref))


def generate(progression, kind="rootless", ref=REF):
    """progression [(root,quality)] -> [(bass, voicing[seřazený])]."""
    out, prev = [], None
    for root, q in progression:
        v = sorted(voicing_for(root, q, kind, prev, ref))
        out.append((36 + (root % 12), v))      # bas (skutečný základ) zvlášť dole
        prev = v
    return out
