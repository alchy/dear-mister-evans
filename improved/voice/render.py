"""render -- (harmonie + melodická linka) -> MIDI.

Tenký wrapper nad osvědčeným renderem prototypu (LH bas+akord/takt sustain, RH linka
dle vlastních nástupů/délek, lehký akcent na 1. dobu).
"""
import os, sys

_HERE = os.path.dirname(__file__)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import scale_drill as sd


def to_midi(harmony, line, out, bpm=110, density=2):
    """harmony = Harmony, line = [(onset_dob, délka_dob, MIDI)] -> uloží MIDI do 'out'."""
    prog = [(b.root, b.quality) for b in harmony.bars]
    voics = [(b.bass, b.voicing) for b in harmony.bars]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sd.render_line(prog, voics, line, out, bpm=bpm, accent_group=0, sub=density)
    return out
