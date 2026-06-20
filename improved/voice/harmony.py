"""harmony -- akordy -> harmonický kontext per takt.

Tenký, čistý port osvědčených funkcí z prototypu (voicingy, chord-scale, guide tóny).
Poskytuje to, co melodický model potřebuje: pro každý takt voice-led voicing + bas,
chord-scale (prostor, ve kterém se melodie pohybuje) a guide tóny (landing cíle).
"""
import os, sys

_HERE = os.path.dirname(__file__)
_ROOT = os.path.dirname(_HERE)                      # improved/
for _p in (_ROOT, os.path.join(_ROOT, "..", "concept", "evans_melody_gen")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scale_drill as sd
import voicings as V
from arrange_chords import parse_symbol


class Bar:
    """Harmonický kontext jednoho taktu (akordu)."""
    def __init__(self, root, quality, bass, voicing, scale, guides):
        self.root = root          # pitch class (0..11)
        self.quality = quality    # 'm7' | 'maj7' | '7' | 'm7b5' | ...
        self.bass = bass          # MIDI bas
        self.voicing = voicing    # MIDI tóny levé ruky (seřazené)
        self.scale = scale        # vzestupné MIDI tóny chord-scale (prostor melodie)
        self.guides = guides      # guide tóny (3., 7.) v rozsahu = landing cíle

    def degree_of(self, pitch):
        """Index ve scale nejblíž danému MIDI tónu (scale-degree pozice)."""
        return min(range(len(self.scale)), key=lambda k: abs(self.scale[k] - pitch))


class Harmony:
    """Progrese (string '|'/mezery, nebo [(root,quality)]) -> seznam Bar.
    Voicingy: rootless Evans s nejúspornějším voice-leadingem. Chord-scale: bebop
    (deterministická kanonická stupnice akordu -> stabilní scale-degree prostor)."""
    def __init__(self, progression, lo=55, hi=88, center=63):
        self.lo, self.hi, self.center = lo, hi, center
        prog = self._parse(progression)
        voics = V.generate_voicings(prog, center=center, style="rootless")
        self.bars = []
        for (root, q), (bass, voic) in zip(prog, voics):
            scale = sd.jazz_scale(root, q, lo, hi, "bebop")     # kanonický chord-scale
            guides = sd.guide_pitches(root, q, lo, hi)
            self.bars.append(Bar(root, q, bass, sorted(voic), scale, guides))

    @staticmethod
    def _parse(progression):
        if isinstance(progression, str):
            return [parse_symbol(s) for s in progression.replace("|", " ").split()]
        return list(progression)

    def __len__(self):
        return len(self.bars)

    def __getitem__(self, i):
        return self.bars[i]
