"""
markov.py -- Markovův (n-gramový) generátor melodických variací nad akordy.

Doporučený PRVNÍ model (před neuronkou): na malá data sedí líp, nepřetrénuje se,
je interpretovatelný a běží bez GPU. Generuje drobné variace vzorkováním.

Reprezentace (transpozičně nezávislá!):
  token = scale-degree tónu vůči KOŘENI aktuálního akordu (0..11),
          tj. (pitch - root) % 12.
  kontext = (kvalita_akordu, předchozí_degree).
  model = P(next_degree | kvalita, prev_degree)  s backoffem na P(next_degree | kvalita).

Generování:
  jdeš akord po akordu; pro každou dobu vzorkuješ další degree z naučeného
  rozdělení, převedeš na konkrétní MIDI tón nejblíž předchozímu (plynulost),
  s omezením na akordovou stupnici (rámec z evans_drill).

Spuštění samostatně (natrénuje na data/ a vygeneruje ukázku):
    python src/markov.py
"""
import os, sys, glob, random, math
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(__file__))

from chords import load_notes, detect_chords, chord_scale_pitches, lh_voicing, chord_pcs, nm, lab
from line_extraction import extract_melody, chord_segments_with_time, align_to_chords

import mido


# ---------- trénink ----------
class MarkovMelody:
    def __init__(self):
        # P(next_degree | quality, prev_degree)
        self.cond = defaultdict(Counter)      # (quality, prev_deg) -> Counter(next_deg)
        self.back = defaultdict(Counter)      # quality -> Counter(deg)   (backoff)

    def train_on(self, aligned):
        """aligned = [(onset, dur, pitch, root, quality), ...] z jedné skladby."""
        prev_deg = None
        for o, d, p, r, q in aligned:
            deg = (p - r) % 12
            self.back[q][deg] += 1
            if prev_deg is not None:
                self.cond[(q, prev_deg)][deg] += 1
            prev_deg = deg

    def sample_degree(self, quality, prev_deg, temperature=1.0, rng=random):
        dist = self.cond.get((quality, prev_deg)) or self.back.get(quality)
        if not dist:
            return rng.choice(range(12))
        degs, weights = zip(*dist.items())
        if temperature != 1.0:
            weights = [w ** (1.0 / max(1e-6, temperature)) for w in weights]
        total = sum(weights)
        x = rng.random() * total
        acc = 0
        for dg, w in zip(degs, weights):
            acc += w
            if x <= acc:
                return dg
        return degs[-1]


def train_model(data_glob, one_per_song=True):
    """Natrénuje model na MIDI souborech. one_per_song: ber jen 1 verzi skladby."""
    files = sorted(glob.glob(data_glob))
    if one_per_song:
        # hrubá deduplikace: ber jednu z každé skupiny dle naší mapy
        keep = {"01", "02", "03", "04", "05", "06", "07"}
        files = [f for f in files if any(f.endswith(f"be-slice{k}.mid") for k in keep)]
    model = MarkovMelody()
    used = 0
    for f in files:
        try:
            notes = load_notes(f)
            mel = extract_melody(notes)
            segs = chord_segments_with_time(notes)
            aligned = align_to_chords(mel, segs)
            model.train_on(aligned)
            used += 1
        except Exception as e:
            print(f"  preskakuji {f}: {e}")
    print(f"natrénováno na {used} souborech, "
          f"{sum(len(c) for c in model.cond.values())} přechodů")
    return model


# ---------- generování ----------
def generate_line(model, progression, temperature=0.9, rh_lo=60, rh_hi=84,
                  beats_per_chord=4, notes_per_beat=2, seed=None):
    """
    progression = [(root, quality), ...]
    Vrátí melodickou linku [(onset_beats, dur_beats, pitch), ...].
    Tóny jsou omezené na akordovou stupnici a vedené plynule (nejblíž předchozímu).
    """
    rng = random.Random(seed)
    line = []
    t = 0.0
    cur_pitch = (rh_lo + rh_hi) // 2
    prev_deg = None
    step = 1.0 / notes_per_beat
    for (r, q) in progression:
        scale = chord_scale_pitches(r, q, rh_lo, rh_hi)
        for _ in range(int(beats_per_chord * notes_per_beat)):
            deg = model.sample_degree(q, prev_deg, temperature, rng)
            # kandidáti se správným degree (transpozice degree do dovolené stupnice)
            target_pc = (r + deg) % 12
            cands = [p for p in scale if p % 12 == target_pc]
            if not cands:
                cands = scale  # fallback: cokoliv ze stupnice
            # vyber nejblíž předchozímu tónu (plynulost, bez velkých skoků)
            note = min(cands, key=lambda x: abs(x - cur_pitch))
            # jemná pojistka proti opakování stejného tónu
            if note == cur_pitch:
                alt = [p for p in cands if p != cur_pitch]
                if alt:
                    note = min(alt, key=lambda x: abs(x - cur_pitch))
            line.append((t, step * 0.95, note))
            cur_pitch = note
            prev_deg = deg
            t += step
    return line


# ---------- render (LH akordy z evans_drill + RH generovaná variace) ----------
def render(progression, present_list, rh_line, path, bpm=92, beats_per_chord=4):
    tpb = 220
    mid = mido.MidiFile(type=1); mid.ticks_per_beat = tpb
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=int(60000000 / bpm), time=0))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    trL = mido.MidiTrack(); trL.append(mido.MetaMessage('track_name', name='LH chords', time=0))
    trR = mido.MidiTrack(); trR.append(mido.MetaMessage('track_name', name='RH variation', time=0))
    mid.tracks += [trL, trR]
    evL = []; evR = []
    BAR = float(beats_per_chord)
    for i, (r, q) in enumerate(progression):
        t0 = i * BAR
        voic = lh_voicing(chord_pcs(r, q, present_list[i]))
        for p in voic:
            evL.append((t0, 1, p)); evL.append((t0 + BAR * 0.96, 0, p))
    for o, d, p in rh_line:
        evR.append((o, 1, p)); evR.append((o + d, 0, p))
    for tr, ev, vel in [(trL, evL, 64), (trR, evR, 90)]:
        ev.sort(key=lambda x: (x[0], x[1])); last = 0
        for tt, typ, p in ev:
            dt = max(0, int(round((tt - last) * tpb))); last = tt
            tr.append(mido.Message('note_on' if typ else 'note_off',
                                   note=int(max(1, min(127, p))),
                                   velocity=vel if typ else 0, time=dt))
    mid.save(path)


if __name__ == "__main__":
    here = os.path.dirname(__file__)
    data_glob = os.path.join(here, "..", "data", "be-slice*.mid")
    out_dir = os.path.join(here, "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)

    print("== trénink Markovova modelu ==")
    model = train_model(data_glob)

    # vezmi akordovou progresi z jedné skladby (Nardis) jako příklad
    notes = load_notes(os.path.join(here, "..", "data", "be-slice09.mid"))
    merged = detect_chords(notes)
    progression = [(r, q) for r, q, pr in merged[:8]]    # prvních 8 akordů
    present = [pr for r, q, pr in merged[:8]]
    print("\nprogrese:", " -> ".join(lab(r, q) for r, q in progression))

    print("\n== generuji 3 variace ==")
    for k in range(1, 4):
        line = generate_line(model, progression, temperature=0.9, seed=k)
        out = os.path.join(out_dir, f"variation_{k}.mid")
        render(progression, present, line, out)
        print(f"  varianta {k}: {out}  ({len(line)} tónů)")
    print("\nHotovo. Poslechni outputs/variation_*.mid a porovnej, jak se liší.")
