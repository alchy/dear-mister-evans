#!/usr/bin/env python3
"""
pattern_engine.py -- OBECNÝ engine pro cvičné vzory (princip = data, ne kód).

Princip cvičení = SPEC (dict) se 4 osami:
  rhythm : {"sub": 2|3|4 (not/dobu), "group": N (délka buňky), "swing": x}
  cell   : {"type": "scale"|"arpeggio"|"markov"|..., + parametry tvaru}
  scale  : "bebop"|"pentatonic"|"auto"|"jazz_color"  (chord-scale paleta)
  target : "guide_tone"|"chord_tone"|None  (landing) + "range": [lo, hi]

Jeden engine zahraje libovolný spec nad libovolnou progresí. Nový princip, který
skládá existující buňky/stupnice = nový SPEC (data). Markov-buňka generuje variace
ve stylu naučeného segmentu. Genuinně nový pohyb = jedna malá funkce cell_*.

Příklad (triplets in four):
  {"rhythm": {"sub": 3, "group": 4, "swing": 0},
   "cell":   {"type": "arpeggio", "step": 2, "starts": "up3", "pickup": "chromatic"},
   "scale":  "jazz_color", "target": "guide_tone", "range": [55, 88]}
"""
import os, sys, random
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import scale_drill as sd


def scale_for(r, q, lo, hi, kind):
    if kind == "jazz_color":
        return sd.color_scale(r, q, lo, hi)
    return sd.jazz_scale(r, q, lo, hi, kind)


