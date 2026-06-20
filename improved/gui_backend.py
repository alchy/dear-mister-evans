#!/usr/bin/env python3
"""
gui_backend.py -- TENKÁ FASÁDA mezi GUI a generátorem.

GUI zná JEN tohle rozhraní (ne vnitřek enginu) -> backend lze vyměnit beze změny
GUI. Poskytuje: výčet voleb (OPTIONS), generování do MIDI (generate) a přehrání
s možností Stop (play / list_ports).
"""
import os, sys, json, random, threading, traceback
from collections import defaultdict, Counter
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))

import pattern_engine as pe
import blend_markov as bl
import melody_markov as mm
import player
from arrange_chords import parse_symbol

OPTIONS = {
    "voicings": ["basic", "rootless", "color"],
    "scales":   ["auto", "bebop", "pentatonic", "jazz_color"],
    "cells":    ["run", "markov", "scale", "arpeggio"],
    "partners": ["peterson", "lines"],   # učený partner do prolnutí (Evans x ?)
    "counts":   ["vše", "2", "4", "6"],  # kolik akordů (taktů) z progrese
    "roots":    ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"],
    "start_qualities": ["m7", "maj7", "7", "m7b5"],
}
# délka/hustota melodických not -> not na dobu (sub); not na takt = sub*4
RHYTHMS = {
    "čtvrtky (4/takt)":   1,
    "osminy (8/takt)":    2,
    "trioly (12/takt)":   3,
    "šestnáctky (16/takt)": 4,
}
OPTIONS["rhythms"] = list(RHYTHMS)


def _sub(params):
    return RHYTHMS.get(str(params.get("rhythm", "")), 2)
DEFAULT_CHORDS = "Am7 D7 Gm7 Cm7 F7 Bbmaj7 Em7b5 A7"

# Vzory progresí v římských číslicích, jako (posun v půltónech od základního tónu,
# kvalita). "S" = použij uživatelem zvolenou kvalitu výchozího (base) akordu.
PROG_PATTERNS = {
    "I (jen tónika)":              [(0, "S")],
    "ii–V (dur)":                  [(0, "S"), (5, "7")],
    "ii–V–I (dur)":                [(0, "S"), (5, "7"), (10, "maj7")],
    "ii–V–I–vi (turnaround dur)":  [(0, "S"), (5, "7"), (10, "maj7"), (7, "m7")],
    "I–vi–ii–V (dur)":             [(0, "S"), (9, "m7"), (2, "m7"), (7, "7")],
    "I–VI–II–V (sekund. dom.)":    [(0, "S"), (9, "7"), (2, "7"), (7, "7")],
    "I–IV–iii–VI–ii–V (dur)":      [(0, "S"), (5, "maj7"), (4, "m7"), (9, "7"), (2, "m7"), (7, "7")],
    "I–vi–ii–V–iii–VI–ii–V (rhythm)": [(0, "S"), (9, "m7"), (2, "m7"), (7, "7"),
                                       (4, "m7"), (9, "7"), (2, "m7"), (7, "7")],
    "ii°–V–i (moll)":              [(0, "S"), (5, "7"), (10, "m7")],
    "i–iv–ii°–V (moll)":           [(0, "S"), (5, "m7"), (2, "m7b5"), (7, "7")],
    "i–VI–ii°–V (moll)":           [(0, "S"), (8, "maj7"), (2, "m7b5"), (7, "7")],
    "i–ii°–V–i (moll turnaround)": [(0, "S"), (2, "m7b5"), (7, "7"), (0, "m7")],
}
OPTIONS["patterns"] = list(PROG_PATTERNS)

_QSUFFIX = {"m7": "m7", "maj7": "maj7", "7": "7", "m7b5": "m7b5"}


def build_chords(root, quality, pattern):
    """Sestaví symboly progrese z base akordu (root+quality) a vzoru (římsky)."""
    roots = OPTIONS["roots"]
    ri = roots.index(root) if root in roots else 0
    out = []
    for off, q in PROG_PATTERNS.get(pattern, [(0, "S")]):
        qq = quality if q == "S" else q
        out.append(roots[(ri + off) % 12] + _QSUFFIX.get(qq, qq))
    return " ".join(out)

# výchozí parametry buněk (pravidlové i markov)
_CELL_CFG = {
    "run":      {"enclose": True, "enc_p": 0.5, "skip": 0.24, "rev": 0.2},
    "markov":   {"temp": 1.0},
    "scale":    {"var": 0.28, "dir": "alt"},
    "arpeggio": {"step": 2, "starts": "up3", "pickup": "chromatic", "dir": "down"},
}


