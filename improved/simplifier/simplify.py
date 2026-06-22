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


BASS_FLOOR = 28      # bas nepouštět pod E1 (ochrana basu — viz hand-split, voleno s J.)


def simplified_events(a, t0=0.0, t1=1e9, melody_ch=0, comp_ch=1, comp_vel=50, mel_vel=92,
                      kind="root_vl", mel_keep=1.0, mel_voices=1, mel_conf=2.5):
    """-> [(sec, mido.Message)] zjednodušené verze ve výřezu [t0,t1].
    kind=voicing comp; mel_keep=míra melodie; mel_voices=1 jednohlas, 2-3 harmonizovaná (advanced)."""
    to_sec = _to_sec_fn(a.grid.beats)
    # 1) RH (melodie + harmonizace) NAPŘED -> comp se pak posadí POD současně znějící melodii
    rh = []
    for o, d, p in melody_simplify(M.melody_line(a.notes, a.grid), mel_keep):
        on, off = to_sec(o), to_sec(o + d)
        if off <= on:
            continue                          # defensivně: nota nulové/záporné délky -> osiřelý note_off
        for pp in _harmonize(p, on, off, o, a.notes, a.spans, mel_voices, mel_conf):
            rh.append((on, off, pp))
    # 2) comp (LH): rootless voicing + bas, voice-led, posazený POD melodii (ruce se nekříží)
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
        prev = voiced                          # voice-leading měříme PŘED posunem pod melodii
        comp = [36 + s.root % 12] + voiced
        # posaď celý comp o oktávy pod nejnižší současně znějící melodický tón; bas chráníme dnem
        lo = min((p for on, off, p in rh if min(off, s.t1) - max(on, s.t0) > 0), default=None)
        if lo is not None:
            while max(comp) >= lo and min(comp) - 12 >= BASS_FLOOR:
                comp = [x - 12 for x in comp]
        if s.t1 < t0 or s.t0 > t1:
            continue
        for p in dict.fromkeys(comp):          # dedup: bas může splynout s tónem voicingu
            ev.append((s.t0, mido.Message("note_on", note=p, velocity=comp_vel, channel=comp_ch)))
            ev.append((s.t1, mido.Message("note_off", note=p, velocity=0, channel=comp_ch)))
    # 3) emit RH (melodie) ve výřezu
    for on, off, pp in rh:
        if off < t0 or on > t1:
            continue
        ev.append((on, mido.Message("note_on", note=pp, velocity=mel_vel, channel=melody_ch)))
        ev.append((off, mido.Message("note_off", note=pp, velocity=0, channel=melody_ch)))
    return ev


# Obtížnostní profily (zafixováno s J. poslechem) -> podadresáře simplified1/2.
# comp = R-3-5-7 voice-led; simplified1 = řidší jednohlas; simplified2 = bohatší + funkční zdvojení.
LEVELS = {
    "simplified1": dict(kind="root_vl", mel_keep=0.5, mel_voices=1),                       # beginner
    "simplified2": dict(kind="root_vl", mel_keep=0.85, mel_voices=3, mel_conf=3.8),         # advanced
}


def _build_track(name, events, sec2tick):
    """[(sec, msg)] -> MidiTrack s delta časy (note_off před markerem před note_on)."""
    prio = {"note_off": 0, "note_on": 2}
    ev = sorted(((sec2tick(t), prio.get(m.type, 1), i, m) for i, (t, m) in enumerate(events)))
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("track_name", name=name, time=0))
    last = 0
    for tick, _, _, msg in ev:
        tr.append(msg.copy(time=tick - last))
        last = tick
    return tr


