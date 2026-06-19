#!/usr/bin/env python3
"""
melody_top.py -- v5: vysoka pravacka melodie POSTAVENA NA voice-led kostre.

Navaznost: v4 (voicings.py) da harmonii, ktera drzi pohromade, a jeji vrchni
tony tvori souvislou linku. Drivejsi melodie nedrzela, protoze nemela o co se
oprit. v5 pouzije voice-led vrchni linku jako KOSTRU (cilove tony) a jen ji
ozdobi ve stylu Evanse:
  - kotva = akordovy/barevny ton vysoko (C5+), vedena plynule od predchozi,
  - do dalsi kotvy nabeh krokem + chromaticky pridrzny ton (enclosure),
  - fraze po 4 taktech, ctvrty takt = nadech (jen kotva, bez behu),
  - pod tim hraje comp z v4 (rootless voicingy), melodie je jasne nad nim.
"""
import os, sys, random
HERE = os.path.dirname(__file__)
CONCEPT = os.path.join(HERE, "..", "concept", "evans_melody_gen")
sys.path.insert(0, CONCEPT); sys.path.insert(0, os.path.join(CONCEPT, "src"))

import mido
from evans_drill import SEV, BEBOP, nm
from voicings import generate_voicings, pcs_for
from melody_v2 import PROGRESSIONS, chord_tone_pitches

MLO, MHI = 72, 91          # melodie C5..G6


def scale_pitches(root, quality, lo, hi):
    pcs = set((root + o) % 12 for o in BEBOP.get(quality, [0,2,4,5,7,9,10,11]))
    return sorted(p for p in range(lo, hi+1) if p % 12 in pcs)

def anchor_pitches(root, quality, lo, hi):
    """Kotvy = akordove tony + 9 (barva), vysoko."""
    offs = list(SEV.get(quality, [0,4,7,10])) + [2]      # +9
    pcs = set((root + o) % 12 for o in offs)
    return sorted(p for p in range(lo, hi+1) if p % 12 in pcs)


def build_anchors(progression, mlo, mhi, seed):
    """Kotvy chodi SMEROVE (arpeggio/linka) -- i nad statickou harmonii se
    melodie hybe misto sezeni na stejnem tonu. Smer se otaci na kraji pasma."""
    rng = random.Random(seed)
    anchors, prev, prev2 = [], None, None
    direction = rng.choice([-1, 1])
    center = (mlo + mhi) // 2
    for root, q in progression:
        cands = anchor_pitches(root, q, mlo, mhi)
        cands = [c for c in cands if c != prev and c != prev2] or cands
        if prev is None:
            a = min(cands, key=lambda x: abs(x - center))
        else:
            ahead = [c for c in cands if (c > prev if direction > 0 else c < prev)]
            if not ahead:                       # na kraji pasma se otoc
                direction = -direction
                ahead = [c for c in cands if (c > prev if direction > 0 else c < prev)]
            pool = sorted(ahead or cands, key=lambda x: abs(x - prev))
            a = rng.choice(pool[:2]) if len(pool) >= 2 else pool[0]
            if a >= mhi - 2: direction = -1
            elif a <= mlo + 2: direction = 1
        anchors.append(a); prev2 = prev; prev = a
    return anchors


