"""melody -- čistý lead line z vrchního hlasu (skyline) v BEAT jednotkách.

Vrch = melodie (z voices.skyline_split). Časy přepočítány na float index beatu
(0-based, jako grid.beats), aby linka šla rovnou do voice/ (formát [(o,d,pitch)]
v dobách). Čištění: sloučení opakovaných tónů, vyhození grace, lehká kvantizace.
"""
import numpy as np
from . import voices


def _to_beat_fn(beats, period):
    bt = np.asarray(beats)

    def to_beat(t):
        i = int(np.searchsorted(bt, t, "right")) - 1
        if i < 0:
            return (t - bt[0]) / period           # extrapolace před první beat
        if i >= len(bt) - 1:
            return (len(bt) - 1) + (t - bt[-1]) / period
        return i + (t - bt[i]) / (bt[i + 1] - bt[i])
    return to_beat


def melody_line(notes, grid, min_dur=0.12, quant=0.25, merge_gap=0.15):
    """-> [(beat_pos, dur_beats, pitch)] v ABSOLUTNÍCH dobách (index beatu)."""
    mel, _harmony = voices.skyline_split(notes)
    if not mel:
        return []
    period = float(np.median(np.diff(grid.beats))) if len(grid.beats) > 1 else 0.5
    to_beat = _to_beat_fn(grid.beats, period)
    raw = []
    for n in sorted(mel, key=lambda x: x.onset):
        ob = to_beat(n.onset)
        db = to_beat(n.onset + n.dur) - ob
        raw.append([ob, max(db, 0.05), n.pitch])
    # sloučit hned navazující stejnou výšku
    merged = [raw[0]]
    for ob, db, p in raw[1:]:
        last = merged[-1]
        if p == last[2] and ob - (last[0] + last[1]) <= merge_gap:
            last[1] = ob + db - last[0]
        else:
            merged.append([ob, db, p])
    # vyhodit grace (moc krátké), lehce kvantovat onset i délku na mřížku
    out = []
    for ob, db, p in merged:
        if db < min_dur:
            continue
        ob_q = round(ob / quant) * quant
        db_q = max(quant, round(db / quant) * quant)
        out.append((ob_q, db_q, p))
    # MONOFONIE: kvantizace může složit dva tóny na týž onset -> nech jen vrchní
    # (lead line je nejvyšší hlas). Jinak legato v simplify vyrobí notu nulové délky.
    mono = []
    for ob, db, p in out:
        if mono and abs(mono[-1][0] - ob) < 1e-9:
            if p > mono[-1][2]:
                mono[-1] = (ob, db, p)
        else:
            mono.append((ob, db, p))
    out = mono
    # vyhodit OKTÁVOVÉ GLITCHE: izolovaný tón daleko od OBOU sousedů (skyline chytil bas)
    clean = []
    for i, (ob, db, p) in enumerate(out):
        nb = [out[j][2] for j in (i - 1, i + 1) if 0 <= j < len(out)]
        if nb and all(abs(p - q) > 11 for q in nb):
            continue                                   # spike o víc než oktávu od všech sousedů
        clean.append((ob, db, p))
    return clean


if __name__ == "__main__":
    import sys
    from . import io_midi, beats as B
    notes = io_midi.load_notes(sys.argv[1])
    grid = B.track(notes)
    line = melody_line(notes, grid)
    print(f"melodických tónů: {len(line)}")
    print("prvních 10 (beat, délka, pitch):", [(round(o, 2), round(d, 2), p) for o, d, p in line[:10]])
