"""chords -- akord na beat-span z beat-synchronní chroma (Evans-aware).

NEpoužívá bass=root: Evans hraje ROOTLESS voicingy, spodní tón je často 3 nebo 7.
Proto: chroma vážená trváním+velocity na každý beat -> template-fit přes všech
12 kořenů × jazzové kvality (váhy: akordové tóny +, mimo-stupnicové −) + prior
tóniny (Krumhansl) + Viterbi vyhlazení (akordy mají držet, ne blikat po beatech).

API:
    label_beats(notes, grid) -> (spans, key_pc, mode)
        spans = [ChordSpan(start_beat, n_beats, root_pc, qual, t0, t1), ...]
"""
from collections import namedtuple
import numpy as np
from . import io_midi

ChordSpan = namedtuple("ChordSpan", "start nbeats root qual t0 t1")
PC = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# kvality: akordové tóny (+1), barevné/stupnicové tenze (+0.3), mimo stupnici (−0.4)
SCALES = {
    "maj7":  ([0, 4, 7, 11], [0, 2, 4, 6, 7, 9, 11]),     # lydická
    "7":     ([0, 4, 7, 10], [0, 2, 4, 5, 7, 9, 10]),     # mixolydická (+ altered níž)
    "m7":    ([0, 3, 7, 10], [0, 2, 3, 5, 7, 9, 10]),     # dorská
    "m7b5":  ([0, 3, 6, 10], [0, 1, 3, 5, 6, 8, 10]),     # lokrická
    "dim7":  ([0, 3, 6, 9],  [0, 2, 3, 5, 6, 8, 9, 11]),  # zmenšená (W-H)
    "6":     ([0, 4, 7, 9],  [0, 2, 4, 6, 7, 9, 11]),
    "m6":    ([0, 3, 7, 9],  [0, 2, 3, 5, 7, 9, 11]),     # melodická moll
}
QUALS = list(SCALES)


def _template(chord_pcs, scale_pcs):
    """Jednotkově normovaná šablona pro COSINE fit s chroma taktu.

    Cosine sám trestá chybějící akordové tóny (šablona je tam má, chroma ne) i
    přebývající hrané tóny (chroma je tam má, šablona ne) -> akord MUSÍ sedět na
    to, co zní. Guide tóny (3 a 7) váží nejvíc = určují kvalitu (dur/moll, 6/7).
    """
    w = np.zeros(12)
    for p in scale_pcs:
        w[p % 12] = 0.35                       # idiomatické tenze -> nepenalizovat
    r, third, fifth, sev = chord_pcs
    w[r % 12] = 0.9
    w[third % 12] = 1.3
    w[fifth % 12] = 0.7
    w[sev % 12] = 1.3
    n = np.linalg.norm(w)
    return w / (n or 1.0)


TEMPLATES = np.array([np.roll(_template(*SCALES[q]), r)
                      for q in QUALS for r in range(12)])      # [84, 12] volné (labeling)
CANDS = [(r, q) for q in QUALS for r in range(12)]


def _tight(chord_pcs):
    """Těsná šablona: jen akordové tóny 1-3-5-7 (pro DISKRIMINATIVNÍ fit segmentace)."""
    w = np.zeros(12)
    for p in chord_pcs:
        w[p % 12] = 1.0
    return w / np.linalg.norm(w)


TIGHT = np.array([np.roll(_tight(SCALES[q][0]), r)
                  for q in QUALS for r in range(12)])          # [84, 12] těsné (segmentace)

# Krumhansl-Schmuckler profily (major/minor)
_KS_MAJ = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
_KS_MIN = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])


