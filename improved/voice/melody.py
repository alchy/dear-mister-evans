"""melody -- JEDEN kontextově podmíněný melodický model (scale-degree prostor).

Stav (kontext) zdrojového tónu -> rozdělení nad KROKEM v chord-scale (delta indexu).
Kontext = (metric: hlava/vnitřek/ocas, registr, degree: akordová role, poslední krok),
multi-level backoff -> robustní na malá/šumná data. Prior z Evanse přes detekci akordů.
Generuje uvnitř harmonické kostry (start na guide tónu, krok z modelu, odraz od krajů).
Feedback (fáze ④) přičte/odečte counts ve STEJNÉM modelu (volný drift).

Nahrazuje dočasný generate.trivial_line.
"""
import os, sys, glob, pickle, random
from collections import defaultdict, Counter

_HERE = os.path.dirname(__file__)
_ROOT = os.path.dirname(_HERE)                                   # improved/
_CONCEPT = os.path.join(_ROOT, "..", "concept", "evans_melody_gen")
for _p in (_ROOT, _CONCEPT, os.path.join(_CONCEPT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scale_drill as sd
import harmony as detect                       # prototyp: detect_progression (top-level)
from evans_drill import load_notes, SEV
from line_extraction import extract_melody

EVANS_DATA = os.path.join(_CONCEPT, "data", "be-slice*.mid")
MODELS_DIR = os.path.join(_ROOT, "..", "models")
PRIOR_PKL = os.path.join(MODELS_DIR, "voice_prior.pkl")

BAR = 4.0
REG_EDGES = (62, 74)            # <62 nízko | 62-73 střed | >=74 vysoko
STEP_CLAMP = 4                  # krok v indexech stupnice (±4)
LAST_CLAMP = 3


def reg_band(p):
    b = 0
    for e in REG_EDGES:
        if p >= e:
            b += 1
    return b


def metric_class(frac):
    """frac = pozice tónu v taktu (0..1) -> 0 hlava | 1 vnitřek | 2 ocas/příchod."""
    if frac < 0.15:
        return 0
    if frac > 0.85:
        return 2
    return 1


def degree_role(pitch, root, quality):
    """Akordová role tónu: '1'/'3'/'5'/'7' (akordový tón) nebo 'x' (barva/průchod)."""
    offs = SEV.get(quality, [0, 4, 7, 10])
    pc = (pitch - root) % 12
    for name, o in zip(("1", "3", "5", "7"), offs):
        if pc == o % 12:
            return name
    return "x"


def _bump(counter, key, amount):
    v = counter.get(key, 0.0) + amount
    if v > 1e-9:
        counter[key] = v
    elif key in counter:
        del counter[key]


def _draw(counter, temperature, rng):
    items, weights = zip(*counter.items())
    if temperature != 1.0:
        weights = [w ** (1.0 / max(1e-6, temperature)) for w in weights]
    tot = sum(weights); x = rng.random() * tot; acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if x <= acc:
            return it
    return items[-1]


class MelodyModel:
    """Counts kroku v chord-scale podmíněné kontextem. Stejný objekt nese Evansův
    prior i (později) feedback delty -- jeden zdroj pravdy."""
    def __init__(self):
        self.tab = defaultdict(Counter)        # ctx-klíč -> Counter(krok)

    @staticmethod
    def _keys(metric, reg, degree, last):      # od nejkonkrétnějšího po globální
        return ((metric, reg, degree, last), (metric, reg, last),
                (metric, reg), (metric,), ())

    def learn(self, metric, reg, degree, last, step, amount=1.0):
        for k in self._keys(metric, reg, degree, last):
            _bump(self.tab[k], step, amount)
            if not self.tab[k]:
                del self.tab[k]

    def sample(self, metric, reg, degree, last, temperature=1.0, rng=random, thresh=2.0):
        for k in self._keys(metric, reg, degree, last):
            d = self.tab.get(k)
            if d and sum(d.values()) >= thresh:
                return _draw(d, temperature, rng)
        return None


def _bar_steps(mel, prog):
    """Z Evansovy melodie [(o,d,p)] + detekované progrese vytáhni PO TAKTECH
    sekvence (metric, reg, degree, idx) v bebop chord-scale -> učící kroky."""
    by_bar = defaultdict(list)
    for o, d, p in mel:
        bi = int(o // BAR)
        if 0 <= bi < len(prog):
            by_bar[bi].append((o, p))
    out = []
    for bi, notes in by_bar.items():
        r, q = prog[bi]
        sc = sd.jazz_scale(r, q, 36, 96, "bebop")
        if len(sc) < 3:
            continue
        seq = []
        for o, p in sorted(notes):
            idx = min(range(len(sc)), key=lambda k: abs(sc[k] - p))
            frac = (o - bi * BAR) / BAR
            seq.append((metric_class(frac), reg_band(sc[idx]), degree_role(sc[idx], r, q), idx))
        out.append(seq)
    return out


def train_prior(verbose=True):
    files = [f for f in sorted(glob.glob(EVANS_DATA))
             if os.path.basename(f) != "be-slice19.mid"]
    m = MelodyModel(); nsteps = 0
    for f in files:
        try:
            notes = load_notes(f)
            prog, _key = detect.detect_progression(notes)
            mel = extract_melody(notes)
        except Exception as e:
            if verbose:
                print(f"  přeskakuji {os.path.basename(f)}: {e}")
            continue
        for seq in _bar_steps(mel, prog):
            last = 0
            for j in range(len(seq) - 1):
                metric, reg, degree, idx = seq[j]
                step = max(-STEP_CLAMP, min(STEP_CLAMP, seq[j + 1][3] - idx))
                if step == 0:                       # neopakovat tentýž tón
                    continue
                m.learn(metric, reg, degree, max(-LAST_CLAMP, min(LAST_CLAMP, last)), step)
                last = step
                nsteps += 1
    if verbose:
        print(f"prior: {len(files)} souborů, {nsteps} kroků, {len(m.tab)} kontextů")
    return m


def get_model(verbose=False):
    """Prior z cache, jinak natrénuj a ulož. None při chybě (-> fallback)."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    if os.path.exists(PRIOR_PKL):
        try:
            with open(PRIOR_PKL, "rb") as fh:
                return pickle.load(fh)
        except Exception:
            pass
    try:
        m = train_prior(verbose=verbose)
    except Exception:
        return None
    try:
        with open(PRIOR_PKL, "wb") as fh:
            pickle.dump(m, fh)
    except Exception:
        pass
    return m


def generate(harmony, model=None, density=2, seed=1, temperature=1.0):
    """Melodická linka v harmonické kostře: start na guide tónu, krok z modelu
    (kontextově podmíněný), odraz od krajů. model=None -> fallback krokový pohyb."""
    rng = random.Random(seed)
    npb = density * 4
    ref = (harmony.lo + harmony.hi) // 2
    line = []
    for i, bar in enumerate(harmony.bars):
        sc = bar.scale
        if len(sc) < 3:
            continue
        start = min(bar.guides, key=lambda g: abs(g - ref)) if bar.guides else sc[len(sc) // 2]
        ci = bar.degree_of(start); last = 0
        for n in range(npb):
            cur = sc[ci]
            line.append((i * BAR + n / density, (1.0 / density) * 0.9, cur))
            step = None
            if model is not None:
                step = model.sample(metric_class(n / npb), reg_band(cur),
                                    degree_role(cur, bar.root, bar.quality),
                                    max(-LAST_CLAMP, min(LAST_CLAMP, last)),
                                    temperature, rng)
            if not step:                                  # fallback / vyhni se 0
                step = rng.choice([-1, 1, 1, 2, -2])
            ni = ci + step
            if ni < 0 or ni >= len(sc):                   # odraz od krajů stupnice
                ni = ci - step
            ni = max(0, min(len(sc) - 1, ni))
            if ni == ci:                                  # nikdy neopakuj tentýž index
                ni = max(0, min(len(sc) - 1, ci + (1 if ci < len(sc) - 1 else -1)))
            last = ni - ci; ci = ni
    return line


if __name__ == "__main__":
    m = train_prior(verbose=True)
    # ukázka nejčastějších kroků v daných kontextech
    for ctx in [(0, 2, "3", 0), (1, 1, "x", 1), (2, 2, "7", -1)]:
        for k in MelodyModel._keys(*ctx):
            if k in m.tab:
                top = m.tab[k].most_common(4)
                print(f"ctx {ctx} via {k}: {top}")
                break
