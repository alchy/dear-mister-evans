"""licks -- sestav ii-V-I licky (changes + reálná melodie) a ulož knihovnu.

Lick = funkční jednotka (functional.find_units) + výřez melodie nad ní, vše v
DOBÁCH relativně k začátku licku -> padne rovnou do voice/ (changes + line).
"""
import os, re, json
import numpy as np
import mido
from . import analyze, functional, melody as M, chords as C, energy as EN
from voice.voicings import SCALE, SEV, voicing_for          # chord-scales + akordové tóny + voicingy


def _scale_pcs(symstr):
    r, q = C.parse_sym(symstr)
    sc = SCALE.get(q, SCALE["maj7"])
    return set((r + s) % 12 for s in sc)


def flow_score(line):
    """Skóre melodického TOKU: tóny plynoucí kontinuálně po sobě.

    Odměna za krok/chromatiku (malé intervaly), časovou návaznost (malé mezery) a
    směrové běhy (krokově/chromaticky jedním směrem). Návraty (změna směru) se
    NEtrestají — hodnotí se plynulost, ne monotónnost. (díky J.)
    """
    pts = sorted(line)
    if len(pts) < 3:
        return 0.0
    cont = []
    for a, b in zip(pts, pts[1:]):
        aiv = abs(b[2] - a[2])
        gap = b[0] - (a[0] + a[1])                  # časová mezera mezi tóny (v dobách)
        if aiv == 0:    ic = 0.5                     # návrat/repete -- ok
        elif aiv == 1:  ic = 1.0                     # chromatický krok
        elif aiv == 2:  ic = 0.95                    # diatonický krok
        elif aiv <= 4:  ic = 0.6                     # tercie
        elif aiv <= 7:  ic = 0.3                     # skok
        else:           ic = 0.05                    # velký skok -- láme tok
        tc = 1.0 if gap <= 0.15 else (0.6 if gap <= 0.6 else 0.25)   # kontinuita v čase
        cont.append(ic * tc)
    base = sum(cont) / len(cont)
    # bonus za běhy: >=3 tóny po kroku/chromaticky stejným směrem
    run, bonus = 1, 0.0
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        d1, d2 = b[2] - a[2], c[2] - b[2]
        if 0 < abs(d1) <= 2 and 0 < abs(d2) <= 2 and (d1 > 0) == (d2 > 0):
            run += 1; bonus += 0.025 * run
        else:
            run = 1
    return round(min(1.0, base + bonus), 2)


def chordtone_consonance(changes, chord_beats, line):
    """Podíl trvání melodie na skutečných AKORDOVÝCH tónech (1-3-5-7), ne jen
    stupnici. Drží disonanci líp než scale-fit (dlouhé mimo-akordové tóny = clash)."""
    bounds = np.cumsum([0] + list(chord_beats))
    syms = changes.split()
    tot = ins = 0.0
    for o, d, p in line:
        ci = int(np.clip(np.searchsorted(bounds, o, "right") - 1, 0, len(syms) - 1))
        r, q = C.parse_sym(syms[ci])
        if p % 12 in set((r + x) % 12 for x in SEV.get(q, SEV["maj7"])):
            ins += d
        tot += d
    return ins / tot if tot else 0.0


def _len_factor(n, beats):
    """Délkový sweet-spot z labelů: dobré licky ~3-7 dob; dlouhý span = roztříštěné/entropie."""
    f = 1.0
    if n < 4:     f *= 0.6        # minimal run
    if beats > 7: f *= 0.45       # moc dlouhé / přes moc akordů
    if beats < 3: f *= 0.7
    if n > 16:    f *= 0.8
    return f


def _chord_conf(a, harch, si, ei):
    """Min. „vysvětlená hmota" harmonie přes akordy licku -> spotty chord = nízké."""
    mn = 1.0
    for k in range(si, ei + 1):
        s = a.spans[k]
        seg = harch[s.start:s.start + s.nbeats].sum(0)
        if seg.sum() == 0:
            return 0.0
        scale = set((s.root + p) % 12 for p in C.SCALES[s.qual][1])
        mn = min(mn, sum(seg[p] for p in scale) / seg.sum())
    return mn


