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
    "partners": ["peterson", "lines"],   # učený partner do prolnutí (Evans x ?)
    "counts":   ["vše", "2", "4", "6"],  # kolik akordů (taktů) z progrese
    "roots":    ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"],
    "start_qualities": ["m7", "maj7", "7", "m7b5"],
}
# délka/hustota melodických not -> not na dobu (sub); not na takt = sub*4
RHYTHMS = {
    "čtvrtky (4/takt)":   1,
    "osminy (8/takt)":    2,
    "trioly (12/takt)":   3,
    "šestnáctky (16/takt)": 4,
}
OPTIONS["rhythms"] = list(RHYTHMS)


def _sub(params):
    return RHYTHMS.get(str(params.get("rhythm", "")), 2)
DEFAULT_CHORDS = "Am7 D7 Gm7 Cm7 F7 Bbmaj7 Em7b5 A7"

# Vzory progresí v římských číslicích, jako (posun v půltónech od základního tónu,
# kvalita). "S" = použij uživatelem zvolenou kvalitu výchozího (base) akordu.
PROG_PATTERNS = {
    "I (jen tónika)":              [(0, "S")],
    "ii–V (dur)":                  [(0, "S"), (5, "7")],
    "ii–V–I (dur)":                [(0, "S"), (5, "7"), (10, "maj7")],
    "ii–V–I–vi (turnaround dur)":  [(0, "S"), (5, "7"), (10, "maj7"), (7, "m7")],
    "I–vi–ii–V (dur)":             [(0, "S"), (9, "m7"), (2, "m7"), (7, "7")],
    "I–VI–II–V (sekund. dom.)":    [(0, "S"), (9, "7"), (2, "7"), (7, "7")],
    "I–IV–iii–VI–ii–V (dur)":      [(0, "S"), (5, "maj7"), (4, "m7"), (9, "7"), (2, "m7"), (7, "7")],
    "I–vi–ii–V–iii–VI–ii–V (rhythm)": [(0, "S"), (9, "m7"), (2, "m7"), (7, "7"),
                                       (4, "m7"), (9, "7"), (2, "m7"), (7, "7")],
    "ii°–V–i (moll)":              [(0, "S"), (5, "7"), (10, "m7")],
    "i–iv–ii°–V (moll)":           [(0, "S"), (5, "m7"), (2, "m7b5"), (7, "7")],
    "i–VI–ii°–V (moll)":           [(0, "S"), (8, "maj7"), (2, "m7b5"), (7, "7")],
    "i–ii°–V–i (moll turnaround)": [(0, "S"), (2, "m7b5"), (7, "7"), (0, "m7")],
}
OPTIONS["patterns"] = list(PROG_PATTERNS)

_QSUFFIX = {"m7": "m7", "maj7": "maj7", "7": "7", "m7b5": "m7b5"}


def build_chords(root, quality, pattern):
    """Sestaví symboly progrese z base akordu (root+quality) a vzoru (římsky)."""
    roots = OPTIONS["roots"]
    ri = roots.index(root) if root in roots else 0
    out = []
    for off, q in PROG_PATTERNS.get(pattern, [(0, "S")]):
        qq = quality if q == "S" else q
        out.append(roots[(ri + off) % 12] + _QSUFFIX.get(qq, qq))
    return " ".join(out)

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
    sub = _sub(params)
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


def _parse_prog(params):
    """Symboly z pole akordů -> (progrese, symboly) se zkrácením na počet akordů."""
    syms = str(params["chords"]).split()
    if not syms:
        raise ValueError("prázdná progrese")
    cnt = str(params.get("count", "vše"))
    if cnt.isdigit():
        syms = syms[:int(cnt)] or syms
    return [parse_symbol(s) for s in syms], syms


