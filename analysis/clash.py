"""Najdi 'skripajici' tony: melodicke tony mimo akordovou stupnici na TEZKE dobe
(dlouhe/durazne) -- ty zni jako chyba, ne jako pruchodny ton."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "improved"))
from melody_v2 import PROGRESSIONS
from melody_top import make_melody
from evans_drill import BEBOP, SEV, nm, PC
from phrases_v3 import FORMS
from motif import generate_motivic

prog = PROGRESSIONS["autumn_leaves"]; form = FORMS["autumn_leaves"]; bpc = 4.0
line = generate_motivic(prog, form, seed=1)
def scale_pcs(r,q): return set((r+o)%12 for o in BEBOP.get(q,[0,2,4,5,7,9,10,11]))
def chord_pcs(r,q): return set((r+o)%12 for o in SEV.get(q,[0,4,7,10]))
bad=0
for o,d,p in sorted(line):
    ci=min(int(o//bpc),len(prog)-1); r,q=prog[ci]
    beatpos=o-ci*bpc
    strong = abs(beatpos-round(beatpos))<0.12 and d>=0.6   # na dobe a delsi
    inscale = p%12 in scale_pcs(r,q)
    if strong and not inscale:
        bad+=1
        print(f"  SKRIPE: {nm(p)} (dur {d:.2f}) na dobe {beatpos:.2f} nad {PC[r]}{q}  "
              f"[mimo stupnici]")
print(f"\ncelkem podezrelych tonu na tezke dobe: {bad} / {len(line)}")
