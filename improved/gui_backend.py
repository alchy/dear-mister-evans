#!/usr/bin/env python3
"""
gui_backend.py -- TENKÁ FASÁDA mezi GUI a generátorem.

GUI zná JEN tohle rozhraní (ne vnitřek enginu) -> backend lze vyměnit beze změny
GUI. Poskytuje: výčet voleb (OPTIONS), generování do MIDI (generate) a přehrání
s možností Stop (play / list_ports).
"""
import os, sys, threading
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import pattern_engine as pe
import blend_markov as bl
import melody_markov as mm
import player
from arrange_chords import parse_symbol

OPTIONS = {
    "voicings": ["basic", "rootless", "color"],
    "scales":   ["auto", "bebop", "pentatonic", "jazz_color"],
    "cells":    ["run", "markov", "scale", "arpeggio"],
    "rhythms":  ["trioly (3)", "osminy (2)"],
    "partners": ["peterson", "lines"],   # učený partner do prolnutí (Evans x ?)
}
DEFAULT_CHORDS = "Am7 D7 Gm7 Cm7 F7 Bbmaj7 Em7b5 A7"

# výchozí parametry buněk (pravidlové i markov)
_CELL_CFG = {
    "run":      {"enclose": True, "enc_p": 0.5, "skip": 0.24, "rev": 0.2},
    "markov":   {"temp": 1.0},
    "scale":    {"var": 0.28, "dir": "alt"},
    "arpeggio": {"step": 2, "starts": "up3", "pickup": "chromatic", "dir": "down"},
}


def list_ports():
    try:
        import mido
        return mido.get_output_names()
    except Exception:
        return []


def default_port():
    """loopMIDI Port 1 (Vienna), jinak Wavetable, jinak první dostupný."""
    names = list_ports()
    for want in ("loopmidi port 1", "wavetable"):
        for n in names:
            if want in n.lower():
                return n
    return names[0] if names else ""


def build_recipe(params):
    """params (dict z GUI) -> recept pro pattern_engine.synth_make."""
    sub = 3 if str(params.get("rhythm", "trioly (3)")).startswith("trioly") else 2
    cells = {k: float(v) for k, v in params.get("cells", {}).items() if float(v) > 0}
    if not cells:
        cells = {"markov": 1.0}
    return {
        "rhythm": {"sub": sub, "group": 4, "swing": 0.11 if sub == 2 else 0,
                   "in_four": bool(params.get("in_four", sub == 3))},
        "scale": params.get("scale", "bebop"),
        "voicing": params.get("voicing", "basic"),
        "target": "guide_tone",
        "range": [55, 88] if sub == 3 else [60, 86],
        "cells": cells,
        "cell_cfg": {k: dict(_CELL_CFG[k]) for k in cells if k in _CELL_CFG},
        "blend_alpha": float(params.get("alpha", 0.5)),
        "partner": params.get("partner", "peterson"),
    }


def _model_for(recipe):
    if recipe["cells"].get("markov", 0) <= 0:
        return None
    a = recipe.get("blend_alpha", 0.5)
    if a >= 0.999:
        return mm.get_model("evans")
    return bl.get_blend(alpha=a, partner=recipe.get("partner", "peterson"),
                        verbose=False) or mm.get_model("evans")


def generate(params, out_path):
    """Vygeneruje MIDI dle parametrů. Vrátí (cesta, seznam typů buněk po taktech)."""
    prog = [parse_symbol(s) for s in str(params["chords"]).split()]
    if not prog:
        raise ValueError("prázdná progrese")
    recipe = build_recipe(params)
    model = _model_for(recipe)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    _, used = pe.synth_make(recipe, prog, out_path,
                            bpm=int(params.get("bpm", 108)), model=model,
                            seed=int(params.get("seed", 1)))
    return out_path, used


def play(path, port_name=None, stop_event=None):
    """Přehraje MIDI na zadaný port; stop_event (threading.Event) přeruší."""
    import mido
    name = port_name or default_port()
    if not name:
        raise RuntimeError("Nenalezen žádný MIDI-out port.")
    with mido.open_output(name) as out:
        for msg in mido.MidiFile(path).play():
            if stop_event is not None and stop_event.is_set():
                break
            out.send(msg)
        for ch in range(16):
            out.send(mido.Message('control_change', channel=ch, control=123, value=0))
