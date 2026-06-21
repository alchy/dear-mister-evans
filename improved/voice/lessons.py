"""lessons -- kurikulum výukového programu (virtuální Levine).

Každá lekce = VÝKLAD (vlastními slovy, ne citace) + PRESET generování (izolace
konceptu) + FOCUS (co v náhledu zdůraznit) + volitelné A/B (slyš rozdíl).
Pořadí dle PEDAGOGY.md / LEVINE_DESIGN.md.

Preset klíče (vše volitelné): density, approach, voicing (kind), color,
root, mode, pattern.
"""

LESSONS = [
    {
        "key": "guide_tones",
        "title": "1 · Guide tóny (3 a 7)",
        "explain": ("3. a 7. stupeň DEFINUJÍ kvalitu akordu (dur/moll/dominanta) — jsou to "
                    "guide tóny. Veď je plynule krokem přes akordy a DOSEDEJ na ně; melodie "
                    "pak obkresluje harmonii i bez plného akordu. Cvičení: čtvrtky, bez "
                    "chromatiky, landing na 3/7. Sleduj zelené kroužky a ▼."),
        "preset": {"density": 1, "approach": 0.0, "voicing": "rootless",
                   "root": "C", "mode": "dur", "pattern": "ii–V–I"},
        "focus": "guides",
        "ab": None,
    },
    {
        "key": "chord_tones_beat",
        "title": "2 · Akord-tóny na těžké",
        "explain": ("Když akordové tóny padnou na SILNÉ doby (1 a 3), linka zní jako changes. "
                    "Mezi nimi spojuj stupnicí. Cvičení: osminy, akordové tóny na dobách."),
        "preset": {"density": 2, "approach": 0.0, "voicing": "rootless"},
        "focus": "scale",
        "ab": None,
    },
    {
        "key": "approach",
        "title": "3 · Approach tóny (chromatika)",
        "explain": ("Půltónový PŘÍCHOD ze sousedního tónu na cíl dodá bebopový spád. "
                    "A/B: slyš linku BEZ approach (A) a S approach (B)."),
        "preset": {"density": 2, "approach": 0.8, "voicing": "rootless"},
        "focus": "approach",
        "ab": {"A": {"approach": 0.0}, "B": {"approach": 0.85}},
    },
    {
        "key": "voice_leading",
        "title": "4 · Vedení levé ruky",
        "explain": ("Mezi akordy přesouvej levou ruku CO NEJMÍŇ — guide tóny se vedou "
                    "půltónem, společné tóny drž. Sleduj modré čáry mezi bublinami. "
                    "A/B: základní tvar (skoky) vs rootless (plynulé vedení)."),
        "preset": {"density": 2, "approach": 0.5, "voicing": "rootless"},
        "focus": "voicing",
        "ab": {"A": {"voicing": "root"}, "B": {"voicing": "rootless"}},
    },
    {
        "key": "landing",
        "title": "5 · Landing do dalšího akordu",
        "explain": ("Konec taktu miř na 3 nebo 7 DALŠÍHO akordu (▼). Tím se přechody spojí "
                    "a linka teče přes celou progresi (anticipace na konci taktu)."),
        "preset": {"density": 2, "approach": 0.6, "voicing": "rootless"},
        "focus": "landing",
        "ab": None,
    },
    {
        "key": "minor_ii_v_i",
        "title": "6 · Mollové ii–V–i (altered)",
        "explain": ("V moll je ii půlzmenšený (iiø, lokrická ♮2) a V míří do i. Inside = "
                    "frygická dominanta (klidnější), outside = altered (♭9 ♯9 ♭13, napětí). "
                    "A/B: inside vs outside dominanta."),
        "preset": {"density": 2, "approach": 0.6, "voicing": "rootless",
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
