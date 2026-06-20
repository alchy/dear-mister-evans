#!/usr/bin/env python3
"""
build_drill_library.py -- strukturovaná cvičebnice stupnicových drilů.

Každý CÍL cvičení (dur / moll) × každá VARIANTA stupnic (bebop / pentatonika /
auto) = vlastní složka. V ní jeden MIDI na progresi (4-8 taktů různých akordů,
pravá ruka = stupnicový dril, levá = bas+akord na takt) + README.md
(co se cvičí + jaká stupnice + jak přesně bylo vygenerováno).

Spuštění:  python improved/build_drill_library.py
"""
import os, sys, traceback
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import scale_drill as sd
from arrange_chords import parse_symbol

ROOT = r"C:\Users\jindr\OneDrive\Jazz Learning\LESSON - Scale Drills"

# varianty stupnic -> (přípona složky, popis do README)
SCALES = {
    "bebop":      ("bebop",       "bebopové stupnice (8-tónové, s chromatickým průchodem)"),
    "pentatonic": ("pentatonika", "pentatonické stupnice (dur/moll/dominantní)"),
    "auto":       ("auto",        "pestrá jazzová paleta (ionská, lydická, mixo, dorská, "
                                  "melodická moll, altered, lydická dom., lokrická, "
                                  "diminished, pentatonika...) — mění se po taktech"),
}


def prog_of(symbols):
    return [parse_symbol(s) for s in symbols.split()]


LIBRARY = [
    {
        "base": "dur-stupnice-evans",
        "goal": "Cvičení DUROVÝCH jazzových stupnic přes funkční progrese (různé "
                "akordy po taktech, ne jen ii-V-I). Pravá ruka = stupnicový dril "
                "(nahoru/dolů + variace), levá = bas + akord na takt. Každý běh "
                "dosedá na guide tone (3./7.) dalšího akordu.",
        "progs": [
            ("C-dur I-vi-ii-V",        "Cmaj7 Am7 Dm7 G7 Em7 A7 Dm7 G7",        120),
            ("F-dur I-IV-iii-VI-ii-V", "Fmaj7 Bbmaj7 Am7 D7 Gm7 C7 Fmaj7 D7",  120),
            ("Bb-dur ii-V-I varianty", "Cm7 F7 Bbmaj7 Gm7 Cm7 F7 Bbmaj7 G7",   126),
            ("Eb-dur ii-V-I",          "Fm7 Bb7 Ebmaj7 Cm7 Fm7 Bb7 Ebmaj7 C7", 120),
            ("G-dur I-IV-iii-VI",      "Gmaj7 Cmaj7 Bm7 E7 Am7 D7 Gmaj7 E7",   120),
            ("D-dur ii-V-I-VI",        "Em7 A7 Dmaj7 Bm7 Em7 A7 Dmaj7 B7",     120),
        ],
    },
    {
        "base": "minor-stupnice-evans",
        "goal": "Cvičení MOLOVÝCH jazzových stupnic přes funkční mollové progrese. "
                "Pravá ruka = stupnicový dril, levá = bas + akord na takt. Mollové "
                "ii-V-i, dosedání na guide tone dalšího akordu.",
        "progs": [
            ("C-moll i-iv-ii-V",      "Cm7 Fm7 Dm7b5 G7 Cm7 Fm7 Dm7b5 G7",      116),
            ("D-moll Alone Together", "Em7b5 A7 Dm6 Gm7 Em7b5 A7 Dm6 A7",       112),
            ("A-moll Black Orpheus",  "Am7 Bm7b5 E7 Am7 Dm7 G7 Cmaj7 Bm7b5",    112),
            ("G-moll Autumn Leaves",  "Cm7 F7 Bbmaj7 Ebmaj7 Am7b5 D7 Gm6 D7",   120),
            ("E-moll Nardis",         "Em7 Am7 Dm7 G7 Cmaj7 Am7 F#m7b5 B7",     112),
            ("C-moll Solar usek",     "Cm7 Gm7 C7 Fmaj7 Fm7 Bb7 Ebmaj7 Dm7b5",  120),
        ],
    },
]


def write_readme(folder, ex, scale_key):
    suffix, desc = SCALES[scale_key]
    progs_md = "\n".join(
        f"- `{name}.mid` — {symbols}" for name, symbols, _ in ex["progs"])
    md = f"""# {ex['base']}-{suffix}

## Co se cvičí
{ex['goal']}

**Stupnice: {desc}**

## Stavba souborů
- **Levá ruka:** bas (kořen) + akord/takt, držený (sustain, bez kompingu)
- **Pravá ruka:** stupnicový dril — 8 osmin/takt, střídavě vzestupně/sestupně
  s variacemi (tercie), swing feel (~0.11, dlouhá-krátká + akcenty),
  dosedá na guide tone (3./7.) dalšího akordu
- **Stupnice:** `{scale_key}` — {desc}

## Jak bylo vygenerováno
Skript: `improved/build_drill_library.py`
Motor: `scale_drill.make_drill(prog, out, kind='{scale_key}', bpm=…, seed=1)`
Příkaz: `python improved/build_drill_library.py`

(Akordy = ručně zadané progrese — 4-8 taktů různých akordů, ne jen ii-V-I.)

## Soubory (progrese)
{progs_md}
"""
    with open(os.path.join(folder, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(md)


def main():
    n = 0
    for ex in LIBRARY:
        for scale_key, (suffix, _) in SCALES.items():
            folder = os.path.join(ROOT, f"{ex['base']}-{suffix}")
            os.makedirs(folder, exist_ok=True)
            print(f"\n=== {ex['base']}-{suffix} ===")
            for name, symbols, bpm in ex["progs"]:
                try:
                    sd.make_drill(prog_of(symbols), os.path.join(folder, f"{name}.mid"),
                                  kind=scale_key, bpm=bpm, seed=1)
                    print(f"  -> {name}.mid"); n += 1
                except Exception as e:
                    print(f"  !! {name}: {e}"); traceback.print_exc()
            write_readme(folder, ex, scale_key)
            print("  README.md")
    print(f"\nHotovo: {n} drilů v {2*len(SCALES)} složkách -> {ROOT}")


if __name__ == "__main__":
    main()
