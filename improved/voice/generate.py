"""generate -- DOČASNÝ triviální generátor (fáze ②) jen pro ověření harmonie/renderu.

Krokový pohyb v chord-scale každého taktu, start i přiblížení k landingu na guide
tónu. Tohle NENÍ cílový model -- ve fázi ③ ho nahradí jeden kontextově podmíněný
melodický model (scale-degree, Evans prior + feedback). Záměrně hloupý a deterministický.
"""
import random

BPC = 4.0   # dob na takt


def trivial_line(harmony, density=2, seed=1):
    """harmony = Harmony, density = not/dobu (1/2/3/4) -> [(onset, délka, MIDI)]."""
    rng = random.Random(seed)
    npb = density * 4
    ref = (harmony.lo + harmony.hi) // 2
    line = []
    for i, bar in enumerate(harmony.bars):
        sc = bar.scale
        if not sc:
            continue
        start = min(bar.guides, key=lambda g: abs(g - ref)) if bar.guides else sc[len(sc) // 2]
        ci = bar.degree_of(start)
        d = 1 if i % 2 == 0 else -1
        for n in range(npb):
            line.append((i * BPC + n / density, (1.0 / density) * 0.9, sc[ci]))
            step = d * (1 if rng.random() < 0.8 else 2)     # převážně krok, občas tercie
            ni = ci + step
            if ni < 0 or ni >= len(sc):                     # odraz od krajů stupnice
                d = -d; ni = ci + d
            ci = max(0, min(len(sc) - 1, ni))
    return line
