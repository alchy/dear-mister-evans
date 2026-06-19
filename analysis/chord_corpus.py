"""Kolik harmonického materiálu je v uživatelově sbírce a co by se model učil?
Z každého LESSON MIDI vytáhne progresi (key-aware), převede akordy RELATIVNĚ KE
KLÍČI (aby se ii-V-I naučilo jednou, ne 12x), a spočítá přechody (bigramy)."""
import os, sys, glob
from collections import Counter
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "improved"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "concept", "evans_melody_gen"))
from evans_drill import load_notes
import harmony

JAZZ = r"C:\Users\jindr\OneDrive\Jazz Learning"
DEG = {0:'I',1:'bII',2:'ii',3:'bIII',4:'iii',5:'IV',6:'#IV',7:'V',8:'bVI',9:'vi',10:'bVII',11:'vii'}

def total_chroma(notes):
    c = np.zeros(12)
    for o,d,p,v in notes: c[p%12] += d*(v/127.0)
    return c

def rel_token(root, quality, key_root):
    return f"{DEG[(root-key_root)%12]}:{quality}"

tunes = 0; chords = 0
bigrams = Counter(); unigrams = Counter()
for d in sorted(glob.glob(os.path.join(JAZZ, "LESSON*"))):
    mids = sorted(glob.glob(os.path.join(d, "*.mid")))
    if not mids: continue
    try:
        notes = load_notes(mids[0])
        prog, _ = harmony.detect_progression(notes, max_bars=64)
        kr, mode, _ = harmony.estimate_key(total_chroma(notes))
    except Exception:
        continue
    toks = []
    for r, q in prog:
        t = rel_token(r, q, kr)
        if not toks or toks[-1] != t:   # sluč opakování
            toks.append(t)
    tunes += 1; chords += len(toks)
    for t in toks: unigrams[t] += 1
    for i in range(1, len(toks)):
        bigrams[(toks[i-1], toks[i])] += 1

print(f"skladeb: {tunes}")
print(f"akordů (po sloučení opakování): {chords}")
print(f"přechodů (bigramů): {sum(bigrams.values())}")
print(f"unikátních akordů: {len(unigrams)} | unikátních přechodů: {len(bigrams)}")
print("\n=== 18 nejčastějších PŘECHODŮ (relativně ke klíči) ===")
for (a, b), n in bigrams.most_common(18):
    print(f"  {a:10} -> {b:10}   {n}x")
print("\n=== 12 nejčastějších akordů ===")
for t, n in unigrams.most_common(12):
    print(f"  {t:10} {n}x")
