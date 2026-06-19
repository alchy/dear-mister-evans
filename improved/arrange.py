#!/usr/bin/env python3
"""
arrange.py -- v7: GENERALIZACE. Z libovolneho MIDI vyrob zjednodusenou
Evansovskou verzi (rootless voicingy + voice-leading + motivicka melodie).

Pipeline:
    libovolne MIDI
       -> detekce akordu PO TAKTECH (chroma + bas, omezeny slovnik)
       -> auto-detekce opakujicich se 4-taktovych bloku (forma -> motiv se vraci)
       -> voicingy (v4) + motivicka melodie (v6) + render (v5)
       -> outputs_arr/<jmeno>.mid  (+ harmony-only varianta)

Pouziti:
    python improved/arrange.py "cesta/k/souboru.mid"
    python improved/arrange.py "cesta/k/souboru.mid" --bars 32 --bpm 120 --no-melody

Pozn.: kvalita zavisi na cistote vstupu. Husta solova klavirni faktura
(melodie+doprovod v jednom kanalu) je pro detekci tezka -> vystup je orientacni.
Cistsi vstup (lead-sheet / jednodussi aranz) = lepsi vysledek.
"""
import os, sys, argparse
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(__file__)
CONCEPT = os.path.join(HERE, "..", "concept", "evans_melody_gen")
sys.path.insert(0, CONCEPT); sys.path.insert(0, os.path.join(CONCEPT, "src"))

from evans_drill import load_notes, PC, nm
from voicings import generate_voicings, render as render_harmony
from melody_top import (make_melody, render as render_full, declash,
                        break_repeats, MLO, MHI)
from motif import generate_motivic

# omezeny slovnik kvalit (bez augMaj7/mMaj7 sumu) + jejich sablony
QUAL_TEMPL = {
    'maj7': [0,4,7,11], '7': [0,4,7,10], 'm7': [0,3,7,10],
    'm7b5': [0,3,6,10], 'dim7': [0,3,6,9], 'm6': [0,3,7,9], '6': [0,4,7,9],
}
def _tvec(ints):
    v = np.zeros(12)
    for i in ints: v[i % 12] = 1.0
    return v / np.linalg.norm(v)
_CH = [(r, q) for q in QUAL_TEMPL for r in range(12)]
_TV = np.array([np.roll(_tvec(QUAL_TEMPL[q]), r) for (r, q) in _CH])


def progression_per_bar(notes, bar=4.0, max_bars=None):
    """Detekuj 1 akord na takt: chroma vazena trvanim+velocity, bonus za bas."""
    end = max(o + d for o, d, p, v in notes)
    nb = int(np.ceil(end / bar))
    if max_bars: nb = min(nb, max_bars)
    prog = []
    for b in range(nb):
        ws, we = b * bar, (b + 1) * bar
        chroma = np.zeros(12); bassw = defaultdict(float)
        for o, d, p, v in notes:
            ov = max(0.0, min(o + d, we) - max(o, ws))
            if ov > 0:
                chroma[p % 12] += ov * (v / 127.0)
                bassw[p] += ov
        if chroma.sum() == 0:
            prog.append(prog[-1] if prog else (0, 'm7')); continue
        chroma /= chroma.sum()
        E = _TV @ chroma
        if bassw:
            bass_pc = min(bassw) % 12               # nejnizsi znejici ton
            for ci, (r, q) in enumerate(_CH):
                if r == bass_pc: E[ci] += 0.12
        r, q = _CH[int(E.argmax())]
        prog.append((r, q))
    # lehke vyhlazeni: osamoceny akord mezi dvema stejnymi sousedy prepis
    for i in range(1, len(prog) - 1):
        if prog[i-1] == prog[i+1] and prog[i] != prog[i-1]:
            prog[i] = prog[i-1]
    return prog


def auto_form(progression, block=4):
    """Stejny 4-taktovy harmonicky blok -> stejny label (motiv se vrati)."""
    labels, seen = [], {}
    nblocks = (len(progression) + block - 1) // block
    for bi in range(nblocks):
        sig = tuple(progression[bi*block:(bi+1)*block])
        if sig not in seen:
            seen[sig] = chr(ord('a') + len(seen))
        labels.append(seen[sig])
    return labels


def arrange(path, bars=None, bpm=110, melody=True, out_dir=None, seed=1):
    name = os.path.splitext(os.path.basename(path))[0][:40]
    notes = load_notes(path)
    prog = progression_per_bar(notes, bar=4.0, max_bars=bars)
    form = auto_form(prog)
    print(f"  {len(prog)} taktu, forma: {''.join(form)}")
    print("  progrese: " + " | ".join(f"{PC[r]}{q}" for r, q in prog))
    voic = generate_voicings(prog, color=False, center=60)
    out_dir = out_dir or os.path.join(HERE, "..", "outputs_arr")
    os.makedirs(out_dir, exist_ok=True)
    outs = []
    # harmonie-only
    oh = os.path.join(out_dir, f"{name}__harmony.mid")
    render_harmony(prog, voic, oh, bpm=bpm); outs.append(oh)
    if melody:
        line = generate_motivic(prog, form, bpc=4.0, seed=seed)
        line = declash(line, voic, prog, bpc=4.0)
        line = break_repeats(line, prog, bpc=4.0)
        om = os.path.join(out_dir, f"{name}__full.mid")
        render_full(prog, voic, line, om, bpm=bpm); outs.append(om)
    for o in outs:
        print(f"  -> {o}")
    return outs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--bars", type=int, default=None)
    ap.add_argument("--bpm", type=int, default=110)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-melody", action="store_true")
    a = ap.parse_args()
    print(f"== aranzuji: {os.path.basename(a.input)} ==")
    arrange(a.input, bars=a.bars, bpm=a.bpm, melody=not a.no_melody, seed=a.seed)