def break_repeats(melody, progression, bpc=4.0):
    """Globalni pojistka: zadny ton 2x po sobe a zadna a-b-a oscilace.
    Opakovani nahradi nejblizsim jinym tonem stupnice (preferuje krok)."""
    out = []
    for o, d, p in sorted(melody):
        ci = min(int(o // bpc), len(progression) - 1)
        r, q = progression[ci]
        scl = scale_pitches(r, q, MLO - 3, MHI)
        is_db = (o - ci * bpc) < 0.3
        last = out[-1][2] if out else None
        last2 = out[-2][2] if len(out) >= 2 else None
        if p == last or p == last2:
            # na tezke dobe ber nahradu z AKORDOVYCH tonu (drz harmonii),
            # jinak ze stupnice
            pool = chord_tone_pitches(r, q, MLO - 3, MHI) if is_db else scl
            alts = [x for x in pool if x != last and x != last2]
            if not alts:
                alts = [x for x in scl if x != last and x != last2]
            if alts:
                ref = last if last is not None else p
                p = min(alts, key=lambda x: (abs(x - ref), abs(x - p)))
        out.append((o, d, p))
    return out


def make_melody(progression, beats_per_chord=4.0, mlo=MLO, mhi=MHI, seed=1,
                density=0.8):
    rng = random.Random(seed * 7 + 1)
    anchors = build_anchors(progression, mlo, mhi, seed)
    notes = []
    n = len(progression)
    for i, (root, q) in enumerate(progression):
        t0 = i * beats_per_chord
        a = anchors[i]
        breathe = (i % 4 == 3)                 # ctvrty takt = nadech
        # kotva na "1" (nebo lehka synkopa)
        notes.append((t0, 1.4 if breathe else 0.9, a))
        if breathe or i+1 >= n or rng.random() > density:
            continue
        b = anchors[i+1]
        scale = scale_pitches(root, q, mlo-2, mhi)
        # nabeh: kroky ze 'a' smerem k 'b' na dobach 2.5/3/3.5, posledni = pridrzny
        positions = [2.0, 2.5, 3.0, 3.5]
        rng.shuffle(positions); positions = sorted(positions[:rng.choice([2,3,3,4])])
        direction = 1 if b >= a else -1
        cur = a
        for j, pos in enumerate(positions):
            if j == len(positions) - 1:
                pitch = b - direction          # chromaticky/krokovy pridrzny do 'b'
            else:
                ahead = [p for p in scale if (p > cur if direction > 0 else p < cur)]
                pitch = min(ahead, key=lambda x: abs(x-cur)) if ahead else cur
            pitch = max(mlo-2, min(mhi, pitch))
            notes.append((t0 + pos, 0.45, pitch))
            cur = pitch
    return notes, anchors


def declash(melody, voicings, progression, bpc=4.0):
    """Odstrani 'skripani': (a) dlouhe tony mimo akordovy ton snapne na akordovy
    ton, (b) tony tvorici malou sekundu/nonu s comp voicingem posune o pulton."""
    out = []
    for o, d, p in melody:
        ci = min(int(o // bpc), len(progression) - 1)
        r, q = progression[ci]
        cts = chord_tone_pitches(r, q, MLO - 3, MHI)
        scl = scale_pitches(r, q, MLO - 3, MHI)
        voic = voicings[ci][1] if ci < len(voicings) else []
        is_db = (o - ci * bpc) < 0.3          # nota na "1" akordu
        def clashes(x):
            return any((x - v) % 12 in (1, 11) for v in voic)
        # dlouhy ton -> akordovy ton
        if d >= 1.0 and p % 12 not in {c % 12 for c in cts}:
            p = min(cts, key=lambda x: abs(x - p)) if cts else p
        # m2/m9 stret s compem -> na tezke dobe z AKORDOVYCH tonu, jinak ze stupnice
        if d >= 0.4 and clashes(p):
            pool = [x for x in (cts if is_db else scl) if not clashes(x)]
            if not pool:
                pool = [x for x in scl if not clashes(x)]
            if pool:
                p = min(pool, key=lambda x: abs(x - p))
        out.append((o, d, p))
    return out


def render(progression, voicings, melody, path, bpm=110, beats_per_chord=4.0,
           swing=0.1):
    tpb = 240
    mid = mido.MidiFile(type=1); mid.ticks_per_beat = tpb
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=int(60000000/bpm), time=0))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    trB = mido.MidiTrack(); trB.append(mido.MetaMessage('track_name', name='Bass', time=0))
    trV = mido.MidiTrack(); trV.append(mido.MetaMessage('track_name', name='Voicings', time=0))
    trM = mido.MidiTrack(); trM.append(mido.MetaMessage('track_name', name='Melody', time=0))
    mid.tracks += [trB, trV, trM]
    BAR = beats_per_chord
    evB, evV, evM = [], [], []
    for i, (bass, voic) in enumerate(voicings):
        t0 = i * BAR
        evB.append((t0, 1, [bass])); evB.append((t0+BAR*0.95, 0, [bass]))
        evV.append((t0, 1, voic)); evV.append((t0+BAR*0.95, 0, voic))
    def sw(t):
        return t + (swing if abs((t-int(t))-0.5) < 1e-3 else 0.0)
    for o, d, p in melody:
        oo = sw(o)
        evM.append((oo, 1, [p])); evM.append((oo+d, 0, [p]))
    def flush(tr, events, vel):
        flat = []
        for tt, typ, ps in events:
            for p in ps: flat.append((tt, typ, p))
        flat.sort(key=lambda x: (x[0], x[1])); last = 0
        for tt, typ, p in flat:
            dt = max(0, int(round((tt-last)*tpb))); last = tt
            tr.append(mido.Message('note_on' if typ else 'note_off',
                                   note=int(max(1,min(127,p))),
                                   velocity=vel if typ else 0, time=dt))
    flush(trB, evB, 52); flush(trV, evV, 66); flush(trM, evM, 100)
    mid.save(path)


FORMS_BPM = {"autumn_leaves": 110, "nardis_A": 90, "iiVI_C": 100}

if __name__ == "__main__":
    out_dir = os.path.join(HERE, "..", "outputs_v5")
    os.makedirs(out_dir, exist_ok=True)
    for name in ("autumn_leaves", "nardis_A", "iiVI_C"):
        prog = PROGRESSIONS[name]
        bpm = FORMS_BPM[name]
        voic = generate_voicings(prog, color=False, center=60)
        print(f"\n== {name} ==")
        for k in (1, 2, 3):
            mel, anchors = make_melody(prog, seed=k)
            out = os.path.join(out_dir, f"{name}_m{k}.mid")
            render(prog, voic, mel, out, bpm=bpm)
            print(f"  m{k}: {os.path.basename(out)}  ({len(mel)} tonu melodie, "
                  f"kotvy: {' '.join(nm(a) for a in anchors[:8])}...)")
    print(f"\nHotovo -> {out_dir}\\")
