#!/usr/bin/env python3
"""
melody_v2.py -- generátor melodických variací, verze 2.

Změna oproti původnímu konceptu (a proč):
  Původní markov.py modeloval P(degree | kvalita_akordu, prev_degree). To stojí
  a padá na (a) správné detekci akordů a (b) správném zarovnání noty k akordu --
  a obojí je na piano2midi datech nespolehlivé (ověřeno: viz analysis/probe.py).
  Navíc to nemodelovalo rytmus, takže výstup byl pořád "dril".

  v2 modeluje MELODICKÝ POHYB nezávisle na harmonii:
      token = (interval_v_pultonech, rytmicka_trida)
      model = P(token_t | poslednich N tokenu)   s backoffem na nizsi rad
  - intervaly nepotrebuji spravny koren akordu  -> imunni vuci sumu v detekci,
  - modeluje RYTMUS (odstupy nastupu, IOI)       -> uz to neni dril,
  - nepotrebuje zarovnani noty k akordu          -> odpada druha vratka noha.

  Harmonie se dodava az pri GENEROVANI, kde ji mame pod kontrolou: kazdy ton se
  snapne na nejblizsi ton akordove/bebopove stupnice ZADANE progrese a na tezke
  dobe se cili akordovy ton (guide-tone). Tim je vysledek vzdy harmonicky a
  pritom melodicky/rytmicky ve stylu naucenem z Evanse.
"""
import os, sys, glob, random
from collections import defaultdict, Counter

HERE = os.path.dirname(__file__)
CONCEPT = os.path.join(HERE, "..", "concept", "evans_melody_gen")
sys.path.insert(0, CONCEPT)
sys.path.insert(0, os.path.join(CONCEPT, "src"))

import mido
from evans_drill import load_notes, SEV, BEBOP, lh_voicing, PC, nm
from line_extraction import extract_melody

# ---- rytmicke tridy (v dobach), kvantizace na osminovou mrizku ----
DUR_BUCKETS = [0.5, 1.0, 1.5, 2.0, 3.0]      # 8., 4., tecka-4., 1/2, tecka-1/2
def nearest_bucket(x):
    return min(DUR_BUCKETS, key=lambda b: abs(b - x))

MAX_INT = 12   # intervaly orizneme do +-oktava (vetsi = artefakt skyline)


# ----------------------------------------------------------------------------
# 1) TOKENIZACE melodie na (interval, dur_bucket)
# ----------------------------------------------------------------------------
def melody_to_tokens(mel, grid=0.5, max_gap=4.0):
    """mel = [(onset, dur, pitch)] -> [(interval, dur_bucket)].
    Kvantizuje nastupy na osminovou mrizku, intervaly a IOI prevede na tokeny.
    Dira > max_gap dob = konec fraze (preruseni retezu)."""
    if len(mel) < 2:
        return []
    # kvantizace nastupu na grid, slouceni not ve stejnem policku (ber prvni)
    q = []
    last_on = None
    for o, d, p in sorted(mel):
        on = round(o / grid) * grid
        if last_on is not None and on == last_on:
            continue
        q.append((on, p))
        last_on = on
    toks = []
    for i in range(1, len(q)):
        ioi = q[i][0] - q[i-1][0]
        if ioi <= 0:
            continue
        if ioi > max_gap:
            toks.append(None)          # marker konce fraze
            continue
        interval = q[i][1] - q[i-1][1]
        interval = max(-MAX_INT, min(MAX_INT, interval))
        toks.append((interval, nearest_bucket(ioi)))
    return toks