def list_ports():
    try:
        import mido
        return mido.get_output_names()
    except Exception:
        return []


def default_port():
    """loopMIDI Port 1 (Vienna), jinak Wavetable, jinak první dostupný."""
    names = list_ports()
    for want in ("loopmidi port 1", "wavetable"):
        for n in names:
            if want in n.lower():
                return n
    return names[0] if names else ""


def build_recipe(params):
    """params (dict z GUI) -> recept pro pattern_engine.synth_make."""
    sub = _sub(params)
    bias = _cell_bias()                                    # MAKRO feedback (bandit) násobí váhy
    cells = {k: float(v) * bias.get(k, 1.0)
             for k, v in params.get("cells", {}).items() if float(v) > 0}
    if not cells:
        cells = {"markov": 1.0}
    return {
        "rhythm": {"sub": sub, "group": 4, "swing": 0.11 if sub == 2 else 0,
                   "in_four": bool(params.get("in_four", sub == 3))},
        "scale": params.get("scale", "bebop"),
        "voicing": params.get("voicing", "basic"),
        "target": "guide_tone",
        "range": [55, 88] if sub == 3 else [60, 86],
        "cells": cells,
        "cell_cfg": {k: dict(_CELL_CFG[k]) for k in cells if k in _CELL_CFG},
        "blend_alpha": float(params.get("alpha", 0.5)),
        "partner": params.get("partner", "peterson"),
    }


# ======================= FEEDBACK: párové ladění (B lepší než A) =======================
# Dvě úrovně podle preference uživatele (klik na regeneraci -> "tahle je lepší"):
#  A) MIKRO: preferenční model intervalů PODMÍNĚNÝ kontextem (poziční třída v taktu +
#     registrové pásmo), párově B counts++ / A counts-- (podlaha 0), přimíchaný do
#     báze (Evans/prolnutí) přes FeedbackOverlay. Base zůstává zmrazený.
#  D) MAKRO: bandit nad vahami typů buněk (recipe "cells") -> _CELL_BIAS násobí váhy.
# Zdroj pravdy = jazz_feedback.json (události + legacy "liked"); model se z něj REPLAYuje
# při startu, takže ladění přežije restart. Každá událost jde i na stdout ([FEEDBACK]).
FB_PATH = os.path.join(os.getcwd(), "jazz_feedback.json")
W_BETTER, W_WORSE = 1.0, 0.5          # přírůstek lepší / úbytek horší fráze
BANDIT_ETA = 0.15                     # krok multiplikativní úpravy vah buněk
BIAS_LO, BIAS_HI = 0.25, 4.0          # meze biasu vah buněk
_FB = None                            # preferenční CondPref (mikro, podmíněný kontextem)
_CELL_BIAS = {}                       # {typ buňky: násobitel váhy} (makro)
_N_EVENTS = 0                         # počet párových událostí (roste -> váha overlaye)


def _bump(counter, key, amount):
    """Float-count úprava s podlahou 0 (nuly mažeme -> backoff na nižší úroveň/bázi)."""
    v = counter.get(key, 0.0) + amount
    if v > 1e-9:
        counter[key] = v
    elif key in counter:
        del counter[key]


def _draw_iv(counter, temperature, rng):
    """Losuj klíč z Counteru úměrně vahám (s teplotou)."""
    items, weights = zip(*counter.items())
    if temperature != 1.0:
        weights = [w ** (1.0 / max(1e-6, temperature)) for w in weights]
    tot = sum(weights); x = rng.random() * tot; acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if x <= acc:
            return it
    return items[-1]


