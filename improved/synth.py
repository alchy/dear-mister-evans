#!/usr/bin/env python3
"""
synth.py -- SYNTEZÁTOR cvičení: skládá linku z VAH typů patternů (pravidlové
buňky scale/arpeggio/run + naučený/prolnutý markov) a z PROLNUTÍ modelu
(Evans <-> Peterson, váha alpha). Vše je recept (data) -> bez zásahu do enginu.

Recept (dict):
  rhythm : {sub, group, swing, in_four}
  scale  : auto | bebop | pentatonic | jazz_color
  cells  : {"run": 0.45, "markov": 0.55, "scale": .., "arpeggio": ..}  # váhy typů
  cell_cfg : per-typ parametry (enclose, temp, var, ...)
  blend_alpha : 1=Evans .. 0=Peterson (pro markov buňku)

Použití:
  python improved/synth.py --recipe evans_peterson_in_four \
      --chords "Am7 D7 Gm7 Cm7 F7 Bbmaj7 Em7b5 A7" --alpha 0.5 --bpm 108
  # nebo přímo váhy:
  python improved/synth.py --cells "run=0.5,markov=0.5,scale=0.2" --scale bebop
"""
import os, sys, copy, argparse
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import pattern_engine as pe
import blend_markov as bl
import melody_markov as mm
from arrange_chords import parse_symbol


def model_for(recipe):
    """Vrátí model pro markov buňku dle blend_alpha (1=Evans, jinak prolnutí)."""
    if "markov" not in recipe.get("cells", {}):
        return None
    a = recipe.get("blend_alpha", 1.0)
    if a >= 0.999:
        return mm.get_model("evans")
    m = bl.get_blend(alpha=a, verbose=False)
    return m if m is not None else mm.get_model("evans")


def parse_cells(s):
    out = {}
    for part in s.split(","):
        if "=" in part:
            k, v = part.split("="); out[k.strip()] = float(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="evans_peterson_in_four",
                    choices=list(pe.RECIPES))
    ap.add_argument("--chords", default="Am7 D7 Gm7 Cm7 F7 Bbmaj7 Em7b5 A7")
    ap.add_argument("--alpha", type=float, default=None, help="prepíše blend_alpha")
    ap.add_argument("--cells", default=None, help="prepíše váhy, např. run=0.5,markov=0.5")
    ap.add_argument("--scale", default=None, help="prepíše stupnici")
    ap.add_argument("--voicing", default=None, choices=["basic", "rootless", "color"],
                    help="tvar akordu LH: basic(R357) | rootless(Evans) | color(alterace)")
    ap.add_argument("--bpm", type=int, default=108)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--render", default="outputs_pat/synth.mid")
    a = ap.parse_args()

    recipe = copy.deepcopy(pe.RECIPES[a.recipe])
    if a.alpha is not None:
        recipe["blend_alpha"] = a.alpha
    if a.cells:
        recipe["cells"] = parse_cells(a.cells)
    if a.scale:
        recipe["scale"] = a.scale
    if a.voicing:
        recipe["voicing"] = a.voicing

    prog = [parse_symbol(s) for s in a.chords.split()]
    model = model_for(recipe)
    os.makedirs(os.path.dirname(a.render), exist_ok=True)
    line, used = pe.synth_make(recipe, prog, a.render, bpm=a.bpm, model=model, seed=a.seed)
    print(f"recept '{a.recipe}'  váhy={recipe['cells']}  alpha={recipe.get('blend_alpha')}")
    print("typy buněk po taktech:", " ".join(used))
    print(f"-> {a.render}")


if __name__ == "__main__":
    main()