def melody_fit(changes, chord_beats, line):
    """Podíl TRVÁNÍ melodie, co padne do chord-scale aktivního akordu.

    Aplikace teorie z voice/: lick = melodie ve stupnicích akordů (+ krátké
    chromatické approach tóny). Nízký fit -> akord/segmentace špatně = random lick.
    """
    bounds = np.cumsum([0] + list(chord_beats))
    syms = changes.split()
    total = inside = 0.0
    for o, d, p in line:
        ci = int(np.clip(np.searchsorted(bounds, o, "right") - 1, 0, len(syms) - 1))
        total += d
        if p % 12 in _scale_pcs(syms[ci]):
            inside += d
    return inside / total if total else 0.0


def extract_licks(a, min_notes=5, keep_fit=0.7):
    """Analysis -> list lick dictů. Drží jen licky, kde melodie SEDÍ do chord-scale."""
    units = functional.find_units(a.spans)
    mel = M.melody_line(a.notes, a.grid)
    E = EN.energy_curve(a.notes, a.grid)                     # energie přes skladbu
    from .voices import skyline_split
    period = float(np.median(np.diff(a.grid.beats)))
    _mh, har = skyline_split(a.notes)
    harch = C.chroma_per_beat(har, a.grid.beats, period)     # pro chord-confidence
    licks = []
    for n, (typ, si, ei) in enumerate(units):
        s0, s1 = a.spans[si], a.spans[ei]
        start, end = s0.start, s1.start + s1.nbeats         # beat indexy [start,end)
        line = [(round(o - start, 3), round(d, 3), p) for (o, d, p) in mel
                if start <= o < end]
        # ořež doznívající konec fráze -> poslední akord nechá zaznít (díky J.)
        nbts = end - start
        ring = 1.0 if nbts >= 4 else 0.0
        trimmed = [t for t in line if t[0] <= nbts - ring]
        if len(trimmed) >= min_notes:
            line = trimmed
        if len(line) < min_notes:
            continue
        changes = " ".join(C.sym(a.spans[k].root, a.spans[k].qual) for k in range(si, ei + 1))
        cb = [a.spans[k].nbeats for k in range(si, ei + 1)]
        fit = melody_fit(changes, cb, line)
        if fit < keep_fit:                                  # melodie nesedí -> zahoď (random)
            continue
        conf = _chord_conf(a, harch, si, ei)                # spotty chord?
        if conf < 0.72 or int(end - start) > 9:             # spotty akord / moc dlouhé -> zahoď
            continue
        flow = flow_score(line)                             # melodický tok
        cons = chordtone_consonance(changes, cb, line)      # konsonance na akordové tóny
        lvl, arc, _ = EN.shape(E, start, end)               # energie úseku (jen kontext/dynamika)
        lenf = _len_factor(len(line), int(end - start))
        sub = min(1.0, max(0.0, (len(line) - 4) / 6.0))     # substance: krátký fragment != lick
        kp, km = a.keys[start]
        # skóre laděné na ruční labely: SUBSTANCE (délka běhu) + tok + konsonance + fit
        score = 0.26 * sub + 0.26 * flow + 0.24 * cons + 0.14 * fit + 0.10 * lenf
        licks.append({
            "id": f"{typ}_{n:03d}",
            "type": typ,
            "key": C.PC[kp] + ("m" if km == "min" else ""),
            "changes": changes,
            "chord_beats": cb,
            "n_beats": int(end - start),
            "bpm": round(float(a.grid.bpm), 1),
            "mel_fit": round(fit, 2),
            "flow": flow,
            "cons": round(cons, 2),
            "chord_conf": round(conf, 2),
            "energy": round(lvl, 2),
            "arc": arc,
            "score": round(score, 2),
            "melody": line,                                  # [(onset_beat, dur_beat, pitch)]
            "src_t": [round(s0.t0, 2), round(s1.t1, 2)],
        })
    return licks


def _classify(sub_spans):
    """Typ licku dle obsahu akordů (ii-V-I/ii-V/turnaround), jinak 'lick'."""
    for typ, si, ei in functional.find_units(sub_spans):
        if ei >= si:
            return typ
    return "lick"