def voicing_notes(params):
    """Pro náhled: [(symbol, bass, [voicing seřazený])] dle tvaru akordu.
    Voicing je seřazený -> hlas i lze párovat mezi akordy (voice-leading)."""
    import voicings as V
    prog, syms = _parse_prog(params)
    sub = _sub(params)
    center = 48 if sub == 3 else 52
    voic = V.generate_voicings(prog, center=center, style=params.get("voicing", "basic"))
    return [(syms[i], b, sorted(v)) for i, (b, v) in enumerate(voic)]


def preview_sequences(params):
    """Pro náhled per-takt: levá ruka (bas+voicing) i melodie v POŘADÍ hraní.
    -> [{label, bass, voicing[seřazený], mel[tóny v čase]}]. DRY pro obě části."""
    import voicings as V
    prog, syms = _parse_prog(params)
    recipe = build_recipe(params)
    sub = recipe["rhythm"]["sub"]
    voic = V.generate_voicings(prog, center=(48 if sub == 3 else 52),
                               style=recipe.get("voicing", "basic"))
    mel_bars = [[] for _ in prog]
    try:
        line, _ = pe.synth_generate(recipe, prog, model=_model_for(recipe),
                                    seed=int(params.get("seed", 1)))
        for onset, _dur, p in line:                # rozděl melodii po taktech (4 doby)
            bi = int(onset // 4.0)
            if 0 <= bi < len(prog):
                mel_bars[bi].append(p)
    except Exception:
        pass
    return [{"label": syms[i], "bass": b, "voicing": sorted(v), "mel": mel_bars[i]}
            for i, (b, v) in enumerate(voic)]


def generate(params, out_path):
    """Vygeneruje MIDI dle parametrů. Vrátí (cesta, seznam typů buněk po taktech)."""
    prog, _ = _parse_prog(params)
    recipe = build_recipe(params)
    model = _model_for(recipe)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    _, used = pe.synth_make(recipe, prog, out_path,
                            bpm=int(params.get("bpm", 108)), model=model,
                            seed=int(params.get("seed", 1)))
    return out_path, used


def _send(mid, port_name=None, stop_event=None):
    """Pošle MidiFile na port; stop_event přeruší + zhasne všechny tóny."""
    import mido
    name = port_name or default_port()
    if not name:
        raise RuntimeError("Nenalezen žádný MIDI-out port.")
    with mido.open_output(name) as out:
        for msg in mid.play():
            if stop_event is not None and stop_event.is_set():
                break
            out.send(msg)
        for ch in range(16):
            out.send(mido.Message('control_change', channel=ch, control=123, value=0))


def play(path, port_name=None, stop_event=None):
    """Přehraje MIDI soubor na zadaný port; stop_event přeruší."""
    import mido
    _send(mido.MidiFile(path), port_name, stop_event)


def play_block(kind, notes, port_name=None, stop_event=None, bpm=108, sub=3):
    """Přehraje jeden blok náhledu: kind='chord' (akord = vše naráz) nebo
    'line' (melodie = tóny v pořadí). notes = seznam MIDI not."""
    import mido
    notes = [int(n) for n in notes if n]
    if not notes:
        return
    mid = mido.MidiFile(); tr = mido.MidiTrack(); mid.tracks.append(tr)
    tpb = mid.ticks_per_beat
    tr.append(mido.MetaMessage('set_tempo', tempo=int(60000000 / max(1, bpm)), time=0))
    if kind == "chord":
        for n in notes:                                    # všechny tóny naráz
            tr.append(mido.Message('note_on', note=n, velocity=78, time=0))
        tr.append(mido.Message('note_off', note=notes[0], velocity=0, time=int(tpb * 2)))
        for n in notes[1:]:
            tr.append(mido.Message('note_off', note=n, velocity=0, time=0))
    else:                                                  # melodická linka v pořadí
        d = max(1, int(tpb / max(1, sub)))
        for n in notes:
            tr.append(mido.Message('note_on', note=n, velocity=92, time=0))
            tr.append(mido.Message('note_off', note=n, velocity=0, time=d))
    _send(mid, port_name, stop_event)
