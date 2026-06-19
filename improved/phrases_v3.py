#!/usr/bin/env python3
"""
phrases_v3.py -- generator v3: FRAZE misto jednotlivych not.

Feedback na v2: "zablesky dobre harmonie, ale nic co obstoji jako celek."
Diagnoza: Markov pres lokalni intervaly ma dobry lokalni pohyb, ale zadnou
strukturu vyssiho radu -- zadne fraze, zadny navracejici se motiv, zadne
nadechnuti. Proto to nedrzi pohromadu.

v3 pridava STRUKTURU nad noty:
  1) z dat vytahne REALNE FRAZE (segmentuje melodii v pauzach/nadechnutich).
     Kazda fraze je vnitrne soudrzna (je to skutecna Evansova myslenka).
  2) frazi polozi na zadanou harmonii (snap na stupnici), zachova jeji tvar+rytmus.
  3) MOTIVICKA NAVRATNOST: v opakovanem dilu formy vrati TUTEZ frazi (re-snapnutou
     na aktualni akordy). 4-taktove fraze s nadechem mezi nimi.

Tim vznika "veta": expozice motivu -> nadech -> navrat motivu nad jinou harmonii.
"""
import os, sys, glob, random
HERE = os.path.dirname(__file__)
CONCEPT = os.path.join(HERE, "..", "concept", "evans_melody_gen")
sys.path.insert(0, CONCEPT); sys.path.insert(0, os.path.join(CONCEPT, "src"))

import mido
from evans_drill import load_notes, SEV, BEBOP, lh_voicing
from line_extraction import extract_melody
from melody_v2 import scale_pitches, chord_tone_pitches, lh_for, _pick

GRID = 0.5


# ---------------------------------------------------------------------------
# 1) EXTRAKCE FRAZI z dat
# ---------------------------------------------------------------------------
class Phrase:
    __slots__ = ("intervals", "iois", "beats", "n")
    def __init__(self, intervals, iois):
        self.intervals = intervals       # pohyb od predchozi noty (1. = 0)
        self.iois = iois                 # odstup nastupu k teto note (1. = 0)
        self.beats = sum(iois)
        self.n = len(intervals)

def extract_phrases(mel, rest_gap=1.25, min_notes=5, max_notes=16,
                    min_beats=2.5, max_beats=8.0, max_leap=8):
    """Segmentuje skyline melodii na fraze v mistech pauzy (IOI > rest_gap)."""
    q, last = [], None
    for o, d, p in sorted(mel):
        on = round(o / GRID) * GRID
        if last is not None and on == last:
            continue
        q.append((on, p)); last = on
    phrases, cur = [], []
    for i, (on, p) in enumerate(q):
        if i == 0:
            cur = [(0.0, p, 0.0)]; continue
        ioi = on - q[i-1][0]
        interval = p - q[i-1][1]
        if ioi > rest_gap or abs(interval) > max_leap:
            phrases.append(cur); cur = [(0.0, p, 0.0)]
        else:
            cur.append((interval, p, ioi))
    phrases.append(cur)
    out = []
    for ph in phrases:
        if not (min_notes <= len(ph) <= max_notes):
            continue
        intervals = [x[0] for x in ph]
        iois = [x[2] for x in ph]
        beats = sum(iois)
        if not (min_beats <= beats <= max_beats):
            continue
        # zahod monotonni (samy stejny ton) a prilis "stojate"
        if len(set(p for _, p, _ in ph)) < 3:
            continue
        out.append(Phrase(intervals, iois))
    return out

def build_library(data_glob, skip=("be-slice19.mid",)):
    files = [f for f in sorted(glob.glob(data_glob))
             if os.path.basename(f) not in skip]
    lib = []
    for f in files:
        try:
            lib += extract_phrases(extract_melody(load_notes(f)))
        except Exception as e:
            print(f"  preskakuji {os.path.basename(f)}: {e}")
    return lib