# ----------------------------------------------------------------------------
# 2) MODEL: Markov na tokenech s backoffem (rad N -> ... -> 0)
# ----------------------------------------------------------------------------
class MotionMarkov:
    def __init__(self, order=2):
        self.order = order
        # ctx (tuple delky k) -> Counter(token)  pro k = order..0
        self.tables = [defaultdict(Counter) for _ in range(order + 1)]
        self.starts = Counter()

    def train_on(self, toks):
        # rozdel na fraze podle None markeru
        phrase = []
        for t in toks + [None]:
            if t is None:
                self._train_phrase(phrase)
                phrase = []
            else:
                phrase.append(t)

    def _train_phrase(self, ph):
        if not ph:
            return
        self.starts[ph[0]] += 1
        for i in range(1, len(ph)):
            for k in range(self.order + 1):
                if i - k < 0:
                    continue
                ctx = tuple(ph[i-k:i])
                self.tables[k][ctx][ph[i]] += 1

    def sample(self, ctx, temperature=1.0, rng=random):
        """ctx = tuple poslednich tokenu. Backoff od nejdelsiho po nejkratsi."""
        for k in range(min(self.order, len(ctx)), -1, -1):
            sub = tuple(ctx[len(ctx)-k:]) if k > 0 else ()
            dist = self.tables[k].get(sub)
            if dist and sum(dist.values()) >= 2:
                return self._draw(dist, temperature, rng)
        # uplny fallback: nejcastejsi pohyby
        if self.tables[0].get(()):
            return self._draw(self.tables[0][()], temperature, rng)
        return (0, 0.5)

    def sample_start(self, temperature=1.0, rng=random):
        return self._draw(self.starts, temperature, rng)

    @staticmethod
    def _draw(counter, temperature, rng):
        items, weights = zip(*counter.items())
        if temperature != 1.0:
            weights = [w ** (1.0 / max(1e-6, temperature)) for w in weights]
        total = sum(weights); x = rng.random() * total; acc = 0
        for it, w in zip(items, weights):
            acc += w
            if x <= acc:
                return it
        return items[-1]

    def stats(self):
        return {
            "order": self.order,
            "ctx_order2": len(self.tables[self.order]),
            "ctx_order1": len(self.tables[1]),
            "starts": len(self.starts),
        }


def train(data_glob, order=2, skip=("be-slice19.mid",), verbose=True):
    files = sorted(glob.glob(data_glob))
    files = [f for f in files if os.path.basename(f) not in skip]
    model = MotionMarkov(order=order)
    total_tok = 0
    for f in files:
        try:
            mel = extract_melody(load_notes(f))
            toks = melody_to_tokens(mel)
            model.train_on(toks)
            total_tok += sum(1 for t in toks if t is not None)
        except Exception as e:
            if verbose:
                print(f"  preskakuji {os.path.basename(f)}: {e}")
    if verbose:
        print(f"natrenovano: {len(files)} souboru, {total_tok} tokenu pohybu, "
              f"{model.stats()}")
    return model


# ----------------------------------------------------------------------------
# 3) GENEROVANI nad ZADANOU progresi (harmonie pod kontrolou)
# ----------------------------------------------------------------------------
def scale_pitches(root, quality, lo, hi):
    pcs = set((root + o) % 12 for o in BEBOP.get(quality, [0,2,4,5,7,9,10,11]))
    return sorted(p for p in range(lo, hi + 1) if p % 12 in pcs)

def chord_tone_pitches(root, quality, lo, hi):
    pcs = set((root + o) % 12 for o in SEV.get(quality, [0,4,7,10]))
    return sorted(p for p in range(lo, hi + 1) if p % 12 in pcs)

def _pick(cands, target, cur, avoid_repeat, avoid_aba, max_leap):
    """Vyber z cands ton nejblizsi 'target', s muzikalnimi pojistkami."""
    pool = [p for p in cands if abs(p - cur) <= max_leap] or cands
    pool = sorted(pool, key=lambda x: (abs(x - target), abs(x - cur)))
    for p in pool:
        if p == avoid_repeat:
            continue
        if p == avoid_aba:
            continue
        return p
    return pool[0]

