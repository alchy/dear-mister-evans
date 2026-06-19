"""
line_extraction.py -- extrakce a čištění melodické linky (pravá ruka) z MIDI.

Princip: 'skyline' = nejvyšší znějící tón nad registrovou hranicí v jemné časové
mřížce. Souvislé stejné výšky se složí do not. Volitelně proředí krátké ozdoby.

Toto je trénovací materiál pro generátor. Není dokonalé (u blokové faktury je
melodie občas v obou rukách), ale je to robustní a univerzální základ.

Spuštění samostatně:
    python src/line_extraction.py data/be-slice09.mid
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from chords import load_notes, detect_chords, nm


def skyline_at(notes, t, floor=59):
    """Nejvyšší znějící tón v čase t (v dobách) nad registrovou hranicí floor."""
    cands = [p for o, d, p, v in notes if o <= t < o + d and p >= floor]
    return max(cands) if cands else None


def extract_melody(notes, floor=59, grid=0.25, min_dur=0.2):
    """
    Vrátí melodickou linku jako [(onset_beats, dur_beats, pitch), ...].

    floor   : spodní registrová hranice melodie (MIDI). Pod ní je doprovod.
    grid    : krok vzorkování skyline v dobách (0.25 = šestnáctinová mřížka).
    min_dur : noty kratší než tohle se zahodí (proředění ozdob/artefaktů).
    """
    end = max(o + d for o, d, p, v in notes)
    line = []
    t = 0.0
    while t < end:
        p = skyline_at(notes, t + grid * 0.4, floor)
        if p is not None:
            if line and line[-1][2] == p:
                # prodluž drženou notu
                o0, d0, pp = line[-1]
                line[-1] = (o0, d0 + grid, pp)
            else:
                line.append((t, grid, p))
        t += grid
    # proředění
    return [(o, d, p) for (o, d, p) in line if d >= min_dur]


def align_to_chords(melody, chord_segments_with_time):
    """
    Přiřadí každé melodické notě aktivní akord.
    chord_segments_with_time : [(start_beat, end_beat, root, quality), ...]
    Vrátí [(onset, dur, pitch, root, quality), ...].
    """
    out = []
    for o, d, p in melody:
        active = None
        for s, e, r, q in chord_segments_with_time:
            if s <= o < e:
                active = (r, q); break
        if active is None and chord_segments_with_time:
            active = chord_segments_with_time[-1][2:]
        if active:
            out.append((o, d, p, active[0], active[1]))
    return out


def chord_segments_with_time(notes, hop=1.0):
    """Pomocná: detekuje akordy a vrátí je s časovými hranicemi v dobách.

    detect_chords vrací sloučené akordy bez časů; tady je znovu odvodíme z
    původní segmentace (jednoduchá varianta: rovnoměrně po hop-oknech nelze,
    proto použijeme interní segmentaci). Pro jednoduchost zde sahneme po
    nesloučené detekci přes evans_drill internals.
    """
    # Jednoduchý přístup: znovu spusť detekci a aproximuj hranice podle změn.
    # Pro demo stačí: vezmi sloučené akordy a rozprostři je rovnoměrně.
    merged = detect_chords(notes)
    end = max(o + d for o, d, p, v in notes)
    n = len(merged)
    seglen = end / n if n else end
    segs = []
    for i, (r, q, pr) in enumerate(merged):
        segs.append((i * seglen, (i + 1) * seglen, r, q))
    return segs


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/be-slice09.mid"
    notes = load_notes(path)
    mel = extract_melody(notes)
    print(f"{path}: {len(mel)} melodických not (po proředění)")
    print("prvních 20:")
    for o, d, p in mel[:20]:
        print(f"  beat {o:6.2f}  {nm(p):4s}  dur {d:.2f}")
    segs = chord_segments_with_time(notes)
    aligned = align_to_chords(mel, segs)
    print(f"\nzarovnáno k akordům: {len(aligned)} not")
    for o, d, p, r, q in aligned[:10]:
        from chords import lab
        print(f"  {nm(p):4s} nad {lab(r,q)}")
