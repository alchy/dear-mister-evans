"""lessons -- kurikulum výukového programu (virtuální Levine).

Každá lekce = VÝKLAD (vlastními slovy, ne citace) + PRESET generování (izolace
konceptu) + FOCUS (kterou vrstvu náhledu zvýraznit, zbytek ztlumit) + volitelné A/B
(slyš rozdíl). Pořadí dle PEDAGOGY.md / LEVINE_DESIGN.md.

Preset klíče (vše volitelné): density, approach, voicing (kind), color,
root, mode, pattern.
FOCUS hodnoty (řídí zvýraznění v náhledu): guides | scale | landing | approach | voicing.
"""

LESSONS = [
    # --- Blok A: cíle (páteř linky na changes) ---
    {
        "key": "guide_tones",
        "title": "1 · Guide tóny (3 a 7)",
        "explain": ("3. a 7. stupeň DEFINUJÍ kvalitu akordu (dur/moll/dominanta) — to jsou "
                    "guide tóny (zelené kroužky). Drž je v uchu: kolem nich se staví celá linka."),
        "preset": {"density": 1, "approach": 0.0, "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "guides",
        "ab": None,
    },
    {
        "key": "chord_tones_beat",
        "title": "2 · Akord-tóny na těžké",
        "explain": ("Když na SILNÉ doby (1 a 3) padnou akordové tóny, linka zní jako changes. "
                    "Mezi nimi spojuj stupnicí. Sleduj, že kolečka na dobách sedí na guide/akord tónech."),
        "preset": {"density": 2, "approach": 0.0, "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "guides",
        "ab": None,
    },
    {
        "key": "landing",
        "title": "3 · Landing do dalšího akordu",
        "explain": ("Konec taktu směřuje na 3/7 DALŠÍHO akordu a dosedne na jeho 1. době — ▼ a "
                    "popisek ukazují cíl (tón a jestli je to 3 nebo 7). Tím se přechody spojí."),
        "preset": {"density": 2, "approach": 0.5, "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "landing",
        "ab": None,
    },
    # --- Blok B: stupnice (materiál mezi cíli) ---
    {
        "key": "chord_scales",
        "title": "4 · Chord-scales dle funkce",
        "explain": ("Každá kvalita má svou stupnici: maj7 lydická, m7 dórská, dominanta "
                    "mixolydická/bebopová. Zelená paleta = tóny stupnice daného akordu."),
        "preset": {"density": 2, "approach": 0.2, "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "scale",
        "ab": None,
    },
    {
        "key": "inside_outside",
        "title": "5 · Inside vs outside dominanty",
        "explain": ("Dominanta unese víc napětí: inside = bebop-dominantní (klidnější), "
                    "outside = lydicko-dominantní/altered (#11, alterace). A/B: slyš obojí na V7."),
        "preset": {"density": 2, "approach": 0.4, "color": "inside", "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "scale",
        "ab": {"A": {"color": "inside"}, "B": {"color": "outside"}},
    },
    # --- Blok C: chromatika ---
    {
        "key": "approach",
        "title": "6 · Approach tóny (chromatika)",
        "explain": ("Půltónový PŘÍCHOD ze sousedního tónu na cíl dodá bebopový spád — fialová "
                    "kolečka jsou chromatika (jen na slabých dobách). A/B: bez (A) a s approach (B)."),
        "preset": {"density": 2, "approach": 0.85, "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "approach",
        "ab": {"A": {"approach": 0.0}, "B": {"approach": 0.85}},
    },
    # --- Blok D: levá ruka ---
    {
        "key": "voice_leading",
        "title": "7 · Vedení levé ruky",
        "explain": ("Mezi akordy přesouvej levou ruku CO NEJMÍŇ — guide tóny vedeš půltónem, "
                    "společné tóny držíš. Modré čáry = pohyb hlasů. A/B: základní tvar vs rootless."),
        "preset": {"density": 2, "approach": 0.4, "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "voicing",
        "ab": {"A": {"voicing": "root"}, "B": {"voicing": "rootless"}},
    },
    {
        "key": "voicing_textures",
        "title": "8 · Voicing textury (LH)",
        "explain": ("Stejné tóny, jiná hustota a barva: rootless (Evans), drop2 (otevřený), "
                    "cluster (těsný). A/B: rootless vs stupnicový cluster — slyš rozdíl textury."),
        "preset": {"density": 2, "approach": 0.4, "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "voicing",
        "ab": {"A": {"voicing": "rootless"}, "B": {"voicing": "cluster3"}},
    },
    # --- Blok E: moll ---
    {
        "key": "minor_ii_v_i",
        "title": "9 · Mollové ii–V–i",
        "explain": ("V moll je ii půlzmenšený (iiø, lokrická ♮2) a V míří do i. Inside = frygická "
                    "dominanta (klidnější), outside = altered (♭9 ♯9 ♭13, napětí). A/B: inside vs outside."),
        "preset": {"density": 2, "approach": 0.6, "color": "inside", "voicing": "rootless",
                   "root": "A", "mode": "moll", "pattern": "iiø–V–i"},
        "focus": "scale",
        "ab": {"A": {"color": "inside"}, "B": {"color": "outside"}},
    },
]


def titles():
    return [l["title"] for l in LESSONS]


def by_title(t):
    for l in LESSONS:
        if l["title"] == t:
            return l
    return LESSONS[0]
