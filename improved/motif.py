#!/usr/bin/env python3
"""
motif.py -- v6: motivicka navratnost (tema se vraci v opakovanem dilu formy).

Navaznost: v5 generuje melodii prubezne, takze opakovany A-dil zni pokazde jinak.
Hudba ale drzi pohromade i tim, ze se MOTIV VRACI. v6:
  - rozdeli formu na 4-taktove bloky s labely (A A B C -> a b a b c d),
  - pro kazdy UNIKATNI label vygeneruje motiv jednou (logikou z v5),
  - kdyz se label vrati, prehraje TENTYZ motiv (rytmus+kontura) snapnuty na
    aktualni harmonii -> ucho slysi "tema se vratilo".
Pod tim hraje voice-led comp z v4. Vrchol "drzi to pohromadu".
"""
import os, sys, random
HERE = os.path.dirname(__file__)
CONCEPT = os.path.join(HERE, "..", "concept", "evans_melody_gen")
sys.path.insert(0, CONCEPT); sys.path.insert(0, os.path.join(CONCEPT, "src"))

from evans_drill import nm
from melody_v2 import PROGRESSIONS, scale_pitches, chord_tone_pitches, _pick
from melody_top import make_melody, render, MLO, MHI
from voicings import generate_voicings
from phrases_v3 import FORMS


def melody_to_motif(notes, base_beat):
    motif, prev = [], None
    for o, d, p in sorted(notes):
        interval = 0 if prev is None else p - prev
        motif.append((o - base_beat, d, interval)); prev = p
    return motif

def place_motif(motif, base_beat, start_pitch, progression, bpc, mlo, mhi):
    out, cur, prev = [], start_pitch, None
    for orel, d, interval in motif:
        t = base_beat + orel
        if t >= len(progression) * bpc - 1e-6:
            break
        ci = min(int(t // bpc), len(progression) - 1)
        r, q = progression[ci]
        downbeat = (t - ci * bpc) < 0.3
        if prev is None:
            cur = _pick(chord_tone_pitches(r, q, mlo, mhi), start_pitch,
                        start_pitch, None, None, 99)
            out.append((t, d, cur)); prev = cur; continue
        target = cur + interval
        cands = (chord_tone_pitches(r, q, mlo, mhi) if downbeat
                 else scale_pitches(r, q, mlo - 2, mhi))
        note = _pick(cands, target, cur, avoid_repeat=cur, avoid_aba=prev, max_leap=12)
        out.append((t, d, note)); prev = cur; cur = note
    return out


def generate_motivic(progression, form_labels, bpc=4.0, bars_per_block=4,
                     mlo=MLO, mhi=MHI, seed=1):
    blocks = [progression[i:i+bars_per_block]
              for i in range(0, len(progression), bars_per_block)]
    motifs = {}
    line = []
    last_pitch = (mlo + mhi) // 2
    for bi, sub in enumerate(blocks):
        label = form_labels[bi] if bi < len(form_labels) else f"_{bi}"
        base = bi * bars_per_block * bpc
        if label not in motifs:
            mel, _ = make_melody(sub, beats_per_chord=bpc, mlo=mlo, mhi=mhi, seed=seed+bi)
            motifs[label] = melody_to_motif(mel, 0.0)
        seg = place_motif(motifs[label], base, last_pitch, progression, bpc, mlo, mhi)
        if seg:
            last_pitch = seg[-1][2]
            line += seg
    return line


if __name__ == "__main__":
    out_dir = os.path.join(HERE, "..", "outputs_v6")
    os.makedirs(out_dir, exist_ok=True)
    bpms = {"autumn_leaves": 110, "nardis_A": 90}
    for name in ("autumn_leaves", "nardis_A"):
        prog = PROGRESSIONS[name]; form = FORMS[name]; bpm = bpms[name]
        voic = generate_voicings(prog, color=False, center=60)
        print(f"\n== {name} (forma {form}) ==")
        for k in (1, 2, 3):
            line = generate_motivic(prog, form, seed=k)
            out = os.path.join(out_dir, f"{name}_mo{k}.mid")
            render(prog, voic, line, out, bpm=bpm)
            print(f"  mo{k}: {os.path.basename(out)}  ({len(line)} tonu)")
    print(f"\nHotovo -> {out_dir}\\  (poslouchej navrat tematu v opakovanem A-dilu)")