# ---------------------------------------------------------------------------
# 2) POLOZENI fraze na harmonii (zachova tvar+rytmus, snapne na akord)
# ---------------------------------------------------------------------------
def place_phrase(phrase, start_beat, start_pitch, progression,
                 beats_per_chord, rh_lo, rh_hi):
    notes = []
    t = start_beat
    cur = start_pitch
    prev = None
    for k in range(phrase.n):
        if k == 0:
            ci = min(int(t // beats_per_chord), len(progression)-1)
            r, q = progression[ci]
            cur = _pick(chord_tone_pitches(r, q, rh_lo, rh_hi),
                        start_pitch, start_pitch, None, None, 99)
            dur = min(phrase.iois[1] if phrase.n > 1 else 1.0, 1.0)
            notes.append([t, max(0.25, (phrase.iois[1] if phrase.n>1 else 1.0)*0.9), cur])
            prev = None
            continue
        t += phrase.iois[k]
        if t >= len(progression)*beats_per_chord - 1e-6:
            break
        ci = min(int(t // beats_per_chord), len(progression)-1)
        r, q = progression[ci]
        chord_start = ci * beats_per_chord
        is_downbeat = (t - chord_start) < (phrase.iois[k] / 2)
        target = cur + phrase.intervals[k]
        cands = (chord_tone_pitches(r, q, rh_lo, rh_hi) if is_downbeat
                 else scale_pitches(r, q, rh_lo, rh_hi))
        note = _pick(cands, target, cur, avoid_repeat=cur, avoid_aba=prev, max_leap=10)
        nd = phrase.iois[k+1] if k+1 < phrase.n else phrase.iois[k]
        notes.append([t, max(0.25, nd*0.9), note])
        prev = cur; cur = note
    return notes


# ---------------------------------------------------------------------------
# 3) GENEROVANI s FORMOU a motivickou navratnosti
# ---------------------------------------------------------------------------
def generate_form(lib, progression, form_labels, beats_per_chord=4.0,
                  bars_per_block=4, rh_lo=62, rh_hi=84, seed=None,
                  phrase_active_beats=11.0):
    """form_labels: stejny label = stejna fraze (motivicka navratnost).
    Kazdy blok = bars_per_block taktu; fraze hraje ~phrase_active_beats, pak nadech."""
    rng = random.Random(seed)
    block_beats = bars_per_block * beats_per_chord
    chosen = {}                       # label -> Phrase (recall)
    line = []
    last_pitch = (rh_lo + rh_hi)//2
    for bi, label in enumerate(form_labels):
        start = bi * block_beats
        if start >= len(progression)*beats_per_chord:
            break
        if label not in chosen:
            cands = [p for p in lib if p.beats <= phrase_active_beats + 1.0]
            chosen[label] = rng.choice(cands or lib)
        ph = chosen[label]
        seg = place_phrase(ph, start, last_pitch, progression,
                           beats_per_chord, rh_lo, rh_hi)
        # orizni na aktivni cast bloku (zbytek = nadech)
        seg = [n for n in seg if n[0] < start + phrase_active_beats]
        if seg:
            last_pitch = seg[-1][2]
            line += seg
    return [(o, d, p) for o, d, p in line]


# ---------------------------------------------------------------------------
# 4) RENDER (LH ze zadane progrese + RH frazova linka), s lehkym swingem
# ---------------------------------------------------------------------------
def render(progression, rh_line, path, bpm=120, beats_per_chord=4.0, swing=0.12):
    tpb = 240
    mid = mido.MidiFile(type=1); mid.ticks_per_beat = tpb
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=int(60000000/bpm), time=0))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    trL = mido.MidiTrack(); trL.append(mido.MetaMessage('track_name', name='LH chords', time=0))
    trR = mido.MidiTrack(); trR.append(mido.MetaMessage('track_name', name='RH phrases', time=0))
    mid.tracks += [trL, trR]
    evL, evR = [], []
    for i, (r, q) in enumerate(progression):
        t0 = i * beats_per_chord
        for p in lh_for(r, q):
            evL.append((t0, 1, p)); evL.append((t0 + beats_per_chord*0.96, 0, p))
    def sw(t):                              # lehky swing: zpozdi druhou osminu
        frac = t - int(t)
        return t + (swing if abs(frac-0.5) < 1e-3 else 0.0)
    for o, d, p in rh_line:
        oo = sw(o)
        evR.append((oo, 1, p)); evR.append((oo + d, 0, p))
    for tr, ev, vel in [(trL, evL, 56), (trR, evR, 94)]:
        ev.sort(key=lambda x: (x[0], x[1])); last = 0
        for tt, typ, p in ev:
            dt = max(0, int(round((tt - last) * tpb))); last = tt
            tr.append(mido.Message('note_on' if typ else 'note_off',
                                   note=int(max(1, min(127, p))),
                                   velocity=vel if typ else 0, time=dt))
    mid.save(path)


from melody_v2 import PROGRESSIONS, verify

# formy (4-taktove bloky; stejne pismeno = navrat motivu)
FORMS = {
    "autumn_leaves": ['a','b','a','b','c','d'],   # A A B C
    "iiVI_C":        ['a'],
    "minor_iiVi_A":  ['a'],
    "nardis_A":      ['a','b'],
}

if __name__ == "__main__":
    data = os.path.join(CONCEPT, "data", "be-slice*.mid")
    out_dir = os.path.join(HERE, "..", "outputs_v3")
    os.makedirs(out_dir, exist_ok=True)

    print("== v3: stavim knihovnu frazi ==")
    lib = build_library(data)
    import statistics
    print(f"  {len(lib)} frazi, prum. {statistics.mean([p.n for p in lib]):.1f} not / "
          f"{statistics.mean([p.beats for p in lib]):.1f} dob")

    for name, bpm in [("autumn_leaves",120),("nardis_A",96),("minor_iiVi_A",116)]:
        prog = PROGRESSIONS[name]; form = FORMS[name]
        print(f"\n== {name} (forma {form}) ==")
        for k in (1,2,3):
            line = generate_form(lib, prog, form, seed=k)
            out = os.path.join(out_dir, f"{name}_v{k}.mid")
            render(prog, line, out, bpm=bpm)
            print(f"  var{k}: {os.path.basename(out)}  {verify(prog, line)}")
    print(f"\nHotovo -> {out_dir}\\")
