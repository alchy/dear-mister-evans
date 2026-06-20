#!/usr/bin/env python3
"""
blend_markov.py -- PROLNUTÍ dvou stylů přes Markov (Evans x Peterson).

Postaví Markov model z Petersonova cvičení (Jazz Exercises Ex.4) a při generování
INTERPOLUJE jeho přechodová rozdělení s naučeným Evansovým modelem:

    P_mix(token | kontext) = alpha * P_Evans  +  (1 - alpha) * P_Peterson

alpha = 1.0 -> čistý Evans;  0.0 -> čistý Peterson;  0.5 -> půl na půl.
Generuje se Evansovým pipeline (learned_line): harmonická kostra + frázování
zůstávají, ale lokální pohyb (interval) i rytmus se táhnou z MIXU obou stylů.

Použití:
    python improved/blend_markov.py --chords "Cm7 F7 Bbmaj7 ..." --alpha 0.5
"""
import os, sys, glob, random
from collections import Counter
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import melody_markov as mm
from melody_v2 import MotionMarkov, melody_to_tokens

# Petersonovo cvičení (uživatelova data, mimo repo) -- default hledá v Downloads.
PETERSON_GLOBS = [
    os.path.join(os.path.expanduser("~"), "Downloads", "Oscar Peterson*Exercise*.mid"),
    os.path.join(HERE, "..", "data_external", "peterson", "*.mid"),
]


def peterson_files():
    out = []
    for g in PETERSON_GLOBS:
        out.extend(sorted(glob.glob(g)))
    return out


def train_peterson(order=2, verbose=True):
    """Markov model z Petersonových cvičení (band-aware vedoucí hlas)."""
    model = MotionMarkov(order=order)
    files = peterson_files()
    used = ntok = 0
    for f in files:
        mel = mm.melody_from_midi(f)
        if not mel:
            continue
        toks = melody_to_tokens(mel)
        model.train_on(toks)
        ntok += sum(1 for t in toks if t is not None); used += 1
    if verbose:
        print(f"Peterson Markov: {used}/{len(files)} souborů, {ntok} tokenů")
    return model if used else None


def _draw(weights, temperature, rng):
    """weights = dict token->váha. Losování s teplotou."""
    items = list(weights.keys()); w = list(weights.values())
    if temperature != 1.0:
        w = [x ** (1.0 / max(1e-6, temperature)) for x in w]
    total = sum(w) or 1.0; x = rng.random() * total; acc = 0.0
    for it, wi in zip(items, w):
        acc += wi
        if x <= acc:
            return it
    return items[-1]


def _norm(counter):
    s = sum(counter.values()) or 1
    return {k: v / s for k, v in counter.items()}


def _mix(da, db, alpha):
    out = {}
    for k, v in _norm(da).items():
        out[k] = out.get(k, 0.0) + alpha * v
    for k, v in _norm(db).items():
        out[k] = out.get(k, 0.0) + (1.0 - alpha) * v
    return out


class BlendMarkov:
    """Drží dva modely a samplová z interpolovaného rozdělení (váha alpha pro a)."""
    def __init__(self, model_a, model_b, alpha=0.5):
        self.a = model_a; self.b = model_b; self.alpha = alpha
        self.order = min(model_a.order, model_b.order)
        self.starts = model_a.starts   # jen pro test getattr() v get_model-like cestě

    @staticmethod
    def _backoff(m, ctx):
        for k in range(min(m.order, len(ctx)), -1, -1):
            sub = tuple(ctx[len(ctx) - k:]) if k > 0 else ()
            dist = m.tables[k].get(sub)
            if dist and sum(dist.values()) >= 2:
                return dist
        return m.tables[0].get(()) or Counter({(0, 0.5): 1})

    def sample(self, ctx, temperature=1.0, rng=random):
        da = self._backoff(self.a, ctx); db = self._backoff(self.b, ctx)
        return _draw(_mix(da, db, self.alpha), temperature, rng)

    def sample_start(self, temperature=1.0, rng=random):
        return _draw(_mix(self.a.starts, self.b.starts, self.alpha), temperature, rng)


def get_blend(alpha=0.5, verbose=True):
    """Hotový prolnutý model Evans x Peterson (None, pokud chybí data)."""
    ev = mm.get_model("evans"); pt = train_peterson(verbose=verbose)
    if ev is None or pt is None:
        return None
    return BlendMarkov(ev, pt, alpha)


if __name__ == "__main__":
    import argparse
    from arrange_chords import parse_symbol
    ap = argparse.ArgumentParser()
    ap.add_argument("--chords", default="Cm7 F7 Bbmaj7 Ebmaj7 Am7b5 D7 Gm7 Gm7")
    ap.add_argument("--alpha", type=float, default=0.5, help="1=Evans, 0=Peterson")
    ap.add_argument("--bpm", type=int, default=120)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--render", default="outputs_pat/blend.mid")
    a = ap.parse_args()
    prog = [parse_symbol(s) for s in a.chords.split()]
    model = get_blend(a.alpha)
    if model is None:
        print("chybí data (Evans nebo Peterson)"); sys.exit(1)
    os.makedirs(os.path.dirname(a.render), exist_ok=True)
    mm.arrange_learned(prog, a.render, bpm=a.bpm, temperature=a.temp,
                       seed=a.seed, model=model)
    print(f"prolnutí alpha={a.alpha} -> {a.render}")