def chroma_per_beat(notes, beats, tail_period):
    """[n_beats,12] chroma vážená překryvem trvání × velocity na každém beat-spanu."""
    edges = list(beats) + [beats[-1] + tail_period] if len(beats) else []
    nb = len(beats)
    C = np.zeros((nb, 12))
    for n in notes:
        a, b = n.onset, n.onset + n.dur
        # beaty, které span protíná (lineární; not je hodně, ale ok pro dev)
        for i in range(nb):
            ws, we = edges[i], edges[i + 1]
            ov = min(b, we) - max(a, ws)
            if ov > 0:
                C[i, n.pitch % 12] += ov * (n.vel / 127.0)
    norm = np.linalg.norm(C, axis=1, keepdims=True)
    return C / np.where(norm > 0, norm, 1.0)


def _best_key(agg):
    """Krumhansl korelace pro jeden chroma vektor -> (key_pc, mode)."""
    if agg.sum() == 0:
        return 0, "maj"
    agg = agg - agg.mean()
    best = (-2, 0, "maj")
    for r in range(12):
        for prof, mode in ((_KS_MAJ, "maj"), (_KS_MIN, "min")):
            p = np.roll(prof - prof.mean(), r)
            c = np.dot(agg, p) / (np.linalg.norm(agg) * np.linalg.norm(p) + 1e-9)
            if c > best[0]:
                best = (c, r, mode)
    return best[1], best[2]


def detect_key(chroma):
    """Globální tónina (agregace přes celý track)."""
    return _best_key(chroma.sum(axis=0))


def local_keys(chroma, win=8):
    """Klouzavá (lokální) tónina na každý beat z okna ±win beatů -> dynamická,
    moduluje s hraním a mění prior akordů v čase."""
    nb = len(chroma)
    out = []
    for i in range(nb):
        a, b = max(0, i - win), min(nb, i + win + 1)
        out.append(_best_key(chroma[a:b].sum(axis=0)))
    return out


def _diatonic_bonus(key_pc, mode):
    """+bonus diatonickým 7-akordům tóniny (pomáhá Dm7 vs D7 apod.)."""
    bonus = np.zeros(len(CANDS))
    if mode == "maj":
        diat = {0: "maj7", 2: "m7", 4: "m7", 5: "maj7", 7: "7", 9: "m7", 11: "m7b5"}
    else:
        diat = {0: "m7", 2: "m7b5", 3: "maj7", 5: "m7", 7: "7", 8: "maj7", 10: "7"}
    for ci, (r, q) in enumerate(CANDS):
        deg = (r - key_pc) % 12
        if diat.get(deg) == q:
            bonus[ci] = 0.05            # jen jemný tie-break, ať netlačí falešné akordy
    return bonus


_ROOTS = np.array([r for r, q in CANDS])


def _trans_bonus():
    """Funkční přechodový bonus mezi akordy: progrese má dávat HARMONICKÝ smysl,
    ne random. Klesající kvinta (ii-V, V-I, kruh) a diatonický krok nahoru +;
    chromatický průchod malý +; ostatní 0 (platí jen switch penaltu)."""
    T = np.zeros((len(CANDS), len(CANDS)))
    for a, (ra, qa) in enumerate(CANDS):
        for b, (rb, qb) in enumerate(CANDS):
            if a == b:
                continue
            d = (ra - rb) % 12
            if d == 7:                                  # kořen dolů o kvintu (kruh)
                T[a, b] = 0.35
                if qa == "m7" and qb == "7":            # ii -> V
                    T[a, b] = 0.6
                elif qa == "m7b5" and qb == "7":        # mollové ii -> V
                    T[a, b] = 0.6
                elif qa == "7" and qb in ("maj7", "6", "m7", "m6", "mmaj7"):  # V -> I
                    T[a, b] = 0.6
            elif (rb - ra) % 12 in (1, 2):              # diatonický krok nahoru
                T[a, b] = 0.15
            elif d == 1:                                # chromatický průchod dolů
                T[a, b] = 0.1
    return T


TRANS = _trans_bonus()