class CondPref:
    """Preferenční model intervalů PODMÍNĚNÝ kontextem = (poziční třída v taktu,
    registrové pásmo zdrojového tónu). Učí se z 👍/párových frází (float counts,
    podlaha 0). sample(cond) vrací interval s multi-level backoffem:
    (pozice,pásmo) -> pozice -> pásmo -> globál. starts = intervaly 1. kroku
    (aktivace overlaye + počet)."""
    def __init__(self):
        self.tab = defaultdict(Counter)        # ctx-klíč -> Counter(interval -> váha)
        self.starts = Counter()

    @staticmethod
    def _keys(pos, band):                      # od nejkonkrétnějšího po globální
        return ((pos, band), (pos,), ("band", band), ())

    def update(self, pitches, amount):
        """amount>0 posílí, amount<0 zeslabí intervaly fráze ve VŠECH úrovních kontextu."""
        n = len(pitches)
        for i in range(1, n):
            iv = max(-12, min(12, int(pitches[i]) - int(pitches[i - 1])))
            pos = pe.pos_class(i, n); band = pe.reg_band(int(pitches[i - 1]))
            for k in self._keys(pos, band):
                _bump(self.tab[k], iv, amount)
                if not self.tab[k]:
                    del self.tab[k]
            if i == 1:
                _bump(self.starts, iv, amount)

    def sample(self, cond, temperature=1.0, rng=None):
        rng = rng or random
        pos, band = cond
        for k in self._keys(pos, band):
            d = self.tab.get(k)
            if d and sum(d.values()) >= 1.0:
                return _draw_iv(d, temperature, rng)
        return None


class FeedbackOverlay:
    """Přimíchá preferenční model: s pravděpodobností w vezme interval z naučených
    preferencí (podmíněných pozicí+registrem přes cond), jinak z báze (Evans/prolnutí).
    cond = (poziční třída, registrové pásmo) z cell_markov; báze ho ignoruje."""
    def __init__(self, base, fb, w=0.4):
        self.base = base; self.fb = fb; self.w = w
        self.order = getattr(base, "order", 2)

    def sample(self, ctx, temperature=1.0, rng=None, cond=None):
        if rng is not None and self.w > 0 and cond is not None and rng.random() < self.w:
            try:
                iv = self.fb.sample(cond, temperature, rng)
                if iv is not None:
                    return (iv, 0.5)               # interval -> token (rytmus řeší cell)
            except Exception:
                pass
        return self.base.sample(ctx, temperature, rng, cond=cond)

    def sample_start(self, temperature=1.0, rng=None):
        if (rng is not None and self.w > 0 and sum(self.fb.starts.values()) > 0
                and rng.random() < self.w):
            try:
                return (_draw_iv(self.fb.starts, temperature, rng), 0.5)
            except Exception:
                pass
        return self.base.sample_start(temperature, rng)


def _bandit_update(bcell, wcell):
    """MAKRO: odměň typ buňky lepší fráze, potrestej typ horší (multiplikativně)."""
    if bcell:
        _CELL_BIAS[bcell] = max(BIAS_LO, min(BIAS_HI, _CELL_BIAS.get(bcell, 1.0) * (1 + BANDIT_ETA)))
    if wcell and wcell != bcell:
        _CELL_BIAS[wcell] = max(BIAS_LO, min(BIAS_HI, _CELL_BIAS.get(wcell, 1.0) * (1 - BANDIT_ETA)))


def _apply_event(ev):
    """Aplikuj jednu párovou událost na živý model + bias (sdíleno se startovním replayem)."""
    global _N_EVENTS
    _FB.update(ev["better"], +W_BETTER)
    if ev.get("worse"):
        _FB.update(ev["worse"], -W_WORSE)
    bc, wc = ev.get("bcell"), ev.get("wcell")
    if bc and wc and bc != wc:                            # typ buňky rozlišuje jen když se liší
        _bandit_update(bc, wc)
    _N_EVENTS += 1


def _fb_model():
    """Líně sestav preferenční model REPLAYEM jazz_feedback.json (zdroj pravdy)."""
    global _FB, _CELL_BIAS, _N_EVENTS
    if _FB is None:
        _FB = CondPref(); _CELL_BIAS = {}; _N_EVENTS = 0
        try:
            data = json.load(open(FB_PATH, encoding="utf-8"))
        except Exception:
            data = {}
        for ph in data.get("liked", []):                  # legacy absolutní 👍
            _FB.update(ph["pitches"], +W_BETTER)
        for ev in data.get("events", []):                 # párové události
            _apply_event(ev)
    return _FB


def _cell_bias():
    _fb_model()                                           # zajisti načtení
    return _CELL_BIAS


def _overlay_w():
    """Váha přimíchání roste s počtem schválení (0.2 -> strop 0.6) = postupné ladění."""
    return min(0.6, 0.2 + 0.05 * _N_EVENTS)


def feedback_count():
    return round(sum(_fb_model().starts.values()), 1)