def guide_start(r, q, sc, lo, hi, direction, prev_last):
    gts = sd.guide_pitches(r, q, lo, hi)
    if not gts:
        return sc[len(sc) // 2]
    span = hi - lo
    zone = ([g for g in gts if g <= lo + span * 0.45] if direction > 0
            else [g for g in gts if g >= lo + span * 0.55]) or gts
    return min(zone, key=lambda x: abs(x - prev_last))


# ---------------- buňky (cell_*) : sekvence npb tónů ze stupnice ----------------
def cell_scale(sc, ci, direction, npb, cell, rng):
    """Stupnicový běh (převážně krok, občas tercie), anti-oscilace."""
    var = cell.get("var", 0.28); notes = [sc[ci]]
    for _ in range(1, npb):
        move = direction * (2 if rng.random() < var else 1)
        ni = max(0, min(len(sc) - 1, ci + move)); cand = sc[ni]
        if cand == notes[-1] or (len(notes) >= 2 and cand == notes[-2]):
            ni = max(0, min(len(sc) - 1, ci + direction * 2)); cand = sc[ni]
            if cand == notes[-1] or (len(notes) >= 2 and cand == notes[-2]):
                ni = max(0, min(len(sc) - 1, ci - direction)); cand = sc[ni]
        ci = ni; notes.append(cand)
    return notes


def cell_run(sc, ci, npb, cell, rng):
    """Bebopový triolový BĚH ve stylu Peterson Ex.4 (komplexní 2. část):
    převážně krok, chromatické OBKLÍČENÍ cíle zespoda na začátku doby, občasná
    tercie (arpeggio vsuvka) a změna směru, odraz od krajů rejstříku."""
    enclose = cell.get("enclose", True)      # chromatické obklíčení cíle
    enc_p = cell.get("enc_p", 0.5)           # jak často (ne na každé době)
    skip = cell.get("skip", 0.22)            # pravděpodobnost tercie (arpeggio)
    rev = cell.get("rev", 0.18)              # pravděpodobnost změny směru
    beat = cell.get("beat", 3)               # trioly = 3/dobu
    hi_i = len(sc) - 1; d = 1; notes = []
    for n in range(npb):
        if enclose and n > 0 and n % beat == 0 and rng.random() < enc_p:
            notes.append(sc[ci] - 1)         # půltón zespoda -> rozvod na cíl
            continue
        notes.append(sc[ci])
        if rng.random() < rev:
            d = -d
        step = (2 if rng.random() < skip else 1) * d
        ni = ci + step
        if ni < 1 or ni > hi_i - 1:          # odraz od krajů -> drž rejstřík
            d = -d; ni = ci - step
        ni = max(0, min(hi_i, ni))
        if sc[ni] == sc[ci]:                 # nikdy neopakuj stejný tón
            ni = max(0, min(hi_i, ci + d))
        ci = ni
    return notes


def cell_arpeggio(sc, base, npb, group, cell, rng):
    """Sestupné arpeggio v terciích po 'group' notách; začátky buněk stoupají;
    volitelný chromatický náběh na první buňce ('triplets in four')."""
    step = cell.get("step", 2); pickup = cell.get("pickup")
    notes = []
    for g in range(max(1, npb // group)):
        top = min(len(sc) - 1, base + g * step + (group - 1) * step)
        t = sc[top]
        descend = [sc[max(0, top - j * step)] for j in range(group)]
        if g == 0 and pickup == "chromatic":
            grp = [t - 1, t] + descend[1:group - 1]
        else:
            grp = descend
        notes.extend(grp)
    return notes[:npb]


def cell_markov(sc, ci, direction, npb, cell, rng, model):
    """Naučený pohyb (interval+rytmus z Markova) snapnutý na chord-scale -> variace."""
    notes = [sc[ci]]; ctx = []; cur = sc[ci]
    for _ in range(1, npb):
        if model:
            semi, _ = model.sample(tuple(ctx[-model.order:]), cell.get("temp", 1.0), rng)
            ctx.append((semi, _))
        else:
            semi = rng.choice([-2, -1, 1, 2])
        tgt = cur + semi
        ni = min(range(len(sc)), key=lambda j: abs(sc[j] - tgt))
        # anti opakování / anti a-b-a "houpání" -> pokračuj ve směru pohybu, ne zpět
        for _ in range(3):
            if sc[ni] != notes[-1] and not (len(notes) >= 2 and sc[ni] == notes[-2]):
                break
            rd = 1 if (len(notes) >= 2 and notes[-1] >= notes[-2]) else -1
            ni = max(0, min(len(sc) - 1, ni + rd))
        cur = sc[ni]; notes.append(sc[ni])
    return notes


def markov_line(spec, progression, model, rng):
    """Souvislá markov linka přes CELOU progresi (vlákno kontextu -> nevrací se,
    neopakuje bary). Na beat 1 dosedne guide tone, snap na chord-scale, anti-houpání."""
    rh = spec["rhythm"]; sub = rh["sub"]; lo, hi = spec.get("range", [60, 86])
    kind = spec.get("scale", "auto"); temp = spec["cell"].get("temp", 1.0)
    bpc = 4.0; npb = sub * 4
    line = []; ctx = []; cur = (lo + hi) // 2; prev = None
    for i, (r, q) in enumerate(progression):
        sc = scale_for(r, q, lo - 1, hi + 1, kind)
        if not sc:
            continue
        idx = lambda p: min(range(len(sc)), key=lambda k: abs(sc[k] - p))
        gts = sd.guide_pitches(r, q, lo, hi)
        for n in range(npb):
            mid = (lo + hi) / 2
            if n == 0:                                   # landing = guide tone (blíž středu)
                ref = (cur + mid) / 2
                cur = sc[idx(min(gts, key=lambda x: abs(x - ref)) if gts else cur)]
            else:
                semi, _ = model.sample(tuple(ctx[-model.order:]), temp, rng); ctx.append((semi, _))
                if cur <= lo + 4 and semi < 0:           # odraz od dna/stropu -> drž rejstřík
                    semi = -semi
                elif cur >= hi - 4 and semi > 0:
                    semi = -semi
                ni = idx(cur + semi)
                cdir = 1 if cur < mid else -1            # při zaseknutí tlač ke STŘEDU, ne na kraj
                for _ in range(3):                       # anti opakování / a-b-a houpání
                    if sc[ni] != cur and not (prev is not None and sc[ni] == prev):
                        break
                    ni = max(0, min(len(sc) - 1, ni + cdir))
                prev = cur; cur = sc[ni]
            line.append((i * bpc + n / sub, (1.0 / sub) * 0.9, cur))
    return line


def limit_leaps(line, max_leap=9):
    """Zploští velké melodické skoky (> velká sexta) o oktávu zpět do linky -> drží
    pásmo, žádné 'útěky o oktávu'. Zachová tónovou třídu. Pak dorovná no_repeats."""
    out = []
    for t, d, p in line:
        if out:
            prev = out[-1][2]
            while p - prev > max_leap:
                p -= 12
            while prev - p > max_leap:
                p += 12
        out.append((t, d, p))
    return out


def no_repeats(line):
    """Pojistka enginu: žádná nota se nikdy neopakuje 2× po sobě (i přes hranice
    taktů). Opakovaný tón posune o krok (přednostně celý tón ve směru pohybu)."""
    out = []
    for k, (t, d, p) in enumerate(line):
        if out and p == out[-1][2]:
            prev = out[-1][2]
            nxt = line[k + 1][2] if k + 1 < len(line) else None
            dr = 1 if (len(out) >= 2 and out[-1][2] >= out[-2][2]) else -1
            for shift in (dr * 2, -dr * 2, dr, -dr, 2, -2, 1, -1):
                cand = prev + shift
                if cand != prev and cand != nxt:
                    p = cand; break
        out.append((t, d, p))
    return out


def generate(spec, progression, model=None, seed=None):
    rng = random.Random(seed)
    rh = spec["rhythm"]; sub = rh["sub"]; group = rh.get("group", 4)
    lo, hi = spec.get("range", [55, 88]); bpc = 4.0; npb = sub * 4
    kind = spec.get("scale", "auto"); cell = spec["cell"]; ctype = cell["type"]
    dirmode = cell.get("dir", "alt")
    if ctype == "markov":
        return no_repeats(limit_leaps(markov_line(spec, progression, model, rng)))
    line = []; prev_last = lo + 6
    for i, (r, q) in enumerate(progression):
        sc = scale_for(r, q, lo - 1, hi + 1, kind)
        if not sc:
            continue
        idx = lambda p: min(range(len(sc)), key=lambda k: abs(sc[k] - p))
        direction = (1 if i % 2 == 0 else -1) if dirmode == "alt" else (1 if dirmode == "up" else -1)
        start_dir = 1 if ctype in ("arpeggio", "run") else direction  # běh/arpeggio zdola
        if spec.get("target", "guide_tone") == "guide_tone":
            start = guide_start(r, q, sc, lo, hi, start_dir, prev_last)
        else:
            start = sc[idx(prev_last)]
        si = idx(start)
        if ctype == "arpeggio":
            pitches = cell_arpeggio(sc, si, npb, group, cell, rng)
        elif ctype == "run":
            pitches = cell_run(sc, si, npb, cell, rng)
        elif ctype == "markov":
            pitches = cell_markov(sc, si, direction, npb, cell, rng, model)
        else:
            pitches = cell_scale(sc, si, direction, npb, cell, rng)
        for n, p in enumerate(pitches[:npb]):
            line.append((i * bpc + n / sub, (1.0 / sub) * 0.9, p))
        prev_last = pitches[-1] if pitches else prev_last
    return no_repeats(limit_leaps(line))


def _render(rh, progression, line, out, bpm, voicing="rootless"):
    sub = rh["sub"]; center = 48 if sub == 3 else 52
    voic = sd.generate_voicings(progression, center=center, style=voicing)
    sw = rh.get("swing", 0)
    if sw:
        sd.render_drill(progression, voic, line, out, bpm=bpm, swing=sw)
    else:
        ag = rh.get("group", 4) if rh.get("in_four") else 0   # 3:4 fázování
        sd.render_line(progression, voic, line, out, bpm=bpm, accent_group=ag, sub=sub)


def make(spec, progression, out, bpm=112, model=None, seed=1):
    """Vygeneruj + vyrenderuj (bas+akord/takt + pravá ruka). Vrátí linku."""
    line = generate(spec, progression, model=model, seed=seed)
    _render(spec["rhythm"], progression, line, out, bpm, spec.get("voicing", "rootless"))
    return line


# ---------------- SYNTEZÁTOR: mix typů buněk dle vah + prolnutí modelu ----------
def _wchoice(weights, rng):
    items = [(k, v) for k, v in weights.items() if v > 0]
    tot = sum(v for _, v in items); x = rng.random() * tot; acc = 0.0
    for k, v in items:
        acc += v
        if x <= acc:
            return k
    return items[-1][0]


def _bar_rng(seed, i, bv):
    """Vlastní RNG pro každý takt -> variaci jednoho taktu (bv) lze přehodit
    lokálně, ostatní takty se nezmění."""
    return random.Random((int(seed) * 1000003 + i * 9176 + int(bv) * 99991) & 0x7fffffff)


def flow_start(r, q, sc, lo, hi, prev_last):
    """Vstup taktu pro PLYNULOU návaznost: guide tón akordu nejblíž konci
    předchozího taktu (BEZ registrové zóny) -> hladké voice-leading švy a zároveň
    propagace (změna konce předchozího taktu posune i start tohoto)."""
    gts = sd.guide_pitches(r, q, lo, hi) or sc
    return min(gts, key=lambda g: abs(g - prev_last))


def land_into(progression, i, pitches, lo, hi):
    """Poziční landing: poslední tón taktu i nahradí CHROMATICKÝM příchodem ke
    guide tónu DALŠÍHO akordu nejblíž aktuální poloze -> rozvede se na 1. dobu
    dalšího taktu (jehož start se odvíjí od konce tohoto = dopředná návaznost)."""
    if len(pitches) < 2 or i + 1 >= len(progression):
        return pitches
    r2, q2 = progression[i + 1]
    gts = sd.guide_pitches(r2, q2, lo, hi)
    if not gts:
        return pitches
    tgt = min(gts, key=lambda g: abs(g - pitches[-2]))    # guide tón dalšího akordu blízko nás
    appr = tgt - 1 if pitches[-2] <= tgt else tgt + 1     # příchod zdola/shora
    out = list(pitches)
    if appr != out[-2]:                                   # neopakuj předchozí tón
        out[-1] = appr
    return out


def synth_generate(recipe, progression, model=None, seed=None, bar_var=None):
    """Skládá cvičení PO TAKTECH (každý takt vlastní RNG -> lokální variace).
    Typ buňky (scale/arpeggio/run = pravidla, markov = naučené/prolnuté) se losuje
    dle 'cells' vah; 'markov' buňka používá předaný (i prolnutý) model.
    bar_var = seznam variant po taktech (změna jednoho prvku přehodí jen ten takt)."""
    rh = recipe["rhythm"]; sub = rh["sub"]; group = rh.get("group", 4)
    lo, hi = recipe.get("range", [55, 88]); bpc = 4.0; npb = sub * 4
    kind = recipe.get("scale", "auto"); cells = recipe["cells"]
    cfg = recipe.get("cell_cfg", {})
    landing = recipe.get("target", "guide_tone") == "guide_tone"
    line = []; used = [None] * len(progression); prev_last = (lo + hi) // 2
    for i, (r, q) in enumerate(progression):
        sc = scale_for(r, q, lo - 1, hi + 1, kind)
        if not sc:
            continue
        bv = bar_var[i] if (bar_var and i < len(bar_var)) else 0
        rng = _bar_rng(seed, i, bv)                       # nezávislý RNG na takt (vnitřek)
        idx = lambda p: min(range(len(sc)), key=lambda k: abs(sc[k] - p))
        ctype = _wchoice(cells, rng); used[i] = ctype
        cell = dict(cfg.get(ctype, {})); cell["type"] = ctype
        direction = 1 if i % 2 == 0 else -1
        start_dir = 1 if ctype in ("arpeggio", "run") else direction
        # DOPŘEDNÁ NÁVAZNOST: vstup taktu = guide tón blízko konce předchozího taktu
        # (hladký šev) -> regenerace taktu se propíše do následujících (ne do předchozích).
        start = flow_start(r, q, sc, lo, hi, prev_last) if landing else (lo + hi) // 2
        si = idx(start)
        if ctype == "arpeggio":
            pitches = cell_arpeggio(sc, si, npb, group, cell, rng)
        elif ctype == "run":
            pitches = cell_run(sc, si, npb, cell, rng)
        elif ctype == "markov":
            pitches = cell_markov(sc, si, direction, npb, cell, rng, model)
        else:
            pitches = cell_scale(sc, si, direction, npb, cell, rng)
        pitches = pitches[:npb]
        if landing:                                       # poziční landing do dalšího akordu
            pitches = land_into(progression, i, pitches, lo, hi)
        seg = no_repeats(limit_leaps([(i * bpc + n / sub, (1.0 / sub) * 0.9, p)
                                      for n, p in enumerate(pitches)]))
        line.extend(seg)
        if seg:
            prev_last = seg[-1][2]                         # konec taktu -> vstup dalšího (návaznost)
    return line, used


def synth_make(recipe, progression, out, bpm=110, model=None, seed=1, bar_var=None):
    """Syntéza cvičení z receptu (váhy typů + prolnutý model) -> MIDI."""
    line, used = synth_generate(recipe, progression, model=model, seed=seed, bar_var=bar_var)
    _render(recipe["rhythm"], progression, line, out, bpm, recipe.get("voicing", "rootless"))
    return line, used


# Recepty = data: jaké patterny v jakém poměru + jak prolnout model (alpha).
RECIPES = {
    # "triplets in four" rámec; takty střídají Petersonův běh (chromatika) a
    # prolnutý Evans x Peterson markov (zpěvný pohyb). alpha = váha Evanse.
    "evans_peterson_in_four": {
        "rhythm": {"sub": 3, "group": 4, "swing": 0, "in_four": True},
        "scale": "bebop", "target": "guide_tone", "range": [55, 88],
        "voicing": "basic",   # základní 7-akord -> nejúspornější voice-leading
        "cells": {"run": 0.45, "markov": 0.55},
        "cell_cfg": {"run": {"enclose": True, "enc_p": 0.5, "skip": 0.24, "rev": 0.2},
                     "markov": {"temp": 1.0}},
        "blend_alpha": 0.5,
    },
}


# ---------------- knihovna principů (SPECY -- data, ne kód) ----------------
SPECS = {
    "drill": {
        "rhythm": {"sub": 2, "group": 4, "swing": 0.11},
        "cell": {"type": "scale", "dir": "alt", "var": 0.28},
        "scale": "auto", "target": "guide_tone", "range": [60, 86],
    },
    "triplets_in_four": {
        "rhythm": {"sub": 3, "group": 4, "swing": 0},
        "cell": {"type": "arpeggio", "step": 2, "starts": "up3", "pickup": "chromatic", "dir": "down"},
        "scale": "jazz_color", "target": "guide_tone", "range": [55, 88],
    },
    "markov_eighths": {
        "rhythm": {"sub": 2, "group": 4, "swing": 0.11},
        "cell": {"type": "markov", "temp": 1.0},
        "scale": "auto", "target": "guide_tone", "range": [60, 86],
    },
    # Oscar Peterson "Jazz Exercises" Ex.4: vzestupný triolový bebopový běh.
    "oscar_run": {   # 1. část: holý vzor (stupnicový běh nahoru, bebopová chromatika)
        "rhythm": {"sub": 3, "group": 4, "swing": 0},
        "cell": {"type": "run", "enclose": False, "skip": 0.18, "rev": 0.0},
        "scale": "bebop", "target": "guide_tone", "range": [55, 90],
    },
    "oscar_dev": {   # 2. část: rozehrané -> obklíčení + směr + arpeggio vsuvky
        "rhythm": {"sub": 3, "group": 4, "swing": 0},
        "cell": {"type": "run", "enclose": True, "enc_p": 0.5, "skip": 0.24, "rev": 0.20},
        "scale": "auto", "target": "guide_tone", "range": [55, 90],
    },
    # "Triplets in four" rytmus, ale tóny z prolnutého Evans x Peterson Markova:
    # souvislý triolový proud (3:4 fázování akcentem po 4) s mixovaným pohybem.
    "blend_in_four": {
        "rhythm": {"sub": 3, "group": 4, "swing": 0, "in_four": True},
        "cell": {"type": "markov", "temp": 1.0},
        "scale": "jazz_color", "target": "guide_tone", "range": [55, 88],
    },
}


if __name__ == "__main__":
    import argparse, chord_markov as cm
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="triplets_in_four", choices=list(SPECS))
    ap.add_argument("--chords", default="Am7 D7 Gm7 Gm7")
    ap.add_argument("--bpm", type=int, default=104)
    ap.add_argument("--render", default="outputs_pat/out.mid")
    a = ap.parse_args()
    from arrange_chords import parse_symbol
    prog = [parse_symbol(s) for s in a.chords.split()]
    model = None
    if SPECS[a.spec]["cell"]["type"] == "markov":
        import melody_markov as mm; model = mm.get_model('evans')
    os.makedirs(os.path.dirname(a.render), exist_ok=True)
    make(SPECS[a.spec], prog, a.render, bpm=a.bpm, model=model)
    print(f"spec '{a.spec}' -> {a.render}")
