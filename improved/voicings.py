#!/usr/bin/env python3
"""
voicings.py -- v4: harmonicky engine (Evansovy rootless voicingy + voice-leading).

Cil (dle feedbacku): nejdriv aby HARMONICKE PRECHODY mely hlavu a patu, bez
vrchni melodie. To, co u Evanse drzi pohromade, je vedeni hlasu mezi barevnymi
bezzakladovymi voicingy -- ne bravurni pravacka.

Princip:
  - kazdy akord = 4-tonovy ROOTLESS voicing (vynechan zakladni ton, pridana
    9/13/#11 barva) -- viz ROOTLESS tabulka nize,
  - VOICE-LEADING: dalsi voicing se vybere tak, aby se hlasy posunuly co nejmin
    (brute-force pres prirazeni 4 hlasu, drzi spolecne tony),
  - REGISTR: vrchni ton voicingu mezi ~C4 a C5 (Evansovo pasmo), bas zvlast dole,
  - vrchni tony voicingu samy tvori melodickou linku (to je pointa).

Zdroj voicingu: rootless A/B formy (Bill Evans / Mark Levine).
"""
import os, sys, glob, itertools
HERE = os.path.dirname(__file__)
CONCEPT = os.path.join(HERE, "..", "concept", "evans_melody_gen")
sys.path.insert(0, CONCEPT); sys.path.insert(0, os.path.join(CONCEPT, "src"))

import mido
from evans_drill import PC, nm

# rootless 4-tonove voicingy: offsety v pultonech od ZAKLADU (root vynechan,
# krome m7b5/dim7, kde se root bezne pridava). Pojmenovani kvalit dle evans_drill.
ROOTLESS = {
    'maj':  [4, 7, 11, 2],    # 3 5 7 9
    'maj7': [4, 7, 11, 2],    # 3 5 7 9
    '6':    [4, 7, 9, 2],     # 3 5 6 9
    'min':  [3, 7, 10, 2],    # b3 5 b7 9
    'm7':   [3, 7, 10, 2],    # b3 5 b7 9
    'm6':   [3, 7, 9, 2],     # b3 5 6 9
    '7':    [4, 10, 2, 9],    # 3 b7 9 13
    'sus':  [5, 10, 2, 7],    # 4 b7 9 5
    'm7b5': [3, 6, 10, 0],    # b3 b5 b7 R
    'dim7': [3, 6, 9, 0],     # b3 b5 6 R
    'mMaj7':[3, 7, 11, 2],    # b3 5 7 9
    'aug':  [4, 8, 11, 2],    # 3 #5 7 9
}
# barevna varianta (vic Evans: dominanty alterovane, maj s #11/6, atd.)
ROOTLESS_COLOR = {
    '7':    [4, 10, 1, 8],    # 3 b7 b9 b13  (alterovana dominanta)
    'maj7': [4, 6, 11, 2],    # 3 #11 7 9    (lydicky)
    '6':    [4, 6, 9, 2],     # 3 #11 6 9
}

WIN_LO, WIN_HI = 52, 76       # pasmo voicingu (vrchni ton ~C4..C5)


def pcs_for(root, quality, color=False):
    table = ROOTLESS.copy()
    if color:
        table.update(ROOTLESS_COLOR)
    offs = table.get(quality, ROOTLESS['maj7'])
    seen, out = set(), []
    for o in offs:
        pc = (root + o) % 12
        if pc not in seen:
            seen.add(pc); out.append(pc)
    return out

def place_near(pc, target):
    d = (pc - target) % 12
    return target + (d - 12 if d > 6 else d)

def build_close(pcs, center=63):
    pcs = sorted(pcs)
    voic = [48 + pcs[0]]
    for pc in pcs[1:]:
        nx = voic[-1] + ((pc - voic[-1]) % 12)
        if nx == voic[-1]:
            nx += 12
        voic.append(nx)
    while sum(voic)/len(voic) < center - 4:
        voic = [v + 12 for v in voic]
    while sum(voic)/len(voic) > center + 4:
        voic = [v - 12 for v in voic]
    return sorted(voic)

