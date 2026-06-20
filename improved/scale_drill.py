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


def drill_line(progression, model=None, kind='auto', rh_lo=60, rh_hi=86, npb=8,
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
        if gts:                                  # start dle směru: ↑ startuj dole, ↓ nahoře
            span = rh_hi - rh_lo
            if direction > 0:
                zone = [g for g in gts if g <= rh_lo + span * 0.45] or gts
            else:
                zone = [g for g in gts if g >= rh_lo + span * 0.55] or gts
            start = min(zone, key=lambda x: abs(x - prev_last))
        else:
            start = scale[idx(prev_last)]
        ci = idx(start)
        notes = [scale[ci]]
        for k in range(1, npb):
            move = direction * (2 if rng.random() < variation else 1)  # převážně krok, občas tercie
            ni = max(0, min(len(scale) - 1, ci + move))
            cand = scale[ni]
            # anti opakování / anti a-b-a oscilace (to byl ten nejazzový vzor)
            if cand == notes[-1] or (len(notes) >= 2 and cand == notes[-2]):
                ni = max(0, min(len(scale) - 1, ci + direction * 2))   # skok dál ve směru
                cand = scale[ni]
                if cand == notes[-1] or (len(notes) >= 2 and cand == notes[-2]):
                    ni = max(0, min(len(scale) - 1, ci - direction))   # u kraje jednorázový obrat
                    cand = scale[ni]
            ci = ni
            notes.append(cand)
        for k, p in enumerate(notes):
            line.append((i * bpc + k * (bpc / npb), (bpc / npb) * 0.92, p))
        prev_last = notes[-1]
        direction = -direction              # střídej nahoru/dolů po taktech
    return line


def render_drill(progression, voicings, line, out, bpm=116, bpc=4.0,
                 swing=0.11, accents=True):
    """Render drilu se SWING feelem: triolové dlouhá-krátká osminky + akcenty
    (beat 1 = landing silnější, offbeaty lehčí). LH = bas + akord/takt (sustain)."""
    import mido
    tpb = 240
    mid = mido.MidiFile(type=1); mid.ticks_per_beat = tpb
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=int(60000000/bpm), time=0))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    trB = mido.MidiTrack(); trC = mido.MidiTrack(); trD = mido.MidiTrack()
    trB.append(mido.MetaMessage('track_name', name='Bass', time=0))
    trC.append(mido.MetaMessage('track_name', name='Chords', time=0))
    trD.append(mido.MetaMessage('track_name', name='Drill', time=0))
    mid.tracks += [trB, trC, trD]
    evB, evC, evD = [], [], []
    for i, (bass, voic) in enumerate(voicings):
        t0 = i * bpc
        evB.append((t0, 1, [bass], 56)); evB.append((t0 + bpc*0.95, 0, [bass], 0))
        evC.append((t0, 1, voic, 50)); evC.append((t0 + bpc*0.95, 0, voic, 0))
    for o, d, p in line:
        bf = o - int(o)                                  # pozice v rámci doby
        offbeat = abs(bf - 0.5) < 1e-3
        if offbeat:                                      # "a" -> swing pozdě, kratší, lehčí
            on = o + swing; dur = max(0.12, 0.5 - swing); vel = 78 if accents else 90
        else:                                            # doba -> delší, plnější
            on = o; dur = 0.5 + swing * 0.8
            vel = 104 if (accents and abs(o % bpc) < 1e-3) else (96 if accents else 90)
        evD.append((on, 1, [p], vel)); evD.append((on + dur, 0, [p], 0))
    for tr, ev in [(trB, evB), (trC, evC), (trD, evD)]:
        flat = []
        for tt, typ, ps, vel in ev:
            for pp in ps:
                flat.append((tt, typ, pp, vel))
        flat.sort(key=lambda x: (x[0], x[1])); last = 0
        for tt, typ, pp, vel in flat:
            dt = max(0, int(round((tt - last) * tpb))); last = tt
            tr.append(mido.Message('note_on' if typ else 'note_off',
                                   note=int(max(1, min(127, pp))),
                                   velocity=vel if typ else 0, time=dt))
    mid.save(out)


def make_drill(progression, out, kind='auto', bpm=120, seed=1, model=None, swing=0.11):
    voic = generate_voicings(progression, color=False, center=52)   # LH níž, dril nad
    line = drill_line(progression, kind=kind, seed=seed)
    render_drill(progression, voic, line, out, bpm=bpm, swing=swing)
    return line


