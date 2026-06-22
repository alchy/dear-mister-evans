"""Regresní test kvality exportu simplified MIDI (spustitelný, bez frameworku).

Reprodukuje a hlídá tři vady nalezené při debuggingu:
  1) visící / neukončené noty (note_on bez párového note_off),
  2) překryv pravé a levé ruky (tatáž klávesa v RH i LH současně),
  3) duplicitní noty v rámci ruky (bas == tón voicingu).

Vstup = reálné Evansovy slices (lokálně v OneDrive). Když nejsou, test se přeskočí.
Spuštění:  python -m improved.simplifier.test_export_quality
"""
import os
import sys
import glob
import tempfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "improved"))

import mido
from improved.simplifier import analyze, simplify as S

SLICES_GLOB = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-Personal/Jazz Learning/LESSON - Bill Evans (Jazz Jane)/be-slice*.mid")


def _track_intervals(tr):
    """MidiTrack -> (intervaly [(on,off,pitch)], počet visících note_on)."""
    t = 0
    pend = defaultdict(list)
    iv = []
    for m in tr:
        t += m.time
        if m.type == "note_on" and m.velocity > 0:
            pend[m.note].append(t)
        elif m.type == "note_off" or (m.type == "note_on" and m.velocity == 0):
            if pend[m.note]:
                iv.append((pend[m.note].pop(0), t, m.note))
    hang = sum(len(v) for v in pend.values())
    return iv, hang


def _same_pitch_overlaps(iv):
    by_p = defaultdict(list)
    for on, off, p in iv:
        by_p[p].append((on, off))
    n = 0
    for p, lst in by_p.items():
        lst.sort()
        for i in range(len(lst) - 1):
            if lst[i + 1][0] < lst[i][1]:
                n += 1
    return n


def _handsplit(rh_iv, lh_iv, floor):
    """Překryv rukou. Vrací (samekey_celkem, porušení).

    samekey = (RH,LH) páry sdílející tutáž klávesu se časovým překryvem.
    porušení = samekey páry, kde comp JEŠTĚ MOHL klesnout o oktávu níž a netrčel by
    pod floor (nejnižší současně znějící LH nota >= floor+12) -> tvrdá chyba
    hand-splitu. Comp je "na dně", když další -12 posun poslal bas pod floor
    (tj. bas < floor+12); tam zbytkový překryv akceptujeme (melodie spadla do levé ruky)."""
    samekey = 0
    viol = 0
    for r_on, r_off, r_p in rh_iv:
        # nejnižší LH nota znějící současně s touto RH notou
        cur = [l_p for l_on, l_off, l_p in lh_iv if min(r_off, l_off) - max(r_on, l_on) > 0]
        if not cur:
            continue
        lo_lh = min(cur)
        for l_on, l_off, l_p in lh_iv:
            if l_p == r_p and min(r_off, l_off) - max(r_on, l_on) > 0:
                samekey += 1
                if lo_lh >= floor + 12:    # comp se mohl posunout o oktávu níž bez bručení -> chyba
                    viol += 1
    return samekey, viol


def measure(path):
    a = analyze.from_file(path)
    res = {}
    for lvl, params in S.LEVELS.items():
        out = os.path.join(tempfile.gettempdir(), f"_tq_{lvl}.mid")
        S.render_simplified(a, out, **params)
        mf = mido.MidiFile(out)
        rh = next((tr for tr in mf.tracks if "RH" in tr.name), None)
        lh = next((tr for tr in mf.tracks if "LH" in tr.name), None)
        rh_iv, rh_hang = _track_intervals(rh) if rh else ([], 0)
        lh_iv, lh_hang = _track_intervals(lh) if lh else ([], 0)
        samekey, viol = _handsplit(rh_iv, lh_iv, S.BASS_FLOOR)
        res[lvl] = dict(
            hang=rh_hang + lh_hang,
            rh_dup=_same_pitch_overlaps(rh_iv),
            lh_dup=_same_pitch_overlaps(lh_iv),
            samekey=samekey,
            handsplit_viol=viol,
        )
    return res


def main():
    files = sorted(glob.glob(SLICES_GLOB))
    if not files:
        print(f"SKIP: žádné vstupní slices ({SLICES_GLOB})")
        return 0
    tot = defaultdict(int)
    for f in files:
        r = measure(f)
        for lvl, m in r.items():
            for k, v in m.items():
                tot[k] += v
    print(f"přes {len(files)} slices × {len(S.LEVELS)} levelů (BASS_FLOOR={S.BASS_FLOOR}):")
    print(f"  visící/neukončené noty           : {tot['hang']}")
    print(f"  duplicita stejné pitch v RH      : {tot['rh_dup']}")
    print(f"  duplicita stejné pitch v LH      : {tot['lh_dup']}")
    print(f"  RH/LH tatáž klávesa (akcept. dole): {tot['samekey']}")
    print(f"  z toho PORUŠENÍ (comp mohl níž)  : {tot['handsplit_viol']}")
    checks = {
        "žádné visící noty": tot["hang"] == 0,
        "žádná duplicita v RH": tot["rh_dup"] == 0,
        "žádná duplicita v LH": tot["lh_dup"] == 0,
        "hand-split: comp vždy co nejníž pod melodií (žádné zbytečné překryvy)": tot["handsplit_viol"] == 0,
    }
    print()
    ok = True
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("\n=> " + ("VŠE OK" if ok else "JSOU CHYBY"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
