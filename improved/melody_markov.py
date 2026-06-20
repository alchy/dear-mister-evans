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
import os, sys, random, pickle
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
import mido

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


# ---------------------------------------------------------------------------
# Band-aware extrakce: z kapelní aranže vytáhne jen vedoucí melodický hlas
# (zahodí bicí kanál 10, bas, akordický comping podle "chordiness").
# ---------------------------------------------------------------------------
def load_notes_chan(path):
    """Načte noty VČETNĚ kanálu + mapu kanál->program. -> ([(o,d,p,v,ch)], prog_of)."""
    mid = mido.MidiFile(path); tpb = mid.ticks_per_beat or 480
    notes = []; prog_of = {}
    for tr in mid.tracks:
        t = 0; active = {}
        for m in tr:
            t += m.time
            if m.type == 'program_change':
                prog_of[m.channel] = m.program
            elif m.type == 'note_on' and m.velocity > 0:
                active.setdefault((m.channel, m.note), []).append((t, m.velocity))
            elif m.type == 'note_off' or (m.type == 'note_on' and m.velocity == 0):
                k = (m.channel, m.note)
                if active.get(k):
                    st, v = active[k].pop(0)
                    notes.append((st/tpb, max(0.01, (t-st)/tpb), m.note, v, m.channel))
    return notes, prog_of


def _chordiness(ns):
    """Průměrný počet tónů na společný nástup (1 = monofonní melodie, >1.5 = akordy)."""
    from collections import Counter
    c = Counter(round(o * 4) / 4 for o, _, _ in ns)
    return sum(c.values()) / max(1, len(c))


def pick_melody_channel(notes, prog_of):
    """Vybere kanál s vedoucí melodií: nejmonofoničtější, mid-high, ne bas/bicí."""
    from collections import defaultdict
    bychan = defaultdict(list)
    for o, d, p, v, ch in notes:
        if ch == 9:                      # bicí
            continue
        bychan[ch].append((o, d, p))
    best, bestkey = None, None
    for ch, ns in bychan.items():
        if 32 <= prog_of.get(ch, 0) <= 39:   # basové programy
            continue
        if len(ns) < 8:
            continue
        meanp = sum(p for _, _, p in ns) / len(ns)
        if not (54 <= meanp <= 92):
            continue
        key = (_chordiness(ns), -meanp, -len(ns))   # málo akordů, výš, víc not
        if bestkey is None or key < bestkey:
            bestkey, best = key, ch
    return best


def melody_from_midi(path):
    """Vrátí melodickou linku [(o,d,p)] z (i kapelního) MIDI -- jen vedoucí hlas."""
    notes, prog_of = load_notes_chan(path)
    if not notes:
        return []
    ch = pick_melody_channel(notes, prog_of)
    if ch is None:
        sub = [(o, d, p, v) for o, d, p, v, c in notes if c != 9]
    else:
        sub = [(o, d, p, v) for o, d, p, v, c in notes if c == ch]
    return extract_melody(sub) if sub else []


EXTERNAL_DIR = os.path.join(HERE, "..", "data_external")   # midkar, bushgrafts, ...


def gather_files(source, include_extra=True):
    """source: 'evans' (jen be-slice) | 'all' (celá sbírka: 1 MIDI/složku +
    MusicXML + cokoliv v data_external/, pokud je k dispozici)."""
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
    # externí korpus(y): každý soubor je jiná skladba -> bez folder-dedupu
    if include_extra and os.path.isdir(EXTERNAL_DIR):
        for f in sorted(glob.glob(os.path.join(EXTERNAL_DIR, "**", "*.mid"), recursive=True)):
            out.append(('mid', f))
    return out


def _extract(kind, f):
    if kind == 'mid':
        return melody_from_midi(f)          # band-aware (jen vedoucí hlas)
    notes = musicxml_notes(f)
    return extract_melody(notes) if notes else []


def train_files(files, order=2, verbose=True, label=""):
    model = MotionMarkov(order=order)
    ntok = used = 0
    for kind, f in files:
        try:
            mel = _extract(kind, f)
            if not mel:
                continue
            toks = melody_to_tokens(mel)
            model.train_on(toks)
            ntok += sum(1 for t in toks if t is not None); used += 1
        except Exception:
            continue
    if verbose:
        print(f"melodický Markov [{label or 'files'}]: {used}/{len(files)} souborů, "
              f"{ntok} tokenů pohybu+rytmu")
    return model


def train(source="evans", order=2, verbose=True):
    return train_files(gather_files(source), order, verbose, label=source)


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


MODELS_DIR = os.path.join(HERE, "..", "models")


def get_model(source="all"):
    """Vrátí natrénovaný melodický model (z cache, jinak natrénuje a uloží).
    None, pokud data nejsou k dispozici (-> fallback na pravidlovou melodii)."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    path = os.path.join(MODELS_DIR, f"melody_{source}.pkl")
    if os.path.exists(path):
        try:
            with open(path, "rb") as fh:
                m = pickle.load(fh)
            if getattr(m, "starts", None):
                return m
        except Exception:
            pass
    try:
        m = train(source, verbose=False)
    except Exception:
        return None
    if not getattr(m, "starts", None):
        return None
    try:
        with open(path, "wb") as fh:
            pickle.dump(m, fh)
    except Exception:
        pass
    return m


def best_melody(progression, seed=1, temperature=1.0, source="evans", bpc=4.0):
    """Naučená melodie (pokud jsou data), jinak fallback na pravidlovou (motif)."""
    model = get_model(source)
    if model is not None:
        try:
            return learned_line(model, progression, temperature=temperature, seed=seed)
        except Exception:
            pass
    from motif import generate_motivic
    from arrange import auto_form
    return generate_motivic(progression, auto_form(progression), bpc=bpc, seed=seed)


def finalize_melody(progression, voic, seed=1, temperature=1.0, source="evans", bpc=4.0):
    """Hotová melodická linka (naučená/fallback) + declash + anti-opakování."""
    line = best_melody(progression, seed=seed, temperature=temperature, source=source, bpc=bpc)
    line = declash(line, voic, progression, bpc=bpc)
    line = break_repeats(line, progression, bpc=bpc)
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
