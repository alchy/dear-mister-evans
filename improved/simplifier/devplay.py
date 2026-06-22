"""devplay -- průběžné poslechové ukázky přes MIDI port (VST).

NEpatří do produkční pipeline; je to nástroj pro vývoj, abys slyšel, co která
fáze udělala. Hraje výřez [t0,t1] živě přes zadaný port.

  python -m simplifier.devplay click  <slice.mid> [t0 t1] [port]
"""
import sys, time
import mido
from . import io_midi, beats, chords, analyze as ana
from voice import voicings as VOI                    # skutečné Evansovy voicingy (s voice-leadingem)

PORT = "IAC Driver Bus 1"
PLAY_BPM = 90        # normalizované tempo přehrávání licků (všechny stejně)
CLICK_BEAT = 95      # B6 -- "tik" nad hudbou
CLICK_DOWN = 99      # D#7 -- akcent na první dobu
CLICK_IN = 103       # G7 -- count-in (dvě vysoké kliky před frází)


def _note(ch, pitch, vel, t_on, t_off):
    return [(t_on, mido.Message("note_on", channel=ch, note=pitch, velocity=vel)),
            (t_off, mido.Message("note_off", channel=ch, note=pitch, velocity=0))]


def play_events(events, port=PORT):
    """events: list (čas_s, mido.Message). Přehraj živě a na konci zhasni vše."""
    events = sorted(events, key=lambda e: e[0])
    with mido.open_output(port) as out:
        t_prev = 0.0
        for t, msg in events:
            dt = t - t_prev
            if dt > 0:
                time.sleep(dt)
            out.send(msg)
            t_prev = t
        for ch in range(16):
            out.send(mido.Message("control_change", channel=ch, control=123, value=0))


def click_demo(path, t0=0.0, t1=20.0, port=PORT):
    a = ana.from_file(path)
    notes, grid = a.notes, a.grid
    win_beats = [b for b in grid.beats if t0 <= b < t1]
    if not win_beats:
        print("ve výřezu nejsou beaty"); return
    dbset = set(round(x, 4) for x in a.downbeats)
    # fráze začne na PRVNÍ DOBĚ (downbeat) ve výřezu -> count-in vede přesně na "1"
    downs = [b for b in win_beats if round(b, 4) in dbset]
    align = downs[0] if downs else win_beats[0]
    import numpy as np
    period = float(np.median(np.diff(win_beats))) if len(win_beats) > 1 else 60.0 / grid.bpm
    lead = 2 * period                       # posun časové osy, ať count-in nezačne v záporu

    ev = []
    # count-in: dvě vysoké kliky v tempu, druhá padne na "1" fráze
    ev += _note(0, CLICK_IN, 112, lead - 2 * period, lead - 2 * period + 0.06)
    ev += _note(0, CLICK_IN, 112, lead - period,     lead - period + 0.06)
    # hudba od "1" do konce výřezu (ztlumená, ať klik vynikne)
    for n in notes:
        if align <= n.onset < t1:
            v = max(1, int(n.vel * 0.7))
            ev += _note(0, n.pitch, v, n.onset - align + lead, n.onset + n.dur - align + lead)
    # klik na beaty + akcent na downbeaty (od "1" dál)
    for b in win_beats:
        if b >= align:
            down = round(b, 4) in dbset
            pitch = CLICK_DOWN if down else CLICK_BEAT
            ev += _note(0, pitch, 115 if down else 72, b - align + lead, b - align + lead + 0.06)
    nb = sum(1 for b in win_beats if b >= align)
    print(f"bpm≈{grid.bpm:.1f} period≈{period:.2f}s | fráze od 1. doby @ {align:.2f}s, "
          f"{nb} beatů + count-in, hraju přes '{port}'…")
    play_events(ev, port)
    print("hotovo")


