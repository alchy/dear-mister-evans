"""meter -- dynamické downbeaty („1") z harmonického rytmu.

Stará globální fáze byla špatně na startu (intro má jiný feel). Tady „1" odvodíme
z DŮKAZŮ: kde se MĚNÍ akord + silný bas + silný úhoz. Barlíny klademe ~co `meter`
beatů (4/4) přes dynamické programování — penalta za odchylku od rozteče drží
metrum, ale dovolí PŘEFÁZOVÁNÍ na hranici dílu (proto „dynamicky v průběhu").

API:
    downbeats(notes, grid, spans, meter=4) -> np.array časů [s]
"""
import numpy as np
from . import io_midi

W_CHANGE = 1.6      # váha: změna akordu = silný signál pro "1"
W_ONSET = 1.0       # váha: síla úhozu na beatu
W_BASS = 1.2        # váha: nízký tón (bas) blízko beatu
SPACING_PEN = 0.5   # penalta (i-j-meter)^2 za odchylku od metra


def _bass_strength(notes, beats, period, lo=54):
    """Na každý beat: síla nízkých tónů (bas) začínajících blízko beatu."""
    nb = len(beats)
    bs = np.zeros(nb)
    half = period / 2
    low = [(n.onset, n.vel) for n in notes if n.pitch <= lo]
    for i, b in enumerate(beats):
        for t, v in low:
            if abs(t - b) <= half:
                bs[i] += v / 127.0
    return bs / (bs.max() or 1.0)


def beat_score(notes, grid, spans, meter=4):
    """Síla důkazu, že daný beat je 'jednička': změna akordu + úhoz + bas."""
    beats = grid.beats
    nb = len(beats)
    period = float(np.median(np.diff(beats)))
    change = np.zeros(nb)
    for s in spans:
        if s.start > 0:
            change[s.start] = 1.0
    sr = grid.sr
    onset = np.array([grid.env[min(int(round(b * sr)), len(grid.env) - 1)] for b in beats])
    bass = _bass_strength(notes, beats, period)
    return W_CHANGE * change + W_ONSET * onset + W_BASS * bass


def downbeats(notes, grid, spans, meter=4, mode="phase"):
    """mode='phase': jedna globální fáze podle nejsilnějšího důkazu (ukotvená,
    drží i přes slabé intro). mode='dp': posuvné DP (umí přefázovat, ale slabé
    intro mu ujede)."""
    beats = grid.beats
    nb = len(beats)
    if nb < meter:
        return beats[:1]
    score = beat_score(notes, grid, spans, meter)
    if mode == "phase":
        # vyber fázi 0..meter-1, kde mají 'jedničky' (každá meter-tá doba) nejvíc důkazu
        best_p = max(range(meter), key=lambda p: score[p::meter].sum())
        return beats[best_p::meter]

    # --- DP varianta (ponecháno pro srovnání) ---
    dp = np.full(nb, -1e9)
    back = -np.ones(nb, dtype=int)
    for i in range(min(meter + 1, nb)):        # první "1" smí být kdekoli v 1. taktu
        dp[i] = score[i]
    for i in range(nb):
        if dp[i] <= -1e8:
            continue
        for step in (meter - 1, meter, meter + 1):   # dovol 3/4/5 -> přefázování
            j = i + step
            if j >= nb:
                continue
            cand = dp[i] + score[j] - SPACING_PEN * (step - meter) ** 2
            if cand > dp[j]:
                dp[j] = cand
                back[j] = i
    # 3) zpětný průchod z nejlepšího konce (v posledním taktu)
    end = int(np.argmax(np.where(np.arange(nb) >= nb - meter, dp, -1e9)))
    db = []
    i = end
    while i >= 0:
        db.append(i)
        i = back[i]
    db.reverse()
    return beats[np.array(db, dtype=int)]


if __name__ == "__main__":
    import sys
    from . import beats as B, chords as C
    notes = io_midi.load_notes(sys.argv[1])
    grid = B.track(notes)
    spans, keys = C.label_beats(notes, grid)
    db = downbeats(notes, grid, spans)
    print(f"beatů={len(grid.beats)} downbeatů={len(db)} (každý ~{len(grid.beats)/max(len(db),1):.1f} beatů)")
    print("první downbeaty [s]:", np.round(db[:8], 2))
