#!/usr/bin/env python3
"""
scale_drill.py -- HYBRID: stupnicový dril pro cvičení, jazzově zabarvený.

Cíl: bass + stupnicový dril (8 osmin/takt, 1 akord/takt). Pro každý akord se
mění stupnice dle CHORD-SCALE teorie (bebop / pentatonika -- NE chromatika).
Kontura běhu je vedená naučeným Evansovým pohybem (Markov), a běh se vždy
ROZVÁDÍ na guide-tone (3./7.) následujícího akordu (správný landing note),
takže cvičíš stupnice i správné spojování přes změny akordů.

Spuštění:
    python improved/scale_drill.py --scale bebop --render out.mid
    python improved/scale_drill.py --scale pentatonic --key C
"""
import os, sys, random, argparse
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

from evans_drill import BEBOP, SEV, PC, nm
from voicings import generate_voicings
from melody_top import render as render_full
import melody_markov as mm
import chord_markov as cm

# pentatoniky dle kvality (jinak fallback na bebop)
PENTA = {
    'maj7': [0,2,4,7,9], 'maj': [0,2,4,7,9], '6': [0,2,4,7,9],
    'm7': [0,3,5,7,10], 'min': [0,3,5,7,10], 'm6': [0,3,5,7,9],
    '7': [0,2,4,7,10], 'sus': [0,2,5,7,10],
}


# paleta jazzových stupnic dle kvality (auto = střídá se -> pestré barvy)
SCALES = {
    'maj7': [[0,2,4,5,7,9,11], [0,2,4,6,7,9,11], [0,2,4,7,9], [0,2,4,5,7,8,9,11]],
    'maj':  [[0,2,4,5,7,9,11], [0,2,4,6,7,9,11], [0,2,4,7,9]],
    '6':    [[0,2,4,7,9], [0,2,4,5,7,9,11], [0,2,4,5,7,8,9,11]],
    'm7':   [[0,2,3,5,7,9,10], [0,3,5,7,10], [0,2,3,4,5,7,9,10]],
    'min':  [[0,2,3,5,7,9,10], [0,3,5,7,10]],
    'm6':   [[0,2,3,5,7,9,11], [0,2,3,5,7,9,10]],
    '7':    [[0,2,4,5,7,9,10], [0,2,4,6,7,9,10], [0,1,3,4,6,8,10],
             [0,2,4,5,7,9,10,11], [0,1,3,4,6,7,9,10]],
    'sus':  [[0,2,4,5,7,9,10], [0,2,5,7,10]],
    'm7b5': [[0,1,3,5,6,8,10], [0,2,3,5,6,8,10]],
    'dim7': [[0,2,3,5,6,8,9,11]],
    'mMaj7':[[0,2,3,5,7,9,11]],
    'aug':  [[0,2,4,6,8,10]],
}


def jazz_scale(r, q, lo, hi, kind, rng=None):
    if kind == 'bebop':
        offs = BEBOP.get(q, [0,2,4,5,7,9,10,11])
    elif kind == 'pentatonic':
        offs = PENTA.get(q, BEBOP.get(q, [0,2,4,5,7,9,10,11]))
    else:  # auto: vyber z palety -> různé jazzové barvy po taktech
        pool = SCALES.get(q, [BEBOP.get(q, [0,2,4,5,7,9,10,11])])
        offs = (rng or random).choice(pool)
    pcs = set((r + o) % 12 for o in offs)
    return sorted(p for p in range(lo, hi + 1) if p % 12 in pcs)


def guide_tone_pcs(r, q):
    offs = SEV.get(q, [0, 4, 7, 10])      # [1, 3, 5, 7]
    return {(r + offs[1]) % 12, (r + offs[3]) % 12}   # 3. a 7.


def nearest_guide(r, q, near, lo, hi):
    gt = guide_tone_pcs(r, q)
    cands = [p for p in range(lo, hi + 1) if p % 12 in gt]
    return min(cands, key=lambda x: abs(x - near)) if cands else near


def chord_color_pitches(r, q, lo, hi):
    offs = list(SEV.get(q, [0, 4, 7, 10])) + [2]      # akordové tóny + 9
    if q == '7':
        offs += [9]                                    # +13 u dominanty
    pcs = set((r + o) % 12 for o in offs)
    return sorted(p for p in range(lo, hi + 1) if p % 12 in pcs)


