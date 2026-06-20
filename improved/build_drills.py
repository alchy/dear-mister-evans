#!/usr/bin/env python3
"""
build_drills.py -- vyrob cvičnou sadu stupnicových drilů do OneDrive.

ii-V-I (dur i moll) přes všechny tóniny (kvintový kruh), rhythm changes, blues.
Každý: bass + akord/takt + stupnicový dril (nahoru/dolů, landing na guide tone).
Varianty stupnic: auto (pestrá paleta), bebop, pentatonika.

Spuštění:  python improved/build_drills.py
"""
import os, sys, traceback
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import scale_drill as sd
from evans_drill import PC

TARGET = r"C:\Users\jindr\OneDrive\Jazz Learning\LESSON - Scale Drills"
CYCLE = [0, 5, 10, 3, 8, 1, 6, 11, 4, 9, 2, 7]   # kvartový kruh (C F Bb Eb ...)


def major_iiVI_cycle():
    prog = []
    for k in CYCLE:
        prog += [((k+2) % 12, 'm7'), ((k+7) % 12, '7'), (k, 'maj7'), (k, 'maj7')]
    return prog

def minor_iiVi_cycle():
    prog = []
    for k in CYCLE:
        prog += [((k+2) % 12, 'm7b5'), ((k+7) % 12, '7'), (k, 'm7'), (k, 'm7')]
    return prog

RHYTHM_BB = [(10,'maj7'),(7,'7'),(0,'m7'),(5,'7'),(2,'m7'),(7,'7'),(0,'m7'),(5,'7')]
BLUES_BB  = [(10,'7'),(3,'7'),(10,'7'),(10,'7'),(3,'7'),(4,'dim7'),
             (10,'7'),(7,'7'),(0,'m7'),(5,'7'),(10,'7'),(7,'7')]

JOBS = [
    ("ii-V-I dur (vsechny toniny)",  major_iiVI_cycle(), 120, ["auto", "bebop", "pentatonic"]),
    ("ii-V-i moll (vsechny toniny)", minor_iiVi_cycle(), 120, ["auto", "bebop"]),
    ("Rhythm Changes Bb",            RHYTHM_BB,           132, ["auto", "bebop"]),
    ("Jazz Blues Bb",                BLUES_BB,            120, ["auto", "bebop", "pentatonic"]),
]


def main():
    os.makedirs(TARGET, exist_ok=True)
    index = ["# SCALE DRILLS -- cvičná sada (bass + akord/takt + stupnicový dril)",
             "# střídavě nahoru/dolů, landing na guide tone dalšího akordu", ""]
    ok = 0
    for label, prog, bpm, scales in JOBS:
        index.append(f"## {label}  ({len(prog)} taktů, {bpm} bpm)")
        for kind in scales:
            name = f"{label} [{kind}]"
            out = os.path.join(TARGET, f"{name}.mid")
            try:
                sd.make_drill(prog, out, kind=kind, bpm=bpm, seed=5)
                index.append(f"   - {os.path.basename(out)}")
                ok += 1
                print(f"  -> {out}")
            except Exception as e:
                print(f"  !! {name}: {e}"); traceback.print_exc()
        index.append("")
    with open(os.path.join(TARGET, "index.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(index))
    print(f"\nHotovo: {ok} drilů -> {TARGET}")


if __name__ == "__main__":
    main()