def bass_pc_per_beat(notes, beats, period):
    """Pc nejnižšího znějícího tónu na každém beatu (sólo Evans si bas hraje sám)."""
    nb = len(beats)
    edges = list(beats) + [beats[-1] + period]
    out = np.full(nb, -1)
    for i in range(nb):
        ws, we = edges[i], edges[i + 1]
        lo = None
        for n in notes:
            if min(n.onset + n.dur, we) - max(n.onset, ws) > 0:
                if lo is None or n.pitch < lo:
                    lo = n.pitch
        if lo is not None:
            out[i] = lo % 12
    return out


def span_profile(notes, t0, t1):
    """Váhový profil pc přes interval: VÁHA = TRVÁNÍ (lehce × dynamika).

    Dlouho držený tón váží hodně; krátké přechodové tóny licku skoro nic ->
    nedělají dlouhou disharmonii a netáhnou akord. (díky J.)
    """
    prof = np.zeros(12)
    for n in notes:
        ov = min(n.onset + n.dur, t1) - max(n.onset, t0)
        if ov > 0:
            prof[n.pitch % 12] += ov * (0.5 + 0.5 * n.vel / 127.0)
    return prof


def _span_bass_pc(notes, t0, t1):
    """Pc nejnižšího znějícího tónu přes celý span (stabilnější než per beat)."""
    lo = None
    for n in notes:
        if min(n.onset + n.dur, t1) - max(n.onset, t0) > 0:
            if lo is None or n.pitch < lo:
                lo = n.pitch
    return -1 if lo is None else lo % 12


def fit_chord(prof, bass_pc=-1, key=None, bass_bonus=0.15):
    """Najdi akord, který se nejlíp NALEPÍ na váhový profil (cosine) + bas + prior."""
    if prof.sum() == 0:
        return 0, "maj7"
    p = prof / np.linalg.norm(prof)
    score = TEMPLATES @ p                                   # cosine pro 84 kandidátů
    if bass_pc >= 0:
        score = score + bass_bonus * (_ROOTS == bass_pc)
    if key is not None:
        score = score + _diatonic_bonus(*key)
    return CANDS[int(score.argmax())]


def _cos_dist(a, b):
    na, nb_ = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb_ == 0:
        return 0.0
    return 1.0 - float(np.dot(a, b) / (na * nb_))


def harmonic_change(harmony, beats, period, win=2):
    """Síla harmonické změny na každém beatu = cosine vzdálenost okna-PŘED vs okna-PO.

    Sliding window duration-vážených profilů (díky J.) -> kde se profil prudce
    změní, tam se mění harmonie. Z MIDI přímo odvozeno, žádné hádání.
    """
    nb = len(beats)
    edges = list(beats) + [beats[-1] + period]
    cs = np.zeros(nb)
    for i in range(1, nb):
        before = span_profile(harmony, edges[max(0, i - win)], edges[i])
        after = span_profile(harmony, edges[i], edges[min(nb, i + win)])
        cs[i] = _cos_dist(before, after)
    return cs


def raw_profile_per_beat(notes, beats, period):
    """[nb,12] duration-vážený profil na každý beat (BEZ normalizace -> prefixové součty)."""
    nb = len(beats)
    edges = np.array(list(beats) + [beats[-1] + period])
    M = np.zeros((nb, 12))
    for n in notes:
        a, b = n.onset, n.onset + n.dur
        i0 = max(0, int(np.searchsorted(edges, a, "right")) - 1)
        i1 = min(nb - 1, int(np.searchsorted(edges, b, "right")) - 1)
        w = 0.5 + 0.5 * n.vel / 127.0
        for i in range(i0, i1 + 1):
            ov = min(b, edges[i + 1]) - max(a, edges[i])
            if ov > 0:
                M[i, n.pitch % 12] += ov * w
    return M