# ---------------------------------------------------------------------------
# "TRIPLETS IN FOUR" -- 4-notová sestupná TERCOVÁ buňka v TRIOLOVÉM rytmu.
# Protože je buňka 4-notová a rytmus triolový (3 noty/dobu), buňka FÁZUJE proti
# 4/4 (3 proti 4) -> přízvuky dosedají pokaždé na jiný tón buňky = sofistikovaný
# evansovský feel. Začátky buněk stoupají po terciích; na začátku akordu
# chromatický náběh (půltón zdola); barvy z charakteristické jazzové stupnice
# (altered na dominantě, dorská na m7, ...). Landing = guide tone akordu.
# ---------------------------------------------------------------------------
JAZZ_COLOR = {           # charakteristická jazzová stupnice dle kvality
    'maj7': [0,2,4,5,7,9,11], 'maj': [0,2,4,5,7,9,11], '6': [0,2,4,5,7,9,11],
    'm7': [0,2,3,5,7,9,10], 'min': [0,2,3,5,7,9,10], 'm6': [0,2,3,5,7,9,11],
    '7': [0,1,3,4,6,8,10],                              # altered (chromatika)
    'sus': [0,2,5,7,9,10], 'm7b5': [0,1,3,5,6,8,10],
    'dim7': [0,2,3,5,6,8,9,11], 'mMaj7': [0,2,3,5,7,9,11], 'aug': [0,2,4,6,8,10],
}


def color_scale(r, q, lo, hi):
    pcs = set((r + o) % 12 for o in JAZZ_COLOR.get(q, [0,2,4,5,7,9,10,11]))
    return sorted(p for p in range(lo, hi + 1) if p % 12 in pcs)


def triplets_in_four(progression, lo=55, hi=88, bpc=4.0, npb=12, seed=None):
    """Sestupné tercové 4-notové buňky v triolách (3/dobu, 12/takt). Začátky
    buněk stoupají po terciích, na začátku akordu chromatický náběh, barvy z
    charakteristické jazzové stupnice. Vrací [(onset, dur, pitch), ...]."""
    line = []
    for i, (r, q) in enumerate(progression):
        sc = color_scale(r, q, lo, hi)
        if not sc:
            continue
        idx = lambda p: min(range(len(sc)), key=lambda k: abs(sc[k] - p))
        gt = guide_pitches(r, q, lo, hi)
        base = idx(min(gt, key=lambda x: abs(x - (lo + 8)))) if gt else len(sc) // 3
        for g in range(npb // 4):                  # 3 buňky/takt
            top = min(len(sc) - 1, base + g * 2 + 6)
            t = sc[top]
            d2, d4, d6 = sc[max(0, top-2)], sc[max(0, top-4)], sc[max(0, top-6)]
            grp = [t - 1, t, d2, d4] if g == 0 else [t, d2, d4, d6]  # g0 = chromat. náběh
            for j, p in enumerate(grp):
                n = g * 4 + j
                line.append((i * bpc + n / 3.0, (1/3.0) * 0.9, p))
    return line


def render_line(progression, voicings, line, out, bpm=104, bpc=4.0):
    """Obecný render: bas + akord/takt (sustain) + pravá ruka (dle vlastních
    nástupů/délek linky), lehký akcent na beat 1."""
    import mido
    tpb = 240; mid = mido.MidiFile(type=1); mid.ticks_per_beat = tpb
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=int(60000000/bpm), time=0))
    trB = mido.MidiTrack(); trC = mido.MidiTrack(); trD = mido.MidiTrack()
    mid.tracks += [trB, trC, trD]
    evB, evC, evD = [], [], []
    for i, (bass, vo) in enumerate(voicings):
        t0 = i * bpc
        evB.append((t0, 1, [bass], 54)); evB.append((t0 + bpc*0.97, 0, [bass], 0))
        evC.append((t0, 1, vo, 46)); evC.append((t0 + bpc*0.97, 0, vo, 0))
    for o, d, p in line:
        vel = 100 if abs(o % bpc) < 1e-3 else 90
        evD.append((o, 1, [p], vel)); evD.append((o + d, 0, [p], 0))
    for tr, ev in [(trB, evB), (trC, evC), (trD, evD)]:
        fl = [(tt, ty, pp, ve) for tt, ty, ps, ve in ev for pp in ps]
        fl.sort(key=lambda x: (x[0], x[1])); last = 0
        for tt, ty, pp, ve in fl:
            dt = max(0, int(round((tt - last) * tpb))); last = tt
            tr.append(mido.Message('note_on' if ty else 'note_off',
                                   note=int(max(1, min(127, pp))),
                                   velocity=ve if ty else 0, time=dt))
    mid.save(out)


def make_triplets_in_four(progression, out, bpm=104, seed=1):
    voic = generate_voicings(progression, color=False, center=48)
    line = triplets_in_four(progression, seed=seed)
    render_line(progression, voic, line, out, bpm=bpm)
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