def generate(model, progression, beats_per_chord=4.0, grid_div=2,
             rh_lo=60, rh_hi=86, temperature=1.0, seed=None):
    """progression = [(root_pc, quality), ...].
    Vraci [(onset, dur, pitch)] -- rytmus i vyska generovane, harmonie ze zadane
    progrese (snap na stupnici, na tezke dobe cilime akordovy ton)."""
    rng = random.Random(seed)
    total_beats = len(progression) * beats_per_chord
    line = []
    t = 0.0
    cur = (rh_lo + rh_hi) // 2
    prev = None            # predposledni ton (anti a-b-a)
    ctx = []               # historie tokenu pro Markov
    first = True
    # zacni na akordovem tonu prvniho akordu
    r0, q0 = progression[0]
    cur = _pick(chord_tone_pitches(r0, q0, rh_lo, rh_hi), cur, cur, None, None, 99)
    line.append((0.0, beats_per_chord/grid_div*0.9, cur))
    t = 0.0
    while t < total_beats - 1e-6:
        tok = model.sample_start(temperature, rng) if first else \
              model.sample(tuple(ctx), temperature, rng)
        first = False
        interval, dur = tok
        ioi = dur
        nxt_t = t + ioi
        if nxt_t >= total_beats - 1e-6:
            break
        # ktery akord zni v case nxt_t
        ci = min(int(nxt_t // beats_per_chord), len(progression) - 1)
        r, q = progression[ci]
        chord_start = ci * beats_per_chord
        is_downbeat = (nxt_t - chord_start) < (ioi / 2)   # prvni nota v akordu
        target = cur + interval
        if is_downbeat:
            cands = chord_tone_pitches(r, q, rh_lo, rh_hi)   # guide-tone na "1"
        else:
            cands = scale_pitches(r, q, rh_lo, rh_hi)
        note = _pick(cands, target, cur,
                     avoid_repeat=cur, avoid_aba=prev, max_leap=10)
        ndur = min(ioi * 0.9, ioi - 0.05)
        line.append((nxt_t, max(0.1, ndur), note))
        prev = cur; cur = note
        ctx.append(tok); ctx = ctx[-model.order:]
        t = nxt_t
    return line


# ----------------------------------------------------------------------------
# 4) RENDER (LH akordy ze zadane progrese + RH generovana linka)
# ----------------------------------------------------------------------------
def lh_for(root, quality):
    pcs = sorted(set((root + i) % 12 for i in SEV.get(quality, [0,4,7,10])))
    return lh_voicing(pcs)

def render(progression, rh_line, path, bpm=120, beats_per_chord=4.0):
    tpb = 240
    mid = mido.MidiFile(type=1); mid.ticks_per_beat = tpb
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=int(60000000/bpm), time=0))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    trL = mido.MidiTrack(); trL.append(mido.MetaMessage('track_name', name='LH chords', time=0))
    trR = mido.MidiTrack(); trR.append(mido.MetaMessage('track_name', name='RH melody', time=0))
    mid.tracks += [trL, trR]
    evL, evR = [], []
    for i, (r, q) in enumerate(progression):
        t0 = i * beats_per_chord
        for p in lh_for(r, q):
            evL.append((t0, 1, p)); evL.append((t0 + beats_per_chord*0.96, 0, p))
    for o, d, p in rh_line:
        evR.append((o, 1, p)); evR.append((o + d, 0, p))
    for tr, ev, vel in [(trL, evL, 58), (trR, evR, 92)]:
        ev.sort(key=lambda x: (x[0], x[1])); last = 0
        for tt, typ, p in ev:
            dt = max(0, int(round((tt - last) * tpb))); last = tt
            tr.append(mido.Message('note_on' if typ else 'note_off',
                                   note=int(max(1, min(127, p))),
                                   velocity=vel if typ else 0, time=dt))
    mid.save(path)


