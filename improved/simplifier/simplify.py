"""simplify -- celý živý Evans -> ZJEDNODUŠENÁ verze (akord + zpívající melodie).

Využívá celou pipeline (beats, chords ze spodku, čistá skyline melodie). Renderuje
CELOU skladbu (ne útržky) v reálném čase Evansova hraní: stopa MELODIE (lead line)
+ stopa COMP (detekované akordy jako rootless voicingy + bas). Výsledek = výukový
artefakt i čistá trénovací data pro modely.
"""
import mido
import numpy as np
from . import melody as M, chords as C
from voice import voicings as VOI
from voice.voicings import SEV, SCALE


def _to_sec_fn(beats):
    period = float(np.median(np.diff(beats))) if len(beats) > 1 else 0.5

    def to_sec(b):
        i = int(np.floor(b))
        if i >= len(beats) - 1:
            return float(beats[-1] + (b - (len(beats) - 1)) * period)
        if i < 0:
            return float(beats[0] + b * period)
        return float(beats[i] + (b - i) * (beats[i + 1] - beats[i]))
    return to_sec


def melody_simplify(line, keep=1.0, legato=True):
    """Reguluj simplifikaci melodie: nech KEEP podíl nejdůležitějších tónů
    (váha = délka + bonus za dobu); legato = natáhni je k dalšímu (zpívavé)."""
    if keep >= 0.999 or len(line) < 4:
        return line
    imp = [(d + 0.3 * (1.0 if abs(o - round(o)) < 0.12 else 0.0), i) for i, (o, d, p) in enumerate(line)]
    n_keep = max(2, int(round(len(line) * keep)))
    keep_idx = sorted(i for _, i in sorted(imp, reverse=True)[:n_keep])
    kept = [line[i] for i in keep_idx]
    if legato:
        kept = [(o, (kept[k + 1][0] - o) if k + 1 < len(kept) else d, p)
                for k, (o, d, p) in enumerate(kept)]
    return kept


def _func_priority(pp, span):
    """Hudební funkce tónu vůči akordu: guide (3/7) > tenze (9/#11/13) > kořen/5 > jiné."""
    ct = SEV.get(span.qual, SEV["maj7"])
    rel = (pp - span.root) % 12
    if rel in (ct[1], ct[3]):       # 3 nebo 7 = guide tóny (nejdůležitější další funkce)
        return 3
    if rel in (2, 6, 9):            # 9, #11, 13 = barevné tenze
        return 2
    if rel in ct:                   # kořen / 5
        return 1
    return 0


def _harmonize(p, on, off, beat, notes, spans, voices, conf_thr=2.5, window=14):
    """Vrch p + (voices-1) REÁLNÉ tóny pod melodií, ZDVOJENÉ JEN PŘI VYSOKÉ JISTOTĚ.

    Skóre kandidáta = hudební funkce (guide 3/7 > tenze) + jak silně ten tón fakt zní
    s melodií (překryv trvání). Přidá se jen >= conf_thr -> kde je jistota nízká,
    zůstane jednohlas (díky J.). Akord = reference pro konsonanci (chord-scale)."""
    if voices <= 1:
        return [p]
    span = next((x for x in spans if x.start <= beat < x.start + x.nbeats), None)
    if span is None:
        return [p]
    scale_pcs = set((span.root + s) % 12 for s in SCALE.get(span.qual, SCALE["maj7"]))
    span_len = max(off - on, 0.1)
    best = {}
    for n in notes:
        if not (p - window <= n.pitch < p) or n.pitch % 12 not in scale_pcs:
            continue
        ov = min(n.onset + n.dur, off) - max(n.onset, on)
        if ov <= 0:
            continue
        score = _func_priority(n.pitch, span) + min(1.0, ov / span_len)   # funkce + síla přítomnosti
        best[n.pitch] = max(best.get(n.pitch, -1), score)
    chosen = [pp for pp in sorted(best, key=lambda x: best[x], reverse=True)
              if best[pp] >= conf_thr][:voices - 1]
    return [p] + chosen