def voicing(root, qual):
    """Bas (kořen, nízko) + rootless-ish mid voicing (3-5-7-9). Jen na poslech."""
    chord_pcs = chords.SCALES[qual][0]                 # [1,3,5,7] offsety
    bass = 36 + (root % 12)                            # C2..B2 -> skutečný kořen (36 je násobek 12!)
    tones = [(root + chord_pcs[1]) % 12, (root + chord_pcs[2]) % 12,
             (root + chord_pcs[3]) % 12, (root + 2) % 12]    # 3,5,7,9
    voiced, cur = [], 57
    for pc in tones:
        cand = cur + ((pc - cur) % 12)
        if cand <= cur:
            cand += 12
        voiced.append(cand); cur = cand
    return bass, voiced


def comp_demo(path, t0=0.0, t1=30.0, port=PORT):
    a = ana.from_file(path)
    notes = a.notes
    downs = [d for d in a.downbeats if t0 <= d < t1]
    if not downs:
        print("ve výřezu nejsou downbeaty"); return
    align = downs[0]
    period = 60.0 / a.grid.bpm
    lead = 2 * period
    sh = lambda t: t - align + lead                    # posun na časovou osu přehrávání

    ev = []
    ev += _note(0, CLICK_IN, 110, lead - 2 * period, lead - 2 * period + 0.06)
    ev += _note(0, CLICK_IN, 110, lead - period, lead - period + 0.06)
    # originál (Evans) ztlumený -> A/B s naším kompem (vše kanál 0 = jistota zvuku)
    for n in notes:
        if align <= n.onset < t1:
            ev += _note(0, n.pitch, max(1, int(n.vel * 0.5)), sh(n.onset), sh(n.onset + n.dur))
    # komp: na každém downbeatu udeř akord aktivního spanu (bas + voicing) do dalšího downbeatu
    edges = downs + [t1]
    syms = []
    for k in range(len(edges) - 1):
        db, nxt = edges[k], edges[k + 1]
        span = next((s for s in a.spans if s.t0 <= db < s.t1), None)
        if span is None:
            continue
        bass, voiced = voicing(span.root, span.qual)
        ev += _note(0, bass, 82, sh(db), sh(nxt) - 0.04)
        for p in voiced:
            ev += _note(0, p, 64, sh(db), sh(nxt) - 0.04)
        syms.append(chords.sym(span.root, span.qual))
    print(f"komp {t0}-{t1}s od 1. doby @ {align:.2f}s | akordy: "
          f"{' '.join(syms[:16])}{' …' if len(syms) > 16 else ''}")
    play_events(ev, port)
    print("hotovo")


def change_demo(path, t0=0.0, t1=30.0, port=PORT):
    """Hudba + klik PŘESNĚ na detekovaných harmonických změnách (hranice akordů)."""
    a = ana.from_file(path)
    notes = a.notes
    starts = [s.t0 for s in a.spans if t0 <= s.t0 < t1]
    if not starts:
        print("ve výřezu nejsou změny"); return
    align = starts[0]
    period = 60.0 / a.grid.bpm
    lead = 2 * period
    sh = lambda t: t - align + lead
    ev = []
    ev += _note(0, CLICK_IN, 110, lead - 2 * period, lead - 2 * period + 0.06)
    ev += _note(0, CLICK_IN, 110, lead - period, lead - period + 0.06)
    for n in notes:
        if align <= n.onset < t1:
            ev += _note(0, n.pitch, max(1, int(n.vel * 0.6)), sh(n.onset), sh(n.onset + n.dur))
    syms = []
    for s in a.spans:
        if align <= s.t0 < t1:
            ev += _note(0, CLICK_DOWN, 118, sh(s.t0), sh(s.t0) + 0.07)   # klik na ZMĚNU akordu
            syms.append(chords.sym(s.root, s.qual))
    print(f"change {t0}-{t1}s od @ {align:.2f}s | {len(syms)} změn: "
          f"{' '.join(syms[:16])}{' …' if len(syms) > 16 else ''}")
    play_events(ev, port)
    print("hotovo")