def label_beats(notes, grid, switch_penalty=0.45, keywin=8, bass_bonus=0.15):
    """Akordové spany: beat-synchronní Viterbi (segmentace + label) na chroma
    SPODKU (harmonie). Emise = cosine fit + bas-kořen + tónina; přechod drží akord
    (switch_penalty). Každý výsledný span se nakonec přeznačí podle duration-váženého
    profilu (akord se nalepí na to, co Evans nejdýl drží)."""
    beats = grid.beats
    nb = len(beats)
    if nb < 2:
        return [], []
    from .voices import skyline_split
    _melody, harmony = skyline_split(notes)                    # SPODEK na akord
    period = float(np.median(np.diff(beats)))
    edges = list(beats) + [beats[-1] + period]
    C = chroma_per_beat(harmony, beats, period)                # L2-norm -> cosine
    keys = local_keys(C, keywin)
    emis = C @ TEMPLATES.T
    emis += np.array([_diatonic_bonus(kp, md) for (kp, md) in keys])
    bass = bass_pc_per_beat(harmony, beats, period)
    bb = bass_bonus * (_ROOTS[None, :] == bass[:, None])
    bb[bass < 0] = 0.0
    emis = emis + bb
    # Viterbi s FUNKČNÍMI přechody: zůstat (a==b, cena 0) vs změnit (−switch + funkční bonus)
    ns = emis.shape[1]
    V = np.full((nb, ns), -1e9); Bk = np.zeros((nb, ns), dtype=int)
    V[0] = emis[0]
    idx = np.arange(ns)
    for i in range(1, nb):
        stay = V[i - 1]                                   # a==b
        M_switch = V[i - 1][:, None] - switch_penalty + TRANS   # [a,b]
        switch_score = M_switch.max(axis=0)
        switch_arg = M_switch.argmax(axis=0)
        use = switch_score > stay
        V[i] = np.where(use, switch_score, stay) + emis[i]
        Bk[i] = np.where(use, switch_arg, idx)
    path = np.zeros(nb, dtype=int)
    path[-1] = int(V[-1].argmax())
    for i in range(nb - 1, 0, -1):
        path[i - 1] = Bk[i, path[i]]
    # segmenty z path -> přeznač akord podle duration-váženého profilu + slouč
    M = raw_profile_per_beat(harmony, beats, period)
    prefix = np.vstack([np.zeros(12), np.cumsum(M, axis=0)])
    spans = []
    i = 0
    while i < nb:
        j = i
        while j + 1 < nb and path[j + 1] == path[i]:
            j += 1
        prof = prefix[j + 1] - prefix[i]
        bpc = _span_bass_pc(harmony, edges[i], edges[j + 1])
        r, q = fit_chord(prof, bass_pc=bpc, key=keys[i], bass_bonus=bass_bonus)
        if spans and spans[-1].root == r and spans[-1].qual == q:
            p = spans[-1]
            spans[-1] = p._replace(nbeats=p.nbeats + (j - i + 1), t1=edges[j + 1])
        else:
            spans.append(ChordSpan(i, j - i + 1, r, q, edges[i], edges[j + 1]))
        i = j + 1
    return spans, keys


def sym(root, qual):
    return PC[root % 12] + ("" if qual == "maj" else qual)


def parse_sym(s):
    """'Ebmaj7' -> (3, 'maj7'). Inverze sym()."""
    if len(s) > 1 and s[1] in "#b":
        root, rest = s[:2], s[2:]
    else:
        root, rest = s[:1], s[1:]
    return PC.index(root), (rest or "maj7")


if __name__ == "__main__":
    import sys
    from . import beats as B
    notes = io_midi.load_notes(sys.argv[1])
    grid = B.track(notes)
    spans, keys = label_beats(notes, grid)
    gk, gm = detect_key(chroma_per_beat(notes, grid.beats, float(np.median(np.diff(grid.beats)))))
    print(f"globální tónina≈ {PC[gk]} {gm} | beatů={len(grid.beats)} | akordů(spanů)={len(spans)}")
    print("  " + "  ".join(f"{sym(s.root, s.qual)}×{s.nbeats}" for s in spans[:24]))
