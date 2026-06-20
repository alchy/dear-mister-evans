#!/usr/bin/env python3
"""
lines_corpus.py -- model z "Daily jazz line" cvičení (reálné jazzové linky).

Soubory jsou husté/jednokanálové: vysoká melodická LINKA proložená nízkými
basovými/akordickými údery. Naivní skyline prolíná registry -> falešné oktávové
skoky. Tady čistá extrakce: registrové hradlo (jen horní pásmo) + sledování
NEJBLIŽŠÍHO tónu (drž linku), basové sloty = pauza. Linka je v souborech
opakovaná v různých tóninách -> transpozičně invariantní Markov ji silně naučí.
"""
import os, sys, glob, pickle
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import mido
from melody_v2 import MotionMarkov, melody_to_tokens

LINES_DIR = os.path.join(HERE, "..", "data_external", "daily_lines")
MODELS_DIR = os.path.join(HERE, "..", "models")


def _notes(path):
    mid = mido.MidiFile(path); tpb = mid.ticks_per_beat or 220
    ev = []; act = {}
    for tr in mid.tracks:
        t = 0
        for m in tr:
            t += m.time
            if m.type == 'note_on' and m.velocity > 0:
                act.setdefault(m.note, []).append(t)
            elif m.type == 'note_off' or (m.type == 'note_on' and m.velocity == 0):
                if act.get(m.note):
                    st = act[m.note].pop(0); ev.append((st / tpb, (t - st) / tpb, m.note))
    ev.sort()
    return ev


def clean_line(path, grid=0.25, floor_pct=0.55):
    """Vytáhne čistou melodickou linku [(onset, dur, pitch)] z husté praktiky."""
    ev = _notes(path)
    if len(ev) < 4:
        return []
    ps = sorted(p for _, _, p in ev)
    floor = ps[int(len(ps) * floor_pct)]            # jen horní pásmo (linka)
    slots = {}
    for o, d, p in ev:
        if p < floor:
            continue                                # bas/akord = pauza v lince
        k = round(o / grid) * grid
        slots.setdefault(k, []).append(p)
    out = []; cur = None
    for k in sorted(slots):
        cand = slots[k]
        cur = max(cand) if cur is None else min(cand, key=lambda p: (abs(p - cur), -p))
        out.append((k, grid, cur))
    return out


def train_lines(folder=LINES_DIR, order=2, verbose=True):
    model = MotionMarkov(order=order)
    files = sorted(glob.glob(os.path.join(folder, "*.mid")))
    used = ntok = 0
    for f in files:
        mel = clean_line(f)
        if not mel:
            continue
        toks = melody_to_tokens(mel)
        model.train_on(toks)
        ntok += sum(1 for t in toks if t is not None); used += 1
    if verbose:
        print(f"Lines Markov: {used}/{len(files)} souborů, {ntok} tokenů")
    return model if used else None


def get_lines_model(verbose=False):
    """Model z daily-lines (cache v models/lines.pkl). None, pokud chybí data."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    path = os.path.join(MODELS_DIR, "lines.pkl")
    if os.path.exists(path):
        try:
            with open(path, "rb") as fh:
                m = pickle.load(fh)
            if getattr(m, "starts", None):
                return m
        except Exception:
            pass
    m = train_lines(verbose=verbose)
    if m is None or not getattr(m, "starts", None):
        return None
    try:
        with open(path, "wb") as fh:
            pickle.dump(m, fh)
    except Exception:
        pass
    return m


if __name__ == "__main__":
    import collections
    from evans_drill import nm
    m = train_lines(verbose=True)
    if m:
        ic = collections.Counter()
        for tok, w in m.tables[0][()].items():
            ic[tok[0]] += w
        print("nejčastější intervaly:", ic.most_common(8))
        oct_ = sum(w for iv, w in ic.items() if abs(iv) >= 12)
        print(f"podíl oktávových skoků v modelu: {round(100*oct_/sum(ic.values()))}%")
