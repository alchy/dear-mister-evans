#!/usr/bin/env python3
"""
standards.py -- KURÁTORSKÝ KORPUS jazzových standardů (čisté changes).

Ručně zadané akordové progrese (changes) známých standardů + uživatelova
repertoáru. Čistá data BEZ šumu z detekce -> férová munice pro Markov i neuronku.
Akordové progrese nejsou autorsky chráněné. Vzorek ověřen přes web.

Formát: (key, mode, [chord_symbols...]) ~ jeden akord na takt (občas dva).
Kvality: maj7, m7, 7, m7b5, dim7, m6, 6, mMaj7, sus (map_quality si poradí i s 9/13).
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from arrange_chords import parse_symbol   # symbol -> (root_pc, quality_token)
from evans_drill import PC

# (jméno, key, mode, changes)
STANDARDS = [
    # ---- major ii-V-I / cyklus kvint ----
    ("Take the A Train", "C", "maj",
     ["Cmaj7","Cmaj7","D7","D7","Dm7","G7","Cmaj7","Cmaj7"]),
    ("Tune Up", "D", "maj",
     ["Em7","A7","Dmaj7","Dmaj7","Dm7","G7","Cmaj7","Cmaj7",
      "Cm7","F7","Bbmaj7","Bbmaj7","Em7","A7","Dmaj7","Dmaj7"]),
    ("Satin Doll", "C", "maj",
     ["Dm7","G7","Dm7","G7","Em7","A7","Em7","A7","Am7","D7","Abm7","Db7",
      "Cmaj7","Dm7 G7","Cmaj7","Cmaj7"]),
    ("Fly Me to the Moon", "C", "maj",
     ["Am7","Dm7","G7","Cmaj7","Fmaj7","Bm7b5","E7","Am7","A7",
      "Dm7","G7","Em7","Am7","Dm7","G7","Cmaj7"]),
    ("All of Me", "C", "maj",
     ["Cmaj7","Cmaj7","E7","E7","A7","A7","Dm7","Dm7","E7","E7","Am7","Am7",
      "D7","D7","Dm7","G7"]),
    ("There Will Never Be Another You", "Eb", "maj",
     ["Ebmaj7","Ebmaj7","Dm7b5","G7","Cm7","Cm7","Bbm7","Eb7","Abmaj7","Abmaj7",
      "Dm7b5","G7","Ebmaj7","C7","Fm7","Bb7","Ebmaj7","Ebmaj7"]),
    ("Days of Wine and Roses", "F", "maj",
     ["Fmaj7","Fmaj7","Eb7","Eb7","Am7","D7","Gm7","Gm7","Bbm7","Eb7",
      "Am7","D7","Gm7","C7","Fmaj7","Gm7 C7"]),
    ("All The Things You Are", "Ab", "maj",
     ["Fm7","Bbm7","Eb7","Abmaj7","Dbmaj7","G7","Cmaj7","Cmaj7",
      "Cm7","Fm7","Bb7","Ebmaj7","Abmaj7","D7","Gmaj7","Gmaj7",
      "Am7","D7","Gmaj7","Gmaj7","F#m7b5","B7","Emaj7","C7",
      "Fm7","Bbm7","Eb7","Abmaj7","Dbmaj7","Gb7","Cm7","Bdim7",
      "Bbm7","Eb7","Abmaj7","Abmaj7"]),
    ("Have You Met Miss Jones", "F", "maj",
     ["Fmaj7","D7","Gm7","C7","Am7","Dm7","Gm7","C7",
      "Bbmaj7","Ab7","Dbmaj7","E7","Amaj7","C7","Fmaj7","Gm7 C7"]),
    ("Autumn in New York", "C", "maj",
     ["Cmaj7","Am7","Dm7","G7","Em7","Eb7","Dm7","G7","Cmaj7","Bm7b5","E7","Am7"]),

    # ---- harmonicky bohaté / balady ----
    ("Stella By Starlight", "Bb", "maj",
     ["Em7b5","A7","Cm7","F7","Fm7","Bb7","Ebmaj7","Ab7",
      "Bbmaj7","Bbmaj7","Em7b5","A7","Dm7","Dm7","Bbm7","Eb7",
      "Fmaj7","Fmaj7","Em7b5","A7","Am7b5","D7","Gm7","Gm7",
      "Cm7","F7","Bbmaj7","Bbmaj7"]),
    ("Misty", "Eb", "maj",
     ["Ebmaj7","Bbm7 Eb7","Abmaj7","Abm7 Db7","Ebmaj7","Cm7","Fm7","Bb7",
      "Gm7","C7","Fm7","Bb7","Ebmaj7","Cm7","Fm7 Bb7","Ebmaj7"]),
    ("Body and Soul", "Db", "maj",
     ["Ebm7","Bb7","Ebm7","Ab7","Dbmaj7","Dbmaj7","Gbmaj7","Fm7 Bb7",
      "Ebm7","Ab7","Dbmaj7","Dbmaj7"]),
    ("In a Sentimental Mood", "F", "maj",
     ["Fmaj7","Fm7","Gm7","Gbdim7","Fmaj7","D7","Gm7","C7",
      "Fmaj7","Fm7","Em7","A7","Dm7","Db7","Cm7","B7"]),
    ("My One and Only Love", "G", "maj",
     ["Gmaj7","Bm7b5 E7","Am7","D7","Gmaj7","Em7","Am7","D7",
      "Gmaj7","Bm7","Em7","Am7 D7","Gmaj7","Em7","Am7 D7","Gmaj7"]),
    ("Georgia On My Mind", "F", "maj",
     ["Fmaj7","A7","Bbmaj7","Bdim7","Fmaj7","Dm7","Gm7","C7",
      "Fmaj7","A7","Dm7","F7","Bb6","Bbm6","Fmaj7","Gm7 C7"]),

    # ---- minor ----
    ("Autumn Leaves", "G", "min",
     ["Cm7","F7","Bbmaj7","Ebmaj7","Am7b5","D7","Gm6","Gm6",
      "Cm7","F7","Bbmaj7","Ebmaj7","Am7b5","D7","Gm6","Gm6",
      "Am7b5","D7","Gm6","Gm6","Cm7","F7","Bbmaj7","Ebmaj7",
      "Am7b5","D7","Gm6","Gm6"]),
    ("Blue Bossa", "C", "min",
     ["Cm7","Cm7","Fm7","Fm7","Dm7b5","G7","Cm7","Cm7",
      "Ebm7","Ab7","Dbmaj7","Dbmaj7","Dm7b5","G7","Cm7","Cm7"]),
    ("Softly as in a Morning Sunrise", "C", "min",
     ["Cm7","Cm7","Fm7","Fm7","Dm7b5","G7","Cm7","Cm7",
      "Fm7","Fm7","Cm7","Cm7","Dm7b5","G7","Cm7","G7"]),
    ("Nardis", "E", "min",
     ["Em7","Fmaj7","Em7","Fmaj7","Am7","Fmaj7","Em7","Em7",
      "Am7","Fmaj7","Dm7","G7","Cmaj7","Fmaj7","Em7","Em7"]),
    ("Summertime", "A", "min",
     ["Am6","Am6","Em7b5","B7","Am6","Am6","Dm7","Dm7",
      "Am6","F7","E7","E7","Am6","Dm7 E7","Am6","Am6"]),
    ("Black Orpheus", "A", "min",
     ["Am7","Bm7b5","E7","Am7","Dm7","G7","Cmaj7","Fmaj7",
      "Bm7b5","E7","Am7","A7","Dm7","G7","Cmaj7","Bm7b5 E7"]),
    ("My Funny Valentine", "C", "min",
     ["Cm7","Cm7","CmMaj7","Cm7","Cm6","Cm6","Abmaj7","Fm7",
      "Dm7b5","G7","Cm7","Cm7","Fm7","Bb7","Ebmaj7","Dm7b5 G7"]),

    # ---- blues ----
    ("Bb Jazz Blues", "Bb", "maj",
     ["Bb7","Eb7","Bb7","Bb7","Eb7","Edim7","Bb7","G7","Cm7","F7","Bb7 G7","Cm7 F7"]),
    ("Blues for Alice", "F", "maj",
     ["Fmaj7","Em7b5 A7","Dm7 G7","Cm7 F7","Bbmaj7","Bbm7 Eb7","Am7 D7","Abm7 Db7",
      "Gm7","C7","Fmaj7 D7","Gm7 C7"]),
    ("Mr PC (minor blues)", "C", "min",
     ["Cm7","Cm7","Cm7","Cm7","Fm7","Fm7","Cm7","Cm7","Ab7","G7","Cm7","G7"]),

    # ---- rhythm changes ----
    ("Rhythm Changes", "Bb", "maj",
     ["Bbmaj7","G7","Cm7","F7","Dm7","G7","Cm7","F7",
      "Bbmaj7","Bb7","Eb7","Edim7","Bbmaj7 G7","Cm7 F7","Bbmaj7","Bbmaj7",
      "D7","D7","G7","G7","C7","C7","F7","F7"]),

    # ---- modal ----
    ("So What", "D", "min",
     ["Dm7","Dm7","Dm7","Dm7","Dm7","Dm7","Dm7","Dm7",
      "Ebm7","Ebm7","Ebm7","Ebm7","Dm7","Dm7","Dm7","Dm7"]),
    ("Impressions", "D", "min",
     ["Dm7","Dm7","Dm7","Dm7","Ebm7","Ebm7","Dm7","Dm7"]),
    ("Cantaloupe Island", "F", "min",
     ["Fm7","Fm7","Fm7","Fm7","Db7","Db7","Dbmaj7","Dbmaj7",
      "Dm7","Dm7","Dm7","Dm7","Fm7","Fm7","Fm7","Fm7"]),

    # ---- bossa ----
    ("Wave", "D", "maj",
     ["Dmaj7","Bb7","Am7","D7","Gmaj7","Gm7","F#m7","B7","Em7","A7","Dmaj7","Am7 D7"]),
    ("Girl from Ipanema", "F", "maj",
     ["Fmaj7","Fmaj7","G7","G7","Gm7","Gm7","F#m7 B7","Fmaj7 B7",
      "F#maj7","F#maj7","B7","B7","F#m7","D7","Gm7","Eb7"]),
]


def to_corpus(modes=("maj", "min")):
    """Vrátí [(mode, [(rel, quality), ...]), ...] -- key-relativní tokeny."""
    out = []
    for name, key, mode, changes in STANDARDS:
        if mode not in modes:
            continue
        key_root = PC.index(key) if key in PC else 0
        toks = []
        for bar in changes:
            for sym in bar.split():            # takt může mít víc akordů
                r, q = parse_symbol(sym)
                t = ((r - key_root) % 12, q)
                if not toks or toks[-1] != t:
                    toks.append(t)
        if len(toks) >= 4:
            out.append((mode, toks))
    return out


if __name__ == "__main__":
    c = to_corpus()
    print(f"standardů: {len(STANDARDS)} | sekvencí: {len(c)} | "
          f"akordů: {sum(len(t) for _, t in c)}")
    from collections import Counter
    big = Counter()
    for _, toks in c:
        for i in range(1, len(toks)):
            big[(toks[i-1], toks[i])] += 1
    print("celkem přechodů:", sum(big.values()), "| unikátních:", len(big))
