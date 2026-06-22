"""energy -- křivka intenzity přes skladbu (stupňuje se / klesá).

Energie na beat = hustota not + dynamika (velocity) + registr (výška) + rytmická
aktivita (krátké tóny = víc). Vyhlazená do oblouků. Dobrý lick má TVAR energie
(buduje/uvolňuje); energetické vrcholy = kde hráč jede ty nejšťavnatější běhy.
"""
import numpy as np


def _norm(x):
    x = np.asarray(x, float)
    rng = x.max() - x.min()
    return (x - x.min()) / (rng or 1.0)


def energy_curve(notes, grid, smooth=4):
    """-> energie na každý beat [0..1]."""
    beats = np.asarray(grid.beats)
    nb = len(beats)
    if nb < 2:
        return np.zeros(nb)
    period = float(np.median(np.diff(beats)))
    edges = np.concatenate([beats, [beats[-1] + period]])
    dens = np.zeros(nb); vel = np.zeros(nb); reg = np.zeros(nb); act = np.zeros(nb); cnt = np.zeros(nb)
    for n in notes:
        i = int(np.clip(np.searchsorted(edges, n.onset, "right") - 1, 0, nb - 1))
        dens[i] += 1
        vel[i] += n.vel
        reg[i] += n.pitch
        act[i] += 1.0 / max(n.dur, 0.1)
        cnt[i] += 1
    velm = np.where(cnt > 0, vel / np.maximum(cnt, 1), 0)
    regm = np.where(cnt > 0, reg / np.maximum(cnt, 1), 0)
    E = 0.35 * _norm(dens) + 0.25 * _norm(velm) + 0.20 * _norm(regm) + 0.20 * _norm(act)
    if smooth > 1:
        E = np.convolve(E, np.ones(smooth) / smooth, "same")
    return _norm(E)


def shape(E, start, end):
    """Energie úseku [start,end): (úroveň 0..1, směr 'build'/'release'/'arch'/'flat', sklon)."""
    seg = E[start:end]
    if len(seg) < 2:
        return float(seg.mean()) if len(seg) else 0.0, "flat", 0.0
    x = np.arange(len(seg))
    slope = float(np.polyfit(x, seg, 1)[0]) * len(seg)        # celkový vzestup/pokles
    peak = int(seg.argmax())
    if 0.25 < peak / len(seg) < 0.75 and seg[peak] - seg[[0, -1]].max() > 0.15:
        d = "arch"
    elif slope > 0.12:
        d = "build"
    elif slope < -0.12:
        d = "release"
    else:
        d = "flat"
    return float(seg.mean()), d, slope


_BLK = "▁▂▃▄▅▆▇█"


def sparkline(E, cols=64):
    """E -> řádek blokových znaků (vidět, jak energie stoupá/klesá přes skladbu)."""
    if len(E) == 0:
        return ""
    idx = (np.linspace(0, len(E) - 1, cols)).astype(int)
    s = _norm(E[idx])
    return "".join(_BLK[min(7, int(v * 7.999))] for v in s)


if __name__ == "__main__":
    import sys
    from . import io_midi, beats as B
    notes = io_midi.load_notes(sys.argv[1])
    grid = B.track(notes)
    E = energy_curve(notes, grid)
    print(f"energie přes skladbu ({len(E)} beatů):")
    print(" ", sparkline(E))