def guide_pitches(r, q, lo, hi):
    gt = guide_tone_pcs(r, q)
    return sorted(p for p in range(lo, hi + 1) if p % 12 in gt)


def _pick_near(cands, near, model, ctx, rng, temperature, avoid=None):
    """Markovem řízený výběr anchoru: cíl = předchozí + naučený interval, snap na kandidáta."""
    if not cands:
        return near
    semi, _ = model.sample(tuple(ctx[-model.order:]), temperature, rng)
    ctx.append((semi, _))
    target = near + semi
    pool = [c for c in cands if c != avoid] or cands
    return min(pool, key=lambda x: abs(x - target))


def drill_line(progression, model=None, kind='auto', rh_lo=60, rh_hi=84, npb=8,
               bpc=4.0, variation=0.28, seed=None, start_dir=1):
    """Nahoru-dolů a jeho variace: takty se střídají vzestupně/sestupně.
    Každý takt běží jazzovou stupnici akordu v daném směru (s občasným skokem
    nebo krátkým obratem = variace). Beat 1 = guide tone (landing), směr se po
    taktu otočí. Stupnice se mění dle akordu (auto = pestrá paleta)."""
    rng = random.Random(seed)
    line = []
    direction = start_dir
    prev_last = rh_lo + 3                      # start nízko -> 1. takt má kam stoupat
    for i, (r, q) in enumerate(progression):
        scale = jazz_scale(r, q, rh_lo - 1, rh_hi + 1, kind, rng)
        if not scale:
            continue
        idx = lambda p: min(range(len(scale)), key=lambda k: abs(scale[k] - p))
        gts = guide_pitches(r, q, rh_lo, rh_hi)
        start = min(gts, key=lambda x: abs(x - prev_last)) if gts else scale[idx(prev_last)]
        ci = idx(start)
        notes = [scale[ci]]
        for k in range(1, npb):
            roll = rng.random()
            if roll < 1 - variation:       move = direction        # krok ve směru
            elif roll < 1 - variation / 3: move = direction * 2     # skok (terc)
            else:                          move = -direction        # krátký obrat (soused)
            ni = ci + move
            if ni < 0 or ni >= len(scale):                          # odraz na kraji pásma
                ni = ci - move
            ci = max(0, min(len(scale) - 1, ni))
            notes.append(scale[ci])
        for k, p in enumerate(notes):
            line.append((i * bpc + k * (bpc / npb), (bpc / npb) * 0.92, p))
        prev_last = notes[-1]
        direction = -direction              # střídej nahoru/dolů po taktech
    return line


def make_drill(progression, out, kind='auto', bpm=120, seed=1, model=None):
    model = model or mm.get_model('evans')
    voic = generate_voicings(progression, color=False, center=52)   # LH níž, dril nad
    line = drill_line(progression, model, kind=kind, seed=seed)
    render_full(progression, voic, line, out, bpm=bpm, comp="sustain")
    return line


# pár cvičných progresí (4-taktové buňky)
DRILLS = {
    "iiVI": [(2,'m7'), (7,'7'), (0,'maj7'), (0,'maj7')],
    "iiVI_turn": [(2,'m7'), (7,'7'), (0,'maj7'), (9,'7')],
    "minor_iiVi": [(11,'m7b5'), (4,'7'), (9,'m7'), (9,'m7')],
    "rhythm_a": [(0,'maj7'), (9,'7'), (2,'m7'), (7,'7')],
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="auto", choices=["bebop", "pentatonic", "auto"])
    ap.add_argument("--drill", default="iiVI_turn", choices=list(DRILLS))
    ap.add_argument("--bpm", type=int, default=120)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--render", default="outputs_drill/drill_full.mid")
    a = ap.parse_args()
    prog = DRILLS[a.drill]
    print("progrese:", " | ".join(f"{PC[r]}{q}" for r, q in prog))
    os.makedirs(os.path.dirname(a.render), exist_ok=True)
    line = make_drill(prog, a.render, kind=a.scale, bpm=a.bpm, seed=a.seed)
    print(f"stupnice: {a.scale} | {len(line)} tónů | -> {a.render}")
