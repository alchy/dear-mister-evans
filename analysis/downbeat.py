"""Ověř tvrzení uživatele:
 (1) nota na ZAČÁTKU akordu (těžká doba) je občas mimo akord ("falešná"),
 (2) nota NÁJEZDU do nového akordu padá mimo akord.
Projdeme generování po fázích, ať vidíme, KDE se to kazí.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "improved"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "concept", "evans_melody_gen"))
from evans_drill import load_notes, SEV, BEBOP, nm, PC
from harmony import detect_progression
from voicings import generate_voicings
from motif import generate_motivic
from melody_top import declash, break_repeats
from phrases_v3 import FORMS  # nepouzito, jen pro jistotu

JAZZ = r"C:\Users\jindr\OneDrive\Jazz Learning"
TUNES = {
  "MyFunnyValentine": (JAZZ + r"\LESSON - My Funny Valenitne\My Funny Valentine.mid", 24),
  "Georgia": (JAZZ + r"\LESSON - Georgia\Georgia On My Mind 4 - transposed.mid", 24),
}
BPC = 4.0

def chord_pcs(r, q): return set((r+o) % 12 for o in SEV.get(q, [0,4,7,10]))
def scale_pcs(r, q): return set((r+o) % 12 for o in BEBOP.get(q, [0,2,4,5,7,9,10,11]))

def auto_form(prog, block=4):
    seen, labels = {}, []
    for bi in range((len(prog)+block-1)//block):
        sig = tuple(prog[bi*block:(bi+1)*block])
        seen.setdefault(sig, chr(ord('a')+len(seen)))
        labels.append(seen[sig])
    return labels

def analyze(name, line, prog):
    # ke kazdemu taktu najdi nejblizsi melodickou notu po jeho zacatku
    starts_bad = 0; starts_tot = 0
    detail = []
    for ci, (r, q) in enumerate(prog):
        bs = ci * BPC
        # prvni nota v tomto taktu
        innotes = [(o, d, p) for (o, d, p) in line if bs - 1e-6 <= o < bs + BPC]
        if not innotes:
            continue
        o, d, p = min(innotes, key=lambda x: x[0])
        starts_tot += 1
        cp = chord_pcs(r, q)
        offset = o - bs
        is_db = offset < 0.3
        if is_db and p % 12 not in cp:
            starts_bad += 1
            detail.append(f"    takt {ci:2d} {PC[r]}{q:5s}: START {nm(p)} @+{offset:.2f} "
                          f"MIMO akord (akord. tóny {sorted(cp)})")
    return starts_tot, starts_bad, detail

for tn, (path, bars) in TUNES.items():
    notes = load_notes(path)
    prog, key = detect_progression(notes, bar=BPC, max_bars=bars)
    form = auto_form(prog)
    voic = generate_voicings(prog, color=False, center=60)
    l0 = generate_motivic(prog, form, bpc=BPC, seed=1)
    l1 = declash(l0, voic, prog, bpc=BPC)
    l2 = break_repeats(l1, prog, bpc=BPC)
    print(f"\n########## {tn}  [{key}] ##########")
    for label, ln in [("po generovani", l0), ("po declash", l1), ("po break_repeats", l2)]:
        tot, bad, det = analyze(tn, ln, prog)
        print(f"  {label:18s}: start akordu MIMO akord: {bad}/{tot}")
    # vypis konkretni hrichy ve finale
    _, _, det = analyze(tn, l2, prog)
    for d in det: print(d)