def _lick_events(lk, t0):
    """Eventy jednoho licku od času t0: count-in + comp + REÁLNÁ melodie. -> (ev, t_end)."""
    spb = 60.0 / PLAY_BPM                            # normalizováno na PLAY_BPM (stejná rychlost)
    lead = t0 + 2 * spb
    ev = []
    ev += _note(0, CLICK_IN, 108, t0, t0 + 0.06)
    ev += _note(0, CLICK_IN, 108, t0 + spb, t0 + spb + 0.06)
    bpos = 0.0
    prev = None
    for symstr, nb in zip(lk["changes"].split(), lk["chord_beats"]):
        r, q = chords.parse_sym(symstr)
        voiced = VOI.voicing_for(r, q, "rootless", prev)   # Evans rootless + voice-leading
        prev = voiced
        bass = 36 + (r % 12)
        t_on, t_off = lead + bpos * spb, lead + (bpos + nb) * spb - 0.05
        ev += _note(0, bass, 68, t_on, t_off)
        for p in voiced:
            ev += _note(0, p, 50, t_on, t_off)
        bpos += nb
    mvel = int(64 + 46 * lk.get("energy", 0.6))     # dynamika melodie ~ energie licku
    for o, d, p in lk["melody"]:
        ev += _note(0, p, mvel, lead + o * spb, lead + (o + d) * spb)
    return ev, lead + lk["n_beats"] * spb


def lick_demo(path, idx=0, port=PORT):
    from . import licks as L
    licks = L.extract_from_file(path)
    if not licks:
        print("žádné licky"); return
    lk = licks[int(idx) % len(licks)]
    ev, _ = _lick_events(lk, 0.3)
    print(f"lick #{idx} [{lk['type']}] {lk['changes']}  ({lk['key']}, {len(lk['melody'])} not) -> '{port}'")
    play_events(ev, port)
    print("hotovo")


def alllicks_demo(path, port=PORT, limit=14):
    from . import licks as L
    licks = sorted(L.extract_from_file(path), key=lambda x: -x.get("score", 0))[:int(limit)]
    if not licks:
        print("žádné licky"); return
    print(f"přehraju {len(licks)} licků (nejlepší SKÓRE první, dynamika ~ energie) přes '{port}':")
    ev = []
    t = 0.3
    for i, lk in enumerate(licks):
        print(f"  #{i:>2} skóre={lk.get('score', 0):.2f} (tok={lk.get('flow', 0):.2f} "
              f"fit={lk.get('mel_fit', 0):.2f} E={lk.get('energy', 0):.2f} {lk.get('arc', ''):>7}) "
              f"[{lk['type']:>7}] {lk['changes']}")
        e, t = _lick_events(lk, t)
        ev += e
        t += 1.1                                    # mezera mezi licky
    play_events(ev, port)
    print("hotovo")


def label_demo(path, port=PORT):
    """Přehraj licky v POŘADÍ SKLADBY (stabilní indexy) k ručnímu olabelování ok/bad."""
    from . import licks as L
    licks = L.extract_from_file(path)                # source order (stabilní)
    if not licks:
        print("žádné licky"); return
    print(f"LABELOVÁNÍ — {len(licks)} licků v pořadí skladby. Ke každému indexu napiš ok / bad:")
    print(f"{'#':>2}  {'typ':>8}  {'změny':<26} {'not':>3}  tok  fit   E   arc")
    for i, lk in enumerate(licks):
        print(f"{i:>2}  {lk['type']:>8}  {lk['changes']:<26} {len(lk['melody']):>3}  "
              f"{lk['flow']:.2f} {lk['mel_fit']:.2f} {lk['energy']:.2f} {lk['arc']}")
    print(f"\nhraju přes '{port}' (počítadlo = nový lick, dle pořadí výše)…")
    ev = []
    t = 0.3
    for lk in licks:
        e, t = _lick_events(lk, t)
        ev += e
        t += 1.6                                     # mezera na olabelování
    play_events(ev, port)
    print("hotovo")


