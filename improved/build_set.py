#!/usr/bin/env python3
"""
build_set.py -- vyrob "Simplified Evans" učební sadu do OneDrive.

Zpracuje (a) tvé nahrávky z Jazz Jane (1 verze na skladbu, pojmenované skutečnými
názvy) a (b) doporučené jazzové standardy. Výstup: __full.mid (s melodií) a
__harmony.mid (jen voicingy) + index.txt.

Spuštění:
    python improved/build_set.py
"""
import os, sys, glob, traceback
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))
from arrange import arrange
from harmony import PC

JAZZ = r"C:\Users\jindr\OneDrive\Jazz Learning"
JJ = os.path.join(JAZZ, "LESSON - Bill Evans (Jazz Jane)")
TARGET = os.path.join(JAZZ, "LESSON - Simplified Evans")

# (název výstupu, zdrojové MIDI, bpm, takty)
JOBS = [
    # --- tvé nahrávky (1 verze na skladbu, dle mapy v SPEC) ---
    ("I Hear a Rhapsody (Evans)", os.path.join(JJ, "be-slice01.mid"), 126, 32),
    ("Nardis (Evans)",            os.path.join(JJ, "be-slice02.mid"), 132, 32),
    ("Emily (Evans)",             os.path.join(JJ, "be-slice03.mid"), 110, 32),
    ("Young and Foolish (Evans)", os.path.join(JJ, "be-slice04.mid"),  96, 32),
    ("Falling Grace (Evans)",     os.path.join(JJ, "be-slice05.mid"), 120, 32),
    ("Invitation (Evans)",        os.path.join(JJ, "be-slice06.mid"), 116, 32),
    ("Tenderly (Evans)",          os.path.join(JJ, "be-slice07.mid"), 110, 32),
    # --- doporučené standardy ---
    ("My One and Only Love",
     glob.glob(os.path.join(JAZZ, "LESSON - My One and Only Love", "*.mid"))[:1],  92, 32),
    ("Misty",
     glob.glob(os.path.join(JAZZ, "LESSON - Misty", "*.mid"))[:1],                 92, 32),
    ("My Funny Valentine",
     glob.glob(os.path.join(JAZZ, "LESSON - My Funny Valenitne", "*.mid"))[:1],   100, 32),
    ("Estate",
     glob.glob(os.path.join(JAZZ, "LESSON - Estaté", "*.mid"))[:1],               104, 32),
    ("Autumn Leaves",
     glob.glob(os.path.join(JAZZ, "LESSON - Autumn Leaves", "*.mid"))[:1],        116, 32),
]

def resolve(src):
    if isinstance(src, list):
        return src[0] if src else None
    return src if os.path.exists(src) else None

def main():
    os.makedirs(TARGET, exist_ok=True)
    index = ["# SIMPLIFIED EVANS -- učební sada", ""]
    ok = 0
    for label, src, bpm, bars in JOBS:
        path = resolve(src)
        if not path:
            print(f"!! přeskakuji (nenalezeno): {label}"); continue
        print(f"\n== {label} ==")
        try:
            r = arrange(path, bars=bars, bpm=bpm, melody=True,
                        out_dir=TARGET, seed=1, name=label)
            prog = " | ".join(f"{PC[a]}{q}" for a, q in r["prog"])
            index += [f"## {label}   [tónina: {r['key']}, {bpm} bpm]",
                      f"   zdroj : {os.path.basename(path)}",
                      f"   akordy: {prog}", ""]
            ok += 1
        except Exception as e:
            print(f"!! chyba u {label}: {e}"); traceback.print_exc()
    with open(os.path.join(TARGET, "index.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(index))
    print(f"\nHotovo: {ok}/{len(JOBS)} -> {TARGET}")

if __name__ == "__main__":
    main()
