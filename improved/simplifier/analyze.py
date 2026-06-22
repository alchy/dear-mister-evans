"""analyze -- jeden vstup: živé MIDI -> kompletní dynamická analýza.

Spojuje fáze: beat-tracking -> akordy (lokální tónina) -> downbeaty (harmonický
rytmus). Vrací vše, co potřebuje devplay (poslech) i licks (export).
"""
from collections import namedtuple
import numpy as np
from . import io_midi, beats, chords, meter

Analysis = namedtuple("Analysis", "notes grid spans downbeats keys")


def analyze(notes):
    grid = beats.track(notes)
    spans, keys = chords.label_beats(notes, grid)
    db = meter.downbeats(notes, grid, spans)
    return Analysis(notes=notes, grid=grid, spans=spans, downbeats=db, keys=keys)


def from_file(path):
    return analyze(io_midi.load_notes(path))