def picks_demo(path, idxs, port=PORT):
    """Přehraj jen vybrané indexy (čárkou) v pořadí skladby."""
    from . import licks as L
    licks = L.extract_from_file(path)
    sel = [int(x) for x in str(idxs).split(",") if x.strip() != ""]
    print(f"přehraju vybrané {sel} přes '{port}':")
    ev = []
    t = 0.3
    for i in sel:
        lk = licks[i % len(licks)]
        print(f"  #{i} [{lk['type']:>7}] {lk['changes']:<22} ({len(lk['melody'])} not)")
        e, t = _lick_events(lk, t)
        ev += e
        t += 1.4
    play_events(ev, port)
    print("hotovo")


def lib_demo(json_path, n=12, port=PORT):
    """Přehraj z knihovny: TOP N (číslo) nebo konkrétní indexy v pořadí skóre (např. '0,6')."""
    import json
    with open(json_path) as f:
        lib = json.load(f)["licks"]
    libs = sorted(lib, key=lambda x: -x.get("score", 0))
    if isinstance(n, str) and "," in n:
        lib = [libs[int(i)] for i in n.split(",")]
    else:
        lib = libs[:int(n)]
    print(f"přehraju {len(lib)} z knihovny přes '{port}':")
    ev = []
    t = 0.3
    for i, lk in enumerate(lib):
        print(f"  #{i:>2} skóre={lk['score']:.2f} [{lk['type']:>7}] {lk['changes']:<20} "
              f"{len(lk['melody']):>2}not  {lk.get('source', '')}")
        e, t = _lick_events(lk, t)
        ev += e
        t += 1.3
    play_events(ev, port)
    print("hotovo")


if __name__ == "__main__":
    mode = sys.argv[1]
    path = sys.argv[2]
    if mode == "phrases":
        from . import licks as L, analyze as A
        a = A.from_file(path)
        ph = sorted(L.extract_phrase_licks(a), key=lambda x: -x["score"])
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        port = sys.argv[4] if len(sys.argv) > 4 else PORT
        print(f"FRÁZOVÉ licky — top {min(n, len(ph))} z {len(ph)} přes '{port}':")
        ev = []
        t = 0.3
        for i, lk in enumerate(ph[:n]):
            print(f"  #{i:>2} sc={lk['score']:.2f} tok={lk['flow']:.2f} cons={lk['cons']:.2f} "
                  f"n={len(lk['melody']):>2} [{lk['type']:>10}] {lk['changes']}")
            e, t = _lick_events(lk, t)
            ev += e
            t += 1.4
        play_events(ev, port)
        print("hotovo")
    elif mode == "lib":
        n = sys.argv[3] if len(sys.argv) > 3 else 12
        port = sys.argv[4] if len(sys.argv) > 4 else PORT
        lib_demo(path, n, port)
    elif mode == "picks":
        port = sys.argv[4] if len(sys.argv) > 4 else PORT
        picks_demo(path, sys.argv[3], port)
    elif mode == "label":
        port = sys.argv[3] if len(sys.argv) > 3 else PORT
        label_demo(path, port)
    elif mode == "lick":
        idx = sys.argv[3] if len(sys.argv) > 3 else 0
        port = sys.argv[4] if len(sys.argv) > 4 else PORT
        lick_demo(path, idx, port)
    elif mode == "alllicks":
        port = sys.argv[3] if len(sys.argv) > 3 else PORT
        alllicks_demo(path, port)
    else:
        t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
        t1 = float(sys.argv[4]) if len(sys.argv) > 4 else (20.0 if mode == "click" else 30.0)
        port = sys.argv[5] if len(sys.argv) > 5 else PORT
        {"click": click_demo, "comp": comp_demo, "change": change_demo}[mode](path, t0, t1, port)
