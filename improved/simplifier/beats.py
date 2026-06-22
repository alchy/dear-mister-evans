"""beats -- rubato-aware beat-tracking z MIDI onsetů (symbolicky, jen numpy).

Žádné audio. Z úderů (io_midi.onset_events) postavíme onset-envelope, odhadneme
tempo (autokorelace v BPM okně s mírnou preferencí kolem ~110) a beaty najdeme
dynamickým programováním ve stylu Ellis 2007: skóre = síla onsetu na beatu
MÍNUS penalta za odchylku od lokálního tempa (log-čtverec). Penalta umožní
PLYNULÉ tempo (rubato), ale brání chaotickým skokům.

API:
    track(notes) -> BeatGrid(beats, downbeats, bpm, sr, env)
"""
from collections import namedtuple
import numpy as np
from . import io_midi

BeatGrid = namedtuple("BeatGrid", "beats downbeats bpm sr env")

SR = 100                 # vzorkování envelope [Hz]
BPM_LO, BPM_HI = 50, 220
PREF_BPM = 110.0         # mírná preference tempa (jako librosa); široká
PREF_WIDTH = 1.1         # v oktávách (log2)
TIGHTNESS = 80.0         # jak tvrdě DP drží tempo (víc = rovnější, míň = volnější rubato)


def onset_envelope(events, dur, sr=SR):
    """Úhozy -> spojitá síla v čase. Síla úderu = součet velocit (× lehký bonus za polyfonii)."""
    n = int(np.ceil(dur * sr)) + 1
    env = np.zeros(n)
    for t, vsum, poly in events:
        i = int(round(t * sr))
        if 0 <= i < n:
            env[i] += vsum * (1.0 + 0.15 * (poly - 1))   # akord/bas = silnější beat-vodítko
    if env.max() > 0:
        env /= env.max()
    return env


def estimate_bpm(env, sr=SR):
    """Tempo z autokorelace envelope, jen v BPM okně, s log-normální preferencí."""
    lag_lo = int(round(60 * sr / BPM_HI))
    lag_hi = int(round(60 * sr / BPM_LO))
    # lehké vyhlazení pro stabilnější autokorelaci
    k = np.hanning(5); k /= k.sum()
    e = np.convolve(env, k, "same")
    lags = np.arange(lag_lo, lag_hi + 1)
    ac = np.array([np.dot(e[:-L], e[L:]) for L in lags])
    bpms = 60 * sr / lags
    pref = np.exp(-0.5 * (np.log2(bpms / PREF_BPM) / PREF_WIDTH) ** 2)
    score = ac * pref
    return float(bpms[int(score.argmax())])


def track_beats(env, bpm, sr=SR, tightness=TIGHTNESS):
    """DP beat-tracking (Ellis): vrať indexy framů, kde leží beaty."""
    period = 60.0 * sr / bpm
    n = len(env)
    C = env.copy()                     # kumulativní skóre
    back = -np.ones(n, dtype=int)
    lo, hi = int(round(period * 0.5)), int(round(period * 2.0))
    for i in range(n):
        m0, m1 = max(0, i - hi), i - lo
        if m1 < m0:
            continue
        cand = np.arange(m0, m1 + 1)
        txcost = -tightness * (np.log((i - cand) / period)) ** 2
        val = C[cand] + txcost
        j = int(val.argmax())
        if val[j] + env[i] >= C[i]:
            C[i] = val[j] + env[i]
            back[i] = cand[j]
    # konec: nejlepší skóre v posledním období, pak zpětný průchod
    tail = C[max(0, n - int(round(period))):]
    end = (n - len(tail)) + int(tail.argmax())
    beats = []
    i = end
    while i >= 0:
        beats.append(i)
        i = back[i]
    beats.reverse()
    return np.array(beats)


def find_downbeats(beat_frames, env, meter=4):
    """Vyber fázi (0..meter-1), kde mají 'první doby' nejvíc onset-síly (silná doba/bas)."""
    if len(beat_frames) == 0:
        return np.array([], dtype=int)
    strengths = env[beat_frames]
    best_phase, best = 0, -1.0
    for ph in range(meter):
        s = strengths[ph::meter].sum()
        if s > best:
            best, best_phase = s, ph
    return beat_frames[best_phase::meter]


def track(notes, sr=SR):
    """Hlavní vstup: notes -> BeatGrid."""
    dur = max((n.onset + n.dur for n in notes), default=0.0)
    events = io_midi.onset_events(notes)
    env = onset_envelope(events, dur, sr)
    bpm = estimate_bpm(env, sr)
    bf = track_beats(env, bpm, sr)
    db = find_downbeats(bf, env)
    # lokální BPM z mediánu IOI mezi beaty (informativní)
    if len(bf) > 1:
        ioi = np.diff(bf) / sr
        bpm = float(60.0 / np.median(ioi))
    return BeatGrid(beats=bf / sr, downbeats=db / sr, bpm=bpm, sr=sr, env=env)


if __name__ == "__main__":
    # Syntetický test: známé tempo 100 BPM, beaty + offbeaty -> tracker má najít ~100.
    import sys
    if len(sys.argv) > 1:
        g = track(io_midi.load_notes(sys.argv[1]))
        print(f"beatů={len(g.beats)} downbeatů={len(g.downbeats)} bpm={g.bpm:.1f}")
        print("první beaty [s]:", np.round(g.beats[:8], 3))
    else:
        from .io_midi import Note
        bpm = 100.0; per = 60.0 / bpm
        notes = []
        for b in range(64):
            t = b * per
            notes.append(Note(t, 0.2, 60, 90))                 # beat
            if b % 2 == 0:
                notes.append(Note(t + per / 2, 0.1, 67, 60))   # offbeat slabší
        g = track(notes)
        ioi = np.diff(g.beats)
        print(f"detekováno bpm={g.bpm:.1f} (čekáno ~100), beatů={len(g.beats)}, "
              f"std IOI={np.std(ioi)*1000:.1f}ms")
        assert 96 <= g.bpm <= 104, "tempo mimo toleranci"
        print("OK syntetický test")
