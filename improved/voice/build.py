"""build -- builder linky CÍL + SPOJKA (Levinovsky, teorií řízený).

Linka se STAVÍ: na doby se kladou CÍLE = akordové tóny (1. doba = guide tón,
voice-led), mezi ně přijdou SPOJKY (chromatický approach na offbeaty -> rozvod na
cíl na další době). Do dalšího taktu se přijde půltónovým approachem na jeho guide
tón. Slovník je TEORETICKÝ (nezávislý na datech); Evans 'taste' je volitelný (zatím
nepoužit -> nespoléháme na prior). Viz LINE_DEVICES.md.
"""
import random

BPC = 4.0          # dob na takt
BEATS = 4


def _nearest(pool, ref):
    return min(pool, key=lambda p: abs(p - ref)) if pool else ref


def _next_chord_tone(ctones, cur, direction, rng):
    """Další akordový tón ve směru (voice-leading kontura); fallback nejbližší."""
    side = [p for p in ctones if (p - cur) * direction > 0]
    if side:
        return min(side, key=lambda p: abs(p - cur))
    return _nearest([p for p in ctones if p != cur] or ctones, cur)


def _approach(target, frm, scale, rng, chrom=0.7):
    """Approach tón na offbeatu -> rozvod na 'target'. Půltón ze strany 'frm'
    (chrom) nebo diatonicky (krok stupnice). Hraje se PŘED cílem."""
    below = frm <= target
    if rng.random() < chrom:
        return target - 1 if below else target + 1     # chromatický náběh
    # diatonický: sousední tón stupnice ze správné strany
    idx = min(range(len(scale)), key=lambda k: abs(scale[k] - target))
    j = max(0, idx - 1) if below else min(len(scale) - 1, idx + 1)
    return scale[j]


def _scale_between(scale, a, b, frac):
    """Tón stupnice mezi a a b v poměru frac (krokové vyplnění)."""
    ia = min(range(len(scale)), key=lambda k: abs(scale[k] - a))
    ib = min(range(len(scale)), key=lambda k: abs(scale[k] - b))
    j = int(round(ia + (ib - ia) * frac))
    return scale[max(0, min(len(scale) - 1, j))]


def generate(harmony, density=2, seed=1, approach=0.7, taste=None):
    """harmony = Harmony, density = not/dobu. Vrať [(onset, délka, MIDI)].
    approach = jak často offbeat před cílem chromaticky obkličuje (0..1).
    taste = volitelný (Evans) model; None = čistě teoretický builder."""
    rng = random.Random(seed)
    npb = density * BEATS
    bars = harmony.bars
    line = []
    prev_exit = harmony.center
    for i, bar in enumerate(bars):
        sc = bar.scale
        nxt = bars[(i + 1) % len(bars)]
        entry = _nearest(bar.guides or sc, prev_exit)        # 1. doba = guide tón, voice-led
        nxt_entry = _nearest(nxt.guides or nxt.scale, entry)
        # CÍLE na doby: beat0 = entry guide tón; další = akord. tóny po kontuře
        targets = [entry]
        cur = entry; d = 1 if i % 2 == 0 else -1
        for b in range(1, BEATS):
            t = _next_chord_tone(bar.chord_tones, cur, d, rng)
            targets.append(t); cur = t
            if rng.random() < 0.4:
                d = -d                                       # měň konturu
        # POZICE: cíl na každou dobu; offbeaty = spojky
        pos = {}
        for b in range(BEATS):
            pos[b * density] = targets[b]
        for b in range(BEATS):
            a = targets[b]
            bnext = targets[b + 1] if b + 1 < BEATS else nxt_entry
            for j in range(1, density):
                p = (_approach(bnext, a, sc, rng, approach) if j == density - 1
                     else _scale_between(sc, a, bnext, j / density))
                pos[b * density + j] = p
        if npb >= 2:                                          # poslední offbeat -> approach do dalšího taktu
            pos[npb - 1] = _approach(nxt_entry, pos.get(npb - 2, targets[-1]), sc, rng, approach)
        for n in range(npb):
            line.append((i * BPC + n / density, (1.0 / density) * 0.9, pos.get(n, targets[0])))
        prev_exit = pos.get(npb - 1, targets[-1])
    return line


def annotate(harmony, line, density=2):
    """Pro náhled-tabuli: role každého tónu = 'guide'|'chord'|'approach'|'scale'.
    (guide = 3/7 na 1. době; chord = akord. tón na těžké; approach = mimo akord/stupnici)."""
    npb = density * BEATS
    roles = []
    for onset, dur, p in line:
        bi = int(onset // BPC); n = int(round((onset - bi * BPC) * density))
        bar = harmony.bars[bi] if 0 <= bi < len(harmony.bars) else None
        if bar is None:
            roles.append("scale"); continue
        on_beat = (n % density == 0)
        if on_beat and n == 0 and p in bar.guides:
            roles.append("guide")
        elif on_beat and p in bar.chord_tones:
            roles.append("chord")
        elif p not in bar.scale:
            roles.append("approach")
        else:
            roles.append("scale")
    return roles
