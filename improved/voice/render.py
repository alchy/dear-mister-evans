"""render -- (harmonie + melodická linka) -> MIDI, se SWINGEM a FEELEM.

LH = bas + voicing/takt (sustain). RH = linka s jazzovým feelem:
  - swing: offbeatová osmina pozdě (triolový long-short), 0.5 = rovně .. ~0.66 = plný swing,
  - akcent na "and" (offbeat) = synkopa, downbeat střední, ostatní měkce,
  - mikro-timing: linka lehce ZA beatem (uvolněně).
Feel se odvozuje z míry swingu (víc swingu -> víc akcentu/laybacku).
"""
import os
import math

BPC = 4.0


def _swing_feel(line, swing, lay, density):
    """Vrať [(onset, délka, frac, pitch)] s aplikovaným swingem a mikro-timingem."""
    do_swing = swing > 0.505 and density == 2            # swing osmin (density 2)
    out = []
    for o, d, p in line:
        beat = math.floor(o + 1e-6)
        frac = o - beat
        no, nd = o, d
        if do_swing:
            if abs(frac) < 0.05:                         # downbeat osmina -> long
                nd = d * (swing / 0.5) * 0.9
            elif abs(frac - 0.5) < 0.05:                 # offbeat "and" -> pozdě, short
                no = beat + swing
                nd = d * ((1.0 - swing) / 0.5)
        out.append((no + lay, nd, frac, p))
    return out


def to_midi(harmony, line, out, bpm=110, density=2, swing=0.5):
    """harmony = Harmony, line = [(onset_dob, délka_dob, MIDI)] -> uloží MIDI do 'out'.
    swing = 0.5 rovně .. ~0.66 plný (feel/akcent se odvozuje z míry swingu)."""
    import mido
    feel = max(0.0, min(1.0, (swing - 0.5) / 0.14))
    lay = 0.03 * feel                                    # za beatem
    sl = _swing_feel(line, swing, lay, density)
    voics = [(b.bass, b.voicing) for b in harmony.bars]

    tpb = 240
    mid = mido.MidiFile(type=1); mid.ticks_per_beat = tpb
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=int(60000000 / bpm), time=0))
    trB, trC, trD = mido.MidiTrack(), mido.MidiTrack(), mido.MidiTrack()
    mid.tracks += [trB, trC, trD]
    evB, evC, evD = [], [], []
    for i, (bass, vo) in enumerate(voics):               # LH: bas + voicing/takt (sustain)
        t0 = i * BPC
        evB += [(t0, 1, [bass], 54), (t0 + BPC * 0.97, 0, [bass], 0)]
        evC += [(t0, 1, list(vo), 46), (t0 + BPC * 0.97, 0, list(vo), 0)]
    for no, nd, frac, p in sl:                            # RH: akcent dle pozice
        if abs(frac - 0.5) < 0.05:                        # "and" -> důraz (synkopa)
            vel = int(94 + 18 * feel)
        elif abs(frac) < 0.05:                            # downbeat -> střední
            vel = 86
        else:                                             # ostatní -> měkce
            vel = int(80 - 8 * feel)
        evD += [(no, 1, [p], max(1, min(127, vel))), (no + nd, 0, [p], 0)]

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    for tr, ev in [(trB, evB), (trC, evC), (trD, evD)]:
        fl = [(tt, ty, pp, ve) for tt, ty, ps, ve in ev for pp in ps]
        fl.sort(key=lambda x: (x[0], x[1])); last = 0.0
        for tt, ty, pp, ve in fl:
            dt = max(0, int(round((tt - last) * tpb))); last = tt
            tr.append(mido.Message('note_on' if ty else 'note_off',
                                   note=int(max(1, min(127, pp))),
                                   velocity=ve if ty else 0, time=dt))
    mid.save(out)
    return out