def _persist(mutate):
    """Načti jazz_feedback.json, zmutuj (callback) a ulož. Vrátí True při úspěchu."""
    try:
        data = json.load(open(FB_PATH, encoding="utf-8")) if os.path.exists(FB_PATH) else {}
        mutate(data)
        with open(FB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        traceback.print_exc()
        return False


def _log_event(ev):
    from evans_drill import nm
    def desc(ps):
        ps = [int(p) for p in ps]
        ivs = [ps[i + 1] - ps[i] for i in range(len(ps) - 1)]
        return f"intervaly={ivs} ({' '.join(nm(p) for p in ps)})"
    parts = [f"[FEEDBACK] LEPŠÍ cell={ev.get('bcell')} {desc(ev['better'])}"]
    if ev.get("worse"):
        parts.append(f"HORŠÍ cell={ev.get('wcell')} {desc(ev['worse'])}")
    bias = {k: round(v, 2) for k, v in _CELL_BIAS.items() if abs(v - 1.0) > 1e-6}
    parts.append(f"cell_bias={bias} w={_overlay_w():.2f} preferencí={feedback_count()} událostí={_N_EVENTS}")
    msg = " | ".join(parts)
    try:                                                  # konzole nemusí umět češtinu (cp1252)
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("ascii", "replace"), flush=True)


def prefer_variant(better, worse, sub, better_cell=None, worse_cell=None):
    """Párový feedback: fráze 'better' je lepší než 'worse' (worse může být None =
    absolutní 👍). MIKRO (interval model) i MAKRO (váhy buněk) + perzistence + stdout."""
    _fb_model()                                           # zajisti načtení
    ev = {"better": [int(p) for p in better],
          "worse": [int(p) for p in (worse or [])],
          "sub": int(sub), "bcell": better_cell, "wcell": worse_cell}
    _apply_event(ev)                                      # živá mutace modelu + biasu
    _persist(lambda d: d.setdefault("events", []).append(ev))
    _log_event(ev)
    return feedback_count()


def add_liked(pitches, sub):
    """Absolutní 👍 (bez srovnání). Zachováno pro kompatibilitu; deleguje na párový."""
    return prefer_variant(pitches, None, sub)


def _model_for(recipe):
    if recipe["cells"].get("markov", 0) <= 0:
        return None
    a = recipe.get("blend_alpha", 0.5)
    base = (mm.get_model("evans") if a >= 0.999 else
            bl.get_blend(alpha=a, partner=recipe.get("partner", "peterson"),
                         verbose=False) or mm.get_model("evans"))
    fb = _fb_model()
    if base is not None and sum(fb.starts.values()) > 0:   # máš-li preference -> přimíchej
        return FeedbackOverlay(base, fb, w=_overlay_w())
    return base


def _parse_prog(params):
    """Symboly z pole akordů -> (progrese, symboly) se zkrácením na počet akordů."""
    syms = str(params["chords"]).split()
    if not syms:
        raise ValueError("prázdná progrese")
    cnt = str(params.get("count", "vše"))
    if cnt.isdigit():
        syms = syms[:int(cnt)] or syms
    return [parse_symbol(s) for s in syms], syms


def voicing_notes(params):
    """Pro náhled: [(symbol, bass, [voicing seřazený])] dle tvaru akordu.
    Voicing je seřazený -> hlas i lze párovat mezi akordy (voice-leading)."""
    import voicings as V
    prog, syms = _parse_prog(params)
    sub = _sub(params)
    center = 48 if sub == 3 else 52
    voic = V.generate_voicings(prog, center=center, style=params.get("voicing", "basic"))
    return [(syms[i], b, sorted(v)) for i, (b, v) in enumerate(voic)]


