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
MLO, MHI = 72, 91


def train(data_glob=EVANS_DATA, order=2, skip=("be-slice19.mid",), verbose=True):
    files = [f for f in sorted(glob.glob(data_glob)) if os.path.basename(f) not in skip]
    model = MotionMarkov(order=order)
    ntok = 0
    for f in files:
        try:
            toks = melody_to_tokens(extract_melody(load_notes(f)))
            model.train_on(toks)
            ntok += sum(1 for t in toks if t is not None)
        except Exception as e:
            if verbose:
                print(f"  preskakuji {os.path.basename(f)}: {e}")
    if verbose:
        print(f"melodický Markov: {len(files)} souborů, {ntok} tokenů pohybu+rytmu")
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
    ap.add_argument("--render", default="outputs_mel/learned_full.mid")
    a = ap.parse_args()

    # progrese z kurátorského Markova
    progs = cm.train_models(cm.load_corpus('curated'))
    seq = cm.generate(progs[a.mode], a.mode, bars=a.bars, temperature=1.0, seed=a.seed)
    prog = cm.to_prog(seq, cm.PC.index(a.key) if a.key in cm.PC else 0)
    print("progrese:", " | ".join(cm.to_symbols(prog)))
    os.makedirs(os.path.dirname(a.render), exist_ok=True)
    model = train()
    arrange_learned(prog, a.render, bpm=a.bpm, temperature=a.temp, seed=a.seed, model=model)
    print(f"aranž (naučená melodie) -> {a.render}")
