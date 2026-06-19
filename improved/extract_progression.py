#!/usr/bin/env python3
"""
extract_progression.py -- "příkaz" pro GUI: z MIDI vytáhni akordovou progresi
a vrať ji jako JSON (akordové značky ve formátu PianoChordu: C, Dm7, G7, Cmaj7,
A#maj7, Cm7b5, ...; používá # místo b).

Použití:
    python improved/extract_progression.py "cesta.mid"            # JSON na stdout
    python improved/extract_progression.py "cesta.mid" --bars 32 --keep-repeats

Výstup (stdout):
    {"source": "...", "key": "C moll", "bars": 24,
     "chords": ["Cm7","G7","D#maj7", ...]}
"""
import os, sys, json, argparse
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

from evans_drill import load_notes
from harmony import detect_progression, PC


def to_symbol(root, quality):
    """(root_pc, quality) -> akordová značka pro PianoChord (# notace)."""
    return f"{PC[root]}{quality}"


def extract(path, bars=None, keep_repeats=False):
    notes = load_notes(path)
    prog, key = detect_progression(notes, bar=4.0, max_bars=bars)
    syms = [to_symbol(r, q) for r, q in prog]
    if not keep_repeats:
        collapsed = []
        for s in syms:
            if not collapsed or collapsed[-1] != s:
                collapsed.append(s)
        syms = collapsed
    return {"source": os.path.basename(path), "key": key,
            "bars": len(prog), "chords": syms}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--bars", type=int, default=None)
    ap.add_argument("--keep-repeats", action="store_true",
                    help="neslučovat opakované akordy (1 na takt)")
    a = ap.parse_args()
    try:
        result = extract(a.input, bars=a.bars, keep_repeats=a.keep_repeats)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
