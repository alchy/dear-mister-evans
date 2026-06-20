#!/usr/bin/env python3
"""
chord_markov.py -- key-relativní Markovův generátor akordových PROGRESÍ.

Učí se z tvé sbírky MIDI, JAK se hýbe harmonie (přechody akordů), a generuje
NOVÉ progrese ve stejném duchu. Reprezentace je RELATIVNÍ KE KLÍČI (stupeň +
kvalita), takže ii-V-I se naučí jednou, ne 12x. Major a minor skladby mají
oddělené modely. Výstup lze rovnou ozvučit (Evansovy voicingy + aranž).

Použití:
    # vygeneruj progresi v C dur, 16 akordů, a přehraj v Evansově hávu
    python improved/chord_markov.py --key C --mode maj --bars 16 --render out.mid
    python improved/chord_markov.py --key A --mode min --temp 1.1 --seed 3

Trénuje se z LESSON složek (lze přepsat --data "glob").
"""
import os, sys, glob, random, argparse
from collections import defaultdict, Counter
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

from evans_drill import load_notes, PC
import harmony

DEFAULT_DATA = r"C:\Users\jindr\OneDrive\Jazz Learning\LESSON*\*.mid"
DEG = {0:'I',1:'bII',2:'ii',3:'bIII',4:'iii',5:'IV',6:'#IV',7:'V',8:'bVI',9:'vi',10:'bVII',11:'vii'}


def total_chroma(notes):
    c = np.zeros(12)
    for o, d, p, v in notes:
        c[p % 12] += d * (v / 127.0)
    return c


def build_corpus(data_glob, max_bars=64):
    """Vrátí [(mode, [(rel, quality), ...]), ...] -- 1 sekvence na skladbu."""
    # 1 MIDI na složku (ať nepřevážíme duplikáty)
    by_dir = {}
    for f in sorted(glob.glob(data_glob)):
        by_dir.setdefault(os.path.dirname(f), f)
    seqs = []
    for f in by_dir.values():
        try:
            notes = load_notes(f)
            prog, _ = harmony.detect_progression(notes, max_bars=max_bars)
            kr, mode, _ = harmony.estimate_key(total_chroma(notes))
        except Exception:
            continue
        toks = []
        for r, q in prog:
            t = ((r - kr) % 12, q)
            if not toks or toks[-1] != t:
                toks.append(t)
        if len(toks) >= 4:
            seqs.append((mode, toks))
    return seqs


class ChordMarkov:
    def __init__(self, order=2):
        self.order = order
        self.tables = [defaultdict(Counter) for _ in range(order + 1)]
        self.starts = Counter()

    def train_seq(self, toks):
        self.starts[toks[0]] += 1
        for i in range(1, len(toks)):
            for k in range(self.order + 1):
                if i - k < 0:
                    continue
                self.tables[k][tuple(toks[i-k:i])][toks[i]] += 1

    def _draw(self, counter, temperature, rng, avoid=None):
        items = [(it, w) for it, w in counter.items() if it != avoid] or list(counter.items())
        keys, weights = zip(*items)
        if temperature != 1.0:
            weights = [w ** (1.0 / max(1e-6, temperature)) for w in weights]
        x = rng.random() * sum(weights); acc = 0
        for it, w in zip(keys, weights):
            acc += w
            if x <= acc:
                return it
        return keys[-1]

    def sample(self, ctx, temperature, rng, avoid=None):
        for k in range(min(self.order, len(ctx)), -1, -1):
            sub = tuple(ctx[len(ctx)-k:]) if k > 0 else ()
            dist = self.tables[k].get(sub)
            if dist and sum(dist.values()) >= 2:
                return self._draw(dist, temperature, rng, avoid)
        return self._draw(self.tables[0][()], temperature, rng, avoid)

    def sample_start(self, temperature, rng):
        return self._draw(self.starts, temperature, rng) if self.starts else (0, 'maj7')


def load_corpus(source="both", data_glob=DEFAULT_DATA):
    """source: 'midi' (detekce z MIDI), 'curated' (čistý korpus standardů), 'both'."""
    seqs = []
    if source in ("curated", "both"):
        import standards
        seqs += standards.to_corpus()
    if source in ("midi", "both"):
        seqs += build_corpus(data_glob)
    return seqs


def train_models(seqs, order=2, verbose=True):
    models = {'maj': ChordMarkov(order), 'min': ChordMarkov(order)}
    counts = {'maj': 0, 'min': 0}
    for mode, toks in seqs:
        models[mode].train_seq(toks); counts[mode] += 1
    if verbose:
        print(f"natrénováno: {len(seqs)} skladeb (dur {counts['maj']}, moll {counts['min']})")
    return models


def train(data_glob, order=2, verbose=True):
    return train_models(build_corpus(data_glob), order, verbose)


def generate(model, mode, bars=16, temperature=1.0, seed=None):
    rng = random.Random(seed)
    tonic = (0, 'maj7') if mode == 'maj' else (0, 'm7')
    seq = [model.sample_start(temperature, rng)]
    while len(seq) < bars:
        nxt = model.sample(tuple(seq[-model.order:]), temperature, rng, avoid=seq[-1])
        seq.append(nxt)
    seq[-1] = tonic                      # čistá kadence na konci
    if bars >= 2 and seq[-2][0] != 7:    # předposlední ať je dominanta (V7)
        seq[-2] = (7, '7')
    return seq


def to_prog(seq, key_root):
    return [((key_root + rel) % 12, q) for rel, q in seq]

def to_symbols(prog):
    return [f"{PC[r]}{q}" for r, q in prog]

def roman(seq):
    return " ".join(f"{DEG[rel]}{q}" for rel, q in seq)


def render(prog, out, bpm=110, seed=1):
    from voicings import generate_voicings
    from motif import generate_motivic
    from melody_top import render as render_full, declash, break_repeats
    from arrange import auto_form
    voic = generate_voicings(prog, color=False, center=60)
    line = generate_motivic(prog, auto_form(prog), bpc=4.0, seed=seed)
    line = declash(line, voic, prog, bpc=4.0)
    line = break_repeats(line, prog, bpc=4.0)
    render_full(prog, voic, line, out, bpm=bpm)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="C", help="cílová tónina (C, F#, A#, ...)")
    ap.add_argument("--mode", default="maj", choices=["maj", "min"])
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--source", default="curated", choices=["midi", "curated", "both"])
    ap.add_argument("--render", default=None, help="ulož aranž do MIDI")
    ap.add_argument("--bpm", type=int, default=110)
    a = ap.parse_args()

    models = train_models(load_corpus(a.source, a.data))
    key_root = PC.index(a.key) if a.key in PC else 0
    seq = generate(models[a.mode], a.mode, bars=a.bars, temperature=a.temp, seed=a.seed)
    prog = to_prog(seq, key_root)
    print(f"\ntónina: {a.key} {a.mode} | teplota {a.temp}")
    print("stupně:  " + roman(seq))
    print("akordy:  " + " | ".join(to_symbols(prog)))
    if a.render:
        render(prog, a.render, bpm=a.bpm, seed=a.seed or 1)
        print(f"aranž -> {a.render}")