def simplified_events(a, t0=0.0, t1=1e9, melody_ch=0, comp_ch=1, comp_vel=50, mel_vel=92,
                      kind="root_vl", mel_keep=1.0, mel_voices=1, mel_conf=2.5):
    """-> [(sec, mido.Message)] zjednodušené verze ve výřezu [t0,t1].
    kind=voicing comp; mel_keep=míra melodie; mel_voices=1 jednohlas, 2-3 harmonizovaná (advanced)."""
    to_sec = _to_sec_fn(a.grid.beats)
    ev = []
    prev = None
    for s in a.spans:
        voiced = sorted(VOI.voicing_for(s.root, s.qual, kind, prev))
        # omez drift voice-leadingu (root_vl/rootless přes stovky akordů ujede z rozsahu)
        m = sum(voiced) / len(voiced)
        while m < 50:
            voiced = [x + 12 for x in voiced]; m += 12
        while m > 70:
            voiced = [x - 12 for x in voiced]; m -= 12
        prev = voiced
        if s.t1 < t0 or s.t0 > t1:
            continue
        for p in [36 + s.root % 12] + voiced:
            ev.append((s.t0, mido.Message("note_on", note=p, velocity=comp_vel, channel=comp_ch)))
            ev.append((s.t1, mido.Message("note_off", note=p, velocity=0, channel=comp_ch)))
    for o, d, p in melody_simplify(M.melody_line(a.notes, a.grid), mel_keep):
        on, off = to_sec(o), to_sec(o + d)
        if off < t0 or on > t1:
            continue
        for pp in _harmonize(p, on, off, o, a.notes, a.spans, mel_voices, mel_conf):
            ev.append((on, mido.Message("note_on", note=pp, velocity=mel_vel, channel=melody_ch)))
            ev.append((off, mido.Message("note_off", note=pp, velocity=0, channel=melody_ch)))
    return ev


# Obtížnostní profily (zafixováno s J. poslechem): comp = R-3-5-7 voice-led;
# beginner = řidší jednohlas; advanced = bohatší + funkční zdvojení reálnými tóny při jistotě.
LEVELS = {
    "beginner": dict(kind="root_vl", mel_keep=0.5, mel_voices=1),
    "advanced": dict(kind="root_vl", mel_keep=0.85, mel_voices=3, mel_conf=3.8),
}


def render_simplified(a, path, bpm=120, tpb=480, parts="full", **simp):
    """Ulož zjednodušenou skladbu jako MIDI. parts: full|melody|harmony; **simp -> simplified_events."""
    def sec2tick(s):
        return max(0, int(round(s * tpb * bpm / 60.0)))

    tracks = {"full": [("melody", 0), ("comp", 1)],
              "melody": [("melody", 0)], "harmony": [("comp", 1)]}[parts]
    allev = simplified_events(a, **simp)
    mf = mido.MidiFile(ticks_per_beat=tpb)
    meta = mido.MidiTrack(); mf.tracks.append(meta)
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    for name, ch in tracks:
        tr = mido.MidiTrack(); mf.tracks.append(tr)
        tr.append(mido.MetaMessage("track_name", name=name, time=0))
        ev = [(sec2tick(t), m) for t, m in allev if m.channel == ch]
        ev.sort(key=lambda x: (x[0], 0 if x[1].type == "note_off" else 1))
        last = 0
        for tick, msg in ev:
            msg.time = tick - last
            tr.append(msg)
            last = tick
    mf.save(path)
    return path


def build_simplified(slice_dir, out_dir):
    """Projede složku slices -> zjednodušené MIDI ve VŠECH obtížnostech (korpus)."""
    import os, glob
    from . import analyze
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for p in sorted(glob.glob(os.path.join(slice_dir, "*.mid"))):
        base = os.path.basename(p).replace(".mid", "")
        try:
            a = analyze.from_file(p)
            for lvl, params in LEVELS.items():
                render_simplified(a, os.path.join(out_dir, f"{base}__{lvl}.mid"), **params)
            print(f"  {base:>18}: {len(a.spans):>3} akordů -> {'/'.join(LEVELS)}")
            n += 1
        except Exception as e:
            print(f"  {base:>18}: CHYBA {type(e).__name__}: {e}")
    print(f"\nhotovo: {n} skladeb × {len(LEVELS)} úrovní -> {out_dir}")
    return n


if __name__ == "__main__":
    import sys
    from . import analyze
    if sys.argv[1] == "--build":
        build_simplified(sys.argv[2], sys.argv[3])
    else:
        a = analyze.from_file(sys.argv[1])
        out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/simplified.mid"
        render_simplified(a, out)
        print(f"zjednodušeno: {len(a.spans)} akordů, {len(M.melody_line(a.notes, a.grid))} tónů -> {out}")