def voice_lead(prev, pcs):
    """Vyber rozlozeni pcs do 4 vysek, ktere se nejmin pohne od prev (sorted)."""
    best, best_cost = None, 1e9
    for perm in itertools.permutations(pcs):
        placed = [place_near(perm[i], prev[i]) for i in range(4)]
        if len(set(placed)) < 4:
            continue
        if any(p < WIN_LO - 3 or p > WIN_HI + 3 for p in placed):
            continue
        cost = sum(abs(placed[i] - prev[i]) for i in range(4))
        if cost < best_cost:
            best_cost, best = cost, sorted(placed)
    return best or build_close(pcs)

def generate_voicings(progression, color=False, center=63):
    voicings, prev = [], None
    for root, q in progression:
        pcs = pcs_for(root, q, color)
        while len(pcs) < 4:                 # pojistka: doplnit kvintou/oktavou
            pcs.append((pcs[0] + 7) % 12)
        pcs = pcs[:4]
        voic = build_close(pcs, center) if prev is None else voice_lead(prev, pcs)
        bass = 36 + (root % 12)             # zakladni ton dole (C2..B2)
        voicings.append((bass, voic))
        prev = voic
    return voicings


def render(progression, voicings, path, bpm=112, beats_per_chord=4.0,
           rearticulate=True):
    tpb = 240
    mid = mido.MidiFile(type=1); mid.ticks_per_beat = tpb
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=int(60000000/bpm), time=0))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    trL = mido.MidiTrack(); trL.append(mido.MetaMessage('track_name', name='Bass', time=0))
    trR = mido.MidiTrack(); trR.append(mido.MetaMessage('track_name', name='Voicings', time=0))
    mid.tracks += [trL, trR]
    evB, evV = [], []
    BAR = beats_per_chord
    for i, (bass, voic) in enumerate(voicings):
        t0 = i * BAR
        evB.append((t0, 1, bass)); evB.append((t0 + BAR*0.95, 0, bass))
        # voicing: drz cely takt, jemne re-artikuluj na "3"
        evV.append((t0, 1, voic)); evV.append((t0 + BAR*0.5*0.97, 0, voic))
        if rearticulate:
            evV.append((t0 + BAR*0.5, 1, voic)); evV.append((t0 + BAR*0.95, 0, voic))
        else:
            evV[-1] = (t0 + BAR*0.95, 0, voic)
    def flush(tr, events, vel):
        flat = []
        for tt, typ, payload in events:
            ps = payload if isinstance(payload, list) else [payload]
            for p in ps:
                flat.append((tt, typ, p))
        flat.sort(key=lambda x: (x[0], x[1])); last = 0
        for tt, typ, p in flat:
            dt = max(0, int(round((tt - last) * tpb))); last = tt
            tr.append(mido.Message('note_on' if typ else 'note_off',
                                   note=int(max(1, min(127, p))),
                                   velocity=vel if typ else 0, time=dt))
    flush(trL, evB, 60)
    flush(trR, evV, 78)
    mid.save(path)


def show(progression, voicings):
    """Vypis voicingu + vrchni linky (ta tvori melodii)."""
    top = []
    for (root, q), (bass, voic) in zip(progression, voicings):
        names = " ".join(nm(p) for p in voic)
        top.append(voic[-1])
        print(f"  {PC[root]}{q:5s}  bas {nm(bass):4s} | {names:20s}  vrch {nm(voic[-1])}")
    print("  vrchni linka:", " ".join(nm(p) for p in top))


from melody_v2 import PROGRESSIONS

if __name__ == "__main__":
    out_dir = os.path.join(HERE, "..", "outputs_v4")
    os.makedirs(out_dir, exist_ok=True)
    for name, bpm in [("autumn_leaves", 112), ("iiVI_C", 104), ("nardis_A", 92)]:
        prog = PROGRESSIONS[name]
        print(f"\n== {name} ==")
        for tag, color, center in [("a", False, 63), ("b", True, 67)]:
            voic = generate_voicings(prog, color=color, center=center)
            out = os.path.join(out_dir, f"{name}_{tag}.mid")
            render(prog, voic, out, bpm=bpm)
            print(f"  [{tag}] color={color} center={center} -> {os.path.basename(out)}")
            if tag == "a":
                show(prog, voic)
    print(f"\nHotovo -> {out_dir}\\")