def melodic_phrases(line, gap_thresh=0.75, max_beats=8, min_notes=5):
    """Rozsekej melodii na FRÁZE: hranice na pauze (mezera > gap_thresh); příliš
    dlouhé fráze (> max_beats dob) se dělí v největší vnitřní mezeře."""
    if len(line) < min_notes:
        return []
    raw, cur = [], [line[0]]
    for prev, note in zip(line, line[1:]):
        if note[0] - (prev[0] + prev[1]) > gap_thresh:
            raw.append(cur); cur = [note]
        else:
            cur.append(note)
    raw.append(cur)
    out = []

    def emit(ph):
        if len(ph) < 2:
            return
        span = ph[-1][0] + ph[-1][1] - ph[0][0]
        if span <= max_beats or len(ph) < 2 * min_notes:
            out.append(ph); return
        gaps = [ph[i + 1][0] - (ph[i][0] + ph[i][1]) for i in range(len(ph) - 1)]
        mid = len(gaps) / 2.0
        gi = max(range(len(gaps)), key=lambda i: gaps[i] - 0.02 * abs(i - mid))  # největší mezera, blíž středu
        emit(ph[:gi + 1]); emit(ph[gi + 1:])

    for ph in raw:
        emit(ph)
    return [p for p in out if len(p) >= min_notes]


def extract_phrase_licks(a, keep_fit=0.6, min_notes=5):
    """Frázový detektor: lick = souvislá plynulá fráze nad svou lokální harmonií."""
    mel = M.melody_line(a.notes, a.grid)
    spans = a.spans
    if not mel or not spans:
        return []
    from .voices import skyline_split
    period = float(np.median(np.diff(a.grid.beats)))
    _mh, har = skyline_split(a.notes)
    harch = C.chroma_per_beat(har, a.grid.beats, period)
    E = EN.energy_curve(a.notes, a.grid)
    licks = []
    for n, ph in enumerate(melodic_phrases(mel, min_notes=min_notes)):
        p0, p1 = ph[0][0], ph[-1][0] + ph[-1][1]
        si = next((k for k, s in enumerate(spans) if s.start + s.nbeats > p0), None)
        ei = next((k for k in range(len(spans) - 1, -1, -1) if spans[k].start < p1), None)
        if si is None or ei is None or ei < si:
            continue
        start, end = spans[si].start, spans[ei].start + spans[ei].nbeats
        line = [(round(o - start, 3), round(d, 3), p) for (o, d, p) in ph]
        # ořez doznívajícího konce
        ring = 1.0 if (end - start) >= 4 else 0.0
        trimmed = [t for t in line if t[0] <= (end - start) - ring]
        if len(trimmed) >= min_notes:
            line = trimmed
        if len(line) < min_notes:
            continue
        changes = " ".join(C.sym(spans[k].root, spans[k].qual) for k in range(si, ei + 1))
        cb = [spans[k].nbeats for k in range(si, ei + 1)]
        fit = melody_fit(changes, cb, line)
        if fit < keep_fit:
            continue
        conf = _chord_conf(a, harch, si, ei)
        if conf < 0.65:
            continue
        flow = flow_score(line)
        cons = chordtone_consonance(changes, cb, line)
        sub = min(1.0, max(0.0, (len(line) - 4) / 6.0))
        lenf = _len_factor(len(line), int(end - start))
        lvl, arc, _ = EN.shape(E, start, end)
        typ = _classify(spans[si:ei + 1])
        kp, km = a.keys[start]
        licks.append({
            "id": f"phrase_{n:03d}",
            "type": typ,
            "key": C.PC[kp] + ("m" if km == "min" else ""),
            "changes": changes,
            "chord_beats": cb,
            "n_beats": int(end - start),
            "bpm": round(float(a.grid.bpm), 1),
            "mel_fit": round(fit, 2),
            "flow": flow,
            "cons": round(cons, 2),
            "chord_conf": round(conf, 2),
            "energy": round(lvl, 2),
            "arc": arc,
            "score": round(0.26 * sub + 0.26 * flow + 0.24 * cons + 0.14 * fit + 0.10 * lenf, 2),
            "melody": line,
            "src_t": [round(spans[si].t0, 2), round(spans[ei].t1, 2)],
        })
    return licks


def extract_from_file(path):
    """Spoj oba: ČISTÉ ii-V-I licky (původní Evans kvalita, + bonus) jako primární;
    FRÁZOVÉ doplní jen tam, kde se s žádným ii-V-I nepřekrývají (etuda/cizí materiál)."""
    a = analyze.from_file(path)
    iv = extract_licks(a)                                    # čisté ii-V-I (kvalita)
    ph = extract_phrase_licks(a)                             # obecné fráze (pokrytí)
    for l in iv:
        l["score"] = round(min(0.99, l["score"] + 0.10), 2)  # funkční kadence = preferuj
    iv_ranges = [tuple(l["src_t"]) for l in iv]
    out = list(iv)
    for l in ph:
        a0, a1 = l["src_t"]
        if any(not (a1 <= b0 or a0 >= b1) for b0, b1 in iv_ranges):   # překryv s ii-V-I -> ii-V-I vyhrává
            continue
        out.append(l)
    out.sort(key=lambda x: -x["score"])
    return out