# ----------------------------------------------------------------------------
# 5) VERIFIKACE (muzikalni sanity, ne metrika "spravnosti")
# ----------------------------------------------------------------------------
def verify(progression, line, beats_per_chord=4.0, rh_lo=60, rh_hi=86):
    pitches = [p for _, _, p in line]
    onsets = [o for o, _, _ in line]
    iois = [round(onsets[i+1]-onsets[i], 2) for i in range(len(onsets)-1)]
    ints = [abs(pitches[i+1]-pitches[i]) for i in range(len(pitches)-1)]
    steps = sum(1 for i in ints if i <= 2)
    leaps = sum(1 for i in ints if i >= 5)
    # akordovy ton na tezke dobe
    db_tot = db_hit = 0
    for o, d, p in line:
        ci = min(int(o // beats_per_chord), len(progression)-1)
        r, q = progression[ci]
        if abs((o - ci*beats_per_chord)) < 0.3:   # pobliz "1"
            db_tot += 1
            ct = set((r+x) % 12 for x in SEV.get(q, [0,4,7,10]))
            if p % 12 in ct: db_hit += 1
    inrange = all(rh_lo <= p <= rh_hi for p in pitches)
    return {
        "tonu": len(pitches),
        "rozsah": f"{min(pitches)}-{max(pitches)} (limit {rh_lo}-{rh_hi}, ok={inrange})",
        "unik_rytmu": sorted(set(iois)),
        "kroky_%": round(100*steps/max(1,len(ints))),
        "skoky>=4pt_%": round(100*leaps/max(1,len(ints))),
        "akord_ton_na_tezke_%": round(100*db_hit/max(1,db_tot)),
    }


# ----------------------------------------------------------------------------
# Hotove progrese (rucni, overene changes) pro demo
# ----------------------------------------------------------------------------
# pc: C=0 C#=1 D=2 D#=3 E=4 F=5 F#=6 G=7 G#=8 A=9 A#=10 B=11
PROGRESSIONS = {
    "iiVI_C": [(2,'m7'),(7,'7'),(0,'maj7'),(0,'maj7')],
    "minor_iiVi_A": [(11,'m7b5'),(4,'7'),(9,'m7'),(9,'m7')],
    "autumn_leaves": [          # G mol, A A B (16+8 taktu), 1 akord/takt
        (0,'m7'),(5,'7'),(10,'maj7'),(3,'maj7'),(9,'m7b5'),(2,'7'),(7,'m6'),(7,'m6'),
        (0,'m7'),(5,'7'),(10,'maj7'),(3,'maj7'),(9,'m7b5'),(2,'7'),(7,'m6'),(7,'m6'),
        (9,'m7b5'),(2,'7'),(7,'m6'),(7,'m6'),(0,'m7'),(5,'7'),(10,'maj7'),(3,'maj7'),
    ],
    "nardis_A": [               # zjednoduseny modalni A-dil (E mol / frygicky)
        (4,'m7'),(5,'maj7'),(4,'m7'),(5,'maj7'),
        (9,'m7'),(5,'maj7'),(4,'m7'),(4,'m7'),
    ],
}


if __name__ == "__main__":
    data = os.path.join(CONCEPT, "data", "be-slice*.mid")
    out_dir = os.path.join(HERE, "..", "outputs_v2")
    os.makedirs(out_dir, exist_ok=True)

    print("== trenink v2 (interval + rytmus, vsechny verze krome slice19) ==")
    model = train(data, order=2)

    demos = [("autumn_leaves", 120), ("iiVI_C", 120),
             ("minor_iiVi_A", 116), ("nardis_A", 96)]
    for name, bpm in demos:
        prog = PROGRESSIONS[name]
        print(f"\n== {name} ({len(prog)} akordu, {bpm} bpm) ==")
        for k, temp in [(1, 0.8), (2, 1.0), (3, 1.2)]:
            line = generate(model, prog, temperature=temp, seed=k)
            out = os.path.join(out_dir, f"{name}_v{k}_t{temp}.mid")
            render(prog, line, out, bpm=bpm)
            v = verify(prog, line)
            print(f"  var{k} t{temp}: {os.path.basename(out)}")
            print(f"        {v}")
    print(f"\nHotovo -> {out_dir}\\  (poslechni a porovnej varianty)")
