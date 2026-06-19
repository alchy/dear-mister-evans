"""
chords.py -- tenká vrstva nad evans_drill.py.

Poskytuje detekci akordů a voicingy levé ruky pro zbytek projektu, ať se to
nemusí duplikovat. Veškerá těžká práce je v evans_drill.py (chroma + Viterbi).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evans_drill import (
    load_notes,        # (path) -> [(onset_beats, dur_beats, pitch, vel), ...]
    detect_chords,     # (notes) -> [[root, quality, present_pcs(set)], ...]  (sloučené)
    chord_pcs,         # (root, quality, present) -> 4 pitch-classy septakordu + barvy
    lh_voicing,        # (pcs, center=48) -> voicing levé ruky (MIDI), cluster ~C3
    BEBOP, SEV, TEMPL, QNAME, PC, nm, lab,
)

__all__ = ["load_notes", "detect_chords", "chord_pcs", "lh_voicing",
           "BEBOP", "SEV", "TEMPL", "QNAME", "PC", "nm", "lab",
           "chord_scale_pitches"]


def chord_scale_pitches(root, quality, lo=0, hi=127):
    """Vrátí všechny MIDI tóny v rozsahu [lo,hi], které patří do bebop/akordové
    stupnice daného akordu. Tím je definovaná 'dovolená' melodická paleta."""
    pcs = set((root + o) % 12 for o in BEBOP.get(quality, [0, 2, 4, 5, 7, 9, 10, 11]))
    return sorted(p for p in range(lo, hi + 1) if p % 12 in pcs)
