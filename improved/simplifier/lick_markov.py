"""lick_markov -- Markov nad extrahovanými licky: nauč se pohyb linky, GENERUJ
nové fráze nad zadanou progresí.

Nápad (J.): trénink na extracted licks vyhladí náhodné nedostatky (jednotlivé
glitche se ve statistice ztratí) a umí generovat nové fráze ve stylu korpusu.

Token = (interval, délka). Order-2 s backoffem. Dlouhé tóny se při generování
zacvaknou do chord-scale aktivního akordu (harmony-aware), krátké smí být
chromatické (approach). Start na akordovém tónu prvního akordu.
"""
import json, random
from collections import defaultdict, Counter
import numpy as np
from . import chords as C
from voice.voicings import SCALE

DURS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
START = ("S", "S")


def _qd(d):
    return min(DURS, key=lambda x: abs(x - d))


def _scale_pcs(sym):
    r, q = C.parse_sym(sym)
    return set((r + s) % 12 for s in SCALE.get(q, SCALE["maj7"]))


class LickMarkov:
    def __init__(self, order=2):
        self.order = order
        self.trans = defaultdict(Counter)

    def train(self, licks):
        for lk in licks:
            mel = lk.get("melody", [])
            if len(mel) < 3:
                continue
            toks = [(max(-12, min(12, b[2] - a[2])), _qd(b[1])) for a, b in zip(mel, mel[1:])]
            seq = [START] * self.order + toks
            for i in range(self.order, len(seq)):
                self.trans[tuple(seq[i - self.order:i])][seq[i]] += 1
        return self

    def _sample(self, ctx, rng):
        for k in range(self.order, 0, -1):
            c = self.trans.get(tuple(ctx[-k:]))
            if c:
                toks, w = zip(*c.items())
                return rng.choices(toks, weights=w)[0]
        return (random.choice([-2, -1, 1, 2]), 0.5)

    def _snap(self, p, sym):
        sc = _scale_pcs(sym)
        if p % 12 in sc:
            return p
        for off in (1, -1, 2, -2, 3, -3):
            if (p + off) % 12 in sc:
                return p + off
        return p

    def generate(self, changes, chord_beats, seed=0, start_pitch=64, lo=54, hi=82):
        rng = random.Random(seed)
        syms = changes.split()
        bounds = np.cumsum([0] + list(chord_beats))
        total = float(bounds[-1])
        start = self._snap(start_pitch, syms[0])
        out = [(0.0, 0.5, start)]
        pos = 0.5
        ctx = [START] * self.order
        while pos < total - 0.1:
            iv, dur = self._sample(ctx, rng)
            p = out[-1][2] + iv
            ci = int(np.clip(np.searchsorted(bounds, pos, "right") - 1, 0, len(syms) - 1))
            if dur > 0.25:
                p = self._snap(p, syms[ci])
            p = max(lo, min(hi, p))
            out.append((round(pos, 3), dur, p))
            pos += dur
            ctx = ctx[1:] + [(iv, dur)]
        return out


def _nearest(prev, pc, lo, hi):
    """Nejbližší výška k prev se zadanou pitch-class, v rozsahu [lo,hi]."""
    cands = [pc + 12 * o for o in range(0, 12) if lo <= pc + 12 * o <= hi]
    return min(cands, key=lambda x: abs(x - prev)) if cands else prev


class ScaleDegreeLM:
    """Token = (stupeň vůči akordovému kořeni 0-11, délka). Harmony-locked: každý
    generovaný tón má pc = kořen+stupeň, takže vždy sedí do akordu. Order-N backoff."""

    def __init__(self, order=3):
        self.order = order
        self.trans = defaultdict(Counter)

    def _tokens(self, lk):
        mel = lk.get("melody", [])
        bounds = np.cumsum([0] + list(lk["chord_beats"]))
        syms = lk["changes"].split()
        toks = []
        for o, d, p in mel:
            ci = int(np.clip(np.searchsorted(bounds, o, "right") - 1, 0, len(syms) - 1))
            r, _ = C.parse_sym(syms[ci])
            toks.append(((p - r) % 12, _qd(d)))
        return toks

    def train(self, licks):
        for lk in licks:
            if len(lk.get("melody", [])) < 3:
                continue
            seq = [START] * self.order + self._tokens(lk)
            for i in range(self.order, len(seq)):
                self.trans[tuple(seq[i - self.order:i])][seq[i]] += 1
        return self

    def _sample(self, ctx, rng):
        for k in range(self.order, 0, -1):
            c = self.trans.get(tuple(ctx[-k:]))
            if c:
                toks, w = zip(*c.items())
                return rng.choices(toks, weights=w)[0]
        return (0, 0.5)

    def generate(self, changes, chord_beats, seed=0, lo=54, hi=82):
        rng = random.Random(seed)
        syms = changes.split()
        bounds = np.cumsum([0] + list(chord_beats))
        total = float(bounds[-1])
        r0, _ = C.parse_sym(syms[0])
        out = [(0.0, 0.5, _nearest(64, r0 % 12, lo, hi))]
        pos = 0.5
        ctx = [START] * self.order
        while pos < total - 0.1:
            tok = self._sample(ctx, rng)
            rel, dur = tok
            if rel == "S":
                rel, dur = 0, 0.5
            ci = int(np.clip(np.searchsorted(bounds, pos, "right") - 1, 0, len(syms) - 1))
            r, _ = C.parse_sym(syms[ci])
            p = _nearest(out[-1][2], (r + rel) % 12, lo, hi)
            out.append((round(pos, 3), dur, p))
            pos += dur
            ctx = ctx[1:] + [tok]
        return out


def lick_dict(changes, chord_beats, melody, bpm=90, tag="markov"):
    return {"id": tag, "type": "markov", "changes": changes, "chord_beats": chord_beats,
            "melody": melody, "n_beats": int(sum(chord_beats)), "bpm": bpm,
            "score": 0.0, "energy": 0.65, "source": "markov"}


if __name__ == "__main__":
    import sys
    lib = json.load(open(sys.argv[1]))["licks"]
    changes = sys.argv[2] if len(sys.argv) > 2 else "Fm7 Bb7 Ebmaj7"
    cb = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [2, 2, 2]
    out = sys.argv[4] if len(sys.argv) > 4 else "/tmp/markov_gen.json"
    m = LickMarkov().train(lib)
    print(f"natrénováno na {len(lib)} licích | kontextů={len(m.trans)} | generuju nad: {changes}")
    gen = [lick_dict(changes, cb, m.generate(changes, cb, seed=s), tag=f"markov_{s}") for s in range(1, 7)]
    json.dump({"licks": gen}, open(out, "w"))
    for g in gen:
        print("  ", " ".join(C.PC[p % 12] for _, _, p in g["melody"]))
    print(f"-> {out}")
