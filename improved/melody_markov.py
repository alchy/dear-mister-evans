#!/usr/bin/env python3
"""
melody_markov.py -- harmonicky vedený MELODICKÝ Markov (naučené Evansovo frázování).

Současná pravačka je pravidlová (kotvy + krokové nájezdy). Tady ji nahradíme
NAUČENÝM lokálním pohybem + RYTMEM z Evansových přepisů:
  - Markov se učí P(další (interval, rytmus) | předchozí) z Evansových melodií
    (reprezentace nezávislá na harmonii -> imunní vůči šumu v detekci),
  - GENERUJE se ale UVNITŘ harmonické kostry: každý tón se snapne na akordovou
    stupnici, na těžké době se cílí akordový ton (kotva), fráze po 4 taktech.
  - Rytmus pochází z naučených tokenů (Evansovo frázování), ne z pravidla.

Tím se spojí: naučený styl (Markov) + soudržnost (kostra). Řeší starý problém
v2 ("záblesky, ale nedrží"), protože strukturu teď drží kostra.
"""
import os, sys, random
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

from melody_v2 import (MotionMarkov, melody_to_tokens, scale_pitches,
                       chord_tone_pitches, _pick)
from melody_top import build_anchors, render as render_full, declash, break_repeats
from voicings import generate_voicings
from evans_drill import load_notes
from line_extraction import extract_melody
import glob

EVANS_DATA = os.path.join(HERE, "..", "concept", "evans_melody_gen", "data", "be-slice*.mid")
JAZZ_ROOT = r"C:\Users\jindr\OneDrive\Jazz Learning"
MLO, MHI = 72, 91
_STEP = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def _local(tag):
    return tag.split('}')[-1]


def musicxml_notes(path):
    """Best-effort čtení not z MusicXML -> [(onset, dur, pitch, vel)] (v dobách)."""
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    notes = []
    for part in [e for e in root if _local(e.tag) == 'part']:
        divisions = 1.0; cursor = 0.0; prev_onset = 0.0
        for measure in [e for e in part if _local(e.tag) == 'measure']:
            for el in measure:
                t = _local(el.tag)
                if t == 'attributes':
                    for a in el:
                        if _local(a.tag) == 'divisions':
                            try: divisions = float(a.text)
                            except Exception: pass
                elif t == 'backup':
                    for c in el:
                        if _local(c.tag) == 'duration':
                            cursor -= float(c.text) / divisions
                elif t == 'forward':
                    for c in el:
                        if _local(c.tag) == 'duration':
                            cursor += float(c.text) / divisions
                elif t == 'note':
                    is_chord = any(_local(c.tag) == 'chord' for c in el)
                    durdiv = 0.0; pitch = None
                    for c in el:
                        lc = _local(c.tag)
                        if lc == 'duration':
                            durdiv = float(c.text)
                        elif lc == 'pitch':
                            step = oct_ = None; alt = 0
                            for pc in c:
                                lp = _local(pc.tag)
                                if lp == 'step': step = pc.text
                                elif lp == 'alter': alt = int(pc.text)
                                elif lp == 'octave': oct_ = int(pc.text)
                            if step in _STEP and oct_ is not None:
                                pitch = (oct_ + 1) * 12 + _STEP[step] + alt
                    durb = durdiv / divisions
                    onset = prev_onset if is_chord else cursor
                    if pitch is not None:
                        notes.append((onset, max(durb, 0.05), pitch, 90))
                        prev_onset = onset
                    if not is_chord:
                        cursor += durb
    return notes


def gather_files(source):
    """source: 'evans' (jen be-slice) | 'all' (celá sbírka: 1 MIDI/složku + MusicXML)."""
    out = []
    if source == "evans":
        for f in sorted(glob.glob(EVANS_DATA)):
            if os.path.basename(f) != "be-slice19.mid":
                out.append(('mid', f))
        return out
    seen = set()
    for f in sorted(glob.glob(os.path.join(JAZZ_ROOT, "**", "*.mid"), recursive=True)):
        d = os.path.dirname(f)
        if d not in seen:
            seen.add(d); out.append(('mid', f))
    for f in sorted(glob.glob(os.path.join(JAZZ_ROOT, "**", "*.musicxml"), recursive=True)):
        out.append(('xml', f))
    return out


