#!/usr/bin/env python3
"""
analyze_segment.py -- z MIDI segmentu vytáhne FAKTA a navrhne SPEC pro
pattern_engine. Mechanickou část (subdivize, intervalový tvar, chromatika,
délka buňky) dělá kód; pojmenování principu doladí člověk/model.

Použití:  python improved/analyze_segment.py "cesta/k/segmentu.mid"
"""
import os, sys, json
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "concept", "evans_melody_gen"))
import mido
from evans_drill import nm


def load_melody(path):
    """Vrátí melodickou linku [(onset_beats, pitch)] = nejvyšší tón na nástup."""
    mid = mido.MidiFile(path); tpb = mid.ticks_per_beat or 480
    raw = []
    for tr in mid.tracks:
        t = 0; act = {}
        for m in tr:
            t += m.time
            if m.type == 'note_on' and m.velocity > 0:
                act.setdefault(m.note, []).append(t)
            elif m.type == 'note_off' or (m.type == 'note_on' and m.velocity == 0):
                if act.get(m.note):
                    st = act[m.note].pop(0); raw.append((st/tpb, (t-st)/tpb, m.note))
    raw.sort()
    # melodie = krátké tóny (ne držené akordy/bas), nejvyšší na nástup
    mel = [(o, p) for o, d, p in raw if d <= 0.9]
    top = {}
    for o, p in mel:
        k = round(o * 6) / 6                       # jemná mřížka
        top[k] = max(top.get(k, -1), p)
    return sorted(top.items())


def analyze(path):
    mel = load_melody(path)
    if len(mel) < 4:
        return {"error": "málo not"}
    onsets = [o for o, _ in mel]; pitches = [p for _, p in mel]
    iois = [round(onsets[i+1]-onsets[i], 3) for i in range(len(onsets)-1)]
    ivs = [pitches[i+1]-pitches[i] for i in range(len(pitches)-1)]
    med = sorted(iois)[len(iois)//2]
    sub = 3 if abs(med-1/3) < abs(med-0.5) and abs(med-1/3) < abs(med-0.25) else \
          (4 if abs(med-0.25) < abs(med-0.5) else 2)
    n = len(ivs)
    chrom = sum(1 for x in ivs if abs(x) == 1) / n
    thirds = sum(1 for x in ivs if abs(x) in (3, 4)) / n
    steps = sum(1 for x in ivs if abs(x) in (1, 2)) / n
    ups = [i for i, x in enumerate(ivs) if x > 2]            # skoky nahoru = reset buňky
    gaps = [ups[i+1]-ups[i] for i in range(len(ups)-1)]
    cell_len = (sorted(gaps)[len(gaps)//2] if gaps else 0)
    net = "down" if sum(ivs) < 0 else ("up" if sum(ivs) > 0 else "mixed")

    cell_type = "arpeggio" if thirds > 0.4 else ("scale" if steps > 0.5 else "markov")
    scale = "jazz_color" if chrom > 0.12 else ("bebop" if cell_type == "scale" else "auto")
    spec = {
        "rhythm": {"sub": sub, "group": cell_len or 4, "swing": 0.0 if sub == 3 else 0.11},
        "cell": {"type": cell_type, "dir": net,
                 **({"step": 2, "starts": "up3", "pickup": "chromatic"} if cell_type == "arpeggio" else {}),
                 **({"var": 0.28} if cell_type == "scale" else {})},
        "scale": scale, "target": "guide_tone", "range": [55, 88] if sub == 3 else [60, 86],
    }
    facts = {
        "not": len(mel), "median_IOI": med, "subdivize": f"{sub}/dobu",
        "chromatika_%": round(100*chrom), "tercie_%": round(100*thirds),
        "kroky_%": round(100*steps), "delka_bunky": cell_len or "?", "smer": net,
        "ukazka": " ".join(nm(p) for p in pitches[:12]),
    }
    return {"facts": facts, "suggested_spec": spec}


if __name__ == "__main__":
    r = analyze(sys.argv[1] if len(sys.argv) > 1 else "")
    if "error" in r:
        print(r["error"]); sys.exit(1)
    print("=== FAKTA ===")
    for k, v in r["facts"].items():
        print(f"  {k}: {v}")
    print("\n=== NAVRŽENÝ SPEC (pro pattern_engine) ===")
    print(json.dumps(r["suggested_spec"], ensure_ascii=False, indent=2))
