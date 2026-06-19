#!/usr/bin/env python3
"""
gallery.py -- davkove vyrob Evansovske aranze vybranych jazzovych standardu
do slozky gallery/ + index.txt k pozdejsimu prochazeni.

Spousteni:
    python improved/gallery.py
"""
import os, sys, glob, traceback
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

from arrange import arrange
from harmony import PC

JAZZ = r"C:\Users\jindr\OneDrive\Jazz Learning"
OUT = os.path.join(HERE, "..", "gallery")

# (klicove slovo ve jmenu LESSON slozky, bpm, kolik taktu) -- jazzove standardy,
# 4/4 (valciky a klasiku schvalne vynechavam)
PICKS = [
    ("Afternoon in Paris", 132, 32),
    ("Bill Evans (Jazz Jane)", 120, 24),     # be-slice01 = I Hear a Rhapsody
    ("Estat", 100, 24),                      # Estate
    ("Georgia", 96, 24),
    ("Misty", 92, 24),
    ("Moon River", 96, 24),
    ("My Funny Valenitne", 100, 24),
    ("My One and Only Love", 92, 24),
    ("Round Midnight", 80, 24),
    ("Lazy River", 120, 24),
    ("Tiptoes", 120, 24),
    ("Englisman in NewYork", 100, 24),
]

def find_midi(keyword):
    for d in glob.glob(os.path.join(JAZZ, f"*{keyword}*")):
        if os.path.isdir(d):
            mids = sorted(glob.glob(os.path.join(d, "*.mid")))
            if mids:
                return mids[0]
    return None

def main():
    os.makedirs(OUT, exist_ok=True)
    index = ["# GALERIE -- Evansovske aranze (key-aware detekce)\n"]
    for keyword, bpm, bars in PICKS:
        f = find_midi(keyword)
        if not f:
            print(f"!! nenalezeno: {keyword}"); continue
        print(f"\n== {keyword} ==  ({os.path.basename(f)})")
        try:
            r = arrange(f, bars=bars, bpm=bpm, melody=True, out_dir=OUT, seed=1)
            prog = " | ".join(f"{PC[a]}{q}" for a, q in r["prog"])
            index.append(f"## {keyword}   [tonina: {r['key']}]")
            index.append(f"   zdroj : {os.path.basename(f)}")
            index.append(f"   forma : {''.join(r['form'])}")
            index.append(f"   akordy: {prog}")
            index.append(f"   soubory: " + ", ".join(os.path.basename(o) for o in r["outs"]))
            index.append("")
        except Exception as e:
            print(f"!! chyba u {keyword}: {e}")
            traceback.print_exc()
    with open(os.path.join(OUT, "index.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(index))
    print(f"\nHotovo -> {OUT}\\  (viz index.txt)")

if __name__ == "__main__":
    main()
