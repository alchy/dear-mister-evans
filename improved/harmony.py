#!/usr/bin/env python3
"""
harmony.py -- key-aware detekce akordove progrese (vylepseni kroku [2]).

Proti puvodnimu per-bar argmaxu pridava tri veci, ktere cisti chromaticky sum
z hustych sol:
  1) ODHAD TONINY z celku (Krumhansl-Kessler profily) -> (root, dur/moll),
  2) DIATONICKY PRIOR: akordy patrici do odhadnute toniny dostanou bonus
     (potlaci F#dim7/Gmaj7 v Cm kontextu), chromatika ale stale projit muze,
  3) VITERBI vyhlazeni: penalizuje caste zmeny -> rozumny harmonicky rytmus,
     mirny bonus za pohyb koren o kvartu/kvintu (funkcni harmonie).

API:  detect_progression(notes, bar=4.0, max_bars=None) -> ([(root,quality)], key_str)
"""
import numpy as np
from collections import defaultdict

# omezeny slovnik kvalit (7) -- akordove sablony (pitch-classy)
QUAL_TEMPL = {
    'maj7': [0,4,7,11], '7': [0,4,7,10], 'm7': [0,3,7,10],
    'm7b5': [0,3,6,10], 'dim7': [0,3,6,9], 'm6': [0,3,7,9], '6': [0,4,7,9],
}
def _tvec(ints):
    v = np.zeros(12)
    for i in ints: v[i % 12] = 1.0
    return v / np.linalg.norm(v)
STATES = [(r, q) for q in QUAL_TEMPL for r in range(12)]
TVEC = {(r, q): np.roll(_tvec(QUAL_TEMPL[q]), r) for (r, q) in STATES}

PC = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

# Krumhansl-Kessler key profily
_KMAJ = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
_KMIN = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])


def estimate_key(total_chroma):
    """Vrati (key_root, mode 'maj'/'min', citelny retezec)."""
    c = total_chroma - total_chroma.mean()
    best, bkey = -1e9, (0, 'maj')
    for r in range(12):
        for prof, mode in [(_KMAJ, 'maj'), (_KMIN, 'min')]:
            p = np.roll(prof, r); p = p - p.mean()
            score = float(np.dot(c, p) / (np.linalg.norm(c)*np.linalg.norm(p) + 1e-9))
            if score > best:
                best, bkey = score, (r, mode)
    r, mode = bkey
    return r, mode, f"{PC[r]} {'dur' if mode=='maj' else 'moll'}"


def diatonic_set(key_root, mode):
    """Mnozina (root,quality) diatonickych akordu v tonine (+bezne alternativy)."""
    K = key_root
    if mode == 'maj':
        degs = [(0,'maj7'),(0,'6'),(2,'m7'),(4,'m7'),(5,'maj7'),(5,'6'),
                (7,'7'),(9,'m7'),(11,'m7b5')]
    else:  # mollova (s harmonickou V a vudcim dim)
        degs = [(0,'m7'),(0,'m6'),(2,'m7b5'),(3,'maj7'),(5,'m7'),
                (7,'7'),(8,'maj7'),(11,'dim7')]
    return set(((K+d) % 12, q) for d, q in degs)


def detect_progression(notes, bar=4.0, max_bars=None,
                       change_pen=0.09, diat_bonus=0.16, bass_bonus=0.10):
    end = max(o + d for o, d, p, v in notes)
    nb = int(np.ceil(end / bar))
    if max_bars: nb = min(nb, max_bars)

    # per-bar chroma + bas, a globalni chroma pro odhad toniny
    barchroma = np.zeros((nb, 12)); basspc = [None]*nb; total = np.zeros(12)
    for b in range(nb):
        ws, we = b*bar, (b+1)*bar; bw = defaultdict(float)
        for o, d, p, v in notes:
            ov = max(0.0, min(o+d, we) - max(o, ws))
            if ov > 0:
                w = ov * (v/127.0)
                barchroma[b, p % 12] += w; total[p % 12] += w; bw[p] += ov
        if bw: basspc[b] = min(bw) % 12
        s = barchroma[b].sum()
        if s > 0: barchroma[b] /= s

    key_root, mode, key_str = estimate_key(total)
    diat = diatonic_set(key_root, mode)

    # emisni skore: cosine(barchroma, template) + bonusy
    N = len(STATES)
    E = np.zeros((nb, N))
    for b in range(nb):
        cb = barchroma[b]; nb_ = np.linalg.norm(cb)
        for si, st in enumerate(STATES):
            tv = TVEC[st]
            cos = float(np.dot(cb, tv) / (nb_*np.linalg.norm(tv) + 1e-9)) if nb_ > 0 else 0
            sc = cos
            if st in diat: sc += diat_bonus
            if basspc[b] is not None and st[0] == basspc[b]: sc += bass_bonus
            E[b, si] = sc

    # Viterbi: max sum(E) - zmena penalty (+ bonus za kvartu/kvintu)
    def trans(a, b):
        if a == b: return 0.0
        cost = change_pen
        if (STATES[b][0] - STATES[a][0]) % 12 in (5, 7):  # kvarta/kvinta
            cost -= 0.05
        return cost
    # transition matica T[a,b] = naklad prechodu a->b (vektorizovane)
    roots = np.array([s[0] for s in STATES])
    same = (np.arange(N)[:, None] == np.arange(N)[None, :])
    fifth = ((roots[None, :] - roots[:, None]) % 12)
    T = np.where(same, 0.0, change_pen)
    T -= np.where(np.isin(fifth, [5, 7]) & ~same, 0.05, 0.0)

    dp = E[0].copy(); back = np.zeros((nb, N), int)
    for b in range(1, nb):
        prev = dp                          # predchozi sloupec (cteme), novy do cur
        cand = prev[:, None] - T           # cand[ps, s]
        back[b] = cand.argmax(axis=0)
        dp = cand.max(axis=0) + E[b]
        # O(nb*N^2) vektorizovane
    path = [int(np.argmax(dp))]
    for b in range(nb-1, 0, -1):
        path.append(int(back[b, path[-1]]))
    path = path[::-1]
    prog = [STATES[i] for i in path]
    return prog, key_str


if __name__ == "__main__":
    import sys, os
    HERE = os.path.dirname(__file__)
    sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))
    from evans_drill import load_notes
    notes = load_notes(sys.argv[1])
    prog, key = detect_progression(notes, max_bars=int(sys.argv[2]) if len(sys.argv)>2 else None)
    print(f"tonina: {key}")
    print("progrese: " + " | ".join(f"{PC[r]}{q}" for r, q in prog))
