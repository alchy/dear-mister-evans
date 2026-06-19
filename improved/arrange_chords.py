#!/usr/bin/env python3
"""
arrange_chords.py -- "příkaz" pro GUI: z DANÝCH akordů (ne z MIDI) vyrob plnou
Evansovskou aranž (bas + comp + melodie) a ulož do MIDI.

Použití:
    python improved/arrange_chords.py --chords "G6 | Cmaj7 | Bm7 | Em7 | Am7 | D7 | Gmaj7" \
        --out "out.mid" --bpm 110
    (--no-melody = jen voicingy; --seed N = jiná melodická varianta)

Výstup (stdout): JSON {"output": "...", "bars": N}
"""
import os, sys, re, json, argparse
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

from voicings import generate_voicings, render as render_harmony
from melody_top import render as render_full, declash, break_repeats
from motif import generate_motivic
from arrange import auto_form

NOTE2PC = {'C':0,'C#':1,'DB':1,'D':2,'D#':3,'EB':3,'E':4,'F':5,'F#':6,'GB':6,
           'G':7,'G#':8,'AB':8,'A':9,'A#':10,'BB':10,'B':11}


def map_quality(q):
    q = (q or "").strip(); low = q.lower()
    if 'm7b5' in low or 'min7b5' in low or 'ø' in q: return 'm7b5'
    if 'dim' in low or '°' in q: return 'dim7'
    is_minor = (low.startswith('m') and not low.startswith('maj')) or \
               low.startswith('-') or low.startswith('min')
    if is_minor and 'maj7' in low: return 'mMaj7'
    if low.startswith('maj') or q.startswith('M') or 'Δ' in q:
        return '6' if low[:1] == '6' else 'maj7'
    if 'aug' in low or '+' in q: return 'aug'
    if 'sus' in low: return 'sus'
    if is_minor: return 'm6' if '6' in q else 'm7'
    if low.startswith('6'): return '6'
    if any(d in q for d in ('7', '9', '11', '13')): return '7'
    return 'maj7'


def parse_symbol(sym):
    m = re.match(r'^\s*([A-Ga-g][#b]?)(.*)$', sym)
    if not m:
        raise ValueError(f"nečitelný akord: {sym!r}")
    note = m.group(1)
    note = note[0].upper() + (note[1:] if len(note) > 1 else "")
    root = NOTE2PC[note.upper()]
    return root, map_quality(m.group(2))


def parse_chords(s):
    parts = re.split(r'[|,]', s) if ('|' in s or ',' in s) else s.split()
    return [parse_symbol(p) for p in parts if p.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chords", required=True, help="např. 'G6 | Cmaj7 | Bm7'")
    ap.add_argument("--out", required=True, help="výstupní .mid")
    ap.add_argument("--bpm", type=int, default=110)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-melody", action="store_true")
    a = ap.parse_args()
    try:
        prog = parse_chords(a.chords)
        if not prog:
            raise ValueError("prázdná progrese")
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        voic = generate_voicings(prog, color=False, center=60)
        if a.no_melody:
            render_harmony(prog, voic, a.out, bpm=a.bpm)
        else:
            line = generate_motivic(prog, auto_form(prog), bpc=4.0, seed=a.seed)
            line = declash(line, voic, prog, bpc=4.0)
            line = break_repeats(line, prog, bpc=4.0)
            render_full(prog, voic, line, a.out, bpm=a.bpm)
        print(json.dumps({"output": a.out, "bars": len(prog)}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
