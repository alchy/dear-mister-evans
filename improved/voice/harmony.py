"""harmony -- akordy -> harmonický kontext per takt (Levinovsky).

Poskytuje to, co builder linky potřebuje: voice-led rootless voicing + bas, a hlavně
KONTEXTOVĚ zvolenou chord-scale (dle funkce: V->moll = altered/frygická dominanta,
m7b5 = lokrická ♮2, ...), chord-tóny a guide tóny (3/7 = landing cíle).

Viz TIPS_WEB.md (mapování funkce->chord-scale) a LINE_DEVICES.md.
"""
import os, sys

_HERE = os.path.dirname(__file__)
_ROOT = os.path.dirname(_HERE)                      # improved/
for _p in (_ROOT, os.path.join(_ROOT, "..", "concept", "evans_melody_gen")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from voice import voicings as Vc
from arrange_chords import parse_symbol

# --- akordové tóny (půltóny od kořene): 1, 3, 5, 7 ---
CHORD_TONES = {
    "maj7": [0, 4, 7, 11], "6": [0, 4, 7, 9], "m7": [0, 3, 7, 10], "m6": [0, 3, 7, 9],
    "mmaj7": [0, 3, 7, 11], "7": [0, 4, 7, 10], "m7b5": [0, 3, 6, 10], "dim7": [0, 3, 6, 9],
}
# --- pojmenované stupnice (půltóny od kořene) ---
SCALES = {
    "lydian": [0, 2, 4, 6, 7, 9, 11], "ionian": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "mixo_b6": [0, 2, 4, 5, 7, 8, 10], "locrian": [0, 1, 3, 5, 6, 8, 10],
    "locrian_n2": [0, 2, 3, 5, 6, 8, 10], "altered": [0, 1, 3, 4, 6, 8, 10],
    "lydian_dom": [0, 2, 4, 6, 7, 9, 10], "phrygian_dom": [0, 1, 4, 5, 7, 8, 10],
    "mel_minor": [0, 2, 3, 5, 7, 9, 11], "harm_minor": [0, 2, 3, 5, 7, 8, 11],
    "dim_wh": [0, 2, 3, 5, 6, 8, 9, 11], "dim_hw": [0, 1, 3, 4, 6, 7, 9, 10],
    "bebop_dom": [0, 2, 4, 5, 7, 9, 10, 11], "bebop_maj": [0, 2, 4, 5, 7, 8, 9, 11],
}

# vestavěné šablony progresí (changes = funkční data; dur i moll)
TEMPLATES = {
    "ii–V–I dur (C)":      "Dm7 G7 Cmaj7 Cmaj7",
    "ii–V–i moll (A)":     "Bm7b5 E7 Am7 Am7",
    "I–vi–ii–V (C)":       "Cmaj7 Am7 Dm7 G7",
    "jazz blues F":        "F7 Bb7 F7 F7 Bb7 Bb7 F7 D7 Gm7 C7 F7 D7",
    "minor blues C":       "Cm7 Cm7 Cm7 Cm7 Fm7 Fm7 Cm7 Cm7 Dm7b5 G7 Cm7 G7",
    "rhythm changes A (Bb)": "Bbmaj7 G7 Cm7 F7 Dm7 G7 Cm7 F7",
    "Autumn Leaves A (G)": "Am7 D7 Gmaj7 Cmaj7 F#m7b5 B7 Em7 Em7",
}


def scale_name_for(q, resolves_to_minor=False, color="inside"):
    """Funkce akordu -> název chord-scale. color: 'inside' krotčí, 'outside' napjatější."""
    if q in ("maj7", "6"):
        return "lydian"
    if q in ("m7", "m6"):
        return "dorian"
    if q == "mmaj7":
        return "mel_minor"
    if q == "m7b5":
        return "locrian_n2"
    if q == "dim7":
        return "dim_wh"
    if q == "7":
        if resolves_to_minor:
            return "altered" if color == "outside" else "phrygian_dom"
        return "bebop_dom" if color == "inside" else "lydian_dom"
    return "mixolydian"


def _pitches(offsets, root, lo, hi):
    pcs = set((root + o) % 12 for o in offsets)
    return sorted(p for p in range(lo, hi + 1) if p % 12 in pcs)


class Bar:
    """Harmonický kontext jednoho taktu."""
    def __init__(self, root, quality, bass, voicing, scale, scale_name, chord_tones, guides):
        self.root = root; self.quality = quality
        self.bass = bass; self.voicing = voicing
        self.scale = scale; self.scale_name = scale_name
        self.chord_tones = chord_tones      # MIDI tóny 1/3/5/7 v rozsahu
        self.guides = guides                # MIDI tóny 3/7 v rozsahu (landing cíle)

    def degree_of(self, pitch):
        return min(range(len(self.scale)), key=lambda k: abs(self.scale[k] - pitch))


class Harmony:
    """Progrese (string/[(root,q)]) -> [Bar]. Chord-scale dle FUNKCE (kontextově,
    z následujícího akordu). color = 'inside' | 'outside' (napětí dominant->moll)."""
    def __init__(self, progression, lo=55, hi=88, center=None, color="inside",
                 voicing="rootless"):
        # center = referenční rejstřík MELODIE; voicing = TYP rozložení LH (viz voicings).
        self.lo, self.hi = lo, hi
        self.center = center if center is not None else (lo + hi) // 2
        self.color = color
        prog = self._parse(progression)
        voics = Vc.generate(prog, kind=voicing)
        self.bars = []
        for i, (root, q) in enumerate(prog):
            nr, nq = prog[(i + 1) % len(prog)]
            to_minor = (q == "7" and nr == (root + 5) % 12 and nq in ("m7", "m6", "mmaj7", "m7b5"))
            name = scale_name_for(q, to_minor, color)
            scale = _pitches(SCALES[name], root, lo, hi)
            chord_tones = _pitches(CHORD_TONES.get(q, [0, 4, 7, 10]), root, lo, hi)
            guides = _pitches([CHORD_TONES.get(q, [0, 4, 7, 10])[k] for k in (1, 3)], root, lo, hi)
            bass, voic = voics[i]
            self.bars.append(Bar(root, q, bass, sorted(voic), scale, name, chord_tones, guides))

    @staticmethod
    def _parse(progression):
        if isinstance(progression, str):
            return [parse_symbol(s) for s in progression.replace("|", " ").split()]
        return list(progression)

    def __len__(self):
        return len(self.bars)

    def __getitem__(self, i):
        return self.bars[i]