def train(source="evans", order=2, verbose=True):
    files = gather_files(source)
    model = MotionMarkov(order=order)
    ntok = used = 0
    for kind, f in files:
        try:
            notes = load_notes(f) if kind == 'mid' else musicxml_notes(f)
            if not notes:
                continue
            toks = melody_to_tokens(extract_melody(notes))
            model.train_on(toks)
            ntok += sum(1 for t in toks if t is not None); used += 1
        except Exception:
            continue
    if verbose:
        print(f"melodický Markov [{source}]: {used}/{len(files)} souborů, "
              f"{ntok} tokenů pohybu+rytmu")
    return model


def learned_line(model, progression, bpc=4.0, mlo=MLO, mhi=MHI,
                 temperature=1.0, seed=None):
    """Generuje melodii: naučený (interval, rytmus) UVNITŘ harmonické kostry."""
    rng = random.Random(seed)
    total = len(progression) * bpc
    anchors = build_anchors(progression, mlo, mhi, seed)   # kotva/takt (chord/color)
    r0, q0 = progression[0]
    cur = _pick(chord_tone_pitches(r0, q0, mlo, mhi), anchors[0], anchors[0], None, None, 99)
    line = [(0.0, 0.9, cur)]
    prev = None
    t = 0.0
    ctx = []
    first = True
    while True:
        tok = model.sample_start(temperature, rng) if first else \
              model.sample(tuple(ctx), temperature, rng)
        first = False
        interval, ioi = tok
        nt = t + ioi
        if nt >= total - 1e-6:
            break
        bar = min(int(nt // bpc), len(progression) - 1)
        r, q = progression[bar]
        pos = nt - bar * bpc
        ctx.append(tok); ctx = ctx[-model.order:]
        # nádech: 4. takt fráze, druhá půlka -> pauza (jen posuň čas)
        if bar % 4 == 3 and pos > bpc * 0.5:
            t = nt; continue
        downbeat = pos < max(0.3, ioi / 2)
        target = cur + interval
        cands = (chord_tone_pitches(r, q, mlo, mhi) if downbeat
                 else scale_pitches(r, q, mlo - 2, mhi))
        note = _pick(cands, target, cur, avoid_repeat=cur, avoid_aba=prev, max_leap=10)
        line.append((nt, max(0.2, ioi * 0.9), note))
        prev = cur; cur = note; t = nt
    return line


def arrange_learned(progression, out, bpm=110, temperature=1.0, seed=1, model=None):
    model = model or train(verbose=False)
    voic = generate_voicings(progression, color=False, center=60)
    line = learned_line(model, progression, temperature=temperature, seed=seed)
    line = declash(line, voic, progression, bpc=4.0)
    line = break_repeats(line, progression, bpc=4.0)
    render_full(progression, voic, line, out, bpm=bpm)
    return line


if __name__ == "__main__":
    import argparse
    import chord_markov as cm
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="C")
    ap.add_argument("--mode", default="maj", choices=["maj", "min"])
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bpm", type=int, default=110)
    ap.add_argument("--source", default="evans", choices=["evans", "all"],
                    help="evans = jen Evans; all = celá sbírka (MIDI + MusicXML)")
    ap.add_argument("--render", default="outputs_mel/learned_full.mid")
    a = ap.parse_args()

    # progrese z kurátorského Markova
    progs = cm.train_models(cm.load_corpus('curated'))
    seq = cm.generate(progs[a.mode], a.mode, bars=a.bars, temperature=1.0, seed=a.seed)
    prog = cm.to_prog(seq, cm.PC.index(a.key) if a.key in cm.PC else 0)
    print("progrese:", " | ".join(cm.to_symbols(prog)))
    os.makedirs(os.path.dirname(a.render), exist_ok=True)
    model = train(a.source)
    arrange_learned(prog, a.render, bpm=a.bpm, temperature=a.temp, seed=a.seed, model=model)
    print(f"aranž (naučená melodie) -> {a.render}")