def save_library(licks, out_json):
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w") as f:
        json.dump({"licks": licks}, f, ensure_ascii=False, indent=1)
    return out_json


def _emit(track, ev):
    """ev = [(tick, msg)] -> seřaď (note_off před note_on na stejném ticku) a zapiš delty."""
    ev.sort(key=lambda x: (x[0], 0 if x[1].type == "note_off" else 1))
    last = 0
    for tick, msg in ev:
        msg.time = tick - last
        track.append(msg)
        last = tick


def render_lick_midi(lk, path, bpm=90, tpb=480):
    """1 lick -> MIDI: stopa MELODIE (ch0, edituješ) + stopa COMP (ch1, kontext)."""
    mf = mido.MidiFile(ticks_per_beat=tpb)
    meta = mido.MidiTrack(); mf.tracks.append(meta)
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    meta.append(mido.MetaMessage("track_name", name=lk["changes"][:60], time=0))
    # melodie (ch0)
    mt = mido.MidiTrack(); mf.tracks.append(mt)
    mt.append(mido.MetaMessage("track_name", name="melody", time=0))
    mev = []
    for o, d, p in lk["melody"]:
        on, off = int(round(o * tpb)), int(round((o + d) * tpb))
        mev.append((on, mido.Message("note_on", note=p, velocity=96, channel=0)))
        mev.append((max(off, on + 1), mido.Message("note_off", note=p, velocity=0, channel=0)))
    _emit(mt, mev)
    # comp (ch1) -- Evans rootless + voice-leading
    ct = mido.MidiTrack(); mf.tracks.append(ct)
    ct.append(mido.MetaMessage("track_name", name="comp", time=0))
    cev = []; bpos = 0.0; prev = None
    for symstr, nb in zip(lk["changes"].split(), lk["chord_beats"]):
        r, q = C.parse_sym(symstr)
        voiced = voicing_for(r, q, "rootless", prev); prev = voiced
        on, off = int(round(bpos * tpb)), int(round((bpos + nb) * tpb))
        for pp in [36 + r % 12] + voiced:
            cev.append((on, mido.Message("note_on", note=pp, velocity=60, channel=1)))
            cev.append((off, mido.Message("note_off", note=pp, velocity=0, channel=1)))
        bpos += nb
    _emit(ct, cev)
    mf.save(path)
    return path


def export_library_midi(licks, out_dir, top=None, bpm=90):
    """Ulož licky jako MIDI (řazené dle skóre, ať se nejlepší edituje první)."""
    os.makedirs(out_dir, exist_ok=True)
    ranked = sorted(licks, key=lambda x: -x.get("score", 0))
    if top:
        ranked = ranked[:top]
    for i, lk in enumerate(ranked):
        ch = re.sub(r"[^\w-]", "", lk["changes"].replace(" ", "-"))[:28]
        src = re.sub(r"[^\w]", "", lk.get("source", "").replace(".mid", ""))[-10:]
        name = f"{i:03d}_sc{int(lk.get('score',0)*100):02d}_{ch}_{src}.mid"
        render_lick_midi(lk, os.path.join(out_dir, name), bpm)
    return len(ranked)


if __name__ == "__main__":
    import sys
    from collections import Counter
    a = analyze.from_file(sys.argv[1])
    alll = extract_licks(a, keep_fit=0.0)                   # vše (i špatné) pro přehled fitu
    good = [l for l in alll if l["mel_fit"] >= 0.7]
    print(f"jednotek={len(alll)}  prošlo filtrem(fit>=0.7)={len(good)}  {dict(Counter(l['type'] for l in good))}")
    print("VŠE (fit = jak melodie sedí do chord-scale):")
    for l in sorted(alll, key=lambda x: -x["mel_fit"]):
        mark = "✓" if l["mel_fit"] >= 0.7 else " "
        print(f"  {mark} fit={l['mel_fit']:.2f} [{l['type']:>10}] {l['changes']:<26} not={len(l['melody'])}")
