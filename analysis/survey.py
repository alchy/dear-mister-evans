"""Projdi LESSON* složky a ohodnoť vhodnost každé skladby pro Evansovskou
extrakci (kvalita detekce harmonie). Vypíše seřazenou tabulku."""
import os, sys, glob
import numpy as np, mido
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "improved"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "concept", "evans_melody_gen"))
from evans_drill import load_notes
import harmony

JAZZ = r"C:\Users\jindr\OneDrive\Jazz Learning"
_KMAJ, _KMIN = harmony._KMAJ, harmony._KMIN

def meter(path):
    try:
        for tr in mido.MidiFile(path).tracks:
            for msg in tr:
                if msg.type == 'time_signature':
                    return msg.numerator, msg.denominator
    except Exception:
        pass
    return 4, 4

def total_chroma(notes):
    c = np.zeros(12)
    for o, d, p, v in notes:
        c[p % 12] += d * (v / 127.0)
    return c

def key_confidence(c):
    c = c - c.mean(); best = -1
    for r in range(12):
        for prof in (_KMAJ, _KMIN):
            p = np.roll(prof, r); p = p - p.mean()
            s = float(np.dot(c, p) / (np.linalg.norm(c)*np.linalg.norm(p)+1e-9))
            best = max(best, s)
    return best

rows = []
for d in sorted(glob.glob(os.path.join(JAZZ, "LESSON*"))):
    if not os.path.isdir(d): continue
    mids = sorted(glob.glob(os.path.join(d, "*.mid")))
    if not mids: continue
    name = os.path.basename(d).replace("LESSON - ", "")[:34]
    f = mids[0]
    try:
        notes = load_notes(f)
    except Exception as e:
        rows.append((0.0, name, "—", "chyba načtení", 0, 0, 0, 0.0, 0.0)); continue
    num, den = meter(f)
    tc = total_chroma(notes)
    kr, mode, kstr = harmony.estimate_key(tc)
    conf = key_confidence(tc)
    prog, _ = harmony.detect_progression(notes, max_bars=32)
    diat = harmony.diatonic_set(kr, mode)
    dfrac = sum(1 for ch in prog if ch in diat) / max(1, len(prog))
    changes = sum(1 for i in range(1, len(prog)) if prog[i] != prog[i-1])
    crate = changes / max(1, len(prog)-1)
    distinct = len(set(prog))
    score = 0.55*dfrac + 0.45*conf
    rows.append((score, name, f"{num}/{den}", kstr, len(prog), distinct,
                 changes, round(dfrac, 2), round(conf, 2)))

rows.sort(reverse=True)
print(f"{'score':>5} {'skladba':35} {'metr':5} {'tónina':9} "
      f"{'tak':>3} {'růz':>3} {'zm':>3} {'diat':>4} {'keyC':>4}  verdikt")
print("-"*108)
for score, name, met, kstr, nb, distinct, ch, dfrac, conf in rows:
    crate = ch/max(1, nb-1)
    if met.startswith("3/") or met.startswith("6/"):
        v = "valčík (3/4) – zatím 4/4 only"
    elif distinct < 3 or crate < 0.15:
        v = "statické – detekce přesmýčkuje"
    elif dfrac >= 0.7 and conf >= 0.70:
        v = "VÝBORNÉ"
    elif dfrac >= 0.55 and conf >= 0.62:
        v = "dobré"
    else:
        v = "slabší – detekce ujede"
    print(f"{score:5.2f} {name:35} {met:5} {kstr:9} {nb:3d} {distinct:3d} "
          f"{ch:3d} {dfrac:4.2f} {conf:4.2f}  {v}")
