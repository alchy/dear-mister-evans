"""
run_markov_demo.py -- kompletní ukázka řetězce: data -> model -> variace MIDI.

Spuštění z kořene projektu:
    python examples/run_markov_demo.py
"""
import os, sys
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from chords import load_notes, detect_chords, lab
from markov import train_model, generate_line, render

DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "outputs")
os.makedirs(OUT, exist_ok=True)

# 1) trénink na všech skladbách (1 verze na skladbu)
model = train_model(os.path.join(DATA, "be-slice*.mid"))

# 2) vezmi akordovou progresi z libovolného souboru (nebo si zadej ručně)
notes = load_notes(os.path.join(DATA, "be-slice03.mid"))   # Emily
merged = detect_chords(notes)
progression = [(r, q) for r, q, pr in merged[:8]]
present = [pr for r, q, pr in merged[:8]]
print("Progrese:", " -> ".join(lab(r, q) for r, q in progression))

# 3) vygeneruj několik variací (různé seedy / teploty)
for k, temp in [(1, 0.7), (2, 0.9), (3, 1.1)]:
    line = generate_line(model, progression, temperature=temp, seed=k)
    out = os.path.join(OUT, f"demo_variation_{k}_t{temp}.mid")
    render(progression, present, line, out)
    print(f"  varianta {k} (teplota {temp}) -> {out}")

print("\nHotovo. Porovnej outputs/demo_variation_*.mid — vyšší teplota = víc variace.")
print("Dál: uprav tokenizaci/rytmus v src/markov.py, pak zkus src/nn_baseline.py.")