def preview_sequences(params):
    """Pro náhled per-takt: levá ruka (bas+voicing) i melodie v POŘADÍ hraní.
    -> [{label, bass, voicing[seřazený], mel[tóny v čase]}]. DRY pro obě části."""
    import voicings as V
    prog, syms = _parse_prog(params)
    recipe = build_recipe(params)
    sub = recipe["rhythm"]["sub"]
    voic = V.generate_voicings(prog, center=(48 if sub == 3 else 52),
                               style=recipe.get("voicing", "basic"))
    mel_bars = [[] for _ in prog]; used = []
    try:
        line, used = pe.synth_generate(recipe, prog, model=_model_for(recipe),
                                       seed=int(params.get("seed", 1)),
                                       bar_var=params.get("bar_var"))
        for onset, _dur, p in line:                # rozděl melodii po taktech (4 doby)
            bi = int(onset // 4.0)
            if 0 <= bi < len(prog):
                mel_bars[bi].append(p)
    except Exception:
        pass
    return [{"label": syms[i], "bass": b, "voicing": sorted(v), "mel": mel_bars[i],
             "cell": (used[i] if i < len(used) else None)}      # typ buňky -> feedback
            for i, (b, v) in enumerate(voic)]


def generate(params, out_path):
    """Vygeneruje MIDI dle parametrů. Vrátí (cesta, seznam typů buněk po taktech)."""
    prog, _ = _parse_prog(params)
    recipe = build_recipe(params)
    model = _model_for(recipe)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    _, used = pe.synth_make(recipe, prog, out_path,
                            bpm=int(params.get("bpm", 108)), model=model,
                            seed=int(params.get("seed", 1)), bar_var=params.get("bar_var"))
    return out_path, used


def _send(mid, port_name=None, stop_event=None):
    """Pošle MidiFile na port; stop_event přeruší + zhasne všechny tóny."""
    import mido
    name = port_name or default_port()
    if not name:
        raise RuntimeError("Nenalezen žádný MIDI-out port.")
    with mido.open_output(name) as out:
        for msg in mid.play():
            if stop_event is not None and stop_event.is_set():
                break
            out.send(msg)
        for ch in range(16):
            out.send(mido.Message('control_change', channel=ch, control=123, value=0))


def play(path, port_name=None, stop_event=None):
    """Přehraje MIDI soubor na zadaný port; stop_event přeruší."""
    import mido
    _send(mido.MidiFile(path), port_name, stop_event)


def describe_params(params):
    """Jednořádkový popis VŠECH parametrů z GUI (kontext pro feedback)."""
    r = build_recipe(params)
    cells = ", ".join(f"{k}={v:.2f}" for k, v in r["cells"].items())
    return ("[NASTAVENÍ] chords='{ch}' | akordů={cnt} | sub={sub} (in_four={i4}, swing={sw}) "
            "| stupnice={sc} | voicing={vo} | buňky: [{cells}] | alpha={a} partner={pa} "
            "| bpm={bpm} seed={sd}").format(
        ch=params.get("chords", ""), cnt=params.get("count", "vše"),
        sub=r["rhythm"]["sub"], i4=r["rhythm"].get("in_four"), sw=r["rhythm"].get("swing"),
        sc=r.get("scale"), vo=r.get("voicing"), cells=cells,
        a=r.get("blend_alpha"), pa=r.get("partner"),
        bpm=params.get("bpm"), sd=params.get("seed"))


def state_dict(params):
    """Serializovatelný stav: parametry z GUI + odvozený recept + souhrn."""
    return {"params": params, "recipe": build_recipe(params),
            "summary": describe_params(params)}


def describe_block(kind, label, notes):
    """Textový popis bloku (pro výpis do stdout = jednoduchý feedback kanál)."""
    from evans_drill import nm
    notes = [int(n) for n in notes]
    if kind == "chord":
        body = " ".join(nm(n) for n in notes)
        return f"[AKORD] {label} | tóny: {body} | MIDI {notes}"
    body = " ".join(f"{i+1}:{nm(n)}" for i, n in enumerate(notes))
    return f"[MELODIE] {label} | {body} | MIDI {notes}"


def play_block(kind, notes, port_name=None, stop_event=None, bpm=108, sub=3):
    """Přehraje jeden blok náhledu: kind='chord' (akord = vše naráz) nebo
    'line' (melodie = tóny v pořadí). notes = seznam MIDI not."""
    import mido
    notes = [int(n) for n in notes if n]
    if not notes:
        return
    mid = mido.MidiFile(); tr = mido.MidiTrack(); mid.tracks.append(tr)
    tpb = mid.ticks_per_beat
    tr.append(mido.MetaMessage('set_tempo', tempo=int(60000000 / max(1, bpm)), time=0))
    if kind == "chord":
        for n in notes:                                    # všechny tóny naráz
            tr.append(mido.Message('note_on', note=n, velocity=78, time=0))
        tr.append(mido.Message('note_off', note=notes[0], velocity=0, time=int(tpb * 2)))
        for n in notes[1:]:
            tr.append(mido.Message('note_off', note=n, velocity=0, time=0))
    else:                                                  # melodická linka v pořadí
        d = max(1, int(tpb / max(1, sub)))
        for n in notes:
            tr.append(mido.Message('note_on', note=n, velocity=92, time=0))
            tr.append(mido.Message('note_off', note=n, velocity=0, time=d))
    _send(mid, port_name, stop_event)