def render_simplified(a, path, bpm=120, tpb=480, **simp):
    """Ulož zjednodušený dvouruční MIDI: meta + CHORDS (markery akordů) + RH (melodie)
    + LH (comp + bas/kořen). Připraveno pro trénink i výukové SW. **simp -> simplified_events."""
    def sec2tick(s):
        return max(0, int(round(s * tpb * bpm / 60.0)))

    allev = simplified_events(a, **simp)
    mf = mido.MidiFile(ticks_per_beat=tpb)
    meta = mido.MidiTrack(); mf.tracks.append(meta)
    meta.append(mido.MetaMessage("track_name", name="meta", time=0))
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    # CHORDS: marker s názvem akordu (+ bas = kořen) na každé změně -> čitelná progrese
    chordev = [(s.t0, mido.MetaMessage("marker", text=f"{C.sym(s.root, s.qual)}/{C.PC[s.root % 12]}"))
               for s in a.spans]
    mf.tracks.append(_build_track("chords", chordev, sec2tick))
    mf.tracks.append(_build_track("RH (melody)", [(t, m) for t, m in allev if m.channel == 0], sec2tick))
    mf.tracks.append(_build_track("LH (comp+bass)", [(t, m) for t, m in allev if m.channel == 1], sec2tick))
    mf.save(path)
    return path


def segment_phrases(a, min_notes=4, max_beats=8):
    """Rozřež CELOU skladbu na souvislé fráze (výukové jednotky) -> [(t0, t1, changes)].
    Hook pro voice/: každá fráze = krátká progrese + linka, co tabule umí ukázat."""
    from .licks import melodic_phrases
    mel = M.melody_line(a.notes, a.grid)
    to_sec = _to_sec_fn(a.grid.beats)
    out = []
    for ph in melodic_phrases(mel, min_notes=min_notes, max_beats=max_beats):
        b0, b1 = ph[0][0], ph[-1][0] + ph[-1][1]
        syms = [C.sym(s.root, s.qual) for s in a.spans
                if s.start < b1 and s.start + s.nbeats > b0]
        out.append((to_sec(b0), to_sec(b1), " ".join(syms)))
    return out


def segment_progressions(a, max_beats=12):
    """Rozřež skladbu na chunky podle PROGRESÍ -- hranice po harmonickém ROZVAZU
    (V->I: předchozí dominanta, kořen o kvintu níž, stabilní akord). Dlouhé úseky
    bez rozvazu se rozpůlí. -> [(t0, t1, changes)] (díky J. -- chunky na progresích)."""
    spans = a.spans
    if not spans:
        return []
    cuts = [0]
    for i in range(1, len(spans)):
        p, s = spans[i - 1], spans[i]
        if p.qual == "7" and (p.root - s.root) % 12 == 7 and s.qual in ("maj7", "6", "m7", "m6", "mmaj7"):
            cuts.append(i + 1)               # konec chunku ZA rozvazovým akordem
    if cuts[-1] != len(spans):
        cuts.append(len(spans))
    cuts = sorted(set(cuts))
    # rozpůl příliš dlouhé chunky (bez rozvazu) na hranici spanu blízko středu
    final = [cuts[0]]
    for k in range(1, len(cuts)):
        si, ei = final[-1], cuts[k]
        while spans[ei - 1].start + spans[ei - 1].nbeats - spans[si].start > max_beats and ei - si > 1:
            mid = si + (ei - si) // 2
            final.append(mid); si = mid
        final.append(ei)
    final = sorted(set(final))
    chunks = []
    for k in range(len(final) - 1):
        si, ei = final[k], final[k + 1] - 1
        if ei < si:
            continue
        changes = " ".join(C.sym(spans[j].root, spans[j].qual) for j in range(si, ei + 1))
        chunks.append((spans[si].t0, spans[ei].t1, changes))
    return chunks


def build_simplified(slice_dir, out_dir):
    """Projede složku slices -> zjednodušené MIDI ve VŠECH obtížnostech (korpus)."""
    import os, glob
    from . import analyze
    for lvl in LEVELS:
        os.makedirs(os.path.join(out_dir, lvl), exist_ok=True)
    n = 0
    for p in sorted(glob.glob(os.path.join(slice_dir, "*.mid"))):
        base = os.path.basename(p).replace(".mid", "")
        try:
            a = analyze.from_file(p)
            for lvl, params in LEVELS.items():
                render_simplified(a, os.path.join(out_dir, lvl, f"{base}.mid"), **params)
            print(f"  {base:>18}: {len(a.spans):>3} akordů -> {'/'.join(LEVELS)}")
            n += 1
        except Exception as e:
            print(f"  {base:>18}: CHYBA {type(e).__name__}: {e}")
    print(f"\nhotovo: {n} skladeb -> {out_dir}/{{{','.join(LEVELS)}}}")
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
